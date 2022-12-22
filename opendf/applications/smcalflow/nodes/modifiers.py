"""
Application specific modifier nodes.
"""

from opendf.applications.smcalflow.nodes.objects import *
from opendf.applications.smcalflow.domain import *
from opendf.graph.nodes.framework_functions import get_refer_match
from opendf.graph.nodes.framework_operators import Modifier
from opendf.graph.nodes.node import search_for_types_in_parents
from opendf.graph.transform_graph import do_transform_graph

# the following modifiers are Event modifiers - in the future we may have modifiers for other types (e.g.  Recipient),
# so the names may have to change to indicate this.
# (alternatively, the graph transformation mechanism may resolve modifiers to their right type / function).

# #################################################################################################
# ######################################## event modifiers ########################################

# We use a design pattern which we call modifiers, which the simplified SMCalFlow annotation is using.
# These are functions which generate constraints in a standardized way. This is useful since the same request can be
# formulated in different ways as a constraint (or combinaiton of constraints).
# By having constraints formulated in a specific way, it is easier to merge and prune multiple constraints.
#
# The modifiers are currently used primarily by the event creation/search/update/delete.
# modifiers (and hence the constraints they create) are combined into constraint trees, where each turn is a branch
# under a top level AND. As the dialogue progresses, more turns may be added.
# When using the tree (e.g. searching for an event), the turn tree is pruned (actually, a copy is made and then pruned),
# and the pruned tree is used for search.
#
# Due to the design of the simplified annotation, modifiers may have many different types of inputs, so they need more
# attention converting this input to the right format - using transform_graph (other node types need this transformation
# as well, but don't have to deal with so many input types).
# The transformation continues in the exec() function - finishing off transformations which require knowledge of the
# types of results of inputs.
#
# modifiers can have one more step - convert_modifier,

# #################################################################################################
# ###################################### location modifiers  ######################################

# at_location's argument:
#  - if result of an input function, then result should be a LocationKeyphrase or a SET of these.
#    if SET - then we convert to OR
#    (we could allow Str/SET(Str), although that should not really happen)
#  - else - LocationKeyphrase or Str (Str will need to be converted to LocationKeyphrase).
#      if plural input, then we interpret it as OR
from opendf.defs import is_pos, posname


class at_location(Modifier):
    def __init__(self):
        super().__init__(Event)
        self.signature.add_sig(posname(1), Node, True)

    # transform input to the right format.
    # there are two use cases for this func (indicated by eval):
    #   1. before graph evaluation (in transform_graph)
    #      - At the time of running, there are no results yet (for any node),
    #         i.e. self.result=self, input_view(i)==inputs[i],
    #              inp.outype may be correct, but if inp is a function, we don't know if it will return one or
    #              multiple objects - therefore we leave it as is for now - it will be handled after eval.
    #   2. after evaluation (e.g. from valid_input or convert_modifier)
    #      - At this point, all results are filled (for children nodes, at least)
    #        i.e. input_view(i) (unless view_INT) is the final (transitive) result of that input, so type==out_type
    def do_trans(self, evl=False):
        inp = self.input_view(posname(1))
        pref = 'Event?(location=LIKE('
        if inp.is_aggregator():
            for i in list(inp.inputs.keys()):
                if is_pos(i):
                    # this would fail on aggregation input to aggregation
                    it = inp.input_view(i).outypename() if evl else inp.inputs[i].typename()
                    if it in ['Str', 'LocationKeyphrase']:
                        s = 'Str_to_Location(' if it == 'Str' else ''
                        inp.wrap_input(i, pref + s, do_eval=evl)
            if inp.typename() != 'OR':  # aggregation for positive locations is set to 'OR'
                self.wrap_input(posname(1), 'replace_agg(', suf=', OR)', do_eval=evl)
        else:
            it = inp.typename()
            if it in ['Str', 'LocationKeyphrase']:
                s = 'Str_to_Location(' if it == 'Str' else ''
                self.wrap_input(posname(1), pref + s, do_eval=evl)

    def exec(self, all_nodes=None, goals=None):
        self.do_trans(evl=True)
        self.set_result(self.input_view(posname(1)))

    def transform_graph(self, top):
        self.do_trans()
        return self, None


