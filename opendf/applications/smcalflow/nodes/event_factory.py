"""
Event factories to create event suggestions based on the constraints.
"""
import logging
from abc import ABC, abstractmethod
from datetime import timedelta, datetime
from typing import Optional

import sqlalchemy
from sqlalchemy import select, not_, func, distinct

from opendf.applications.core.nodes.time_nodes import describe_Pdatetime, Pdatetime_to_sexp, is_holiday, \
    Pdate_to_Pdatetime, round_Ptime, DateTime, next_work_time
from opendf.applications.core.partial_time import PartialInterval
from opendf.applications.smcalflow.database import Database, time_in_holiday, time_in_off_hours, time_bad_for_subject, \
    select_event_with_overlap
from opendf.applications.smcalflow.domain import time_ok_for_subj
from opendf.applications.smcalflow.exceptions.df_exception import BadEventConstraintException, NoEventSuggestionException, \
    MultipleEventSuggestionsException
from opendf.parser.pexp_parser import escape_string
from opendf.utils.database_utils import get_database_handler
from opendf.applications.smcalflow.storage_factory import StorageFactory
from opendf.applications.smcalflow.time_utils import has_out_time, get_event_times_str, DateTimeIterator, skip_minutes
from opendf.graph.nodes.node import Node, create_node_from_dict
from opendf.utils.utils import id_sexp, comma_id_sexp
from opendf.defs import get_system_datetime

logger = logging.getLogger(__name__)
storage = StorageFactory.get_instance()


class EventFactory(ABC):
    """
    Defines an event factory.
    """

    @abstractmethod
    def create_event_suggestion(self, root, parent, avoid_id, prm=None) -> Node:
        """
        Creates an event suggestion, based on the constraints.

        :param root: the root node # TODO: improve description
        :type root: Node
        :param parent: the parent node # TODO: improve description
        :type parent: Node
        :param avoid_id: an event id in order to avoid collision. It is useful when updating an existing event,
        in this case, the `avoid_id` should be the id of the event to be updated, allowing the system to avoid
        checking for constraint collisions between the new 'updated' event and the old 'out-of-date' event
        :type avoid_id:
        :param prm: not used, ** deprecated? **
        :type prm:
        :return: the suggested event node
        :rtype: Node
        """
        pass


