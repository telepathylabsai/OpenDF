"""
TimeSlot node.
"""
from sqlalchemy import or_

from opendf.applications.smcalflow.nodes.time_nodes import *
from opendf.defs import VIEW, posname
from opendf.applications.smcalflow.exceptions.python_exception import TimeSlotException
from opendf.utils.utils import flatten_list, to_list, Message

SI_START = 10  # partial time interval as start
SI_END = 11
SI_BOUND = 12
SI_INTER = 13
SI_DUR = 14


class slot_interval:
    def __init__(self, iv, obj=None, typ=None, dur=None, durtyp=None, comp=None):
        self.interval = iv  # partial interval (None for dur)
        self.typ = typ  # PT_START/...
        self.dur = dur  # python datedelta for dur, else None
        self.durtyp = durtyp  # 'eq' / 'lt' ...
        self.obj = obj  # the original TimeSlot?()
        self.comp = comp  # compound slot

    si_names = {SI_START: 'start', SI_END: 'end', SI_DUR: 'dur', SI_BOUND: 'bound', SI_INTER: 'inter', }

    def __repr__(self):
        s = '%s %s' % (self.si_names[self.typ], self.interval if self.interval else 'obj=%s' % self.obj)
        return s

    def comparable_slot(self, other, mode=None):
        if self.typ == SI_DUR or other.typ == SI_DUR:
            return True
        return self.interval.comparable(other.interval, mode)

    def compatible_dur(self, other):
        if self.typ != SI_DUR or other.typ != SI_DUR:
            return True
        if self.durtyp == 'eq' or other.durtyp == 'eq':
            return False
        if self.durtyp in ['lt', 'le'] and other.durtyp in ['lt', 'le']:
            return False
        if self.durtyp in ['gt', 'ge'] and other.durtyp in ['gt', 'ge']:
            return False
        if self.durtyp in ['lt', 'le'] and other.durtyp in ['gt', 'ge'] and self.dur >= other.dur:
            return False
        if self.durtyp in ['gt', 'ge'] and other.durtyp in ['lt', 'le'] and self.dur <= other.dur:
            return False
        return True

    def compatible_bound(self, other):
        if self.typ != SI_BOUND or other.typ != SI_BOUND:
            return True
        if not self.interval.comparable(other.interval):
            return True
        if self.interval.intersect(other.interval):  # no negative bounds...
            return True
        return False

    def compatible_inter(self, other):
        if self.typ != SI_INTER or other.typ != SI_INTER:
            return True
        if not self.interval.comparable(other.interval):
            return True
        # always true for positive. For negative may not be true
        siv, oiv = self.interval, other.interval
        if siv.typ == 'nitv':
            if oiv.typ in ['nitv', 'neq']:
                return siv.intersect(oiv)
            else:
                return siv.bounds(oiv)
        if oiv.typ == 'nitv':
            return siv.intersect(oiv)
        if siv.typ in ['eq', 'neq'] and oiv.typ in ['eq', 'neq'] and siv.intersect(oiv):
            return False
        return True

    # update a list for a specific field - add new interval, and possibly remove older, incompatible, ones
    def update_field_list(self, curr, prune):
        upd = []
        typ = self.typ
        for o in curr:
            compat = self.compatible_dur(o) if typ == SI_DUR else \
                self.compatible_bound(o) if typ == SI_BOUND else \
                    self.compatible_inter(o) if typ == SI_INTER else \
                        self.interval.compatible(o.interval)
            if compat:
                upd.append(o)
            elif o not in prune:
                prune.append(o)
        upd.append(self)
        return upd, prune

    # TODO: verify logic for all the prune_xx_list cases

    # curr is a list of bound constraints.
    # self is an interval (of a type not bound - that was already covered in update_field_list).
    # prune bounds which are incompatible with self.
    def prune_bound_list(self, curr, prune):
        upd = []
        typ = self.typ
        for o in curr:
            compat = True
            if typ in [SI_START, SI_END]:
                compat = True if not self.interval.comparable(o.interval) else o.interval.bounds(self.interval)
            elif typ == SI_DUR:
                compat = self.dur > o.interval.length()
            elif typ == SI_INTER:
                compat = False  # TODO:
            if compat:
                upd.append(o)
            elif o not in prune:
                prune.append(o)
        return upd, prune

    def prune_inter_list(self, curr, prune):
        upd = []
        typ = self.typ
        for o in curr:
            compat = True
            if typ == SI_START:
                compat = not self.interval.strictly_after(o.interval)
            elif typ == SI_END:
                compat = not self.interval.strictly_before(o.interval)
            elif typ == SI_DUR:
                compat = True
            elif typ == SI_BOUND:
                compat = False  # TODO:
            if compat:
                upd.append(o)
            elif o not in prune:
                prune.append(o)
        return upd, prune

    # handles only bound, inter, and direct interaction with start - no INDIRECT interaction between start/end/dur
    def prune_start_list_simp(self, curr, prune):
        upd = []
        typ = self.typ
        for o in curr:
            compat = True
            if typ == SI_BOUND:
                compat = not (self.interval.strictly_before(o.interval) or self.interval.strictly_after(o.interval))
            elif typ == SI_INTER:
                compat = not self.interval.strictly_before(o.interval)
            elif typ == SI_END:
                compat = not self.interval.strictly_before(o.interval)  # direct interaction (end before start)
            if compat:
                upd.append(o)
            elif o not in prune:
                prune.append(o)
        return upd, prune

    # handles only bound, inter, and direct interaction with end - no INDIRECT interaction between start/end/dur
    def prune_end_list_simp(self, curr, prune):
        upd = []
        typ = self.typ
        for o in curr:
            compat = True
            if typ == SI_BOUND:
                compat = not (self.interval.strictly_before(o.interval) or self.interval.strictly_after(o.interval))
            elif typ == SI_INTER:
                compat = not self.interval.strictly_after(o.interval)
            elif typ == SI_START:
                compat = not self.interval.strictly_after(o.interval)
            if compat:
                upd.append(o)
            elif o not in prune:
                prune.append(o)
        return upd, prune

    # handles only bound, inter, and direct interaction with end - no INDIRECT interaction between start/end/dur
    def prune_dur_list_simp(self, curr, prune):
        upd = []
        typ = self.typ
        for o in curr:
            compat = True
            if typ == SI_BOUND:
                compat = self.interval.length() < o.dur
            elif typ == SI_INTER:
                compat = True
            if compat:
                upd.append(o)
            elif o not in prune:
                prune.append(o)
        return upd, prune

    # This is called when the latest interval is a bound
    # - the interval is already added to the curr_bound, as the last element.
    # - the curr_bound list does NOT have to be updated - it was updated in the previous turn, and adding a new
    #   bound (which might have pruned a previous bound object) will not cause any more bounds to be pruned
    def prune_lists_by_bound(self, curr_start, curr_end, curr_dur, curr_bound, curr_inter, prune):
        curr_inter, prune = self.prune_inter_list(curr_inter, prune)
        curr_start, prune = self.prune_start_list_simp(curr_start, prune)
        curr_end, prune = self.prune_end_list_simp(curr_end, prune)
        curr_dur, prune = self.prune_dur_list_simp(curr_dur, prune)
        return curr_start, curr_end, curr_dur, curr_bound, curr_inter, prune

    def prune_lists_by_inter(self, curr_start, curr_end, curr_dur, curr_bound, curr_inter, prune):
        curr_bound, prune = self.prune_bound_list(curr_bound, prune)
        curr_start, prune = self.prune_start_list_simp(curr_start, prune)
        curr_end, prune = self.prune_end_list_simp(curr_end, prune)
        curr_dur, prune = self.prune_dur_list_simp(curr_dur, prune)
        return curr_start, curr_end, curr_dur, curr_bound, curr_inter, prune

    def prune_lists_by_start(self, curr_start, curr_end, curr_dur, curr_bound, curr_inter, prune):
        curr_bound, prune = self.prune_bound_list(curr_bound, prune)
        curr_inter, prune = self.prune_inter_list(curr_inter, prune)
        curr_end, prune = self.prune_end_list_simp(curr_end, prune)
        curr_dur, prune = self.prune_dur_list_simp(curr_dur, prune)
        # curr interval (self) is start.
        # find which is the last constraint (from end or dur) which is comparable (compatible?) with it, and prune
        # the "other". for now - aggressively prune the other if comparable
        # TODO: we should prune only if the "other" is incompatible with the combination of self+"last"
        c_end = [o for o in curr_end if self.interval.comparable(o.interval)]
        c_dur = [o for o in curr_dur if self.interval.comparable(o.interval)]
        if c_end and c_dur:
            if c_end[-1].obj.created_turn > c_dur[-1].obj.created_turn:
                curr_dur = [o for o in curr_dur if o not in c_dur]
                prune += c_dur
            else:
                curr_end = [o for o in curr_end if o not in c_end]
                prune += c_end
        return curr_start, curr_end, curr_dur, curr_bound, curr_inter, prune

    def prune_lists_by_end(self, curr_start, curr_end, curr_dur, curr_bound, curr_inter, prune):
        curr_bound, prune = self.prune_bound_list(curr_bound, prune)
        curr_inter, prune = self.prune_inter_list(curr_inter, prune)
        curr_start, prune = self.prune_start_list_simp(curr_start, prune)
        curr_dur, prune = self.prune_dur_list_simp(curr_dur, prune)
        c_start = [o for o in curr_start if self.interval.comparable(o.interval)]
        c_dur = [o for o in curr_dur if self.interval.comparable(o.interval)]
        if c_start and c_dur:
            if c_start[-1].obj.created_turn > c_dur[-1].obj.created_turn:
                curr_dur = [o for o in curr_dur if o not in c_dur]
                prune += c_dur
            else:
                curr_start = [o for o in curr_start if o not in c_start]
                prune += c_start
        return curr_start, curr_end, curr_dur, curr_bound, curr_inter, prune

    def prune_lists_by_dur(self, curr_start, curr_end, curr_dur, curr_bound, curr_inter, prune):
        curr_bound, prune = self.prune_bound_list(curr_bound, prune)
        curr_inter, prune = self.prune_inter_list(curr_inter, prune)
        curr_start, prune = self.prune_start_list_simp(curr_start, prune)
        curr_end, prune = self.prune_end_list_simp(curr_end, prune)
        c_start = [o for o in curr_start if o.interval.comparable(self.interval)]
        c_end = [o for o in curr_end if o.interval.comparable(self.interval)]
        if c_start and c_end:
            if c_start[-1].obj.created_turn >= c_end[-1].obj.created_turn:
                curr_end = [o for o in curr_end if o not in c_end]
                prune += c_end
            else:
                curr_start = [o for o in curr_start if o not in c_start]
                prune += c_start
        return curr_start, curr_end, curr_dur, curr_bound, curr_inter, prune

    def prune_curr(self, curr_start, curr_end, curr_dur, curr_bound, curr_inter, prune):
        typ = self.typ

        # 1. separate update per field
        if typ == SI_START:
            curr_start, prune = self.update_field_list(curr_start, prune)
        elif typ == SI_END:
            curr_end, prune = self.update_field_list(curr_end, prune)
        elif typ == SI_DUR:
            curr_dur, prune = self.update_field_list(curr_dur, prune)
        elif typ == SI_BOUND:
            curr_bound, prune = self.update_field_list(curr_bound, prune)
        elif typ == SI_INTER:
            curr_inter, prune = self.update_field_list(curr_inter, prune)

        # 2. prune with interactions
        # don't try to prune again same type - the interval is already in the curr_... - will prune itself
        if typ == SI_BOUND:
            curr_start, curr_end, curr_dur, curr_bound, curr_inter, prune = \
                self.prune_lists_by_bound(curr_start, curr_end, curr_dur, curr_bound, curr_inter, prune)

        elif typ == SI_INTER:
            curr_start, curr_end, curr_dur, curr_bound, curr_inter, prune = \
                self.prune_lists_by_inter(curr_start, curr_end, curr_dur, curr_bound, curr_inter, prune)

        elif typ == SI_START:
            curr_start, curr_end, curr_dur, curr_bound, curr_inter, prune = \
                self.prune_lists_by_start(curr_start, curr_end, curr_dur, curr_bound, curr_inter, prune)

        elif typ == SI_END:
            curr_start, curr_end, curr_dur, curr_bound, curr_inter, prune = \
                self.prune_lists_by_end(curr_start, curr_end, curr_dur, curr_bound, curr_inter, prune)

        elif typ == SI_DUR:
            curr_start, curr_end, curr_dur, curr_bound, curr_inter, prune = \
                self.prune_lists_by_dur(curr_start, curr_end, curr_dur, curr_bound, curr_inter, prune)

        return curr_start, curr_end, curr_dur, curr_bound, curr_inter, prune


