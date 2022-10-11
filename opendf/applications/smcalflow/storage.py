"""
Class to define an interface to interact with the SMCalFlow storage.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Set

from opendf.graph.nodes.node import Node


class DataEntry(ABC):
    """
    Represents a data entity.
    """

    @abstractmethod
    def unique_identifier(self):
        """
        Gets the unique identifier of the entity.

        :return: the unique identifier
        :rtype: Any
        """
        pass

    def __hash__(self):
        return hash(self.unique_identifier())

    def __eq__(self, other):
        if isinstance(other, DataEntry):
            return self.unique_identifier() == other.unique_identifier()

        return False

    def __repr__(self):
        return f"{self.__class__.__name__}(identifier={self.unique_identifier()})"


# Recipient will not have the friends field here because a recipient might have too many friends and, most of the time,
# we do not want to load the friends. In order to see the friends of a recipient, ask the storage class, by passing the
# recipient's id to the method get_friends
class RecipientEntry(DataEntry):
    """
    Defines a recipient.
    """

    def __init__(self, identifier, full_name, first_name, last_name, phone_number, email_address, manager_id):
        """
        Creates a recipient.

        :param identifier: the recipient identifier
        :type identifier: int
        :param full_name: the full name
        :type full_name: str
        :param first_name: the first name
        :type first_name: str
        :param last_name: the last name
        :type last_name: str
        :param phone_number: the phone number
        :type phone_number: str
        :param email_address: the email address
        :type email_address: str
        :param manager_id: the manager identifier
        :type manager_id: int
        """
        self.identifier = identifier
        self.full_name = full_name
        self.first_name = first_name
        self.last_name = last_name
        self.phone_number = phone_number
        self.email_address = email_address
        self.manager_id = manager_id

    def unique_identifier(self):
        return self.identifier

    def __repr__(self):
        return f"{self.__class__.__name__}(identifier={self.identifier}, full_name={self.full_name}, manager_id=" \
               f"{self.manager_id})"


# Differently from the recipient, that does not hold a field for the friends, the event has a field for the attendees,
# since we want to look at the attendees of an event very often.
class EventEntry(DataEntry):
    """
    Defines an event.
    """

    def __init__(self, identifier, subject, starts_at, ends_at, location, organizer, attendees):
        """
        Creates an event.

        :param identifier: the event identifier
        :type identifier: int
        :param subject: the subject
        :type subject: str
        :param starts_at: the starting datetime
        :type starts_at: datetime
        :param ends_at: the ending datetime
        :type ends_at: datetime
        :param location: the location
        :type location: LocationEntry
        :param organizer: the organizer
        :type organizer: RecipientEntry
        :param attendees: the attendees
        :type attendees: List[AttendeeEntry]
        """
        self.identifier = identifier
        self.subject = subject
        self.starts_at = starts_at
        self.ends_at = ends_at
        self.location = location
        self.organizer = organizer
        self.attendees = attendees

    def unique_identifier(self):
        return self.identifier

    def get_attendee_ids_set(self):
        """
        Gets a set containing the ids of the attendees of the event.

        :return: the set of ids of the attendees of the event
        :rtype: Set[int]
        """
        return set(map(lambda x: x.recipient.identifier, self.attendees))

    def __repr__(self):
        attendees = list(map(lambda x: x.unique_identifier(), self.attendees))
        return f"{self.__class__.__name__}(identifier={self.unique_identifier()}, subject={self.subject}, starts_at=" \
               f"{self.starts_at}, ends_at={self.ends_at}, location={self.location}, " \
               f"organizer_id={self.organizer.unique_identifier()}, attendees_ids={attendees})"


class LocationEntry(DataEntry):
    """
    Defines a location.
    """

    def __init__(self, identifier, name=None, address=None, latitude=None, longitude=None, radius=None,
                 always_free=None, is_virtual=None):
        """
        Creates a location.

        :param identifier: the location identifier
        :type identifier: int
        :param name: the name
        :type name: Optional[str]
        :param name: the name
        :type name: Optional[str]
        :param name: the name
        :type name: Optional[str]
        :param name: the name
        :type name: Optional[str]
        :param name: the name
        :type name: Optional[str]
        :param always_free: Whether the location is always free. For instance, it if location is a city, does not make
        sense to check if the city is free when booking an appointment at the location
        :type always_free: Optional[bool]
        :param is_virtual: Whether the location represents a virtual (online) location
        :type is_virtual: Optional[bool]
        """
        self.identifier = identifier
        self.name = name
        self.address = address
        self.latitude = latitude
        self.longitude = longitude
        self.radius = radius
        self.always_free = always_free
        self.is_virtual = is_virtual

    def unique_identifier(self):
        return self.identifier

    def __repr__(self):
        return f"{self.__class__.__name__}(identifier={self.unique_identifier()}, name={self.name}, " \
               f"always_free={self.always_free})"


class AttendeeEntry(DataEntry):
    """
    Defines an attendee.
    """

    def __init__(self, event_id, recipient, show_as_status, response_status):
        """
        Creates an attendee.

        :param event_id: the event identifier
        :type event_id: int
        :param recipient: the recipient
        :type recipient: RecipientEntry
        :param show_as_status: the show as status
        :type show_as_status: str
        :param response_status: the response status
        :type response_status: str
        """
        self.event_id = event_id
        self.recipient = recipient
        self.show_as_status = show_as_status
        self.response_status = response_status

    def unique_identifier(self):
        return self.event_id, self.recipient.unique_identifier()


class HolidayEntry(DataEntry):
    """
    Defines a Holiday.
    """

    def __init__(self, name, date):
        """
        Creates a Holiday.

        :param name: the holiday name
        :type name: str
        :param date: the holiday date
        :type date: date
        """
        self.name = name
        self.date = date

    def unique_identifier(self):
        return self.name, self.date

    def __repr__(self):
        return f"{self.name} on {self.date}"


class Storage(ABC):
    """
    Defines a unified interface to store and retrieve data.
    """

    @abstractmethod
    def get_current_recipient_id(self):
        """
        Gets the identifier of the current recipient.

        :return: the identifier of the current recipient
        :rtype: int
        """
        pass

    # TODO: this function should be improved to use a better authentication system.
    @abstractmethod
    def set_current_recipient_id(self, identifier):
        """
        Sets the current recipient identifier.

        :param identifier: the new identifier
        :type identifier: int
        """
        pass

    @abstractmethod
    def get_current_recipient_entry(self):
        """
        Gets the current recipient entry.

        :return: the current recipient
        :rtype: Optional[RecipientEntry]
        """
        pass

    @abstractmethod
    def get_current_recipient_graph(self, d_context):
        """
        Gets the current recipient graph.

        :return: the current recipient graph
        :rtype: Optional[Node]
        """
        pass

    @abstractmethod
    def get_current_attendee_graph(self, d_context):
        """
        Gets the current attendee graph.

        :return: the current attendee graph
        :rtype: Optional[Node]
        """
        pass

    @abstractmethod
    def get_current_recipient_location(self):
        """
        Returns the location of the current recipient.

        :return:  the location of the current recipient
        :rtype: Optional[LocationEntry]
        """
        pass

    def set_current_recipient_location_id(self, value):
        """
        Sets the id of the location of the current recipient.

        :param value: the id of the location
        :type value: int
        """
        pass

    @abstractmethod
    def get_recipient_entry(self, identifier):
        """
        Gets the recipient entry based on the `identifier`.

        :param identifier: the identifier
        :type identifier: int
        :return: the recipient entry
        :rtype: Optional[RecipientEntry]
        """
        pass

    @abstractmethod
    def get_recipient_graph(self, identifier, d_context, update_cache=True):
        """
        Gets the recipient graph based on the `identifier`.

        :param identifier: the identifier
        :type identifier: int
        :return: the recipient graph
        :rtype: Optional[Node]
        """
        pass

    @abstractmethod
    def get_attendee_graph(self, event_id, recipient_id, d_context):
        """
        Gets the attendee graph based on the `identifier`.

        :param event_id: the identifier of the event
        :type event_id: int
        :param recipient_id: the identifier of the recipient
        :type recipient_id: int
        :return: the attendee graph
        :rtype: Optional[Node]
        """
        pass

    @abstractmethod
    def get_manager(self, recipient_id):
        """
        Gets the manager of the recipient.

        :param recipient_id: the recipient identifier
        :type recipient_id: int
        :return: the manager of the recipient
        :rtype: Optional[RecipientEntry]
        """
        pass

    @abstractmethod
    def get_friends(self, recipient_id):
        """
        Gets the friends of the recipient.

        :param recipient_id: the recipient identifier
        :type recipient_id: int
        :return: the friends of the recipient
        :rtype: List[int]
        """
        pass

    @abstractmethod
    def find_recipients_that_match(self, operator, d_context):
        """
        Gets the recipient graphs that match the `operator`.

        :param operator: the operator
        :type operator: Optional[Node]
        :return: the recipients that match the operator
        :rtype: List[Node]
        """
        pass

    def find_attendees_that_match(self, operator, d_context):
        """
        Gets the attendee graphs that match the `operator`.

        :param operator: the operator
        :type operator: Optional[Node]
        :return: the recipients that match the operator
        :rtype: List[Node]
        """
        pass

    @abstractmethod
    def find_events_that_match(self, operator, d_context):
        """
        Gets the event graphs that match the `operator`.

        :param operator: the operator
        :type operator: Optional[Node]
        :return: the events that match the operator
        :rtype: List[Node]
        """
        pass

    @abstractmethod
    def find_locations_that_match(self, operator):
        """
        Gets the location entries that match the `operator`.

        :param operator: the operator
        :type operator: Optional[Node]
        :return: the locations that match the operator
        :rtype: List[LocationEntry]
        """
        pass

    @abstractmethod
    def find_feature_for_place(self, place_id, feature=None):
        """
        Gets the features for the place. If `feature` is given, returns only the features that match `feature`.

        :return: the list of features of the place
        :rtype: List[str]
        """
        pass

    @abstractmethod
    def find_holidays_that_match(self, d_context, name=None, holiday_date=None, sort=None, limit=None):
        """
        Gets the holidays that match `name` and `holiday_date`. If `name` is given, returns only the holidays that
        match `name`. If `holiday_date` is given, returns only the holidays that match `holiday_date`. If both are
        given, returns the holidays that match both.


        :param name: the name to filter the holiday
        :type name: Node or Any
        :param holiday_date: the date to filter the holiday
        :type holiday_date: Node
        :param sort: ASC, DESC or `None`; if `None`, no sorting is performed
        :type sort: Optional[str]
        :param limit: if set, limits the number of returned items
        :type limit: Optional[int]
        :return: the list of holidays
        :rtype: List[HolidayEntry]
        """
        pass

    @abstractmethod
    def get_event_entry(self, identifier):
        """
        Gets the event entry based on the `identifier`.

        :param identifier: the identifier
        :type identifier: int
        :return: the event entry
        :rtype: Optional[EventEntry]
        """
        pass

    @abstractmethod
    def get_event_graph(self, identifier, d_context):
        """
        Gets the event graph based on the `identifier`.

        :param identifier: the identifier
        :type identifier: int
        :return: the event graph
        :rtype: Optional[Node]
        """
        pass

    @abstractmethod
    def add_event(self, subject, start, end, location, attendees):
        """
        Adds the event to the storage.

        :param subject: the subject
        :type subject: str
        :param start: the start
        :type start: datetime
        :param end: the end
        :type end: datetime
        :param location: the location
        :type location: str
        :param attendees: the list of ids from the attendees
        :type attendees: List[int]
        :return: the created event
        :rtype: EventEntry
        """
        pass

    @abstractmethod
    def update_event(self, identifier, subject, start, end, location, attendees):
        """
        Updates the event with the given `identifier` to have the new fields.

        :param identifier: the identifier
        :type identifier: int
        :param subject: the new subject
        :type subject: str
        :param start: the new start
        :type start: datetime
        :param end: the new end
        :type end: datetime
        :param location: the new location
        :type location: str
        :param attendees: the new attendees
        :type attendees: List[int]
        :return: the updated event
        :rtype: EventEntry
        """
        pass

    @abstractmethod
    def delete_event(self, identifier, subject, start, end, location, attendees):
        """
        Deletes the event, if it exists in the storage system as described by the parameters.

        :param identifier: the identifier
        :type identifier: int
        :param subject: the subject
        :type subject: str
        :param start: the start
        :type start: datetime
        :param end: the end
        :type end: datetime
        :param location: the location
        :type location: str
        :param attendees: the list of ids from the attendees
        :type attendees: List[int]
        :return: the deleted event, if the event was deleted successfully; otherwise, `False`
        :rtype: Optional[EventEntry]
        """
        pass

    @abstractmethod
    def get_events(self, identifier=None, avoid_id=None, subject=None, start=None, end=None, location=None,
                   attendees=None, pre_filter=None, with_current_recipient=True):
        """
        Gets events that match with the parameter, if a parameter is given, the event must match it.

        It is a simple filter, more complex filters should be handled by a graph match.

        :param identifier: the identifier of the event
        :type identifier: Optional[int]
        :param avoid_id: the identifier of an event to avoid
        :type avoid_id: Optional[int]
        :param subject: the subject of the event
        :type subject: Optional[str]
        :param start: the start
        :type start: Optional[str]
        :param end: the end
        :type end: Optional[str]
        :param location: the location
        :type location: Optional[str]
        :param attendees: the list of attendees ids
        :type attendees: Optional[List[int]]
        :param pre_filter: a subset of event, if given, only these events are considered
        :type pre_filter: Optional[List[EventEntry]]
        :param with_current_recipient: if `True`, only events containing the current user is considered
        :type with_current_recipient: bool
        :return: the list of matched events
        :rtype: List[EventEntry]
        """
        pass

    @abstractmethod
    def get_time_overlap_events(self, start, end, attendees, avoid_id=None, pre_filter=None):
        """
        Gets a list of events whose time overlap with `start` and `end` and has attendee.

        :param start: the start
        :type start: str
        :param end: the end
        :type end: str
        :param attendees: a list of attendees ids
        :type attendees: List[int]
        :param avoid_id: if given, the event with this identifier will be ignored
        :type avoid_id: Optional[int]
        :param pre_filter: a subset of event, if given, only these events are considered
        :type pre_filter: Optional[List[EventEntry]]
        :return: the list of overlapping events
        :rtype: List[EventEntry]
        """
        pass

    @abstractmethod
    def get_location_overlap_events(self, location, start=None, end=None, avoid_id=None, pre_filter=None):
        """
        Gets a list of events whose time overlap with `start`, `end` and location.

        :param location: the location
        :type location: str
        :param start: the start
        :type start: Optional[str]
        :param end: the end
        :type end: Optional[str]
        :param avoid_id: if given, the event with this identifier will be ignored
        :type avoid_id: Optional[int]
        :param pre_filter: a subset of event, if given, only these events are considered
        :type pre_filter: Optional[List[EventEntry]]
        :return: the list of overlapping events
        :rtype: List[EventEntry]
        """
        pass

    @abstractmethod
    def is_recipient_free(self, recipient_id, start, end, avoid_id=None):
        """
        Checks if the `recipient` is free between the period defined by `start` and `end`.

        If `avoid_event` is given, do not consider it when checking the availability of the recipient.

        :param recipient_id: the recipient identifier
        :type recipient_id: int
        :param start: the start of the period
        :type start: datetime
        :param end: the end of the period
        :type end: datetime
        :param avoid_id: the event to avoid during the check
        :type avoid_id: Optional[int]
        :return: `True`, if the recipient is free during the given period; otherwise, `False`
        :rtype: bool
        """
        pass

    @abstractmethod
    def is_location_free(self, location, start, end, avoid_id=None):
        """
        Checks if the `location` is free between the period defined by `start` and `end`.

        If `avoid_event` is given, do not consider it when checking the availability of the recipient.

        :param location: the location
        :type location: str
        :param start: the start of the period
        :type start: datetime
        :param end: the end of the period
        :type end: datetime
        :param avoid_id: the event to avoid during the check
        :type avoid_id: Optional[int]
        :return: `True`, if the location is free during the given period; otherwise, `False`
        :rtype: bool
        """
        pass