class avoid_location(Modifier):
    def __init__(self):
        super().__init__(Event)
        self.signature.add_sig(posname(1), Node, True)

    def do_trans(self, evl=False):
        inp = self.input_view(posname(1))
        pref = 'Event?(location=NOT(LIKE('
        if inp.is_aggregator():
            for i in list(inp.inputs.keys()):
                if is_pos(i):
                    # this would fail on aggregation input to aggregation
                    it = inp.input_view(i).outypename() if evl else inp.inputs[i].typename()
                    if it in ['Str', 'LocationKeyphrase']:
                        s = 'Str_to_Location(' if it == 'Str' else ''
                        inp.wrap_input(i, pref + s, do_eval=evl)
            if inp.typename() != 'AND':  # aggregation for positive locations is set to 'AND'
                self.wrap_input(posname(1), 'replace_agg(', suf=', AND)', do_eval=evl)
        else:
            it = inp.typename()
            if it in ['Str', 'LocationKeyphrase']:
                s = 'Str_to_Location(' if it == 'Str' else ''
                self.wrap_input(posname(1), pref + s, do_eval=evl)

    def exec(self, all_nodes=None, goals=None):
        self.do_trans(evl=True)
        self.set_result(self.input_view(posname(1)))

    def transform_graph(self, top):
        self.do_trans()
        return self, None


# #################################################################################################
# ###################################### attendee modifiers  ######################################

class with_attendee(Modifier):
    def __init__(self):
        super().__init__(Event)
        self.signature.add_sig(posname(1), Node, True)
        self.signature.add_sig(posname(2), Node, alias='exclusive')

    def do_trans(self, evl=False):
        inp = self.input_view(posname(1))
        ot, it = inp.outypename(), inp.typename()
        # 1. add ANY to indicate that a DB event will match, if ANY of its attendees match the specified attendee
        #    i.e. it's not exclusive - there may be additional people
        if posname(2) in self.inputs and self.get_dat(posname(2)):
            pref1 = 'Event?(attendees=ANY(Attendee(exclusive=True, recipient='
        else:
            pref1 = 'Event?(attendees=ANY(Attendee(recipient='
        suf1 = '))'
        # 2. when input is a name, find who it refers to (may initiate a clarification dialog)
        pref2 = 'singleton(refer(Recipient?(name=LIKE(PersonName('
        suf2 = '))),multi=True)))'
        # avoid having to do multiple refers for the same TEE - directly wrap the input to refer
        #       TODO: handling of TEE should be more general! We shouldn't have to do it explicitly
        if inp.is_aggregator():
            for i in list(inp.inputs.keys()):
                if is_pos(i):
                    if inp.input_view(i).outypename() == 'Str':
                        inp.wrap_input(i, pref2, suf=suf2, do_eval=evl)
                    if inp.input_view(i).outypename() == 'Recipient':
                        inp.wrap_input(i, pref1, do_eval=evl)
            if inp.typename() not in ['AND', 'OR']:  # if not AND/OR - defaults to 'AND'
                self.wrap_input(posname(1), 'replace_agg(', suf=', AND)', do_eval=evl)
        elif it == 'TEE':
            if ot == 'Str':
                inp.wrap_input(posname(1), pref2, suf=suf2)
            self.wrap_input(posname(1), pref1, do_eval=evl)
        elif ot in ['Str']:
            self.wrap_input(posname(1), pref1 + pref2, suf=suf2 + suf1, do_eval=evl)
        elif ot == 'Recipient':
            self.wrap_input(posname(1), pref1, do_eval=evl)
        elif it in ['Clear', 'Empty'] and not evl:
            self.wrap_input(posname(1), 'Event?(attendees=', do_eval=evl)

    def exec(self, all_nodes=None, goals=None):
        self.do_trans(evl=True)
        self.set_result(self.input_view(posname(1)))

    def transform_graph(self, top):
        self.do_trans()
        return self, None


