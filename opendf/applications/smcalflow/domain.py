"""
Useful functions to deal with smcalflow nodes.
"""

from typing import Optional, Dict, List

import opendf.defs
import opendf.utils.utils as utils

from opendf.applications.smcalflow.storage import RecipientEntry, EventEntry, LocationEntry, AttendeeEntry, Storage, \
    HolidayEntry
from opendf.applications.smcalflow.stub_data import db_persons, CURRENT_RECIPIENT_ID, db_events, weather_places, \
    place_has_features, CURRENT_RECIPIENT_LOCATION_ID, HOLIDAYS
from opendf.applications.core.nodes.time_nodes import datetime_to_str
from opendf.defs import *
from opendf.graph.nodes.node import Node
from opendf.parser.pexp_parser import escape_string
from opendf.utils.utils import to_list, id_sexp, str_to_datetime

from datetime import time, datetime, date

logger = logging.getLogger(__name__)

TIME_SUITABLE_FOR_SUBJECT = {
    "breakfast": [time(7), time(9)],
    "lunch": [time(12), time(14)],
    "dinner": [time(18), time(20)],
}


def location_to_str_node(location: LocationEntry):
    """
    Create a string representation of a node, based on the `location`.

    :param location: the location
    :type location: LocationEntry
    :return: the string representation of the node
    :rtype: str
    """
    params = []
    if location.identifier:
        params.append(f"id={location.identifier}")
    if location.name:
        params.append(f"name={escape_string(location.name)}")
    if location.address:
        params.append(f"address={escape_string(location.address)}")
    if location.latitude is not None and location.longitude is not None:
        params.append(f"coordinates=GeoCoords(lat={location.latitude}, long={location.longitude})")
    if location.radius is not None:
        params.append(f"radius={location.radius}")
    if location.always_free is not None:
        params.append(f"always_free={location.always_free}")
    if location.is_virtual is not None:
        params.append(f"is_virtual={location.is_virtual}")

    return f"Place({', '.join(params)})"


def recipient_to_str_node(recipient: RecipientEntry):
    s = 'Recipient(name=PersonName(%s),firstName=%s,lastName=%s,id=%d, phoneNum=%s, email=%s)' % \
        (recipient.full_name, recipient.first_name, recipient.last_name, recipient.identifier,
         recipient.phone_number, recipient.email_address)
    return s


def attendee_to_str_node(attendee, recipient):
    """
    Create an attendee node representation of the attendee.

    :param attendee: the attendee
    :type attendee: AttendeeEntry
    :param recipient: the string representation of the recipient, this parameter is used in order to allow the
    re-use of nodes by passing the id of the node as the recipient
    :type recipient: str
    :return: the node representation of the attendee
    :rtype: str
    """
    return f"Attendee(recipient={recipient}, response={attendee.response_status}, show={attendee.show_as_status})"


def attendees_to_str_node(att, nodes=None):
    """
    Converts the attendees to string.

    :param att: the id of the attendee
    :type att: List[AttendeeEntry]
    :param nodes: a list of recipient nodes for each attendee, the node `i` from `nodes` must be the recipient from
    attendee `i` from `att`
    :type nodes: List[Node]
    :return: the string representation of the objects
    :rtype: str
    """
    attendee_strs = []
    if nodes:
        nodes = to_list(nodes)
        for attendee, node in zip(att, nodes):
            attendee_strs.append(attendee_to_str_node(attendee, id_sexp(node)))
    else:
        for attendee in att:
            attendee_strs.append(attendee_to_str_node(attendee, recipient_to_str_node(attendee.recipient)))
    if len(attendee_strs) == 1:
        return attendee_strs[0]
    elif attendee_strs:
        return f"SET({', '.join(attendee_strs)})"

    return None


def datetime_to_str_node(s: datetime):
    return 'DateTime(date=Date(year=%d,month=%d,day=%d), time=Time(hour=%d,minute=%d))' % (
        s.year, s.month, s.day, s.hour, s.minute)  # avoid spaces!


def duration_to_str_node(st, en):
    return Ptimedelta_to_period_sexp(en - st)


