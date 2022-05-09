#!/bin/bash

# run with venv2

# manually copy the new train and valid simplified jsonl files to this location:
dataflow_dialogues_dir="output/dataflow_dialogues"
mkdir -p "${dataflow_dialogues_dir}"

# compute dialog stats

dataflow_dialogues_stats_dir="output/dataflow_dialogues_stats"
mkdir -p "${dataflow_dialogues_stats_dir}"
python -m dataflow.analysis.compute_data_statistics \
    --dataflow_dialogues_dir ${dataflow_dialogues_dir} \
    --subset train valid \
    --outdir ${dataflow_dialogues_stats_dir}

# prepare text for onmt
#   note - the added --simplify_format flag - use for simplified format!

onmt_text_data_dir="output/onmt_text_data"
mkdir -p "${onmt_text_data_dir}"

rm -f output/onmt_text_data/*

for subset in "train" "valid"; do
    python -m dataflow.onmt_helpers.create_onmt_text_data \
        --dialogues_jsonl ${dataflow_dialogues_dir}/${subset}.dataflow_dialogues.jsonl \
        --num_context_turns 2 \
        --include_program \
        --include_described_entities \
		--simplify_format \
        --onmt_text_data_outbase ${onmt_text_data_dir}/${subset}
done


# Compute statistics for the created OpenNMT text data.

onmt_data_stats_dir="output/onmt_data_stats"
mkdir -p "${onmt_data_stats_dir}"
python -m dataflow.onmt_helpers.compute_onmt_data_stats \
    --text_data_dir ${onmt_text_data_dir} \
    --suffix src src_tok tgt \
    --subset train valid \
    --outdir ${onmt_data_stats_dir}

# make binarized data

onmt_binarized_data_dir="output/onmt_binarized_data"
mkdir -p "${onmt_binarized_data_dir}"

src_tok_max_ntokens=$(jq '."100"' ${onmt_data_stats_dir}/train.src_tok.ntokens_stats.json)
tgt_max_ntokens=$(jq '."100"' ${onmt_data_stats_dir}/train.tgt.ntokens_stats.json)

# create OpenNMT binarized data
#  deleting old data first
rm -f output/onmt_binarized_data/*

onmt_preprocess \
    --dynamic_dict \
    --train_src ${onmt_text_data_dir}/train.src_tok \
    --train_tgt ${onmt_text_data_dir}/train.tgt \
    --valid_src ${onmt_text_data_dir}/valid.src_tok \
    --valid_tgt ${onmt_text_data_dir}/valid.tgt \
    --src_seq_length ${src_tok_max_ntokens} \
    --tgt_seq_length ${tgt_max_ntokens} \
    --src_words_min_frequency 0 \
    --tgt_words_min_frequency 0 \
    --save_data ${onmt_binarized_data_dir}/data


# embeddings - (have to do this)
glove_840b_dir="output/glove_840b"

onmt_embeddings_dir="output/onmt_embeddings"
mkdir -p "${onmt_embeddings_dir}"
python -m dataflow.onmt_helpers.embeddings_to_torch \
    -emb_file_both ${glove_840b_dir}/glove.840B.300d.txt \
    -dict_file ${onmt_binarized_data_dir}/data.vocab.pt \
    -output_file ${onmt_embeddings_dir}/embeddings


# train OpenNMT models

# deleting old models!
rm -f output/onmt/models/*

setgpu6


onmt_models_dir="output/onmt_models"
mkdir -p "${onmt_models_dir}"

batch_size=64
train_num_datapoints=$(jq '.train' ${onmt_data_stats_dir}/nexamples.json)
valid_steps=$(python3 -c "from math import ceil; print(ceil(${train_num_datapoints}/${batch_size}))")

rm -f output/onmt_models/*

onmt_train \
    --encoder_type brnn \
    --decoder_type rnn \
    --rnn_type LSTM \
    --global_attention general \
    --global_attention_function softmax \
    --generator_function softmax \
    --copy_attn_type general \
    --copy_attn \
    --seed 1 \
    --optim adam \
    --learning_rate 0.001 \
    --early_stopping 2 \
    --batch_size ${batch_size} \
    --valid_batch_size 8 \
    --valid_steps ${valid_steps} \
    --save_checkpoint_steps ${valid_steps} \
    --data ${onmt_binarized_data_dir}/data \
    --pre_word_vecs_enc ${onmt_embeddings_dir}/embeddings.enc.pt \
    --pre_word_vecs_dec ${onmt_embeddings_dir}/embeddings.dec.pt \
    --word_vec_size 300 \
    --attention_dropout 0 \
    --dropout 0.5 \
    --layers 2 \
    --rnn_size 384 \
    --gpu_ranks 0 \
    --world_size 1 \
    --save_model ${onmt_models_dir}/checkpoint

last=`ls -t output/onmt_models/*.pt | head -n 1`
cp $last output/onmt_models/checkpoint_last.pt

# predict programs using a trained OpenNMT model


onmt_translate_outdir="output/onmt_translate_output"
mkdir -p "${onmt_translate_outdir}"

onmt_model_pt="${onmt_models_dir}/checkpoint_last.pt"
nbest=5
tgt_max_ntokens=$(jq '."100"' ${onmt_data_stats_dir}/train.tgt.ntokens_stats.json)

onmt_translate \
    --model ${onmt_model_pt} \
    --max_length ${tgt_max_ntokens} \
    --src ${onmt_text_data_dir}/valid.src_tok \
    --replace_unk \
    --n_best ${nbest} \
    --batch_size 8 \
    --beam_size 10 \
    --gpu 0 \
    --report_time \
    --output ${onmt_translate_outdir}/valid.nbest


# evaluate


evaluation_outdir="output/evaluation_output"
mkdir -p "${evaluation_outdir}"

# create the prediction report
python -m dataflow.onmt_helpers.create_onmt_prediction_report \
    --dialogues_jsonl ${dataflow_dialogues_dir}/valid.dataflow_dialogues.jsonl \
    --datum_id_jsonl ${onmt_text_data_dir}/valid.datum_id \
    --src_txt ${onmt_text_data_dir}/valid.src_tok \
    --ref_txt ${onmt_text_data_dir}/valid.tgt \
    --nbest_txt ${onmt_translate_outdir}/valid.nbest \
    --nbest ${nbest} \
    --outbase ${evaluation_outdir}/valid

# evaluate the predictions (all turns)
python -m dataflow.onmt_helpers.evaluate_onmt_predictions \
    --prediction_report_tsv ${evaluation_outdir}/valid.prediction_report.tsv \
    --scores_json ${evaluation_outdir}/valid.all.scores.json

# evaluate the predictions (refer turns)
python -m dataflow.onmt_helpers.evaluate_onmt_predictions \
    --prediction_report_tsv ${evaluation_outdir}/valid.prediction_report.tsv \
    --datum_ids_json ${dataflow_dialogues_stats_dir}/valid.refer_turn_ids.jsonl \
    --scores_json ${evaluation_outdir}/valid.refer_turns.scores.json

# evaluate the predictions (revise turns)
python -m dataflow.onmt_helpers.evaluate_onmt_predictions \
    --prediction_report_tsv ${evaluation_outdir}/valid.prediction_report.tsv \
    --datum_ids_json ${dataflow_dialogues_stats_dir}/valid.revise_turn_ids.jsonl \
    --scores_json ${evaluation_outdir}/valid.revise_turns.scores.json