class avoid_attendee(Modifier):
    def __init__(self):
        super().__init__(Event)
        self.signature.add_sig(posname(1), Node, True)

    def do_trans(self, evl=False):
        inp = self.input_view(posname(1))
        ot, it = inp.outypename(), inp.typename()
        # 1. add ANY to indicate that a DB event will match, if ANY of its attendees match the specified attendee
        #    i.e. it's not exclusive - there may be additional people
        pref1 = 'Event?(attendees=NONE(Attendee(recipient='
        suf1 = '))'
        # 2. when input is a name, find who it refers to, but we do NOT require it to be just one person
        pref2 = 'refer(Recipient?(name=LIKE(PersonName('
        suf2 = '))),multi=True))'
        # avoid having to do multiple refers for the same TEE - directly wrap the input to refer
        #       TODO: handling of TEE should be more general! we shouldn't have to do it explicitly
        if inp.is_aggregator():
            for i in list(inp.inputs.keys()):
                if is_pos(i):
                    if inp.input_view(i).outypename() == 'Str':
                        inp.wrap_input(i, pref2, suf=suf2, do_eval=evl)
                    if inp.input_view(i).outypename() == 'Recipient':
                        inp.wrap_input(i, pref1, do_eval=evl)
            if inp.typename() not in ['AND', 'OR']:  # if not AND/OR - defaults to 'AND'
                self.wrap_input(posname(1), 'replace_agg(', suf=', AND)', do_eval=evl)
        elif it == 'TEE':
            if ot == 'Str':
                inp.wrap_input(posname(1), pref2, suf=suf2)
            self.wrap_input(posname(1), pref1, do_eval=evl)
        elif ot in ['Str']:
            self.wrap_input(posname(1), pref1 + pref2, suf=suf2 + suf1, do_eval=evl)
        elif ot == 'Recipient':
            self.wrap_input(posname(1), pref1, do_eval=evl)
        elif it in ['Empty'] and not evl:   # avoid_attendee(Empty()) means NOT an event without attendees.
                                            #  Clear() does not make sense here
                                            self.wrap_input(posname(1), 'NOT(Event?(attendees=', do_eval=evl)

    def exec(self, all_nodes=None, goals=None):
        self.do_trans(evl=True)
        self.set_result(self.input_view(posname(1)))

    def transform_graph(self, top):
        self.do_trans()
        return self, None


class clear_attendees(Modifier):

    def __init__(self):
        super().__init__(Event)

    def exec(self, all_nodes=None, goals=None):
        g, _ = Node.call_construct_eval("Event?(attendees=Clear())", self.context)
        self.set_result(g)


class clear_event_field(Modifier):

    def __init__(self):
        super().__init__(Event)
        self.signature.add_sig(posname(1), Str, True)

    def exec(self, all_nodes=None, goals=None):
        g, _ = Node.call_construct_eval(f"Event?({self.get_dat(posname(1))}=Clear())", self.context)
        self.set_result(g)


class empty_event_field(Modifier):

    def __init__(self):
        super().__init__(Event)
        self.signature.add_sig(posname(1), Str, True)

    def exec(self, all_nodes=None, goals=None):
        g, _ = Node.call_construct_eval(f"Event?({self.get_dat(posname(1))}=Empty())", self.context)
        self.set_result(g)

# ################################################################################################
# ######################################## time modifiers ########################################

# we could add a modifier on_holidays - different use of time


class starts_at(Modifier):
    def __init__(self):
        super().__init__(Event)
        self.signature.add_sig(posname(1), Node, True)

    def do_trans(self, evl=False):
        inp = self.input_view(posname(1))
        ot, it = inp.outypename(), inp.typename()
        if not evl:
            do_transform_graph(inp, add_yield=False)  # need to transform input before ToEventCTree
        pref1 = 'ToEventCTree('
        if inp.is_aggregator():
            for i in list(inp.inputs.keys()):
                if is_pos(i):
                    if inp.input_view(i).outypename() in TIME_NODE_NAMES:
                        inp.wrap_input(i, pref1, do_eval=evl)
            if inp.typename() not in ['AND', 'OR']:  # if not AND/OR - defaults to 'AND'
                self.wrap_input(posname(1), 'replace_agg(', suf=', AND)', do_eval=evl)
        elif it == 'TEE':
            if ot in TIME_NODE_NAMES:
                inp.wrap_input(posname(1), pref1)
        elif ot in TIME_NODE_NAMES: #  or inp.get_op_type().__name__ in TIME_NODE_NAMES:
            self.wrap_input(posname(1), pref1, do_eval=evl)
        # allow using an event (actual object) as a time spec (treating it as a time range). needs more work.
        elif evl and inp.constraint_level == 0 and ot == 'Event':
            self.wrap_input(posname(1), 'ToEventCTree(EventToTimeInput(', do_eval=evl)

    def exec(self, all_nodes=None, goals=None):
        self.do_trans(evl=True)
        self.set_result(self.input_view(posname(1)))

    def transform_graph(self, top):
        self.do_trans()
        return self, None


