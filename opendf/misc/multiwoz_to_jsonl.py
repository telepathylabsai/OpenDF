"""
Merges the MultiWOZ 2.2 generated files into a JSONL file.
"""
import argparse
import copy
import json
import logging
import os
import time
from typing import Dict

from opendf.defs import config_log, LOG_LEVELS
from opendf.utils.simplify_exp import tokenize_pexp

logger = logging.getLogger(__name__)

MULTIWOZ_FOLDERS = ["train", "dev", "test"]
MULTIWOZ_INDEX = "index_2_2.json"

MICROSOFT_FILES = ["train", "valid", "test"]
MICROSOFT_FILE_SUFFIX = ".dataflow_dialogues.jsonl"


def create_arguments_parser():
    """
    Creates the argument parser for the file.

    :return: the argument parser
    :rtype: argparse.ArgumentParser
    """
    parser = argparse.ArgumentParser(
        description="Merges the MultiWOZ 2.2 generated files into a JSONL file.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument(
        "--multiwoz_data_dir", "-m", metavar="multiwoz_data_dir", type=str, required=False, default="multiwoz_2_2",
        help="MultiWOZ 2.2 dataset directory containing the train, dev and test directories with "
             "their corresponding json files"
    )

    parser.add_argument(
        "--microsoft_data_dir", "-ms", metavar="microsoft_data_dir", type=str, required=True,
        help="Microsoft data directory containing the converted multiwoz dialogs"
    )

    parser.add_argument(
        "--p_exp_input_files", "-p", metavar="input_file", type=str, required=True,
        help="The input jsonl file(s) with the P-Expressions",
        nargs="+"
    )

    parser.add_argument(
        "--separate_equal", "-s", required=False,
        default=False, action="store_true",
        help=f"If `True`, combines the = (equal) sign (between the name and the value of an input) "
             f"with the name, as a single token"
    )

    parser.add_argument(
        "--output_directory", "-o", metavar="output_directory", type=str, required=False, default="",
        help="Output directory for the result files"
    )

    parser.add_argument(
        "--log", "-log", metavar="log", type=str, required=False, default="DEBUG",
        choices=LOG_LEVELS.keys(),
        help=f"The level of the logging, possible values are: {list(LOG_LEVELS.keys())}"
    )

    return parser


def check_for_files(multiwoz_directory, microsoft_directory, p_exp_filepaths):
    """
    Checks if all the necessary files are in place.

    :param multiwoz_directory: the MultiWOZ 2.2 directory
    :type multiwoz_directory: str
    :param microsoft_directory: the Microsoft directory
    :type microsoft_directory: str
    :param p_exp_filepaths: the P-Expressions input files
    :type p_exp_filepaths: List[str]
    """
    for folder in MULTIWOZ_FOLDERS:
        directory = os.path.join(multiwoz_directory, folder)
        assert os.path.isdir(directory), f"{folder} not found in {multiwoz_directory}"
    assert os.path.isfile(os.path.join(multiwoz_directory, MULTIWOZ_INDEX)), \
        f"{MULTIWOZ_INDEX} not found in {multiwoz_directory}"

    for file_name in MICROSOFT_FILES:
        filepath = os.path.join(microsoft_directory, file_name + MICROSOFT_FILE_SUFFIX)
        assert os.path.isfile(filepath), \
            f"{file_name + MICROSOFT_FILE_SUFFIX} not found in {microsoft_directory}"

    for p_exp_file in p_exp_filepaths:
        assert os.path.isfile(p_exp_file), f"{p_exp_file} not found"


def get_p_expressions_from_file(p_exp_path):
    p_dialogues = []
    with open(p_exp_path) as p_exp_file:
        for line in p_exp_file:
            p_dialogues.append(json.loads(line))
    return p_dialogues


def get_ms_jsonl_dialogue(microsoft_directory):
    dialogues = {}
    for file_name in MICROSOFT_FILES:
        filepath = os.path.join(microsoft_directory, file_name + MICROSOFT_FILE_SUFFIX)
        with open(filepath) as input_file:
            for line in input_file:
                dialogue = json.loads(line)
                dialogues[dialogue["dialogue_id"]] = dialogue

    return dialogues


