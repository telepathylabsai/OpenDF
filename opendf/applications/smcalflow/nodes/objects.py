"""
Application specific object nodes.
"""

import re

from opendf.applications.smcalflow.nodes.time_slot import *
from opendf.applications.smcalflow.domain import *

from opendf.applications.smcalflow.weather import wtable_to_dict, wtab_row_summary
from opendf.applications.smcalflow.exceptions.df_exception import ClashEventSuggestionsException, \
    RecipientNotFoundException
from opendf.graph.nodes.framework_operators import LIKE
from opendf.applications.smcalflow.nodes.event_factory import *
from opendf.defs import posname

storage = StorageFactory.get_instance()
environment_definitions = EnvironmentDefinition.get_instance()


class ShowAsStatus(Node):
    POSSIBLE_VALUES = {'OutOfOffice', 'WorkingElsewhere', 'Unknown', 'Busy', 'Tentative', 'Free'}

    def __init__(self):
        super().__init__(ShowAsStatus)
        self.signature.add_sig(posname(1), Str, True)

    def valid_input(self):
        dt = self.dat
        if dt is not None:
            if dt not in self.POSSIBLE_VALUES:
                raise InvalidOptionException(posname(1), dt, self.POSSIBLE_VALUES, self, hints='ShowAsStatus')
        else:
            raise MissingValueException(posname(1), self)

    def generate_sql_where(self, selection, parent_id, **kwargs):
        return self.input_view(posname(1)).generate_sql_where(
            selection, Database.EVENT_HAS_ATTENDEE_TABLE.columns.show_as_status, **kwargs)

    def describe(self, params=None):
        return self.get_dat(posname(1))


class WeatherQuantifier(Node):
    POSSIBLE_VALUES = {'average', 'summarize', 'sum', 'min', 'max'}

    def __init__(self):
        super().__init__(WeatherQuantifier)
        self.signature.add_sig('pos1', Str, True)

    def valid_input(self):
        dt = self.dat.lower()
        if dt is not None:
            if dt not in self.POSSIBLE_VALUES:
                raise InvalidOptionException(posname(1), dt, self.POSSIBLE_VALUES, self, hints='WeatherQuantifier')
        else:
            raise MissingValueException(posname(1), self)


class WeatherProp(Node):
    POSSIBLE_VALUES = {
        "apparentTemperature", "cloudCover", "dewPoint", "humidity", "precipProbability", "pressure",
        "rainPrecipIntensity", "rainPrecipProbability", "snowPrecipAccumulation", "snowPrecipIntensity",
        "snowPrecipProbability", "sunriseTime", "sunsetTime", "temperature", "uvIndex", "visibility", "windBearing",
        "windSpeed"
    }

    def __init__(self):
        super().__init__(WeatherProp)
        self.signature.add_sig('pos1', Str, True)

    def valid_input(self):
        dt = self.dat
        if dt is not None:
            if dt not in self.POSSIBLE_VALUES:
                raise InvalidOptionException(posname(1), dt, self.POSSIBLE_VALUES, self, hints='WeatherQuantifier')
        else:
            raise MissingValueException(posname(1), self)


class ResponseStatusType(Node):
    POSSIBLE_VALUES = {'Accepted', 'Declined', 'TentativelyAccepted', 'None', 'NotResponded'}

    def __init__(self):
        super().__init__(ResponseStatusType)
        self.signature.add_sig('pos1', Str, True)

    def valid_input(self):
        dt = self.dat
        if dt is not None:
            if dt not in self.POSSIBLE_VALUES:
                raise InvalidOptionException(posname(1), dt, self.POSSIBLE_VALUES, self, hints='ResponseStatusType')
        else:
            raise MissingValueException(posname(1), self)

    def generate_sql_where(self, selection, parent_id, **kwargs):
        return self.input_view(posname(1)).generate_sql_where(
            selection, Database.EVENT_HAS_ATTENDEE_TABLE.columns.response_status, **kwargs)

    def describe(self, params=None):
        return self.get_dat(posname(1))


# #################################################################################################
# #############################################  Place  ###########################################

class LocationKeyphrase(Node):
    """
    Natural language string describing a place (not necessarily normalized or unique).
    """

    # TODO: should have its own func_LIKE for fuzzy name match
    def __init__(self):
        super().__init__(type(self))
        self.signature.add_sig(posname(1), Str, True)

    # used by LIKE -
    #    for now: if the object location string (rf) contains the LIKE query string (sl), they are considered similar
    #   more fully - may want to normalize rf,sl to be valid location names/abbreviations/...?
    def strings_are_similar(self, rf, sl):
        return sl.lower() in rf.lower()

    def describe(self, params=None):
        params = params if params else []
        p = self.res.dat
        if p is None and posname(1) in self.inputs:
            p = self.get_dat(posname(1))
        if p is None:
            return None
        if 'add_prep' in params:  # some logic about prepositions
            if p.lower() != 'online':
                p = 'in ' + p
        return p

    def generate_sql_select(self):
        return select(Database.LOCATION_TABLE)

    def generate_sql_where(self, selection, parent_id, **kwargs):
        name_field = kwargs.get("name_field", Database.LOCATION_TABLE.columns.name)
        if 'qualifier' not in kwargs:
            kwargs['qualifier'] = LIKE()
        return self.input_view(posname(1)).generate_sql_where(selection, name_field, **kwargs)


