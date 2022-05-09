"""
Class to interact with a relational database specific for the application.
"""

from datetime import datetime, timedelta, time, date
from typing import Sequence, Optional, Dict, List, Tuple

import sqlalchemy
from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, ForeignKey, DateTime, insert, \
    Boolean, select, func, update, delete, text, and_, or_, not_, cast, Date, Float

from opendf.applications.core.nodes.time_nodes import Pdate_to_date_sexp
from opendf.applications.smcalflow.domain import recipient_to_str_node, event_to_str_node, match_start, match_end, \
    attendees_to_str_node, TIME_SUITABLE_FOR_SUBJECT
from opendf.applications.smcalflow.storage import Storage, RecipientEntry, AttendeeEntry, LocationEntry, EventEntry, \
    HolidayEntry
from opendf.applications.smcalflow.stub_data import db_events, db_persons, CURRENT_RECIPIENT_ID, weather_places, \
    place_has_features, CURRENT_RECIPIENT_LOCATION_ID, HOLIDAYS
from opendf.exceptions.python_exception import SingletonClassException
from opendf.graph.nodes.node import Node
from opendf.defs import database_connection, database_log, database_future, NODE_COLOR_DB, DB_NODE_TAG, \
    event_suggestion_period, minimum_slot_interval, minimum_duration, maximum_duration_days, get_system_date, posname, \
    get_system_datetime
from opendf.utils.database_utils import get_database_handler
from opendf.utils.utils import to_list, str_to_datetime, id_sexp

database_handler = get_database_handler()


def create_recipient_from_row(row):
    """
    Create a recipient entry from the select row from the database.

    :param row: the row
    :type row: Any
    :return: the recipient entry
    :rtype: RecipientEntry
    """
    return RecipientEntry(row.id, row.full_name, row.first_name, row.last_name, row.phone_number,
                          row.email_address, row.manager_id)


def time_in_holiday(time_column, label="in_holiday"):
    """
    Returns a database column that is `True` if the time on `time_column` is in a holiday; or `False`,
    otherwise.

    The holidays are defined on the holiday table.

    :param time_column: the time column
    :type time_column: Any
    :param label: the label of the column
    :type label: str
    :return: the holiday column
    :rtype: Any
    """
    return database_handler.to_database_date(time_column).in_(select(Database.HOLIDAY_TABLE.columns.date)).label(label)


# TODO: maybe we should account for the starting and ending of an event.
#   It might not be so simple, because an event may spam over more than one day
def time_in_off_hours(time_column, starting_hour=9, ending_hour=17, label="in_off_hours"):
    """
    Returns a database column that is `True` if the time on `time_column` is not in working hours; or `False`,
    otherwise.

    :param time_column: the time column
    :type time_column: Any
    :param starting_hour: the starting hour
    :type starting_hour: int
    :param ending_hour: the ending hour
    :type ending_hour: int
    :param label: the label of the column
    :type label: str
    :return: the `not in working hours` column
    :rtype: Any
    """
    time_column_ = database_handler.to_database_time(time_column)
    time_condition = [time_column_ < database_handler.to_database_time(time(starting_hour)),
                      time_column_ > database_handler.to_database_time(time(ending_hour))]
    day_of_week = database_handler.database_date_to_day_of_week(time_column)
    day_of_the_week_condition = [day_of_week < 1, day_of_week > 5]

    return or_(*(time_condition + day_of_the_week_condition)).self_group().label(label)


def time_bad_for_subject(time_column, subject, label="bad_for_subject"):
    """
    Returns a database column that is `True` if the time on `time_column` is bad for the subject; or `False`,
    if the time is suitable for the subject.

    The definition of a suitable time for the subject is given in `applications.ms_domain.TIME_SUITABLE_FOR_SUBJECT`.

    :param time_column: the time column
    :type time_column: Any
    :param subject: the subject
    :type subject: str
    :param label: the label of the column
    :type label: str
    :return: the bad for subject column
    :rtype: Any
    """
    time_range = TIME_SUITABLE_FOR_SUBJECT.get(subject.lower())
    if time_range is None:
        column = sqlalchemy.sql.expression.bindparam(label, False).label(label)
    else:
        time_column_ = database_handler.to_database_time(time_column)
        column = cast(not_(and_(
            database_handler.to_database_time(time_range[0]) <= time_column_,
            time_column_ <= database_handler.to_database_time(time_range[-1]))), Boolean).label(label)

    return column


