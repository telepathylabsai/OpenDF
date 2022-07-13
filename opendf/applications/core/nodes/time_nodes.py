"""
Core time nodes.
"""

from typing import Tuple

from opendf.applications.smcalflow.stub_data import HOLIDAYS
from opendf.exceptions.debug_exception import DebugDFException
from opendf.exceptions.df_exception import InvalidOptionException, MissingValueException, InvalidResultException
from opendf.applications.core.exceptions.python_exception import CalendarException
from opendf.graph.nodes.framework_operators import EQ, LE, GE, LT, GT
from opendf.graph.nodes.framework_objects import *

from datetime import date, datetime
from opendf.applications.core.partial_time import *
from calendar import monthrange

from opendf.utils.database_utils import get_database_handler
from opendf.utils.utils import id_sexp, str_to_datetime
from opendf.defs import get_system_date, posname, get_system_datetime

TIME_NODE_NAMES = ['DateTime', 'Date', 'Time', 'DateRange', 'TimeRange', 'DateTimeRange']

datetime_components = ['year', 'month', 'day', 'hour', 'minute']
period_components = ['year', 'month', 'week', 'day', 'hour', 'minute']
monthname = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
monthname_full = ['January', 'February', 'March', 'April', 'May', 'June',
                  'July', 'August', 'September', 'October', 'November', 'December']


def last_month_day(yr, mn):
    """
    Gets the number of the last day of the month.

    :param yr: the year
    :type yr: int
    :param mn: the month
    :type mn: int
    :return: the number of the last day of the month
    :rtype: int
    """
    return monthrange(yr, mn)[1]


def week_of_month(dt):
    n = (dt.isocalendar()[1] - dt.replace(day=1).isocalendar()[1] + 1)
    if n < 0:
        n += 52
    return n


# noinspection SpellCheckingInspection
def todays_date():
    """
    Gets today's date as a triple (year, month, day).

    :return: today's date
    :rtype: Tuple[int, int, int]
    """
    t = get_system_date()
    return t.year, t.month, t.day


def tomorrows_date():
    """
    Gets tomorrow's date as a triple (year, month, day).

    :return: tomorrow's date
    :rtype: Tuple[int, int, int]
    """
    t = get_system_date() + timedelta(days=1)
    return t.year, t.month, t.day


def yesterdays_date():
    """
    Gets yesterday's date as a triple (year, month, day).

    :return: yesterday's date
    :rtype: Tuple[int, int, int]
    """
    t = get_system_date() + timedelta(days=-1)
    return t.year, t.month, t.day


def nows_time():
    """
    Gets now's time as a pair (hour, minute).

    :return: now's time
    :rtype: Tuple[int, int]
    """
    t = get_system_datetime()
    return t.hour, t.minute


def ordinal_suffix(n):
    """
    Gets the ordinal suffix for the number `n`.

    :param n: the number
    :type n: int
    :return: the ordinal suffix
    :rtype: str
    """
    if n in [1, 21, 31]:
        return 'st'
    if n in [2, 22]:
        return 'nd'
    if n in [3, 23]:
        return 'rd'
    return 'th'


def round_Ptime(p, res_mn=5):
    p = p.replace(second=0, microsecond=0)
    m = p.minute
    mm = m % res_mn
    if mm > res_mn // 2:
        n = p + timedelta(seconds=60 * (res_mn - mm))
    else:
        n = p - timedelta(seconds=60 * mm)
    return n


def name_to_dow(nm):
    for i, d in enumerate(days_of_week):
        if d.lower() == nm.lower() or (len(nm) == 3 and nm.lower() == d[:3].lower()):
            return i + 1
    raise CalendarException('Bad weekday : %s' % nm)


def name_to_month(nm):
    for i, d in enumerate(monthname_full):
        if d.lower() == nm.lower() or (len(nm) == 3 and nm.lower() == d[:3].lower()):
            return i + 1
    raise CalendarException('Bad month : %s' % nm)


def next_work_time(t, workday, out_time):
    """
    Gets the next work date and time after `t`.

    :param t: the date and time
    :type t: datetime
    :param workday: if `True`, only business days are considered; if `False` any day is considered
    :type workday: bool
    :param out_time: if `True`, 'out-of-time hours' should be considered; if `False`, only business hours are considered
    :type out_time: bool
    :return: the next work date and time after `t`
    :rtype: datetime
    """
    if not out_time:
        h, m = t.hour, t.minute
        if h > 17:
            t = t + timedelta(0, 3600 * (9 + 24 - h) - 60 * m)  # moves the date `t` FORWARD to the next 9 a.m.
        elif h < 9:
            t = t + timedelta(0, 3600 * (9 - h) - 60 * m)  # moves the date `t` FORWARD to the next 9 a.m.
    if workday:
        w = t.isoweekday()
        if w > 5:
            t = t + timedelta(8 - w)  # moves the date forward until the next business day
    return t


def Pdate_to_Pdatetime(p, h=0, m=0):
    return datetime(year=p.year, month=p.month, day=p.day, hour=h, minute=m, second=0, microsecond=0)


