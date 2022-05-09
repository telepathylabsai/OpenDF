"""
The main entry point to run the dataflow graphs.
"""
import argparse
import time
import pickle

from opendf.graph.draw_graph import draw_all_graphs
from opendf.defs import *
from opendf.utils.arg_utils import add_environment_option


def create_arguments_parser():
    """
    Creates the argument parser for the file.

    :return: the argument parser
    :rtype: argparse.ArgumentParser
    """
    parser = argparse.ArgumentParser(
        description="The entry point to draw a dataflow graphs from a serialized context.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument(
        "files", metavar="files", type=str, nargs="+",
        help="the path(s) to the serialized contexts"
    )

    parser.add_argument(
        "--log", "-l", metavar="log", type=str, required=False, default="DEBUG",
        choices=LOG_LEVELS.keys(),
        help=f"The level of the logging, possible values are: {list(LOG_LEVELS.keys())}"
    )

    parser = add_environment_option(parser)

    return parser


environment_definitions = EnvironmentDefinition.get_instance()


def main(path):
    try:
        with open(path, 'rb') as input_file:
            d_context = pickle.load(input_file)
        draw_all_graphs(d_context)
    except Exception as e:
        raise e


if __name__ == "__main__":
    start = time.time()
    try:
        parser = create_arguments_parser()
        arguments = parser.parse_args()
        config_log(arguments.log)
        if arguments.environment:
            environment_definitions.update_values(**arguments.environment)

        for file in arguments.files:
            main(file)
    except Exception as e:
        raise e
    finally:
        end = time.time()
        logger.info(f"{end - start:.3f}s")
        logging.shutdown()
