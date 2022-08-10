"""
SMCalFlow nodes.
"""
from opendf.exceptions.python_exception import BadEventException
from opendf.graph.nodes.node import *
from opendf.utils.utils import add_element, remove_element
from opendf.defs import is_pos, posname, posname_idx
from opendf.graph.simplify_graph import recursive_simplify_limit

EVENT_NODES = ['CreateEvent', 'FindEvents', 'FindEventWrapperWithDefaults', 'UpdateEvent', 'DeleteEvent',
               'ModifyEventRequest', 'ForwardEventWrapper', 'ConfirmUpdateAndReturnActionIntension',
               'ConfirmDeleteAndReturnAction', 'RecipientAvailability', 'ChooseUpdateEventFromConstraint',
               'CreatePreflightEventWrapper', 'CreateCommitEventWrapper',
               'FindNumNextEvent', 'FindLastEvent', 'ConfirmCreateAndReturnAction', 'ChooseCreateEventFromConstraint']

EVENT_AT_NODES = ['EventOnDate', 'EventOnDate']

EV_TIME_MODS = ['at_time', 'starts_at', 'ends_at', 'avoid_time', 'avoid_start', 'avoid_end']

TIME_NODE_NAMES = ['DateTime', 'Date', 'Time', 'DateRange', 'TimeRange', 'DateTimeRange']

NEGATIONS = ['NOT', 'negate', 'NEQ']

ASSIGN_NODES = ['x%d' % i for i in range(7)]

connect_assign = False  # keep this False to be safe. Turning on allows transparent traversal through assignments,


#   but can lead to unexpected behavior, as well as making graph drawing messier


def float_input_to_int(n, i):
    if n and i in n.inputs and n.inputs[i].data is not None and isinstance(n.inputs[i].data, float):
        n.inputs[i].data = int(n.inputs[i].data)

# check if the context has an assignment with the name n
def is_assigned(n, d_context):
    return d_context.is_assigned(n)


# use this only when SURE the assignment is not used more than once, OR that the assignment does not do anything which
#   should be done only once (e.g. performing a refer...)
# TODO: maybe add a check for that here?
def follow_assign(nd):
    # return d_context.get_node(nd.typename()) if nd.typename() in d_context.assign else nd
    return nd.context.get_node(nd.typename()) if nd.context and nd.typename() in nd.context.assign else nd


def compose_ev_constr(nd, top, mode):
    d_context = nd.context
    pnm, parent = nd.get_parent()
    if parent.typename() != 'AND':
        parent.wrap_input(pnm, 'AND(')
    pnm, parent = nd.get_parent()
    ev = nd.input_view('event')
    if ev:
        if len(ev.inputs) > 0:
            # prevent simplification from going up to parent
            nd.disconnect_input('event')
            n, e = recursive_simplify_limit(ev, d_context, top, None, mode)
            parent.add_pos_input(n)
        nd.disconnect_input('event')


# get the person/attendee/name which is the "seed" of a computation representing a person.
# this is called from simplify() of the root of the computation (e.g. AttendeeListHasRecipient),
# nd is the relevant input of that root
# returns the "seed" - name / recipient / attendee. return None if failed
# TODO: handle assignment correctly
def get_person(nd):
    if not nd:
        return None
    if len(nd.inputs) == 0:
        return nd
    if nd.typename() == 'PersonName' and 'pos1' in nd.inputs:
        return nd.inputs['pos1']

    if nd.typename() in ['Str', 'String']:
        return nd

    if nd.typename() == 'toRecipient' and 'pos1' in nd.inputs:
        return get_person(nd.input_view('pos1'))

    if nd.typename() == 'Execute':
        path, names = nd.get_input_path(':refer.:extensionConstraint.pos1')
        if path:
            return get_person(path[-1])

    if nd.typename() == 'RecipientWithNameLike':
        constr, name = nd.get_input_views(['constraint', 'name'])
        if constr and name:
            if len(constr.inputs) == 0 or constr.typename() == 'EQ':
                return get_person(name)
            elif constr.typename() == 'refer' and name.typename() == 'PersonName':
                inp = constr.input_view('pos1')
                if inp.typename() == 'Recipient' and len(inp.inputs) == 0:
                    return get_person(name)
        elif name:
            return get_person(name)

    if nd.typename() == 'AttendeeListHasRecipient' and 'pos1' in nd.inputs:
        return get_person(nd.input_view('pos1'))

    if nd.typename() == 'RecipientFromRecipientConstraint' and 'pos1' in nd.inputs:
        if nd.input_view('pos1').typename() == 'EQ':
            nd = nd.input_view('pos1')
        return get_person(nd.input_view('pos1'))

    if nd.typename() == 'refer':
        path, names = nd.get_input_path(':Recipient.:LIKE.pos1')
        if path:
            return get_person(path[-1])

    path, names = nd.get_input_path(':RecipientWithNameLike.name')
    if path:
        return get_person(path[-1])

    return None


############################################################


class Operator(Node):
    def __init__(self, outtyp=None):
        super().__init__(outtyp)
        self.copy_in_type = posname(1)  # to help type inference -- not used anymore (for any node type!)


# Aggregators: AND, OR, SET, ...
class Aggregator(Operator):
    def __init__(self, outtyp=None):
        super().__init__(outtyp)


# Qualifiers: EQ, NEQ, GT, LT, ...
class Qualifier(Operator):
    def __init__(self, outtyp=None):
        super().__init__(outtyp)


class Modifier(Node):
    def __init__(self, outtyp=None):
        super().__init__(outtyp)


############################################################
# new base types

class Int(Node):
    def __init__(self):
        super().__init__(type(self))


class Float(Node):
    def __init__(self):
        super().__init__(type(self))


class Bool(Node):
    def __init__(self):
        super().__init__(type(self))


class Str(Node):
    def __init__(self):
        super().__init__(type(self))


class CasedStr(Node):
    def __init__(self):
        super().__init__(type(self))


class Index(Node):
    def __init__(self):
        super().__init__(type(self))
        self.signature.add_sig(posname(1), Int)


###################################################################

# Leaf 

class Duration(Node):
    def __init__(self):
        super().__init__(Duration)
        self.signature.add_sig('pos1', Node)


class Boolean(Node):
    def __init__(self):
        super().__init__(Boolean)
        self.signature.add_sig('pos1', Str)


class LocationKeyphrase(Node):
    def __init__(self):
        super().__init__(LocationKeyphrase)
        self.signature.add_sig('pos1', Str)

    def simplify(self, top, mode):
        if 'pos1' in self.inputs:
            inp = self.inputs['pos1']
            if inp.data:
                self.replace_self(inp)
                return inp, None, mode
        return self, None, mode


class PersonName(Node):
    def __init__(self):
        super().__init__(PersonName)
        self.signature.add_sig('pos1', Str)

    def simplify(self, top, mode):
        pnm, parent = self.get_parent()
        if parent.typename() == 'Let':
            self.replace_self(self.inputs['pos1'])
            return parent, None, mode
        return self, None, mode


class DayOfWeek(Node):
    def __init__(self):
        super().__init__(DayOfWeek)
        self.signature.add_sig('pos1', Str)


class Number(Node):
    def __init__(self):
        super().__init__(Number)
        self.signature.add_sig('pos1', Str)

    def simplify(self, top, mode):
        if 'pos1' in self.inputs:
            n = self.inputs['pos1']
            if n.dat:
                self.replace_self(n)
                return n, None, mode
        return self, None, mode


class Month(Node):
    def __init__(self):
        super().__init__(Month)
        self.signature.add_sig('pos1', Str)


class WeatherProp(Node):
    def __init__(self):
        super().__init__(WeatherProp)
        self.signature.add_sig('pos1', Str)


class WeatherQuantifier(Node):
    def __init__(self):
        super().__init__(WeatherQuantifier)
        self.signature.add_sig('pos1', Str)
        #  Average, Summarize, Sum, Min, Max


class RespondComment(Node):
    def __init__(self):
        super().__init__(RespondComment)
        self.signature.add_sig('pos1', Str)


class ResponseStatusType(Node):
    def __init__(self):
        super().__init__(ResponseStatusType)
        self.signature.add_sig('pos1', Str)
        #  Accepted, Declined, TentativelyAccepted, None, NotResponded


class Holiday(Node):
    def __init__(self):
        super().__init__(Holiday)
        self.signature.add_sig('pos1', Str)
        #  FathersDay, ValentinesDay, EasterMonday, Halloween, AshWednesday, NewYearsDay, PresidentsDay,
        #  StPatricksDay, EarthDay, LaborDay, FlagDay, MothersDay, Thanksgiving, Easter, BlackFriday,
        #  VeteransDay, TaxDay, MemorialDay, MardiGras, Kwanzaa, GoodFriday, NewYearsEve, GroundhogDay,
        #  MLKDay, IndependenceDay, ElectionDay, ColumbusDay, PalmSunday, AprilFoolsDay, PatriotDay, Christmas


class PlaceFeature(Node):
    def __init__(self):
        super().__init__(PlaceFeature)
        self.signature.add_sig('pos1', Str)
        #  FullBar, OutdoorDining, WaiterService, FamilyFriendly, Takeout, Casual, GoodforGroups, HappyHour


class Temperature(Node):
    def __init__(self):
        super().__init__(Temperature)
        self.signature.add_sig('pos1', Int)


class AttendeeType(Node):
    def __init__(self):
        super().__init__(AttendeeType)
        self.signature.add_sig('pos1', Str)
        #  Required, Optional


class RespondShouldSend(Node):
    def __init__(self):
        super().__init__(RespondShouldSend)
        self.signature.add_sig('pos1', Str)


############################################################
# types


class CreateCommitEvent(Node):
    def __init__(self):
        super().__init__(CreateCommitEvent)
        self.signature.add_sig('data', EventSpec)


class Date(Node):
    def __init__(self):
        super().__init__(Date)
        self.signature.add_sig('dayOfWeek', Node)
        self.signature.add_sig('day', Node)
        self.signature.add_sig('month', Node)
        self.signature.add_sig('nonEmptyBase', Node)
        self.signature.add_sig('year', Node)
        self.signature.add_sig('dow', DayOfWeek)  # new param

    def simplify(self, top, mode):
        float_input_to_int(self, 'year')
        float_input_to_int(self, 'day')
        return self, None, mode


class DateTime(Node):
    def __init__(self):
        super().__init__(DateTime)
        self.signature.add_sig('date', Node)
        self.signature.add_sig('time', Node)
        self.signature.add_sig('dow', DayOfWeek)  # new param

    def simplify(self, top, mode):
        pnm, parent = self.get_parent()
        s = [i for i in ['date', 'time', 'dow'] if i in self.inputs]
        if len(s) == 1:
            p = self.inputs[s[0]]
            if parent.is_modifier():
                self.replace_self(p)
                return parent, None, mode
        return self, None, mode


# TODO: currently we explicitly open these to separate modifiers (AND(starts_at(), ...). Alternatively, we could define
#  similar functions, without the 'event' field (or even keep the same funcs, just omit the event input), and expand
#  them at run time? would that be "simpler"?

EVENT_WITH_TIME = ['EventOnDate', 'EventOnDateTime', 'EventDuringRange', 'EventDuringRangeDateTime',
                   'EventAllDayForDateRange', 'EventAllDayOnDate', 'EventAllDayOnDate', 'EventAtTime',
                   'EventAllDayStartingDateForPeriod', 'EventSometimeOnDate', 'EventOnDateWithTimeRange',
                   'EventBeforeDateTime', 'EventOnDateFromTimeToTime', 'EventOnDateFromTimeToTime',
                   'EventRescheduled', 'EventAfterDateTime', 'EventOnDateAfterTime', 'EventOnDateBeforeTime']

EVENT_WITH_TIME_SPAN = ['EventAllDayForDateRange', 'EventAllDayOnDate', 'EventAllDayStartingDateForPeriod']


def adjust_pos_neg_date(pos, neg):
    if not neg and len(pos) == 1:
        p = pos[0]
        d_context = p.context
        if p.typename() in ['DateTime', 'Date', 'Time']:
            if p.typename() == 'DateTime':
                if len(p.inputs) != 1:
                    return pos, neg
                p = p.get_single_input_view()
            if p.typename() in ['NOT', 'negate', 'NEQ'] and 'pos1' in p.inputs:
                ng = p.input_view('pos1')
                p.replace_self(ng)
                pos, neg = [], [ng]
            elif len(p.inputs) == 1:
                nd = p.get_single_input_view()
                if nd.typename() in ['NOT', 'negate', 'NEQ'] and 'pos1' in nd.inputs:
                    ng = nd.input_view('pos1')
                    nd.replace_self(ng)
                    pos, neg = [], [ng]

    return pos, neg