class Str_to_Location(Node):
    """
    Converts Str to LocationKeyphrase.
    """

    # TODO: should have its own func_LIKE for fuzzy name match
    def __init__(self):
        super().__init__(LocationKeyphrase)
        self.signature.add_sig(posname(1), [Str, LocationKeyphrase], True)

    def exec(self, all_nodes=None, goals=None):
        inp = self.input_view(posname(1))
        if inp.typename() == 'LocationKeyphrase':
            self.set_result(inp)
        else:
            r, e = self.call_construct_eval('LocationKeyphrase(%s)' % id_sexp(inp), self.context)
            self.set_result(r)


class PlaceUniqueID(Node):
    """
    Unique ID for a place - a string.
    """

    # corresponding to a unique entity, but not necessarily have a unique geo location (or even not have a geo location)
    # e.g. two logical entities which share place, or a specific online meeting room
    def __init__(self):
        super().__init__(type(self))
        self.signature.add_sig(posname(1), Str)
        self.signature.add_sig('keyphrase', [Str, LocationKeyphrase])  # optional - to be able to link back to keyphrase


class Place(Node):
    """
    Node representation of a place.
    """

    def __init__(self):
        super(Place, self).__init__(type(self))
        self.signature.add_sig('id', Int)
        self.signature.add_sig('name', Str)
        self.signature.add_sig('address', Str)
        self.signature.add_sig('coordinates', GeoCoords)
        self.signature.add_sig('radius', Float)
        self.signature.add_sig('always_free', Bool)
        self.signature.add_sig('is_virtual', Bool)

    def describe(self, params=None):
        message = ""
        name = self.get_dat("name")
        if name:
            message += name
        address = self.get_dat("address")
        if address:
            message += ", "
            message += address

        if not message:
            coordinates = self.input_view("coordinates")
            if coordinates:
                latitude = coordinates.get_dat("lat")
                longitude = coordinates.get_dat("long")
                if latitude and longitude:
                    message = f"{latitude}, {longitude}"

        if not message:
            # TODO: maybe it should raise an exception if there is no information about place, but raise before get
            #  to this point
            message = "Sorry, I don't no where you are."

        return message


class GeoCoords(Node):
    """
    Geographical coordinates.
    """

    def __init__(self):
        super().__init__(type(self))
        self.signature.add_sig('lat', Float)
        self.signature.add_sig('long', Float)

    def valid_input(self):
        if not self.get_dat('lat'):
            raise MissingValueException('latitude', self)
        if not self.get_dat('long'):
            raise MissingValueException('longitude', self)

    def describe(self, params=None):
        return '%s;%s' % (self.get_dat('lat'), self.get_dat('long'))


# TODO: do we also need a Location() type?

# #################################################################################################
# ############################################ weather ############################################


class WeatherTable(Node):
    """
    Holds weather forecast table (in string format)- the result of calling WeatherQueryApi.
    """

    # this could be for one or multiple time point (maybe also multiple locations?)
    # for now, assume the format is:
    #   place+date|time:temp:comment,time:temp:comment,.../place+date|time:temp:comment,time:temp:comment
    # "Zurich+2021-08-30|9:12:-,10:14:cloudy,11:15:rain/Bern+2021-08-30|9:10:snow,10:11:-,11:15:rain"
    def __init__(self):
        super().__init__(type(self))
        self.signature.add_sig('table', Str)

    def describe(self, params=None):
        d = self.get_dat('table')
        if d:
            dc = wtable_to_dict(d)
            s = []
            for l in dc:
                for dt in dc[l]:
                    s.append(wtab_row_summary(dc, l, dt))
            d = ''
            if len(s) > 1:
                p = set([i.split()[0] for i in s])
                if len(p) == 1:
                    d = list(p)[0] + ' weather summary: NL '
                    d += re.sub('/', '', ' NL '.join([' '.join(t.split()[1:]) for t in s]))
            if not d:
                d = ' NL '.join(s)
            if params and 'compact' in params:
                d = f"Weather for  NL {d.split()[0]}"
        return d if d else ''


# #################################################################################################
# ############################################ person  ############################################

class PersonName(Node):
    def __init__(self):
        super().__init__(type(self))
        self.signature.add_sig(posname(1), Str)

    # for PersonName, this is not symmetric - ref can have additional names, but must have the name in self.inputs
    # additionally, for person name, giving just first or last name should also match
    # self is (a leaf of) a constraint (possibly a partial name), ref is a "real" name (e.g. coming from the DB)
    # does not handle nicknames, honorifics, etc.
    def func_LIKE(self, ref):
        sl, rf = self.res.inputs[posname(1)].res.dat, ref.res.dat
        if sl is None and rf is None:
            return True
        if sl is None or rf is None:
            return False
        # '_' should not be there, but '-' is possible
        names = re.sub('[-_]', ' ', sl).lower().split()  # all names must be there
        rr = re.sub('[-_]', ' ', rf.lower()).split()
        for n in names:
            match = [1 for r in rr if n in r]
            if not match:
                return False
        return True

    def generate_sql_where(self, selection, parent_id, **kwargs):
        return self.input_view(posname(1)).generate_sql_where(selection, parent_id, **kwargs)