class SimpleEventFactory(EventFactory):
    """
    Defines a simple approach for event suggestions.
    """

    # noinspection PyMissingOrEmptyDocstring
    def create_event_suggestion(self, root, parent, avoid_id, prm=None) -> Node:
        # root must not be None!
        prms = []
        # note that there is dependence between the fields. For now, we resolve one field at a time (suboptimal), which
        #      may cause the process to rely on the order of fields: e.g. time depends on attendees and location.
        # fields which can have only one (positive) value, could still have multiple values in the constraints.
        # this could happen if the user specified explicitly an OR in some turn.
        #   - For 'subject' - just pick one. If it's wrong, the user can easily correct it. (another option would be to
        #                     ask the user which one, but that will not make the dialog shorter).
        #   - for 'location' - potentially, we could choose a location depending on which one is free. This would
        #                      require choosing location and time together - do that later. for now, just pick one.
        #   - for time - this is the most complicated.
        # Fields which allow multiple (or no) values - just collect the positive values (even if there is an OR)

        # 1. subject - one or none
        pos, neg = root.get_tree_pos_neg_fields('Event', 'subject')
        if pos:
            subj = pos[-1].dat
            prms.append('subject=%s' % id_sexp(pos[-1]))
        else:
            subj = 'meeting'
            prms.append('subject=meeting')

        # 2. location - one or none
        pos, neg = root.get_tree_pos_neg_fields('Event', 'location')
        if pos:
            loc = pos[-1].dat
            prms.append('location=%s' % id_sexp(pos[-1]))
        else:
            loc = 'online'
            prms.append('location=online')

        # 3. attendees - one, multiple, none
        pos, neg = root.get_tree_pos_neg_fields('Event', 'attendees')
        if not pos or storage.get_current_recipient_id() not in [i.inputs['recipient'].get_dat('id') for i in pos]:
            pos.append(storage.get_current_attendee_graph(root.context))  # add current user to pos if not there yet
        if len(pos) > 1:
            prms.append('attendees=' + 'SET(' + comma_id_sexp(pos) + ')')
        else:
            prms.append('attendees=' + id_sexp(pos[0]))
        atts = [i.inputs['recipient'].get_dat('id') for i in pos]

        # 4. for time, we need to take in account SIMULTANEOUSLY: start, end, duration, as well as availability of
        #    all attendees and location.
        #    unlike the other fields, we have to suggest values, which are not explicitly included in the conditions,
        #    and we have to present them to the user for approval.

        st, en, dur = self.get_time_suggestions(root, subj, loc, atts, parent,
                                                avoid_id=avoid_id)  # will throw exception on no/multi suggestions

        slt = 'slot=TimeSlot(' + ','.join([st, en, dur]) + ')'
        prms.append(slt)

        sugg, e = Node.call_construct('Event(' + ','.join(prms) + ')', root.context)

        return sugg

    # get time slot suggestions
    # this will continue to get called, until start and end are uniquely clarified. This can be either:
    #  - they are given explicitly as specific (fully specified) datetime
    #  - the time constraints enforced by user (possibly together with defaults) lead to unique MATCHING time suggestion
    # until we get to that point, we keep giving the user multiple suggestions, and the user reacts by either
    # accepting a suggestion (which then in the next turn will lead to unique match), or adding a new constraint.
    # Currently we suggest start and end separately (should we change this?), but also SELECT start and end separately,
    #  which is not correct (but easier and more efficient) - we should verify that start and end are compatible.
    #  This is practically not so easy, and there are some heuristics which need to be formalized - e.g. how values
    #  which appear only in one of start/end influence the other. e.g.:
    #    from 9AM until Saturday 8AM / from 9AM until Saturday 10AM /
    #    from 9AM Saturday until 10AM /  from 9AM Saturday until 10AM / from 9AM Saturday until December / ...
    # In many cases, some of the fields transfer from one to the other (e.g. if start>X, then also end>X) BUT this is
    #    more complicated when it comes to partial time - for fields which are "practically periodic" (i.e. their
    #    period is less than what the event duration can reasonably be (which can depend on the event)) this transfer
    #    does not apply:
    #      - e.g. start>Monday may not mean end>Monday for a vacation, but for a meeting it may. (easy to implement)
    # The main practical difficulty is that it's too expensive to try and match ALL time points in the calendar
    #   against the constraints (maybe an SQL call could help?) - so we first restrict the search range. This can fail
    # So - the current logic is incomplete, and there are a few shortcuts taken - fix, when relevant use cases show up.
    # will throw exception if no/multi suggestions
    # atts - list of attendee ids,
    # avoid_id - when searching for clashing events, exclude this event (during update - don't count clashes with old
    # event)
    # TODO: decide how to handle "earliest/latest" - should we have them at all? this may be handled by a modifier
    #  which looks at the "suggestions" - so no need to remember this at the create/update/... node.
    def get_time_suggestions(self, root, subj, loc, atts, parent, avoid_id=None, earliest=None, latest=None, mode=None):
        # for efficiency (looping while trying to find a time slot), we make (new) trees stripped to only datetime
        # constraints
        ttree = Node.get_truncated_constraint_tree(root, 'Event', 'TimeSlot', 'slot')
        cstart = Node.get_truncated_constraint_tree(ttree, 'TimeSlot', 'DateTime', 'start')
        cend = Node.get_truncated_constraint_tree(ttree, 'TimeSlot', 'DateTime', 'end')
        dur, _ = ttree.get_tree_pos_neg_fields('TimeSlot', 'duration')
        dur = dur[0].to_Ptimedelta() if dur else None

        spec_start, spec_end, dur, need_start_end, ask_bnd = self.sugg_time_aux_vals(cstart, cend, dur, subj)
        start, end = spec_start, spec_end

        if spec_start and spec_end and spec_start > spec_end:
            raise BadEventConstraintException(
                'Error - requested start time is later than end time - please suggest a different time', parent)
        if ask_bnd is not None:
            dts = self.suggest_date(cstart, cend, ask_bnd, earliest, latest)
            if earliest and spec_start and spec_start > earliest:
                earliest = spec_start
            flt = cstart if ask_bnd else cend
            dir = self.get_search_direction(flt)
            clash = False
            ts = self.search_calendar_times(dts[0], atts, loc, dur, ask_bnd, earliest=earliest,
                                            n_times=50, max_tries=100, subj=subj, avoid_id=avoid_id, filt=flt)
            ts = self.do_filt_suggest_time(ts, None, 3, dir=dir)
            if not ts:  # no match survived. one more chance - don't restrict to work hours
                out_time = has_out_time(flt)
                ts = self.search_calendar_times(dts[0], atts, loc, dur, ask_bnd, earliest=earliest, avoid_id=avoid_id,
                                                n_times=1, subj=subj, filt=flt, out_time=out_time, max_tries=20)
                ts = self.do_filt_suggest_time(ts, None, 3, dir=dir)
            if not ts:
                # no match - one more chance - allow calendar clashes
                out_time = has_out_time(flt)
                ts = self.search_calendar_times(dts[0], atts, loc, dur, ask_bnd, earliest=earliest, avoid_id=avoid_id,
                                                n_times=1, subj=subj, filt=flt, out_time=out_time, max_tries=20,
                                                ignore_clash=True)
                ts = self.do_filt_suggest_time(ts, None, 3, dir=dir)
                if ts:
                    clash = True
            # another option would be to ignore constraint, and show times when there are no calendar clashes
            # another option is soft filtering - use a scoring function (based on constraint and clashes) and sort by
            # score
            if ts:
                mm = 'Your request clashes with existing events. Would you still like to go ahead with any of these ' \
                     'times?' if clash else 'does any of these times look ok?'
                if spec_start:
                    ts = ts[:1]
                    msg = mm + ' NL from %s NL to %s' % (describe_Pdatetime(spec_start), describe_Pdatetime(ts[0]))
                elif spec_end:
                    ts = ts[:1]
                    msg = mm + ' NL from %s NL to %s' % (describe_Pdatetime(ts[0]), describe_Pdatetime(spec_end))
                else:
                    tms = [describe_Pdatetime(t) for t in ts]
                    msg = mm
                    msg = msg + ' NL ' + ' NL '.join(tms)
                md = 'starts_at' if ask_bnd else 'ends_at'
                sg = ['ModifyEventRequest(%s(%s))' % (md, Pdatetime_to_sexp(t)) for t in ts]
                # experimental - add an option for earlier and later
                sg.append('ModifyEventRequest(%s(LT(%s)))?:?prev' % (md, Pdatetime_to_sexp(ts[0])))
                sg.append('ModifyEventRequest(%s(GT(%s)))?:?next' % (md, Pdatetime_to_sexp(ts[-1])))
                dflt = ['rerun(id=%d)' % parent.id]
                if len(ts) == 1:
                    start, end = self.get_sugg_start_end(ts[0], spec_start, spec_end, need_start_end, ask_bnd, dur)
                else:
                    raise MultipleEventSuggestionsException(msg, parent, hints=[], suggestions=dflt + sg)
            else:
                raise NoEventSuggestionException(parent)
        # TODO: make sure start, end, dur are consistent! - need to look at constraint order to decide which one has
        #  precedence!
        st, en, dr = get_event_times_str(start, end, dur)
        return st, en, dr

    # find free times based on calendar of attendants and location
    # start search from a given date, loop forward on time until reaching a limit on #found / #tried
    # advance time - hops of 30 minutes, and stay within work hours/work days unless told otherwise
    # we could add a preference score to each time, and sort by preference
    # TODO: will not work if user asks exact minutes (not rectified to 30 minutes)
    def search_calendar_times(self, dt, att_ids, loc, dur, ask_bnd, earliest, latest=None, n_times=3, avoid_id=None,
                              add_curr_user=True, workday=True, subj=None, filt=None, out_time=False,
                              max_tries=None, ignore_clash=False):
        if is_holiday(dt):
            workday = False
        att_ids = att_ids if att_ids else []
        if add_curr_user:
            curr_id = storage.get_current_recipient_id()
            att_ids = att_ids if curr_id in att_ids else att_ids + [curr_id]
        if not dur:
            dur = timedelta(minutes=30)
        tms = []
        t = Pdate_to_Pdatetime(dt)
        earliest = earliest if earliest else get_system_datetime()
        t = earliest if t < earliest else t
        t = round_Ptime(t, 30)  # TODO: if user specifies exact minutes - don't rectify to 30 minutes.
        m1 = timedelta(seconds=60)  # avoid problems with end of one event just ending when another is starting
        tries = 0
        if filt:
            # filtering requires converting time to a DateTime graph. Creating one datetime and reusing for each time
            tt = DateTime.from_Pdatetime(t, None, register=False)
        for i in range(n_times):
            found = False
            while not found:
                t = next_work_time(t, workday, out_time)
                if ask_bnd:
                    st, en = t + m1, t + dur - m1
                else:
                    st, en = t + m1 - dur, t - m1

                subject_and_time_ok = not subj or time_ok_for_subj(st, subj)
                clash_ok = ignore_clash or self.check_clash(att_ids, st, en, loc, avoid_id)
                if subject_and_time_ok and clash_ok:
                    if filt:
                        tt.overwrite_values(Pdt=t)
                        if filt.match(tt):
                            found = True
                    else:
                        found = True
                if not found:
                    t = t + timedelta(minutes=30)
                    tries += 1
                    if max_tries and tries > max_tries:
                        return tms
            tms.append(t)
            t += timedelta(minutes=30)
            if latest and t > latest:
                return tms
        return tms

    def check_clash(self, attendee_ids, start, end, location, avoid_id):
        if not storage.is_location_free(location, start, end, avoid_id):
            return False
        for i in attendee_ids:
            if not storage.is_recipient_free(i, start, end, avoid_id):
                return False

        return True

    # logic related to suggestion time boundaries
    #   - some events require two boundaries - start AND end  (e.g. vacation, where there is no default duration)
    #   - for some events it's enough to just give one boundary, and the other is guessed based on default duration
    # there are a few options:
    #   - user does not specify any time (start or end) -> suggest start (as well as end, if it needs both start and
    #       end)
    #   - user specifies start - if specification is full:
    #     - if it needs start and end - suggest end. else - we're done
    #   - user specifies end - similarly
    #   - user specifies both start and end - if start is not fully specified - suggest start, else if end not fully
    #      spec...
    def sugg_time_aux_vals(self, cstart, cend, dur, subj):
        """
        :rtype: (datetime, datetime, timedelta, bool, Optional[bool])
        """
        spec_start, spec_end = self.datetime_tree_is_specific(cstart), self.datetime_tree_is_specific(cend)
        dur = spec_end - spec_start if spec_start and spec_end else dur
        if dur and spec_start and not spec_end:
            spec_end = spec_start + dur
        elif dur and spec_end and not spec_start:
            spec_start = spec_end - dur
        need_start_end = True if (cstart and cend) or (subj and self.event_subj_needs_beg_end(subj)) else False
        # ask_bnd : do we need to ask user further clarifications about either of boundaries?
        ask_bnd = None  # None: don't ask,  True: ask about start; False: ask about end
        if (need_start_end and not (spec_start and spec_end)) or not (spec_start or spec_end):
            ask_bnd = (need_start_end and not spec_start and (not cend or spec_end)) or (cstart and not spec_start)
            ask_end = (need_start_end and not spec_end) or (cend and not spec_end)
            ask_bnd = True if not (ask_bnd or ask_end) else ask_bnd  # ask at least for one
        return spec_start, spec_end, dur, need_start_end, ask_bnd

    # check if datetime tree is just a wrapper around a single, full datetime
    # if not - return None, else return the datetime object
    def datetime_tree_is_specific(self, root, mode=None):
        if not root:
            return None
        pos, _ = root.get_pos_neg_objs()
        # TODO: combine fields from multiple DateTime objects
        if len(pos) == 1:
            if pos[0].is_specific(mode):
                itv = self.tree_to_intervals(pos)
                if len(itv) == 1 and itv[0].typ == 'eq':
                    return pos[0].to_Pdatetime()
        return None

    # convert a list of nodes (typically all positive or all negative)
    # for time modifiers - the negation is ABOVE the Event - we don't expect it inside the event
    # the intervals would either be single-sided ("rays"), or double-sided
    # decided not to convert negative to positive, because that could be messy and result in double the number of
    #   intervals.
    # we assume that if there is aggregation, it's only AND's!
    #   (this is good enough to be used during pruning, which excludes OR)
    def tree_to_intervals(self, nodes):
        intervals = []
        for n in nodes:
            if len(n.outputs) > 0:  # should be the case for "normal" constraint tree for time values
                #   (but may not be for other values (like Recipient))!
                nm, par = n.outputs[-1]
                tp = par.typename()
                p = n.to_partialDateTime()
                typ = tp.lower() if tp in ['LT', 'LE', 'GT', 'GE', 'EQ'] else 'eq'
                intervals.append(PartialInterval(p, None, typ=typ))
        return intervals

    # placeholder for smarter logic
    # decide if an event needs specs for both start and end (or just one timepoint is enough), depending on event
    # subject
    def event_subj_needs_beg_end(self, s):
        if 'golf' in s.lower():
            return True
        return False

    # unnecessary detail!
    # "show me a slot earlier than X" - would users prefer to get time slots close to now or to X?
    #   for the case where the user reacts to system suggestions, clearer that the latter
    def get_search_direction(self, root):
        if not root:
            return 'fwd'
        ts = root.get_tree_turns()
        if ts:
            ns = ts[-1].topological_order()
            typs = list(set([i.typename() for i in ns]))
            if ('LT' in typs or 'LE' in typs) and not ('GT' in typs or 'GE' in typs):
                return 'bwd'
        return 'fwd'

    # suggest a date for start/end
    # return a list of possible dates - sorted by order of likelihood
    # only limited logic implemented, but for now seems to work. we're just giving a date recommendation -
    #    if it's not correct, the user can fix it.
    def suggest_date(self, cstart, cend, is_start, earliest=None, latest=None):
        now = get_system_datetime()
        d1 = timedelta(days=1)
        earliest = earliest if earliest and earliest > now else now
        latest = latest if latest else now + timedelta(days=1000)  # long way off
        if latest <= earliest:  # should not happen
            logger.debug('===>latest<earliest??')
            latest = earliest + d1
        dearly = earliest.date()
        dlate = latest.date()
        dnow = now.date()

        tm1, tm2 = (cstart, cend) if is_start else (cend, cstart)

        dates1 = tm1.get_subnodes_of_type('Date') if tm1 else []
        dates2 = tm2.get_subnodes_of_type('Date') if tm2 else []

        # TODO: these dates may hold individual fields (e.g. only month or only day) - need to combine these!
        if not dates1:  # tm1 has no date info - no need to do filtering for date!
            if not dates2:
                pt = [dearly] if dearly == dnow else [dearly, dnow]
                pt = pt + [pt[0] + d1]  # why not
                return pt
            else:
                dt = self.get_possible_dates(tm2, tm2)
                dt2 = self.clip_dates(dt, dearly, dlate)
                if dnow not in dt2:
                    dt2.append(dnow)
                return dt2
        else:  # tm1 has dates
            if not dates2:
                dt = self.get_possible_dates(tm1, tm1)
                dt2 = self.clip_dates(dt, dearly, dlate)
                if dnow not in dt2:
                    dt2.append(dnow)
                return dt2
            else:  # both tm1 and tm2 have dates
                dt_1 = self.get_possible_dates(tm1, tm1)
                dt_2 = self.get_possible_dates(tm2, tm1)
                dt = dt_1 + [i for i in dt_2 if i not in dt_1]
                dt2 = self.clip_dates(dt, dearly, dlate)
                if dnow not in dt2:
                    dt2.append(dnow)
                return dt2

    # tm is a datetime constraint tree
    # if specific - return its date
    # else - return dates which match it
    def get_possible_dates(self, tm, filt):
        # TODO: fix this - tm is now a constraint tree, which may hold separate date fields in different constraints!
        spec = self.datetime_tree_is_specific(tm, mode='date')
        if spec:
            return [spec.date()]
        dates = tm.get_subnodes_of_type('Date')
        if not dates:
            return []
        spt = list(set([i.to_P() for i in dates if i.is_specific()]))  # only objects with date
        pt = list(set([i.to_P() for i in dates if i.is_specific()]))  # copy of same
        # TODO: add logic for partial dates
        d1 = timedelta(days=1)
        pt = sum([[i, i + d1, i - d1] for i in pt], [])
        # d_context = DialogContext()
        ot = [DateTime.from_Pdate(i, None, register=False) for i in pt]
        pt0 = [pt[j] for j, i in enumerate(ot) if filt.match(i, match_miss=True)]
        pt = [i for i in spt if i in pt0]  # rearrange - mentioned dates come first
        pt += [i for i in pt0 if i not in pt]
        return pt

    def clip_dates(self, pt, earliest, latest):
        pt = [i for i in pt if earliest <= i <= latest]
        return pt

    def do_filt_suggest_time(self, sg, filt, n=3, dir=None):
        rev = dir == 'bwd'
        n = min(n, len(sg))
        sg = list(reversed(sg)) if rev else sg
        if not filt:
            return list(reversed(sg[:n])) if rev else sg[:n]
        m = []
        # d_context = DialogContext()
        for t in sg:
            if len(m) < n:
                nd = DateTime.from_Pdatetime(t, None, register=False)
                if filt.match(nd):
                    m.append(t)
        return list(reversed(m)) if rev else m

    # once a time is selected, get start and/or end from it. (all in python format)
    def get_sugg_start_end(self, t, spec_start, spec_end, need_start_end, ask_bnd, dur):
        stime, etime = None, None
        if not dur:
            dur = timedelta(minutes=30)
        if ask_bnd:  # we know it's not None, otherwise would not call make_start_end_nodes
            stime = t
            if need_start_end or (spec_end and t + dur > spec_end):
                etime = t + dur
        else:
            etime = t
            if need_start_end or (spec_start and t - dur < spec_start):
                stime = t - dur
        return stime, etime