class Event(Node):
    def __init__(self):
        super().__init__(Event)
        self.signature.add_sig('attendees', Node)
        self.signature.add_sig('location', Node)
        self.signature.add_sig('subject', Node)
        self.signature.add_sig('start', Node)
        self.signature.add_sig('duration', Node)
        self.signature.add_sig('end', Node)
        self.signature.add_sig('id', Node)
        self.signature.add_sig('nonEmptyBase', Node)
        self.signature.add_sig('showAs', Node)
        self.signature.add_sig('isAllDay', Node)
        self.signature.add_sig('isOneOnOne', Node)
        self.signature.add_sig('organizer', Node)
        self.signature.add_sig('responseStatus', Node)
        self.signature.add_sig('span', Node)  # temp var
        # aux, only for simplification
        self.signature.add_sig('range', Node)

    def simplify(self, top, mode):
        pnm, parent = self.get_parent()
        d_context = self.context

        if len(self.inputs) > 1:
            mode = remove_element(mode, 'modify_event')

        if 'nonEmptyBase' in self.inputs:
            path, names = self.get_input_path('nonEmptyBase.:refer.:Event')
            if path and path[0].typename() == 'Execute' and len(path[-1].inputs) == 0:
                self.disconnect_input('nonEmptyBase')
            else:
                if parent.typename() != 'AND':
                    parent.wrap_input(pnm, 'AND(')
                    pnm, parent = self.get_parent()
                n, e = recursive_simplify_limit(self.inputs['nonEmptyBase'], d_context, top, None, mode)
            self.disconnect_input('nonEmptyBase')
            parent.add_pos_input(n)

        if mode and 'modify_event' in mode and self.constraint_level == 1:
            # careful - returning parent may cause simplification to unexpectedly stop - e.g. if parent AND's are merged
            if 'attendees' in self.inputs:  # for attendees, no need to decide now if positive or negative
                n = self.inputs['attendees']
                self.replace_self(n)
                if n.typename() == 'AND':
                    return parent, None, mode
                return n, None, mode
            if 'organizer' in self.inputs:  # for attendees, no need to decide now if positive or negative
                n = self.inputs['organizer']
                nd = get_person(n)
                if nd:
                    d, e = self.call_construct('with_organizer(%s)' % id_sexp(nd), d_context)
                    self.replace_self(d)
                    return parent, None, mode
                return n, None, mode
            if 'start' in self.inputs:
                n = self.inputs['start']
                pos, neg = n.res.get_pos_neg_objs()
                pos, neg = adjust_pos_neg_date(pos, neg)
                func = 'avoid_start' if neg else 'starts_at'  # enough??
                d, e = self.call_construct('%s(%s)' % (func, id_sexp(n)), d_context)
                self.replace_self(d)
                return d, None, mode
            if 'end' in self.inputs:
                n = self.inputs['end']
                pos, neg = n.res.get_pos_neg_objs()
                func = 'avoid_end' if neg else 'ends_at'  # enough??
                d, e = self.call_construct('%s(%s)' % (func, id_sexp(n)), d_context)
                self.replace_self(d)
                return d, None, mode
            if 'range' in self.inputs:
                n = self.inputs['range']
                pos, neg = n.res.get_pos_neg_objs()
                func = 'avoid_time' if neg else 'at_time'  # enough??
                d, e = self.call_construct('%s(%s)' % (func, id_sexp(n)), d_context)
                self.replace_self(d)
                return d, None, mode
            if 'span' in self.inputs:
                n = self.inputs['span']
                func = 'spans_time'
                d, e = self.call_construct('%s(%s)' % (func, id_sexp(n)), d_context)
                self.replace_self(d)
                return d, None, mode
            if 'duration' in self.inputs:
                n = self.inputs['duration']
                pos, neg = n.res.get_pos_neg_objs()
                func = 'avoid_duration' if neg else 'has_duration'  # enough??
                d, e = self.call_construct('%s(%s)' % (func, id_sexp(n)), d_context)
                self.replace_self(d)
                return d, None, mode
            if 'subject' in self.inputs:
                n = self.inputs['subject']
                pos, neg = n.res.get_pos_neg_objs()
                func = 'avoid_subject' if neg else 'has_subject' if pos else None  # enough??
                if not func:
                    raise BadEventException('event subject...??')
                obj = neg[0] if neg else pos[0]
                d, e = self.call_construct('%s(%s)' % (func, id_sexp(obj)), d_context)
                self.replace_self(d)
                return d, None, remove_element(mode, 'modify_event')
            if 'location' in self.inputs:
                n = self.inputs['location']
                pos, neg = n.res.get_pos_neg_objs()
                func = 'avoid_location' if neg else 'at_location' if pos else None  # enough??
                if not func:
                    raise BadEventException('event location...??')
                obj = neg[0] if neg else pos[0]
                d, e = self.call_construct('%s(%s)' % (func, id_sexp(obj)), d_context)
                self.replace_self(d)
                return d, None, mode
            if 'showAs' in self.inputs:
                n = self.inputs['showAs']
                func = 'has_status'
                d, e = self.call_construct('%s(%s)' % (func, id_sexp(n)), d_context)
                self.replace_self(d)
                return d, None, remove_element(mode, 'modify_event')
            if 'id' in self.inputs:
                n = self.inputs['id']
                pos, neg = n.res.get_pos_neg_objs()
                func = 'avoid_id' if neg else 'has_id' if pos else None  # enough??
                if not func:
                    raise BadEventException('event id...??')
                obj = neg[0] if neg else pos[0]
                d, e = self.call_construct('%s(%s)' % (func, id_sexp(obj)), d_context)
                self.replace_self(d)
                return d, None, mode
            if 'isAllDay' in self.inputs:
                n = self.inputs['isAllDay']
                pos, neg = n.res.get_pos_neg_objs()
                v = pos and pos[0].dat
                func = 'is_allDay' if v else 'not_allDay'
                d, e = self.call_construct('%s()' % func, d_context)
                self.replace_self(d)
                return d, None, mode
            if 'isOneOnOne' in self.inputs:
                n = self.inputs['isOneOnOne']
                pos, neg = n.res.get_pos_neg_objs()
                v = pos and pos[0].dat
                func = 'is_oneOnOne' if v else 'not_oneOnOne'
                d, e = self.call_construct('%s()' % func, d_context)
                self.replace_self(d)
                return d, None, mode

        # TODO: handle case of (possibly multiple) AND wrapper(s) around current Event
        up, _ = None, None
        if parent.typename() == 'AND':  # handles only one AND wrapper - TODO: add handle multi
            nn, pp = parent.get_parent()
            if pp and pp.typename() in EVENT_NODES + ['refer']:
                up = pp
        if (not mode or 'modify_event' not in mode) and self.constraint_level == 1 and \
                ((parent.typename() in EVENT_NODES + EVENT_WITH_TIME + ['refer']) or up):
            st, en = self.get_inputs(['start', 'end'])
            if st and en and st.show() == en.show():
                self.disconnect_input('start')
                self.disconnect_input('end')
                st.connect_in_out('range', self)
            s = self.to_separate_input_constr_str()
            e = None
            if s and s.startswith('AND'):  # if only one input - no change needed
                d, e = self.call_construct(s, d_context)
                self.replace_self(d)
            return parent, e, add_element(mode, 'modify_event')
        return self, None, mode


class EventSpec(Node):
    def __init__(self):
        super().__init__(EventSpec)
        self.signature.add_sig('start', Node)
        self.signature.add_sig('attendees', Node)


class Path(Node):
    def __init__(self):
        super().__init__(Path)
        self.signature.add_sig('pos1', Str)


class PeriodDuration(Node):
    def __init__(self):
        super().__init__(PeriodDuration)
        self.signature.add_sig('period', Node)
        self.signature.add_sig('duration', Node)
        self.signature.add_sig('pos1', RawDateTime)  # new param


class Person(Node):  # V2
    def __init__(self):
        super().__init__(Person)
        self.signature.add_sig('phoneNumber', Node)
        self.signature.add_sig('officeLocation', Node)
        self.signature.add_sig('emailAddress', Node)


class Place(Node):
    def __init__(self):
        super().__init__(Place)
        self.signature.add_sig('rating', Node)
        self.signature.add_sig('url', Node)
        self.signature.add_sig('price', Node)
        self.signature.add_sig('phoneNumber', Node)
        self.signature.add_sig('formattedAddress', Node)
        self.signature.add_sig('hours', Node)


class QueryEventResponse(Node):
    def __init__(self):
        super().__init__(QueryEventResponse)
        self.signature.add_sig('results', Node)


class Recipient(Node):
    def __init__(self):
        super().__init__(Recipient)
        self.signature.add_sig('name', [Str, PersonName])  # new param
        self.signature.add_sig('firstName', Str)  # new param
        self.signature.add_sig('lastName', Str)  # new param
        self.signature.add_sig('id', Int)  # new param
        self.signature.add_sig('pos1', Str)  # new param


class ShowAsStatus(Node):
    def __init__(self):
        super().__init__(ShowAsStatus)
        self.signature.add_sig('pos1', Str)
        #  OutOfOffice, WorkingElsewhere, Unknown, Busy, Tentative, Free


class String(Node):
    def __init__(self):
        super().__init__(String)
        self.signature.add_sig('pos1', Node)


############################################################
# Functions


class Acouple(Node):
    def __init__(self):
        super().__init__()


class ActionIntensionConstraint(Node):
    def __init__(self):
        super().__init__()


class Add(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)
        self.signature.add_sig('pos2', [Number, Int])

    def simplify(self, top, mode):
        float_input_to_int(self, 'pos2')
        return self, None, mode


class Afew(Node):
    def __init__(self):
        super().__init__()


class Afternoon(Node):
    def __init__(self):
        super().__init__(TimeRange)


class AgentStillHere(Node):
    def __init__(self):
        super().__init__()


class AlwaysFalseConstraint(Node):
    def __init__(self):
        super().__init__()


class AlwaysTrueConstraint(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)  # new param

    def simplify(self, top, mode):
        pnm, parent = self.get_parent()
        if 'pos1' in self.inputs:
            inp = self.inputs['pos1']
            if parent.typename() == 'refer' and inp.typename() == inp.outypename() and inp.constraint_level == 0:
                inp.constraint_level = 1
                self.replace_self(inp)
                return parent, None, mode
        return self, None, mode


