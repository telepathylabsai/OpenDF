"""
File containing python exceptions related to Dataflow SMCalFlow application.
These are the exceptions which the user CANNOT do anything about, such as internal errors.
"""
from opendf.exceptions.python_exception import InvalidDataException


class TimeSlotException(InvalidDataException):  # CHECK: move to applications.smcalflow
    """
    Invalid data for TimeSlot.
    """

    def __init__(self, message):
        super(TimeSlotException, self).__init__(message)