def describe_Pdate(t, params=None):
    params = params if params else []
    n = get_system_date()
    m = n + timedelta(days=1)
    s, prep = '', 'on ' if 'prep' in params else ''
    if t.day == n.day and t.year == n.year and t.month == n.month:
        s = 'Today'
        prep = ''
    elif t.day == m.day and t.year == m.year and t.month == m.month:
        s = 'Tomorrow'
        prep = ''
    else:
        s = days_of_week[t.isoweekday() - 1] + ' %d %s' % (t.day, monthname[t.month - 1])
        if t.year != n.year:
            s += ' %d' % t.year
    return prep + s


def describe_Pdatetime(t):
    n = get_system_datetime()
    m = n + timedelta(days=1)
    if t.day == n.day and t.year == n.year and t.month == n.month:
        s = 'Today'
    elif t.day == m.day and t.year == m.year and t.month == m.month:
        s = 'Tomorrow'
    else:
        s = days_of_week[t.isoweekday() - 1] + ' %d %s' % (t.day, monthname[t.month - 1])
        if t.year != n.year:
            s += ' %d' % t.year
    s += ' %d-%02d' % (t.hour, t.minute)
    return s


def Pdatetime_to_sexp(t):
    if isinstance(t, str):
        t = datetime.strptime(t, "%Y-%m-%d %H:%M:%S")
    y, m, d, h, mi = t.year, t.month, t.day, t.hour, t.minute
    return 'DateTime(date=Date(year=%d, month=%d, day=%d), time=Time(hour=%d, minute=%d))' % (y, m, d, h, mi)


def is_holiday(p):
    """
    Checks if `p` is a holiday.

    :param p: the date
    :type p: date
    :return: `True`, if `p` is a holiday; otherwise, `False`
    :rtype: bool
    """
    if p.weekday() >= 5:
        return True

    # add other holidays
    m, d = p.month, p.day
    if (d, m) in HOLIDAYS:
        return True

    return False


#########################################################################################################
#########################################################################################################

database_handler = get_database_handler()


class Time(Node):
    """
    Corresponds to the time (hour, minute) node.
    """

    def __init__(self):
        super().__init__(type(self))
        self.signature.add_sig('hour', Int, match_miss=True)
        self.signature.add_sig('minute', Int, match_miss=True)

    def generate_sql_where(self, selection, parent_id, **kwargs):
        qualifier = kwargs.get("qualifier", EQ())
        if self.is_specific():
            return selection.where(qualifier(database_handler.to_database_time(parent_id),
                                             database_handler.to_database_time(self.to_Ptime())))

        if "hour" in self.inputs:
            selection = self.input_view('hour').generate_sql_where(
                selection, database_handler.database_date_to_hour(parent_id), **kwargs)

        if "minute" in self.inputs:
            selection = self.input_view('minute').generate_sql_where(
                selection, database_handler.database_date_to_minute(parent_id), **kwargs)

        return selection

    def to_partialDateTime(self):
        # assuming no operators around hour/minute. otherwise - use get_op_object()...
        return PartialDateTime(hour=self.get_dat('hour'), minute=self.get_dat('minute'))

    def to_partialInterval(self):
        pt = self.to_partialDateTime()
        return PartialInterval(pt, typ='eq')

    def valid_h_m(self):
        s = self.to_partialDateTime().valid_time_values()
        if s != True:
            raise InvalidResultException("Invalid time generation from node.", self)

    def valid_constraint(self):
        self.valid_h_m()

    def valid_input(self):
        self.valid_h_m()

    def describe(self, params=None):
        return self.to_partialDateTime().describe_time()

    # node is a "real" object, with all values given (and are leaf nodes)
    def is_specific(self):
        if self.get_dat('hour') is not None and self.get_dat('minute') is not None:
            return True
        return False

    def get_time_values(self):
        return self.get_dat('hour'), self.get_dat('minute')

    def get_time_values_with_default(self, hr=None, mt=None, p=None):
        orgp = p
        if not p:
            p = get_system_datetime()
        if not hr:
            hr = p.hour
        if not mt:
            mt = 0 if not orgp else p.minute
        hr = self.get_dat('hour') if 'hour' in self.inputs else hr
        mt = self.get_dat('minute') if 'minute' in self.inputs else mt
        return hr, mt

    def get_datetime_values(self):
        return None, None, None, None, self.get_dat('hour'), self.get_dat('minute')

    def get_datetime_values_with_default(self, yr=None, mn=None, dy=None, hr=None, mt=None, p=None):
        hr, mt = self.get_time_values_with_default(hr, mt, p)
        p = p if p else get_system_datetime()
        yr = p.year if not yr else yr
        mn = p.month if not mn else mn
        dy = p.day if not dy else dy
        return yr, mn, dy, None, hr, mt

    def to_Ptime(self):
        return self.to_partialDateTime().to_ptime()

    def to_datetime_sexp(self, allow_constr=True):
        hr, mt = self.get_time_values()
        t = time_sexp(hr, mt, allow_constr)

    def to_P(self):
        return self.to_Ptime()

    def func_EQ(self, ref, op=None, mode=None):
        return not self.to_partialDateTime().contradict(ref.to_partialDateTime())

    def func_NEQ(self, ref, op=None, mode=None):
        return not self.func_EQ(ref, op=op)

    def func_LT(self, ref, op=None, mode=None):
        return ref.to_partialDateTime() < self.to_partialDateTime()

    def func_GT(self, ref, op=None, mode=None):
        return ref.to_partialDateTime() > self.to_partialDateTime()

    def func_LE(self, ref, op=None, mode=None):
        return self.func_EQ(ref, op=op) or self.func_LT(ref, op=op)

    def func_GE(self, ref, op=None, mode=None):
        return self.func_EQ(ref, op=op) or self.func_GT(ref, op=op)