def bound_surround_event(bound, start_column, end_column, selection, kwargs):
    """
    Add conditions to `selection` in order to check if `bound` surrounds the interval defined by `start_column` and
    `end_column`.

    :param bound: the bound
    :type bound: Range
    :param start_column: the start column
    :type start_column: Any
    :param end_column: the end column
    :type end_column: Any
    :param selection: the selection
    :type selection: Any
    :param kwargs: additional parameters
    :type kwargs: Dict[str, Any]
    :return: the new selection, with the surrounding conditions
    :rtype: Any
    """
    qualifier = kwargs.get("qualifier")
    kwargs["qualifier"] = GE()
    selection = bound.input_view("start").generate_sql_where(selection, start_column, **kwargs)
    kwargs["qualifier"] = LE()
    selection = bound.input_view("end").generate_sql_where(selection, end_column, **kwargs)
    kwargs["qualifier"] = qualifier
    return selection


def event_surround_point(start_column, end_column, point, selection, kwargs):
    """
    Add conditions to `selection` in order to check if the event, represented by `start_column` and `end_column`
    surrounds the `point` in time.

    :param start_column: the start column
    :type start_column: Any
    :param end_column: the end column
    :type end_column: Any
    :param point: the point in time
    :type point: Date or Time or DateTime
    :param selection: the selection
    :type selection: Any
    :param kwargs: additional parameters
    :type kwargs: Dict[str, Any]
    :return: the new selection, with the surrounding conditions
    :rtype: Any
    """
    qualifier = kwargs.get("qualifier")
    kwargs["qualifier"] = LE()
    selection = point.generate_sql_where(selection, start_column, **kwargs)
    kwargs["qualifier"] = GE()
    selection = point.generate_sql_where(selection, end_column, **kwargs)
    kwargs["qualifier"] = qualifier
    return selection