def select_event_with_overlap(start, end, selection):
    """
    Adds a where clause to `selection`, in order to filter events that have an overlap with `start` and `end`.

    :param start: the start; it can be a string, a datetime object or a database object
    :type start: str or datetime or Any
    :param end: the end; it can be a string, a datetime object or a database object
    :type end: str or datetime or Any
    :param selection: the selection query
    :type selection: Any
    :return: the selection query with the appropriated where conditions
    :rtype: Any
    """
    if isinstance(start, str):
        start = str_to_datetime(start)  # b2
    if isinstance(start, datetime):
        start = database_handler.to_database_datetime(start)

    if isinstance(end, str):
        end = str_to_datetime(end)  # e2
    if isinstance(end, datetime):
        end = database_handler.to_database_datetime(end)

    selection = selection.where(or_(
        # event starts before start AND ends after start
        # starting point is between event's start and end
        and_(Database.EVENT_TABLE.columns.starts_at <= start,
             start < Database.EVENT_TABLE.columns.ends_at).self_group(),

        # event starts before end AND ends after end
        # ending point is between event's start and end
        and_(Database.EVENT_TABLE.columns.starts_at < end,
             end <= Database.EVENT_TABLE.columns.ends_at).self_group(),

        # event starts after start AND before end
        # event's starting point is between start and end
        and_(start <= Database.EVENT_TABLE.columns.starts_at,
             Database.EVENT_TABLE.columns.starts_at < end).self_group(),

        # event ends after start ADN before end
        # event's ending point is between start and end
        and_(start < Database.EVENT_TABLE.columns.ends_at,
             Database.EVENT_TABLE.columns.ends_at <= end).self_group(),
    ).self_group())
    return selection