class DayOfWeek(Node):
    """
    Special type for day of week name.
    """

    def __init__(self):
        super().__init__(type(self))
        self.signature.add_sig(posname(1), Str)

    def generate_sql_where(self, selection, parent_id, **kwargs):
        qualifier = kwargs.get("qualifier", EQ())
        return selection.where(qualifier(database_handler.database_date_to_day_of_week(parent_id), self.to_dow()))

    def valid_input(self):
        dt = self.dat
        if dt is not None:
            if dt not in days_of_week:
                dd = [i.lower() for i in days_of_week] + [i[:3].lower() for i in days_of_week]
                if dt.lower() not in dd:
                    raise InvalidOptionException("DayOfWeek", dt, days_of_week, self)
        else:
            raise MissingValueException(posname(1), self)

    def func_EQ(self, ref, op=None, mode=None):
        sl, rf = self.get_dat(posname(0)), ref.get_dat(posname(0))
        if sl and rf:
            return sl.lower()[:3] == rf.lower()[:3]
        return False

    def to_dow(self):
        d = self.get_dat(posname(1))
        return name_to_dow(d)


class Range(Node):
    """
    Defines a range between a start and an end.
    """

    def generate_sql_where(self, selection, parent_id, **kwargs):
        qualifier: Node = kwargs.get("qualifier")
        qualifier_name = qualifier.typename() if qualifier is not None else "EQ"

        if qualifier_name in {"EQ", "LIKE"}:
            kwargs["qualifier"] = GE()
            selection = self.input_view('start').generate_sql_where(selection, parent_id, **kwargs)
            kwargs["qualifier"] = LE()
            selection = self.input_view('end').generate_sql_where(selection, parent_id, **kwargs)
            kwargs["qualifier"] = qualifier
        elif qualifier_name in {"NEQ"}:
            kwargs["qualifier"] = LT()
            selection = self.input_view('start').generate_sql_where(selection, parent_id, **kwargs)
            kwargs["qualifier"] = GT()
            selection = self.input_view('end').generate_sql_where(selection, parent_id, **kwargs)
            kwargs["qualifier"] = qualifier
        elif qualifier_name in {"LT", "LE"}:
            selection = self.input_view('start').generate_sql_where(selection, parent_id, **kwargs)
        elif qualifier_name in {"GT", "GE"}:
            selection = self.input_view('end').generate_sql_where(selection, parent_id, **kwargs)
        elif qualifier in {"TRUE", "FALSE", "FN"}:
            selection = self.input_view('start').generate_sql_where(selection, parent_id, **kwargs)
            selection = self.input_view('end').generate_sql_where(selection, parent_id, **kwargs)
            kwargs["qualifier"] = qualifier
            selection = selection

        return selection


