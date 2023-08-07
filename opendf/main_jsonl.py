"""
The main entry point to run the dataflow graphs from a jsonl file.
"""
import argparse
import json
import time

import yaml
from tqdm import tqdm

from opendf.applications import EnvironmentClass, SMCalFlowEnvironment
from opendf.defs import *
from opendf.main import OpenDFDialogue
from opendf.utils.arg_utils import add_environment_option

logger = logging.getLogger(__name__)
environment_definitions = EnvironmentDefinition.get_instance()


def create_arguments_parser():
    """
    Creates the argument parser for the file.

    :return: the argument parser
    :rtype: argparse.ArgumentParser
    """
    parser = argparse.ArgumentParser(
        description="The main entry point to run the dataflow graphs from a jsonl file",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument(
        "--config", "-c", metavar="config", type=str, required=False, default="resources/smcalflow_config.yaml",
        help="the configuration file for the application"
    )

    parser.add_argument(
        "--dialog_id", "-d", metavar="dialog_id", type=str, required=False, default=None,
        help="the dialog id to use."
    )

    parser.add_argument(
        "--examples_files", "-ef", metavar="examples_file", type=str, nargs="+",
        help="the examples files to use"
    )

    parser.add_argument(
        "--additional_nodes", "-n", metavar="additional_nodes", type=str, required=False,
        default=None, nargs="+",
        help="path for python modules containing additional nodes to be imported. "
             "The path should be in python dot notation "
             "(e.g. `opendf.applications.sandbox.sandbox`) "
             "This argument only works when using `SMCalFlowEnvironment` as environment class"
    )

    parser.add_argument(
        "--log", "-l", metavar="log", type=str, required=False, default="DEBUG",
        choices=LOG_LEVELS.keys(),
        help=f"The level of the logging, possible values are: {list(LOG_LEVELS.keys())}"
    )

    parser = add_environment_option(parser)

    return parser


def extract_p_expressions(dialog):
    p_expressions = []
    for turn in dialog["turns"]:
        p_expressions.append(turn["lispress"])
    return p_expressions


def run_dialogue(dialogs, environment_class: EnvironmentClass):
    df_dialogue = OpenDFDialogue()
    error = 0
    total = 0
    for dialog in tqdm(dialogs, dynamic_ncols=True, unit=" dialogues"):
        try:
            d_context = environment_class.get_new_context()
            environment_class.d_context = d_context
            with environment_class:
                total += 1
                p_expressions = extract_p_expressions(dialog)
                df_dialogue.run_dialogue(p_expressions, d_context, draw_graph=False)
        except Exception as e:
            error += 1

    logger.warning(f"Good Dialogues:  {total - error}")
    logger.warning(f"Error Dialogues: {error}")
    logger.warning(f"Total Dialogues: {total}")


def run_dialogue_from_arguments(arguments):
    target_dialog = arguments.dialog_id
    if arguments.environment:
        environment_definitions.update_values(**arguments.environment)

    application_config = yaml.load(open(arguments.config, 'r'), Loader=yaml.UnsafeLoader)
    environment_class = application_config["environment_class"]

    if isinstance(environment_class, SMCalFlowEnvironment) and arguments.additional_nodes:
        environment_class.additional_paths = arguments.additional_nodes

    dialogues = []
    for example_path in arguments.examples_files:
        with open(example_path) as examples_file:
            for line in examples_file:
                dialogue = json.loads(line)
                if target_dialog is None:
                    dialogues.append(dialogue)
                else:
                    if dialogue["dialogue_id"].startswith(target_dialog):
                        dialogues.append(dialogue)
                        break

    run_dialogue(dialogues, environment_class)


if __name__ == "__main__":
    start = time.time()
    try:
        parser = create_arguments_parser()
        arguments = parser.parse_args()
        config_log(level=arguments.log)
        run_dialogue_from_arguments(arguments)
    except Exception as e:
        raise e
    finally:
        end = time.time()
        logger.info(f"Running time: {end - start:.3f}s")
        logging.shutdown()
