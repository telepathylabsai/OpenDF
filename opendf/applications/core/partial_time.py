"""
Functions and classes to deal with partially defined time objects.
"""

from datetime import date, time, datetime, timedelta

# similar to the python time, date, datetime, but allowing for default values
# for now we don't have PartialTime and PartialDate.

# PartialDateTime implements the concept of partially specified time point (NOT duration).
#  - examples: "9AM",  "june", "monday 9:30", "december 2020"
# Time can be specified at different resolutions (year, month, day, hour, minute)
# Two ways (there are more) to think about partial datetime are:
# 1. A big calendar at the minute level - each minute has a square.
#    A full specification will have all the squares blank, except for one black square.
#    A partial specification will have multiple squares black:
#      - giving only year, e.g. 2020, will mark all squares (minutes) of that year
#      - giving only minute, e.g. 23, will mark the 23rd minute of every hour, of every day, of every month...
#      - giving only month, e.g. June, will mark all the squares of June, for every year.
# 2. A 5-digit number, where only some digits are given (and the rest are '*')
#    e.g. ***5*, 9*7*4
# Notice that each way is associated with some intuitions, which not always coincide.
#
# There is a minor twist to dates compared to numbers - we have "parallel" ways to represent the same date - by day
# of month or day of week + week of month (and potentially also month of year / month of quarter + quarter...).
#
# python time/date/datetime objects can be directly translated to PartialDateTime, but not necessarily the reverse.
# We use this class to perform comparisons (between PartialDateTime objects, or with python time objects).
# Unlike fully specified time, there is no "full order" over partially specified time:
#   - i.e. for two PartialDateTime objects t1, t2  it is possible that both t1>=t2 and t1<=t2 are not true.
#     e.g. neither 9AM<=2nd June  or 9AM>=2nd June. Similarly, neither  *1*** < ***5*  nor *1*** < ***5*;
#   - in this case, we say both t1<=t2 and t2<=t1 are false (binary comparisons), but we also allow fuzzy comparisons
#     which will return True/False/Maybe;
#
# In principle, when specifications are not full for both objects, it is (often) impossible to compare between them.
# In practice, under some intuitions/constraints, it is possible to do comparisons, sometimes.
# Intuitively, there are many cases where it seems possible, but that intuition needs to be formalized.
# Rather than ask IF t1<t2, we better ask WHEN ARE WE WILLING TO SAY that t1<t2 - we can be more strict or more lax,
# depending on the usage. Ideally, we could formalize our intuitions so that we can automatically select the correct
# level of strictness for a given comparison (and then just use the standard '<' python expression), but we may
# still want to call a specific comparison version for some cases.
# In any case, comparison start at the MSF (most significant field) and progresses towards the LSF (least ...), possibly
# reaching a decision before checking all fields.
#
# From the perspective of the black squares on the calendar, or numbers with missing digits,
# we can think of 4 levels of strictness:
#   1. L1: e.g.
#        - 2021 June < 2021 July - every black square in t1 is before every black square in t2
#        - 25*** < 27*** - no matter what the missing digits are, t1<t2
#        practically this means we don't allow missing values before reaching a decision
#   2. L2: e.g.
#        - monday < tuesday : each square in t1 has a "naturally matching" square in t2, such that sq1<sq2
#        - **3** < **4**
#        if all other fields are the same (which is the "natural matching" we use), then this holds.
#        practically - this means we allow missing values before reaching a decision, but only if the
#        same values are missing in both t1 and t2
#   3. L3: e.g:
#        - 9AM < 11AM Wednesday
#        - 12**3 < **456
#        practically - allow missing values in either t1 OR t2 before reaching a decision - ignore positions where
#        a value is missing.
#   4. L4:
#        similar to L3, but demand that there are some common fields in the two times
#
# depending on the intersection of fields present in the specifications (and the level of strictness),
# two objects may or may not be comparable.
#
# It is more natural for the specified fields of PartialDateTime to be adjacent fields -
#    for example, if we want to use PartialDateTime as the boundary of an interval,
#    - e.g. "after 9:30" (meaning every day, month, year) makes more sense than "after June 9AM"
#      (ambiguous - meaning after 9AM every day in June every year? after 1st june 9AM until year end every year?...)
#    - in this case it may be better to split 9AM June to two PartialDateTime objects


# PartialInterval is used to represent partially specified time intervals (again - these are NOT durations).
#   - examples: "december", "monday morning", "9:00-12:00", "monday to Thursday"
# intervals have different types - they can represent a point, a ray, or a specific interval (with start and end)
# for rays and start/end intervals, boundary inclusion can be specified (but is not yet consistently implemented).
# Two extensions to the "basic" intervals:
#  - negative types: 'neq' (not equal to a point), 'nitv' - not in the interval start-end  (so PartialInterval may
#                     actually represent something which is not a contiguous interval
#  - composed intervals: CompPtInterval: ANDs and ORs of PartialIntervals (potentially deeper composition)
#                        again, potentially resulting in non-contiguous intervals