class Date(Node):
    """
    Date: year, month, day, [dayOfWeek].
    """

    def __init__(self):
        super().__init__(type(self))
        self.signature.add_sig('year', Int, match_miss=True)
        self.signature.add_sig('month', Int, match_miss=True)
        self.signature.add_sig('day', Int, match_miss=True)
        self.signature.add_sig('dow', DayOfWeek, match_miss=True)
        self.signature.add_sig('dayOfWeek', DayOfWeek, match_miss=True, prop=True)

    def generate_sql_where(self, selection, parent_id, **kwargs):
        qualifier = kwargs.get("qualifier", EQ())
        if self.is_specific():
            return selection.where(qualifier(
                database_handler.to_database_date(parent_id), database_handler.to_database_date(self.to_Pdate())))

        if "year" in self.inputs:
            selection = self.input_view('year').generate_sql_where(
                selection, database_handler.database_date_to_year(parent_id), **kwargs)
        if "month" in self.inputs:
            selection = self.input_view('month').generate_sql_where(
                selection, database_handler.database_date_to_year(parent_id), **kwargs)
        if "day" in self.inputs:
            selection = self.input_view('day').generate_sql_where(
                selection, database_handler.database_date_to_year(parent_id), **kwargs)
        if "dow" in self.inputs:
            selection = self.input_view("dow").generate_sql_where(selection, parent_id)

        return selection

    def valid_input(self):
        t, s = self.get_Pdate()
        if s and not t:
            raise ('Bad date : %s' % s, self)

    def special_day(self):
        yr, mn, dy, dw = self.get_date_values()
        y, m, d = todays_date()
        y0, m0, d0 = tomorrows_date()
        if (yr == y or yr is None) and mn is not None and dy is not None and mn == m and dy == d:
            return 'today'
        if (yr == y0 or yr is None) and mn is not None and dy is not None and mn == m0 and dy == d0:
            return 'tomorrow'
        return ''

    def to_partialDateTime(self):
        # assuming no operators around individual field; otherwise, use get_op_object per field.
        return PartialDateTime(self.get_dat('year'), self.get_dat('month'), self.get_dat('day'), self.get_dat('dow'))

    def to_partialInterval(self):
        pt = self.to_partialDateTime()
        return PartialInterval(pt, typ='eq')

    def to_partialTime_with_default(self, yr=None, mn=None, dy=None, dw=None, hr=None, mt=None, p=None):
        pr = PartialDateTime(self.get_dat('year'), self.get_dat('month'), self.get_dat('day'), self.get_dat('dow'))
        pr.fill_missing_values(yr, mn, dy, dw, hr, mt, pt=p)  # overwrite values
        return pr

    def describe(self, params=None):
        s = self.special_day()
        if s:
            return s
        params = params if params else []
        dd = [self.get_dat(i) for i in ['year', 'month', 'day']]
        s = '.'.join([str(i) if i else '?' for i in dd])
        if self.get_dat('dayOfWeek') and 'compact' not in params:
            s = self.get_dat('dayOfWeek') + '  ' + s
        return s

    def get_missing_value(self, nm, as_node=True):
        if nm == 'dow':
            t, s = self.get_Pdate()
            if t:
                wd = days_of_week[t.isoweekday() - 1]
                if as_node:
                    g, e = self.call_construct_eval('DayOfWeek(%s)' % wd, self.context)
                    self.add_linked_input('dow', g)
                    return g
                return wd
        return None

    def get_property(self, nm):
        if nm=='dayOfWeek':
            return self.get_missing_value('dow')
        super().get_property(nm)

    # node is real object - with only leaf nodes under it (ignore weekday input)
    def is_specific(self):
        if self.get_dat('year') and self.get_dat('month') is not None and self.get_dat('day') is not None:
            return True
        return False

    def get_date_values(self):
        return self.to_partialDateTime().get_date_values()

    def func_EQ(self, ref, op=None, mode=None):
        if ref.typename() != 'Date':
            return False
        return not self.to_partialDateTime().contradict(ref.to_partialDateTime())

    def func_NEQ(self, ref, op=None, mode=None):
        return not self.func_EQ(ref, op=op)

    def func_LT(self, ref, op=None, mode=None):
        return ref.to_partialDateTime() < self.to_partialDateTime()

    def func_GT(self, ref, op=None, mode=None):
        return ref.to_partialDateTime() > self.to_partialDateTime()

    def func_LE(self, ref, op=None, mode=None):
        return self.func_EQ(ref, op=op) or self.func_LT(ref, op=op)

    def func_GE(self, ref, op=None, mode=None):
        return self.func_EQ(ref, op=op) or self.func_GT(ref, op=op)

    def get_date_values_with_default(self, yr=None, mn=None, dy=None, dw=None, p=None):
        if not p:
            p = get_system_datetime()
        return self.to_partialTime_with_default(yr, mn, dy, dw, p=p).get_date_values()

    def get_datetime_values(self):
        return self.get_dat('year'), self.get_dat('month'), self.get_dat('day'), self.get_dat('dow'), None, None

    def get_Pdate(self):
        pr = self.to_partialDateTime()
        if pr.is_complete_date():
            return pr.to_pdate(), pr.date_str()
        return None, ''

    def to_Pdate(self, yr=None, mn=None, dy=None, p=None):
        yr, mn, dy, _ = self.get_date_values_with_default(yr, mn, dy, p)
        return date(yr, mn, dy)

    def to_datetime_sexp(self, allow_constr=True):
        yr, mn, dy, dw = self.get_date_values()
        t = date_sexp(yr, mn, dy, allow_constr)
        return 'DateTime?(date=%s)' % t

    def to_P(self):
        return self.to_Pdate()

    def getattr_yield_msg(self, attr, val=None):
        yr, mn, dy, dw = self.get_date_values()
        if attr == 'month':
            if mn is not None:
                return monthname_full[mn - 1]
        if attr in ['dow', 'dayOfWeek']:
            if dw is not None:
                return dw
                # return days_of_week[dw - 1]
        return super(type(self), self).getattr_yield_msg(attr, val)