class Recipient(Node):
    """
    Recipient is ONE person, with first and last names and an id.
    """

    # For now - we use this class for both: 1. person spec, 2. validated person instance
    # by convention, this is filled only by system, so if it exists it means this
    #   was already processed by the system, and all entries are filled correctly.
    # By convention, one recipient SHOULD mean one person (even if we could subvert this with operators/partial spec)
    #    so we can always add singleton on top of it

    # In the dataset, we have:
    #   1. RecipientWithNameLike :constraint (Constraint[Recipient]) :name #(PersonName "Jerri Skinner")
    #   2. FindManager:recipient (toRecipient (CurrentUser ) )
    # from 1 - creating a constraint - the lookup (name->uniq) may be deferred to the wrapper logic
    #          - in that case, Recipient should have a PersonName as input.
    # otherwise, it does not need it - PersonName is an input to RecipientWithNameLike, and it does the lookup
    # OR - we could think of this as a hybrid type/function - if only name is given, then create result
    #    - new Recipient with the unique fields.
    # OR - just add the missing fields in validate/exec (violates 'common ground'?)

    def __init__(self):
        super().__init__(type(self))
        self.signature.add_sig('name', PersonName)  # TODO: decide if needed - see comment above
        self.signature.add_sig('firstName', Str)  # maybe should also be PersonName?
        self.signature.add_sig('lastName', Str)  # maybe should also be PersonName?
        self.signature.add_sig('id', Int)
        self.signature.add_sig('phoneNum', Str)
        self.signature.add_sig('email', Str)
        # separate input for simplified sexp. we could rename it as is convenient
        self.signature.add_sig(posname(1), Str)  # not used anymore
        self.obj_name_singular = 'person'  # override default ('Recipient')
        self.obj_name_plural = 'people'

    # has this recipient already been verified by system? (having person id implies it has)
    def is_complete(self):
        return self.get_dat('id') is not None

    def equivalent_obj(self, other):
        other = to_list(other)
        eq = []
        for o in other:
            if self.id == o.id or (self.is_complete() and o.is_complete() and self.get_dat('id') == o.get_dat('id')):
                eq.append(o)
        return eq

    def add_like(self):
        if not self.is_complete():
            nm, fn, ln = self.input_view('name'), self.input_view('firstName'), self.input_view('lastName')
            if nm and nm.typename() in ['Str', 'CasedStr', 'PersonName']:
                self.wrap_input('name', 'LIKE(')
            if fn and fn.typename() in ['Str', 'CasedStr', 'PersonName']:
                self.wrap_input('firstName', 'LIKE(')
            if ln and ln.typename() in ['Str', 'CasedStr', 'PersonName']:
                self.wrap_input('lastName', 'LIKE(')

    def valid_constraint(self):
        self.add_like()

    def valid_input(self):
        pass
        # self.add_like(d_context)  # probably happens just for constraints?

    def trans_simple(self, top):
        if not self.is_complete() and self.outputs:
            if posname(1) in self.inputs:
                self.wrap_input(posname(1), 'LIKE(PersonName(', new_nm='name',
                                do_eval=False)  # important to cast to PersonName!
                self.constraint_level = 1  # make it into a query!
                nm, par = self.outputs[0]
                # todo: if used as a negative object (check up the graph), maybe do not do refer
                par.wrap_input(nm, 'singleton(refer(', suf=',multi=True))', do_eval=False)
        return self, None

    def describe(self, params=None):
        params = params if params else []
        if 'SQL_Event' in params:
            return str(self.get_dat('id'))
        i = self.get_dat('id')
        if i and i == storage.get_current_recipient_id():
            return 'You'
        if 'firstName' in self.inputs and 'lastName' in self.inputs:
            return '%s %s' % (self.simple_desc('firstName'), self.simple_desc('lastName'))
        if 'name' in self.inputs:
            return '%s' % self.simple_desc('name')
        if 'id' in self.inputs:
            return 'id=%s' % self.simple_desc('id')
        return ''

    def fallback_search(self, parent, all_nodes=None, goals=None, do_eval=True, params=None):
        # prs = [i for i in graph_db.gr_persons if self.match(i)]
        prs = storage.find_recipients_that_match(self, self.context)
        if prs and True:  # prefer friends
            friends = storage.get_friends(storage.get_current_recipient_id())
            fr = [i for i in prs if i.get_dat('id') and i.get_dat('id') in friends]
            if 0 < len(fr) < len(prs):
                return fr
        return prs

    def search_error_message(self, node):
        p = self.describe()
        if p:
            message = 'Could not find a person matching the name "%s"' % p
        else:
            message = "Could not find a matching person"
        return RecipientNotFoundException(node, message=message)

    def singleton_multi_error(self, matches):
        s = ' NL '.join(
            ['%d. %s %s' % (i + 1, n.get_dat('firstName'), n.get_dat('lastName')) for i, n in enumerate(matches)])
        return 'Which of these people did you mean? NL NL ' + s

    def generate_sql_select(self):
        return select(Database.RECIPIENT_TABLE)

    def generate_sql_where(self, selection, parent_id, **kwargs):
        qualifier = kwargs.get('qualifier')
        if "id" in self.inputs:
            # id is the primary key, if it exists it is sufficient to add only this to the where clause
            qualifier = qualifier if qualifier is not None else EQ()
            selection = selection.where(qualifier(Database.RECIPIENT_TABLE.columns.id, self.get_dat("id")))
            return selection

        if 'qualifier' not in kwargs:
            kwargs['qualifier'] = LIKE()
        if "name" in self.inputs:
            # if we have the name, use only it
            return self.input_view("name").generate_sql_where(
                selection, Database.RECIPIENT_TABLE.columns.full_name, **kwargs)
        if "firstName" in self.inputs:
            selection = self.input_view('firstName').generate_sql_where(
                selection, Database.RECIPIENT_TABLE.columns.first_name, **kwargs)
        if "lastName" in self.inputs:
            selection = self.input_view('lastName').generate_sql_where(
                selection, Database.RECIPIENT_TABLE.columns.last_name, **kwargs)

        return selection


