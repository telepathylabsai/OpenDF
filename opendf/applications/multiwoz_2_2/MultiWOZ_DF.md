# MultiWOZ-DF - A Dataflow Implementation of MultiWOZ

This page describes the dataflow implementation of MultiWOZ, and how to run the experiments described in our upcoming
paper "MultiWOZ-DF".

## Data

We are using MultiWOZ version 2.2.

Please follow the instructions in the MultiWOZ GitHub page (not that some scripts need to be run).

Make a directory `opendf/resources/multiwoz`, and copy the 7 domain databases
(`attraction_db.json`, `hospital_db.json`, `hotel_db.json`, `police_db.json`, `restaurant_db.json`, `taxi_db.json`, 
`train_db.json`) into that directory. These files can be found in MultiWOZ 2.1. dataset.

Manually add the following line to the hospital_db.json:

```
{"department": "Addenbrookes Hospital", "id": 999, "phone": "01223245151"},
```

(this appears as answer in multiple dialogues, but not in the hospital database)

The `taxi_db.json` file may contain some values using single quotes, which is not supported by json. You may need to
replace them by double quotes.

Make a directory `opendf/tmp/multiwoz_2_2`, and under that create directories `train`, `dev`, `test`,
and copy the corresponding dialogue json files (`dialogues_001.json`, ...) there.

Copy the file `dialog_acts.json` to `tmp/multiwoz_2_2`.

## Running

Use `main_multiwoz_2_2.py` to run the MultiWOZ experiments.

This program:

1. converts each dialogue turn to our DF format;
2. writes out the converted DF expressions - for use by the seq2seq model training;
3. executes the expression; and
4. compares the execution results with the manual dialogue state annotation.

For example, running:

`main_multiwoz_2_2.py -o tmp/multiwoz_2_2/dev_ -a -A -g -x -d MUL1271`

will run one dialogue (MUL1271), and draw the resulting graphs for the whole conversation.
It will also save the file `tmp/multiwos_2_2/dev_dialog_good.txt` (or `.../dev_dialog_bad.txt`,
depending on the success of the comparison to the manual annotation) with the log of the conversation.

Please see the program for explanation about the required/optional inputs. One can run `main_multiwoz_2_2.py -h` for
help.

To run main.py with MultiWOZ nodes, use:

`main.py -c resources/multiwoz_2_2_config.yaml`

## Translation

In order to run the translation experiments, one should run the `main_multiwoz_2_2.py` file for the whole dataset by running the command:

```
python3 opendf/main_multiwoz_2_2.py \
    -d train dev test \
    -o tmp/multiwoz_2_2/full_
    -a -A
```

This will save the P-Expressions to `tmp/multiwoz_2_2/full_dialogue.jsonl` and `tmp/multiwoz_2_2/full_dialogue_bad.jsonl` (the dialogues that fail the state comparison).

After generating the P-Expresion, one can follow the original training procedure described on 
[Microsoft's GitHub page](https://github.com/microsoft/task_oriented_dialogue_as_dataflow_synthesis), 
for the MultiWOZ dataset, with minimal changes.

At the end of step 1, the jsonl files used to train the translation model will have been generated in the `output/dataflow_dialogues`. These files contain the original MS Dataflow expressions. In order to replace these expressions by the OpenDF P-Expression, one should run:

```
python3 opendf/misc/multiwoz_to_jsonl.py 
    -m tmp/multiwoz_2_2 \
    -ms <PATH>/task_oriented_dialogue_as_dataflow_synthesis/output/dataflow_dialogues  \ 
    -p tmp/multiwoz_2_2/full_dialogue.jsonl tmp/multiwoz_2_2/full_dialogue_bad.jsonl \
    -o <OUTPUT PATH>
```

This will generate the files `train.dataflow_dialogues.jsonl`, `valid.dataflow_dialogues.jsonl` and 
`test.dataflow_dialogues.jsonl` containing the OpenDF P-Expression. These files should be put in 
`output/dataflow_dialogues`, replacing the previous ones. 
We suggest moving the original ones, so it can be used again for further experiments.

After replacing the files, one can move to step 2 of the 
[Microsoft's GitHub page](https://github.com/microsoft/task_oriented_dialogue_as_dataflow_synthesis), 
but instead of running:

```
onmt_text_data_dir="output/onmt_text_data"
mkdir -p "${onmt_text_data_dir}"
for subset in "train" "valid" "test"; do
    python -m dataflow.onmt_helpers.create_onmt_text_data \
        --dialogues_jsonl ${dataflow_dialogues_dir}/${subset}.dataflow_dialogues.jsonl \
        --num_context_turns 2 \
        --include_agent_utterance \
        --onmt_text_data_outbase ${onmt_text_data_dir}/${subset}
done
```

One should run the following command instead:

```
onmt_text_data_dir="output/onmt_text_data"
mkdir -p "${onmt_text_data_dir}"
for subset in "train" "valid" "test"; do
    python3 -m opendf/misc/create_onmt_text_data.py \
        --dialogues_jsonl ${dataflow_dialogues_dir}/${subset}.dataflow_dialogues.jsonl \
        --num_context_turns 2 \
        --include_agent_utterance \
        --simplify_format \
        --remove_time_space \
        --onmt_text_data_outbase ${onmt_text_data_dir}/${subset}
done
```

This is an adapted version to handle OpenDF's P-Expressions.

After that, the instructions are the same as the ones in 
[Microsoft's GitHub page](https://github.com/microsoft/task_oriented_dialogue_as_dataflow_synthesis).

## Code

The MultiWOZ implementation is under `opendf/applications/multiwoz_2_2`, with each domain implemented as a separate
file under nodes.

The code for the different domain nodes is to a large degree a copy-paste of each other, but each domain has some 
unique peculiarities.

The code for the domains' nodes is longer than the "typical" SMCalFlow node, due to the fact that in addition to 
"normal" execution, we also have to take care of conversion from the original annotation, handling the oracle input 
(see paper), and comparing the execution result to the manual DST annotation.

## Implementation Style

In the MultiWOZ experiment in the original Semantic Machines paper, the focus was on a minimal DF implementation to
demonstrate possible benefits of the DF paradigm even for flat intents/entities type of datasets.

In the current implementation, we decided to give a fuller implementation, which is closer to
an actually functional dialogue system - connect this with the seq2seq translation model,
and you could run interactive dialogues.

In particular - the user can ask questions (and have them answered) about the domains, as well
as having a top-level (interaction-level) active node, which keeps prompting the user for input, keeping
the conversation "alive".