class DateTime(Node):
    """
    This type describes a DateTime in year, month, day, hour, minute, second.
    """

    def __init__(self):
        super().__init__(type(self))
        self.signature.add_sig('date', [Date, DateRange], match_miss=True)
        self.signature.add_sig('time', [Time, TimeRange], match_miss=True)
        self.signature.add_sig('dow', DayOfWeek, prop=True)

    def generate_sql_where(self, selection, parent_id, **kwargs):
        if self.is_specific():
            qualifier = kwargs.get("qualifier", EQ())
            return selection.where(qualifier(database_handler.to_database_datetime(parent_id),
                                             database_handler.to_database_datetime(self.to_Pdatetime())))
        for key in ["date", "time", "dow"]:
            if key in self.inputs:
                selection = self.input_view(key).generate_sql_where(selection, parent_id, **kwargs)

        return selection

    def valid_input(self):
        d, t = self.input_view('date'), self.input_view('time')
        if d and d.typename() == 'DateRange':
            self.wrap_input('date', 'DateRange_to_Date(')
        if t and t.typename() == 'TimeRange':
            self.wrap_input('time', 'TimeRange_to_Time(')

    def valid_constraint(self):
        self.valid_input()

    def to_partialDateTime(self):
        # Create a PartialTime object from this DateTime.
        # this assumes subfields are "simple":
        #    if there are any qualifiers (LT, GT,...) they are ignored
        #    if subfields contain multiple objects - undefined behavior - arbitrarily takes one object.
        # room for improvement.
        if 'date' in self.inputs:
            dt = self.input_view('date')
            if dt.is_operator():
                dt = dt.get_op_object(typs=['Date'])
            yr, mn, dy, dw = dt.get_dat('year'), dt.get_dat('month'), dt.get_dat('day'), dt.get_dat('dow')
        else:
            yr, mn, dy, dw = None, None, None, None
        if 'time' in self.inputs:
            tm = self.input_view('time')
            if tm.is_operator():
                tm = tm.get_op_object(typs=['Time'])
            hr, mt = tm.get_dat('hour'), tm.get_dat('minute')
        else:
            hr, mt = None, None
        return PartialDateTime(yr, mn, dy, dw, hr, mt)

    # create a simple partialInterval (mode='eq') from this object.
    # for now, treating this as a simple object (ignoring any qualifiers) (by calling to_partialDateTime first)
    # in future, maybe convert to more complex intervals
    def to_partialInterval(self):
        pt = self.to_partialDateTime()
        return PartialInterval(pt, typ='eq')

    # missing values agree:
    # equal if for each field: either both self and ref have a value which agrees or one or the other is not given
    def func_EQ(self, ref):
        return not self.to_partialDateTime().contradict(ref.to_partialDateTime())

    # missing values - agree
    # self is a DateTime object, which was wrapped by an LT()
    # if op is not None,
    #   it means that we're doing an INTERSECTION between two qualifiers
    #     - and returning True if the intersection is not empty
    #   it also means that self and ref have been reversed.
    # e.g. self=10AM, ref=9AM, op=GT, means:
    #  originally we had self:GT(9AM)  ref:LT(10AM), and the intersection is calculated by checking 9AM.GT(10AM),
    #   i.e. calling ref.func_GT(self, op=None)
    def func_LT(self, ref):
        return ref.to_partialDateTime() < self.to_partialDateTime()

    def func_GT(self, ref):
        return ref.to_partialDateTime() > self.to_partialDateTime()

    # modes:
    # - date: enough that date is specific
    # - time: enough that time is specific
    # - None - datetime: both need to be specific
    def is_specific(self, mode=None):
        ds = False
        if 'date' in self.inputs:
            d = self.input_view('date')
            ds = type(d) == Date and d.is_specific()
        ts = False
        if 'time' in self.inputs:
            t = self.input_view('time')
            ts = type(t) == Time and t.is_specific()
        if mode == 'time':
            return ts
        elif mode == 'date':
            return ds
        return ds and ts

    def describe(self, params=None):
        params = params if params else []
        yr, mn, dy, dw, hr, mt = self.get_datetime_values()
        dte = self.input_view('date')
        s = dte.special_day() if dte else ''
        dw = dw + ' ' if dw is not None else ''
        if not s:
            y, m, d = todays_date()
            if yr != y and yr is not None:
                s = dw + '%d/%s/%d,' % (dy, monthname[mn - 1], yr)
                if 'add_prep' in params:
                    s = 'on ' + s
            elif mn is not None and dy is not None:
                s = dw + '%d/%s,' % (dy, monthname[mn - 1])
                if 'add_prep' in params:
                    s = 'on ' + s
            elif mn is not None:
                s = monthname[mn - 1]
            elif dy is not None:
                s = '%d-%s' % (dy, ordinal_suffix(dy))
        if hr is not None:
            if [1 for i in params if 'SQL' in i]:
                mt = '?' if mt is None else '%02d' % mt
            else:
                mt = '0' if mt is None else '%02d' % mt
            if 'add_prep' in params:
                s += ' at'
            s += ' %d:%s' % (hr, mt)
        return s

    # assuming simple object - ignoring qualifiers
    def get_datetime_values(self, with_wd=True):
        nd = self.res
        t, d = nd.input_view('time'), nd.input_view('date')
        if t and t.typename() == 'Time':
            hr, mt = t.get_time_values()
        else:
            hr, mt = None, None
        if d and d.typename() == 'Date':
            yr, mn, dy, dw = d.get_date_values()
        else:
            yr, mn, dy, dw = None, None, None, None
        return (yr, mn, dy, dw, hr, mt) if with_wd else (yr, mn, dy, hr, mt)

    def get_datetime_values_with_default(self, yr=None, mn=None, dy=None, hr=None, mt=None, p=None):
        nd = self.res
        orgp = p
        p = p if p else get_system_datetime()
        t, d = nd.input_view('time'), nd.input_view('date')
        if t:
            hr, mt = t.get_time_values_with_default(hr, mt, orgp)
        else:
            hr = hr if hr else p.hour
            mt = mt if mt else orgp.minute if orgp else 0

        if d:
            yr, mn, dy, dw = d.get_date_values_with_default(yr, mn, dy, orgp)
        else:
            yr = yr if yr else p.year
            mn = mn if mn else p.month
            dy = dy if dy else p.day
        return yr, mn, dy, None, hr, mt

    def to_Pdatetime(self, yr=None, mn=None, dy=None, hr=None, mt=None, p=None):
        yr, mn, dy, dw, hr, mt = self.get_datetime_values_with_default(yr, mn, dy, hr, mt, p)
        return datetime(yr, mn, dy, hr, mt)

    def to_Pdate(self, yr=None, mn=None, dy=None, p=None):
        yr, mn, dy, _, _, _ = self.get_datetime_values_with_default(yr, mn, dy, 0, 0, p)
        return date(yr, mn, dy)

    @staticmethod
    def from_Pdate(pd, d_context, register=False):
        s = 'DateTime?(date=Date(year=%d,month=%d,day=%d))' % (pd.year, pd.month, pd.day)
        d, e = Node.call_construct_eval(s, d_context, register=register)
        return d

    @staticmethod
    def from_Pdatetime(pdt, d_context, register=False):
        s = datetime_sexp(*Pdatetime_to_values(pdt))
        d, e = Node.call_construct_eval(s, d_context, register=register)
        return d

    def to_P(self):
        return self.to_Pdatetime()

    def get_missing_value(self, nm, as_node=True):
        if nm in ['dow', 'year', 'month', 'day']:
            d = self.input_view('date')
            if d:
                r = d.input_view(nm)
                if not r:
                    r = d.get_missing_value(nm, as_node)
                return r
            return None

    def getattr_yield_msg(self, attr, val=None):
        if attr == 'dow':
            d = self.input_view('date')
            if d:
                r = d.describe()
                return r + ' is ' + val
        return super(type(self), self).getattr_yield_msg(attr, val)

    def overwrite_values(self, yr=None, mn=None, dy=None, dw=None, hr=None, mt=None, Pdt=None):
        if Pdt is not None:
            yr, mn, dy, hr, mt, dw = Pdatetime_to_values(Pdt)
        if 'date' in self.inputs:  # TODO: should create date if not ...
            if yr is not None:
                self.inputs['date'].inputs['year'].data = yr
            if mn is not None:
                self.inputs['date'].inputs['month'].data = mn
            if dy is not None:
                self.inputs['date'].inputs['day'].data = dy
        if 'time' in self.inputs:  # TODO: should create time if not ...
            if hr is not None:
                self.inputs['time'].inputs['hour'].data = hr
            if mt is not None:
                self.inputs['time'].inputs['minute'].data = mt

    def func_FN(self, obj, fname=None, farg=None, op=None, mode=None):
        if fname == 'holiday':
            return is_holiday(obj.to_Pdatetime())
        return False