# for now - not complete implementation for week / dow, and meridiem.
# also missing - seconds, quarters, decades, centuries, millennium, ...
from opendf.applications.core.exceptions.python_exception import PartialDateTimeException, PartialIntervalException

MINIMUM_VALID_YEAR = 2000
MAXIMUM_VALID_YEAR = 2030

neg_typ = {'lt': 'ge', 'le': 'gt', 'gt': 'le', 'ge': 'lt', 'eq': 'neq', 'itv': 'nitv'}

maybe = 3  # fuzzy value for comparison - could mean unknown / not-applicable / ...

days_of_week = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']


def dow_to_name(i):
    """
    Gets the day of the week based on the index `i`. Such as 1: Monday, ..., 7: Sunday.

    :param i: the index of the day
    :type i: int
    :return: the day of the week
    :rtype: str
    """
    return days_of_week[i - 1]


def incomparable(i, j):
    return (i is None and j is not None) or (i is not None and j is None)


def contradict(i, j):
    return i != j and (i is not None and j is not None)


class PartialDateTime:

    def __init__(self, year=None, month=None, day=None, dow=None,
                 hour=None, minute=None, mode=None, pt=None, other=None, check=False):
        """
        If `pt` or `other` are given, values will be taken from there (python time / other PartialTime),
        but will be overridden by any given non-None values
        """
        self.year = year
        self.month = month
        self.day = day
        # TODO: add week - e.g. first/second/... week of the month. add logic for wk+dow in functions!
        self.week = None  # week TODO: e.g. week= 1,2,3,4,-1 (-1 for last week of the month)
        self.dow = dow  # day of week
        self.hour = hour  # 24h format
        self.minute = minute
        # self.meridiem = meridiem  # for now - let the user worry about meridiem,
        # and assume hours are given correctly in 24h range
        self.mode = mode  # we need to store the mode, since qualifiers (like '<') may need it

        if pt:
            if isinstance(pt, (date, datetime)):
                self.year = pt.year if self.year is None else self.year
                self.month = pt.month if self.month is None else self.month
                self.day = pt.day if self.day is None else self.day
            if isinstance(pt, (time, datetime)):
                self.hour = pt.hour if self.hour is None else self.hour
                self.minute = pt.minute if self.minute is None else self.minute

        if other:
            self.year = other.year if self.year is None else self.year
            self.month = other.month if self.month is None else self.month
            self.day = other.day if self.day is None else self.day
            self.hour = other.hour if self.hour is None else self.hour
            self.minute = other.minute if self.minute is None else self.minute

        if check and self.valid_time_values() != True:
            raise PartialDateTimeException(self.valid_time_values())

    def __repr__(self):
        params = []
        if self.year:
            params.append('yr=%s' % self.year)
        if self.month:
            params.append('mn=%s' % self.month)
        if self.day:
            params.append('dy=%s' % self.day)
        if self.dow:
            params.append('wd=%s' % self.dow)
        if self.hour:
            params.append('hr=%s' % self.hour)
        if self.minute:
            params.append('mt=%s' % self.minute)
        return '<' + ', '.join(params) + '>'

    def describe_time(self, mode=None):
        hr, mt = self.hour, self.minute
        mt = '0' if mt is None else '%02d' % mt
        hr = '00' if hr is None else '%s' % hr
        return '%s:%s' % (hr, mt)

    def describe_date(self, mode=None):
        s = '/'.join(['%d' % i if i is not None else '?' for i in [self.year, self.month, self.day]])
        if self.dow is not None:
            s = dow_to_name(self.dow) + ' ' + s
        return s

    def describe_timedate(self, mode=None):
        s = self.describe_date() if self.has_date_values() else ''
        if self.has_time_values():
            s += ' ' + self.describe_time()
        return s

    def msf_lsf(self):
        """
        Return most and least significant specified fields.
        """
        v = self.has_values()
        h = [i for i, j in enumerate(v) if j]
        if not h:
            return None, None
        return h[0], h[1]

    def valid_time_values(self):
        yr, mn, dy, dw, hr, mt = self.get_values()
        if yr and (yr < MINIMUM_VALID_YEAR or yr > MAXIMUM_VALID_YEAR):
            return 'Invalid year %d' % yr
        if mn and (mn < 1 or mn > 12):
            return 'Invalid month %d' % mn
        if dy:
            if dy < 1 or dy > 31:
                return 'Invalid day %d' % dy
            # add logic for date/month combinations, if month given
        if dw and (dw < 1 or dw > 7):
            return 'Invalid dow %d' % dw
        if hr and (hr < 0 or hr > 24):  # should we include 24? 0?
            return 'Invalid hour %d' % hr
        if mt and (mt < 0 or mt > 60):  # should we include 60?
            return 'Invalid minute %d' % mt
        return True

    # can we use this as an interval boundary? some combinations don't make sense - e.g "after monday 2022"
    def valid_boundary(self, mode=None):
        if self.is_complete():
            return True
        if self.is_empty():
            return False
        yr, mn, dy, dw, hr, mt = self.has_values()
        if self.has_only_date():
            if yr and not mn and (dy or dw):  # 'after monday 2020'
                return False
            if mn and dw and not dy:  # 'after monday in january'
                return False
            return True
        elif self.has_only_time():
            return True
        else:
            if mt and not hr and self.has_date_values():  # after january, minutes=30
                return False
            if hr and not dy and (mn or yr):  # after 9AM on january
                return False
        return True

    # are two partialTime objects comparable?
    # e.g. t1=Monday, t2=2021 are not comparable
    # depends on mode
    # TODO: deal with dow
    def comparable(self, other, mode=None):
        mode = mode if mode and any([i in mode for i in ['L1', 'L2', 'L3', 'L4', 'L5']]) else 'L4'
        if mode == 'L3':
            return True
        yr1, mn1, dy1, dw1, hr1, mt1 = self.get_values()
        yr2, mn2, dy2, dw2, hr2, mt2 = other.get_values()
        if mode == 'L1':  #
            # no missing value (stop at different actual value)
            if yr1 is None or yr2 is None:
                return False
            if yr1 == yr2:
                if mn1 is None or mn2 is None:
                    return False
                if mn1 == mn2:
                    if dy1 is None or dy2 is None:
                        return False
                    if dy1 == dy2:
                        if hr1 is None or hr2 is None:
                            return False
                        if hr1 == hr2:
                            if mt1 is None or mt2 is None:
                                return False
            return True
        if mode == 'L2':  # if value is missing, it has to be missing for both times (stop at different actual value)
            if yr1 != yr2 and (yr1 is None or yr2 is None):
                return False
            if yr1 == yr2:
                if mn1 != mn2 and (mn1 is None or mn2 is None):
                    return False
                if mn1 == mn2:
                    if dy1 != dy2 and (dy1 is None or dy2 is None):
                        return False
                    if dy1 == dy2:
                        if hr1 != hr2 and (hr1 is None or hr2 is None):
                            return False
                        if hr1 == hr2:
                            if mt1 != mt2 and (mt1 is None or mt2 is None):
                                return False
            return True
        if mode == 'L5':  # if value is missing, it has to be missing for both times - for ALL fields, except minutes
            if yr1 != yr2 and (yr1 is None or yr2 is None):
                return False
            if mn1 != mn2 and (mn1 is None or mn2 is None):
                return False
            if dy1 != dy2 and (dy1 is None or dy2 is None):
                return False
            if hr1 != hr2 and (hr1 is None or hr2 is None):
                return False
            return True
        if mode == 'L4':  # must have SOME non-None fields in common
            if yr1 and yr2:
                return True
            if mn1 and mn2:
                return True
            if dy1 and dy2:
                return True
            if hr1 is not None and hr2 is not None:
                return True
            if mt1 is not None and mt2 is not None:
                return True
            return False

    # missing values allowed only if same value is missing in both. **4** < **5** but not *34** < **5**
    def fuzzy_lt_L2(self, other, mode=None):
        yr1, mn1, dy1, dw1, hr1, mt1 = self.get_values()
        yr2, mn2, dy2, dw2, hr2, mt2 = other.get_values()
        first = True  # is the value inspected the first non-null value seen?
        if incomparable(yr1, yr2):
            return maybe
        if yr1 and yr2:
            if yr1 < yr2:
                return True
            first = False
        if yr1 == yr2:
            if incomparable(mn1, mn2):
                return maybe
            if mn1 and mn2:
                if mn1 < mn2:
                    return True
                first = False
            if mn1 == mn2:
                if incomparable(dy1, dy2) or incomparable(dw1, dw2):
                    return maybe
                if dy1 and dy2:
                    if dy1 < dy2:
                        return True if mn1 is not None or first else maybe  # 5th jan < 6th jan,  but not  5th 2020 < 6th 2020
                    first = False
                if not dy1 and not dy2 and (dw1 and dw2):
                    if dw1 < dw2:
                        return True if self.week is not None or first else maybe  # TODO: add week logic
                    first = False
                if (dy1 == dy2 and not dw1 and not dw2) or (not dy1 and not dy2 and dw1 == dw2):
                    if incomparable(hr1, hr2):
                        return maybe
                    if hr1 and hr2:
                        if hr1 < hr2:
                            return True if (dy1 is not None or dw1 is not None) or first else maybe
                        first = False
                    if hr1 == hr2:
                        if mt1 is not None and mt2 is not None:
                            if mt1 < mt2:
                                return True if hr1 is not None or first else maybe
                        # todo - some logic considering None minutes as :00?
        return False

    def fuzzy_lt_L3(self, other, mode=None):
        """
        Performs laxer comparison on a field by field way. Ignores missing fields - *34** < 2*5**.
        """
        yr1, mn1, dy1, dw1, hr1, mt1 = self.get_values()
        yr2, mn2, dy2, dw2, hr2, mt2 = other.get_values()
        if yr1 and yr2 and yr1 < yr2:
            return True
        elif yr2 == yr1 or not yr1 or not yr2:
            if mn1 and mn2 and mn1 > mn2:
                return True
            elif not mn1 or not mn2 or mn2 == mn1:
                if dy1 and dy2 and dy1 < dy2:
                    return True
                if dw1 and dw2 and dw1 < dw2:
                    return True
                elif (dy2 == dy1 or not dy1 or not dy2) and (dw2 == dw1 or not dw1 or not dw2):
                    if hr1 is not None and hr2 is not None and hr1 < hr2:
                        return True
                    elif hr2 == hr1 or hr1 is None and hr2 is None:
                        if mt1 is not None and mt2 is not None and mt1 < mt2:
                            return True
        return False

    # fuzzy comparison - Less Than. Return True/False/Maybe
    # mode - selects between L2 / L3 (do we need L1?)
    #        by default - L2, unless self OR other are complete (but not both) - then L3.
    #        if both are complete, then just use pythons' datetime's comparison
    def fuzzy_lt(self, other, mode=None):
        if self.is_complete() and other.is_complete():  # possibly day/dow_week are different
            return self.to_pdatetime() < other.to_pdatetime()
        if mode is not None:
            if mode == 'L2':
                return self.fuzzy_lt_L2(other, mode)
            elif mode == 'L3':
                return self.fuzzy_lt_L3(other, mode)
        if (other.is_complete() and self.valid_boundary(mode)) or (self.is_complete() and other.valid_boundary(mode)):
            # when one object is fully specified, we interpret the other as a constraint to be matched to it
            return self.fuzzy_lt_L3(other, mode)
        return self.fuzzy_lt_L2(other, mode)

    # we may not be able to just rely on using lt(other, self).
    # for now we do.
    # def fuzzy_gt(self, other, mode=None):
    #     # if not self.comparable(other):
    #     #     return Maybe
    #     yr1, mn1, dy1, dw1, hr1, mt1 = self.get_values()
    #     yr2, mn2, dy2, dw2, hr2, mt2 = other.get_values()
    #     if self.is_complete():
    #         if other.is_complete():  # possibly day/dow_week are different
    #             return self.to_pdatetime() > other.to_pdatetime()
    #         return False  # TODO: add logic for dow/week
    #     first = True  # is the value inspected the first non null value seen?
    #     if incomparable(yr1,yr2):
    #         return Maybe
    #     if yr1 and yr2:
    #         if yr1 > yr2:
    #             return True
    #         first = False
    #     if yr1 == yr2:
    #         if incomparable(mn1, mn2):
    #             return Maybe
    #         if mn1 and mn2:
    #             if mn1 > mn2:
    #                 return True
    #             first = False
    #         if mn1 == mn2:
    #             if incomparable(dy1, dy2) or incomparable(dw1, dw2):
    #                 return Maybe
    #             if dy1 and dy2:
    #                 if dy1 > dy2:
    #                     return True if mn1 is not None or first  else Maybe
    #                 first = False
    #             if not dy1 and not dy2 and (dw1 and dw2):
    #                 if dw1 > dw2:
    #                     return True if self.week is not None or first else Maybe
    #                 first = False
    #             if (dy1 == dy2 and not dw1 and not dw2) or (not dy1 and not dy2 and dw1 == dw2):
    #                 if incomparable(hr1, hr2):
    #                     return Maybe
    #                 if hr1 and hr2:
    #                     if hr1 > hr2:
    #                         return True if (dy1 is not None or dw1 is not None) or first else Maybe
    #                     first = False
    #                 if hr1 == hr2:
    #                     if mt1 is not None and mt2 is not None:
    #                         if mt1 > mt2:
    #                             return True if hr1 is not None or first else Maybe
    #     return False

    def __eq__(self, other):
        if not self.comparable(other):
            return False
        yr1, mn1, dy1, dw1, hr1, mt1 = self.get_values()
        yr2, mn2, dy2, dw2, hr2, mt2 = other.get_values()
        return yr1 == yr2 and mn1 == mn2 and dy1 == dy2 and dw1 == dw2 and hr1 == hr2 and mt1 == mt2

    # do the two objects contradict on any field where they are both non None?
    # less strict that EQ
    def contradict(self, other):
        yr1, mn1, dy1, dw1, hr1, mt1 = self.get_values()
        yr2, mn2, dy2, dw2, hr2, mt2 = other.get_values()
        return contradict(yr1, yr2) or contradict(mn1, mn2) or contradict(dy1, dy2) or \
               contradict(dw1, dw2) or contradict(hr1, hr2) or contradict(mt1, mt2)

    def __lt__(self, other):
        v = self.fuzzy_lt(other)
        return False if v == maybe else v

    # def __gt__(self, other):
    #     v = self.fuzzy_gt(other)
    #     return False if v == Maybe else v

    def __ne__(self, other):
        return self != other

    def __le__(self, other):
        return not (self.contradict(other)) or self < other

    def __ge__(self, other):
        return not (self.contradict(other)) or self > other

    def get_time_values(self):
        return self.hour, self.minute

    def get_date_values(self):
        return self.year, self.month, self.day, self.dow

    def get_values(self):
        return self.year, self.month, self.day, self.dow, self.hour, self.minute

    def has_time_values(self):
        return self.hour is not None, self.minute is not None

    def has_date_values(self):
        return self.year is not None, self.month is not None, self.day is not None, self.dow is not None

    def has_values(self):
        return self.year is not None, self.month is not None, self.day is not None, self.dow is not None, \
               self.hour is not None, self.minute is not None  # , self.meridiem is not None

    def is_complete_time(self, mode=None):
        # TODO: meridiem? some mode to interpret no minutes as minutes==0?
        return self.hour is not None and self.minute is not None

    def is_complete_date(self):
        return self.year is not None and self.month is not None and self.day is not None

    def is_complete(self, mode=None):
        return self.is_complete_date() and self.is_complete_time(mode)

    def is_empty(self):
        """
        No value is filled.
        """
        if self.year is None and self.month is None and self.day is None and self.dow is None and \
                self.hour is None and self.minute is None:
            return True
        return False

    def has_only_time(self):
        """
        Has time values but no date values.
        """
        if self.hour is not None or self.minute is not None:
            if self.year is None and self.month is None and self.day is None and self.dow is None:
                return True
        return False

    def has_only_date(self):
        """
        Has date values but no time values.
        """
        if self.year is not None or self.month is not None or self.day is not None or self.dow is not None:
            if self.hour is None and self.minute is None:
                return True
        return False

    # has full specification of day of month -
    #   either date (e.g. 5th of the month) or month week + day of week (e.g. 3rd Monday of the month)
    def has_dom(self):
        """
        Day of month specified.
        """
        return self.day is not None or (self.dow is not None and self.week is not None)

    def to_ptime(self, hr=None, mt=None, pt=None):
        """
        Convert to datetime.time.
        Return None if not complete.
        Uses supplied default values to overwrite None values (but self is not changed!).
        """
        if self.is_complete_time():
            return time(self.hour, self.minute)
        if pt and isinstance(pt, (time, datetime)):
            hr, mt = pt.hour, pt.minute
        hour = hr if self.hour is None else self.hour
        minute = mt if self.minute is None else self.minute
        if hour is not None and minute is not None:
            return time(hour, minute)
        return None

    def to_pdate(self, yr=None, mn=None, dy=None, pt=None):
        """
        Converts to datetime.date.
        """
        if self.is_complete_date():
            return date(self.year, self.month, self.day)
        if pt and isinstance(pt, (date, datetime)):
            yr, mn, dy = pt.year, pt.month, pt.day
        year = yr if self.year is None else self.year
        month = mn if self.month is None else self.month
        day = dy if self.day is None else self.day
        if year is not None and month is not None and day is not None:
            return date(year, month, day)
        return None

    def to_pdatetime(self, yr=None, mn=None, dy=None, hr=None, mt=None, pt=None):
        """
        Converts to datetime.datetime.
        """
        dt = self.to_pdate(yr, mn, dy, pt)
        if dt:
            tm = self.to_ptime(hr, mt, pt)
            if tm:
                return datetime.combine(dt, tm)
        return None

    def fill_missing_values(self, yr=None, mn=None, dy=None, dw=None, hr=None, mt=None, pt=None):
        """
        Uses supplied default values to fill None values (self is changed).
        Single values override `pt`.
        """
        if self.is_complete():
            return
        if pt and isinstance(pt, (time, datetime)):
            hr = pt.hour if hr is None else hr
            mt = pt.minute if mt is None else mt
        if pt and isinstance(pt, (date, datetime)):
            yr = pt.year if yr is None else yr
            mn = pt.month if mn is None else mn
            dy = pt.day if dy is None else dy
        self.year = yr if self.year is None else self.year
        self.month = mn if self.month is None else self.month
        self.day = dy if self.day is None else self.day
        self.dow = dw if self.dow is None else self.dow
        self.hour = hr if self.hour is None else self.hour
        self.minute = mt if self.minute is None else self.minute

    def time_str(self):
        hr = '?' if self.hour is None else str(self.hour)
        mt = '?' if self.minute is None else '%02d' % self.minute
        return ':'.join([hr, mt])

    def date_str(self):
        dy = '?' if self.day is None else str(self.day)
        mn = '?' if self.month is None else str(self.month)
        yr = '?' if self.year is None else str(self.year)
        return '/'.join([yr, mn, dy])

    def datetime_str(self):
        return self.date_str() + '_' + self.time_str()

    def delta_to(self, other):
        """
        Gets Ptimedelta from self to `other`.
        """
        if self.comparable(other, 'L5'):
            yr1, mn1, dy1, dw1, hr1, mt1 = self.get_values()
            yr2, mn2, dy2, dw2, hr2, mt2 = other.get_values()
            days, secs = 0, 0
            if yr1:
                days += 365 * (yr2 - yr1)
            if mn1:
                days += 30 * (mn2 - mn1)  # <<< not quite...
            if dy1:
                days += dy2 - dy1
            if dw1 and dw2 and not dy1 and not mn1:
                if dw1 > dw2:  # assumes other > self
                    dw2 += 7
                days += dw2 - dw1
            if hr1:
                secs += 3600 * (hr2 - hr1)
            if mt1:
                secs -= 60 * mt1
            if mt2:
                secs += 60 * mt2
            return timedelta(days, secs)
        return None

    # TODO: do we need different modes?
    # - e.g. add 300 days to June 12
    #    depending on usage - we may want either
    #    - a 'mod' calculation,
    #    - or just give december 31? - e.g. when filling interval end?
    def add_delta(self, delta, mode=None):
        """
        Returns a new defaultDateTime with its fields increased by delta (delta is datetime.timedelta),
        assuming self is valid for adding delta.

        :param delta: the delta
        :type delta: timedelta
        """
        neg_delta = delta.days * 24 * 60 * 60 + delta.seconds < 0

        if self.is_complete():
            return PartialDateTime(pt=self.to_pdatetime() + delta)
        yr, mn, dy, dw, hr, mt = self.has_values()

        if self.has_only_date():
            if self.is_complete_date():
                p = datetime.combine(self.to_pdate(), time(0, 0)) + delta
                return PartialDateTime(pt=p.date())
            elif yr and mn:
                p = datetime.combine(date(self.year, self.month, 1), time(0, 0)) + delta
                return PartialDateTime(pt=p.date())
            elif mn and not yr:
                d = dy if dy else 1
                p = datetime.combine(date(MINIMUM_VALID_YEAR, self.month, d), time(0, 0)) + delta
                if p.year == MINIMUM_VALID_YEAR:
                    return PartialDateTime(month=p.month, day=p.day)
                else:  # beyond year-end, but we don't know which year - so set to last day of year
                    if mode == 'mod':
                        return PartialDateTime(month=p.month, day=p.day)
                    else:
                        if neg_delta:
                            return PartialDateTime(month=1, day=1)
                        else:
                            return PartialDateTime(month=12, day=31)
            else:
                raise PartialDateTimeException('add_delta - wrong argument')
        elif self.has_only_time():
            # ignore year/month/day - do a modulus addition
            seconds = delta.seconds
            if delta.days != 0:
                seconds = 24 * 60 * 60 if delta.days > 0 else -24 * 60 * 60
            dlt = min(seconds, 24 * 60 * 60)
            h, m = dlt // 3600, (dlt // 60) % 60
            hh = self.hour if hr else 1
            mm = self.minute if mt else 0
            p = datetime(MINIMUM_VALID_YEAR, 1, 1, hh, mm) + timedelta(seconds=h * 3600 + m * 60)
            if p.day == 1:  # did not go beyond day
                if hr:
                    mm = p.minute if mt else None
                    return PartialDateTime(hour=p.hour, minute=mm)
                else:  # no hour given
                    if p.hour == hh:  # did not overstep hour
                        return PartialDateTime(minute=p.minute)
                    elif mode == 'mod':
                        return PartialDateTime(minute=p.minute)
                    else:
                        if neg_delta:
                            return PartialDateTime(minute=0)
                        else:
                            return PartialDateTime(minute=59)
            else:  # overstepped day
                if mode == 'mod':
                    hh = p.hour if hr else None
                    mm = p.minute if mt else None
                    return PartialDateTime(hour=hh, minute=mm)
                else:
                    if neg_delta:
                        return PartialDateTime(hour=0 if hr else None, minute=0 if mt else None)
                    else:
                        if hr and mt:
                            return PartialDateTime(hour=23, minute=59)
                        else:
                            return PartialDateTime(hour=24 if hr else None, minute=59 if mt else None)
        else:  # for all else - for now just return the 'mod' answer - fix as needed
            dt = self.to_pdatetime(MINIMUM_VALID_YEAR, 1, 1, 0, 1, 0)
            d = dt + delta
            year = d.year if yr else None
            month = d.month if mn else None
            day = d.day if dy else None
            hour = d.hour if hr else None
            minute = d.minute if mt else None
            return PartialDateTime(year, month, day, None, hour, minute)