class avoid_start(Modifier):
    def __init__(self):
        super().__init__(Event)
        self.signature.add_sig(posname(1), Node, True)

    def do_trans(self, evl=False):
        inp = self.input_view(posname(1))
        ot, it = inp.outypename(), inp.typename()
        if not evl:
            do_transform_graph(inp, add_yield=False)  # need to trans input before ToEventCTree
        pref1 = 'NOT(ToEventCTree('
        if inp.is_aggregator():
            for i in list(inp.inputs.keys()):
                if is_pos(i):
                    if inp.input_view(i).outypename() in TIME_NODE_NAMES:
                        inp.wrap_input(i, pref1, do_eval=evl)
            if inp.typename() not in ['AND', 'OR', 'NOT']:  # if not AND/OR - defaults to 'AND'
                self.wrap_input(posname(1), 'replace_agg(', suf=', AND)', do_eval=evl)
        elif it == 'TEE':
            if ot in TIME_NODE_NAMES:
                inp.wrap_input(posname(1), pref1)
        elif ot in TIME_NODE_NAMES:
            self.wrap_input(posname(1), pref1, do_eval=evl)
        elif evl and inp.constraint_level == 0 and ot == 'Event':
            self.wrap_input(posname(1), 'NOT(ToEventCTree(EventToTimeInput(', do_eval=evl)

    def exec(self, all_nodes=None, goals=None):
        self.do_trans(evl=True)
        self.set_result(self.input_view(posname(1)))

    def transform_graph(self, top):
        self.do_trans()
        return self, None


def partial_Time_to_time_str(partial):
    time_str = ""
    hour, minute = partial.get_time_values()
    if hour is not None:
        time_str += f"hour={hour}"
    if minute is not None:
        if time_str:
            time_str += ", "
        time_str += f"minute={minute}"
    if time_str:
        time_str = f"Time({time_str})"
    return time_str


def partial_date_to_date_str(partial):
    date_str = ""
    year, month, day, _ = partial.get_date_values()
    if year is not None:
        date_str += f"year={year}"
    if month is not None:
        if date_str:
            date_str += ", "
        date_str += f"month={month}"
    if day is not None:
        if date_str:
            date_str += ", "
        date_str += f"day={day}"
    if date_str:
        date_str = f"Date({date_str})"
    return date_str


def partial_DateTime_to_datetime_str(partial):
    """
    Creates a DateTime node string from the `partial` datetime.

    :param partial: the partial datetime
    :type partial: PartialDateTime
    :return: the node string
    :rtype: str
    """
    date_str = partial_date_to_date_str(partial)
    time_str = partial_Time_to_time_str(partial)

    datetime_str = "DateTime("
    if date_str:
        datetime_str += f"date={date_str}"
    if time_str:
        if date_str:
            datetime_str += ", "
        datetime_str += f"time={time_str}"
    datetime_str += ")"

    return datetime_str


class shift_start(Modifier):

    def __init__(self):
        super().__init__(Event)
        self.signature.add_sig(posname(1), Period, True)
        self.time_name = 'start'

    def convert_modifier(self, parent, constr, obj=None):
        # parent: the Node that called the conversion e.g. Update/CreatePreflightEventWrapper
        # constr: is the constraint tree
        d_context = self.context
        pos1, _ = Node.call_construct_eval(f"Event??(slot=TimeSlot?({self.time_name}=DateTime?()))", d_context)
        events = get_refer_match(d_context, constr.topological_order(), [constr], pos1=pos1, no_fallback=True,
                                 search_last_goal=False)
        events.sort(key=lambda x: x.created_turn, reverse=True)
        if events:
            event = events[0]
            event_field: DateTime = event.get_ext_view(f"slot.{self.time_name}")
            partial_datetime: PartialDateTime = event_field.to_partialDateTime()
            shift: Period = self.input_view(posname(1))
            partial_shift: PartialDateTime = shift.to_partialDateTime()
            if partial_datetime.comparable(partial_shift):
                shifted_time = partial_datetime.add_delta(shift.to_Ptimedelta())
                g, _ = Node.call_construct_eval(
                    f"Event?(slot=TimeSlot?({self.time_name}={partial_DateTime_to_datetime_str(shifted_time)}))",
                    d_context)
                self.set_result(g)

    def match(self, obj, iview=VIEW.INT, oview=None, check_level=False, match_miss=False):
        return self.res.match(obj, check_level=check_level, match_miss=match_miss)


class shift_end(shift_start):

    def __init__(self):
        super(shift_end, self).__init__()
        self.time_name = 'end'


# ################################################################################################