def format_solutions_message(completed_solutions, clashed_solutions):
    """
    Formats a message to present the solutions based on the complete and clashed solutions.

    :param completed_solutions: the complete solutions
    :type completed_solutions: List[Tuple[datetime, datetime]]
    :param clashed_solutions: clashed solutions
    :type clashed_solutions: List[Tuple[datetime, datetime]]
    :return: the formatted message
    :rtype: str
    """
    message = ""
    if len(completed_solutions) > 0:
        message += "Does any of these times look ok?"
        message += " NL " + " NL ".join(map(lambda x: describe_Pdatetime(x[0]), completed_solutions))
    if len(clashed_solutions) > 0 and len(completed_solutions) < 3:
        if len(completed_solutions) > 0:
            message += " NL "
        message += "The following times clash with existing events. Would you still like to go ahead " \
                   "with any of these?"
        message += " NL " + " NL ".join(map(lambda x: describe_Pdatetime(x[0]), clashed_solutions))
    return message


class IteratorEventFactory(SimpleEventFactory):
    """
    Class to suggest events based on the constraints.

    This class iterates over a set of possible starts and ends datetime in order to find a pair of start and end that
    satisfies the constraints.
    """

    def __init__(self, number_of_completed_suggestions=3, number_of_clashed_suggestions=5,
                 maximum_number_of_solutions=5):
        """
        Creates an iterator event factory.

        This factory will stop looking for new suggestions after finding `number_of_completed_suggestions`
        of completed suggestions or `number_of_clashed_suggestions` of clashed suggestions, the one that happens first.

        A completed suggestion is a suggestion that does not clash into other events from the attendees AND have a
        suitable subject for the time of the event; otherwise, it is a clashed suggestion.

        :param number_of_completed_suggestions: the maximum number of completed suggestions
        :type number_of_completed_suggestions: int
        :param number_of_clashed_suggestions: the maximum number of clashed suggestions. This factory will stop
        looking for new suggestions after it found `number_of_clashed_suggestions`
        :type number_of_clashed_suggestions: int
        :param maximum_number_of_solutions: the maximum number of solutions that will be returned. The completed
        solutions has priority over the clashed ones
        :type maximum_number_of_solutions: int
        """
        super(IteratorEventFactory, self).__init__()
        self.number_of_completed_suggestions = number_of_completed_suggestions
        self.number_of_clashed_suggestions = number_of_clashed_suggestions
        self.maximum_number_of_solutions = maximum_number_of_solutions

    def get_time_suggestions(self, root, subj, loc, atts, parent, avoid_id=None, earliest=None, latest=None, mode=None):
        # TODO: generalize the duration for complex constraint trees
        ttree = Node.get_truncated_constraint_tree(root, 'Event', 'TimeSlot', 'slot')
        cstart = Node.get_truncated_constraint_tree(ttree, 'TimeSlot', 'DateTime', 'start')
        cend = Node.get_truncated_constraint_tree(ttree, 'TimeSlot', 'DateTime', 'end')
        dur, _ = ttree.get_tree_pos_neg_fields('TimeSlot', 'duration')
        if dur:
            if len(dur) > 1:
                dur = sorted(dur, key=lambda x: x.created_turn, reverse=True)
            dur = dur[0]

        if cstart and cend and dur:
            # TODO: check if the three constraints are incompatible, we only need to throw one constraint way if they
            #  are not compatible
            # the three fields are constrained, which might cause issue, let one constraint go
            # preferably, not the last cited one. For now, simply remove the end
            cend = None

        spec_start, spec_end = self.datetime_tree_is_specific(cstart), self.datetime_tree_is_specific(cend)
        if spec_start and spec_end:
            if spec_start > spec_end:
                raise BadEventConstraintException(
                    'Error - requested start time is later than end time - please suggest a different time', parent)
            else:
                return get_event_times_str(spec_start, spec_end, spec_end - spec_start)

        dur = dur.to_Ptimedelta() if dur else timedelta(minutes=30)

        if earliest and spec_start and spec_start > earliest:
            earliest = spec_start
        if not earliest:
            earliest = get_system_datetime()

        # Creates a start and an end iterator to run over all possible dates starting on earliest
        # It might be optimized to avoid periods not allowed by the constraints, might be tricky for complex constraints
        # If a specific time is given, iterate only over the specif time, otherwise, iterate over all possible dates
        latest = earliest + timedelta(days=365)  # to avoid an infinite loop, only look for event within 1 year range

        # TODO: A big performance improvement can be done here, by constraining the DateTimeIterator to iterate only
        #  over suitable values
        start_iterator = DateTimeIterator(earliest=earliest, latest=latest) if spec_start is None else iter([
            spec_start])
        end_iterator = DateTimeIterator(earliest=earliest, latest=latest) if spec_end is None else iter([spec_end])
        completed_solutions = []
        clashed_solutions = []
        try:
            start = next(start_iterator)
            end = next(end_iterator)
            m1 = timedelta(seconds=60)  # avoid problems with end of one event just ending when another is starting
            att_ids = atts if atts else []
            curr_id = storage.get_current_recipient_id()
            att_ids = att_ids if curr_id in att_ids else att_ids + [curr_id]
            time_node = DateTime.from_Pdatetime(earliest, root.context, register=False)
            start_ok = False
            end_ok = False
            while not start_ok or not end_ok:
                time_node.overwrite_values(Pdt=start)
                if cstart is not None and not cstart.match(time_node):
                    start = next(start_iterator)
                    start_ok = False
                    continue
                else:
                    start_ok = True

                # start was moved forward, end should keep up
                # maybe we should not make too many assumptions on durations right now
                while end < start + dur:
                    end = next(end_iterator)
                time_node.overwrite_values(Pdt=end)
                if cend is not None and not cend.match(time_node):
                    end = next(end_iterator)
                    end_ok = False
                    continue
                else:
                    end_ok = True

                if not cstart or not cend:
                    # Only check for duration if NEITHER start constraint NOR end constraint are present
                    # TODO: duration constraint logic must be improved to account for complex duration constraint trees
                    delta = end - start
                    if delta > dur:
                        # event is too long, increase start
                        start = next(start_iterator)
                        start_ok = False
                        continue
                    if delta < dur:
                        # event is too short, increase end
                        end = next(end_iterator)
                        end_ok = False
                        continue

                # If we get here, everything should be good with start, end and duration
                # check for subject and clashes
                subject_and_time_ok = not subj or time_ok_for_subj(start + m1, subj)
                clash_ok = self.check_clash(att_ids, start + m1, end - m1, loc, avoid_id)
                if not subject_and_time_ok or not clash_ok:
                    # we have a problem with this suggestion, make a small change to it, which will force the while
                    # loop to look for another suitable candidate
                    assert end > start  # just to be sure
                    if not clashed_solutions or start - clashed_solutions[-1][0] >= timedelta(minutes=30):
                        # only consider the clashed solution if it is, at least, 30 minutes apart from the previous
                        # clashed solution (comparing the starts from both solutions)
                        clashed_solutions.append((start, end))
                    start = next(start_iterator)
                    start_ok = False
                    if len(clashed_solutions) >= self.number_of_clashed_suggestions:
                        # we have enough solutions, break here
                        break

                if start_ok and end_ok:
                    assert end > start  # just to be sure
                    completed_solutions.append((start, end))
                    start_ok = False
                    if len(completed_solutions) >= self.number_of_completed_suggestions:
                        # we have enough solutions, break here
                        break
                    else:
                        # we will keep looking for more solutions, skip 30 minutes forward
                        start = skip_minutes(start, start_iterator, timedelta(minutes=30))
        except StopIteration:
            pass

        completed_solutions = completed_solutions[:self.maximum_number_of_solutions]
        clashed_solutions = clashed_solutions[:self.maximum_number_of_solutions - len(completed_solutions)]

        solutions = completed_solutions + clashed_solutions
        if not solutions:
            raise NoEventSuggestionException(parent)

        if len(solutions) == 1:
            start, end = solutions[0]
        else:
            message = format_solutions_message(completed_solutions, clashed_solutions)

            default = ['rerun(id=%d)' % parent.id]
            suggestions = [f"ModifyEventRequest(AND(starts_at({Pdatetime_to_sexp(s)}), "
                           f"ends_at({Pdatetime_to_sexp(e)})))" for s, e in solutions]
            earliest = Pdatetime_to_sexp(min(map(lambda x: x[0], solutions)))
            latest = Pdatetime_to_sexp(max(map(lambda x: x[1], solutions)))
            suggestions.append(f"ModifyEventRequest(ends_at(LT({earliest})))?:?prev")
            suggestions.append(f"ModifyEventRequest(starts_at(GT({latest})))?:?next")

            raise MultipleEventSuggestionsException(message, parent, hints=[], suggestions=default + suggestions)

        dur = end - start
        return get_event_times_str(start, end, dur)


