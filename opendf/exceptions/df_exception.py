"""
File containing Dataflow exceptions.
These are the exceptions which the user can do something about.
"""

from abc import ABC
from typing import Sequence
from opendf.utils.utils import Message

class DFException(Exception, ABC):
    """
    The base Dataflow exception.
    """

    def __init__(self, message, node, hints=None, suggestions=None, orig=None, chain=None, objects=None, turn=None):
        """
        Creates a base Dataflow exception.

        :param message: the message
        :type message: str
        :param node: the node which raised the exception
        :type node: Node
        :param hints: the hints
        :type hints: List
        :param suggestions: the suggestions to fix the exception, as a list of P-expressions
        :type suggestions: List[str]
        :param orig: the origin exception
        :type orig: DFException
        :param chain: the chain exception
        :type chain: DFException
        """
        msg = message
        if isinstance(msg, Message):
            x=1
        if isinstance(message, tuple) and len(message)==2 and isinstance(message[0], str):
            msg = message[0]
            if isinstance(message[1], list):
                if objects is None:
                    objects = message[1]
                elif isinstance(objects, list):
                    objects += message[1]

        super(DFException, self).__init__(msg)
        self.message = msg
        self.node = node
        self.hints = hints
        self.suggestions = suggestions
        self.orig = orig
        self.chain = chain
        self.objects = objects if objects else []
        self.turn = turn
        if turn is None and not isinstance(node, int):  # in case called from unpack context, the turn would be copied by dup.
            self.turn = node.context.turn_num  # the turn when this exception was created (not when node was created)

    def __reduce__(self):
        return (self.__class__, (
            self.message, self.node, self.hints, self.suggestions, self.orig, self.chain, self.objects, self.turn))

    def chain_end(self):
        return self.chain.chain_end() if self.chain else self

    def chain_orig(self):
        return self.chain.chain_orig() if self.orig else self

    # def dup(self):
    #     ex = DFException(self.message, self.node, self.hints, self.suggestions,
    #                      self.orig, self.chain, self.objects, self.turn)
    #     ex.__class__ = self.__class__
    #     return ex


class NotImplementedYetDFException(DFException):
    """
    Exception when encountering an invalid input on a Dataflow node.
    """

    def __init__(self, message, node, hints=None, suggestions=None, orig=None, chain=None, objects=None):
        super().__init__(message, node, hints=hints, suggestions=suggestions, orig=orig, chain=chain, objects=objects)


class NoReviseMatchException(DFException):
    """
    An exception raised when revise is not able to match any node.
    """

    def __init__(self, node, message="No revise match", hints=None, suggestions=None, orig=None, chain=None, objects=None):
        super().__init__(message, node, hints=hints, suggestions=suggestions, orig=orig, chain=chain, objects=objects)

    def __reduce__(self):
        return (self.__class__, (
            self.node, self.message, self.hints, self.suggestions, self.orig, self.chain, self.objects))

class InvalidResultException(DFException):
    """
    Exception when computing a wrong result during the execution of a node, e.g. get the 30th day of February.
    """

    def __init__(self, message, node, hints=None, suggestions=None, orig=None, chain=None, objects=None):
        super().__init__(message, node, hints=hints, suggestions=suggestions, orig=orig, chain=chain, objects=objects)


class InvalidInputException(DFException):
    """
    Exception when encountering an invalid input on a Dataflow node.

    This class and all its subclasses must only be raised from inside Node's `valid_input(.)` method.
    """

    def __init__(self, message, node, hints=None, suggestions=None, orig=None, chain=None, objects=None):
        super().__init__(message, node, hints=hints, suggestions=suggestions, orig=orig, chain=chain, objects=objects)


class InvalidOptionException(InvalidInputException):
    """
    Exception when encountering an input on a node, that is not in the list of possible values for the input.
    """

    def __init__(self, key, value, possible_values, node, hints=None, suggestions=None, orig=None, chain=None, objects=None):
        message = f"Value '{value}' for field '{key}' not in the set of possible values {{{set(possible_values)}}}"
        super().__init__(message, node, hints=hints, suggestions=suggestions, orig=orig, chain=chain, objects=objects)


class InvalidTypeException(InvalidInputException):
    """
    Exception when encountering an input on a node, that is not of the correct type.
    """

    def __init__(self, message, node, hints=None, suggestions=None, orig=None, chain=None, objects=None):
        super().__init__(message, node, hints=hints, suggestions=suggestions, orig=orig, chain=chain, objects=objects)


class InvalidValueException(InvalidInputException):
    """
    Exception when encountering an input on a node, that does not have a valid value, e.g. a negative number for size.
    """

    def __init__(self, message, node, hints=None, suggestions=None, orig=None, chain=None, objects=None):
        super().__init__(message, node, hints=hints, suggestions=suggestions, orig=orig, chain=chain, objects=objects)