class DateTimeRange(Range):
    """
    DateTime range - from start DateTime to end DateTime.
    """

    def __init__(self):
        super().__init__(type(self))
        self.signature.add_sig(posname(1), DateTime, alias='start')
        self.signature.add_sig(posname(2), DateTime, alias='end')

    # TODO: explicitly use TimeSlot. Maybe also allow to create just a TimeSlot string (without Event)
    def to_constr_sexp(self, ev=None):
        """
        Makes a constraint string. If `ev` is given, make this into an Event constraint, with `ev` being the subfield
        of the Event.

        :param ev: the event
        :type ev: Node
        :return: the string constraint
        :rtype: str
        """
        s, e, sx = self.input_view('start'), self.input_view('end'), ''
        s = s if not s else id_sexp(s)
        e = e if not e else id_sexp(e)
        if s and e:
            sx = 'AND(Event?(slot=TimeSlot(%s=GE(%s))), Event?(slot=TimeSlot(%s=LE(%s))))' % (
                ev, s, ev, e) if ev else 'AND(GE(%s), LE(%s))' % (s, e)
        elif s:
            sx = 'Event?(slot=TimeSlot(%s=GE(%s)))' % (ev, s) if ev else 'GE(%s)' % s
        elif e:
            sx = 'Event?(slot=TimeSlot(%s=LE(%s)))' % (ev, e) if ev else 'LE(%s)' % e
        return sx

    def to_partialInterval(self):
        s, e = self.input_view('start'), self.input_view('end')
        if s:
            s = s.to_partialDateTime()
        if e:
            e = e.to_partialDateTime()
        if s:
            if e:
                return PartialInterval(s, e)
            return PartialInterval(s, 'ge')
        elif e:
            return PartialInterval(e, 'le')
        else:
            return None


class DateTimeRange_to_DateTime(Node):

    def __init__(self):
        super().__init__(DateTime)
        self.signature.add_sig(posname(1), DateTimeRange, True)

    def exec(self, all_nodes=None, goals=None):
        d = self.input_view(posname(1))
        sx = d.to_constr_sexp()
        if sx:
            g, e = self.call_construct_eval(sx, self.context)
            if e:
                raise DebugDFException('Error - TimeRange conversion problem', self, e)
            self.set_result(g)