# TODO: for now, we only consider Period nodes as simple duration, as long as they are not inside a qualifier (other
#  than EQ) and are not negate. Maybe we can be less restrictive than that. For instance, we could allow other types
#  of nodes; and allow for 2 * n negations, e.g. NOT(NOT(Period(X))) -> Period(X)
def get_simple_duration(duration_tree):
    """
    Checks if the `duration_tree` is a simple duration. If it is, returns it; otherwise, returns `None`.

    A simple duration is a Period node that is not negated nor under a qualifier different from EQ.

    :param duration_tree: the duration constraint tree
    :type duration_tree: Node
    :return: the simple duration, if it is simple; otherwise, `None`
    :rtype: Optional[Node]
    """
    if duration_tree is None:
        return None

    current = duration_tree
    while len(current.inputs) > 0:
        # the condition is that the input has at least one child,
        # period must have children, so it is safe

        # It is a period, return it
        if current.typename() == "Period":
            return current

        # checking for complex characteristics
        if len(current.inputs) > 1:
            # it is not a period and has more than one input, it is not simple, return None
            return None
        if current.is_qualifier() and current.typename() != "EQ":
            # it is a qualifier, and it is not EQ, it is not simple, return None
            return None
        if current.is_aggregator() and current.typename() == "NOT":
            # it is an aggregator, and it NOT, it is not simple, return None
            return None

        # it is not a period, but it is not complex either
        # move to the first (and only) child, we already checked that there is only one child
        current = next(iter(current.inputs))

    return None