class TimeSlot(Node):
    """
    Describes a time slot.
    """

    # TimeSlot unifies values and constraints which describe a time slot object / constraint.
    # The basic object has start, end, and duration; additionally, constraints can specify a (partial) time span
    # which the slot should be bound by or intersect with.
    # Since all these arguments are inter-connected, processing can not be done independently.
    # TimeSlot implements the logic for the interaction between them.
    # In the simplified annotation, we use modifiers to create constraints, so we can expect the following timeslots:
    #  - for an object from the DB - start, end, duration (as one TimeSlot object)
    #    - when converted to a constraint, it will be separated to 3 TimeSlot constraints - for start, end, duration
    #  - from a modifier:
    #    - this translates to a constraint with only one field:
    #       - has_start / has_end / has_duration - start / end / duration only (similarly for the negative ones)
    #          - at least for now, we assume the argument is one of:
    #                  - simple time value:                 DateTime, Date, Time - 9AM
    #                  - qualifier over simple time value:  DateTime, Date, Time - GT(9AM)
    #                  - range:              DateTimeRange, DateRange, TimeRange - Morning(), TimeRange(9AM, 11AM)
    #                       - which is internally converted to AND(GE(start), LE(end))
    #                         so that the default match() will work
    #                  i.e. - the argument can be represented by one interval
    #             - if there are aggregators, they will be outside the modifiers, not inside
    #               - >> any contradictory examples?
    #       - at_time - one argument (time point or interval), simple values, without any operators (quals / aggs)
    #             - e.g. at time(morning()) / at_time(9AM)
    #             - argument can be represented by one interval
    #          the plan is to translate this, depending on context, to either timeslot.bound or timeslot.inter
    #          - find event at_time(time point/range) means intersection
    #               - the point is during the event, or there is an intersection between the event and the range
    #          - create event at_time(range) means bounding interval:
    #               - create event EXACTLY at this range, or sub part of this range

    def __init__(self):
        super().__init__(type(self))
        self.signature.add_sig('start', [Date, Time, DateTime, TimeRange, DateRange, DateTimeRange])
        self.signature.add_sig('end', [Date, Time, DateTime, TimeRange, DateRange, DateTimeRange])
        self.signature.add_sig('duration', Period)
        # 'bound' - means the time slot is bounded to be within a time range
        #           (i.e. both start and end are within that range)
        #           e.g. "create a meeting in the afternoon / tomorrow"
        #         we could interpret point (as opposed to range) input as whole day / month / hour / ... ??
        #         note - "not in the morning" translates to negative 'inter', not 'bound' - no negative bounds
        self.signature.add_sig('bound', [Date, Time, DateTime, TimeRange, DateRange, DateTimeRange], custom=True)
        # 'inter' - means the time slot intersects a time point/range
        #      e.g. "find an event at 10AM / in the afternoon"
        self.signature.add_sig('inter', [Date, Time, DateTime, TimeRange, DateRange, DateTimeRange], custom=True)

    def generate_sql_where(self, selection, parent_id, **kwargs):
        """
        Generates the SQL where conditions to select objects conforming to TimeSlot.

        :param selection: the previous selection
        :type selection: Any
        :param parent_id: the parent id
        :type parent_id: Any
        :param kwargs: the mapping from the database columns to the time slot fields, must contain a mapping for
        start and end
        :type kwargs: Dict[str, Any]
        :return: the SQL query with the conditions
        :rtype: Any
        """
        start_column = kwargs["start"]
        end_column = kwargs["end"]

        if "start" in self.inputs:
            selection = self.input_view("start").generate_sql_where(selection, start_column, **kwargs)

        if "end" in self.inputs:
            selection = self.input_view("end").generate_sql_where(selection, end_column, **kwargs)

        if "duration" in self.inputs:
            selection = self.input_view("duration").generate_sql_where(selection, parent_id, **kwargs)

        # In order for it to work properly, the DateTime, Date or Time must be fully specified
        if "bound" in self.inputs:
            bound = self.input_view("bound")
            if isinstance(bound, Range):
                selection = bound_surround_event(bound, start_column, end_column, selection, kwargs)
            else:
                selection = bound.generate_sql_where(selection, start_column, **kwargs)
                selection = bound.generate_sql_where(selection, end_column, **kwargs)

        # In order for it to work properly, the DateTime, Date or Time must be fully specified
        if "inter" in self.inputs:
            bound = self.input_view("inter")
            if isinstance(bound, Range):
                conditions = []
                # we have start_column twice in the call below, because we want to check if the bound surrounds the
                # start of the event. Same for the end_column
                start = bound.input_view('start')
                end = bound.input_view('end')
                conditions.append(
                    bound_surround_event(bound, start_column, start_column, select(), kwargs).whereclause.self_group())
                conditions.append(
                    bound_surround_event(bound, end_column, end_column, select(), kwargs).whereclause.self_group())
                conditions.append(
                    event_surround_point(start_column, end_column, start, select(), kwargs).whereclause.self_group())
                conditions.append(
                    event_surround_point(start_column, end_column, end, select(), kwargs).whereclause.self_group())
                selection = selection.where(or_(*conditions).self_group())
            else:
                # intersect is a point
                selection = event_surround_point(start_column, end_column, bound, selection, kwargs)

        return selection

    def custom_match(self, nm, obj, iview=VIEW.INT, oview=None, check_level=False, match_miss=False):
        # self is a TimeSlot constraint, obj is a "real" TimeSlot object (not a constraint)
        # since obj is real object, guaranteed that intervals are always comparable
        if nm == 'bound':
            c = self.input_view('bound')  # constraint should be a simple object! (check?)
            pt = c.to_partialInterval()
            si = obj.to_slot_interval().interval
            return pt.bounds(si)
        elif nm == 'inter':
            c = self.input_view('inter')
            pt = c.to_partialInterval()
            si = obj.to_slot_interval().interval
            return pt.intersect(si)
        return True

    def describe(self, params=None):
        s = ''
        obj = []
        pp = [] if params is None else params
        if isinstance(params, dict):
            pp['add_prep'] = 1
        else:
            pp += ['add_prep']
        if 'start' in self.inputs:
            msg = self.input_view('start').describe(pp)
            t, o = msg.text, msg.objects
            if t:
                s += ' starting ' + t
            obj += o
        if 'end' in self.inputs and ('start' not in self.inputs or 'duration' not in self.inputs):
            msg = self.input_view('end').describe(pp)
            t, o = msg.text, msg.objects
            if t:
                s += ' ending ' + t
            obj += o
        if 'duration' in self.inputs:
            msg = self.input_view('duration').describe(params)
            t, o = msg.text, msg.objects
            if t:
                s += ' lasting ' + t
            obj += o
        if 'bound' in self.inputs:
            msg = self.input_view('bound').describe(params)
            t, o = msg.text, msg.objects
            if t:
                s += ' during ' + t
            obj += o
        if 'inter' in self.inputs:
            msg = self.input_view('inter').describe(params)
            t, o = msg.text, msg.objects
            if t:
                s += ' intersecting ' + t
            obj += o
        return Message(s, objects=obj)

    def slot_ctree_str(self, sep_date=True, open_slot=True):
        """
        Converts the timeslot field of an ACTUAL event into ONE timeslot constraint.

        :type sep_date: bool
        :param open_slot: if `True`, create strings for printing (not for construction)
        :type open_slot: bool
        :rtype: List[str]
        """
        prms = []
        if 'start' in self.inputs:
            # TODO: sep_date - separate year/month/day to individual constraints
            #   e.g. if the user specifies month, then we should not prune the whole date (year, day) as well
            st = self.input_view('start')
            s = []
            if 'date' in st.inputs:
                s.append('date=%s' % id_sexp(st.input_view('date')))
            if 'time' in st.inputs:
                s.append('time=%s' % id_sexp(st.input_view('time')))
            if s:
                if sep_date:
                    prms.extend(['start=DateTime(%s)' % i for i in s])
                else:
                    prms.append('start=DateTime(' + ','.join(s) + ')')
        if 'end' in self.inputs:
            # TODO: sep_date - separate year/month/day to individual constraints?
            en = self.input_view('end')
            s = []
            if 'date' in en.inputs:
                s.append('date=%s' % id_sexp(en.input_view('date')))
            if 'time' in en.inputs:
                s.append('time=%s' % id_sexp(en.input_view('time')))
            if s:
                if sep_date:
                    prms.extend(['end=DateTime(%s)' % i for i in s])
                else:
                    prms.append('end=DateTime(' + ','.join(s) + ')')
        if 'duration' in self.inputs:
            prms.append('duration=%s' % id_sexp(self.input_view('duration')))
        # actual object - does not have 'bound', 'inter'
        if not prms:
            return None
        if open_slot:
            return prms
        return ['slot=TimeSlot?(%s)' % p for p in prms]

    @staticmethod
    def get_ptime_and_qual(nd):
        t = nd.typename()
        if nd.not_operator():
            v = nd.to_partialDateTime()
            return v, 'eq'
        if nd.is_qualifier():
            tp = t.lower() if t in ['LT', 'LE', 'GT', 'GE', 'EQ'] else None
            n = nd.input_view(posname(1))
            if tp and n:
                v = n.to_partialDateTime()
                return v, tp
        raise TimeSlotException('Error - get_ptime_val %s\n%s' % (nd, nd.show()))

    @staticmethod
    def input_to_interval(nd, neg=False):
        """
        Converts input to an interval.
        Assumes input is either:
           1. simple time value (Date, Time, DateTime);
           2. simple time value with a qualifier;
           3. AND(x, y) where x,y are of type 2.
        """
        if isinstance(nd, Range):
            nd, _ = Node.call_construct_eval(nd.to_constr_sexp(), nd.context)  # temp context. new nodes will be discarded
        if nd.typename() == 'AND':
            s, e = nd.get_input_views([posname(1), posname(2)])  # verify pos input names...
            if s and e:
                v1, t1 = TimeSlot.get_ptime_and_qual(s)
                v2, t2 = TimeSlot.get_ptime_and_qual(e)
                tt = t1[0] + t2[0]
                if tt in ['lg', 'gl']:  # make sure this corresponds to a valid time range
                    if tt == 'lg':
                        v1, t1, v2, t2 = v2, t2, v1, t1
                    incl = ('(' if t1 == 'gt' else '[') + (')' if t2 == 'lt' else ']')
                    return PartialInterval(v1, v2, incl=incl, neg=neg)
        if nd.not_operator():
            v = nd.to_partialDateTime()
            return PartialInterval(v, None, neg=neg)
        if nd.is_qualifier():
            v, tp = TimeSlot.get_ptime_and_qual(nd)
            return PartialInterval(v, None, tp, neg=neg)
        raise TimeSlotException('Error - input_to_interval %s\n %s' % (nd, nd.show()))

    def to_slot_interval(self, neg=False):
        """
        Converts a TimeSlot to a slot_interval. The input to start, end, bound, inter may be a simple time value,
        or a simple tree (i.e. a tree which can be represented as one interval).
        """
        start, end, dur, bound, inter = self.get_input_views(['start', 'end', 'duration', 'bound', 'inter'])
        if start:
            return slot_interval(TimeSlot.input_to_interval(start, neg), typ=SI_START, obj=self)  # obj=start)
        if end:
            return slot_interval(TimeSlot.input_to_interval(end, neg), typ=SI_END, obj=self)  # , obj=end)
        if bound:
            return slot_interval(TimeSlot.input_to_interval(bound, neg), typ=SI_BOUND, obj=self)  # , obj=bound)
        if inter:
            return slot_interval(TimeSlot.input_to_interval(inter, neg), typ=SI_INTER, obj=self)  # , obj=inter)
        if dur:
            typ, t = dur.typename(), 'eq'
            if typ in ['LT', 'LE', 'GT', 'GE', 'EQ'] and posname(1) in dur:
                dur = dur.input_view(posname(1))
                t = typ.lower()
                t = neg_typ[t] if neg else t
                typ = dur.typename()
            if typ == 'Period':
                d = dur.to_Ptimedelta()
                pt = dur.to_partialDateTime()
                return slot_interval(pt, typ=SI_DUR, dur=d, durtyp=t, obj=self)  # , obj=dur)
        raise TimeSlotException('Error - to_slot_interval %s\n%s' % (self, self.show()))

    @staticmethod
    def to_interval_clusters(t, neg=False):
        """
        For each OR - return all the objects under it as a set of objects.
        """
        typ = t.typename()
        if typ == 'NOT':
            return TimeSlot.to_interval_clusters(t.input_view(posname(1)), not neg)
        elif typ == 'AND':
            iv = []
            for i in t.inputs:
                iv.append(TimeSlot.to_interval_clusters(t.input_view(i), neg)[0])
            return iv
        elif typ == 'OR':
            return [[TimeSlot.to_interval_clusters(t.input_view(i), neg)[0] for i in t.inputs]]
        elif typ == 'TimeSlot':
            return [t.to_slot_interval(neg=neg)]
        else:
            raise TimeSlotException('Error - to comp interval: %s\n%s' % (t, t.show()))

    # do the two clusters have comparable elements?
    # c1, c2 are lists of slot_interval
    @staticmethod
    def comparable_clusters(c1, c2):
        for i1 in to_list(c1):
            for i2 in to_list(c2):
                if i1.comparable_slot(i2, mode='L4'):
                    return True
        return False

    # TODO: verify
    @staticmethod
    def get_prune(turns):
        """
        Finds TimeSlots which need to be pruned.

        This is run on a TimeSlot constraint tree it is possible that the TimeSlot constraint tree is a truncation of a
        different tree (e.g. and Event tree) - in that case, we want to prune the original (Event) tree, not the
        TimeSlot tree, so we return the objects to be pruned, but don't prune the tree.

        Pruning time slots is tricky since the different fields (start/end/duration) are interdependent. The turns in
        the turn tree are assumed to be combined with an AND. If a turn has multiple constraints, unless there is an
        OR in the turn, we extract the separate constraints from the tree and combine them with an AND.

        In case of OR: (note that here we are only concerned with pruning. OR is not a problem for matching...). We
        don't forbid the use of OR, but it can be tricky to prune constraints with OR. The current strategy is to allow
        OR turns but prune previous OR turns if there is a chance they could contradict later turns. If there is an
        OR (or several ORs) (possibly combined with ANDs), we group all the constraints under an OR to a cluster.
        For now, we simply check if there is any later turn which is comparable (i.e. uses intersecting time
        components), and if so, we prune the whole OR cluster. This is overly aggressive, but because of the interaction
        between the different fields, we can't be sure that constraints on different fields don't contradict. If an
        OR cluster survives this, we treat it as if it was an AND - it should not affect the pruning results.

        :return: a list of TimeSlot nodes to be pruned (they are NOT pruned yet - this is done somewhere else)
        """
        turn_ivs = []  # list of lists - intervals for each turn
        all_ivs, turn_bnds, niv = [], [], 0  # intervals for all turns, with indices showing start/end of each turn
        has_ors = []

        prune = []  # list of slot_intervals

        # 1. get intervals / interval-clusters per turn
        for t in turns:
            iv = []
            h = False
            if t:
                if t.get_subnodes_of_type('OR'):
                    iv = TimeSlot.to_interval_clusters(t)
                    h = True
                else:
                    pos, neg = t.get_pos_neg_objs()
                    ipos, prune_pos = TimeSlot.slot_to_interval(pos)
                    ineg, prune_neg = TimeSlot.slot_to_interval(neg, neg=True)
                    # ipos, ineg = [o.to_slot_interval() for o in pos], [o.to_slot_interval(neg=True)
                    #                                                    for o in neg]
                    prune.extend(prune_pos)  # TODO - fix - this is not a slot_interval
                    prune.extend(prune_neg)
                    iv = ipos + ineg
            has_ors.append(h)
            turn_ivs.append(iv)
            turn_bnds.append((niv, niv + len(iv)))
            all_ivs.extend(iv)
            niv += len(iv)

        prune_slots = set()  # slot intervals to prune

        # 2. prune OR clusters - if comparable
        #    after this (aggressive) pruning, there are no comparable OR's left, so it should not
        #    matter if it's interpreted as AND or OR
        for i, ti in enumerate(turn_ivs):
            for j, tj in enumerate(turn_ivs):
                if j > i and ti and tj and (has_ors[i] or has_ors[j]):
                    for ki in ti:
                        for kj in tj:
                            if isinstance(ki, list) or isinstance(kj, list):
                                if TimeSlot.comparable_clusters(ki, kj):
                                    prune_slots.update(set(to_list(ki)))

        # 3. collect intervals which were not pruned
        all_ivs = [i for i in flatten_list(turn_ivs) if i not in prune_slots]

        # 4. collect intervals to prune


        # go over all intervals, from old to new. At each interval:
        #   1. update a (pruned) list of intervals, separately for each one of (start, end, dur);
        #   2. prune previous intervals taking into account interactions between different types.

        curr_start, curr_end, curr_dur, curr_bound, curr_inter = [], [], [], [], []
        for siv in all_ivs:
            curr_start, curr_end, curr_dur, curr_bound, curr_inter, prune = \
                siv.prune_curr(curr_start, curr_end, curr_dur, curr_bound, curr_inter, prune)

        return prune

    @staticmethod
    def slot_to_interval(time_slots, neg=False):
        intervals = []
        prune = []
        for time_slot in time_slots:
            try:
                intervals.append(time_slot.to_slot_interval(neg=neg))
            except TimeSlotException:
                prune.append(time_slot)

        return intervals, prune