class AroundDateTime(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('dateTime', Node)


# AtPlace is a "casting" type - no need to explicitly mention it - it can be recovered at infer time based on input type
class AtPlace(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('place', Node)
        self.signature.add_sig('pos1', PlaceUniqueID)  # new param

    def simplify(self, top, mode):
        path, names = self.get_input_path_by_type('FindPlace.LocationKeyphrase.Str')
        pnm, parent = self.get_parent()
        if path:
            self.disconnect_input(names[0])
            self.replace_self(path[-1])
            return self, None, mode
        path, names = self.get_input_path(':FindPlace.keyphrase')
        if path:
            self.replace_self(path[-1])
            return parent, None, mode
        elif 'place' in self.inputs:  # replace all place?
            pl = self.input_view('place')
            self.replace_self(pl)
            return parent, None, mode
        return self, None, mode


class AttendeeFromEvent(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('event', Node)
        self.signature.add_sig('recipient', Node)

    # TODO: this logic may need to move to Event.simplify!!
    def simplify(self, top, mode):
        path, names = self.get_input_path_by_type(
            'Execute.refer.extensionConstraint.RecipientWithNameLike.PersonName.Str')
        if path:
            d, e = path[-1], None
            self.replace_input('recipient', d)
            return self, e, mode
        return self, None, mode


class AttendeeListExcludesRecipient(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('recipient', Node)

    def simplify(self, top, mode):
        pnm, parent = self.get_parent()
        path, names = self.get_input_path_by_type(
            'RecipientWithNameLike.EQ.Execute.refer.extensionConstraint.Recipient')
        path2, names2 = self.get_input_path_by_type('RecipientWithNameLike.PersonName.Str')
        if not path:
            path, names = self.get_input_path_by_type(
                'EQ.Execute.refer.extensionConstraint.RecipientWithNameLike.PersonName.Str')
            path2 = path
        if path and path2:
            d, e = self.call_construct('avoid_attendee(%s)' % id_sexp(path2[-1]), self.context)
            self.replace_self(d)
            return parent, e, mode
        if parent.typename() in EVENT_NODES:
            path, names = self.get_input_path_by_type(
                'EQ.Execute.refer.extensionConstraint.RecipientWithNameLike.PersonName.Str')
            if path:
                d, e = self.call_construct('avoid_attendee(%s)' % id_sexp(path[-1]), self.context)
                self.replace_self(d)
                return parent, e, mode
        if mode and 'modify_event' in mode:
            d, e = self.call_construct('avoid_attendee(%s)' % id_sexp(self.inputs['recipient']), self.context)
            self.replace_self(d)
            return parent, e, mode

        return self, None, mode


class AttendeeListHasPeople(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('people', Node)

    def simplify(self, top, mode):
        pnm, parent = self.get_parent()
        ppl = self.input_view('people')
        if ppl and mode and 'modify_event' in mode:
            d, e = self.call_construct('with_attendee(%s)' % id_sexp(ppl), self.context)
            self.replace_self(d)
            return parent, e, mode
        return self, None, mode


class AttendeeListHasPeopleAnyOf(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('people', Node)


class AttendeeListHasRecipient(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('recipient', Node)

    # TODO: this logic may need to move to Event.simplify!!
    def simplify(self, top, mode):
        pnm, parent = self.get_parent()
        rcp = self.input_view('recipient')
        nd = get_person(rcp)
        if nd:
            d, e = self.call_construct('with_attendee(%s)' % id_sexp(nd), self.context)
            self.replace_self(d)
            return parent, e, mode

        path, names = self.get_input_path(':Execute.:refer.:extensionConstraint.:RecipientWithNameLike.name')
        if path:
            p = path[-1]
            s = id_sexp(p.input_view('pos1')) if p.typename() == 'PersonName' else id_sexp(p)
            d, e = self.call_construct('with_attendee(%s)' % s, self.context)
            self.replace_self(d)
            return parent, e, mode
        if mode and 'modify_event' in mode:
            d, e = self.call_construct('with_attendee(%s)' % id_sexp(self.inputs['recipient']), self.context)
            self.replace_self(d)
            return parent, e, mode
        if parent.typename() in ['allows'] and parent.get_subnodes_of_type('Event'):
            d, e = self.call_construct('with_attendee(%s)' % id_sexp(self.inputs['recipient']), self.context)
            self.replace_self(d)
            return parent, e, mode

        return self, None, mode


class AttendeeListHasRecipientConstraint(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('recipientConstraint', Node)

    # TODO: this logic may need to move to Event.simplify!!
    def simplify(self, top, mode):
        pnm, parent = self.get_parent()
        rcp = self.input_view('recipient')
        nd = get_person(rcp)
        if nd:
            d, e = self.call_construct('with_attendee(%s)' % id_sexp(nd), self.context)
            self.replace_self(d)
            return parent, e, mode

        path, names = self.get_input_path_by_type('RecipientWithNameLike.PersonName.Str')
        if path:
            d, e = self.call_construct('with_attendee(%s)' % id_sexp(path[-1]), self.context)
            self.replace_self(d)
            return parent, e, mode
        path = self.get_input_path_by_name('recipientConstraint.name')
        if path:
            d, e = self.call_construct('with_attendee(%s)' % id_sexp(path[-1]), self.context)
            self.replace_self(d)
            return parent, e, mode
        if mode and 'modify_event' in mode:
            d, e = self.call_construct('with_attendee(%s)' % id_sexp(self.inputs['recipientConstraint']), self.context)
            self.replace_self(d)
            return parent, e, mode
        return self, None, mode


class AttendeeListHasRecipientWithType(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('recipient', Node)
        self.signature.add_sig('type', AttendeeType)

    # TODO: this logic may need to move to Event.simplity!

    def simplify(self, top, mode):
        pnm, parent = self.get_parent()
        rcp = self.input_view('recipient')
        nd = get_person(rcp)
        if nd:
            d, e = self.call_construct('with_attendee(%s)' % id_sexp(nd), self.context)
            self.replace_input('recipient', d)
            return parent, e, mode

        path, names = self.get_input_path(':Execute.:refer.:extensionConstraint.:RecipientWithNameLike.name')
        if path and names[0] == 'recipient':
            p = path[-1]
            s = id_sexp(p.input_view('pos1')) if p.typename() == 'PersonName' else id_sexp(p)
            d, e = self.call_construct('with_attendee(%s)' % s, self.context)
            self.replace_input('recipient', d)
            return self, e, mode
        if mode and 'modify_event' in mode:
            d, e = self.call_construct('with_attendee(%s)' % id_sexp(self.inputs['recipient']), self.context)
            self.replace_input('recipient', d)
            return self, e, mode
        if parent.typename() in ['allows'] and parent.get_subnodes_of_type('Event'):
            d, e = self.call_construct('with_attendee(%s)' % id_sexp(self.inputs['recipient']), self.context)
            self.replace_input('recipient', d)
            return self, e, mode

        return self, None, mode


class AttendeeResponseStatus(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('attendee', Node)


class AttendeesWithNotResponse(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('attendees', Node)
        self.signature.add_sig('response', ResponseStatusType)


class AttendeesWithResponse(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('attendees', Node)
        self.signature.add_sig('response', ResponseStatusType)


class BottomResult(Node):
    def __init__(self):
        super().__init__()


class Breakfast(Node):
    def __init__(self):
        super().__init__()


class Brunch(Node):
    def __init__(self):
        super().__init__()


class CancelScreen(Node):
    def __init__(self):
        super().__init__()


class ChooseCreateEvent(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('index', Node)
        self.signature.add_sig('intension', Node)

    def simplify(self, top, mode):
        pnm, parent = self.get_parent()
        path, _ = self.get_input_path(':refer.:ActionIntensionConstraint')
        ind, ins = self.get_inputs(['index', 'intension'])
        if ind and path:
            d, e = self.call_construct('AcceptSuggestion(%s)' % id_sexp(ind), self.context)
            self.replace_self(d)
            return parent, e, mode
        return self, None, mode


class ChooseCreateEventFromConstraint(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('constraint', Node)
        self.signature.add_sig('intension', Node)

    def simplify(self, top, mode):
        pnm, parent = self.get_parent()
        cstr, ins = self.get_inputs(['constraint', 'intension'])
        if cstr and ins and cstr.typename() == 'Event' and len(
                cstr.inputs) == 0 and ins.typename() == 'refer' and 'pos1' in ins.inputs:
            rf = ins.inputs['pos1']
            if rf.typename() == 'ActionIntensionConstraint' and len(rf.inputs) == 0:
                d, e = self.call_construct('AcceptSuggestion()', self.context)
                self.replace_self(d)
                return parent, e, mode
        if ins:  # TODO: verify
            path = ins.get_input_path_by_type('refer.ActionIntensionConstraint')
            if path:
                self.disconnect_input('intension')
        return self, None, mode


class ChoosePersonFromConstraint(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('constraint', Node)
        self.signature.add_sig('intension', Node)


class ChooseUpdateEvent(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('index', Node)
        self.signature.add_sig('intension', Node)

    def simplify(self, top, mode):
        pnm, parent = self.get_parent()
        path, names = self.get_input_path(':refer.:ActionIntensionConstraint')
        ind, ins = self.get_inputs(['index', 'intension'])
        if ind and path and ind.dat is not None:
            d, e = self.call_construct('AcceptSuggestion(%d)' % ind.dat, self.context)
            self.replace_self(d)
            return parent, e, mode
        return self, None, mode


class ChooseUpdateEventFromConstraint(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('constraint', Node)
        self.signature.add_sig('intension', Node)

    def simplify(self, top, mode):
        pnm, parent = self.get_parent()
        cstr, ins = self.get_inputs(['constraint', 'intension'])
        if cstr and ins and cstr.typename() == 'Event' and len(
                cstr.inputs) == 0 and ins.typename() == 'refer' and 'pos1' in ins.inputs:
            rf = ins.inputs['pos1']
            if rf.typename() == 'ActionIntensionConstraint' and len(rf.inputs) == 0:
                d, e = self.call_construct('AcceptSuggestion()', self.context)
                self.replace_self(d)
                return parent, e, mode
        if ins:  # TODO: verify
            path = ins.get_input_path_by_type('refer.ActionIntensionConstraint')
            if path:
                self.disconnect_input('intension')
        return self, None, mode


class ClosestDay(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('date', Node)
        self.signature.add_sig('day', [Number, Int])

    def simplify(self, top, mode):
        float_input_to_int(self, 'day')
        return self, None, mode


class ClosestDayOfWeek(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('date', Node)
        self.signature.add_sig('dow', DayOfWeek)


class ClosestMonthDayToDate(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('date', Node)
        self.signature.add_sig('day', [Number, Int])
        self.signature.add_sig('month', Month)

    def simplify(self, top, mode):
        float_input_to_int(self, 'day')
        return self, None, mode


class ConfirmAndReturnAction(Node):
    def __init__(self):
        super().__init__()


class ConfirmCreateAndReturnAction(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node, alias='constraint')


class ConfirmDeleteAndReturnAction(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('constraint', Node)


class ConfirmUpdateAndReturnActionIntension(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('constraint', Event)


class ConvertTimeToAM(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('time', Node)


class ConvertTimeToPM(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('time', Node)


class CreateCommitEventWrapper(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('event', Node)
        self.signature.add_sig('sugg', Event)  # new param
        self.signature.add_sig('confirm', Bool)  # new param

    def simplify(self, top, mode):
        pnm, parent = self.get_parent()
        path, names = self.get_input_path(':Execute.:refer.:extensionConstraint.:CreateCommitEvent.:EventSpec')
        if path:
            cl = path[-1].constraint_level
            r, e = path[-1].simplify_rename('Event')
            r.constraint_level = cl
            d, e = self.call_construct('ChooseCreateEventFromConstraint(constraint=%s)' % id_sexp(r), self.context)
            self.replace_self(d)
            return parent, None, mode
        path = self.get_input_path_by_name('event.constraint')
        if path:
            _, n2 = path
            d, e = self.call_construct('CreateEvent(%s)' % id_sexp(n2), self.context)
            self.replace_self(d)
            return parent, e, mode
        return self, None, mode


class CreateEventResponse(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('end', DateTime)
        self.signature.add_sig('nonEmptyBase', Node)


class CreatePreflightEventWrapper(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('constraint', Node)
        self.signature.add_sig('tmp', Node)  # new param


class CurrentUser(Node):
    def __init__(self):
        super().__init__()


class DateAndConstraint(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('date1', Node)
        self.signature.add_sig('date2', Node)


# TODO: define set of similar nodes ['DateAtTimeWithDefaults']...

class DateAtTimeWithDefaults(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('date', Node)
        self.signature.add_sig('time', Node)

    def simplify(self, top, mode):
        pnm, parent = self.get_parent()
        dt, tm = self.get_inputs(['date', 'time'])
        if dt and tm:
            g, e = self.call_construct('DateTime?(date=%s, time=%s)' % (id_sexp(dt), id_sexp(tm)), self.context)
            self.replace_self(g)
            return parent, None, mode
        return self, None, mode


# this means a time RANGE
class DateTimeAndConstraint(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('dateTime1', Node)
        self.signature.add_sig('dateTime2', Node)

    def simplify(self, top, mode):
        pnm, parent = self.get_parent()
        d1, d2 = self.get_inputs(['dateTime1', 'dateTime2'])
        if d1 and d2:
            g, e = self.call_construct('DateTimeRange(start=%s, end=%s)' % (id_sexp(d1), id_sexp(d2)), self.context)
            self.replace_self(g)
            return parent, None, mode
        return self, None, mode


class DateTimeAndConstraintBetweenEvents(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('event1', Node)
        self.signature.add_sig('event2', Node)


class DateTimeConstraint(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('constraint', Node)
        self.signature.add_sig('date', Node)

    def simplify(self, top, mode):
        pnm, parent = self.get_parent()
        dt, c = self.get_input_views(['date', 'constraint'])
        if dt and dt.typename() == 'EQ':
            dt = dt.input_view('pos1')
        if c and c.typename() == 'EQ':
            c = c.input_view('pos1')
        if c and dt:
            s = 'DateTime?(date=%s, time=%s)' % (id_sexp(dt), id_sexp(c))
            d, e = self.call_construct(s, self.context)
            self.replace_self(d)
            return parent, e, mode
        return self, None, mode


class DateTimeFromDowConstraint(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('dowConstraint', Node)
        self.signature.add_sig('time', Node)

    def simplify(self, top, mode):
        pnm, parent = self.get_parent()
        tm, wd = self.get_input_views(['time', 'dowConstraint'])
        if wd and wd.typename() == 'EQ':
            wd = wd.input_view('pos1')
        if tm and wd:
            ns = [i.typename() for i in self.topological_order()]
            if 'NOT' in ns or 'negate' in ns:
                s = 'AND(DateTime?(date=Date(dow=%s)), DateTime?(time=%s))' % (id_sexp(wd), id_sexp(tm))
            else:
                s = 'DateTime?(date=Date(dow=%s), time=%s)' % (id_sexp(wd), id_sexp(tm))
            d, e = self.call_construct(s, self.context)
            self.replace_self(d)
            return parent, e, mode
        return self, None, mode


class DeleteCommitEventWrapper(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('event', Node)
        self.signature.add_sig('sugg', Event)  # new param
        self.signature.add_sig('confirm', Bool)  # new param

    def simplify(self, top, mode):
        pnm, parent = self.get_parent()
        if 'event' in self.inputs:
            ev = self.inputs['event']
            if ev.typename() == 'DeletePreflightEventWrapper' and 'id' in ev.inputs:
                i = ev.inputs['id']
                d, e = self.call_construct('DeleteEvent(%s)' % id_sexp(i), self.context)
                self.replace_self(d)
                return parent, e, mode
        return self, None, mode


class DeletePreflightEventWrapper(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('id', Node)


class Dinner(Node):
    def __init__(self):
        super().__init__()


class DoNotConfirm(Node):
    def __init__(self):
        super().__init__()


class DowOfWeekNew(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('dow', Node)
        self.signature.add_sig('week', Node)


class DowToDowOfWeek(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('day1', DayOfWeek)
        self.signature.add_sig('day2', DayOfWeek)
        self.signature.add_sig('week', Node)


class DummyRoot(Node):  # used as aux for simplify only
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)


class EQ(Qualifier):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)

    def simplify(self, top, mode):
        pnm, parent = self.get_parent()
        n = self.inputs['pos1']
        self.replace_self(n)
        return parent, None, mode


class Earliest(Node):
    def __init__(self):
        super().__init__()


class Early(Node):
    def __init__(self):
        super().__init__()


class EarlyDateRange(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('dateRange', Node)


class EarlyTimeRange(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('timeRange', Node)


class EndOfWorkDay(Node):
    def __init__(self):
        super().__init__()


class Evening(Node):
    def __init__(self):
        super().__init__()


def replace_sub_assign(nd):
    if nd.typename() == 'getattr':
        nm, nd1 = nd.get_input_views(['pos1', 'pos2'])
        if nd1 and nm and nd.typename()[0] == 'x':
            x = nd.context.get_assign(nd.typename())
            m = nm.dat
            if x and m in x.inputs:
                n = x.input_view(m)
                nd.replace_self(n)
                return n
    return nd


class EventAfterDateTime(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('dateTime', Node)
        self.signature.add_sig('event', Node)

    def simplify(self, top, mode):
        compose_ev_constr(self, top, mode)
        pnm, parent = self.get_parent()
        dt = self.input_view('dateTime')
        if dt:
            dt = replace_sub_assign(dt)
            d, e = self.call_construct('starts_at(GE(%s))' % id_sexp(dt), self.context)
            self.replace_self(d)
            return parent, e, mode
        return self, None, mode


class EventAllDayForDateRange(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('dateRange', Node)
        self.signature.add_sig('event', Event)

    def simplify(self, top, mode):
        compose_ev_constr(self, top, mode)
        pnm, parent = self.get_parent()
        dt = self.input_view('dateRange')
        if dt:
            dt = replace_sub_assign(dt)
            d, e = self.call_construct('spans_time(%s)' % id_sexp(dt), self.context)
            self.replace_self(d)
            return parent, e, mode
        return self, None, mode


class EventAllDayOnDate(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('date', Node)
        self.signature.add_sig('event', Event)

    def simplify(self, top, mode):
        compose_ev_constr(self, top, mode)
        pnm, parent = self.get_parent()
        dt = self.input_view('date')
        if dt:
            dt = replace_sub_assign(dt)
            d, e = self.call_construct('spans_time(%s)' % id_sexp(dt), self.context)
            self.replace_self(d)
            return parent, e, mode
        return self, None, mode


class EventAllDayStartingDateForPeriod(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('event', Event)
        self.signature.add_sig('period', Node)
        self.signature.add_sig('startDate', Node)

    def simplify(self, top, mode):
        compose_ev_constr(self, top, mode)
        pnm, parent = self.get_parent()
        pr, stdt = self.get_inputs(['period', 'startDate'])
        if pr and stdt:
            pr = replace_sub_assign(pr)
            stdt = replace_sub_assign(stdt)
            s = 'AND(has_duration(%s), starts_at(%s), starts_at(Time(hour=0, minute=0)))' % \
                (id_sexp(pr), id_sexp(stdt))
            d, e = self.call_construct(s, self.context)
            self.replace_self(d)
            return parent, e, mode
        return self, None, mode


class EventAtTime(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('event', Event)
        self.signature.add_sig('time', Node)

    def simplify(self, top, mode):
        compose_ev_constr(self, top, mode)
        pnm, parent = self.get_parent()
        dt = self.inputs['time']
        if dt:
            dt = replace_sub_assign(dt)
            d, e = self.call_construct('at_time(%s)' % id_sexp(dt), self.context)
            self.replace_self(d)
            return parent, e, mode
        return self, None, mode


class EventAttendance(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('comment', RespondComment)
        self.signature.add_sig('event', Node)
        self.signature.add_sig('response', ResponseStatusType)
        self.signature.add_sig('sendResponse', RespondShouldSend)


class EventBeforeDateTime(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('dateTime', Node)
        self.signature.add_sig('event', Node)

    def simplify(self, top, mode):
        compose_ev_constr(self, top, mode)
        pnm, parent = self.get_parent()
        dt = self.inputs['dateTime']
        if dt:
            dt = replace_sub_assign(dt)
            d, e = self.call_construct('starts_at(LT(%s))' % id_sexp(dt), self.context)
            self.replace_self(d)
            return parent, e, mode
        return self, None, mode


class EventBetweenEvents(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('event', Node)
        self.signature.add_sig('event1', Node)
        self.signature.add_sig('event2', Node)

    def simplify(self, top, mode):
        compose_ev_constr(self, top, mode)
        pnm, parent = self.get_parent()
        ev1, ev2 = self.get_inputs(['event1', 'event2'])
        if ev1 and ev2:
            d, e = self.call_construct('AND(starts_at(GE(%s)), ends_at(LE(%s)))' % (id_sexp(ev1), id_sexp(ev2)),
                                       self.context)
            self.replace_self(d)
            return parent, e, mode
        return self, None, mode


class EventDuringRangeDateTime(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('event', Event)
        self.signature.add_sig('range', Node)

    def simplify(self, top, mode):
        compose_ev_constr(self, top, mode)
        pnm, parent = self.get_parent()
        dt = self.inputs['range']
        if dt:
            dt = replace_sub_assign(dt)
            d, e = self.call_construct('at_time(%s)' % id_sexp(dt), self.context)
            self.replace_self(d)
            return parent, e, mode
        return self, None, mode


class EventDuringRangeTime(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('event', Node)
        self.signature.add_sig('timeRange', Node)

    def simplify(self, top, mode):
        compose_ev_constr(self, top, mode)
        pnm, parent = self.get_parent()
        dt = self.inputs['timeRange']
        if dt:
            dt = replace_sub_assign(dt)
            d, e = self.call_construct('at_time(%s)' % id_sexp(dt), self.context)
            self.replace_self(d)
            return parent, e, mode
        return self, None, mode


class EventForRestOfToday(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('event', Event)

    def simplify(self, top, mode):
        compose_ev_constr(self, top, mode)
        pnm, parent = self.get_parent()
        d, e = self.call_construct('AND(starts_at(Now()), ends_at(Today()), ends_at(Time(hour=23, minute=59)))',
                                   self.context)
        self.replace_self(d)
        return parent, e, mode


class EventOnDate(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('date', Node)
        self.signature.add_sig('event', Node)

    def simplify(self, top, mode):
        compose_ev_constr(self, top, mode)
        pnm, parent = self.get_parent()
        dt = self.input_view('date')
        if dt:
            dt = replace_sub_assign(dt)
            d, e = self.call_construct('starts_at(%s)' % id_sexp(dt), self.context)
            self.replace_self(d)
            return parent, e, mode
        return self, None, mode


class EventOnDateAfterTime(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('date', Node)
        self.signature.add_sig('event', Event)
        self.signature.add_sig('time', Node)

    def simplify(self, top, mode):
        compose_ev_constr(self, top, mode)
        pnm, parent = self.get_parent()
        dt, tm = self.get_input_views(['date', 'time'])
        if dt and tm:
            dt = replace_sub_assign(dt)
            tm = replace_sub_assign(tm)
            d, e = self.call_construct('AND(starts_at(%s), starts_at(GT(%s)))' % (id_sexp(dt), id_sexp(tm)), self.context)
            self.replace_self(d)
            return parent, e, mode
        return self, None, mode


class EventOnDateBeforeTime(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('date', Node)
        self.signature.add_sig('event', Node)
        self.signature.add_sig('time', Node)

    def simplify(self, top, mode):
        compose_ev_constr(self, top, mode)
        pnm, parent = self.get_parent()
        dt, tm = self.get_input_views(['date', 'time'])
        if dt and tm:
            dt = replace_sub_assign(dt)
            tm = replace_sub_assign(tm)
            d, e = self.call_construct('AND(starts_at(%s), starts_at(LT(%s)))' % (id_sexp(dt), id_sexp(tm)), self.context)
            self.replace_self(d)
            return parent, e, mode
        return self, None, mode


class EventOnDateFromTimeToTime(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('date', Node)
        self.signature.add_sig('event', Event)
        self.signature.add_sig('time1', Node)
        self.signature.add_sig('time2', Node)

    def simplify(self, top, mode):
        compose_ev_constr(self, top, mode)
        pnm, parent = self.get_parent()
        dt, tm1, tm2 = self.get_input_views(['date', 'time1', 'time2'])
        if dt and tm1 and tm2:
            dt = replace_sub_assign(dt)
            tm1 = replace_sub_assign(tm1)
            tm2 = replace_sub_assign(tm2)
            d, e = self.call_construct('AND(starts_at(%s), starts_at(%s), ends_at(%s))' %
                                       (id_sexp(dt), id_sexp(tm1), id_sexp(tm2)), self.context)
            self.replace_self(d)
            return parent, e, mode
        return self, None, mode


class EventOnDateTime(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('dateTime', Node)
        self.signature.add_sig('event', Event)

    def simplify(self, top, mode):
        compose_ev_constr(self, top, mode)
        pnm, parent = self.get_parent()
        dt = self.input_view('dateTime')
        if dt:
            dt = replace_sub_assign(dt)
            d, e = self.call_construct('at_time(%s)' % id_sexp(dt), self.context)
            self.replace_self(d)
            return parent, e, mode
        return self, None, mode


class EventOnDateWithTimeRange(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('event', Node)
        self.signature.add_sig('timeRange', Node)
        self.signature.add_sig('date', Node)

    def simplify(self, top, mode):
        compose_ev_constr(self, top, mode)
        pnm, parent = self.get_parent()
        dt, tm = self.get_input_views(['date', 'timeRange'])
        if tm:
            tm = replace_sub_assign(tm)
            if dt:
                dt = replace_sub_assign(dt)
                d, e = self.call_construct('AND(starts_at(%s), at_time(%s))' % (id_sexp(dt), id_sexp(tm)), self.context)
            else:
                d, e = self.call_construct('at_time(%s)' % id_sexp(tm), self.context)
            self.replace_self(d)
            return parent, e, mode
        return self, None, mode


class EventRescheduled(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('event', Event)


class EventSometimeOnDate(Node):  # what's the difference between this and EventOnDate?
    def __init__(self):
        super().__init__()
        self.signature.add_sig('date', Node)
        self.signature.add_sig('event', Event)

    def simplify(self, top, mode):
        compose_ev_constr(self, top, mode)
        pnm, parent = self.get_parent()
        dt = self.input_view('date')
        if dt:
            dt = replace_sub_assign(dt)
            d, e = self.call_construct('at_time(%s)' % id_sexp(dt), self.context)
            self.replace_self(d)
            return parent, e, mode
        return self, None, mode


class Execute(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('intension', Node)
        self.signature.add_sig('nonEmptyBase', Node)

    def simplify(self, top, mode):
        pnm, parent = self.get_parent()
        if parent.typename() == 'Let':
            path, names = self.get_input_path(':refer.:extensionConstraint.:RecipientWithNameLike.:PersonName')
            if path and path[-1].dat:
                self.replace_self(path[-1].inputs['pos1'])
                return parent, None, mode

        if 'intension' in self.inputs and self.inputs['intension'].typename() == 'ConfirmAndReturnAction':
            self.print_tree(parent, with_id=False)
            d, e = self.call_construct('AcceptSuggestion()', self.context)
            self.replace_self(d)
            return parent, None, mode
        path, names = self.get_input_path(':refer.:extensionConstraint.pos1')
        if path:
            d, e = self.call_construct('refer(%s)' % id_sexp(path[-1]), self.context)
            self.replace_self(d)
            return parent, e, mode
        # remove all Execute?
        if 'intension' in self.inputs:
            self.replace_self(self.inputs['intension'])
            return parent, None, mode
        return self, None, mode


class FenceAggregation(Node):
    def __init__(self):
        super().__init__()


class FenceAttendee(Node):
    def __init__(self):
        super().__init__()


class FenceComparison(Node):
    def __init__(self):
        super().__init__()


class FenceConditional(Node):
    def __init__(self):
        super().__init__()


class FenceConferenceRoom(Node):
    def __init__(self):
        super().__init__()


class FenceDateTime(Node):
    def __init__(self):
        super().__init__()


class FenceGibberish(Node):
    def __init__(self):
        super().__init__()


class FenceMultiAction(Node):
    def __init__(self):
        super().__init__()


class FenceNavigation(Node):
    def __init__(self):
        super().__init__()


class FenceOther(Node):
    def __init__(self):
        super().__init__()


class FencePeopleQa(Node):
    def __init__(self):
        super().__init__()


class FencePlaces(Node):
    def __init__(self):
        super().__init__()


class FenceRecurring(Node):
    def __init__(self):
        super().__init__()


class FenceReminder(Node):
    def __init__(self):
        super().__init__()


class FenceScope(Node):
    def __init__(self):
        super().__init__()


class FenceSpecify(Node):
    def __init__(self):
        super().__init__()


class FenceSwitchTabs(Node):
    def __init__(self):
        super().__init__()


class FenceTeams(Node):
    def __init__(self):
        super().__init__()


class FenceTriviaQa(Node):
    def __init__(self):
        super().__init__()


class FenceWeather(Node):
    def __init__(self):
        super().__init__()


class FindEventWrapperWithDefaults(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('constraint', Node)

    def simplify(self, top, mode):
        if 'constraint' in self.inputs:  # simply change node type -- could just map name in simplify_exp...
            n = self.inputs['constraint']
            d, e = self.simplify_rename('FindEvents', {'constraint': posname(1)})
            return n, e, mode
        return self, None, mode


class FindLastEvent(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('constraint', Node)


class FindManager(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node, alias='recipient')  # new param

    def simplify(self, top, mode):
        rcp = self.input_view('recipient')
        nd = get_person(rcp)
        if nd:
            self.replace_input('recipient', nd)
            return self, None, mode

        path, names = self.get_input_path(':refer.:RecipientWithNameLike.pos1')
        if path:
            self.replace_input('recipient', path[-1])
            return self, None, mode
        path, names = self.get_input_path(':Execute.:refer.:extensionConstraint.:RecipientWithNameLike.name')
        if path:
            # p = follow_assign(path[-1])
            p = path[-1]
            if p.typename() == 'PersonName':
                p = p.inputs['pos1']
            self.replace_input('recipient', p)
            return self, None, mode
        path, names = self.get_input_path(':Execute.:refer.:extensionConstraint.pos1')
        if path:
            p = path[-1]
            if p.typename() == 'PersonName':
                p = p.inputs['pos1']
            self.replace_input('recipient', p)
            return self, None, mode

        return self, None, mode


class FindNumNextEvent(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('constraint', Node)
        self.signature.add_sig('number', [Number, Int])

    def simplify(self, top, mode):
        float_input_to_int(self, 'number')
        return self, None, mode


class FindPlace(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('keyphrase', Node)


class FindPlaceAtHere(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('place', [LocationKeyphrase, Str])
        self.signature.add_sig('radiusConstraint', Node)


class FindPlaceMultiResults(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('place', Node)


class FindReports(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('recipient', Node)


class FindTeamOf(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('recipient', Node)

    def simplify(self, top, mode):
        pnm, parent = self.get_parent()
        rcp = self.input_view('recipient')
        nd = get_person(rcp)
        if nd:
            if parent.typename() not in ['with_attendee', 'avoid_attendee']:
                d, e = self.call_construct('with_attendee(%s)' % id_sexp(nd), self.context)
            else:
                d = nd
            self.replace_input('recipient', d)
            return self, None, mode

        path, names = self.get_input_path(':Execute.:refer.:extensionConstraint')
        if path:
            if 'pos1' in path[-1].inputs and path[-1].inputs['pos1'].typename() == 'RecipientWithNameLike':
                name, cnstr = path[-1].inputs['pos1'].get_input_views(['name', 'constraint'])
                if cnstr and len(cnstr.inputs) == 0 and name:
                    p = name.input_view('pos1') if name.typename() == 'PersonName' else name
                    self.replace_input('recipient', p)
                    return self, None, mode
        return self, None, mode


class ForwardEventWrapper(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('event', Node)
        self.signature.add_sig('recipients', Node)

    def simplify(self, top, mode):
        pnm, parent = self.get_parent()
        rcp, ev = self.get_input_views(['recipients', 'event'])
        changed = False
        if ev and rcp and rcp.typename() == 'append':
            for i in list(rcp.inputs.keys()):
                n = rcp.input_view(i)
                if n.typename() == 'List':
                    p = n.input_view('pos1')
                    if p and len(p.inputs) == 0 and len(rcp.inputs) > 1:
                        rcp.disconnect_input(i)
                        changed = True
                elif n.typename() == 'refer':
                    path, names = n.get_input_path(':Recipient.:LIKE.pos1')
                    if path:
                        d, e = self.call_construct('with_attendee(%s)' % id_sexp(path[-1]), self.context)
                        n.replace_self(d)
                        changed = True
            if changed:
                d, e = rcp.simplify_rename('AND')
                n, e = self.call_construct('ForwardEvent(event=%s, constraint=%s)' % (id_sexp(ev), id_sexp(d)),
                                           self.context)
                self.replace_self(n)
                return parent, None, mode

        return self, None, mode


class ForwardEvent(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('event', Node)
        self.signature.add_sig('constraint', Node)


class FullMonthofLastMonth(Node):
    def __init__(self):
        super().__init__()


class FullMonthofMonth(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node, alias='month')
        self.signature.add_sig('year', Node)

    def simplify(self, top, mode):
        if 'month' in self.inputs:
            float_input_to_int(self, 'year')
            month = self.inputs['month']
            if month.typename() == 'Month' and month.dat:
                self.context.replace_assign(month, month.inputs['pos1'])  # to be safe
                self.replace_input('month', month.inputs['pos1'])
        return self, None, mode


class FullMonthofPreviousMonth(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Month, alias='month')


class FullYearofYear(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node, alias='year')

    def simplify(self, top, mode):
        float_input_to_int(self, 'pos1')
        return self, None, mode


class Future(Node):
    def __init__(self):
        super().__init__()


class GenericPleasantry(Node):
    def __init__(self):
        super().__init__()


class GreaterThanFromStructDateTime(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('dateTimeConstraint', Node)

    def simplify(self, top, mode):
        pnm, parent = self.get_parent()
        dt = self.inputs['dateTimeConstraint']
        if dt:
            if dt.typename() == 'EQ':
                dt = dt.input_view('pos1')
            s = 'GT(%s)' % id_sexp(dt)
            d, e = self.call_construct(s, self.context)
            self.replace_self(d)
            return parent, e, mode
        return self, None, mode


class Here(Node):
    def __init__(self):
        super().__init__()


class HolidayYear(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('holiday', Node)
        self.signature.add_sig('year', Node)

    def simplify(self, top, mode):
        float_input_to_int(self, 'year')
        return self, None, mode


class HourMilitary(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', [Number, Int], alias='hours')

    def simplify(self, top, mode):
        float_input_to_int(self, 'pos1')
        return self, None, mode


class HourMinuteAm(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('hours', [Number, Int])
        self.signature.add_sig('minutes', [Number, Int])

    def simplify(self, top, mode):
        for i in ['hours', 'minutes']:
            float_input_to_int(self, i)
        return self, None, mode


class HourMinuteMilitary(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('hours', [Number, Int])
        self.signature.add_sig('minutes', [Number, Int])

    def simplify(self, top, mode):
        float_input_to_int(self, 'hours')
        float_input_to_int(self, 'minutes')
        return self, None, mode


class HourMinutePm(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('hours', [Number, Int])
        self.signature.add_sig('minutes', [Number, Int])
        self.signature.add_sig('hour', Int)  # new param
        self.signature.add_sig('minute', Int)  # new param

    def simplify(self, top, mode):
        for i in ['hours', 'minutes']:
            float_input_to_int(self, i)
        return self, None, mode


class IsBusy(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('eventCandidates', Node)


class IsCloudy(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node, alias='table')


class IsCold(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node, alias='table')


class IsFree(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('eventCandidates', Node)


class IsHighUV(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node, alias='table')


class IsHot(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node, alias='table')


class IsRainy(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node, alias='table')


class IsSnowy(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node, alias='table')


class IsStormy(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node, alias='table')


class IsSunny(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node, alias='table')


class IsTeamsMeeting(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('event', Node)


class IsWindy(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node, alias='table')


class LT(Qualifier):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)


class LastDayOfMonth(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('month', Node)


class LastDuration(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('periodDuration', PeriodDuration)


class LastPeriod(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('period', Node)


class LastWeekNew(Node):  # date range - last week
    def __init__(self):
        super().__init__()


class LastWeekendOfMonth(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('month', Node)


class LastYear(Node):
    def __init__(self):
        super().__init__()


class Late(Node):
    def __init__(self):
        super().__init__()


class LateAfternoon(Node):
    def __init__(self):
        super().__init__(TimeRange)


# later in the week/month / last part of the year...
class LateDateRange(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('dateRange', Node)


class LateMorning(Node):
    def __init__(self):
        super().__init__()


class LateTimeRange(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('timeRange', Node)


class Later(Node):
    def __init__(self):
        super().__init__()


class Latest(Node):
    def __init__(self):
        super().__init__()


class LessThanFromStructDateTime(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('dateTimeConstraint', Node)

    def simplify(self, top, mode):
        pnm, parent = self.get_parent()
        dt = self.inputs['dateTimeConstraint']
        if dt:
            if dt.typename() == 'EQ':
                dt = dt.input_view('pos1')
            s = 'LT(%s)' % id_sexp(dt)
            d, e = self.call_construct(s, self.context)
            self.replace_self(d)
            return parent, e, mode
        return self, None, mode


class List(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)


class Lunch(Node):
    def __init__(self):
        super().__init__()


class MD(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('month', Node)
        self.signature.add_sig('day', [Number, Int])

    def simplify(self, top, mode):
        float_input_to_int(self, 'day')
        self.cut_cast('month', 'Month')

        return self, None, mode


class MDY(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('month', Node)
        self.signature.add_sig('day', [Number, Int])
        self.signature.add_sig('year', Node)

    def simplify(self, top, mode):
        float_input_to_int(self, 'day')
        float_input_to_int(self, 'month')
        float_input_to_int(self, 'year')
        return self, None, mode


class Midnight(Node):
    def __init__(self):
        super().__init__()


class MonthDayToDay(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('month', Node)
        self.signature.add_sig('num1', [Number, Int])
        self.signature.add_sig('num2', Node)

    def simplify(self, top, mode):
        float_input_to_int(self, 'num1')
        float_input_to_int(self, 'num2')
        return self, None, mode


class Morning(Node):
    def __init__(self):
        super().__init__()


class NeedsJacket(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node, alias='table')


def proc_slot(n, old=None, role=None):
    if n.typename() == 'AND':
        for i in n.inputs:
            nd = n.input_view(i)
            old, role = proc_slot(nd, old, role)
    elif n.typename() == 'extensionConstraint':
        old = n.input_view('pos1')
    elif n.constraint_level == 2:
        old = n
    elif n.typename() == 'roleConstraint':
        m = n.input_view('pos1')
        if m.dat:
            role = m
        else:
            if m.typename() == 'append':
                path, names = m.get_input_path_by_type('List.Path')
                path2, names2 = m.get_input_path_by_type('Path')
                if path and len(path[-1].inputs) == 0 and path2 and path2[-1].input_view('pos1') and \
                        path2[-1].input_view('pos1').typename() in ['Str', String]:
                    role = path2[-1].input_view('pos1')
    return old, role


# NewClobber is a version of revise, which does NOT do "smart" constraint merging/pruning - it overwrites the current
# constraints.
# It is used for ALL types of functions (not just Event functions).
# For Event functions, it behaves the same as ModifyEventRequest when applied to fields which allow just one positive
#   value (e.g. location and subject), but for attendee it behaves differently.
#   not sure what it does for time - e.g. specifying start just replaces start, or the whole time slot...?
# When applied to other functions - we can translate it to revise(..., newMode=overwrite), but need to make sure
#  that input names match...
# in order to know if it's being applied top an Event function or not, we need to look at the previous turn!
#   not very nice, but here is the only place we do that. It corresponds to a fairly drastic change in annotation.
class NewClobber(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('intension', Node)
        self.signature.add_sig('slotConstraint', Node)
        self.signature.add_sig('value', Node)

    def simplify(self, top, mode):
        pnm, parent = self.get_parent()
        ins, slt, val = self.get_input_views(['intension', 'slotConstraint', 'value'])
        if ins and slt and val:
            nval = None
            old, role = proc_slot(slt)
            if val.typename() == 'intension' and 'pos1' in val.inputs:
                nval = val.input_view('pos1')
                if nval.typename() == 'EQ':
                    nval = nval.input_view('pos1')
            if nval:
                ev_func = False
                if self.context.prev_nodes:
                    if self.context.prev_nodes == 'EventFunc':  # for debugging single expression
                        ev_func = False
                    else:
                        nds = self.context.prev_nodes[0][0].topological_order()
                        ev_func = any([i.typename() in EVENT_NODES + ['Event'] for i in nds])
                if ev_func:
                    s = ''
                    if role and role.dat:
                        r = role.dat
                        if r == 'subject':
                            s = 'ModifyEventRequest(has_subject(%s), clobber=True)' % id_sexp(nval)
                        elif r == 'location':
                            s = 'ModifyEventRequest(has_location(%s), clobber=True)' % id_sexp(nval)
                        elif r == 'recipient':
                            s = 'ModifyEventRequest(with_attendee(%s), clobber=True)' % id_sexp(nval)
                        elif r == 'start':
                            s = 'ModifyEventRequest(starts_at(%s), clobber=True)' % id_sexp(nval)
                        elif r == 'end':
                            s = 'ModifyEventRequest(ends_at(%s), clobber=True)' % id_sexp(nval)
                        elif r == 'duration':
                            s = 'ModifyEventRequest(has_duration(%s), clobber=True)' % id_sexp(nval)
                    if not s and old and len(old.inputs) == 0:
                        o = old.typename()
                        if o == 'Recipient':
                            s = 'ModifyEventRequest(with_attendee(%s), clobber=True)' % id_sexp(nval)

                    s = s if s else 'ModifyEventRequest(%s, clobber=True)' % id_sexp(nval)
                else:
                    if (old and old.typename in ['Recipient', 'Attendee']) or \
                            'RecipientWithNameLike' in [i.typename() for i in val.topological_order()]:
                        nd = get_person(nval)
                        if nd:
                            func = 'RecipientWithNameLike'  # 'with_attendee'
                            nval, e = self.call_construct('%s(%s)' % (func, id_sexp(nd)), self.context)
                    prms = []
                    if role:
                        prms.append('role=%s' % id_sexp(role))
                    if old:
                        prms.append('old=%s' % id_sexp(old))
                    prms.append('new=%s' % id_sexp(nval))

                    prms.append('newMode=overwrite')
                    s = 'revise(' + ','.join(prms) + ')'
                d, e = self.call_construct(s, self.context)
                self.replace_self(d)
                return parent, None, mode

        return self, None, mode


class NextDOW(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node, alias='dow')

    def simplify(self, top, mode):
        self.cut_cast('dow', 'DayOfWeek')

        return self, None, mode


class NextHolidayFromToday(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('holiday', Holiday)


class NextMonth(Node):
    def __init__(self):
        super().__init__(DateTimeRange)


class NextPeriod(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('period', Node)


class NextPeriodDuration(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('periodDuration', PeriodDuration)
        self.signature.add_sig('period', Period)  # new param


class NextTime(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('time', Node)


class NextWeekList(Node):
    def __init__(self):
        super().__init__()


class NextWeekend(Node):
    def __init__(self):
        super().__init__(DateTimeRange)


class NextYear(Node):
    def __init__(self):
        super().__init__(DateTimeRange)


class Night(Node):
    def __init__(self):
        super().__init__(TimeRange)


class Noon(Node):
    def __init__(self):
        super().__init__(TimeRange)


class Now(Node):
    def __init__(self):
        super().__init__(DateTime)


class NumberAM(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', [Number, Int], alias='number')

    def simplify(self, top, mode):
        float_input_to_int(self, 'number')
        return self, None, mode


class NumberInDefaultTempUnits(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('number', [Number, Int])

    def simplify(self, top, mode):
        float_input_to_int(self, 'number')
        return self, None, mode


class NumberPM(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', [Number, Int], alias='number')

    def simplify(self, top, mode):
        float_input_to_int(self, 'pos1')
        return self, None, mode


def simplify(self, top, mode):
    if 'number' in self.inputs and isinstance(self.inputs['number'].dat, float):
        self.inputs['number'].data = int(self.inputs['number'].dat)
    return self, None, mode


class NumberWeekFromEndOfMonth(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('month', Month)
        self.signature.add_sig('number', [Number, Int])

    def simplify(self, top, mode):
        float_input_to_int(self, 'number')
        return self, None, mode


class NumberWeekOfMonth(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('month', Node)
        self.signature.add_sig('number', [Number, Int])

    def simplify(self, top, mode):
        float_input_to_int(self, 'number')
        return self, None, mode


# TODO: need to be simplified to something
class OnDateAfterTime(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('date', Node)
        self.signature.add_sig('time', Node)


# TODO: need to be simplified to something
class OnDateBeforeTime(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('date', Node)
        self.signature.add_sig('time', Node)


class PeriodBeforeDate(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('date', Node)
        self.signature.add_sig('period', Node)


class PeriodDurationBeforeDateTime(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('dateTime', Node)
        self.signature.add_sig('periodDuration', PeriodDuration)


# todo - get rid of person - have only recipient - simply remove this node
#  but we still need to decide on format!
# if we just skip, the we may get things like 'refer(recipient?(name=LIKE(x)))' which works, but does not quite
# match the modifier style simplifications - is there a way to avoid explicitly using refer?
class PersonFromRecipient(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('recipient', Node)

    def simplify(self, top, mode):
        pnm, parent = self.get_parent()
        rcp = self.input_view('recipient')

        # simply skip this node
        # self.replace_self(rcp)
        # return parent, None, mode

        if rcp.typename() == 'with_attendee':
            return self, None, mode

        nd = get_person(rcp)
        if nd:
            d, e = self.call_construct('with_attendee(%s)' % id_sexp(nd), self.context)
            self.replace_input('recipient', d)
            return parent, e, mode

        path, names = self.get_input_path(':Execute.:refer.:extensionConstraint.:RecipientWithNameLike.name')
        if path:
            # we'll convert this to something else at transform time if needed
            s = id_sexp(path[-1].inputs['pos1']) if path[-1].typename() == 'PersonName' else id_sexp(path[-1])
            d, e = self.call_construct('with_attendee(%s)' % s, self.context)
            self.replace_input('recipient', d)
            return self, None, mode
        path, names = self.get_input_path(':RecipientFromRecipientConstraint.:RecipientWithNameLike.name')
        if path and 'constraint' in path[-2].inputs and len(path[-2].input_view('constraint').inputs) == 0:
            s = id_sexp(path[-1].inputs['pos1']) if path[-1].typename() == 'PersonName' else id_sexp(path[-1])
            d, e = self.call_construct('with_attendee(%s)' % s, self.context)
            self.replace_input('recipient', d)
            return self, None, mode
        return self, None, mode


class PersonOnTeam(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('person', Node)
        self.signature.add_sig('team', Node)


class PersonWithNameLike(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('constraint', Node)
        self.signature.add_sig('name', PersonName)


class PlaceDescribableLocation(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('place', Node)


class PlaceHasFeature(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('feature', PlaceFeature)
        self.signature.add_sig('place', Node)


class PleasantryAnythingElseCombined(Node):
    def __init__(self):
        super().__init__()


class PleasantryCalendar(Node):
    def __init__(self):
        super().__init__()


class QueryEventIntensionConstraint(Node):
    def __init__(self):
        super().__init__()


class RecipientAvailability(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('eventConstraint', Event)
        self.signature.add_sig('includingMe', Boolean)


class RecipientFromRecipientConstraint(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node, alias='constraint')

    def simplify(self, top, mode):
        _, parent = self.get_parent()
        if mode and 'modify_event' in mode:
            path, names = self.get_input_path(':RecipientWithNameLike.name')
            if path:
                p = path[-1]
                if parent.typename() in ['with_attendee', 'avoid_attendee']:
                    d = p.input_view('pos1') if p.typename() == 'PersonName' else p
                else:
                    s = id_sexp(p.input_view('pos1')) if p.typename() == 'PersonName' else id_sexp(p)
                    d, e = self.call_construct('with_attendee(%s)' % s, self.context)
                self.replace_self(d)
                return parent, None, mode

        return self, None, mode


class RecipientWithNameLike(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node, alias='name')
        self.signature.add_sig('constraint', Node)

    def simplify(self, top, mode):
        constr, name = self.get_inputs(['constraint', 'name'])
        pnm, parent = self.get_parent()
        if parent.typename() == 'Let':
            nd = get_person(self)
            if nd:
                self.replace_self(nd)
                return parent, None, mode

        if parent.typename() in ['refer']:
            if constr and name and constr.typename() == 'Recipient' and name.typename() == 'PersonName':
                # d, e = self.call_construct('Recipient?(name=LIKE(#%s))' % re.sub(' ', '_', name.dat), self.context)
                d, e = self.call_construct('Recipient?(name=LIKE(%s))' % name.dat, self.context)
                self.replace_self(d)
                return parent, e, mode
        if parent.typename() in ['with_attendee', 'without_attendee']:
            if constr and name and constr.typename() == 'Recipient' and name.typename() == 'PersonName':
                self.replace_self(name.input_view('pos1'))
                return parent, None, mode
        if constr and constr.typename() == 'Recipient' and len(constr.inputs) == 0:
            self.disconnect_input('constraint')
        constr = self.input_view('constraint')
        if not constr and name and parent.typename() == 'Let':
            p = name.inputs['pos1'] if name.typename() == 'PersonName' else name
            self.replace_self(p)
            return parent, None, mode
        return self, None, mode


class RepeatAgent(Node):
    def __init__(self):
        super().__init__()


# in the SM dataset, ReviseConstraint is used ONLY for Event functions. This is where we use modifiers with "smart"
# constraint merging/pruning.
class ReviseConstraint(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('rootLocation', Node)
        self.signature.add_sig('oldLocation', Node)
        self.signature.add_sig('new', Node)
        self.signature.add_sig('newConstraint', Node)
        self.signature.add_sig('oldConstraint', Node)

    def simplify(self, top, mode):
        pnm, parent = self.get_parent()
        root, old, new = self.get_inputs(['rootLocation', 'oldLocation', 'new'])
        if root:
            p1, n1 = root.get_input_path(':Path.pos1')
            if p1 and p1[-1].dat == 'output':
                self.disconnect_input('rootLocation')
                return parent, None, mode
        if old and new:
            if new.typename() == 'Event':
                if old.typename() in ['Event', 'UpdateEventIntensionConstraint',
                                      'QueryEventIntensionConstraint']:  # more checks needed?
                    d, e = self.call_construct('ModifyEventRequest(%s)' % id_sexp(new), self.context)
                    self.replace_self(d)
                    return parent, e, mode
            elif (old.typename() == 'Event' and old.constraint_level == 2) or \
                    old.typename() in ['Event', 'UpdateEventIntensionConstraint', 'QueryEventIntensionConstraint']:
                if new.typename() in EVENT_WITH_TIME:
                    d, e = self.call_construct('ModifyEventRequest(%s)' % id_sexp(new), self.context)
                    self.replace_self(d)
                    return parent, e, mode
        return self, None, mode


class SeasonFall(Node):
    def __init__(self):
        super().__init__(DateTimeRange)


class SeasonSpring(Node):
    def __init__(self):
        super().__init__()


class SeasonSummer(Node):
    def __init__(self):
        super().__init__(DateTimeRange)


class SeasonWinter(Node):
    def __init__(self):
        super().__init__(DateTimeRange)


class SetOtherOrganizer(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('eventConstraint', Event)
        self.signature.add_sig('recipient', Node)


class Sub(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)
        self.signature.add_sig('pos2', [Number, Int])

    def simplify(self, top, mode):
        float_input_to_int(self, 'pos2')
        return self, None, mode


class ThisWeek(Node):
    def __init__(self):
        super().__init__(DateTimeRange)


class ThisWeekend(Node):
    def __init__(self):
        super().__init__(DateTimeRange)


class Time(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('hour', Int)  # new param
        self.signature.add_sig('minute', Int)  # new param

    def simplify(self, top, mode):
        float_input_to_int(self, 'hour')
        float_input_to_int(self, 'minute')
        return self, None, mode


class TimeAfterDateTime(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('dateTime', Node)
        self.signature.add_sig('time', Node)

    # replace this by just the time is USUALLY ok (as it's typically used to assert the logic that end time > start time),
    # but in general it's too aggressive.
    # A preferable option may be to keep TimeAfterDateTime, and replace it dynamically in trans_simp -
    #   this could account for cases where just date or just time are given
    def simplify(self, top, mode):
        pnm, parent = self.get_parent()
        dt, tm = self.get_inputs(['dateTime', 'time'])
        if dt and tm:
            d, e = self.call_construct('AND(GE(%s), %s)' %(id_sexp(dt), id_sexp(tm)), self.context)
            #self.replace_self(tm)  # too aggressive (in a few cases)
            self.replace_self(d)
            return parent, None, mode
        return self, None, mode


class TimeAround(Node):
    def __init__(self):
        super().__init__(DateTimeRange)
        self.signature.add_sig('pos1', Node, alias='time')


class TimeBeforeDateTime(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('dateTime', Node)
        self.signature.add_sig('time', Node)


class TimeSinceEvent(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node, alias='event')


class TimeToTime(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('time1', Node)
        self.signature.add_sig('time2', Node)


class Today(Node):
    def __init__(self):
        super().__init__(DateTimeRange)


class Tomorrow(Node):
    def __init__(self):
        super().__init__(DateTimeRange)


class TopResult(Node):
    def __init__(self):
        super().__init__()


class UpdateCommitEventWrapper(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('event', Node)
        self.signature.add_sig('sugg', Event)  # new param
        self.signature.add_sig('confirm', Bool)  # new param

    def simplify(self, top, mode):
        pnm, parent = self.get_parent()
        if 'event' in self.inputs:
            ev = self.inputs['event']
            if ev.typename() == 'UpdatePreflightEventWrapper' and 'id' in ev.inputs and 'update' in ev.inputs:
                i, u = ev.inputs['id'], ev.inputs['update']
                d, e = self.call_construct('UpdateEvent(event=%s, constraint=%s)' % (id_sexp(i), id_sexp(u)), self.context)
                self.replace_self(d)
                return parent, e, mode
        return self, None, mode


class UpdateEventIntensionConstraint(Node):
    def __init__(self):
        super().__init__()


class UpdatePreflightEventWrapper(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('id', Node)
        self.signature.add_sig('update', Node)
        self.signature.add_sig('event', Node)  # new param
        self.signature.add_sig('constraint', Event)  # new param

    def simplify(self, top, mode):
        path = self.get_input_path_by_name('id.pos1')
        if path and path[0].typename() == 'getattr' and path[1].dat and path[1].dat == 'id' and \
                'pos2' in path[0].inputs:
            self.replace_input('id', path[0].inputs['pos2'])
        return self, None, mode


class UserPauseResponse(Node):
    def __init__(self):
        super().__init__()


class WeatherAggregate(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('property', WeatherProp)
        self.signature.add_sig('quantifier', WeatherQuantifier)
        self.signature.add_sig('table', Node)


class WeatherForEvent(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node, alias='event')


class WeatherPleasantry(Node):
    def __init__(self):
        super().__init__()


class WeatherQueryApi(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('place', Node)
        self.signature.add_sig('time', Node)

    def simplify(self, top, mode):
        t = self.input_view('time')
        if t and t.typename() == 'DateTime' and t.constraint_level == 1 and len(t.inputs) == 1:
            nm = list(t.inputs.keys())[0]
            n = t.input_view(nm)
            n = n.get_op_object()
            if n.outypename() in TIME_NODE_NAMES:
                self.disconnect_input('time')
                n.connect_in_out('time', self)
        return self, None, mode


class WeekOfDateNew(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('date', Node)


class Weekdays(Node):
    def __init__(self):
        super().__init__()


class Weekend(Node):
    def __init__(self):
        super().__init__()


class WeekendOfDate(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('date', Node)


class WeekendOfMonth(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('month', Month)
        self.signature.add_sig('num', [Number, Int])

    def simplify(self, top, mode):
        float_input_to_int(self, 'num')
        return self, None, mode


class WhenProperty(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('property', WeatherProp)
        self.signature.add_sig('quantifier', WeatherQuantifier)
        self.signature.add_sig('wt', Node)


class WillRain(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node, alias='table')


class WillSleet(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node, alias='table')


class WillSnow(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('table', Node)
        self.signature.add_sig('place', GeoCoords)  # new param
        self.signature.add_sig('time', DateTime)  # new param


class Yesterday(Node):
    def __init__(self):
        super().__init__()


class Yield(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node, alias='output')

    def simplify(self, top, mode):
        pnm, parent = self.get_parent()
        p1 = self.inputs['output']
        if p1:
            if not parent:
                self.disconnect_input('output')
                return p1, None, mode
            elif parent.typename() == 'DummyRoot':
                self.disconnect_input('output')
                self.replace_self(p1)
                return parent, None, mode
            elif parent.typename() == 'do' and parent.max_pos_input() == posname_idx(
                    pnm):  # yield is last in multi exps
                self.replace_self(p1)
                return parent, None, mode
        return self, None, mode


class addDurations(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)
        self.signature.add_sig('pos2', Node)


class addPeriodDurations(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', PeriodDuration)
        self.signature.add_sig('pos2', PeriodDuration)


class addPeriods(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)
        self.signature.add_sig('pos2', Node)


class adjustByDuration(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)
        self.signature.add_sig('pos2', Node)


class adjustByPeriod(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)
        self.signature.add_sig('pos2', Node)


class adjustByPeriodDuration(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)
        self.signature.add_sig('pos2', Node)


class allows(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)
        self.signature.add_sig('pos2', Node)

    def simplify(self, top, mode):
        p1, p2 = self.get_input_views(['pos1', 'pos2'])
        if p1 and p2 and p2.typename() == 'getattr':
            nm = p2.input_view('pos1').dat
            if nm == 'attendees':
                self.replace_input('pos2', p2.input_view('pos2'))
        return self, None, mode


class alwaysTrueConstraintConstraint(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)

    def simplify(self, top, mode):
        pnm, parent = self.get_parent()
        if 'pos1' in self.inputs:
            inp = self.inputs['pos1']
            if parent.typename() == 'refer' and inp.typename() == inp.outypename() and inp.constraint_level == 0:
                inp.constraint_level = 2
                self.replace_self(inp)
                return parent, None, mode
        return self, None, mode


class andConstraint(Aggregator):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)
        self.signature.add_sig('pos2', Node)

    def pre_simplify(self, top, mode):
        d, e = self.simplify_rename('AND')
        d.simplify(None, None)
        return self, e, mode


class append(Aggregator):
    def __init__(self):
        super().__init__()

    def simplify(self, top, mode):
        ms = [i for i in list(self.inputs.keys()) if is_pos(i)]
        ns = [self.inputs[i] for i in ms]
        na = [n.typename() == 'append' for n in ns]
        if any(na):
            if len(ms) > 1:
                objs = []
                for i in range(len(na)):
                    s, a = ns[i], na[i]
                    o = [s.inputs[j] for j in s.inputs] if a else [s]
                    if a:
                        s.disconnect_input_nodes(o)
                    self.disconnect_input(ms[i])
                    objs += o
                s = 'append(%s)' % ','.join([id_sexp(o) for o in objs])
                d, e = self.call_construct(s, self.context)
                self.replace_self(d)
                return d, e, mode
            else:
                pnm, parent = self.get_parent()
                self.replace_self(ns[0])
                return parent, None, mode
        return self, None, mode


class callFindManager(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)


class cursorNext(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)


class cursorPrevious(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)


class do(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)
        self.signature.add_sig('pos2', Node)
        self.signature.add_sig('pos3', Node)
        self.signature.add_sig('pos4', Node)


class exists(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)


class extensionConstraint(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)


class fEQ(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)
        self.signature.add_sig('pos2', Node)


class fGE(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)
        self.signature.add_sig('pos2', Node)


class fGT(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)
        self.signature.add_sig('pos2', Node)


class fLE(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)
        self.signature.add_sig('pos2', Node)


class fLT(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)
        self.signature.add_sig('pos2', Node)


class fNOT(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)


class false(Node):
    def __init__(self):
        super().__init__()


class get(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)
        self.signature.add_sig('pos2', Path)


class getattr(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Str)
        self.signature.add_sig('pos2', Node)

    def pre_simplify(self, top, mode):
        # remove some unnecessary getattr's - simplified signatures
        pnm, parent = self.get_parent()
        nm, nd = self.get_inputs(['pos1', 'pos2'])
        if nm and nd:
            nm, nd = self.inputs['pos1'], self.inputs['pos2']
            # instead of returning a QueryEventResponse wrapping results, we just return the results (possibly as SET)
            if nd.typename() == 'FindEventWrapperWithDefaults' and nm.dat == 'results':
                self.replace_self(nd)
                return parent, None, mode
        return self, None, mode


class inCelsius(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)


class inFahrenheit(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)


class inInches(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)


class inKilometersPerHour(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)


class inUsMilesPerHour(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)


class intension(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)


class joinEventCommand(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)


class setx0(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)

    def exec(self, all_nodes=None, goals=None):
        self.context.assign['x0'] = self.inputs['pos1']


class setx1(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)

    def exec(self, all_nodes=None, goals=None):
        self.context.assign['x1'] = self.inputs['pos1']


class setx2(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)

    def exec(self, all_nodes=None, goals=None):
        self.context.assign['x2'] = self.inputs['pos1']


class setx3(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)

    def exec(self, all_nodes=None, goals=None):
        self.context.assign['x3'] = self.inputs['pos1']


class setx4(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)

    def exec(self, all_nodes=None, goals=None):
        self.context.assign['x4'] = self.inputs['pos1']


class setx5(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)

    def exec(self, all_nodes=None, goals=None):
        self.context.assign['x5'] = self.inputs['pos1']


class setx6(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)

    def exec(self, all_nodes=None, goals=None):
        self.context.assign['x6'] = self.inputs['pos1']


class x0(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)

    def exec(self, all_nodes=None, goals=None):
        if connect_assign:
            self.set_result(self.context.assign['x0'])

    def simplify(self, top, mode):
        if 'x0' in self.context.assign:
            return self.context.assign['x0'], None, mode
        return self, None, mode


class x1(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)

    def exec(self, all_nodes=None, goals=None):
        if connect_assign:
            self.set_result(self.context.assign['x1'])

    def simplify(self, top, mode):
        if 'x1' in self.context.assign:
            return self.context.assign['x1'], None, mode
        return self, None, mode


class x2(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)

    def exec(self, all_nodes=None, goals=None):
        if connect_assign:
            self.set_result(self.context.assign['x2'])

    def simplify(self, top, mode):
        if 'x2' in self.context.assign:
            return self.context.assign['x2'], None, mode
        return self, None, mode


class x3(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)

    def exec(self, all_nodes=None, goals=None):
        if connect_assign:
            self.set_result(self.context.assign['x3'])

    def simplify(self, top, mode):
        if 'x3' in self.context.assign:
            return self.context.assign['x3'], None, mode
        return self, None, mode


class x4(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)

    def exec(self, all_nodes=None, goals=None):
        if connect_assign:
            self.set_result(self.context.assign['x4'])

    def simplify(self, top, mode):
        if 'x4' in self.context.assign:
            return self.context.assign['x4'], None, mode
        return self, None, mode


class x5(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)

    def exec(self, all_nodes=None, goals=None):
        if connect_assign:
            self.set_result(self.context.assign['x5'])

    def simplify(self, top, mode):
        if 'x5' in self.context.assign:
            return self.context.assign['x5'], None, mode
        return self, None, mode


class x6(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)

    def exec(self, all_nodes=None, goals=None):
        if connect_assign:
            self.set_result(self.context.assign['x6'])

    def simplify(self, top, mode):
        if 'x6' in self.context.assign:
            return self.context.assign['x6'], None, mode
        return self, None, mode


class let(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)
        self.signature.add_sig('pos2', Node)

    def simplify(self, top, mode):
        if 'pos1' in self.inputs and 'pos2' in self.inputs:
            p1, p2 = self.input_view('pos1'), self.input_view('pos2')
            if p1.typename() == 'SET' or p1.typename().startswith('setx'):
                inps = [p1.inputs[i] for i in p1.inputs] if p1.typename() == 'SET' else [p1]
                s = ['Let(%s, %s)' % (i.typename()[3:], id_sexp(i.inputs['pos1'])) for i in inps]
                for i in list(p1.inputs.keys()):
                    p1.disconnect_input(i)
                self.disconnect_input('pos2')
                d, e = self.call_construct('do(%s, %s)' % (','.join(s), id_sexp(p2)), self.context)
                pnm, parent = self.get_parent()
                self.replace_self(d)
                return parent, e, mode
        return self, None, mode


class Let(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Str)
        self.signature.add_sig('pos2', Node)


class listSize(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)
        self.signature.add_sig('pos2', Node)


class minBy(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)
        self.signature.add_sig('pos2', Path)


class negate(Qualifier):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)

    def pre_simplify(self, top, mode):
        d, e = self.simplify_rename('NOT')
        d.simplify(None, None)
        return self, e, mode

    def simplify(self, top, mode):
        pnm, parent = self.get_parent()
        if 'pos1' in self.inputs:
            n = self.inputs['pos1']
            d, e = self.call_construct('NOT(%s)' % id_sexp(n), self.context)
            self.replace_self(d)
            return parent, e, mode
        return self, None, mode


class nextDayOfMonth(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)
        self.signature.add_sig('pos2', [Number, Int])

    def simplify(self, top, mode):
        float_input_to_int(self, 'pos2')
        return self, None, mode


class nextDayOfWeek(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)
        self.signature.add_sig('pos2', DayOfWeek)


class nextHoliday(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)
        self.signature.add_sig('pos2', Node)


class nextMonthDay(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)
        self.signature.add_sig('pos2', Month)
        self.signature.add_sig('pos3', [Number, Int])

    def simplify(self, top, mode):
        float_input_to_int(self, 'pos3')
        return self, None, mode


class numberToIndexPath(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)


class orConstraint(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)
        self.signature.add_sig('pos2', Node)

    def pre_simplify(self, top, mode):
        d, e = self.simplify_rename('OR')
        d.simplify(None, None)
        return self, e, mode


class previousDayOfMonth(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)
        self.signature.add_sig('pos2', [Number, Int])

    def simplify(self, top, mode):
        float_input_to_int(self, 'pos2')
        return self, None, mode


class previousDayOfWeek(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)
        self.signature.add_sig('pos2', DayOfWeek)


class previousHoliday(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)
        self.signature.add_sig('pos2', Holiday)


class previousMonthDay(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)
        self.signature.add_sig('pos2', Node)
        self.signature.add_sig('pos3', [Number, Int])

    def simplify(self, top, mode):
        float_input_to_int(self, 'pos3')
        return self, None, mode


class refer(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)
        self.signature.add_sig('role', Str)  # new param
        self.signature.add_sig('mid', Node)  # new param
        self.signature.add_sig('midId', Str)  # new param
        self.signature.add_sig('type', Str)  # new param
        self.signature.add_sig('cond', Node)  # new param
        self.signature.add_sig('midtype', Str)  # new param
        self.signature.add_sig('id', Str)  # new param
        self.signature.add_sig('no_fallback', Bool)  # new param
        self.signature.add_sig('force_fallback', Bool)  # new param
        self.signature.add_sig('multi', Bool)  # new param
        self.signature.add_sig('no_eval', Bool)  # new param
        self.signature.add_sig('match_miss', Bool)  # new param

    def simplify(self, top, mode):
        pnm, parent = self.get_parent()
        if 'pos1' in self.inputs:
            inp = self.inputs['pos1']
            if inp.typename() == 'AND':
                if len(inp.inputs) == 2:
                    os = inp.get_op_objects()
                    ts = list(set(o.typename() for o in os))
                    if len(os) == 2 and len(ts) == 2 and all(
                            [t in ['extensionConstraint', 'roleConstraint'] for t in ts]):
                        self.disconnect_input('pos1')
                        for o in os:
                            if o.typename() == 'extensionConstraint':
                                self.replace_input('pos1', o)
                            if o.typename() == 'roleConstraint':
                                self.replace_input('role', o)
                        return parent, None, mode
        return self, None, mode


class roleConstraint(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)

    def simplify(self, top, mode):
        if 'pos1' in self.inputs:
            p1, n1 = self.get_input_path(':append.:List.:Path')
            if p1 and len(p1[-1].inputs) == 0:
                p2, n2 = self.get_input_path(':append.:Path.pos1')
                if p2:
                    p2[-2].disconnect_input('pos1')
                    p2[0].replace_self(p2[-1])
                    return self, None, mode
            p1, n1 = self.get_input_path(':Path.pos1')
            if p1 and len(p1[-1].inputs) == 0:
                p1[0].disconnect_input('pos1')
                p1[0].replace_self(p1[-1])
        return self, None, mode


class roomRequest(Node):
    def __init__(self):
        super().__init__()


class send(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)


class singleton(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)
        self.signature.add_sig('filter', Node)  # new param
        self.signature.add_sig('index', Int)  # new param

    def simplify(self, top, mode):
        if 'pos1' in self.inputs:
            pnm, parent = self.get_parent()
            self.replace_self(self.inputs['pos1'])
            return parent, None, mode
        return self, None, mode


class size(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)
        self.signature.add_sig('unroll', Bool)  # new param


class subtractDurations(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)
        self.signature.add_sig('pos2', Node)


class take(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)
        self.signature.add_sig('pos2', [Number, Int])

    def simplify(self, top, mode):
        float_input_to_int(self, 'pos2')
        return self, None, mode


class takeRight(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)
        self.signature.add_sig('pos2', [Number, Int])

    def simplify(self, top, mode):
        float_input_to_int(self, 'pos2')
        return self, None, mode


class toDays(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)

    def simplify(self, top, mode):
        float_input_to_int(self, 'pos1')
        return self, None, mode


class toFahrenheit(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', [Number, Int])

    def simplify(self, top, mode):
        float_input_to_int(self, 'pos1')
        return self, None, mode


class toFourDigitYear(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)

    def simplify(self, top, mode):
        float_input_to_int(self, 'pos1')
        return self, None, mode


class toHours(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)

    def simplify(self, top, mode):
        float_input_to_int(self, 'pos1')
        return self, None, mode


class toMinutes(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)

    def simplify(self, top, mode):
        float_input_to_int(self, 'pos1')
        return self, None, mode


class toMonth(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', [Number, Int])

    def simplify(self, top, mode):
        float_input_to_int(self, 'pos1')
        return self, None, mode


class toMonths(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', [Number, Int])

    def simplify(self, top, mode):
        float_input_to_int(self, 'pos1')
        return self, None, mode


class toRecipient(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)

    def simplify(self, top, mode):
        pnm, parent = self.get_parent()
        if 'pos1' in self.inputs:
            self.replace_self(self.inputs['pos1'])
            return parent, None, mode
        return self, None, mode


class toWeeks(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)


class toYears(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', [Number, Int])

    def simplify(self, top, mode):
        float_input_to_int(self, 'pos1')
        return self, None, mode


class true(Node):
    def __init__(self):
        super().__init__()


class update(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)
        self.signature.add_sig('pos2', Path)
        self.signature.add_sig('pos3', Node)


############################################################
# New Nodes


class ALL(Aggregator):  # new type
    def __init__(self):
        super().__init__()


class AND(Aggregator):  # new type
    def __init__(self):
        super().__init__()

    def simplify(self, top, mode):
        ms = [i for i in list(self.inputs.keys()) if is_pos(i)]
        ns = [self.inputs[i] for i in ms]
        na = [n.typename() == 'AND' for n in ns]
        if any(na):
            if len(ms) > 1:
                objs = []
                for i in range(len(na)):
                    s, a = ns[i], na[i]
                    o = [s.inputs[j] for j in s.inputs] if a else [s]
                    if a:
                        s.disconnect_input_nodes(o)
                    self.disconnect_input(ms[i])
                    objs += o
                s = 'AND(%s)' % ','.join([id_sexp(o) for o in objs])
                d, e = self.call_construct(s, self.context)
                self.replace_self(d)
                return d, e, mode
            else:
                pnm, parent = self.get_parent()
                self.replace_self(ns[0])
                return parent, None, mode
        return self, None, mode

    def custom_compare_tree(self, other, diffs):
        smatched, omatched = [], []

        for snm in self.inputs:
            for onm in other.inputs:
                if snm not in smatched and onm not in omatched:
                    df = self.inputs[snm].compare_tree(other.inputs[onm], [])
                    if not df:
                        smatched.append(snm)
                        omatched.append(onm)

        if len(smatched) == len(self.inputs) and len(omatched) == len(other.inputs):
            return diffs

        for snm in self.inputs:
            if snm not in smatched:
                diffs.append('ANDmissing(%s)' % re.sub('[ \n]', '', self.inputs[snm].show()))
        for onm in other.inputs:
            if onm not in omatched:
                diffs.append('ANDextra(%s)' % re.sub('[ \n]', '', other.inputs[onm].show()))
        return diffs


class ANDf(Node):  # new type
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos', Bool)


class ANY(Aggregator):  # new type
    def __init__(self):
        super().__init__()


class AcceptSuggestion(Node):  # new type
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', [Int, Number])


class CreateEvent(Node):  # new type
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)


class DateRange(Node):  # new type
    def __init__(self):
        super().__init__()
        self.signature.add_sig('start', Date)
        self.signature.add_sig('end', Date)


class DateRange_to_Date(Node):  # new type
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', DateRange)


class DateRange_to_DateTimeRange(Node):  # new type
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', DateRange)


class DateTimeRange(Node):  # new type
    def __init__(self):
        super().__init__()
        self.signature.add_sig('start', DateTime)
        self.signature.add_sig('end', DateTime)

    def simplify(self, top, mode):
        pnm, parent = self.get_parent()
        d1, d2 = self.get_inputs(['start', 'end'])
        if d1 and d2 and d1.typename() == 'getattr' and d2.typename() == 'getattr':
            n1, v1 = d1.get_inputs([posname(1), posname(2)])
            n2, v2 = d2.get_inputs([posname(1), posname(2)])
            if n1.dat == 'start' and n2.dat == 'end' and v1.typename() == v2.typename() and \
                    v1.typename()[0] == 'x' and v2.typename()[0] == 'x':
                g, e = self.call_construct('getEventDateTimeRange(%s)' % id_sexp(v1), self.context)
                self.replace_self(g)
                return parent, None, mode
        return self, None, mode


class DateTimeRange_to_DateTime(Node):  # new type
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', DateTimeRange)


class DeleteEvent(Node):  # new type
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)

    def simplify(self, top, mode):
        if 'pos1' in self.inputs:
            ev = self.inputs['pos1']
            if ev.typename() == 'getattr':
                p1, p2 = ev.get_inputs(['pos1', 'pos2'])
                if p1 and p2 and p1.dat == 'id':
                    self.context.replace_assign(ev, p2)
                    self.replace_input('pos1', p2)
                    ev.disconnect_input('pos2')
            path, names = self.get_input_path(':Execute.:refer.:extensionConstraint.:Event')
            if path:
                self.replace_input('pos1', path[-1])

        return self, None, mode


class Div(Node):  # new type
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Int)
        self.signature.add_sig('pos2', Int)


class EQf(Node):  # new type
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)
        self.signature.add_sig('pos2', Node)


class EventToCTree(Node):  # new type
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Event)


class Exists(Node):  # new type
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)


class FN(Qualifier):  # new type
    def __init__(self):
        super().__init__()
        self.signature.add_sig('farg', Node)
        self.signature.add_sig('fname', Str)


class FindEvents(Node):  # new type
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)
        self.signature.add_sig('tmp', Node)

    def simplify(self, top, mode):
        pnm, parent = self.get_parent()
        if 'pos1' in self.inputs and parent.typename() in EVENT_NODES:
            self.replace_self(self.inputs['pos1'])
            return parent, None, mode
        return self, None, mode


class GE(Qualifier):  # new type
    def __init__(self):
        super().__init__()


class GEf(Node):  # new type
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)
        self.signature.add_sig('pos2', Node)


class GT(Qualifier):  # new type
    def __init__(self):
        super().__init__()


class GTf(Node):  # new type
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)
        self.signature.add_sig('pos2', Node)


class GeoCoords(Node):  # new type
    def __init__(self):
        super().__init__()
        self.signature.add_sig('lat', Str)
        self.signature.add_sig('long', Str)
        self.signature.add_sig('noCoord', Str)
        self.signature.add_sig('uplace', PlaceUniqueID)


class LAST(Aggregator):  # new type
    def __init__(self):
        super().__init__()


class LE(Qualifier):  # new type
    def __init__(self):
        super().__init__()


class LEf(Node):  # new type
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)
        self.signature.add_sig('pos2', Node)


class LIKE(Qualifier):  # new type
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)


class LIKEf(Node):  # new type
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)
        self.signature.add_sig('pos2', Node)


class LTf(Node):  # new type
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)
        self.signature.add_sig('pos2', Node)


class MAX(Aggregator):  # new type
    def __init__(self):
        super().__init__()


class MIN(Aggregator):  # new type
    def __init__(self):
        super().__init__()


class MODE(Modifier):  # new type
    def __init__(self):
        super().__init__()
        self.signature.add_sig('mode', Str)
        self.signature.add_sig('pos1', Node)


class ModifyEventRequest(Node):  # new type
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)
        self.signature.add_sig('clobber', Bool)

    def simplify(self, top, mode):
        return self, None, mode


class MoreSuggestions(Node):  # new type
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Str)


class Mult(Node):  # new type
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Int)
        self.signature.add_sig('pos2', Int)


class NEQ(Qualifier):  # new type
    def __init__(self):
        super().__init__()


class NEQf(Node):  # new type
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)
        self.signature.add_sig('pos2', Node)


class NONE(Aggregator):  # new type
    def __init__(self):
        super().__init__()


class NOT(Aggregator):  # new type
    def __init__(self):
        super().__init__()


class NOTf(Node):  # new type
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Bool)


class OR(Aggregator):  # new type
    def __init__(self):
        super().__init__()

    def custom_compare_tree(self, other, diffs):
        smatched, omatched = [], []

        for snm in self.inputs:
            for onm in other.inputs:
                if snm not in smatched and onm not in omatched:
                    df = self.inputs[snm].compare_tree(other.inputs[onm], [])
                    if not df:
                        smatched.append(snm)
                        omatched.append(onm)

        if len(smatched) == len(self.inputs) and len(omatched) == len(other.inputs):
            return diffs

        for snm in self.inputs:
            if snm not in smatched:
                diffs.append('ORmissing(%s)' % re.sub('[ \n]', '', str(self.inputs[snm])))
        for onm in other.inputs:
            if onm not in omatched:
                diffs.append('ORextra(%s)' % re.sub('[ \n]', '', str(other.inputs[onm])))
        return diffs


class ORf(Node):  # new type
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos', Bool)


class Period(Node):  # new type
    def __init__(self):
        super().__init__()
        self.signature.add_sig('day', Int)
        self.signature.add_sig('week', Int)
        self.signature.add_sig('month', Int)
        self.signature.add_sig('year', Int)
        self.signature.add_sig('hour', Int)
        self.signature.add_sig('minute', Int)


class PlaceUniqueID(Node):  # new type
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Str)
        self.signature.add_sig('keyphrase', LocationKeyphrase)


class RawDateTime(Node):  # new type
    def __init__(self):
        super().__init__()
        self.signature.add_sig('year', Int)
        self.signature.add_sig('month', Int)
        self.signature.add_sig('week', Int)
        self.signature.add_sig('day', Int)
        self.signature.add_sig('hour', Int)
        self.signature.add_sig('minute', Int)


class RejectSuggestion(Node):  # new type
    def __init__(self):
        super().__init__()


class SET(Aggregator):  # new type
    def __init__(self):
        super().__init__()

    def custom_compare_tree(self, other, diffs):
        smatched, omatched = [], []

        for snm in self.inputs:
            for onm in other.inputs:
                if snm not in smatched and onm not in omatched:
                    df = self.inputs[snm].compare_tree(other.inputs[onm], [])
                    if not df:
                        smatched.append(snm)
                        omatched.append(onm)

        if len(smatched) == len(self.inputs) and len(omatched) == len(other.inputs):
            return diffs

        for snm in self.inputs:
            if snm not in smatched:
                diffs.append('SETmissing(%s)' % re.sub('[ \n]', '', str(self.inputs[snm])))
        for onm in other.inputs:
            if onm not in omatched:
                diffs.append('SETextra(%s)' % re.sub('[ \n]', '', str(other.inputs[onm])))
        return diffs


class Select(Node):  # new type
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos', Node)
        self.signature.add_sig('inp', Node)


class Str_to_Location(Node):  # new type
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Str)


class TEE(Aggregator):  # new type
    def __init__(self):
        super().__init__()
        self.signature.add_sig('name', Str)
        self.signature.add_sig('pos1', Node)


class ThisWeekEnd(Node):  # new type
    def __init__(self):
        super().__init__()


class TimeRange(Node):  # new type
    def __init__(self):
        super().__init__()
        self.signature.add_sig('start', Time)
        self.signature.add_sig('end', Time)


class TimeRange_to_DateTimeRange(Node):  # new type
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', TimeRange)


class TimeRange_to_Time(Node):  # new type
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', TimeRange)


class ToDateTimeCTree(Node):  # new type
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', DateTime)


class ToEventCTree(Node):  # new type
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', DateTime)
        self.signature.add_sig('as_end', Bool)


class UpdateEvent(Node):  # new type
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Event, alias='event')
        self.signature.add_sig('pos2', Event, alias='constraint')

    def simplify(self, top, mode):
        ev = self.get_inputs('event')
        path = self.get_input_path_by_name('event.pos1')
        if path and path[0].typename() == 'getattr' and path[1].dat and path[1].dat == 'id' and \
                'pos2' in path[0].inputs:
            self.context.replace_assign(path[0], path[0].inputs['pos2'])
            self.replace_input('event', path[0].inputs['pos2'])
            path[0].disconnect_input('pos2')
        elif ev and is_assign_name(ev.typename()):
            nm = ev.typename()
            # these rules target specific (but recurring) expressions:
            # e.g. UpdateEvent(event=x0, constraint=AND(...,starts_at(:date(:start(x0)))))
            # i.e. asking to update event x0 to have the start date of event x0 - unnecessary
            path, names = self.get_input_path(':AND.:starts_at.:getattr.:getattr.:%s' % nm)
            if path and path[2].inputs['pos1'].dat == 'date' and path[3].inputs['pos1'].dat == 'start':
                path[0].disconnect_input(names[1])
            else:
                path, names = self.get_input_path(':AND.:ends_at.:getattr.:getattr.:%s' % nm)
                if path and path[2].inputs['pos1'].dat == 'date' and path[3].inputs['pos1'].dat == 'end':
                    path[0].disconnect_input(names[1])
        return self, None, mode


class WeatherTable(Node):  # new type
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Str, alias='table')


class WeekDays(Node):  # new type
    def __init__(self):
        super().__init__()


class WeekEndDays(Node):  # new type
    def __init__(self):
        super().__init__()


class at_location(Modifier):  # new type
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)

    def simplify(self, top, mode):
        pnm, parent = self.get_parent()
        # if there is some negation above (and not empty input) change self to avoid_location
        if 'pos1' in self.inputs:
            if parent.typename() in NEGATIONS:
                ppnm, pparent = parent.get_parent()
                if pparent:
                    d, e = self.simplify_rename('avoid_location')
                    parent.replace_self(d)
                    return pparent, None, mode
        return self, None, mode


class avoid_attendee(Modifier):  # new type
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)


class avoid_duration(Modifier):  # new type
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)


class avoid_end(Modifier):  # new type
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)


class avoid_location(Modifier):  # new type
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)


class avoid_start(Modifier):  # new type
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)


class avoid_subject(Modifier):  # new type
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)


class do_multi(Node):  # new type
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)
        self.signature.add_sig('pos2', Node)
        self.signature.add_sig('pos3', Node)
        self.signature.add_sig('pos4', Node)
        self.signature.add_sig('pos5', Node)
        self.signature.add_sig('pos6', Node)


class eventBeforeDate(Node):  # new type
    def __init__(self):
        super().__init__()
        self.signature.add_sig('date', Date)
        self.signature.add_sig('event', Event)


class EventDuringRange(Node):  # new type
    def __init__(self):
        super().__init__()
        self.signature.add_sig('range', [DateRange, DateTimeRange, TimeRange])
        self.signature.add_sig('event', Event)

    def simplify(self, top, mode):
        compose_ev_constr(self, top, mode)
        pnm, parent = self.get_parent()
        dt = self.input_view('range')
        if dt:
            dt = replace_sub_assign(dt)
            d, e = self.call_construct('at_time(%s)' % id_sexp(dt), self.context)
            self.replace_self(d)
            return parent, e, mode
        return self, None, mode


class eventOnDate(Node):  # new type
    def __init__(self):
        super().__init__()
        self.signature.add_sig('date', Date)
        self.signature.add_sig('event', Event)

    def simplify(self, top, mode):
        compose_ev_constr(self, top, mode)
        pnm, parent = self.get_parent()
        dt = self.input_view('date')
        if dt:
            dt = replace_sub_assign(dt)
            d, e = self.call_construct('at_time(%s)' % id_sexp(dt), self.context)
            self.replace_self(d)
            return parent, e, mode
        return self, None, mode


class execute(Node):  # new type
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)
        self.signature.add_sig('clear', Bool)
        self.signature.add_sig('hide_goal', Bool)


class filtering(Node):  # new type
    def __init__(self):
        super().__init__()
        self.signature.add_sig('filter', Node)
        self.signature.add_sig('pos1', Node)
        self.signature.add_sig('index', Int)


class has_id(Modifier):  # new type
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Int)

    def simplify(self, top, mode):
        pnm, parent = self.get_parent()
        if 'pos1' in self.inputs:
            if parent.typename() in NEGATIONS:
                ppnm, pparent = parent.get_parent()
                if pparent:
                    d, e = self.simplify_rename('avoid_id')
                    parent.replace_self(d)
                    return pparent, None, mode
        return self, None, mode


class has_subject(Modifier):  # new type
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)

    def simplify(self, top, mode):
        pnm, parent = self.get_parent()
        # handle negation or unnecessary 'LIKE' above self (only if non empty input)
        if 'pos1' in self.inputs:
            if parent.typename() in NEGATIONS + ['LIKE']:
                ppnm, pparent = parent.get_parent()
                if pparent:
                    if parent.typename() == 'LIKE':
                        parent.replace_self(self)
                        return pparent, None, mode
                    else:
                        d, e = self.simplify_rename('avoid_subject')
                        parent.replace_self(d)
                        return pparent, None, mode
        return self, None, mode


class has_status(Modifier):  # new type
    def __init__(self):
        super().__init__(Event)
        self.signature.add_sig(posname(1), Node)

    def simplify(self, top, mode):
        pnm, parent = self.get_parent()
        # handle negation above self (only if non empty input)
        if 'pos1' in self.inputs:
            if parent.typename() in NEGATIONS:
                ppnm, pparent = parent.get_parent()
                if pparent:
                    d, e = self.simplify_rename('avoid_status')
                    parent.replace_self(d)
                    return pparent, None, mode
        return self, None, mode


class avoid_status(Modifier):  # new type
    def __init__(self):
        super().__init__(Event)
        self.signature.add_sig(posname(1), Node)


class has_duration(Modifier):  # new type
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)

    def simplify(self, top, mode):
        pnm, parent = self.get_parent()
        # handle negation above self (only if non empty input)
        if 'pos1' in self.inputs:
            if parent.typename() in NEGATIONS:
                ppnm, pparent = parent.get_parent()
                if pparent:
                    d, e = self.simplify_rename('avoid_duration')
                    parent.replace_self(d)
                    return pparent, None, mode
        return self, None, mode


class prefer_friends(Node):  # new type
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)


class replace_agg(Node):  # new type
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)
        self.signature.add_sig('pos2', Str)


class rerun(Node):  # new type
    def __init__(self):
        super().__init__()
        self.signature.add_sig('id', Int)
        self.signature.add_sig('keep_goal', Bool)


class revise(Node):  # new type
    def __init__(self):
        super().__init__()
        self.signature.add_sig('goal', Node)
        self.signature.add_sig('root', Node)
        self.signature.add_sig('mid', Node)
        self.signature.add_sig('midGoal', Node)
        self.signature.add_sig('old', Node)
        self.signature.add_sig('oclevel', Str)
        self.signature.add_sig('oldType', Str)
        self.signature.add_sig('oldTypes', Node)
        self.signature.add_sig('oldNodeId', Str)
        self.signature.add_sig('oldNode', Node)
        self.signature.add_sig('role', Str)
        self.signature.add_sig('hasParam', Str)
        self.signature.add_sig('hasTag', Str)
        self.signature.add_sig('new', Node)
        self.signature.add_sig('newMode', Str)
        self.signature.add_sig('inp_nm', Str)
        self.signature.add_sig('no_add_goal', Bool)
        self.signature.add_sig('no_eval_res', Bool)


class sel_inp(Node):  # new type
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)
        self.signature.add_sig('pos2', Str)
        self.signature.add_sig('inp', Node)


class shift_start0(Modifier):  # new type
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)


class starts_at(Modifier):  # new type
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)

    def simplify(self, top, mode):
        pnm, parent = self.get_parent()
        if 'pos1' in self.inputs:
            inp = self.inputs['pos1']
            if parent.typename() in NEGATIONS:
                ppnm, pparent = parent.get_parent()
                if pparent:
                    d, e = self.simplify_rename('avoid_start')
                    parent.replace_self(d)
                    return pparent, None, mode

            tp = inp.typename()
            if is_assign_name(tp) and self.context.has_assign(tp):
                inp = self.context.get_assign(tp)
                tp = inp.typename()
            if tp in ['AND', 'OR']:
                prms = [inp.inputs[i] for i in inp.inputs]
                if len(prms) == 2:
                    s = '%s(%s)' % (tp, ','.join(['starts_at(%s)' % id_sexp(i) for i in prms]))
                    d, e = self.call_construct(s, self.context)
                    self.replace_self(d)
                    return parent, None, mode
                elif len(prms) == 1:
                    self.disconnect_input('pos1')
                    self.replace_input('pos1', prms[0])
                    return self, None, mode
            elif tp in ['DateAtTimeWithDefaults', 'DateTimeConstraint',
                        'ClosestDayOfWeek']:  # TODO: makes some nodes have multiple parents - asking for trouble!
                prms = [inp.inputs[i] for i in inp.inputs]
                if len(prms) == 2:
                    s = 'AND(%s)' % ','.join(['starts_at(%s)' % id_sexp(i) for i in prms])
                    d, e = self.call_construct(s, self.context)
                    self.replace_self(d)
                    return parent, None, mode
                elif len(prms) == 1:
                    self.disconnect_input('pos1')
                    self.replace_input('pos1', prms[0])
                    return self, None, mode
            if tp == 'DateTime':
                if len(inp.inputs) == 1:
                    inp = inp.get_single_input_view()
                    tp = inp.typename()
            if tp in ['Date', 'Time']:
                if len(inp.inputs) == 1:
                    nd = inp.get_single_input_view()
                    if 'pos1' in nd.inputs and nd.typename() in ['NOT', 'negate', 'NEQ']:
                        ng = nd.input_view('pos1')
                        nd.replace_self(ng)
                        self.simplify_rename('avoid_start')
                        return parent, None, mode

        return self, None, mode


class ends_at(Modifier):  # new type3
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)

    def simplify(self, top, mode):
        pnm, parent = self.get_parent()
        if 'pos1' in self.inputs:
            inp = self.inputs['pos1']
            if parent.typename() in NEGATIONS:
                ppnm, pparent = parent.get_parent()
                if pparent:
                    d, e = self.simplify_rename('avoid_end')
                    parent.replace_self(d)
                    return pparent, None, mode

            tp = inp.typename()
            if is_assign_name(tp) and self.context.has_assign(tp):
                inp = self.context.get_assign(tp)
                tp = inp.typename()
            if tp == 'DateAtTimeWithDefaults':  # TODO: makes some nodes have multiple parents - asking for trouble!
                prms = [inp.inputs[i] for i in inp.inputs]
                if len(prms) == 2:
                    s = 'AND(%s)' % ','.join(['ends_at(%s)' % id_sexp(i) for i in prms])
                    d, e = self.call_construct(s, self.context)
                    self.replace_self(d)
                    return parent, None, mode
                elif len(prms) == 1:
                    self.disconnect_input('pos1')
                    self.replace_input('pos1', prms[0])
                    return self, None, mode
        return self, None, mode


class at_time(Modifier):  # new type
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)

    def simplify(self, top, mode):
        pnm, parent = self.get_parent()
        if 'pos1' in self.inputs:
            inp = self.inputs['pos1']
            if parent.typename() in NEGATIONS:
                ppnm, pparent = parent.get_parent()
                if pparent:
                    d, e = self.simplify_rename('avoid_time')
                    parent.replace_self(d)
                    return pparent, None, mode

            tp = inp.typename()
            if is_assign_name(tp) and self.context.has_assign(tp):
                inp = self.context.get_assign(tp)
                tp = inp.typename()

            if tp in ['DateAtTimeWithDefaults', 'DateTimeConstraint',
                      'ClosestDayOfWeek']:  # TODO: makes some nodes have multiple parents - asking for trouble!
                prms = [inp.inputs[i] for i in inp.inputs]
                if len(prms) == 2:
                    s = 'AND(%s)' % ','.join(['at_time(%s)' % id_sexp(i) for i in prms])
                    d, e = self.call_construct(s, self.context)
                    self.replace_self(d)
                    return parent, None, mode
                elif len(prms) == 1:
                    self.disconnect_input('pos1')
                    self.replace_input('pos1', prms[0])
                    return self, None, mode
        return self, None, mode


class avoid_time(Modifier):  # new type
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)

    def simplify(self, top, mode):
        pnm, parent = self.get_parent()
        if 'pos1' in self.inputs:
            inp = self.inputs['pos1']
            tp = inp.typename()
            if is_assign_name(tp) and self.context.has_assign(tp):
                inp = self.context.get_assign(tp)
                tp = inp.typename()
            if tp in ['DateAtTimeWithDefaults', 'DateTimeConstraint',
                      'ClosestDayOfWeek']:  # TODO: makes some nodes have multiple parents - asking for trouble!
                prms = [inp.inputs[i] for i in inp.inputs]
                if len(prms) == 2:
                    s = 'AND(%s)' % ','.join(['avoid_time(%s)' % id_sexp(i) for i in prms])
                    d, e = self.call_construct(s, self.context)
                    self.replace_self(d)
                    return parent, None, mode
                elif len(prms) == 1:
                    self.disconnect_input('pos1')
                    self.replace_input('pos1', prms[0])
                    return self, None, mode
        return self, None, mode


# this means that the given input (a Date/Time range) should be taken exactly as start and end
class spans_time(Modifier):  # new type
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)

    def simplify(self, top, mode):
        pnm, parent = self.get_parent()
        if 'pos1' in self.inputs:
            inp = self.inputs['pos1']
            if parent.typename() in NEGATIONS:
                ppnm, pparent = parent.get_parent()
                if pparent:
                    d, e = self.simplify_rename('avoid_span')
                    parent.replace_self(d)
                    return pparent, None, mode
            tp = inp.typename()
            if is_assign_name(tp) and self.context.has_assign(tp):
                inp = self.context.get_assign(tp)
                tp = inp.typename()
            if tp in ['DateAtTimeWithDefaults', 'DateTimeConstraint',
                      'ClosestDayOfWeek']:  # TODO: makes some nodes have multiple parents - asking for trouble!
                prms = [inp.inputs[i] for i in inp.inputs]
                if len(prms) == 2:
                    s = 'AND(%s)' % ','.join(['spans_time(%s)' % id_sexp(i) for i in prms])
                    d, e = self.call_construct(s, self.context)
                    self.replace_self(d)
                    return parent, None, mode
                elif len(prms) == 1:
                    self.disconnect_input('pos1')
                    self.replace_input('pos1', prms[0])
                    return self, None, mode
        return self, None, mode


class with_attendee(Modifier):  # new type
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)

    def simplify(self, top, mode):
        _, parent = self.get_parent()
        if parent and parent.typename() in ['with_attendee', 'avoid_attendee']:
            self.replace_self(self.inputs['pos1'])
            return parent, None, mode
        if parent:
            _, pparent = parent.get_parent()
            if pparent and pparent.typename() in ['with_attendee', 'avoid_attendee']:
                self.replace_self(self.inputs['pos1'])
                return parent, None, mode
        return self, None, mode


class with_id(Modifier):  # new type
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)

    def simplify(self, top, mode):
        pnm, parent = self.get_parent()
        d = self.input_view(posname(1))
        if parent.typename() in NEGATIONS:
            ppnm, pparent = parent.get_parent()
            if pparent:
                d, e = self.simplify_rename('avoid_id')
                parent.replace_self(d)
                return pparent, None, mode

        if d and d.typename() == 'getattr':  # with_id can handle event as input (no need to explicitly extract id)
            n, v = d.get_inputs(['pos1', 'pos2'])
            if n.dat == 'id':
                self.disconnect_input('pos1')
                d.disconnect_input('pos2')
                v.connect_in_out('pos1', self)
                return parent, None, mode
        return self, None, mode


class avoid_id(Modifier):  # new type
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)

    def simplify(self, top, mode):
        pnm, parent = self.get_parent()
        d = self.input_view(posname(1))
        if d and d.typename() == 'getattr':  # avoid_id can handle event as input (no need to explicitly extract id)
            n, v = d.get_inputs(['pos1', 'pos2'])
            if n.dat == 'id':
                self.disconnect_input('pos1')
                d.disconnect_input('pos2')
                v.connect_in_out('pos1', self)
                return parent, None, mode
        return self, None, mode


class is_allDay(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Boolean)


class is_oneOnOne(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Boolean)


class not_allDay(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Boolean)


class not_oneOnOne(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Boolean)


class with_organizer(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)


class not_organizer(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('pos1', Node)


class TRUE(Qualifier):  # new type
    def __init__(self):
        super().__init__()


class FALSE(Qualifier):  # new type
    def __init__(self):
        super().__init__()


# new node - input: event, output: the DateTimeRange of the event
class getEventDateTimeRange(Node):
    def __init__(self):
        super().__init__(DateTimeRange)
        self.signature.add_sig('pos1', Node)

    def simplify(self, top, mode):
        pnm, parent = self.get_parent()
        d = self.input_view(posname(1))
        if d and parent.typename() in EV_TIME_MODS:
            self.replace_self(d)
            return parent, None, mode
        return self, None, mode