database_handler = get_database_handler()


class DatabaseEventFactory(EventFactory):
    """
    Class to suggest events by transforming a constraint tree into a SQL query and passing the work to a relational
    database management system (DBMS).
    """

    def __init__(self, number_of_completed_suggestions=3, number_of_clashed_suggestions=5,
                 maximum_number_of_solutions=5):
        """
        Creates a database event factory.

        This factory will stop looking for new suggestions after finding `number_of_completed_suggestions`
        of completed suggestions or `number_of_clashed_suggestions` of clashed suggestions, the one that happens first.

        A completed suggestion is a suggestion that does not clash into other events from the attendees;
        otherwise, it is a clashed suggestion.

        :param number_of_completed_suggestions: the maximum number of completed suggestions
        :type number_of_completed_suggestions: int
        :param number_of_clashed_suggestions: the maximum number of clashed suggestions. This factory will stop
        looking for new suggestions after it found `number_of_clashed_suggestions`
        :type number_of_clashed_suggestions: int
        :param maximum_number_of_solutions: the maximum number of solutions that will be returned. The completed
        solutions has priority over the clashed ones
        :type maximum_number_of_solutions: int
        """
        super(DatabaseEventFactory, self).__init__()
        self.number_of_completed_suggestions = number_of_completed_suggestions
        self.number_of_clashed_suggestions = number_of_clashed_suggestions
        self.maximum_number_of_solutions = maximum_number_of_solutions
        self.database = Database.get_instance()

    def create_event_suggestion(self, root, parent, avoid_id, prm=None) -> Node:
        # root must not be None!
        parameters = []

        # 1. subject - one or none - just pick one. If it's wrong, the user can easily correct it.
        pos, neg = root.get_tree_pos_neg_fields('Event', 'subject')
        pos = list(filter(lambda x: x.typename() != 'Empty', pos))
        if pos:
            subj = pos[-1].dat
            parameters.append('subject=%s' % id_sexp(pos[-1]))
        else:
            subj = 'meeting'
            parameters.append(f'subject={subj}')

        # 3. attendees - one, multiple, none
        pos, neg = root.get_tree_pos_neg_fields('Event', 'attendees')
        pos = list(filter(lambda x: x.typename() == 'Attendee', pos))
        if not pos or storage.get_current_recipient_id() not in [i.inputs['recipient'].get_dat('id') for i in pos]:
            pos.append(storage.get_current_attendee_graph(root.context))  # add current user to pos if not there yet
        if len(pos) > 1:
            parameters.append('attendees=' + 'SET(' + comma_id_sexp(pos) + ')')
        else:
            parameters.append('attendees=' + id_sexp(pos[0]))
        atts = [i.inputs['recipient'].get_dat('id') for i in pos if i and 'recipient' in i.inputs]

        all_suggestions, completed_suggestions, clashed_suggestions = \
            self.get_suggestions_from_database(root, root.context, subj, atts, avoid_id)

        if not all_suggestions:
            raise NoEventSuggestionException(parent)

        if len(all_suggestions) == 1 or len(all_suggestions)>0 and prm and 'first_only' in prm:
            suggestion = all_suggestions[0]
            suggested_start = suggestion.suggested_starts_at
            suggested_end = suggestion.suggested_ends_at
            if isinstance(suggested_end, str):
                suggested_end = datetime.strptime(suggested_end, "%Y-%m-%d %H:%M:%S")
            start, end, duration = get_event_times_str(suggested_start, suggested_end, suggested_end - suggested_start)
            slot = f"slot=TimeSlot({','.join([start, end, duration])})"
            parameters.append(slot)
            parameters.append(f"location={suggestion.suggested_location_name}")
        else:
            if len(all_suggestions) <= self.maximum_number_of_solutions:
                # since there are only a few suggestions in total, the suggestions will be all the suggestions
                # sorted by the suggestions with the least amount of clashes on top, then the starting date
                suggestions = sorted(all_suggestions, key=lambda x: (x.attendees_clashes, x.suggested_starts_at))
                completed_solutions = list(filter(lambda x: x.attendees_clashes == 0, suggestions))
                clashed_solutions = suggestions[len(completed_solutions):]
            else:
                completed_solutions = completed_suggestions[:self.maximum_number_of_solutions]
                clashed_solutions = clashed_suggestions[:self.maximum_number_of_solutions - len(completed_solutions)]
                suggestions = completed_solutions + clashed_solutions
            message = format_solutions_message(completed_solutions, clashed_solutions)

            default = ['rerun(id=%d)' % parent.id]
            modify_suggestions = [f"ModifyEventRequest(AND("
                                  f"starts_at({Pdatetime_to_sexp(s.suggested_starts_at)}), "
                                  f"ends_at({Pdatetime_to_sexp(s.suggested_ends_at)}), "
                                  f"at_location({escape_string(s.suggested_location_name)})"
                                  f"))" for s in suggestions]
            earliest = Pdatetime_to_sexp(min(map(lambda x: x.suggested_starts_at, suggestions)))
            latest = Pdatetime_to_sexp(max(map(lambda x: x.suggested_ends_at, suggestions)))
            modify_suggestions.append(f"ModifyEventRequest(ends_at(LT({earliest})))?:?prev")
            modify_suggestions.append(f"ModifyEventRequest(starts_at(GT({latest})))?:?next")

            raise MultipleEventSuggestionsException(message, parent, hints=[], suggestions=default + modify_suggestions)

        event_suggestion, _ = Node.call_construct('Event(' + ','.join(parameters) + ')', root.context)

        return event_suggestion

    def get_suggestions_from_database(self, root, d_context, subject, attendees_ids, ignore_event_id):
        """
        Gets the suggestions for event from transforming the constraints into a SQL query.

        The suggestions are represented as a named tuple with the following format:
        namedtuple(
            0: suggested_starts_at: datetime,
            1: suggested_ends_at: datetime or str,
            2: suggested_duration: float (in seconds),
            3: suggested_location_id: int,
            4: suggested_location_name: str,
            5: (location.)always_free: bool,
            6: in_holiday: bool,
            7: in_off_hours: bool,
            8: bad_for_subject: bool,
            9: attendees_clashes: int
        )

        :param root: the root containing the constraints for the time and location
        :type root: Node
        :param subject: the subject of the event
        :type subject: str
        :param attendees_ids: the list of attendees ids
        :type attendees_ids: List[int]
        :param ignore_event_id: an event id to ignore, in case of an event update, we would like to ignore the event
        that is being updated, so it will not clash with the suggestions
        :type ignore_event_id: int
        :return: three lists containing all the suggestions, suggestions that don't clash into other events and
        suggestions that clash into other events, respectively
        :rtype: Tuple[List[Any], List[Any], List[Any]]
        """
        selection = self.create_database_selection(root, d_context, subject, attendees_ids, ignore_event_id)

        completed_suggestions = []
        clashed_suggestions = []
        all_suggestions = []
        with self.database.engine.connect() as connection:
            minimum_interval = timedelta(minutes=30 - 1)
            last_complete_start = None
            last_clashed_start = None
            for row in connection.execute(selection):
                # filtering in order to reduce the number of suggestions, for instance,
                #  remove suggestions that are close in time e.g. starts at 13:00, 13:05, 13:10...
                #  maybe we should consider close (in time) suggestions if they are on different locations
                all_suggestions.append(row)
                clashed = row.attendees_clashes > 0
                if clashed:
                    if last_clashed_start is None or row.suggested_starts_at - last_clashed_start > minimum_interval:
                        clashed_suggestions.append(row)
                        last_clashed_start = row.suggested_starts_at
                        # early stop
                        if len(clashed_suggestions) >= self.number_of_clashed_suggestions:
                            break
                else:
                    if last_complete_start is None or row.suggested_starts_at - last_complete_start > minimum_interval:
                        completed_suggestions.append(row)
                        last_complete_start = row.suggested_starts_at
                        # early stop
                        if len(completed_suggestions) >= self.number_of_completed_suggestions:
                            break

        return all_suggestions, completed_suggestions, clashed_suggestions

    def create_database_selection(self, root, d_context, subject, attendees_ids, ignore_event_id):
        """
        Creates the selection that will generate the event suggestions.

        The result of this selection must have the following format:
        namedtuple(
            0: suggested_starts_at: datetime,
            1: suggested_ends_at: datetime or str,
            2: suggested_duration: float (in seconds),
            3: suggested_location_id: int,
            4: suggested_location_name: str,
            5: (location.)always_free: bool,
            6: in_holiday: bool,
            7: in_off_hours: bool,
            8: bad_for_subject: bool,
            9: attendees_clashes: int
        )

        :param root: the root containing the constraints for the time and location
        :type root: Node
        :param subject: the subject of the event
        :type subject: str
        :param attendees_ids: the list of attendees ids
        :type attendees_ids: List[int]
        :param ignore_event_id: an event id to ignore, in case of an event update, we would like to ignore the event
        that is being updated, so it will not clash with the suggestions
        :type ignore_event_id: int
        :return: the selection SQL query
        :rtype: Any
        """
        # Graph part
        ttree = Node.get_truncated_constraint_tree(root, 'Event', 'TimeSlot', 'slot')
        cstart, cend, dur, bound, inter = None, None, None, None, None

        if ttree is not None:
            cstart = Node.get_truncated_constraint_tree(ttree, 'TimeSlot', 'DateTime', 'start')
            cend = Node.get_truncated_constraint_tree(ttree, 'TimeSlot', 'DateTime', 'end')
            dur = Node.get_truncated_constraint_tree(ttree, 'TimeSlot', 'Period', 'duration')
            bound = Node.get_truncated_constraint_tree(ttree, 'TimeSlot', None, 'bound')
            inter = Node.get_truncated_constraint_tree(ttree, 'TimeSlot', None, 'inter')  # TODO: should not be possible
        if not cstart or not cend:
            # if bound is None:
            dur: Optional[Node] = dur if dur else Node.call_construct("Period(minute=30)", d_context)[0]
        if not cstart and not cend and not bound and not inter:
            cstart = Node.call_construct_eval("GT(Now())", d_context)[0]

        location_node = Node.get_truncated_constraint_tree(root, 'Event', 'LocationKeyphrase', 'location')

        # if location is busy, reject the suggestion
        if location_node is None:
            location_node, _ = Node.call_construct("LocationKeyphrase(online)", d_context)
        has_location = self.database.has_location(location_node)

        # Database/SQL part

        # Definitions
        join_tables = []
        location_table = Database.LOCATION_TABLE.alias("location_table")
        start_table = Database.POSSIBLE_TIME_TABLE.alias("start_table")
        suggested_starts_at = start_table.columns.point_in_time.label("suggested_starts_at")
        join_tables.append(start_table)

        # if duration is a simple positive constraint with a given period,
        # we can compute suggested_ends_at as suggested_starts_at + duration;
        # this way, we avoid the cartesian product between the start and the end, which dramatically improves
        # performance
        simple_dur = get_simple_duration(dur)
        if simple_dur is None:
            suggested_duration, suggested_ends_at = self.select_duration_and_end(suggested_starts_at, join_tables)
        else:
            duration_delta: timedelta = simple_dur.to_Ptimedelta()
            seconds = duration_delta.total_seconds()
            increment = int(seconds / 60)
            suggested_ends_at = database_handler.database_datetime_offset(
                suggested_starts_at, increment).label("suggested_ends_at")
            suggested_duration = sqlalchemy.sql.expression.bindparam(
                "suggested_duration", seconds).label("suggested_duration")

        if has_location:
            suggested_location_id = location_table.columns.id.label("suggested_location_id")
            suggested_location_name = location_table.columns.name.label("suggested_location_name")
            suggested_location_always_free = location_table.columns.always_free
        else:
            pos, neg = root.get_tree_pos_neg_fields('Event', 'location')
            if pos:
                loc = pos[-1].dat
            else:
                loc = 'online'
            suggested_location_id = sqlalchemy.sql.expression.bindparam("id", -1).label("suggested_location_id")
            suggested_location_name = sqlalchemy.sql.expression.bindparam(
                "suggested_location_name", loc).label("suggested_location_name")
            suggested_location_always_free = sqlalchemy.sql.expression.bindparam(
                "always_free", True).label("always_free")
        selection = select(
            suggested_starts_at, suggested_ends_at, suggested_duration, suggested_location_id,
            suggested_location_name, suggested_location_always_free,
        ).select_from(*join_tables)

        if simple_dur is None:
            # if duration is simple, we guarantee (by definition) that end is bigger than start;
            # otherwise, we have to add a condition to enforce that
            selection = selection.where(suggested_starts_at < suggested_ends_at)

        # 1 - Subject

        # 1.1 - Holiday
        in_holiday = time_in_holiday(suggested_starts_at)
        # 1.2 - Working hours
        in_off_hours = time_in_off_hours(suggested_starts_at)
        # 1.3 - Time suitable for subject
        bad_for_subject = time_bad_for_subject(suggested_starts_at, subject)

        selection = selection.add_columns(in_holiday, in_off_hours, bad_for_subject)

        # 2 - Location
        selection = location_node.generate_sql_where(selection, None, name_field=suggested_location_name)
        if has_location:
            location_subquery = select(Database.LOCATION_TABLE.columns.id).select_from(
                Database.EVENT_TABLE).join(Database.LOCATION_TABLE)
            location_subquery = select_event_with_overlap(suggested_starts_at, suggested_ends_at, location_subquery)
            location_subquery = location_subquery.where(Database.LOCATION_TABLE.columns.always_free == False)
            location_subquery = location_subquery.where(Database.LOCATION_TABLE.columns.id == suggested_location_id)
            if ignore_event_id:
                location_subquery = location_subquery.where(Database.EVENT_TABLE.columns.id != ignore_event_id)
            location_subquery = location_subquery.exists()

            # this might make the query very expensive, if there are only few conditions
            selection = selection.where(not_(location_subquery))

        # 3 - Attendees
        attendees_subquery = select(
            func.count(distinct(Database.EVENT_HAS_ATTENDEE_TABLE.columns.recipient_id)).label("count")
        ).join(Database.EVENT_TABLE).where(
            Database.EVENT_HAS_ATTENDEE_TABLE.columns.recipient_id.in_(attendees_ids))

        attendees_subquery = select_event_with_overlap(suggested_starts_at, suggested_ends_at, attendees_subquery)
        if ignore_event_id:
            attendees_subquery = attendees_subquery.where(Database.EVENT_TABLE.columns.id != ignore_event_id)
        attendees_subquery = attendees_subquery.scalar_subquery()
        selection = selection.add_columns(attendees_subquery.label("attendees_clashes"))

        # 4 - Time
        time_slot, _ = Node.call_construct_eval(create_node_from_dict(
            "TimeSlot", start=cstart, end=cend, duration=dur, bound=bound, inter=inter), d_context)

        selection = time_slot.generate_sql_where(
            selection, Database.EVENT_TABLE.columns.id, start=suggested_starts_at, end=suggested_ends_at)

        # Sorting
        selection = selection.order_by(in_holiday, in_off_hours, bad_for_subject, suggested_starts_at)

        return selection

    def select_duration_and_end(self, suggested_starts_at, join_tables,
                                duration_label="suggested_duration", end_label="suggested_ends_at"):
        """
        Creates the fields for duration and end, based on the start.

        :param suggested_starts_at: the start column
        :type suggested_starts_at: Any
        :param join_tables: the list of tables to be added to the final query, if this method uses a table,
        it must be appended to the list
        :type join_tables: List
        :param duration_label: the label for the duration column
        :type duration_label: str
        :param end_label: the label for the end column
        :type end_label: str
        :return: the duration and end columns, respectively
        :rtype: Tuple[Any, Any]
        """
        end_table = Database.POSSIBLE_TIME_TABLE.alias("end_table")
        suggested_ends_at = end_table.columns.point_in_time.label(end_label)
        join_tables.append(end_table)
        suggested_duration = database_handler.get_database_duration_column(
            suggested_starts_at, suggested_ends_at).label(duration_label)

        return suggested_duration, suggested_ends_at