def get_dialogue_set(multiwoz_directory) -> Dict[str, str]:
    dialogue_set = {}
    with open(os.path.join(multiwoz_directory, MULTIWOZ_INDEX)) as index_file:
        indexes = json.load(index_file)
        for dialogue_id, index in indexes.items():
            set_name = os.path.split(os.path.split(index["file"])[0])[-1]
            if set_name == "dev":
                set_name = "valid"
            dialogue_set[dialogue_id] = set_name

    return dialogue_set


def main(multiwoz_directory, microsoft_directory, p_exp_filepaths, output_directory, sep_equal=True):
    """
    Merge the MultiWOZ 2.2 files into a JSONL file.

    :param multiwoz_directory: the MultiWOZ 2.2 data directory
    :type multiwoz_directory: str
    :param microsoft_directory: the Microsoft conversion data directory
    :type microsoft_directory: str
    :param p_exp_filepaths: the P-Expressions input files
    :type p_exp_filepaths: List[str]
    :param output_directory: the output directory
    :type output_directory: str
    """
    if not os.path.isdir(output_directory):
        os.makedirs(output_directory, exist_ok=True)

    check_for_files(multiwoz_directory, microsoft_directory, p_exp_filepaths)
    ms_jsonl_dialogues = get_ms_jsonl_dialogue(microsoft_directory)
    dialogue_set = get_dialogue_set(multiwoz_directory)

    errors = []
    converted = 0
    with open(os.path.join(output_directory, "all" + MICROSOFT_FILE_SUFFIX), "w") as all_output_file, \
            open(os.path.join(output_directory, "train" + MICROSOFT_FILE_SUFFIX), "w") as train_file, \
            open(os.path.join(output_directory, "valid" + MICROSOFT_FILE_SUFFIX), "w") as valid_file, \
            open(os.path.join(output_directory, "test" + MICROSOFT_FILE_SUFFIX), "w") as test_file:
        file_sets = {"train": train_file, "valid": valid_file, "test": test_file}
        # TODO: split the output files into train, valid and test
        for p_exp_path in p_exp_filepaths:
            p_dialogues = get_p_expressions_from_file(p_exp_path)
            for p_dialogue in p_dialogues:
                dialogue_id = p_dialogue["dialogue_id"]
                expressions = p_dialogue["expressions"]
                ms_jsonl_dialogue = ms_jsonl_dialogues.get(dialogue_id)
                if not ms_jsonl_dialogue:
                    errors.append(f"{dialogue_id}: dialogue not found in MS data")
                    continue
                if len(expressions) != len(ms_jsonl_dialogue["turns"]):
                    errors.append(f"{dialogue_id}: number of turns between P-Expression and MS "
                                  f"data do not match")
                    continue

                result_dialogue = copy.deepcopy(ms_jsonl_dialogue)
                for i, p_exp in enumerate(expressions):
                    tokenized_exp = tokenize_pexp(p_exp, sep_equal=sep_equal)
                    result_dialogue["turns"][i]["lispress"] = tokenized_exp

                    # cleaning some fields
                    result_dialogue["turns"][i]["agent_utterance"]["described_entities"] = []
                    result_dialogue["turns"][i]["program_execution_oracle"]["has_exception"] = False
                    result_dialogue["turns"][i]["program_execution_oracle"]["refer_are_correct"] = True
                    result_dialogue["turns"][i]["skip"] = False

                # selected_output_file
                output_file = file_sets.get(dialogue_set.get(dialogue_id, {}))
                if output_file:
                    json.dump(result_dialogue, output_file)
                    output_file.write("\n")
                else:
                    errors.append(f"{dialogue_id}: could not determine the output set for the dialogue")

                json.dump(result_dialogue, all_output_file)
                all_output_file.write("\n")

                converted += 1

    print(f"Total of converted dialogues:   {converted}")
    print(f"Total of dialogues with errors: {len(errors)}")
    if errors:
        print("")
        print("Errors:")
        for error in errors:
            print(error)


if __name__ == '__main__':
    start = time.time()
    try:
        parser = create_arguments_parser()
        arguments = parser.parse_args()
        config_log(level=arguments.log)

        multiwoz_dir = arguments.multiwoz_data_dir
        microsoft_dir = arguments.microsoft_data_dir
        p_exp_files = arguments.p_exp_input_files
        output_dir = arguments.output_directory
        separate_equal = arguments.separate_equal

        main(multiwoz_dir, microsoft_dir, p_exp_files, output_dir, sep_equal=separate_equal)
    except Exception as e:
        raise e
    finally:
        end = time.time()
        logger.info(f"Running time: {end - start:.3f}s")
        logging.shutdown()