class IncompatibleInputException(InvalidInputException):
    """
    Exception when encountering input fields that are incompatible.
    """

    def __init__(self, message, node, hints=None, suggestions=None, orig=None, chain=None, objects=None):
        super().__init__(message, node, hints=hints, suggestions=suggestions, orig=orig, chain=chain, objects=objects)


class AskMoreInputException(InvalidInputException):
    """
    Exception when asking for more input.
    """

    def __init__(self, message, node, hints=None, suggestions=None, orig=None, chain=None, objects=None):
        super().__init__(message, node, hints=hints, suggestions=suggestions, orig=orig, chain=chain, objects=objects)


class InvalidNumberOfInputsException(InvalidInputException):
    """
    Exception when encountering wrong number of inputs in a node.
    """

    # use this, since copy() gets confused otherwise (really needed??)
    @staticmethod
    def make_exc(node, expected, found=None, hints=None, suggestions=None, orig=None, chain=None, objects=None):
        message = f"{node.typename()} should have {expected} input(s)"
        if found is not None:
            message += f", {found} found"
        message += '.'
        return InvalidNumberOfInputsException(message, node, hints=hints, suggestions=suggestions, orig=orig, chain=chain, objects=objects)

    def __init__(self, message, node, hints=None, suggestions=None, orig=None, chain=None, objects=None):
        super().__init__(message, node, hints=hints, suggestions=suggestions, orig=orig, chain=chain, objects=objects)


class MissingValueException(InvalidInputException):
    """
    Exception when data is missing for required node field.
    """

    def __init__(self, key,  node, message=None, hints=None, suggestions=None, orig=None, chain=None, objects=None):
        if message is None:
            message = f"Missing data for field {key} on node {node.__class__.__name__}"
            if hints:
                message += f", hint: {hints}"
            message += '.'
        super().__init__(message, node, hints=hints, suggestions=suggestions, orig=orig, chain=chain, objects=objects)
        self.key = key

    def __reduce__(self):
        return (self.__class__, (
            self.key, self.node, self.message, self.hints, self.suggestions, self.orig, self.chain, self.objects))

class NoPropertyException(DFException):
    """
    Exception when trying to get an invalid property from a node.
    """

    def __init__(self, message, node, hints=None, suggestions=None, orig=None, chain=None, objects=None):
        super().__init__(message, node, hints=hints, suggestions=suggestions, orig=orig, chain=chain, objects=objects)


class WrongSuggestionSelectionException(DFException):
    """
    Clashed event suggestion exception.
    """

    def __init__(self, node, hints=None, suggestions=None, orig=None, chain=None, message=None, objects=None):
        if message is None:
            message = "I'm not sure which suggestion you're referring to. Please be explicit"
        super().__init__(message, node, hints=hints, suggestions=suggestions, orig=orig, chain=chain, objects=objects)

    def __reduce__(self):
        return (self.__class__, (self.node, self.hints, self.suggestions, self.orig, self.chain,
                                 self.message, self.objects))

class ElementNotFoundException(DFException):
    """
    Exception when an element is not found.
    """

    def __init__(self, message, node, hints=None, suggestions=None, orig=None, chain=None, objects=None):
        super().__init__(message, node, hints=hints, suggestions=suggestions, orig=orig, chain=chain, objects=objects)


class SingletonException(DFException):
    """
    Exceptions for singleton.
    """

    pass


class EmptyEntrySingletonException(SingletonException):
    """
    No entry for singleton.
    """

    def __init__(self, typename, node, hints=None, suggestions=None, orig=None, chain=None, objects=None):
        message = f"Singleton error - no matching {typename} objects"
        super().__init__(message, node, hints=hints, suggestions=suggestions, orig=orig, chain=chain, objects=objects)


class MultipleEntriesSingletonException(SingletonException):
    """
    Multiple entries for singleton.
    """

    def __init__(self, message, node, hints=None, suggestions=None, orig=None, chain=None, objects=None):
        super().__init__(message, node, hints=hints, suggestions=suggestions, orig=orig, chain=chain, objects=objects)


class OracleException(DFException):
    """
    Forwarding agent oracle's answer as an exception
    """

    def __init__(self, message, node, hints=None, suggestions=None, orig=None, chain=None, objects=None):
        super().__init__(message, node, hints=hints, suggestions=suggestions, orig=orig, chain=chain, objects=objects)


def get_current_exception(exceptions):
    """
    Gets the current exception from the list of exceptions.
    """
    if not exceptions:
        return None
    if isinstance(exceptions, Sequence):
        exceptions = exceptions[0]
    if isinstance(exceptions, DFException):
        return exceptions.chain_end()

    return exceptions