class DatabaseStartDurationEventFactory(DatabaseEventFactory):
    """
    Class to suggest events by transforming a constraint tree into a SQL query and passing the work to a relational
    database management system (DBMS).

    This class differs from `DatabaseEventFactory` in the way the SQL query is generated.
    Different from `DatabaseEventFactory`, where there is a cartesian product between `start` and `end`, and the
    `duration` is computed as `end - start`; here there is a cartesian product between `start` and `duration`, and the
    `end` is computed as `start + duration`.
    """

    def __init__(self, number_of_completed_suggestions=3, number_of_clashed_suggestions=5,
                 maximum_number_of_solutions=5):
        super().__init__(number_of_completed_suggestions, number_of_clashed_suggestions, maximum_number_of_solutions)

    def select_duration_and_end(self, suggested_starts_at, join_tables,
                                duration_label="suggested_duration", end_label="suggested_ends_at"):
        duration_table = Database.POSSIBLE_DURATION_TABLE.alias("duration_table")
        suggested_ends_at = database_handler.database_datetime_offset(
            suggested_starts_at, duration_table.columns.offset).label(end_label)
        join_tables.append(duration_table)
        suggested_duration = database_handler.get_database_duration_column(
            suggested_starts_at, suggested_ends_at).label(duration_label)
        return suggested_duration, suggested_ends_at