class Database(Storage):
    """
    Class to interact with the database.
    """

    __instance = None

    metadata = MetaData()

    RECIPIENT_TABLE = Table(
        "recipient", metadata,
        Column("id", Integer, primary_key=True),
        Column("full_name", String),
        Column("first_name", String),
        Column("last_name", String),
        Column("phone_number", String),
        Column("email_address", String),
        Column("manager_id", ForeignKey("recipient.id"), nullable=False),
    )

    RECIPIENT_HAS_FRIEND_TABLE = Table(
        "recipient_has_friend", metadata,
        Column("recipient_id", ForeignKey("recipient.id"), nullable=False, primary_key=True),
        Column("friend_id", ForeignKey("recipient.id"), nullable=False, primary_key=True)
    )

    LOCATION_TABLE = Table(
        "location", metadata,
        Column("id", Integer, primary_key=True),
        Column("name", String),
        Column("address", String),
        Column("latitude", Float),
        Column("longitude", Float),
        Column("radius", Float),
        Column("always_free", Boolean),
        Column("is_virtual", Boolean),
    )

    EVENT_TABLE = Table(
        "event", metadata,
        Column("id", Integer, primary_key=True),
        Column("subject", String),
        Column("starts_at", DateTime),
        Column("ends_at", DateTime),
        Column("location_id", ForeignKey("location.id")),
        Column("organizer_id", ForeignKey("recipient.id")),
    )

    EVENT_HAS_ATTENDEE_TABLE = Table(
        "event_has_attendee", metadata,
        Column("event_id", ForeignKey("event.id"), nullable=False, primary_key=True),
        Column("recipient_id", ForeignKey("recipient.id"), nullable=False, primary_key=True),
        Column("show_as_status", String),  # e.g. busy, free, away... it should be a foreign key for a table
        #  containing all possible status, for now, it is a string, for simplicity
        Column("response_status", String)  # e.g. accepted, rejected, not responded... same comment as above
    )

    PLACE_FEATURE_TABLE = Table(
        "place_feature", metadata,
        Column("id", Integer, primary_key=True),
        Column("feature", String, nullable=False),
    )

    PLACE_HAS_FEATURE_TABLE = Table(
        "place_has_feature", metadata,
        Column("location_id", ForeignKey("location.id"), nullable=False, primary_key=True),
        Column("feature_id", ForeignKey("place_feature.id"), nullable=False, primary_key=True),
    )

    POSSIBLE_TIME_TABLE = Table(
        "possible_time", metadata,
        Column("point_in_time", DateTime, nullable=False, primary_key=True)
    )

    POSSIBLE_DURATION_TABLE = Table(
        "possible_duration", metadata,
        Column("offset", Integer, nullable=False, primary_key=True)
    )

    HOLIDAY_TABLE = Table(
        "holiday", metadata,
        Column("name", String, nullable=False, primary_key=True),
        Column("date", Date, nullable=False, primary_key=True),
    )

    @staticmethod
    def get_instance():
        """
        Static access method.

        :return: the database instance
        :rtype: Database or None
        """
        if Database.__instance is None:
            Database.__instance = Database()
        return Database.__instance

    def __init__(self, connection_string=None):
        """
        Create the database class.
        """
        if Database.__instance is not None:
            raise SingletonClassException()
        if connection_string is None:
            connection_string = database_connection
        Database.__instance = self
        self.engine: sqlalchemy.engine.base.Engine = \
            create_engine(connection_string, echo=database_log, future=database_future)
        self._create_database()
        self._current_recipient_id: Optional[int] = None
        self._current_recipient_location_id: Optional[int] = None

        # cache for the node representation of the entities
        self._recipient_graph: Dict[int, Node] = {}
        self._attendee_graph: Dict[Tuple[int, int], Node] = {}
        self._event_graph: Dict[int, Node] = {}
        self._location_graph: Dict[int, Node] = {}

    def erase_database(self):
        """
        Erases the database.
        This method only touches the tables created by this class.
        """
        self.metadata.drop_all(self.engine)
        self.metadata.clear()  # clear the tables known by the metadata

    def clean_database(self):
        """
        Erase all data from the database, but does not delete the scheme.
        This method only touches the tables created by this class.
        """
        with self.engine.connect() as connection:
            transaction = connection.begin()
            for table in reversed(self.metadata.sorted_tables):
                connection.execute(table.delete())
            transaction.commit()

    def _create_database(self):
        """
        Create the database for the application. During testing, we will create the database whenever the application is
        lunched and destroy it whenever it finishes, this behaviour must be changed on production phase.
        """
        self.metadata.create_all(self.engine)

    def get_current_recipient_id(self):
        return self._current_recipient_id

    def set_current_recipient_id(self, identifier):
        self._current_recipient_id = identifier

    def get_current_recipient_entry(self):
        return self.get_recipient_entry(self._current_recipient_id)

    def get_current_recipient_graph(self, d_context):
        return self.get_recipient_graph(self._current_recipient_id, d_context)

    def get_current_attendee_graph(self, d_context):
        return self.get_attendee_graph(None, self._current_recipient_id, d_context)

    def get_current_recipient_location(self):
        with self.engine.connect() as connection:
            selection = select(self.LOCATION_TABLE).where(
                self.LOCATION_TABLE.columns.id == self._current_recipient_location_id)
            for row in connection.execute(selection):
                return self._location_entry_from_row(row)

        return None

    def set_current_recipient_location_id(self, value):
        self._current_recipient_location_id = value

    def get_recipient_entry(self, identifier):
        with self.engine.connect() as connection:
            selection = select(self.RECIPIENT_TABLE).where(self.RECIPIENT_TABLE.columns.id == identifier)
            for row in connection.execute(selection):
                return create_recipient_from_row(row)

        return None

    def get_recipient_graph(self, identifier, d_context, update_cache=True):
        recipient_graph = self._recipient_graph.get(identifier)
        if recipient_graph is None:
            recipient_entry = self.get_recipient_entry(identifier)
            if recipient_entry is None:
                return None
            string_entry = recipient_to_str_node(recipient_entry)
            recipient_graph, _ = Node.call_construct_eval(string_entry, d_context, constr_tag=NODE_COLOR_DB)
            recipient_graph.tags[DB_NODE_TAG] = 0
            if update_cache:
                self._recipient_graph[identifier] = recipient_graph

        return recipient_graph

    def get_attendee_graph(self, event_id, recipient_id, d_context):
        attendee_graph = self._attendee_graph.get((event_id, recipient_id))
        if attendee_graph is None:
            recipient_entry = self.get_recipient_entry(recipient_id)
            recipient_graph = self.get_recipient_graph(recipient_id, d_context)
            if recipient_graph is None:
                return None
            # TODO: replace string literals by default values for `show as status` and `response status`
            # noinspection PyTypeChecker
            attendee = AttendeeEntry(None, recipient_entry, "Busy", "NotResponded")
            string_entry = attendees_to_str_node([attendee], [recipient_graph])
            attendee_graph, _ = Node.call_construct_eval(string_entry, d_context, constr_tag=NODE_COLOR_DB)
            attendee_graph.tags[DB_NODE_TAG] = 0
            self._attendee_graph[(event_id, recipient_id)] = attendee_graph

        return attendee_graph

    def get_manager(self, recipient_id):
        with self.engine.connect() as connection:
            recipient = self.RECIPIENT_TABLE.alias("r")
            manager = self.RECIPIENT_TABLE.alias("m")
            selection = select(manager).join(recipient, recipient.c.manager_id == manager.c.id).where(
                recipient.c.id == recipient_id)
            for row in connection.execute(selection):
                return create_recipient_from_row(row)

        return None

    def get_friends(self, recipient_id):
        friends = []
        with self.engine.connect() as connection:
            selection = select(self.RECIPIENT_HAS_FRIEND_TABLE.columns.friend_id).where(
                self.RECIPIENT_HAS_FRIEND_TABLE.columns.recipient_id == recipient_id)
            for row in connection.execute(selection):
                friends.append(row.friend_id)

        return friends

    def _find_recipient_from_operator_query(self, selection, d_context):
        """
        Returns all the recipient graphs from the `selection` query.

        :param selection: the SQL query to retrieve the recipients
        :type selection: Any
        :return: the recipient graphs
        :rtype: List[Node]
        """
        recipients = []
        with self.engine.connect() as connection:
            for row in connection.execute(selection):
                recipient_graph = self.get_recipient_graph(row.id, d_context)
                recipients.append(recipient_graph)

        return recipients

    def find_recipients_that_match(self, operator, d_context):
        try:
            if operator is not None:
                selection = operator.generate_sql()
                if selection is not None:
                    return self._find_recipient_from_operator_query(selection, d_context)
        except:
            pass
        recipients = []
        with self.engine.connect() as connection:
            selection = select(self.RECIPIENT_TABLE.columns.id)
            for row in connection.execute(selection):
                recipient_graph = self.get_recipient_graph(row.id, d_context, update_cache=False)
                if operator is None or operator.match(recipient_graph):
                    recipients.append(recipient_graph)
                    self._recipient_graph[row.id] = recipient_graph

        return recipients

    def _find_attendees_from_operator_query(self, selection, d_context):
        """
        Returns all the recipient graphs from the `selection` query.

        :param selection: the SQL query to retrieve the recipients
        :type selection: Any
        :return: the recipient graphs
        :rtype: List[Node]
        """
        attendees = []
        with self.engine.connect() as connection:
            for row in connection.execute(selection):
                attendee = self._attendee_graph.get((row.event_id, row.recipient_id))
                if attendee is None:
                    recipient_graph = self.get_recipient_graph(row.recipient_id, d_context)
                    attendee, _ = Node.call_construct_eval(
                        f"Attendee(recipient={id_sexp(recipient_graph)}, response={row.response_status}, "
                        f"show={row.show_as_status}, eventid={row.event_id})", d_context)
                    attendees.append(attendee)
                    self._attendee_graph[(row.event_id, row.recipient_id)] = attendee

        return attendees

    def find_attendees_that_match(self, operator, d_context):
        try:
            if operator is not None:
                selection = operator.generate_sql()
                if selection is not None:
                    return self._find_attendees_from_operator_query(selection, d_context)
        except:
            pass
        attendees = []
        with self.engine.connect() as connection:
            selection = select(self.EVENT_HAS_ATTENDEE_TABLE)
            for row in connection.execute(selection):
                recipient_graph = self.get_recipient_graph(row.recipient_id, d_context, update_cache=False)
                attendee, _ = Node.call_construct_eval(
                    f"Attendee(recipient={id_sexp(recipient_graph)}, response={row.response_status}, "
                    f"show={row.show_as_status}, eventid={row.event_id})", d_context)
                if operator is None or operator.match(attendee):
                    attendees.append(attendee)
                    self._attendee_graph[(row.event_id, row.recipient_id)] = attendee

        return attendees

    def _find_events_from_operator_query(self, selection, d_context):
        """
        Returns all the event graphs from the `selection` query.

        :param selection: the SQL query to retrieve the events
        :type selection: Any
        :return: the event graphs
        :rtype: List[Node]
        """
        events = []
        with self.engine.connect() as connection:
            for row in connection.execute(selection):
                event_graph = self.get_event_graph(row.id, d_context)
                events.append(event_graph)

        return events

    def find_events_that_match(self, operator, d_context):
        try:
            if operator is not None:
                selection = operator.generate_sql()
                if selection is not None:
                    return self._find_events_from_operator_query(selection, d_context)
        except:
            pass
        events = []
        with self.engine.connect() as connection:
            selection = select(self.EVENT_TABLE.columns.id)
            for row in connection.execute(selection):
                event_graph = self.get_event_graph(row.id, d_context, update_cache=False)
                if operator is None or operator.match(event_graph):
                    events.append(event_graph)
                    self._event_graph[row.id] = event_graph

        return events

    def _find_locations_from_operator_query(self, selection):
        """
        Returns all the location entries from the `selection` query.

        :param selection: the SQL query to retrieve the locations
        :type selection: Any
        :return: the location entries
        :rtype: List[LocationEntry]
        """
        locations = []
        with self.engine.connect() as connection:
            for row in connection.execute(selection):
                locations.append(self._location_entry_from_row(row))

        return locations

    def find_locations_that_match(self, operator):
        if operator is not None:
            selection = operator.generate_sql()
            if selection is not None:
                return self._find_locations_from_operator_query(selection)
        locations = []
        location_name = operator.res.dat
        with self.engine.connect() as connection:
            selection = select(self.LOCATION_TABLE)
            for row in connection.execute(selection):
                if location_name in row.name:
                    locations.append(self._location_entry_from_row(row))

        return locations

    def find_feature_for_place(self, place_id, feature=None):
        with self.engine.connect() as connection:
            selection = select(self.PLACE_FEATURE_TABLE.columns.feature).join(
                self.PLACE_HAS_FEATURE_TABLE).where(self.PLACE_HAS_FEATURE_TABLE.columns.location_id == place_id)
            if feature:
                selection = selection.where(self.PLACE_FEATURE_TABLE.columns.feature.like(feature))
            features = list(map(lambda x: x.feature, connection.execute(selection)))

        return features

    def _find_all_holidays_from_selection(self, selection):
        holidays = []
        with self.engine.connect() as connection:
            for row in connection.execute(selection):
                holidays.append(HolidayEntry(row.name, row.date))
        return holidays

    def find_holidays_that_match(self, d_context, name=None, holiday_date=None, sort=None, limit=None):
        if isinstance(name, Node) and name.typename() == "Holiday":
            selection = name.generate_sql()
            if selection is not None:
                if isinstance(holiday_date, Node) and (
                        holiday_date.typename() == "Date" or holiday_date.is_qualifier()):
                    selection = holiday_date.generate_sql_where(selection, self.HOLIDAY_TABLE.columns.date)
                    if sort:
                        if sort.lower() == "desc":
                            selection = selection.order_by(self.HOLIDAY_TABLE.columns.date.desc())
                        else:
                            selection = selection.order_by(self.HOLIDAY_TABLE.columns.date)
                    if limit is not None:
                        selection = selection.limit(limit)

                    return self._find_all_holidays_from_selection(selection)

        holidays = []
        with self.engine.connect() as connection:
            selection = select(self.HOLIDAY_TABLE)
            if name is not None:
                selection = selection.where(self.HOLIDAY_TABLE.columns.name.like(f"%{name.get_dat(posname(1))}%"))
            if sort:
                if sort.lower() == "desc":
                    selection = selection.order_by(self.HOLIDAY_TABLE.columns.date.desc())
                else:
                    selection = selection.order_by(self.HOLIDAY_TABLE.columns.date)
            for row in connection.execute(selection):
                if holiday_date is not None:
                    holiday_date_graph, _ = Node.call_construct_eval(Pdate_to_date_sexp(row.date), d_context)
                    if not holiday_date.match(holiday_date_graph):
                        continue
                holidays.append(HolidayEntry(row.name, row.date))
                if limit is not None and len(holidays) == limit:
                    break

        return holidays

    def _get_attendees_from_event(self, event_id):
        """
        Gets the list of attendees from the event.

        :param event_id: the event id
        :type event_id: int
        :return: the list of attendees from the event
        :rtype: List[AttendeeEntry]
        """
        attendees = []
        with self.engine.connect() as connection:
            selection = select(self.EVENT_HAS_ATTENDEE_TABLE, self.RECIPIENT_TABLE).join(self.RECIPIENT_TABLE).where(
                self.EVENT_HAS_ATTENDEE_TABLE.columns.event_id == event_id)
            for row in connection.execute(selection):
                recipient_entry = create_recipient_from_row(row)
                attendees.append(AttendeeEntry(event_id, recipient_entry, row.show_as_status, row.response_status))

        return attendees

    def _get_event_entries(self, identifiers):
        """
        Gets a list of event entries with the given `identifiers`.

        :param identifiers: the identifiers
        :type identifiers: List[int]
        :return: the event entries
        :rtype: List[EventEntry]
        """
        if not identifiers:
            return []
        with self.engine.connect() as connection:
            selection = select(self.EVENT_TABLE, self.LOCATION_TABLE, self.RECIPIENT_TABLE).join(
                self.LOCATION_TABLE, self.EVENT_TABLE.columns.location_id == Database.LOCATION_TABLE.columns.id,
                isouter=True).join(self.RECIPIENT_TABLE).where(self.EVENT_TABLE.columns.id.in_(identifiers))
            events = []
            for row in connection.execute(selection):
                attendees = self._get_attendees_from_event(row.id)
                organizer = RecipientEntry(row.id_2, row.full_name, row.first_name, row.last_name,
                                           row.phone_number, row.email_address, row.manager_id)
                location = self._location_entry_from_row(row)
                event = EventEntry(row.id, row.subject, row.starts_at, row.ends_at, location, organizer, attendees)
                events.append(event)

        return events

    def _location_entry_from_row(self, row):
        """
        Creates a `LocationEntry` from the `row` result from the database.

        :param row: the row result
        :type row: Any
        :return: the location entry
        :rtype: LocationEntry
        """
        return LocationEntry(
            row[Database.LOCATION_TABLE.columns.id],
            name=row[Database.LOCATION_TABLE.columns.name],
            address=row[Database.LOCATION_TABLE.columns.address],
            latitude=row[Database.LOCATION_TABLE.columns.latitude],
            longitude=row[Database.LOCATION_TABLE.columns.longitude],
            radius=row[Database.LOCATION_TABLE.columns.radius],
            always_free=row[Database.LOCATION_TABLE.columns.always_free],
            is_virtual=row[Database.LOCATION_TABLE.columns.is_virtual],
        )

    def get_event_entry(self, identifier):
        events = self._get_event_entries([identifier])
        if len(events) > 0:
            return events[0]

        return None

    def get_event_graph(self, identifier, d_context, update_cache=True):
        event_graph = self._event_graph.get(identifier)
        if event_graph is None:
            event_entry = self.get_event_entry(identifier)
            if event_entry is None:
                return None
            recipient_nodes = \
                [self.get_recipient_graph(attendee.recipient.identifier, d_context) for attendee in event_entry.attendees]
            string_entry = event_to_str_node(event_entry, recipient_nodes)
            event_graph, _ = Node.call_construct_eval(string_entry, d_context, constr_tag=NODE_COLOR_DB)
            event_graph.tags[DB_NODE_TAG] = 0
            if update_cache:
                self._event_graph[identifier] = event_graph

        return event_graph

    def _get_maximum_event_id(self):
        """
        Gets the maximum event identifier.

        :return: the maximum event identifier
        :rtype: int
        """
        with self.engine.connect() as connection:
            selection = select(func.max(self.EVENT_TABLE.columns.id).label("max"))
            for row in connection.execute(selection):
                return row.max

    def _get_maximum_location_id(self):
        """
        Gets the maximum location identifier.

        :return: the maximum location identifier
        :rtype: int
        """
        with self.engine.connect() as connection:
            selection = select(func.max(self.LOCATION_TABLE.columns.id).label("max"))
            for row in connection.execute(selection):
                return row.max

    def _get_location_if_exist(self, location):
        """
        Gets the identifier of the location, if the location exists in the database.

        :param location: the name of the location
        :type location: str
        :return: the identifier of the location, if exists; otherwise, `None`
        :rtype: Optional[int]
        """
        with self.engine.connect() as connection:
            selection = select(self.LOCATION_TABLE.columns.id).where(self.LOCATION_TABLE.columns.name == location)
            for row in connection.execute(selection):
                return row.id

        return None

    @staticmethod
    def _get_has_attendee_data(event_id, attendees):
        """
        Generates the data to add the attendees to an event in the database.

        :param event_id: the id of the event
        :type event_id: int
        :param attendees: the id of the attendees
        :type attendees: List[int]
        :return: the data to be added to the database
        :rtype: List[Dict[str, Any]]
        """
        event_has_attendee_data = []
        # TODO: replace string literals by default values for `show as status` and `response status`
        for attendee in attendees:
            event_has_attendee_data.append({
                "event_id": event_id, "recipient_id": attendee,
                "show_as_status": "Busy", "response_status": "NotResponded"
            })
        return event_has_attendee_data

    def add_event(self, subject, start, end, location, attendees):
        location_id = self._get_location_if_exist(location)
        organizer_id = self._current_recipient_id
        identifier = self._get_maximum_event_id() + 1
        with self.engine.connect() as connection:
            if location_id is None:
                location_id = self._get_maximum_location_id() + 1
                connection.execute(insert(self.LOCATION_TABLE),
                                   {"id": location_id, "name": location, "always_free": False})

            connection.execute(insert(self.EVENT_TABLE), {
                "id": identifier, "subject": subject, "location_id": location_id, "organizer_id": organizer_id,
                "starts_at": start, "ends_at": end
            })

            # for now, we don't need to check if the attendee exists in the database, since the system will only
            # suggest existing attendees

            # for now, the organizer must also be an attendee
            if self._current_recipient_id not in attendees:
                attendees = attendees + [self._current_recipient_id]

            event_has_attendee_data = self._get_has_attendee_data(identifier, attendees)
            connection.execute(insert(self.EVENT_HAS_ATTENDEE_TABLE), event_has_attendee_data)

            connection.commit()

        return self.get_event_entry(identifier)

    def update_event(self, identifier, subject, start, end, location, attendees):
        old_event = self.get_event_entry(identifier)
        if old_event is None:
            # could not find the original event, it will create a new one
            return self.add_event(subject, start, end, location, attendees)

        location_id = self._get_location_if_exist(location)
        organizer_id = self._current_recipient_id
        with self.engine.connect() as connection:
            if location_id is None:
                location_id = self._get_maximum_location_id() + 1
                connection.execute(insert(self.LOCATION_TABLE),
                                   {"id": location_id, "name": location, "always_free": False})

            connection.execute(update(self.EVENT_TABLE).where(self.EVENT_TABLE.columns.id == identifier).values(
                subject=subject, starts_at=start, ends_at=end, location_id=location_id, organizer_id=organizer_id))

            # for now, we will delete all the attendees and add the new ones. This will set the response of the
            # attendees to `NotAnswered`. This may or may not be the intended behaviour.
            connection.execute(delete(self.EVENT_HAS_ATTENDEE_TABLE).where(
                self.EVENT_HAS_ATTENDEE_TABLE.columns.event_id == identifier))

            # for now, the organizer must also be an attendee
            if self._current_recipient_id not in attendees:
                attendees = attendees + [self._current_recipient_id]

            event_has_attendee_data = self._get_has_attendee_data(identifier, attendees)
            connection.execute(insert(self.EVENT_HAS_ATTENDEE_TABLE), event_has_attendee_data)

            connection.commit()

        self._event_graph.pop(identifier, None)  # invalidate cached value
        return self.get_event_entry(identifier)

    def delete_event(self, identifier, subject, start, end, location, attendees):
        ev = self.get_events(identifier, subject=subject, start=start, end=end, location=location, attendees=attendees)
        if len(ev) != 1:
            return None

        with self.engine.connect() as connection:
            connection.execute(delete(self.EVENT_TABLE).where(self.EVENT_TABLE.columns.id == ev[0].identifier))
            connection.commit()

        self._event_graph.pop(identifier, None)  # invalidate cached value
        return ev

    def _select_attendees(self, attendees, threshold, selection):
        """
        Adds a where condition to `selection` in order to select only the events whose number of attendees is equal
        to or greater than `threshold`, considering only the attendees in `attendees`.

        :param attendees: the attendees to consider
        :type attendees: List[int]
        :param threshold: the threshold
        :type threshold: int
        :param selection: the current selection
        :type selection: select
        :return: the updated selection
        :rtype: select
        """
        label = "selected_attendees"
        selected_attendees = func.count(self.EVENT_HAS_ATTENDEE_TABLE.columns.recipient_id).label(label)
        c = select(self.EVENT_HAS_ATTENDEE_TABLE.columns.event_id, selected_attendees).where(
            self.EVENT_HAS_ATTENDEE_TABLE.columns.recipient_id.in_(attendees)
        ).group_by(self.EVENT_HAS_ATTENDEE_TABLE.columns.event_id).alias("c")
        selection = selection.join(c, c.columns.event_id == self.EVENT_TABLE.columns.id)
        # TODO: replace text(.) function below by `selected_attendees >= threshold`
        selection = selection.where(text(f"{label} >= {threshold}"))
        return selection

    def get_events(self, identifier=None, avoid_id=None, subject=None, start=None, end=None, location=None,
                   attendees=None, pre_filter=None, with_current_recipient=True):

        selection = select(self.EVENT_TABLE)
        if location is not None:
            selection = select(self.EVENT_TABLE, self.LOCATION_TABLE)
            selection = selection.join(self.LOCATION_TABLE)

        if identifier is not None:
            selection = selection.where(self.EVENT_TABLE.columns.id == identifier)

        if avoid_id is not None:
            selection = selection.where(self.EVENT_TABLE.columns.id != avoid_id)

        if subject is not None:
            selection = selection.where(self.EVENT_TABLE.columns.subject.like(f"%{subject}%"))

        if location is not None:
            selection = selection.where(self.LOCATION_TABLE.columns.name.like(f"%{location}%"))

        if with_current_recipient:
            # event must contain the current user and AT LEAST one attendee, if given
            selection = selection.join(self.EVENT_HAS_ATTENDEE_TABLE).where(
                self.EVENT_HAS_ATTENDEE_TABLE.columns.recipient_id == self._current_recipient_id)
            if attendees is not None and len(attendees) > 1:
                selection = self._select_attendees(attendees, 1, selection)
        else:
            if attendees is not None and len(attendees) > 1:
                selection = self._select_attendees(attendees, len(attendees), selection)

        if pre_filter is not None:
            selection = selection.where(self.EVENT_TABLE.columns.id.in_(set(map(lambda x: x.identifier, pre_filter))))

        with self.engine.connect() as connection:
            identifiers = []
            for row in connection.execute(selection):
                if match_start(row, start) and match_end(row, end):
                    identifiers.append(row.id)

        return self._get_event_entries(identifiers)

    def get_time_overlap_events(self, start, end, attendees, avoid_id=None, pre_filter=None):
        selection = select(self.EVENT_TABLE)

        selection = select_event_with_overlap(start, end, selection)

        # Not sure what should be done with attendees here
        attendees = to_list(attendees)
        if attendees is not None and len(attendees) > 0:
            selection = self._select_attendees(attendees, len(attendees), selection)

        if avoid_id is not None:
            selection = selection.where(self.EVENT_TABLE.columns.id != avoid_id)

        if pre_filter is not None:
            selection = selection.where(self.EVENT_TABLE.columns.id.in_(set(map(lambda x: x.identifier, pre_filter))))

        with self.engine.connect() as connection:
            identifiers = []
            for row in connection.execute(selection):
                identifiers.append(row.id)

        return self._get_event_entries(identifiers)

    def get_location_overlap_events(self, location, start=None, end=None, avoid_id=None, pre_filter=None):
        selection = select(self.EVENT_TABLE, self.LOCATION_TABLE)
        selection = selection.join(self.LOCATION_TABLE)

        selection = selection.where(
            self.LOCATION_TABLE.columns.name == location, self.LOCATION_TABLE.columns.always_free == False)

        if start is not None and end is not None:
            selection = select_event_with_overlap(start, end, selection)

        if avoid_id is not None:
            selection = selection.where(self.EVENT_TABLE.columns.id != avoid_id)

        if pre_filter is not None:
            selection = selection.where(self.EVENT_TABLE.columns.id.in_(set(map(lambda x: x.identifier, pre_filter))))

        with self.engine.connect() as connection:
            identifiers = []
            for row in connection.execute(selection):
                identifiers.append(row.id)

        return self._get_event_entries(identifiers)

    def is_recipient_free(self, recipient_id, start, end, avoid_id=None):
        selection = select(func.count(self.EVENT_TABLE.columns.id).label("count")).select_from(self.EVENT_TABLE)
        selection = selection.join(self.EVENT_HAS_ATTENDEE_TABLE)

        selection = selection.where(self.EVENT_HAS_ATTENDEE_TABLE.columns.recipient_id == recipient_id)

        selection = select_event_with_overlap(start, end, selection)

        if avoid_id is not None:
            selection = selection.where(self.EVENT_TABLE.columns.id != avoid_id)

        with self.engine.connect() as connection:
            for row in connection.execute(selection):
                return row.count == 0

    def has_location(self, operator):
        """
        Checks if there is at least one location that complies with `operator`.

        :param operator: the operator
        :type operator: Node
        :return: `True`, if there is at least one location; otherwise, `False`
        :rtype: bool
        """
        selection = select(func.count(self.LOCATION_TABLE.columns.id).label("count"))
        selection = operator.generate_sql_where(selection, None)

        with self.engine.connect() as connection:
            for row in connection.execute(selection):
                return row.count != 0

    def is_location_free(self, location, start, end, avoid_id=None):
        selection = select(func.count(self.EVENT_TABLE.columns.id).label("count")).select_from(self.EVENT_TABLE)
        selection = selection.join(self.LOCATION_TABLE)

        selection = selection.where(
            self.LOCATION_TABLE.columns.name == location, self.LOCATION_TABLE.columns.always_free == False)

        selection = select_event_with_overlap(start, end, selection)

        if avoid_id is not None:
            selection = selection.where(self.EVENT_TABLE.columns.id != avoid_id)

        with self.engine.connect() as connection:
            for row in connection.execute(selection):
                return row.count == 0


