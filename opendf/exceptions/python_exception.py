"""
File containing python exceptions related to Dataflow.
These are the exceptions which the user CANNOT do anything about, such as internal errors.
"""
from abc import ABC


class PythonDFException(Exception, ABC):
    """
    Defines the base Python Dataflow Exception.
    """

    def __init__(self, message):
        """
        Creates a Python Dataflow Exception.

        :param message: the message
        :type message: str
        """
        super(PythonDFException, self).__init__(message)


class EvaluationError(PythonDFException):
    """
    An exception raised when evaluating the graph and cannot be handled.
    """

    def __init__(self, message="Evaluation error"):
        super(EvaluationError, self).__init__(message)


class SingletonClassException(PythonDFException):
    """
    An exception when trying to instantiate a singleton class that has already been instantiated.
    """

    def __init__(self, message="This class is a singleton! Use `get_instance()` instead of calling constructor"):
        super(SingletonClassException, self).__init__(message)


class NoEnvironmentAttributeException(PythonDFException):
    """
    Exception when passing a value for an invalid Environment Attribute field.
    """

    def __init__(self, clazz, key):
        """
        Creates a NoEnvironmentAttributeException.
        :param clazz: the name of the class
        :type clazz: str
        :param key: the name of the field
        :type key: str
        """
        super(NoEnvironmentAttributeException, self).__init__(f"{clazz} has no attribute {key}!")


class InputProgramException(PythonDFException):
    """
    Exception when processing the input P-expression.
    """

    pass


class LexerException(InputProgramException):
    """
    Lexer exception when processing the input P-expression.
    """

    def __init__(self, token):
        super(LexerException, self).__init__(f"Illegal character `{token}`")
        self.token = token


class ParserException(InputProgramException):
    """
    Parser exception when processing the input P-expression.
    """

    def __init__(self, parsed):
        super(ParserException, self).__init__(f"Syntax error at `{parsed}`")
        self.parsed = parsed


class SemanticException(InputProgramException):
    """
    Parser exception when processing unsupported P-expressions.
    """

    def __init__(self, message):
        super(SemanticException, self).__init__(message)


class UnknownNodeTypeException(SemanticException):
    """
    Unknown node type exception.
    """

    def __init__(self, node_type):
        message = f"No such node type: {node_type}"
        super(UnknownNodeTypeException, self).__init__(message)


class InvalidDataException(PythonDFException):
    """
    Exception when invalid data is found on different objects.
    """

    def __init__(self, message):
        super(InvalidDataException, self).__init__(message)


class BadEventException(InvalidDataException):
    """
    Invalid data for event simplify.
    """

    def __init__(self, message):
        super(BadEventException, self).__init__(message)