class ends_at(Modifier):
    def __init__(self):
        super().__init__(Event)
        self.signature.add_sig(posname(1), Node, True)
        self.label = "end"

    def do_trans(self, evl=False):
        inp = self.input_view(posname(1))
        ot, it = inp.outypename(), inp.typename()
        if not evl:
            do_transform_graph(inp, add_yield=False)  # need to trans input before ToEventCTree
        pref1 = f'ToEventCTree(label={self.label},'
        if inp.is_aggregator():
            for i in list(inp.inputs.keys()):
                if is_pos(i):
                    if inp.input_view(i).outypename() in TIME_NODE_NAMES:
                        inp.wrap_input(i, pref1, do_eval=evl)
            if inp.typename() not in ['AND', 'OR']:  # if not AND/OR - defaults to 'AND'
                self.wrap_input(posname(1), 'replace_agg(', suf=', AND)', do_eval=evl)
        elif it == 'TEE':
            if ot in TIME_NODE_NAMES:
                inp.wrap_input(posname(1), pref1)
        elif ot in TIME_NODE_NAMES:
            self.wrap_input(posname(1), pref1, do_eval=evl)
        elif evl and inp.constraint_level == 0 and ot == 'Event':
            self.wrap_input(posname(1), f'ToEventCTree(label={self.label},EventToTimeInput(', do_eval=evl)

    def exec(self, all_nodes=None, goals=None):
        self.do_trans(evl=True)
        self.set_result(self.input_view(posname(1)))

    def transform_graph(self, top):
        self.do_trans()
        return self, None


class at_time(ends_at):

    def __init__(self):
        super().__init__()

    def do_trans(self, evl=False):
        name = search_for_types_in_parents(self, {"CreatePreflightEventWrapper", "FindEvents"})
        if name == "FindEvents":
            self.label = "inter"
        else:
            self.label = "bound"
        super(at_time, self).do_trans(evl=evl)


class avoid_end(Modifier):
    def __init__(self):
        super().__init__(Event)
        self.signature.add_sig(posname(1), Node, True)

    def do_trans(self, evl=False):
        inp = self.input_view(posname(1))
        ot, it = inp.outypename(), inp.typename()
        if not evl:
            do_transform_graph(inp, add_yield=False)  # need to trans input before ToEventCTree
        pref1 = 'NOT(ToEventCTree(label=end,'
        if inp.is_aggregator():
            for i in list(inp.inputs.keys()):
                if is_pos(i):
                    if inp.input_view(i).outypename() in TIME_NODE_NAMES:
                        inp.wrap_input(i, pref1, do_eval=evl)
            if inp.typename() not in ['AND', 'OR', 'NOT']:  # if not AND/OR - defaults to 'AND'
                self.wrap_input(posname(1), 'replace_agg(', suf=', AND)', do_eval=evl)
        elif it == 'TEE':
            if ot in TIME_NODE_NAMES:
                inp.wrap_input(posname(1), pref1)
        elif ot in TIME_NODE_NAMES:
            self.wrap_input(posname(1), pref1, do_eval=evl)
        elif evl and inp.constraint_level == 0 and ot == 'Event':
            self.wrap_input(posname(1), 'NOT(ToEventCTree(label=end,EventToTimeInput(', do_eval=evl)

    def exec(self, all_nodes=None, goals=None):
        self.do_trans(evl=True)
        self.set_result(self.input_view(posname(1)))

    def transform_graph(self, top):
        self.do_trans()
        return self, None


# ################################################################################################

#  todo - unfinished work - has not been tested/used yet!!
# at_time: similar to starts_at / ends_at, but not explicitly specifying start or end.
# the parameter can be one or more time point or time ranges
# example notation:
#     - Event1: existing event, scheduled for 9-11
#     - if one time point - t1, if range: b1, e1
# use cases:
#    1 - when used for search, we look for events which intersect with this time
#        if param is time point: the time point is between candidate event's start and end
#            "find event tomorrow at 10" - will match Event1 (starts_at / ends_at will fail to match)
#        if param is range - then (may depend on case?) the range should have non-empty intersection with candidate
#            "find event tomorrow morning" - will match Event1
#    2 - when used to specify new event, this could mean:
#        "schedule a meeting tomorrow morning"
#            - give time suggestions for slots in the morning
#        "schedule a meeting between 9 and 12"
#            - set start/end to 9 - 12
#        how do we know...? maybe by the duration of the range? (e.g. if more than an hour, search slot, else - set
#        start/end)?
#        it's ok not to be able to exactly get the user meaning! - prefer the one which is easier for
#        the user to correct (and not get stuck in a correction loop)
# for matching
#   - we could either translate this to AND/OR conditions on start/end. something like:
#     - for t1:     start<=t1 and end>=t1
#     - for b1, e1: (start<=b1 and end>=b1) or (start<=e1 and end>=e1) or (start>=b1 and end<=e1)
#   - or implement an additional qualifier (operator) INTERSECT, to be implemented at the Event level
#     - or just use "LIKE" to mean this? <---