def event_to_time_slot_str_node(event_entry: EventEntry):
    params = []
    if event_entry.starts_at is not None:
        params.append(f"start={datetime_to_str_node(event_entry.starts_at)}")
    if event_entry.ends_at is not None:
        params.append(f"end={datetime_to_str_node(event_entry.ends_at)}")
    if len(params) > 1:
        params.append(f"duration={duration_to_str_node(event_entry.starts_at, event_entry.ends_at)}")

    if params:
        return f"TimeSlot({', '.join(params)})"

    return None


def event_to_str_node(event_entry: EventEntry, att_nodes=None):
    params = []
    if event_entry.subject is not None:
        params.append(f"subject={event_entry.subject}")
    time_slot = event_to_time_slot_str_node(event_entry)
    if time_slot is not None:
        params.append(f"slot={time_slot}")
    if event_entry.location.name is not None:
        params.append(f"location=LocationKeyphrase({event_entry.location.name})")
    attendees = attendees_to_str_node(event_entry.attendees, att_nodes)
    if attendees is not None:
        params.append(f"attendees={attendees}")
    if event_entry.identifier is not None:
        params.append(f"id={event_entry.identifier}")
    sexp = f"Event({', '.join(params)})"
    # sexp = fix_sp(sexp)
    logger.debug('>:> %s', sexp)
    return sexp


def match_subject(ev: EventEntry, filt):
    return True if filt is None or filt in ev.subject else False


def match_start(ev: EventEntry, filt):
    if filt is None:
        return True
    start = datetime_to_str(ev.starts_at)
    e = [int(i) if i.isnumeric() else -1 for i in start.split('/')]
    r = [int(i) if i.isnumeric() else -1 for i in filt.split('/')]
    mismatch = [1 for i, t in enumerate(e) if t >= 0 and r[i] >= 0 and t != r[i]]
    return False if mismatch else True


def match_end(ev, filt):
    if filt is None:
        return True
    end = datetime_to_str(ev.ends_at)
    e = [int(i) if i.isnumeric() else -1 for i in end.split('/')]
    r = [int(i) if i.isnumeric() else -1 for i in filt.split('/')]
    mismatch = [1 for i, t in enumerate(e) if t >= 0 and r[i] >= 0 and t != r[i]]
    return False if mismatch else True


def overlap_start_end(ev: EventEntry, start, end):
    b1, e1 = ev.starts_at, ev.ends_at
    b2, e2 = str_to_datetime(start), str_to_datetime(end)
    return b1 <= b2 < e1 or b1 < e2 <= e1 or b2 <= b1 < e2 or b2 < e1 <= e2


def overlap_t_dur(ev: EventEntry, t, dur):
    b1, e1 = ev.starts_at, ev.ends_at
    b2, e2 = t, t + dur
    return b1 <= b2 < e1 or b1 < e2 <= e1 or b2 <= b1 < e2 or b2 < e1 <= e2


def match_location(ev: EventEntry, filt: str):
    return True if filt is None or filt in ev.location.name else False


def match_attendees(ev: EventEntry, filt: List[int], must_include=None, match_any=False):
    e = ev.get_attendee_ids_set()
    e.add(ev.organizer.identifier)  # include the organizer in the set of attendees
    if must_include:
        m = utils.to_list(must_include)
        for a in m:
            if a not in e:
                return False
    if not filt:
        return True
    filt = utils.to_list(filt)
    if match_any:
        for a in filt:
            if a in e:  # this is already after name normalization - so we get the full names. (but no id yet...)
                return True
        return False
    else:
        for a in filt:
            if a not in e:  # this is already after name normalization - so we get the full names. (but no id yet...)
                return False
        return True


# some event subjects require specific times
def time_ok_for_subj(dt, subj):
    time_range = TIME_SUITABLE_FOR_SUBJECT.get(subj.lower())
    if time_range is None:
        return True

    return time_range[0] <= dt.time() <= time_range[-1]


