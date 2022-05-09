"""
File containing python exceptions related to core Dataflow application.
These are the exceptions which the user CANNOT do anything about, such as internal errors.
"""
from opendf.exceptions.python_exception import InvalidDataException, PythonDFException


class PartialDateTimeException(InvalidDataException):  # CHECK: move to applications.core
    """
    Invalid data for PartialDateTime.
    """

    def __init__(self, message):
        super(PartialDateTimeException, self).__init__(message)


class PartialIntervalException(InvalidDataException):  # CHECK: move to applications.core
    """
    Invalid data for PartialInterval.
    """

    def __init__(self, message):
        super(PartialIntervalException, self).__init__(message)


class CalendarException(InvalidDataException):  # CHECK: move to applications.core
    """
    Invalid data for time nodes.
    """

    def __init__(self, message):
        super(CalendarException, self).__init__(message)


class BadConstructionException(PythonDFException):  # CHECK: move to applications.core
    """
    Invalid construction of python objects.
    """

    def __init__(self, message):
        super(BadConstructionException, self).__init__(message)


class BadRangeException(BadConstructionException):  # CHECK: move to applications.core
    """
    Range class not well-defined, begin > end.
    """

    def __init__(self, begin, end):
        message = f"Begin should be less than or equal to end, begin: {begin}, end: {end}"
        super(BadRangeException, self).__init__(message)