class Attendee(Node):

    def __init__(self):
        super().__init__(type(self))
        self.signature.add_sig('recipient', Recipient)
        self.signature.add_sig('response', ResponseStatusType)
        self.signature.add_sig('show', ShowAsStatus)
        self.signature.add_sig('eventid', [Int, Event])  # needed?
        self.signature.add_sig('exclusive', Bool)  # aux field for clobber

    def describe(self, params=None):
        rcp = self.input_view('recipient')
        if rcp:
            resp = [self.input_view(i).describe(params).lower() for i in ['response', 'show'] if i in self.inputs]
            s = rcp.describe(params)
            if 'eventid' in self.inputs:
                s = s + ' @ event#%d' % self.get_dat('eventid')
            return s + ': ' + ', '.join(resp) if resp else s
        return ''

    def generate_sql_select(self):
        return select(Database.EVENT_HAS_ATTENDEE_TABLE).join(Database.RECIPIENT_TABLE)

    def generate_sql_where(self, selection, parent_id, **kwargs):
        # if `parent_id` is not `None`, it is the id of an event. In this case, we need to create a subquery to find
        # the ids of the attendees corresponding to self and check if `parent_id` is one of those.
        # if parent_id is `None`, it is a query on the attendees itself.
        if parent_id is None:
            if 'recipient' in self.inputs:
                selection = self.input_view("recipient").generate_sql_where(
                    selection, Database.EVENT_HAS_ATTENDEE_TABLE.columns.recipient_id, **kwargs)
            if 'response' in self.inputs:
                selection = self.input_view("response").generate_sql_where(
                    selection, Database.EVENT_HAS_ATTENDEE_TABLE.columns.response_status, **kwargs)
            if 'show' in self.inputs:
                selection = self.input_view("show").generate_sql_where(
                    selection, Database.EVENT_HAS_ATTENDEE_TABLE.columns.show_as_status, **kwargs)

            if "eventid" in self.inputs:
                selection = self.input_view('eventid').generate_sql_where(
                    selection, Database.EVENT_HAS_ATTENDEE_TABLE.columns.event_id, **kwargs)
            return selection
        else:
            selection = self._generate_sql_where_for_event(selection, parent_id, **kwargs)

        return selection

    def _generate_sql_where_for_event(self, selection, parent_id, **kwargs):
        """
        Generates the SQL where query, using a subquery, when `parent_id` is not `None`.

        :param selection: the current selection
        :type selection: Any
        :param parent_id: the id of the parent event (this is the representation of the table column which contains
        the id, in the event table, It is NOT the id itself)
        :type parent_id: Any
        :param kwargs: additional parameters to be specified by the implementation
        :type kwargs: Dict[str, Any]
        :return: the query
        :rtype: Any
        """
        subquery = select(Database.EVENT_HAS_ATTENDEE_TABLE.columns.event_id).join(Database.RECIPIENT_TABLE)
        for item in self.inputs:
            subquery = self.input_view(item).generate_sql_where(subquery, parent_id, **kwargs)

        return selection.where(parent_id.in_(subquery))

    def fallback_search(self, parent, all_nodes=None, goals=None, do_eval=True, params=None):
        # prs = [i for i in graph_db.gr_persons if self.match(i)]
        prs = storage.find_attendees_that_match(self, self.context)
        if prs and (not params or 'ignore_friendship' not in params):  # prefer friends
            friends = storage.get_friends(storage.get_current_recipient_id())
            fr = [i for i in prs if i.get_ext_dat('recipient.id') and i.get_ext_dat('recipient.id') in friends]
            if 0 < len(fr) < len(prs):
                return fr
        return prs


# #################################################################################################
# ############################################ event  #############################################


