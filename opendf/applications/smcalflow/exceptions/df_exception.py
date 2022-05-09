"""
File containing Dataflow exceptions specific to the SMCalFlow application.
These are the exceptions which the user can do something about.
"""

from opendf.exceptions import DFException
from opendf.exceptions.df_exception import ElementNotFoundException


class EventException(DFException):
    """
    Exception when dealing with events.
    """

    def __init__(self, message, node, hints=None, suggestions=None, orig=None, chain=None):
        super().__init__(message, node, hints=hints, suggestions=suggestions, orig=orig, chain=chain)


class BadEventConstraintException(EventException):
    """
    Bad event constraint exception.
    """

    def __init__(self, message, node, hints=None, suggestions=None, orig=None, chain=None):
        super().__init__(message, node, hints=hints, suggestions=suggestions, orig=orig, chain=chain)


class EventConfirmationException(EventException):
    """
    Event confirmation exception.
    """

    def __init__(self, message, node, suggestions=None, orig=None, chain=None):
        super().__init__(message, node, hints='confirm', suggestions=suggestions, orig=orig, chain=chain)


class BadEventDeletionException(EventException):
    """
    Bad event deletion exception.
    """

    def __init__(self, message, node, hints=None, suggestions=None, orig=None, chain=None):
        super().__init__(message, node, hints=hints, suggestions=suggestions, orig=orig, chain=chain)


class EventSuggestionException(EventException):
    """
    Event suggestion exception.
    """

    def __init__(self, message, node, hints=None, suggestions=None, orig=None, chain=None):
        super().__init__(message, node, hints=hints, suggestions=suggestions, orig=orig, chain=chain)


class NoEventSuggestionException(EventSuggestionException):
    """
    No event suggestion exception.
    """

    def __init__(self, node, hints=None, suggestions=None, orig=None, chain=None):
        message = "I could not find a matching time. Do you have a suggestion?"
        super().__init__(message, node, hints=hints, suggestions=suggestions, orig=orig, chain=chain)


class MultipleEventSuggestionsException(EventSuggestionException):
    """
    Multiple event suggestions exception.
    """

    def __init__(self, message, node, hints=None, suggestions=None, orig=None, chain=None):
        super().__init__(message, node, hints=hints, suggestions=suggestions, orig=orig, chain=chain)


class ClashEventSuggestionsException(EventSuggestionException):
    """
    Clashed event suggestion exception.
    """

    def __init__(self, message, node, hints=None, suggestions=None, orig=None, chain=None):
        super().__init__(message, node, hints=hints, suggestions=suggestions, orig=orig, chain=chain)


class WeatherInformationNotFoundException(ElementNotFoundException):
    """
    Exception when an element is not found.
    """

    def __init__(self, message, node, hints=None, suggestions=None, orig=None, chain=None):
        super().__init__(message, node, hints=hints, suggestions=suggestions, orig=orig, chain=chain)


class HolidayNotFoundException(ElementNotFoundException):
    """
    Exception when a holiday is not found.
    """

    def __init__(self, node, hints=None, suggestions=None, orig=None, chain=None):
        super().__init__("No holidays found.", node, hints=hints, suggestions=suggestions, orig=orig, chain=chain)


class MultipleHolidaysFoundException(ElementNotFoundException):
    """
    Exception when multiple holidays are found.
    """

    def __init__(self, node, hints=None, suggestions=None, orig=None, chain=None):
        super().__init__("Found more than one holiday, can you be more specific?",
                         node, hints=hints, suggestions=suggestions, orig=orig, chain=chain)


class AttendeeNotFoundException(ElementNotFoundException):
    """
    Exception when an element is not found.
    """

    def __init__(self, node, hints=None, suggestions=None, orig=None, chain=None):
        super().__init__(
            "No such attendee found on your calendar.",
            node, hints=hints, suggestions=suggestions, orig=orig, chain=chain)


class EventNotFoundException(ElementNotFoundException):
    """
    Exception when an element is not found.
    """

    def __init__(self, node, hints=None, suggestions=None, orig=None, chain=None):
        super().__init__(
            "No such event found on your calendar.",
            node, hints=hints, suggestions=suggestions, orig=orig, chain=chain)


class RecipientNotFoundException(ElementNotFoundException):
    """
    Exception when an element is not found.
    """

    def __init__(self, node, hints=None, suggestions=None, orig=None, chain=None,
                 message="No such recipient found on your calendar."):
        super().__init__(
            message,
            node, hints=hints, suggestions=suggestions, orig=orig, chain=chain)


class PlaceNotFoundException(ElementNotFoundException):
    """
    Exception when an element is not found.
    """

    def __init__(self, value, node, hints=None, suggestions=None, orig=None, chain=None):
        super().__init__(
            f"Error - Cannot find a place named {value}",
            node, hints=hints, suggestions=suggestions, orig=orig, chain=chain)


class PlaceNotFoundForUserException(ElementNotFoundException):
    """
    Exception when an element is not found.
    """

    def __init__(self, node, hints=None, suggestions=None, orig=None, chain=None):
        super().__init__(
            "Error - Can not find the location for the current user",
            node, hints=hints, suggestions=suggestions, orig=orig, chain=chain)