class GraphDB(Storage):
    """
    A graph representation of the stored data.
    """

    __instance = None

    @staticmethod
    def get_instance():
        """
        Static access method.

        :return: the GraphDB
        :rtype: GraphDB
        """
        if GraphDB.__instance is None:
            GraphDB.__instance = GraphDB()
        return GraphDB.__instance

    def __init__(self):
        """
        Virtually private constructor.
        """
        if GraphDB.__instance is not None:
            raise SingletonClassException()

        GraphDB.__instance = self
        self.db_recipients: Dict[int, RecipientEntry] = {}  # dict of recipient entries
        self.gr_recipients: Dict[int, Node] = {}  # dict of graph recipients
        self.db_attendees: Dict[(int, int), AttendeeEntry] = {}  # dict of attendees per event
        self.gr_attendees: Dict[(int, int), Node] = {}  # dict of graph attendees
        self.friends_by_recipient: Dict[int, List[int]] = {}  # friends by recipient id

        self.db_events: Dict[int, EventEntry] = {}  # dict of event entries
        self.gr_events: Dict[int, Node] = {}  # event nodes

        self.locations: Dict[str, LocationEntry] = {}  # location entries by name
        self.location_by_id: Dict[int, LocationEntry] = {}  # location entries by id
        self.location_features: Dict[int, List[str]] = {}  # location features by id

        self._current_recipient_id: Optional[int] = None
        self._current_recipient_location_id: Optional[int] = None

    def get_current_recipient_id(self):
        return self._current_recipient_id

    def set_current_recipient_id(self, identifier):
        self._current_recipient_id = identifier

    def get_current_recipient_entry(self):
        return self.get_recipient_entry(self._current_recipient_id)

    def get_current_recipient_graph(self, d_context):
        return self.get_recipient_graph(self._current_recipient_id, d_context)

    def get_current_attendee_graph(self, d_context):
        recipient_entry = self.get_recipient_entry(self._current_recipient_id)
        recipient_graph = self.get_recipient_graph(self._current_recipient_id, d_context)
        attendee = AttendeeEntry(None, recipient_entry, "Busy", "NotResponded")
        string_entry = attendees_to_str_node([attendee], [recipient_graph])
        attendee_graph, _ = Node.call_construct_eval(string_entry, d_context, constr_tag=NODE_COLOR_DB)
        attendee_graph.tags[DB_NODE_TAG] = 0

        return attendee_graph

    def get_current_recipient_location(self):
        if self._current_recipient_location_id:
            return self.location_by_id.get(self._current_recipient_location_id)
        return None

    def set_current_recipient_location_id(self, value):
        self._current_recipient_location_id = value

    def get_recipient_entry(self, identifier):
        return self.db_recipients.get(identifier)

    def get_recipient_graph(self, identifier, d_context, update_cache=True):
        return self.gr_recipients.get(identifier)

    def get_attendee_graph(self, event_id, recipient_id, d_context):
        return self.gr_attendees.get((event_id, recipient_id))

    def find_recipients_that_match(self, operator, d_context):
        if operator is None:
            return list(self.gr_recipients.values())
        return list(filter(operator.match, self.gr_recipients.values()))

    def find_attendees_that_match(self, operator, d_context):
        if operator is None:
            return list(self.gr_attendees.values())
        return list(filter(operator.match, self.gr_attendees.values()))

    def find_events_that_match(self, operator, d_context):
        if operator is None:
            return list(self.gr_events.values())
        return list(filter(operator.match, self.gr_events.values()))

    def find_locations_that_match(self, operator):
        location_name = operator.dat.lower()
        result = self.locations.get(location_name)
        if result is not None:
            return [result]

        results = []
        for key, value in self.locations.items():
            if location_name in key:
                results.append(value)

        return results

    def find_feature_for_place(self, place_id, feature=None):
        results = self.location_features.get(place_id, [])
        if feature:
            results = list(filter(lambda x: feature in x, results))

        return results

    def find_holidays_that_match(self, d_context, name=None, holiday_date=None, sort=None, limit=None):
        holidays = []
        if holiday_date is not None:
            year = holiday_date.get_dat("year")
        else:
            year = opendf.defs.get_system_date().year
        if isinstance(name, Node):
            name = name.get_dat(opendf.defs.posname(1))
        name = name.lower()
        for (day, month), h_name in HOLIDAYS.items():
            if name is not None and name not in h_name.lower():
                continue
            if holiday_date is not None:
                date_day = holiday_date.get_dat("day")
                if date_day and day != date_day:
                    continue
                date_month = holiday_date.get_dat("month")
                if date_month and month != date_month:
                    continue

            holidays.append(HolidayEntry(h_name, date(year, month, day)))

        if sort:
            holidays.sort(key=lambda x: x.date, reverse=sort.lower() == "desc")

        if limit is not None:
            holidays = holidays[:limit]

        return holidays

    def get_event_entry(self, identifier):
        return self.db_events.get(identifier)

    def get_event_graph(self, identifier, d_context, update_cache=True):
        return self.gr_events.get(identifier)

    def _create_attendees_from_ids(self, attendees, event_id):
        """
        Creates a list of attendees from a list of ids.

        :param attendees: the list of ids
        :type attendees: List[int]
        :param event_id: the event id
        :type event_id: int
        :return: the list of attendees
        :rtype: List[AttendeeEntry]
        """
        result = []
        for attendee in attendees:
            # TODO: replace string literals by default values for `show as status` and `response status`
            result.append(AttendeeEntry(event_id, self.get_recipient_entry(attendee), "Busy", "Accepted"))

        return result

    def _get_location_by_name(self, location):
        """
        Gets the location entry by name. If there is no location entry for the name, it creates one.

        :param location: the name of the location
        :type location: str
        :return: the location entry
        :rtype: LocationEntry
        """
        location_entry = self.locations.get(location)
        if location_entry is None:
            location_entry = LocationEntry(len(self.locations) + 1, location, location == "online")
            self.locations[location] = location_entry

        return location_entry

    def add_event(self, subject, start, end, location, attendees):
        event_id = len(self.db_events) + 1
        attendees_entries = self._create_attendees_from_ids(attendees, event_id)

        location_entry = self._get_location_by_name(location)
        event = EventEntry(event_id, subject, start, end, location_entry,
                           self.get_current_recipient_entry(), attendees_entries)
        self.db_events[event.identifier] = event
        logger.debug('~~~new db_event:')
        logger.debug(event)

        # d = self._create_event_node(event)
        # self.gr_events[event.identifier] = d

        return event

    def update_event(self, identifier, subject, start, end, location, attendees):
        old_event = self.get_event_entry(identifier)
        if old_event is None:
            # could not find the original event, it will create a new one
            return self.add_event(subject, start, end, location, attendees)

        location_entry = self._get_location_by_name(location)
        new_event = EventEntry(old_event.identifier, subject, start, end, location_entry,
                               old_event.organizer, old_event.attendees)

        # d = self._create_event_node(new_event)
        # self.gr_events[new_event.identifier] = d
        self.gr_events.pop(new_event.identifier, None)
        self.db_events[new_event.identifier] = new_event

        return new_event

    def delete_event(self, identifier, subject, start, end, location, attendees):
        ev = self.get_events(identifier, subject=subject, start=start, end=end, location=location, attendees=attendees)
        if len(ev) != 1:
            return None

        old_event = self.db_events.pop(identifier, None)
        old_event_graph = self.gr_events.pop(identifier, None)
        if old_event is None or old_event_graph is None:
            # Error deleting event, put event back
            if old_event is not None:
                self.db_events[identifier] = old_event
            if old_event_graph is not None:
                self.gr_events[identifier] = old_event_graph
            return None

        return old_event

    # TODO: this function does just initial filtering!
    #  the complete filtering (including aggregated conditions) should be done
    #  by calling a match() on the returned candidates
    def get_events(self, identifier=None, avoid_id=None, subject=None, start=None, end=None, location=None,
                   attendees=None, pre_filter=None, with_current_recipient=True):
        evs = pre_filter if pre_filter is not None else list(self.db_events.values())
        # if pre filter given - apply filtering to the given pre-filtered set.
        if identifier is not None and evs:
            evs = [e for e in evs if e.identifier == identifier]
            # return evs
        if avoid_id is not None and evs:
            evs = [e for e in evs if e.identifier != avoid_id]
        if subject is not None and evs:
            evs = [e for e in evs if match_subject(e, subject)]
        if start is not None and evs:
            evs = [e for e in evs if match_start(e, start)]
        if end is not None and evs:
            evs = [e for e in evs if match_end(e, end)]
        if location is not None and evs:
            evs = [e for e in evs if match_location(e, location)]
        if with_current_recipient:
            evs = [e for e in evs if
                   match_attendees(e, attendees, must_include=self._current_recipient_id, match_any=True)]
        else:
            if attendees is not None and evs:
                evs = [e for e in evs if match_attendees(e, attendees)]
        return evs

    def get_time_overlap_events(self, start, end, attendees, avoid_id=None, pre_filter=None):
        evs = pre_filter if pre_filter is not None else list(self.db_events.values())
        # if pre filter given - apply filtering to the given pre-filtered set.
        evs = [e for e in evs if overlap_start_end(e, start, end)]
        att = to_list(attendees)
        if att is not None and evs:
            evs = [e for e in evs if match_attendees(e, att)]
        if avoid_id is not None and evs:
            evs = [e for e in evs if e.identifier != avoid_id]
        return evs

    def get_location_overlap_events(self, location, start=None, end=None, avoid_id=None, pre_filter=None):
        evs = pre_filter if pre_filter is not None else list(self.db_events.values())
        # if pre filter given - apply filtering to the given pre-filtered set.
        evs = [e for e in evs if e.location.name == location and not e.location.always_free]
        if start is not None and end is not None:
            evs = [e for e in evs if overlap_start_end(e, start, end)]
        if avoid_id is not None and evs:
            evs = [e for e in evs if e.identifier != avoid_id]
        return evs

    def is_recipient_free(self, recipient_id, start, end, avoid_id=None):
        for e in self.db_events.values():
            if avoid_id is None or e.identifier != avoid_id:
                if (recipient_id == e.organizer.identifier or recipient_id in e.get_attendee_ids_set()) \
                        and overlap_t_dur(e, start, end - start):
                    return False
        return True

    def is_location_free(self, location, start, end, avoid_id=None):
        for e in self.db_events.values():
            if avoid_id is None or e.identifier != avoid_id:
                if not e.location.always_free and location == e.location.name and overlap_t_dur(e, start, end - start):
                    return False
        return True

    def get_manager(self, recipient_id):
        recipient_data = self.get_recipient_entry(recipient_id)
        if recipient_data is not None:
            return self.get_recipient_entry(recipient_data.manager_id)
        return None

    def get_friends(self, recipient_id):
        return self.friends_by_recipient.get(recipient_id, [])