class PartialInterval:

    def __init__(self, start=None, end=None, typ=None, incl=None, mode=None, delta=None, neg=False, info=None):
        """
        Start and end are partialTime or datetime/date/time.
        typ - what kind of interval - ['eq', 'gt', 'lt', 'ge', 'le', 'itv']
        incl - what inclusion type - ['()', '[]', '(]', '[)']
        mode - not used yet, but could include hints for comparison
        TODO: there is a confusion with mode - inclusion mode / comparison mode / both ... - clarify!
        explicit_start, explicit end - (may be redundant)

        :param delta: if given, then a second side will be added to single-sided intervals - (start:start+delta) or
        (end-delta:end)  (clipping at the appropriate resolution - e.g. start=12:10 -> (12:10, 23:59]
        """
        if start and isinstance(start, (date, time, datetime)):
            start = PartialDateTime(start)
        if end and isinstance(end, (date, time, datetime)):
            end = PartialDateTime(end)
        self.explicit_start = False  # was the start given explicitly or extrapolated automatically
        self.explicit_end = False
        if not typ or typ not in ['eq', 'gt', 'lt', 'ge', 'le', 'itv']:
            typ = 'itv' if start and end else 'eq'
        if not incl or incl not in ['()', '[]', '(]', '[)']:
            incl = '[]'
        if neg:
            typ = neg_typ[typ]
        self.incl = incl
        self.typ = typ
        self.mode = mode
        self.info = info  # optional, store additional info
        if not start and not end:
            raise PartialIntervalException('partialInterval needs at least one of start/end')
        if start and not start.valid_boundary():
            raise PartialIntervalException('start boundary is invalid')
        if end and not end.valid_boundary():
            raise PartialIntervalException('end boundary is invalid')
        if end and not start:
            start, end = end, start

        if start and end:
            self.typ = typ
            if not start.comparable(end, mode):
                raise PartialIntervalException('start/end values are incompatible')
            if start > end:
                start, end = end, start
            self.explicit_start = True
            self.explicit_end = True
            self.start = start
            self.end = end
            # we need to store the mode, since qualifiers (like '<') may need it
        elif start:  # TODO: fix one-sided boundary according to new definition!!
            # if one-sided - then give only start, with the appropriate mode
            if typ in ['eq', 'neq']:
                self.start = start
                self.end = start
                self.incl = '[]'
                self.explicit_start = True
                self.explicit_end = True
            elif typ in ['lt', 'le']:
                self.explicit_end = True
                self.end = start
                self.start = start.add_delta(timedelta(days=-delta.days, seconds=-delta.seconds)) if delta else start
                self.incl = '[)' if typ == 'lt' else '[]'
            else:  # gt, ge
                self.explicit_start = True
                self.start = start
                self.end = start.add_delta(delta) if delta else start
                self.incl = '(]' if typ == 'gt' else '[]'

    def comparable(self, other, mode=None):
        if isinstance(other, PartialDateTime):
            return self.start.comparable(other, mode)
        return self.start.comparable(other.start, mode)  # assuming start and end are comparable, if either is itv,
        # and that comparable is transitive

    def __repr__(self):
        if self.typ == 'itv':
            return self.incl[0] + '%s,%s' % (self.start, self.end) + self.incl[1]
        return '%s(%s)' % (self.typ, self.start)

    def __eq__(self, other):
        if not self.comparable(other):
            return False
        return self.typ == other.typ and self.start == other.start and self.end == other.end and self.incl == other.incl

    def compatible(self, other, neg_self=False, neg_other=False, mode=None, mindur=None):
        """
        Checks if two intervals are compatible (assuming both interval play the same role - e.g. start / end /...).

        If the two intervals don't play a symmetric role, assume self takes precedence over other.

        neg_self, neg_other - if `True`, then we invert the intervals self / other and check if they are compatible
        negation introduces two new types - neq, nitv.

        mindur - if not None, this is the minimum duration required for two intervals to overlap for them to be
        compatible."""
        # TODO: 'comparable' mode may depend on the typs! (e.g. if both are 'eq' vs. lt/gt...)
        if not self.comparable(other, mode):
            return True  # ? at least not contradictory. maybe return None?
        styp = neg_typ[self.typ] if neg_self else self.typ
        otyp = neg_typ[other.typ] if neg_other else other.typ
        if styp=='neq' and self.start and self.start.is_complete() and self.end and \
                self.end == self.start:
            if otyp=='eq' and (not other==self):
                return True
            if otyp=='neq':  # and other.start and other.start.is_complete() and other.end and other.end == other.start:
                return True
        intersects = self.intersect(other)
        if styp == 'eq':
            if otyp not in ['neq', 'nitv']:
                return False
            return not intersects
        if styp == 'neq':
            return not intersects
            # TODO: if other is itv including this point?
        if styp == 'itv':
            if otyp not in ['neq', 'nitv']:
                return False
            return not intersects
        if styp == 'nitv':
            return not intersects
        if otyp == 'eq':
            return False  # already took care of styp=eq/neq. all others - incompatible
        if otyp == 'neq':
            return not intersects
        if otyp == 'nitv':
            return not intersects
        if otyp == 'itv':
            return False

        if styp in ['lt', 'le']:
            if otyp in ['lt', 'le']:
                return False
            # otyp is gt/ge
            if self.end < other.start:  # use fuzzy_lt(mode)?
                return False
            # "mathematically", two intervals are compatible if one is >=x and the other <=x (intersecting at one point)
            # practically, they probably are not compatible (e.g. constraint pruning) - this can be controlled by 'mode'
            # return True if styp == 'le' and otyp == 'ge' and self.start == other.end else other.start<self.end
            # mindur: even if there is a non-zero overlap between the intervals, if it's "small enough" we take
            #   it to mean that the other is an unwanted restriction
            if mindur and self.end.is_complete() and other.start.is_complete() \
                    and self.end.to_pdatetime() - other.start.to_pdatetime() < mindur:
                return False
            # special case - for specific values, if
            return other.start < self.end
        else:  # styp in ['gt', 'ge']
            if otyp in ['gt', 'ge']:
                return False
            # otyp is lt/le
            if other.end < self.start:  # use fuzzy_lt(mode)?
                return False
            if mindur and self.start.is_complete() and other.end.is_complete() \
                    and other.end.to_pdatetime() - self.start.to_pdatetime() < mindur:
                return False
            # return True if styp == 'ge' and otyp == 'le' and self.end == other.start else self.start < other.end
            return self.start < other.end

    def intersect_point(self, p, mode, ignore_incl=False, handle_neg=False):
        """
        Does the interval intersect with a point? `False` if not comparable or no intersection; else `True`.
        """
        if not p.comparable(self.start, mode) or not p.comparable(self.end, mode):
            return False  # throw exception?
        if handle_neg and self.typ == 'nitv':
            return not self.intersect_point(p, mode, ignore_incl, False)
        if ignore_incl:
            return self.start <= p <= self.end
        if p > self.start or ('[' in mode and p == self.start):
            if p < self.end or (']' in mode and p == self.end):
                return True
        return False

    def intersect(self, other, mode=None, ret_inter=False, ignore_incl=True, mindur=None, handle_neg=False):
        """
        Does interval intersect with point or interval? `False` if not comparable or no intersection; else returns
        intersection interval.
        """
        if isinstance(other, PartialDateTime):
            return self.intersect_point(other, mode, ignore_incl, handle_neg)
        else:  # interval
            if not other.start.comparable(self.start, mode) or not other.end.comparable(self.end, mode):
                return False  # throw exception?
            if handle_neg and self.typ in ['neq', 'nitv'] or other.typ in ['neq', 'nitv']:
                if self.typ == 'nitv':
                    if other.typ not in ['nitv', 'neq']:
                        s1 = PartialInterval(start=self.start, typ='le')
                        s2 = PartialInterval(start=self.end, typ='ge')
                        return s1.intersect(other, mode, False, True, mindur, False) or \
                               s2.intersect(other, mode, False, True, mindur, False)
                    return True
                if self.typ == 'neq':
                    if other.typ == 'eq' and other.start == self.start:
                        return False
                    return True
                if other.typ == 'nitv':
                    o1 = PartialInterval(start=other.start, typ='le')
                    o2 = PartialInterval(start=other.end, typ='ge')
                    return o1.intersect(other, mode, False, True, mindur, False) or \
                           o2.intersect(other, mode, False, True, mindur, False)
                if other.typ == 'neq' and self.typ == 'eq' and self.start == other.start:
                    return False
                return True
            else:
                if self.end < other.start or self.start > other.end:
                    return False
                if ignore_incl:
                    return True
                if other.start <= self.start:
                    if other.end >= self.start:
                        if other.end == self.start and ('(' in self.incl or ')' in other.incl):
                            return False
                        if not ret_inter:
                            return True
                        mb = '[' if '[' in self.incl and '[' in other.incl else '('
                        me = ']' if ']' in self.incl and ']' in other.incl else ')'
                        e = other.end if other.end < self.end else self.end
                        return PartialInterval(start=self.start, end=e, mode=mb + me)
                else:
                    if (')' in self.incl or '(' in other.incl) and self.end == other.start:
                        return False
                    if not ret_inter:
                        return True
                    mb = '[' if '[' in self.incl and '[' in other.incl else '('
                    me = ']' if ']' in self.incl and ']' in other.incl else ')'
                    e = other.end if other.end < self.end else self.end
                    return PartialInterval(start=other.start, end=e, mode=mb + me)

    def bounds(self, other, mode=None, ignore_incl=True):
        """
        Checks if the other interval is bounded (wholly included) by self.
        """
        if not other.start.comparable(self.start, mode) or not other.end.comparable(self.end, mode):
            return False  # throw exception?
        if other.start < self.start or other.end > self.end:
            return False
        if ignore_incl:
            return True
        if other.start == self.start and '(' in self.incl and '[' in other.incl:
            return False
        if other.end == self.end and ')' in self.incl and ']' in other.incl:
            return False
        return True

    def length(self):
        """
        Timedelta between start and end.
        """
        return self.start.delta_to(self.end)

    #
    # remember - there is no complete order on intervals -
    #
    def strictly_after(self, other, mode=None):
        """
        Checks if self is STRICTLY after `other`. Remember, there is no complete order on intervals. If `x` is not
        strictly after `y`, does NOT mean `x` is before `y`, or even that `x` is not partially after `y`.
        """
        if not other.start.comparable(self.start, mode) or not other.end.comparable(self.end, mode):
            return False
        styp, otyp = self.typ, other.typ
        if styp in ['neq', 'nitv'] or otyp in ['neq', 'nitv']:
            return False
        return self.start > other.end

    def strictly_before(self, other, mode=None):
        """
        Checks if self is STRICTLY before `other`. Remember, there is no complete order on intervals. If `x` is not
        strictly before `y`, does NOT mean `x` is after `y`, or even that `x` is not partially before `y`.
        """
        if not other.start.comparable(self.start, mode) or not other.end.comparable(self.end, mode):
            return False
        styp, otyp = self.typ, other.typ
        if styp in ['neq', 'nitv'] or otyp in ['neq', 'nitv']:
            return False
        return self.end < other.start