class DateRange(Range):
    """
    Date range - from start Date to end Date.
    """

    def __init__(self):
        super().__init__(type(self))
        self.signature.add_sig(posname(1), Date, alias='start')
        self.signature.add_sig(posname(2), Date, alias='end')

    def to_constr_sexp(self, as_dt=False, ev=None):
        s, e, sx = self.input_view('start'), self.input_view('end'), ''
        s = s if not s else 'DateTime?(date=%s)' % id_sexp(s) if as_dt or ev else id_sexp(s)
        e = e if not e else 'DateTime?(date=%s)' % id_sexp(e) if as_dt or ev else id_sexp(e)
        if s and e:
            sx = 'AND(Event?(%s=GE(%s)), Event?(%s=LE(%s)))' % (ev, s, ev, e) if ev else 'AND(GE(%s), LE(%s))' % (s, e)
        elif s:
            sx = 'Event?(%s=GE(%s))' % (ev, s) if ev else 'GE(%s)' % s
        elif e:
            sx = 'Event?(%s=LE(%s))' % (ev, e) if ev else 'LE(%s)' % e
        return sx

    def to_partialInterval(self):
        s, e = self.input_view('start'), self.input_view('end')
        if s:
            s = s.to_partialDateTime()
        if e:
            e = e.to_partialDateTime()
        if s:
            if e:
                return PartialInterval(s, e)
            return PartialInterval(s, 'ge')
        elif e:
            return PartialInterval(e, 'le')
        else:
            return None


class TimeRange(Range):
    """
    Time range - from start Time to end Time.
    """

    def __init__(self):
        super().__init__(type(self))
        self.signature.add_sig(posname(1), Time, alias='start')
        self.signature.add_sig(posname(2), Time, alias='end')

    def to_constr_sexp(self, as_dt=False, ev=None):
        s, e, sx = self.input_view('start'), self.input_view('end'), ''
        s = s if not s else 'DateTime?(time=%s)' % id_sexp(s) if as_dt or ev else id_sexp(s)
        e = e if not e else 'DateTime?(time=%s)' % id_sexp(e) if as_dt or ev else id_sexp(e)
        if s and e:
            sx = 'AND(Event?(%s=GE(%s)), Event?(%s=LE(%s)))' % (ev, s, ev, e) if ev else 'AND(GE(%s), LE(%s))' % (s, e)
        elif s:
            sx = 'Event?(%s=GE(%s))' % (ev, s) if ev else 'GE(%s)' % s
        elif e:
            sx = 'Event?(%s=LE(%s))' % (ev, e) if ev else 'LE(%s)' % e
        return sx

    def to_partialInterval(self):
        s, e = self.input_view('start'), self.input_view('end')
        if s:
            s = s.to_partialDateTime()
        if e:
            e = e.to_partialDateTime()
        if s:
            if e:
                return PartialInterval(s, e)
            return PartialInterval(s, 'ge')
        elif e:
            return PartialInterval(e, 'le')
        else:
            return None


class DateRange_to_Date(Node):

    def __init__(self):
        super().__init__(Date)
        self.signature.add_sig(posname(1), DateRange, True)

    def exec(self, all_nodes=None, goals=None):
        d = self.input_view(posname(1))
        sx = d.to_constr_sexp()
        if sx:
            g, e = self.call_construct_eval(sx, self.context)
            if e:
                raise DebugDFException('Error - DateRange conversion problem', self, e)
            self.set_result(g)


class DateRange_to_DateTimeRange(Node):

    def __init__(self):
        super().__init__(DateTimeRange)
        self.signature.add_sig(posname(1), DateRange, True)

    def exec(self, all_nodes=None, goals=None):
        d = self.input_view(posname(1))
        st, en = d.input_view('start'), d.input_view('end')
        s = 'DateTimeRange(start=DateTime(date=%s), end=DateTime(date=%s))' % (id_sexp(st), id_sexp(en))
        g, e = self.call_construct_eval(s, self.context)
        if e:
            raise DebugDFException('Error - DateRange conversion problem', self, e)
        self.set_result(g)


class TimeRange_to_DateTimeRange(Node):

    def __init__(self):
        super().__init__(DateTimeRange)
        self.signature.add_sig(posname(1), TimeRange, True)

    def exec(self, all_nodes=None, goals=None):
        d = self.input_view(posname(1))
        st, en = d.input_view('start'), d.input_view('end')
        s = 'DateTimeRange(start=DateTime(time=%s), end=DateTime(time=%s))' % (id_sexp(st), id_sexp(en))
        g, e = self.call_construct_eval(s, self.context)
        if e:
            raise DebugDFException('Error - DateRange conversion problem', self, e)
        self.set_result(g)