class Event(Node):

    @staticmethod
    def get_event_factory():
        """
        Gets the event factory.

        :return: the event factory
        :rtype: EventFactory
        """
        event_factory_class = globals().get(environment_definitions.event_factory_name)
        if event_factory_class is not None:
            return event_factory_class()

    def __init__(self):
        super().__init__(type(self))
        self.signature.add_sig('subject', Str)
        # for the start/end time - allowing multiple time types (Date/Time/DateTime).
        #   avoids requiring explicit conversion, but might confuse type inference in construction
        self.signature.add_sig('slot', TimeSlot)
        # start, end, duration are now INSIDE slot. They are kept here just as properties only! (shorthand)
        self.signature.add_sig('start', [Date, Time, DateTime, TimeRange, DateRange, DateTimeRange], prop=True)
        self.signature.add_sig('end', [Date, Time, DateTime, TimeRange, DateRange, DateTimeRange], prop=True)
        self.signature.add_sig('duration', Period, prop=True)
        self.signature.add_sig(
            'attendees', Attendee, multi=True)  # either constraint(s) or one/SET of simple Recipient(s)
        self.signature.add_sig('location', LocationKeyphrase)
        self.signature.add_sig('id', Int)

    def get_property(self, nm):
        if nm in ['start', 'end', 'duration'] and 'slot' in self.inputs:
            slot = self.inputs['slot']
            if nm in slot.inputs:
                return slot.inputs[nm]
        raise MissingValueException(nm, self)

    # has this event already been verified by system? (having event id implies it has)
    def is_complete(self):
        return self.get_dat('id') is not None

    # auto convert input time format to DateTime() - wrap inputs by type converters
    def fix_start_end(self):
        trans_to_DateTime(self, 'start')
        trans_to_DateTime(self, 'end')

    def fix_slot(self):
        self.fix_start_end()
        if any([i in self.inputs for i in ['start', 'end', 'duration']]):
            if 'slot' not in self.inputs:
                d, e = self.call_construct_eval('TimeSlot()', self.context, constr_tag=WRAP_COLOR_TAG)
                d.connect_in_out('slot', self)
            slot = self.inputs['slot']
            for i in ['start', 'end', 'duration']:
                if i in self.inputs:
                    n = self.inputs[i]
                    self.disconnect_input(i)
                    n.connect_in_out(i, slot)

    def trans_simple(self, top):
        self.fix_slot()
        return self, None

    # add wrappers - singleton(refer()) around incomplete Recipients
    # note - if trans_simple is applied, and it already added a singleton(refer()) wrapper, then fix_attendee will not
    #        do any change - because the traversal of the tree (looking for Recipient nodes) will be blocked at the
    #        added singleton node above it.
    def fix_attendee(self):
        at = self.input_view('attendees')
        if at and at.typename() not in ['NOT', 'NONE']:
            ats = [i for i in at.get_op_objects(typs=['Recipient']) if not i.is_complete()]
            if ats:
                self.recursive_wrap_input('attendees', 'singleton(refer(', 'Recipient', suf=',multi=True))',
                                          only_incompl=True)

    def valid_constraint(self):
        self.fix_attendee()
        self.fix_slot()

    def valid_input(self):
        self.fix_attendee()
        self.fix_slot()

    def get_attendee_ids(self):
        a = self.input_view('attendees')
        if not a:
            return [], None
        pos, _ = a.get_pos_neg_objs(typ=['Attendee'])
        att_ids = [i.get_ext_dat('recipient.id') for i in pos]
        return att_ids, a

    def describe(self, params=None):
        params = params if params else []
        s = 'meeting' if self.get_dat('subject') is None else self.get_dat('subject')
        if 'attendees' in self.inputs:
            t = self.input_view('attendees').describe_set(params=params)
            if t:
                s += ' with ' + t
        if 'slot' in self.inputs:
            t = self.input_view('slot').describe(params)
            if t:
                s += t
        if 'location' in self.inputs:
            t = self.input_view('location').describe(params + ['add_prep'])
            if t:
                s += ' NL and held ' + t
        return s

    # check if this event is compatible with external data
    #  if this is a common pattern - we may want to add this as a base function
    # check that:
    #  - user is available
    #  - attendees are available
    #  - location is available
    # exclude_id - don't complain about clashes with this event id
    # TODO: add valid_input to check (local) validity of data!
    def event_possible(self, avoid_id=None, allow_clash=False):
        clash = False
        att, _ = self.get_attendee_ids()
        cuid = storage.get_current_recipient_id()
        st = datetime_to_domain_str(self.get_ext_view('slot.start'))
        en = datetime_to_domain_str(self.get_ext_view('slot.end'))
        for a in att:
            evs = storage.get_time_overlap_events(st, en, a, avoid_id=avoid_id)
            if evs:
                if allow_clash:
                    clash = True
                else:
                    e, ex = self.call_construct_eval(event_to_str_node(evs[0]), self.context, register=False)
                    m = 'You already have' if cuid in evs[0].get_attendee_ids_set() else \
                        storage.get_recipient_entry(a).full_name + ' already has'
                    raise ClashEventSuggestionsException(
                        '%s another event overlapping: NL %s' % (m, e.describe()), self)
        loc = self.get_dat('location')
        if loc and loc != 'online':
            evs = storage.get_location_overlap_events(loc, start=st, end=en, avoid_id=avoid_id)
            if evs:
                if allow_clash:
                    clash = True
                else:
                    e, ex = self.call_construct_eval(event_to_str_node(evs[0]), self.context, register=False)
                    raise ClashEventSuggestionsException(
                        'Another event is using this location: NL %s' % e.describe(), self)
        return clash

    def contradicting_commands(self, other):
        for i in self.inputs:
            if i in other.inputs:
                return True
        return False

    def getattr_yield_msg(self, attr, val=None):
        subj = self.get_dat('subject')
        subj = 'The ' + subj if subj else 'it'
        slot = self.input_view('slot')
        if attr == 'start':  # if it does not exist, then getattr would have already complained
            nd = slot.input_view(attr)
            tm = nd.describe(params=['add_prep'])
            return subj + ' is ' + tm
        if attr == 'end':
            nd = slot.input_view(attr)
            tm = nd.describe(params=['add_prep'])
            return subj + ' ends ' + tm
        return super(type(self), self).getattr_yield_msg(attr, val=val)

    def generate_sql_select(self):
        return select(
            Database.EVENT_TABLE,
            Database.LOCATION_TABLE.columns.name, Database.LOCATION_TABLE.columns.always_free
        ).join(Database.LOCATION_TABLE,
               Database.EVENT_TABLE.columns.location_id == Database.LOCATION_TABLE.columns.id, isouter=True)

    def generate_sql_where(self, selection, parent_id, **kwargs):
        if 'start' in self.inputs:
            selection = self.input_view("start").generate_sql_where(
                selection, Database.EVENT_TABLE.columns.starts_at, **kwargs)
        if 'end' in self.inputs:
            selection = self.input_view("end").generate_sql_where(
                selection, Database.EVENT_TABLE.columns.ends_at, **kwargs)
        if "slot" in self.inputs:
            kwargs["start"] = Database.EVENT_TABLE.columns.starts_at
            kwargs["end"] = Database.EVENT_TABLE.columns.ends_at
            selection = self.input_view("slot").generate_sql_where(selection, Database.EVENT_TABLE.columns.id, **kwargs)
        if 'attendees' in self.inputs:
            # select_attendees_with_threshold
            attendees_input = self.input_view('attendees')
            if attendees_input.typename() == 'Empty':
                selection = selection.where(self._attendee_count_query() == 0)
            elif kwargs.get('aggregator') == 'EXACT':
                return self._attendee_count_query()
            else:
                selection = attendees_input.generate_sql_where(selection, Database.EVENT_TABLE.columns.id, **kwargs)
        if 'location' in self.inputs:
            # since event and location has an 1-to-1 relation, we need to join the existing selection from event with
            # the location table
            location_input = self.input_view('location')
            if location_input.typename() in EMPTY_CLEAR_FIELDS:
                selection = location_input.generate_sql_where(
                    selection, Database.EVENT_TABLE.columns.location_id, **kwargs)
            else:
                selection = location_input.generate_sql_where(selection, Database.EVENT_TABLE.columns.id, **kwargs)
        if 'subject' in self.inputs:
            subject_input = self.input_view('subject')
            if subject_input.typename() in EMPTY_CLEAR_FIELDS:
                selection = subject_input.generate_sql_where(selection, Database.EVENT_TABLE.columns.subject, **kwargs)
            else:
                new_kwargs = dict(kwargs)
                if 'qualifier' not in new_kwargs:
                    new_kwargs['qualifier'] = LIKE()
                selection = self.input_view('subject').generate_sql_where(
                    selection, Database.EVENT_TABLE.columns.subject, **new_kwargs)
        if 'id' in self.inputs:
            selection = self.input_view('id').generate_sql_where(selection, Database.EVENT_TABLE.columns.id, kwargs)

        return selection

    def _attendee_count_query(self):
        attendees_subquery = select(
            func.count(distinct(Database.EVENT_HAS_ATTENDEE_TABLE.columns.recipient_id)).label("count")
        ).where(
            Database.EVENT_HAS_ATTENDEE_TABLE.columns.event_id == Database.EVENT_TABLE.columns.id
        ).scalar_subquery()
        return attendees_subquery

    @staticmethod
    def do_fallback_search(flt, parent, all_nodes=None, goals=None, do_eval=True, params=None):
        if environment_definitions.event_fallback_force_curr_user and (not params or 'without_curr_user' not in params):
            # add filter to ensure getting only events with current user
            flt, _ = Node.call_construct('AND(%s, Event?(attendees=ANY(Attendee(recipient=Recipient?(id=%d)))))' %
                                         (id_sexp(flt), storage.get_current_recipient_id()), flt.context, register=False)
        evs = storage.find_events_that_match(flt, flt.context)
        return evs

    def fallback_search(self, parent, all_nodes=None, goals=None, do_eval=True, params=None):
        # unused hack: if self is a "nominal" Event node (used only to invoke the right fallback_search),
        #   then use parent arg as search condition
        return Event.do_fallback_search(self, parent, all_nodes, goals, do_eval, params)

    # handling of TimeSlot constraints is done in a post proc step, not in the turn against turn way, since the
    # pruning of time has to consider more than two objects at a time.
    # to make the design modular, we build a "pure" TimeSlot constraint tree, so that the main logic can be
    #   done entirely within TimeSlot
    @staticmethod
    def post_prune(root, turns):
        slot_turns = [
            Node.get_truncated_constraint_tree(t, 'Event', 'TimeSlot', 'slot', allow_single=['NOT', 'OR'])
            for t in turns]
        prune = TimeSlot.get_prune(slot_turns)
        for p in prune:
            pnm, parent = p.obj.get_parent(typ='Event', name='slot')
            parent.disconnect_input(pnm)

        root.clean_turn_tree()
        # prune is a list of TimeSlots which need to be completely removed
        # now - prune the Event? objects having these TimeSlot objects
        #       and detach empty turns from root

    # here we concentrate the logic regarding when two constraint trees (curr, prev) contradict each other
    # (wholly or partially)
    # if no contradiction - do nothing - return prev
    # if full contradiction - prune all - return None
    # if partial contradiction - prune (in place) prev, and return it
    # this is a "heavy" function - a lot of Event logic - which constraints are compatible with which...
    # potentially move this outside of Event, but it is essentially Event logic.
    @staticmethod
    def prune_modifier_tree(prev, curr, prep, curr_idx, prm=None):
        emtpy = has_emtpy(curr.topological_order())
        psubf, csubf = prev.get_tree_subfields('Event'), curr.get_tree_subfields('Event')
        # get first level fields (direct inputs to Event)
        pf = list(set(['.'.join(i.split('.')[:2]) for i in psubf]))
        cf = list(set(['.'.join(i.split('.')[:2]) for i in csubf]))
        pf1 = list(set(['.'.join(i.split('.')[:1]) for i in psubf]))
        cf1 = list(set(['.'.join(i.split('.')[:1]) for i in csubf]))
        if not set(psubf) & set(csubf) and not ('slot' in pf1 and 'slot' in cf1) and not emtpy:
            return prev  # no intersection - no pruning. TODO: add logic to handle start/end/duration interaction!

        # there are common fields between the two trees
        # if either curr or prev are complex trees - prune prev
        if prev.turn_is_complex() or curr.turn_is_complex():
            # TODO: allow some cases - e.g.
            #   1. OR on different sub fields, e.g.:  prev=AND(month=X, hour=OR(.)), curr=AND(month=OR(), hour=Y)
            #   2. prev: with_attendee X or Y,  curr turn: not X
            #   3. maybe let TimeSlot deal with OR separately?
            return None  # prune

        # both are not complex trees
        ret = prev
        # TODO: add handling of AlwaysTrueConstraint / AlwaysFalseConstraint (using new Qualifiers?)
        # location:
        if 'location' in pf and 'location' in cf:
            prune = Event.prune_single_value_field(prev, curr, 'location')
            ret = prev.prune_field_values('Event', prune)
        # subject:
        if 'subject' in pf and 'subject' in cf:
            prune = Event.prune_single_value_field(prev, curr, 'subject')
            ret = prev.prune_field_values('Event', prune)
        if 'attendees' in pf1 and 'attendees' in cf1:
            # the logic for attendees is:
            # attendees can have multiple (positive) values - they are not mutually exclusive.
            # 1) previous negatives are kept, unless they appear as positive in curr
            # 2) previous positives are kept, unless they appear in cur neg
            # BUT - if any of the current positives is 'exclusive' (clobber), prune all other pos/neg
            # in case of empty:
            #   if current positive OR negative Empty - prune all prevs
            #   if prev positive Empty - prune. if prev negative Empty - for now prune anyway
            ext = 'recipient.id'
            ppos, pneg = prev.get_tree_pos_neg_fields('Event', 'attendees')
            cpos, cneg = curr.get_tree_pos_neg_fields('Event', 'attendees')
            if has_emtpy(cpos) or has_emtpy(cneg) or [i for i in cpos if i.inp_equals('exclusive', True)]:
                prune = ppos + pneg
            else:
                cpos_ids, cneg_ids = [i.get_ext_dat(ext) for i in cpos], [i.get_ext_dat(ext) for i in cneg]
                prune = [i for i in pneg if i.get_ext_dat(ext) and i.get_ext_dat(ext) in cpos_ids] + \
                        [i for i in ppos if i.get_ext_dat(ext) and i.get_ext_dat(ext) in cneg_ids]
                # todo - prune prev turn if has empty <<<
            ret = prev.prune_field_values('Event', prune)

        # TODO: complete logic for: end, duration, subject
        return ret

    @staticmethod
    def prune_single_value_field(prev, curr, field_name):
        """
        Gets the Nodes to be pruned from previous turns, when they contradict values from the current turn.
        This method does NOT perform the pruning, only return the nodes to be pruned elsewhere.

        The logic for single value fields is: (intuition - we interpret multi turns as having AND between them)
        these fields can have only one definitive positive value
           "in loc 1", followed by "in loc 2" --> in loc 2
           (or multiple alternative values 'OR' - "complex tree" - but in that case we prune prev completely)
           "in loc1 or loc2" followed by "in loc 3" --> loc3;
           similarly -- loc1 followed by "loc2 or loc3" -> loc2 or loc3
        it can have multiple negative values (not in loc1 AND not in loc2) - e.g. when filtering a list
          of suggestions.
        1) previous negatives are kept, unless they appear as positive in curr
           "not in loc1" followed by "not in loc2" --> not in loc1 AND not in loc2
           "not in loc1 and not in loc2" followed by "in loc1" --> "in loc1 and not in loc2"
           we keep the negative from the previous turn! Debatable. reason:
             in case later we get "not in loc1" -->  "not in loc1 and not in loc2"
        2) previous positives are deleted if they appear in current neg, or if there is a current pos
           "in loc1" - will be pruned if followed by "in loc2" or "not in loc1"
        3) all previous turn values are deleted, if there is an Empty node in current positives

        :param prev: the tree from previous turns
        :type prev: Node
        :param curr: the tree from the current turn
        :type curr: Node
        :param field_name: the name of the single value field
        :type field_name: str
        :return: the list of Node to be pruned
        :rtype: List[Node]
        """
        ppos, pneg = prev.get_tree_pos_neg_fields('Event', field_name)
        cpos, cneg = curr.get_tree_pos_neg_fields('Event', field_name, dat=True)
        if has_emtpy(cpos):
            prune = ppos + pneg
        else:
            prune = [i for i in pneg if i.dat in cpos] + [i for i in ppos if cpos or i.dat in cneg]
        return prune

    # given a (pruned) tree of constraints, consolidate the tree into one object
    # potentially move this outside of Event, but it is essentially Event logic.
    @staticmethod
    def create_suggestion(root, parent, avoid_id=None):
        return Event.get_event_factory().create_event_suggestion(root, parent, avoid_id)

    # generate sexp converting this event into a constraint tree, where each input field is converted into
    # a separate Event constraint
    # Note: this function is intended to be called on an ACTUAL event, not an event constraint, so we can assume
    #        that the subfields are simple events, not operator trees.
    def event_ctree_str(self, sep_date=True, return_prm=False, open_slot=False):
        prms = []
        if 'subject' in self.inputs:
            prms.append('subject=%s' % id_sexp(self.input_view('subject')))
        # create one constraint for the time slot. logic to be handled by TimeSlot.
        if 'slot' in self.inputs:
            pps = self.input_view('slot').slot_ctree_str(sep_date, open_slot)
            if pps:
                prms.extend(pps)
        if 'attendees' in self.inputs:
            att = self.input_view('attendees')
            if att.typename() == 'SET':
                for a in att.inputs:
                    prms.append('attendees=ANY(%s)' % id_sexp(att.input_view(a)))
            else:
                prms.append('attendees=ANY(%s)' % id_sexp(att))
        if 'location' in self.inputs:
            prms.append('location=%s' % id_sexp(self.input_view('location')))
        if 'id' in self.inputs:
            prms.append('id=%s' % id_sexp(self.input_view('id')))

        s = 'AND(' + ','.join(['Event?(%s)' % p for p in prms]) + ')'
        return prms if return_prm else s