# class at_time(Modifier):
#     def __init__(self):
#         super().__init__(Event)
#         self.signature.add_sig(posname(1), Node, True)
#
#     def do_trans(self, evl=False):
#         inp = self.input_view(posname(1))
#         ot, it = inp.outypename(), inp.typename()
#         if not evl:
#             trans_graph(inp, add_yield=False)  # need to trans input before ToEventCTree
#         # todo - decide if 'bound' or 'inter' depending on context - as described in comment above
#         pref1 = 'ToEventCTree(label=bound,'
#         if inp.is_aggregator():
#             for i in list(inp.inputs.keys()):
#                 if is_pos(i):
#                     if inp.input_view(i).outypename() in TIME_NODE_NAMES:
#                         inp.wrap_input(i, pref1, do_eval=evl)
#             if inp.typename() not in ['AND', 'OR']:  # if not AND/OR - defaults to 'AND'
#                 self.wrap_input(posname(1), 'replace_agg(', suf=', AND)', do_eval=evl)
#         elif it == 'TEE':
#             if ot in TIME_NODE_NAMES:
#                 inp.wrap_input(posname(1), pref1)
#         elif ot in TIME_NODE_NAMES:
#             self.wrap_input(posname(1), pref1, do_eval=evl)
#         elif evl and inp.constraint_level == 0 and ot == 'Event':
#             self.wrap_input(posname(1), 'ToEventCTree(as_end=True,EventToTimeInput(', do_eval=evl)
#
#     def exec(self, all_nodes=None, goals=None):
#         self.do_trans(evl=True)
#         self.set_result(self.input_view(posname(1)))
#
#     def transform_graph(self, top):
#         self.do_trans()
#         return self, None


class avoid_time(Modifier):
    def __init__(self):
        super().__init__(Event)
        self.signature.add_sig(posname(1), Node, True)

    def do_trans(self, evl=False):
        inp = self.input_view(posname(1))
        ot, it = inp.outypename(), inp.typename()
        if not evl:
            do_transform_graph(inp, add_yield=False)  # need to trans input before ToEventCTree
        pref1 = 'NOT(ToEventCTree(label=bound,'
        if inp.is_aggregator():
            for i in list(inp.inputs.keys()):
                if is_pos(i):
                    if inp.input_view(i).outypename() in TIME_NODE_NAMES:
                        inp.wrap_input(i, pref1, do_eval=evl)
            if inp.typename() not in ['AND', 'OR', 'NOT']:  # if not AND/OR - defaults to 'AND'
                self.wrap_input(posname(1), 'replace_agg(', suf=', AND)', do_eval=evl)
        elif it == 'TEE':
            if ot in TIME_NODE_NAMES:
                inp.wrap_input(posname(1), pref1)
        elif ot in TIME_NODE_NAMES:
            self.wrap_input(posname(1), pref1, do_eval=evl)
        elif evl and inp.constraint_level == 0 and ot == 'Event':
            self.wrap_input(posname(1), 'NOT(ToEventCTree(label=bound,EventToTimeInput(', do_eval=evl)

    def exec(self, all_nodes=None, goals=None):
        self.do_trans(evl=True)
        self.set_result(self.input_view(posname(1)))

    def transform_graph(self, top):
        self.do_trans()
        return self, None


# ################################################################################################
# ####################################### subject modifier #######################################

class has_subject(Modifier):
    def __init__(self):
        super().__init__(Event)
        self.signature.add_sig(posname(1), Node, True)

    def do_trans(self, evl=False):
        inp = self.input_view(posname(1))
        pref = 'Event?(subject=LIKE('
        if inp.is_aggregator():
            for i in list(inp.inputs.keys()):
                if is_pos(i):
                    # this would fail on aggregation input to aggregation
                    it = inp.input_view(i).outypename() if evl else inp.inputs[i].typename()
                    if it in ['Str']:
                        inp.wrap_input(i, pref, do_eval=evl)
            if inp.typename() != 'OR':  # aggregation for positive locations is set to 'OR'
                self.wrap_input(posname(1), 'replace_agg(', suf=', OR)', do_eval=evl)
        else:
            it = inp.typename()
            if it in ['Str']:
                self.wrap_input(posname(1), pref, do_eval=evl)

    def exec(self, all_nodes=None, goals=None):
        self.do_trans(evl=True)
        self.set_result(self.input_view(posname(1)))

    def transform_graph(self, top):
        self.do_trans()
        return self, None