class TimeRange_to_Time(Node):

    def __init__(self):
        super().__init__(Time)
        self.signature.add_sig(posname(1), TimeRange, True)

    def exec(self, all_nodes=None, goals=None):
        d = self.input_view(posname(1))
        sx = d.to_constr_sexp()
        if sx:
            g, e = self.call_construct_eval(sx, self.context)
            if e:
                raise DebugDFException('Error - TimeRange conversion problem', self, e)
            self.set_result(g)


class ToDateTimeCTree(Node):
    """
    Converts multiple time formats to a constraint tree of DateTime.
    Either one DateTime?, or AND(DateTime?(), DateTime?()) for ranges.
    """

    def __init__(self):
        super().__init__(DateTime)
        self.signature.add_sig(posname(1), [DateTime, Date, Time, DateRange, TimeRange, DateTimeRange], True)

    def exec(self, all_nodes=None, goals=None):
        inp = self.input_view(posname(1))
        tp = inp.typename()
        r = ''
        if tp == 'Date':
            r = 'DateTime?(date=' + id_sexp(inp) + ')'
        elif tp == 'Time':
            r = 'DateTime?(time=' + id_sexp(inp) + ')'
        elif tp == 'DateTimeRange':
            r = inp.to_constr_sexp()
        elif tp == 'DateRange':
            r = inp.to_constr_sexp(as_dt=True)
        elif tp == 'TimeRange':
            r = inp.to_constr_sexp(as_dt=True)

        if tp == 'DateTime':
            # make sure we return DateTime?()  (and not DateTime()). (should not really matter)
            if inp.constraint_level == 1:
                r = inp
            else:
                prms = ['%s=%s' % (i, id_sexp(inp.input_view(i))) for i in ['date', 'time'] if i in inp.inputs]
                r, e = self.call_construct_eval('DateTime(' + ','.join(prms) + ')', self.context)
        else:
            d = r if r else 'DateTime?()'
            r, e = self.call_construct_eval(d, self.context)
        self.set_result(r)


def trans_to_DateTime(nd, inp_nm):
    """
    Transforms an input with a time type (Time, Date, TimeRange, DateRange, DateTimeRange) to DateTime (query).
    """
    s = nd.input_view(inp_nm)
    if s:
        if type(s) == Time:
            nd.wrap_input(inp_nm, 'DateTime?(time=')
        elif type(s) == Date:
            nd.wrap_input(inp_nm, 'DateTime?(date=')
        elif type(s) == TimeRange:
            nd.wrap_input(inp_nm, 'DateTime?(time=TimeRange_to_Time(')
        elif type(s) == DateRange:
            nd.wrap_input(inp_nm, 'DateTime?(date=DateRange_to_Date(')
        elif type(s) == DateTimeRange:
            nd.wrap_input(inp_nm, 'DateTimeRange_to_DateTime(')


def datetime_to_domain_str(n):
    return '%d/%d/%d/%d/%d' % (n.get_datetime_values(with_wd=False))


def datetime_to_str(d: datetime):
    return f"{d.year}/{d.month}/{d.day}/{d.hour}/{d.minute}"


def datetime_node_to_datetime(n):
    return str_to_datetime(datetime_to_domain_str(n))


def time_sexp(hr, mt, allow_constr=True):
    tc = '?' if allow_constr and (hr is None or mt is None) else ''
    s = 'Time%s(' % tc
    p = []
    if hr is not None:
        p.append('hour=%d' % hr)
    if mt is not None:
        p.append('minute=%d' % mt)
    s += ','.join(p) + ')'
    return s


def date_sexp(yr, mn, dy, dw=None, allow_constr=True):
    dc = '?' if allow_constr and (yr is None or mn is None or dy is None) else ''
    s = 'Date%s(' % dc
    p = []
    if yr is not None or not dc:
        p.append('year=%d' % yr)
    if mn is not None:
        p.append('month=%d' % mn)
    if dy is not None:
        p.append('day=%d' % dy)
    if dw is not None:
        p.append('dow=%s' % dw)
    s += ','.join(p) + ')'
    return s


def datetime_sexp(yr, mn, dy, hr, mt, dw=None, allow_constr=True):
    dtc = '?' if allow_constr and (yr is None or mn is None or dy is None or hr is None or mt is None) else ''
    s = 'DateTime%s(' % dtc
    p = []
    if not allow_constr or not all([i is None for i in [yr, mn, dy]]):
        p.append('date=' + date_sexp(yr, mn, dy, dw=dw, allow_constr=allow_constr))
    if not allow_constr or not all([i is None for i in [hr, mt]]):
        p.append('time=' + time_sexp(hr, mt, allow_constr))
    s += ','.join(p)
    s += ')'
    return s


def to_Pdatetime(nd):
    return nd.to_partialDateTime().to_pdatetime(get_system_datetime())


def Pdatetime_to_values(d):
    return d.year, d.month, d.day, d.hour, d.minute, days_of_week[d.date().weekday()]


def Pdate_to_values(d):
    return d.year, d.month, d.day


def Pdatetime_to_datetime_sexp(p):
    return datetime_sexp(*Pdatetime_to_values(p))


def Pdate_to_date_sexp(p):
    return date_sexp(*Pdate_to_values(p))


TIME_NODE_TYPES = [DateTime, Date, Time, DateRange, TimeRange, DateTimeRange]