# convert multiple time formats to tree of Event constraints
#   either one Event?(), or AND(Event?(), Event?()) for ranges
class ToEventCTree(Node):
    def __init__(self):
        super().__init__(Event)
        self.signature.add_sig(posname(1), TIME_NODE_TYPES, True)
        self.signature.add_sig('label', Str)  # if True, the time will be used to specify Event.end

    def exec(self, all_nodes=None, goals=None):
        inp = self.input_view(posname(1))
        label = self.get_dat('label') if 'label' in self.inputs else 'start'
        qual, suf = '', ''
        if inp.typename() in ['GT', 'GE', 'LE', 'LT']:
            qual, suf = inp.typename() + '(', ')'
            inp = inp.input_view(posname(1))
        tp = inp.outypename()
        r = ''
        if tp == 'DateTime':
            r = 'Event?(slot=TimeSlot(%s=%s%s%s))' % (label, qual, id_sexp(inp), suf)
            # TODO: split date/time? (won't work with qualifiers)
        elif tp == 'Date':
            r = 'Event?(slot=TimeSlot(%s=%sDateTime?(date=%s)))%s' % (label, qual, id_sexp(inp), suf)
        elif tp == 'Time':
            r = 'Event?(slot=TimeSlot(%s=%sDateTime?(time=%s)))%s' % (label, qual, id_sexp(inp), suf)
        elif isinstance(inp, Range):
            if label in {"bound", "inter"}:
                r = 'Event?(slot=TimeSlot(%s=%s))%s' % (label, id_sexp(inp), suf)
            elif tp == 'DateTimeRange':
                r = inp.to_constr_sexp(ev=label)
            elif tp == 'DateRange':
                r = inp.to_constr_sexp(ev=label)
            elif tp == 'TimeRange':
                r = inp.to_constr_sexp(ev=label)

        d = r if r else 'Event?()'
        r, e = self.call_construct_eval(d, self.context)
        self.set_result(r)


