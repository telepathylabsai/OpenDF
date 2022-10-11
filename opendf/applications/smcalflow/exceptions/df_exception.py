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

    def __init__(self, message, node, hints=None, suggestions=None, orig=None, chain=None, objects=None):
        super().__init__(message, node, hints=hints, suggestions=suggestions, orig=orig, chain=chain, objects=objects)


class BadEventConstraintException(EventException):
    """
    Bad event constraint exception.
    """

    def __init__(self, message, node, hints=None, suggestions=None, orig=None, chain=None, objects=None):
        super().__init__(message, node, hints=hints, suggestions=suggestions, orig=orig, chain=chain, objects=objects)


class EventConfirmationException(EventException):
    """
    Event confirmation exception.
    """

    def __init__(self, message, node, hints='confirm', suggestions=None, orig=None, chain=None, objects=None):
        super().__init__(message, node, hints=hints, suggestions=suggestions, orig=orig, chain=chain, objects=objects)


class BadEventDeletionException(EventException):
    """
    Bad event deletion exception.
    """

    def __init__(self, message, node, hints=None, suggestions=None, orig=None, chain=None, objects=None):
        super().__init__(message, node, hints=hints, suggestions=suggestions, orig=orig, chain=chain, objects=objects)


class EventSuggestionException(EventException):
    """
    Event suggestion exception.
    """

    def __init__(self, message, node, hints=None, suggestions=None, orig=None, chain=None, objects=None):
        super().__init__(message, node, hints=hints, suggestions=suggestions, orig=orig, chain=chain, objects=objects)


class NoEventSuggestionException(EventSuggestionException):
    """
    No event suggestion exception.
    """

    def __init__(self, node, message = "I could not find a matching time. Do you have a suggestion?",
                 hints=None, suggestions=None, orig=None, chain=None, objects=None):
        super().__init__(message, node, hints=hints, suggestions=suggestions, orig=orig, chain=chain, objects=objects)


class MultipleEventSuggestionsException(EventSuggestionException):
    """
    Multiple event suggestions exception.
    """

    def __init__(self, message, node, hints=None, suggestions=None, orig=None, chain=None, objects=None):
        super().__init__(message, node, hints=hints, suggestions=suggestions, orig=orig, chain=chain, objects=objects)


class ClashEventSuggestionsException(EventSuggestionException):
    """
    Clashed event suggestion exception.
    """

    def __init__(self, message, node, hints=None, suggestions=None, orig=None, chain=None, objects=None):
        super().__init__(message, node, hints=hints, suggestions=suggestions, orig=orig, chain=chain, objects=objects)


class WeatherInformationNotFoundException(ElementNotFoundException):
    """
    Exception when an element is not found.
    """

    def __init__(self, message, node, hints=None, suggestions=None, orig=None, chain=None, objects=None):
        super().__init__(message, node, hints=hints, suggestions=suggestions, orig=orig, chain=chain, objects=objects)


class HolidayNotFoundException(ElementNotFoundException):
    """
    Exception when a holiday is not found.
    """

    def __init__(self, node, message="No holidays found.", hints=None, suggestions=None, orig=None, chain=None, objects=None):
        super().__init__(message, node, hints=hints, suggestions=suggestions, orig=orig, chain=chain, objects=objects)


class MultipleHolidaysFoundException(ElementNotFoundException):
    """
    Exception when multiple holidays are found.
    """

    def __init__(self, node, message="Found more than one holiday, can you be more specific?",
                 hints=None, suggestions=None, orig=None, chain=None, objects=None):
        super().__init__(message,
                         node, hints=hints, suggestions=suggestions, orig=orig, chain=chain, objects=objects)


class AttendeeNotFoundException(ElementNotFoundException):
    """
    Exception when an element is not found.
    """

    def __init__(self, node, message="No such attendee found on your calendar.",
                 hints=None, suggestions=None, orig=None, chain=None, objects=None):
        super().__init__(
            message,
            node, hints=hints, suggestions=suggestions, orig=orig, chain=chain, objects=objects)


class EventNotFoundException(ElementNotFoundException):
    """
    Exception when an element is not found.
    """

    def __init__(self, node, message="No such event found on your calendar.",
                 hints=None, suggestions=None, orig=None, chain=None, objects=None):
        super().__init__(
            message, node, hints=hints, suggestions=suggestions, orig=orig, chain=chain, objects=objects)


class RecipientNotFoundException(ElementNotFoundException):
    """
    Exception when an element is not found.
    """

    def __init__(self, node, hints=None, suggestions=None, orig=None, chain=None,
                 message="No such recipient found on your calendar.", objects=None):
        super().__init__(
            message, node, hints=hints, suggestions=suggestions, orig=orig, chain=chain, objects=objects)


class PlaceNotFoundException(ElementNotFoundException):
    """
    Exception when an element is not found.
    """

    def __init__(self, value, node, hints=None, suggestions=None, orig=None, chain=None, objects=None):
        super().__init__(
            f"Error - Cannot find a place named {value}",
            node, hints=hints, suggestions=suggestions, orig=orig, chain=chain, objects=objects)


class PlaceNotFoundForUserException(ElementNotFoundException):
    """
    Exception when an element is not found.
    """

    def __init__(self, node, message="Error - Can not find the location for the current user",
                 hints=None, suggestions=None, orig=None, chain=None, objects=None):
        super().__init__(
            message,
            node, hints=hints, suggestions=suggestions, orig=orig, chain=chain, objects=objects)
