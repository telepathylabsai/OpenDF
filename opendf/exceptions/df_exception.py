"""
File containing Dataflow exceptions.
These are the exceptions which the user can do something about.
"""

from abc import ABC


class DFException(Exception, ABC):
    """
    The base Dataflow exception.
    """

    def __init__(self, message, node, hints=None, suggestions=None, orig=None, chain=None):
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
        super(DFException, self).__init__(message)
        self.message = message
        self.node = node
        self.hints = hints
        self.suggestions = suggestions
        self.orig = orig
        self.chain = chain

    def chain_end(self):
        return self.chain.chain_end() if self.chain else self

    def chain_orig(self):
        return self.chain.chain_orig() if self.orig else self


class NotImplementedYetDFException(DFException):
    """
    Exception when encountering an invalid input on a Dataflow node.
    """

    def __init__(self, message, node, hints=None, suggestions=None, orig=None, chain=None):
        super().__init__(message, node, hints=hints, suggestions=suggestions, orig=orig, chain=chain)


class NoReviseMatchException(DFException):
    """
    An exception raised when revise is not able to match any node.
    """

    def __init__(self, node, message="No revise match", hints=None, suggestions=None, orig=None, chain=None):
        super().__init__(message, node, hints=hints, suggestions=suggestions, orig=orig, chain=chain)


class InvalidResultException(DFException):
    """
    Exception when computing a wrong result during the execution of a node, e.g. get the 30th day of February.
    """

    def __init__(self, message, node, hints=None, suggestions=None, orig=None, chain=None):
        super().__init__(message, node, hints=hints, suggestions=suggestions, orig=orig, chain=chain)


class InvalidInputException(DFException):
    """
    Exception when encountering an invalid input on a Dataflow node.

    This class and all its subclasses must only be raised from inside Node's `valid_input(.)` method.
    """

    def __init__(self, message, node, hints=None, suggestions=None, orig=None, chain=None):
        super().__init__(message, node, hints=hints, suggestions=suggestions, orig=orig, chain=chain)


class InvalidOptionException(InvalidInputException):
    """
    Exception when encountering an input on a node, that is not in the list of possible values for the input.
    """

    def __init__(self, key, value, possible_values, node, hints=None, suggestions=None, orig=None, chain=None):
        message = f"Value '{value}' for field '{key}' not in the set of possible values {{{set(possible_values)}}}"
        super().__init__(message, node, hints=hints, suggestions=suggestions, orig=orig, chain=chain)


class InvalidTypeException(InvalidInputException):
    """
    Exception when encountering an input on a node, that is not of the correct type.
    """

    def __init__(self, message, node, hints=None, suggestions=None, orig=None, chain=None):
        super().__init__(message, node, hints=hints, suggestions=suggestions, orig=orig, chain=chain)


class InvalidValueException(InvalidInputException):
    """
    Exception when encountering an input on a node, that does not have a valid value, e.g. a negative number for size.
    """

    def __init__(self, message, node, hints=None, suggestions=None, orig=None, chain=None):
        super().__init__(message, node, hints=hints, suggestions=suggestions, orig=orig, chain=chain)


class IncompatibleInputException(InvalidInputException):
    """
    Exception when encountering input fields that are incompatible.
    """

    def __init__(self, message, node, hints=None, suggestions=None, orig=None, chain=None):
        super().__init__(message, node, hints=hints, suggestions=suggestions, orig=orig, chain=chain)


class InvalidNumberOfInputsException(InvalidInputException):
    """
    Exception when encountering wrong number of inputs in a node.
    """

    def __init__(self, node, expected, found=None, hints=None, suggestions=None, orig=None, chain=None):
        message = f"{node.typename()} should have {expected} input(s)"
        if found is not None:
            message += f", {found} found"
        message += '.'
        super().__init__(message, node, hints=hints, suggestions=suggestions, orig=orig, chain=chain)
        self.expected = expected
        self.found = found


class MissingValueException(InvalidInputException):
    """
    Exception when data is missing for required node field.
    """

    def __init__(self, key, node, hints=None, suggestions=None, orig=None, chain=None, message=None):
        if message is None:
            message = f"Missing data for field {key} on node {node.__class__.__name__}"
            if hints:
                message += f", hint: {hints}"
            message += '.'
        super().__init__(message, node, hints=hints, suggestions=suggestions, orig=orig, chain=chain)
        self.key = key


class NoPropertyException(DFException):
    """
    Exception when trying to get an invalid property from a node.
    """

    def __init__(self, message, node, hints=None, suggestions=None, orig=None, chain=None):
        super().__init__(message, node, hints=hints, suggestions=suggestions, orig=orig, chain=chain)


class WrongSuggestionSelectionException(DFException):
    """
    Clashed event suggestion exception.
    """

    def __init__(self, node, hints=None, suggestions=None, orig=None, chain=None, message=None):
        if message is None:
            message = "I'm not sure which suggestion you're referring to. Please be explicit"
        super().__init__(message, node, hints=hints, suggestions=suggestions, orig=orig, chain=chain)


class ElementNotFoundException(DFException):
    """
    Exception when an element is not found.
    """

    def __init__(self, message, node, hints=None, suggestions=None, orig=None, chain=None):
        super().__init__(message, node, hints=hints, suggestions=suggestions, orig=orig, chain=chain)


class SingletonException(DFException):
    """
    Exceptions for singleton.
    """

    pass


class EmptyEntrySingletonException(SingletonException):
    """
    No entry for singleton.
    """

    def __init__(self, typename, node, hints=None, suggestions=None, orig=None, chain=None):
        message = f"Singleton error - no matching {typename} objects"
        super().__init__(message, node, hints=hints, suggestions=suggestions, orig=orig, chain=chain)


class MultipleEntriesSingletonException(SingletonException):
    """
    Multiple entries for singleton.
    """

    def __init__(self, message, node, hints=None, suggestions=None, orig=None, chain=None):
        super().__init__(message, node, hints=hints, suggestions=suggestions, orig=orig, chain=chain)