def populate_stub_database():
    """
    Populates the database based on the data from the ms_domain.py file.
    """
    database = Database.get_instance()

    # reads the events from the ms_domain
    people = db_persons
    events = db_events
    database.clean_database()
    with database.engine.connect() as connection:
        recipient_data = []
        recipient_has_friend_data = []
        for person in people:
            recipient_data.append({
                "id": person.id, "full_name": person.fullName, "first_name": person.firstName,
                "last_name": person.lastName, "phone_number": person.phone_number,
                "email_address": person.email_address, "manager_id": person.manager_id
            })
            if isinstance(person.friends, Sequence):
                for friend in person.friends:
                    recipient_has_friend_data.append({"recipient_id": person.id, "friend_id": friend})
            else:
                recipient_has_friend_data.append({"recipient_id": person.id, "friend_id": person.friends})
        connection.execute(insert(database.RECIPIENT_TABLE), recipient_data)
        connection.execute(insert(database.RECIPIENT_HAS_FRIEND_TABLE), recipient_has_friend_data)

        location_data = []
        event_data = []
        event_has_attendee_data = []
        organizer_id = CURRENT_RECIPIENT_ID  # for now, the organizer is the current user
        for event in events:
            event_data.append({
                "id": event.id, "subject": event.subject, "location_id": event.location, "organizer_id": organizer_id,
                "starts_at": str_to_datetime(event.start), "ends_at": str_to_datetime(event.end)
            })
            if isinstance(event.attendees, Sequence):
                for attendee, accepted, show_as in zip(event.attendees, event.accepted, event.showas):
                    event_has_attendee_data.append({
                        "event_id": event.id, "recipient_id": attendee,
                        "show_as_status": show_as, "response_status": accepted
                    })
            else:
                event_has_attendee_data.append({
                    "event_id": event.id, "recipient_id": event.attendees,
                    "show_as_status": event.showas, "response_status": event.accepted
                })

        for weather_place in weather_places:
            location_data.append({
                'id': len(location_data), 'name': weather_place.name, 'address': weather_place.address,
                'latitude': weather_place.latitude, 'longitude': weather_place.longitude,
                'radius': weather_place.radius, 'always_free': weather_place.always_free,
                'is_virtual': weather_place.is_virtual
            })

        feature_data = []
        location_has_feature_data = []
        possible_features = dict()
        for location_id, features in place_has_features.items():
            for feature in features:
                feature_id = possible_features.get(feature)
                if feature_id is None:
                    feature_id = len(possible_features)
                    feature_data.append({"id": feature_id, "feature": feature})
                    possible_features[feature] = feature_id
                location_has_feature_data.append({"location_id": location_id, "feature_id": feature_id})

        connection.execute(insert(database.LOCATION_TABLE), location_data)
        connection.execute(insert(database.PLACE_FEATURE_TABLE), feature_data)
        connection.execute(insert(database.PLACE_HAS_FEATURE_TABLE), location_has_feature_data)

        connection.execute(insert(database.EVENT_TABLE), event_data)
        connection.execute(insert(database.EVENT_HAS_ATTENDEE_TABLE), event_has_attendee_data)

        earliest = get_system_datetime().replace(hour=0, minute=0, second=0, microsecond=0)
        latest = earliest + timedelta(days=event_suggestion_period)
        interval = timedelta(minutes=minimum_slot_interval)

        values = []
        current = earliest
        while current < latest:
            values.append({Database.POSSIBLE_TIME_TABLE.columns.point_in_time: current})
            current += interval
        connection.execute(insert(Database.POSSIBLE_TIME_TABLE, values))

        # duration values in minutes
        maximum_duration = maximum_duration_days * 24 * 60 + minimum_slot_interval
        # 1 day * 24h per day * 60 minutes per hour + offset to include last value

        durations = list(map(lambda x: {Database.POSSIBLE_DURATION_TABLE.columns.offset: x},
                             range(minimum_duration, maximum_duration, minimum_slot_interval)))
        connection.execute(insert(Database.POSSIBLE_DURATION_TABLE, durations))

        current_year = get_system_date().year
        values = []
        for i in range(-1, 10):
            for (day, month), name in HOLIDAYS.items():
                values.append({"name": name,
                               "date": date(year=current_year + i, month=month, day=day)})
        connection.execute(insert(Database.HOLIDAY_TABLE, values))

        connection.commit()

        database.set_current_recipient_id(CURRENT_RECIPIENT_ID)
        database.set_current_recipient_location_id(CURRENT_RECIPIENT_LOCATION_ID)