def fill_graph_db(d_context):
    graph_db = GraphDB.get_instance()

    def fill_recipient_graph_db():
        gr_recipient: Dict[int, Node] = {}
        # gr_attendee: Dict[int, Node] = {}
        db_recipient: Dict[int, RecipientEntry] = {}
        friends_by_recipient: Dict[int, List[int]] = {}
        for p in db_persons:
            # create recipient entry
            recipient_entry = RecipientEntry(p.id, p.fullName, p.firstName, p.lastName, p.phone_number,
                                             p.email_address, p.manager_id)

            # create recipient graph
            s = recipient_to_str_node(recipient_entry)
            recipient_graph, _ = Node.call_construct_eval(s, d_context, constr_tag=NODE_COLOR_DB)
            recipient_graph.tags[DB_NODE_TAG] = 0
            db_recipient[recipient_entry.identifier] = recipient_entry
            gr_recipient[recipient_entry.identifier] = recipient_graph
            for friend in p.friends:
                friends_by_recipient.setdefault(p.id, []).append(friend)

            # create attendee graph
            # noinspection PyTypeChecker
            # TODO: get `show as status` and `response status` from stub data
            # attendee = AttendeeEntry(None, recipient_entry, "Busy", "NotResponded")
            # string_entry = attendees_to_str_node([attendee], [recipient_graph])
            # attendee_graph, _ = Node.call_construct_eval(string_entry, constr_tag=NODE_COLOR_DB)
            # attendee_graph.tags[DB_NODE_TAG] = 0
            # gr_attendee[recipient_entry.identifier] = attendee_graph

        graph_db.gr_recipients = gr_recipient
        # graph_db.gr_attendees = gr_attendee
        graph_db.db_recipients = db_recipient
        graph_db.friends_by_recipient = friends_by_recipient
        graph_db.set_current_recipient_id(CURRENT_RECIPIENT_ID)
        graph_db.set_current_recipient_location_id(CURRENT_RECIPIENT_LOCATION_ID)

    def fill_event_graph_db():
        db_event = {}
        gr_event = {}
        gr_attendee: Dict[(int, int), Node] = {}
        db_attendee: Dict[(int, int), AttendeeEntry] = {}
        locations: Dict[str, LocationEntry] = {"online": LocationEntry(0, "online", True)}
        organizer = graph_db.get_current_recipient_entry()
        location_by_id = dict()

        for weather_place in weather_places:
            location_entry = LocationEntry(weather_place.id, name=weather_place.name, address=weather_place.address,
                                           latitude=weather_place.latitude, longitude=weather_place.longitude,
                                           radius=weather_place.radius, always_free=weather_place.always_free,
                                           is_virtual=weather_place.is_virtual)
            locations[weather_place.name] = location_entry
            location_by_id[weather_place.id] = location_entry

        for e in db_events:
            location = locations[location_by_id[e.location].name]
            attendees = []
            for att, accepted, show_as in zip(to_list(e.attendees), to_list(e.accepted), to_list(e.showas)):
                attendees.append(AttendeeEntry(e.id, graph_db.get_recipient_entry(att), show_as, accepted))

            pnodes = []
            for a in attendees:
                aid = a.recipient.identifier
                rcp = graph_db.get_recipient_graph(aid, d_context)
                d, _ = Node.call_construct_eval('Attendee(recipient=%s, response=%s, show=%s, eventid=%d)' %
                                                (id_sexp(rcp), a.response_status, a.show_as_status, e.id), d_context,
                                                constr_tag=NODE_COLOR_DB)
                d.tags[DB_NODE_TAG] = 0
                db_attendee[(e.id, aid)] = a
                gr_attendee[(e.id, aid)] = d
                pnodes.append(rcp)

            event_entry = EventEntry(e.id, e.subject, str_to_datetime(e.start), str_to_datetime(e.end), location,
                                     organizer, attendees)

            # pnodes = [graph_db.get_recipient_graph(attendee.recipient.identifier) for attendee in attendees]
            s = event_to_str_node(event_entry, pnodes)
            d, _ = Node.call_construct_eval(s, d_context, constr_tag=NODE_COLOR_DB)
            d.tags[DB_NODE_TAG] = 0
            db_event[event_entry.identifier] = event_entry
            gr_event[event_entry.identifier] = d

        graph_db.gr_events = gr_event
        graph_db.db_events = db_event
        graph_db.db_attendees = db_attendee
        graph_db.gr_attendees = gr_attendee
        graph_db.locations = locations
        graph_db.location_by_id = location_by_id
        graph_db.location_features = place_has_features

    # prt = d_context.show_print
    d_context.set_print(False)
    d_context.set_next_node_id(10000)  # put DB nodes id's to be high
    fill_recipient_graph_db()
    fill_event_graph_db()
    # d_context.set_print(prt)
    d_context.set_next_node_id(0)  # reset node id's to start from 0

    return graph_db


def period_str(yr=None, mn=None, wk=None, dy=None, hr=None, mt=None):
    p = []
    if yr is not None and yr >= 0:
        p.append('year=%d' % yr)
    if mn is not None and mn >= 0:
        p.append('month=%d' % mn)
    if wk is not None and wk >= 0:
        p.append('week=%d' % wk)
    if dy is not None and dy >= 0:
        p.append('day=%d' % dy)
    if hr is not None and hr >= 0:
        p.append('hour=%d' % hr)
    if mt is not None and mt >= 0:
        p.append('minute=%d' % mt)
    return 'Period(' + ','.join(p) + ')'


def Ptimedelta_to_period_values(p):
    d = p.days
    s = p.seconds
    yr, mn, wk, dy, hr, mt = None, None, None, None, None, None
    if d > 365:
        yr = d // 365
        d -= yr * 365
    if d > 0:
        dy = d
    if s > 3600:
        hr = s // 3600
        s -= hr * 3600
    if s > 60:
        mt = s // 60
    return yr, mn, wk, dy, hr, mt


def Ptimedelta_to_period_sexp(p):
    return period_str(*Ptimedelta_to_period_values(p))
