"""
Useful classes and functions to parse command line arguments.
"""

import argparse
from typing import Tuple


def split_key_value(key_value):
    """
    Splits the key and value from `key_value`.
    :param key_value: a string representing the key and the value, separated with a `=` character
    :type key_value: str
    :return: the split key and value
    :rtype: Tuple[str, str]
    """
    return key_value.split("=", maxsplit=1)


class KeyValue(argparse.Action):
    """
    Class to define an action to retrieve key-value pair from the command line.
    """

    def __call__(self, parser, namespace, values, option_string=None):
        key_value_dict = dict()
        setattr(namespace, self.dest, key_value_dict)

        for value in values:
            key, value = split_key_value(value)
            key_value_dict[key] = value


def add_environment_option(parser):
    """
    Adds an option to the parser, so the user can change the values of environment variables.

    :param parser: the parser
    :type parser: argparse.ArgumentParser
    :return: the parser with the option
    :rtype: argparse.ArgumentParser
    """
    parser.add_argument(
        "--environment", "-env", nargs="+", action=KeyValue, metavar="KEY=VALUE",
        help="define a set of key-value pairs to overwrite environment definitions values from `opendf/defs.py`. "
             "See `opendf/defs.py`, to see the list of possible variables to overwrite."
    )

    return parser