# convert multiple time formats to tree of Event constraints
#   either one Event?(), or AND(Event?(), Event?()) for ranges
class ToEventDurConstr(Node):
    def __init__(self):
        super().__init__(Event)
        self.signature.add_sig(posname(1), Period, True)

    def exec(self, all_nodes=None, goals=None):
        inp = self.input_view(posname(1))
        qual, suf = '', ''
        if inp.typename() in ['GT', 'GE', 'LE', 'LT']:
            qual, suf = inp.typename() + '(', ')'
            inp = inp.input_view(posname(1))
        tp = inp.outypename()
        if tp != 'Period':
            raise InvalidResultException('Error - wrong input: ToEventDurConstr %s / %s' % (inp, inp.show()), self)
        d = 'Event?(slot=TimeSlot(duration=%s%s%s))' % (qual, id_sexp(inp), suf)
        # TODO: split date/time? (won't work with qualifiers)
        r, e = self.call_construct_eval(d, self.context)
        self.set_result(r)


class EventToCTree(Node):
    def __init__(self):
        super().__init__(Event)
        self.signature.add_sig(posname(1), Event, True)

    def exec(self, all_nodes=None, goals=None):
        inp = self.input_view(posname(1))
        s = inp.event_ctree_str()
        d, e = self.call_construct_eval(s, self.context)
        # ugly hack : mark this new tree so that it recognizes it's a multi turn tree
        if d.typename() == 'AND':  # should be the case
            for i in d.inputs:
                d.input_view(i).created_turn = -1
        self.set_result(d)