class avoid_subject(Modifier):
    def __init__(self):
        super().__init__(Event)
        self.signature.add_sig(posname(1), Node, True)

    def do_trans(self, evl=False):
        inp = self.input_view(posname(1))
        pref = 'Event?(subject=NOT(LIKE('
        if inp.is_aggregator():
            for i in list(inp.inputs.keys()):
                if is_pos(i):
                    # this would fail on aggregation input to aggregation
                    it = inp.input_view(i).outypename() if evl else inp.inputs[i].typename()
                    if it in ['Str']:
                        inp.wrap_input(i, pref, do_eval=evl)
            if inp.typename() != 'AND':  # aggregation for positive locations is set to 'AND'
                self.wrap_input(posname(1), 'replace_agg(', suf=', AND)', do_eval=evl)
        else:
            it = inp.typename()
            if it in ['Str']:
                self.wrap_input(posname(1), pref, do_eval=evl)

    def exec(self, all_nodes=None, goals=None):
        self.do_trans(evl=True)
        self.set_result(self.input_view(posname(1)))

    def transform_graph(self, top):
        self.do_trans()
        return self, None


# ################################################################################################

class has_status(Modifier):
    def __init__(self):
        super().__init__(Event)
        self.signature.add_sig(posname(1), Node, True)

    def do_trans(self, evl=False):
        inp = self.input_view(posname(1))
        pref = 'Event?(showAs='
        it = inp.typename()
        if it in ['Str']:
            self.wrap_input(posname(1), pref, do_eval=evl)

    def exec(self, all_nodes=None, goals=None):
        self.do_trans(evl=True)
        self.set_result(self.input_view(posname(1)))

    def transform_graph(self, top):
        self.do_trans()
        return self, None


# ################################################################################################
# ########################## id modifier - this is used only for debug! ##########################

# this is used only for debugging, when we want to bypass multistep event description in 'FindEvent'
# the given id must belong to an event which has curr_user as attendee, otherwise find will fail
class has_id(Modifier):
    def __init__(self):
        super().__init__(Event)
        self.signature.add_sig(posname(1), Int, True)

    def exec(self, all_nodes=None, goals=None):
        inp = self.input_view(posname(1))
        d, e = self.call_construct_eval('Event?(id=%s)' % id_sexp(inp), self.context)
        self.set_result(d)


class has_duration(Modifier):
    def __init__(self):
        super().__init__(Event)
        self.signature.add_sig(posname(1), Node, True)

    def do_trans(self, evl=False):
        inp = self.input_view(posname(1))
        ot, it = inp.outypename(), inp.typename()
        if not evl:
            do_transform_graph(inp, add_yield=False)  # need to trans input before ToEventCTree
        pref1 = 'ToEventDurConstr('
        if inp.is_aggregator():
            for i in list(inp.inputs.keys()):
                if is_pos(i):
                    if inp.input_view(i).outypename() == 'Period':
                        inp.wrap_input(i, pref1, do_eval=evl)
            if inp.typename() not in ['AND', 'OR']:  # if not AND/OR - defaults to 'AND'
                self.wrap_input(posname(1), 'replace_agg(', suf=', AND)', do_eval=evl)
        if ot == 'Period':
            self.wrap_input(posname(1), pref1, do_eval=evl)

    def exec(self, all_nodes=None, goals=None):
        self.do_trans(evl=True)
        self.set_result(self.input_view(posname(1)))

    def transform_graph(self, top):
        self.do_trans()
        return self, None


class avoid_duration(Modifier):  # TODO:
    def __init__(self):
        super().__init__(Event)
        self.signature.add_sig(posname(1), Node, True)


# TODO:
#  - duration
#  - clear_field - e.g. "remove all attendees"  or  "find event without attendees" ?
#  - shift_start, shift_end - these get as input an additive value, to be added to the current value
#    (if one exists. else - they are ignored).
#  - change_duration - similar to shift_x


# ################################################################################################
# ###################################### Attendee modifiers ######################################


class with_recipient(Modifier):
    def __init__(self):
        super().__init__(Attendee)
        self.signature.add_sig(posname(1), Node, True)

    def do_trans(self, evl=False):
        inp = self.input_view(posname(1))
        ot, it = inp.outypename(), inp.typename()
        pref1 = 'Attendee?(recipient='
        suf1 = ')'
        # 2. when input is a name, find who it refers to (may initiate a clarification dialog)
        pref2 = 'singleton(refer(Recipient?(name=LIKE(PersonName('
        suf2 = '))),multi=True))'
        # avoid having to do multiple refers for the same TEE - directly wrap the input to refer
        #       TODO: handling of TEE should be more general! We shouldn't have to do it explicitly
        if inp.is_aggregator():
            for i in list(inp.inputs.keys()):
                if is_pos(i):
                    if inp.input_view(i).outypename() == 'Str':
                        inp.wrap_input(i, pref2, suf=suf2, do_eval=evl)
                    if inp.input_view(i).outypename() == 'Recipient':
                        inp.wrap_input(i, pref1, do_eval=evl)
            if inp.typename() not in ['AND', 'OR']:  # if not AND/OR - defaults to 'AND'
                self.wrap_input(posname(1), 'replace_agg(', suf=', AND)', do_eval=evl)
        elif it == 'TEE':
            if ot == 'Str':
                inp.wrap_input(posname(1), pref2, suf=suf2)
            self.wrap_input(posname(1), pref1, do_eval=evl)
        elif ot in ['Str']:
            self.wrap_input(posname(1), pref1 + pref2, suf=suf2 + suf1, do_eval=evl)
        elif ot == 'Recipient':
            self.wrap_input(posname(1), pref1, do_eval=evl)

    def exec(self, all_nodes=None, goals=None):
        self.do_trans(evl=True)
        self.set_result(self.input_view(posname(1)))

    def transform_graph(self, top):
        self.do_trans()
        return self, None


# convert an event (or events) result an input event id (or event ids)
class EventToAttendeeConstraint(Node):
    def __init__(self):
        super().__init__(Attendee)
        self.signature.add_sig(posname(1), Node, True)

    def exec(self, all_nodes=None, goals=None):
        inp = self.input_view(posname(1))
        ot, it = inp.outypename(), inp.typename()
        d_context = self.context
        if ot == 'Node' and inp.is_aggregator():
            ot = inp.get_op_object().typename()
        if ot == 'Event':
            if inp.is_aggregator():
                evs = inp.get_op_objects(typs='Event')
                ats = ['Attendee?(eventid=getattr(id, %s))' % id_sexp(e) for e in evs]
                if ats:
                    s = ats[0] if len(evs) == 1 else 'OR(' + ','.join(ats) + ')'
                    d, _ = self.call_construct_eval(s, d_context)
                    self.set_result(d)
            else:
                d, _ = self.call_construct_eval('Attendee?(eventid=getattr(id, %s))' % id_sexp(inp), d_context)
                self.set_result(d)
        elif ot == 'Int':
            if inp.is_aggregator():
                evs = inp.get_op_objects(typ='Int')
                ats = ['Attendee?(eventid=%s)' % id_sexp(e) for e in evs]
                if ats:
                    s = ats[0] if len(evs) == 1 else 'OR(' + ','.join(ats) + ')'
                    d, _ = self.call_construct_eval(s, d_context)
                    self.set_result(d)
            else:
                d, _ = self.call_construct_eval('Attendee?(eventid=%s)' % id_sexp(inp), d_context)
                self.set_result(d)


# express the idea that the attendee participated in an event
# input can be one of:
#  - event id  (or function returning an event id)      ---> Attendee?(eventid=input)
#  - Event (or function returning an Event)             ---> Attendee?(eventid=getattr(id, input))
#  - an aggregation event ids                           ---> Attendee(eventid=ANY(input))
#  - an aggregation of Events / event ids ---> Attendee?(eventid=ANY(SET(getattr(id, input1), getattr(id, input2),...)))
#  - an event modifier                   ---> Attendee?(eventid=ANY(FindEvents(input)))
#  - an aggregation of event modifiers   ---> Attendee?(eventid=ANY(FindEvents(input)))
# Note - in case an aggregate (OR/SET) - by default interpret this as OR - true if participated in any of the events
#        - do we need AND as well? ("a participant who attended ALL the events with condX" ?)
class participated_in(Modifier):
    def __init__(self):
        super().__init__(Attendee)
        self.signature.add_sig(posname(1), Node, True)

    def do_trans(self, evl=False):
        inp = self.input_view(posname(1))
        ot, it = inp.outypename(), inp.typename()
        if ot == 'Node' and inp.is_aggregator():
            ot = inp.get_op_object().typename()
        if not evl:
            if inp.is_modifier_tree('Event'):
                self.wrap_input(posname(1), 'FindEvents(')
        else:  # evl
            if ot in ['Event', 'Int']:
                self.wrap_input(posname(1), 'EventToAttendeeConstraint(', do_eval=True)

    def exec(self, all_nodes=None, goals=None):
        self.do_trans(evl=True)
        self.set_result(self.input_view(posname(1)))

    def transform_graph(self, top):
        self.do_trans()
        return self, None
