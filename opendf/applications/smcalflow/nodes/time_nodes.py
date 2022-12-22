"""
Application specific time nodes.
"""
from sqlalchemy import select

from opendf.applications.core.nodes.time_nodes import *
from opendf.applications.smcalflow.database import Database
from opendf.applications.smcalflow.storage_factory import StorageFactory
from opendf.defs import get_system_date, posname, get_system_datetime, Message
from opendf.exceptions.df_exception import IncompatibleInputException, InvalidValueException, \
    InvalidResultException, InvalidInputException
from opendf.applications.smcalflow.exceptions.df_exception import HolidayNotFoundException, MultipleHolidaysFoundException
from opendf.graph.nodes.framework_operators import LIKE
from opendf.utils.utils import to_list

storage = StorageFactory.get_instance()


class RawDateTime(Node):
    """
    Raw units of time - to be converted to explicit interpretation (duration/time point/...).
    """

    def __init__(self):
        super().__init__(type(self))
        self.signature.add_sig('year', Int)
        self.signature.add_sig('month', Int)
        self.signature.add_sig('week', Int)
        self.signature.add_sig('day', Int)
        self.signature.add_sig('hour', Int)
        self.signature.add_sig('minute', Int)


class Period(Node):
    """
    Period of time.
    """

    def __init__(self):
        super().__init__(type(self))
        # Define parameter of this type
        self.signature.add_sig('day', Int)
        self.signature.add_sig('week', Int)
        self.signature.add_sig('month', Int)
        self.signature.add_sig('year', Int)
        self.signature.add_sig('hour', Int)
        self.signature.add_sig('minute', Int)

    def generate_sql_where(self, selection, parent_id, **kwargs):
        qualifier = kwargs.get("qualifier", EQ())
        duration: timedelta = self.to_Ptimedelta()

        start_column = kwargs["start"]
        end_column = kwargs["end"]
        db_duration = database_handler.get_database_duration_column(start_column, end_column)

        return selection.where(qualifier(db_duration, duration.total_seconds()))

    def describe(self, params=None):
        yr, mn, wk, dy, hr, mt = self.get_period_values()
        d = []
        if yr and yr > 0:
            d.append('%d year%s' % (yr, 's' if yr > 1 else ''))
        if mn and mn > 0:
            d.append('%d month%s' % (mn, 's' if mn > 1 else ''))
        if dy and dy > 0:
            d.append('%d day%s' % (dy, 's' if dy > 1 else ''))
        if wk and wk > 0:
            d.append('%d week%s' % (wk, 's' if wk > 1 else ''))
        if hr and hr > 0:
            d.append('%d hour%s' % (hr, 's' if hr > 1 else ''))
        if mt and mt > 0:
            d.append('%d minute%s' % (mt, 's' if mt > 1 else ''))
        if len(d) == 0:
            s = '0 minutes'
        elif len(d) == 1:
            s = d[0]
        else:
            s = ' '.join(d[:-1]) + ' and ' + d[-1]
        return Message(s, objects=['DT#'+s])

    def get_period_values(self):
        """
        Returns None for values not in input!
        """
        n = self.res
        yr = n.get_dat('year') if 'year' in n.inputs else None
        mn = n.get_dat('month') if 'month' in n.inputs else None
        wk = n.get_dat('week') if 'week' in n.inputs else None
        dy = n.get_dat('day') if 'day' in n.inputs else None
        hr = n.get_dat('hour') if 'hour' in n.inputs else None
        mt = n.get_dat('minute') if 'minute' in n.inputs else None
        return yr, mn, wk, dy, hr, mt

    def to_Ptimedelta(self):
        yr, mn, wk, dy, hr, mt = self.get_period_values()
        days = 365 * yr if yr else 0
        days += 30 * mn if mn else 0
        days += 7 * wk if wk else 0
        days += dy if dy else 0
        secs = 3600 * hr if hr else 0
        secs += 60 * mt if mt else 0
        return timedelta(days, secs)

    def to_partialDateTime(self, mode=None):
        yr, mn, wk, dy, hr, mt = self.get_period_values()
        return PartialDateTime(year=yr, month=mn, day=dy, hour=hr, minute=mt)


class adjustByPeriod(Node):

    def __init__(self):
        super().__init__(DateTime)
        self.signature.add_sig(posname(1), [Date, DateTime], True, alias='date')
        self.signature.add_sig(posname(2), Period, True, alias='period')

    def exec(self, all_nodes=None, goals=None):
        pr = self.input_view("period").res.to_Ptimedelta()

        res = self.input_view("date").res
        if res.typename() == "DateTime":
            dt = res.to_Pdatetime()
            new_date = dt + pr
            g, _ = Node.call_construct_eval(Pdatetime_to_sexp(new_date), self.context)
        else:  # date
            dt = res.to_Pdate()
            dt = datetime(dt.year, dt.month, dt.day)
            new_date = dt + pr
            new_date = Pdate_to_date_sexp(new_date.date())
            g, _ = Node.call_construct_eval(new_date, self.context)

        self.set_result(g)


# #####################################################################################################
# ########################################## time  functions ##########################################


class Holiday(Node):
    """
    Represents a holiday.
    """

    POSSIBLE_VALUES = {
        'FathersDay', 'ValentinesDay', 'EasterMonday', 'Halloween', 'AshWednesday', 'NewYearsDay', 'PresidentsDay',
        'StPatricksDay', 'EarthDay', 'LaborDay', 'FlagDay', 'MothersDay', 'Thanksgiving', 'Easter', 'BlackFriday',
        'VeteransDay', 'TaxDay', 'MemorialDay', 'MardiGras', 'Kwanzaa', 'GoodFriday', 'NewYearsEve', 'GroundhogDay',
        'MLKDay', 'IndependenceDay', 'ElectionDay', 'ColumbusDay', 'PalmSunday', 'AprilFoolsDay', 'PatriotDay',
        'Christmas'}

    def __init__(self):
        super().__init__(Holiday)
        self.signature.add_sig('pos1', Str)

    def valid_input(self):
        dt = self.dat
        if dt is not None:
            if dt not in self.POSSIBLE_VALUES:  # ...
                raise InvalidOptionException(posname(1), dt, self.POSSIBLE_VALUES, self, hints='Holiday')
        else:
            raise MissingValueException(posname(1), self)

    def generate_sql_select(self):
        return select(Database.HOLIDAY_TABLE)

    def generate_sql_where(self, selection, parent_id, **kwargs):
        if 'qualifier' not in kwargs:
            kwargs['qualifier'] = LIKE()
        return self.input_view(posname(1)).generate_sql_where(selection, Database.HOLIDAY_TABLE.columns.name, **kwargs)


class Breakfast(Node):
    """
    Returns TimeRange() for lunch.
    """

    def __init__(self):
        super().__init__(TimeRange)

    def exec(self, all_nodes=None, goals=None):
        # TODO: hard-coded value should become a constant
        d, e = self.call_construct_eval('TimeRange(start=Time(hour=9,minute=0), end=Time(hour=10, minute=0))',
                                        self.context)
        self.set_result(d)


class Brunch(Node):
    """
    Returns TimeRange() for lunch.
    """

    def __init__(self):
        super().__init__(TimeRange)

    def exec(self, all_nodes=None, goals=None):
        # TODO: hard-coded value should become a constant
        d, e = self.call_construct_eval('TimeRange(start=Time(hour=10,minute=0), end=Time(hour=12, minute=0))',
                                        self.context)
        self.set_result(d)


class Lunch(Node):
    """
    Returns TimeRange() for lunch.
    """

    def __init__(self):
        super().__init__(TimeRange)

    def exec(self, all_nodes=None, goals=None):
        # TODO: hard-coded value should become a constant
        d, e = self.call_construct_eval('TimeRange(start=Time(hour=12,minute=0), end=Time(hour=13, minute=0))',
                                        self.context)
        self.set_result(d)


class Dinner(Node):
    """
    Returns TimeRange() for lunch.
    """

    def __init__(self):
        super().__init__(TimeRange)

    def exec(self, all_nodes=None, goals=None):
        # TODO: hard-coded value should become a constant
        d, e = self.call_construct_eval('TimeRange(start=Time(hour=19,minute=0), end=Time(hour=20, minute=0))',
                                        self.context)
        self.set_result(d)


class Noon(Node):
    """
    Returns TimeRange() for lunch.
    """

    def __init__(self):
        super().__init__(TimeRange)

    def exec(self, all_nodes=None, goals=None):
        # TODO: hard-coded value should become a constant
        d, e = self.call_construct_eval('TimeRange(start=Time(hour=11,minute=0), end=Time(hour=13, minute=0))',
                                        self.context)
        self.set_result(d)


class Morning(Node):
    """
    Returns TimeRange() for morning.
    """

    def __init__(self):
        super().__init__(TimeRange)

    def exec(self, all_nodes=None, goals=None):
        # TODO: hard-coded value should become a constant
        d, e = self.call_construct_eval('TimeRange(start=Time(hour=8,minute=0), end=Time(hour=11, minute=30))',
                                        self.context)
        self.set_result(d)


class LateMorning(Node):
    """
    Returns TimeRange() for late morning.
    """

    def __init__(self):
        super().__init__(TimeRange)

    def exec(self, all_nodes=None, goals=None):
        # TODO: hard-coded value should become a constant
        d, e = self.call_construct_eval('TimeRange(start=Time(hour=10,minute=0), end=Time(hour=11, minute=30))',
                                        self.context)
        self.set_result(d)


class Afternoon(Node):
    """
    Returns TimeRange() for afternoon.
    """

    def __init__(self):
        super().__init__(TimeRange)

    def exec(self, all_nodes=None, goals=None):
        # TODO: hard-coded value should become a constant
        d, e = self.call_construct_eval('TimeRange(start=Time(hour=11,minute=30), end=Time(hour=17, minute=00))',
                                        self.context)
        self.set_result(d)


class LateAfternoon(Node):
    """
    Returns TimeRange() for late afternoon.
    """

    def __init__(self):
        super().__init__(TimeRange)

    def exec(self, all_nodes=None, goals=None):
        # TODO: hard-coded value should become a constant
        d, e = self.call_construct_eval('TimeRange(start=Time(hour=15,minute=30), end=Time(hour=17, minute=00))',
                                        self.context)
        self.set_result(d)


class Evening(Node):
    """
    Returns TimeRange() for morning.
    """

    def __init__(self):
        super().__init__(TimeRange)

    def exec(self, all_nodes=None, goals=None):
        # TODO: hard-coded value should become a constant
        d, e = self.call_construct_eval('TimeRange(start=Time(hour=17,minute=0), end=Time(hour=21, minute=30))',
                                        self.context)
        self.set_result(d)


class Night(Evening):
    pass


class Midnight(Node):
    """
    Returns the DateTime() for midnight.
    """

    def __init__(self):
        super().__init__(DateTime)

    def exec(self, all_nodes=None, goals=None):
        day = get_system_date() + timedelta(days=1)
        g, e = self.call_construct_eval(
            f"DateTime(date=Date(year={day.year},month={day.month},day={day.day}), time=Time(hour=0, minute=0))",
            self.context)
        self.set_result(g)


# input-less function
# result is today's date - Date()
class Today(Node):
    """
    Returns the Date() of today.
    """

    def __init__(self):
        super().__init__(Date)

    def exec(self, all_nodes=None, goals=None):
        y, m, d = todays_date()
        g, e = self.call_construct_eval('Date(year=%d,month=%d,day=%d)' % (y, m, d), self.context)
        self.set_result(g)

    def yield_msg(self, params=None):
        g = self.res
        return Message('Today is %d %s %d' % (g.get_dat('day'), monthname_full[g.get_dat('month') - 1], g.get_dat('year')))


class Tomorrow(Node):
    """
    Returns the Date() of tomorrow.
    """

    def __init__(self):
        super().__init__(Date)

    def exec(self, all_nodes=None, goals=None):
        y, m, d = tomorrows_date()
        g, e = self.call_construct_eval('Date(year=%d,month=%d,day=%d)' % (y, m, d), self.context)
        self.set_result(g)

    def yield_msg(self, params=None):
        g = self.res
        return Message('Tomorrow is %d %s %d' % (g.get_dat('day'), monthname_full[g.get_dat('month') - 1], g.get_dat('year')))


class Yesterday(Node):
    """
    Returns the Date() of yesterday.
    """

    def __init__(self):
        super().__init__(Date)

    def exec(self, all_nodes=None, goals=None):
        y, m, d = yesterdays_date()
        g, e = self.call_construct_eval('Date(year=%d,month=%d,day=%d)' % (y, m, d), self.context)
        self.set_result(g)

    def yield_msg(self, params=None):
        g = self.res
        return Message('Yesterday was %d %s %d' % (g.get_dat('day'), monthname_full[g.get_dat('month') - 1], g.get_dat('year')))


class nextDayOfWeek(Node):
    """
    Returns the date for the next day of the week. It might be in the same week or in the following week.
    """

    def __init__(self):
        super().__init__(Date)
        self.signature.add_sig(posname(1), Date, True, alias='date')
        self.signature.add_sig(posname(2), [Str, DayOfWeek], True, alias='dow')

    def exec(self, all_nodes=None, goals=None):
        d, dow_name = self.get_input_views(['date', 'dow'])
        dow = name_to_dow(dow_name.dat)
        day: date = d.to_Pdate()
        delta = dow - day.isoweekday()
        if delta < 1:
            delta = 7 + delta
        next_day = day + timedelta(days=delta)
        g, e = self.call_construct_eval(Pdate_to_date_sexp(next_day), self.context)
        self.set_result(g)


class previousDayOfWeek(Node):
    """
    Returns the date for the previous day of the week. It might be in the same week or in the previous week.
    """

    def __init__(self):
        super().__init__(Date)
        self.signature.add_sig(posname(1), Date, True, alias='date')
        self.signature.add_sig(posname(2), Str, True, alias='dow')

    def exec(self, all_nodes=None, goals=None):
        d, dow_name = self.get_input_views(['date', 'dow'])
        dow = name_to_dow(dow_name.dat)
        day: date = d.to_Pdate()
        delta = day.isoweekday() - dow
        if delta < 1:
            delta = 7 + delta
        next_day = day + timedelta(days=-delta)
        g, e = self.call_construct_eval(Pdate_to_date_sexp(next_day), self.context)
        self.set_result(g)


class HolidayYear(Node):

    def __init__(self):
        super().__init__(Date)
        self.signature.add_sig(posname(1), Holiday, True, alias='holiday')
        self.signature.add_sig(posname(2), Int, True, alias='year')

    def exec(self, all_nodes=None, goals=None):
        date_node, _ = Node.call_construct_eval(f"Date?(year={self.get_dat('year')})", self.context)
        holidays = storage.find_holidays_that_match(self.context, self.input_view("holiday"), date_node)

        if not holidays:
            raise HolidayNotFoundException(self)

        if len(holidays) > 1:
            raise MultipleHolidaysFoundException(self)

        g, _ = Node.call_construct_eval(Pdate_to_date_sexp(holidays[0].date), self.context)

        self.set_result(g)

    def yield_msg(self, params=None):
        m = self.res.describe()
        return Message(f"{self.get_dat('holiday')} is on {m.text}", objects=m.objects)


class nextHoliday(Node):

    def __init__(self):
        super().__init__(Date)
        self.signature.add_sig(posname(1), Date, True, alias='date')
        self.signature.add_sig(posname(2), Holiday, True, alias='holiday')

    def exec(self, all_nodes=None, goals=None):
        date_node, _ = Node.call_construct_eval(f"GT({id_sexp(self.input_view('date'))})", self.context)
        holidays = storage.find_holidays_that_match(self.context, self.input_view("holiday"), date_node, sort="asc",
                                                    limit=1)

        if not holidays:
            raise HolidayNotFoundException(self)

        g, _ = Node.call_construct_eval(Pdate_to_date_sexp(holidays[0].date), self.context)

        self.set_result(g)

    def yield_msg(self, params=None):
        m = self.res.describe()
        return Message(f"{self.get_dat('holiday')} is on {m.text}", objects=m.objects)


class previousHoliday(Node):

    def __init__(self):
        super().__init__(Date)
        self.signature.add_sig(posname(1), Date, True, alias='date')
        self.signature.add_sig(posname(2), Holiday, True, alias='holiday')

    def exec(self, all_nodes=None, goals=None):
        date_node, _ = Node.call_construct_eval(f"LT({id_sexp(self.input_view('date'))})", self.context)
        holidays = storage.find_holidays_that_match(self.context, self.input_view("holiday"), date_node, sort="desc",
                                                    limit=1)

        if not holidays:
            raise HolidayNotFoundException(self)

        g, _ = Node.call_construct_eval(Pdate_to_date_sexp(holidays[0].date), self.context)

        self.set_result(g)

    def yield_msg(self, params=None):
        m = self.res.describe()
        return Message(f"{self.get_dat('holiday')} is on {m.text}", objects=m.objects)


class NextHolidayFromToday(Node):

    def __init__(self):
        super().__init__(Date)
        self.signature.add_sig(posname(1), Holiday, True, alias='holiday')

    def exec(self, all_nodes=None, goals=None):
        g, _ = Node.call_construct(f"nextHoliday(Today(), {id_sexp(self.input_view('holiday'))})", self.context)
        self.set_result(g)
        e = g.call_eval(add_goal=False)
        if e:
            raise to_list(e)[-1]


    def yield_msg(self, params=None):
        m = self.res.describe()
        return Message(f"{self.get_dat('holiday')} is on {m.text}", objects=m.objects)


class WeekendOfDate(Node):
    """
    Returns the weekend closer to the date.
    """

    def __init__(self):
        super().__init__(DateRange)
        self.signature.add_sig(posname(1), Date, True, alias='date')

    def exec(self, all_nodes=None, goals=None):
        d = self.input_view('date')
        day: date = d.to_Pdate()
        dow = day.isoweekday()
        if dow > 2:  # closest weekend is ahead
            start = day + timedelta(days=6 - dow)
            end = start + timedelta(days=1)
        else:  # closest weekend is behind
            end = day - timedelta(days=dow)
            start = end - timedelta(days=1)

        g, e = self.call_construct_eval(Pdates_to_daterange_sexp(start, end), self.context)
        self.set_result(g)


class NextWeekend(Node):

    def __init__(self):
        super().__init__(DateRange)

    def exec(self, all_nodes=None, goals=None):
        g, _ = self.call_construct_eval(f"nextDayOfWeek({Pdate_to_date_sexp(get_system_date())}, SATURDAY)", self.context)
        day = g.res.to_Pdate()
        r, _ = self.call_construct_eval(
            f"DateRange(start={id_sexp(g.res)}, end={Pdate_to_date_sexp(day + timedelta(days=1))})", self.context)
        self.set_result(r)


# There are some ways of thinking about first/last week of a month, and also the definition a week (e.g.
# what is the start and end of a week). In this implementation, we assume that the first week of the month is the week
# starting from the first day of the month, and ending 6 days later. We do the reverse for the last week.

class NumberWeekOfMonth(Node):

    def __init__(self):
        super().__init__(DateRange)
        self.signature.add_sig('month', [Str, Int], True)
        self.signature.add_sig('number', Int, True)

    def exec(self, all_nodes=None, goals=None):
        month = self.get_dat("month")
        num = self.get_dat("number")
        if isinstance(month, str):
            month = name_to_month(month)
        year = get_system_date().year

        last_day = last_month_day(year, month)

        if num * 7 >= last_day:
            raise InvalidResultException(f"Month {self.get_dat('month')} has no week {num}.", self)

        start = date(year, month, 1) + timedelta(days=(num - 1) * 7)
        end = start + timedelta(days=6)
        g, _ = Node.call_construct_eval(f"DateRange({Pdate_to_date_sexp(start)}, {Pdate_to_date_sexp(end)})", self.context)

        self.set_result(g)


class NumberWeekFromEndOfMonth(Node):

    def __init__(self):
        super().__init__(DateRange)
        self.signature.add_sig('month', [Str, Int], True)
        self.signature.add_sig('num', Int, True)

    def exec(self, all_nodes=None, goals=None):
        month = self.get_dat("month")
        num = self.get_dat("num")
        if isinstance(month, str):
            month = name_to_month(month)
        year = get_system_date().year

        last_day = last_month_day(year, month)

        if last_day - (num * 7) < 0:
            raise InvalidResultException(f"Month {self.get_dat('month')} has no week {num}, from the end.", self)

        start = date(year, month, last_day) - timedelta(days=(num * 7) - 1)
        end = start + timedelta(days=6)
        g, _ = Node.call_construct_eval(f"DateRange({Pdate_to_date_sexp(start)}, {Pdate_to_date_sexp(end)})", self.context)

        self.set_result(g)


class ThisWeekend(Node):

    def __init__(self):
        super().__init__(DateRange)

    def exec(self, all_nodes=None, goals=None):
        today = get_system_date()

        end = today + timedelta(days=7 - today.isoweekday())
        start = end - timedelta(days=1)

        g, _ = Node.call_construct_eval(f"DateRange({Pdate_to_date_sexp(start)}, {Pdate_to_date_sexp(end)})", self.context)
        self.set_result(g)


class WeekendOfMonth(Node):

    def __init__(self):
        super().__init__(DateRange)
        self.signature.add_sig(posname(1), [Str, Int], True, alias='month')
        self.signature.add_sig(posname(2), Int, True, alias='num')

    def exec(self, all_nodes=None, goals=None):
        month = self.get_dat("month")
        num = self.get_dat("num")
        if isinstance(month, str):
            month = name_to_month(month)
        year = get_system_date().year

        first_day = date(year, month, 1)
        delta = 6 - first_day.isoweekday()
        if delta < 0:
            delta += 7
        first_weekend_day = first_day + timedelta(delta)

        start = first_weekend_day + timedelta(days=(num - 1) * 7)
        if start.month != month:
            raise InvalidResultException(f"Month {self.get_dat('month')} has no weekend {num}.", self)

        end = start + timedelta(days=1)
        g, _ = Node.call_construct_eval(f"DateRange({Pdate_to_date_sexp(start)}, {Pdate_to_date_sexp(end)})", self.context)

        self.set_result(g)


class LastWeekendOfMonth(Node):

    def __init__(self):
        super().__init__(DateRange)
        self.signature.add_sig('month', [Str, Int], True)
        self.signature.add_sig('num', Int, True)

    def exec(self, all_nodes=None, goals=None):
        month = self.get_dat("month")
        num = self.get_dat("num")
        if isinstance(month, str):
            month = name_to_month(month)
        year = get_system_date().year

        last_day = date(year, month, last_month_day(year, month))
        delta = last_day.isoweekday() % 7
        last_weekend_month = last_day - timedelta(days=delta)

        end = last_weekend_month - timedelta(days=(num - 1) * 7)
        start = end - timedelta(days=1)
        if start.month != month:
            raise InvalidResultException(f"Month {self.get_dat('month')} has no weekend {num}.", self)

        g, _ = Node.call_construct_eval(f"DateRange({Pdate_to_date_sexp(start)}, {Pdate_to_date_sexp(end)})", self.context)

        self.set_result(g)


class DowOfWeekNew(Node):
    """
    Returns the first occurrence of the day of week in a given DataRange.
    """

    def __init__(self):
        super().__init__(Date)
        self.signature.add_sig(posname(1), [Str, DayOfWeek], True, alias='dow')
        self.signature.add_sig(posname(2), DateRange, True, alias='week')

    def exec(self, all_nodes=None, goals=None):
        dow_name, week = self.get_input_views(['dow', 'week'])
        dow = name_to_dow(dow_name.dat)
        start: date = week.input_view('start').to_Pdate()
        delta = dow - start.isoweekday()
        if delta < 1:
            delta = 7 + delta
        next_day = start + timedelta(days=delta)
        end = week.input_view('end').to_Pdate()
        if next_day > end:
            raise InvalidResultException(f"Day of week {dow_name.dat} is out of range from {start} to {end}!", self)
        g, e = self.call_construct_eval(Pdate_to_date_sexp(next_day), self.context)
        self.set_result(g)


class DowToDowOfWeek(Node):

    def __init__(self):
        super().__init__(DateRange)
        self.signature.add_sig(posname(1), Str, True, alias='day1')
        self.signature.add_sig(posname(2), Str, True, alias='day2')
        self.signature.add_sig(posname(3), DateRange, True, alias='week')

    def exec(self, all_nodes=None, goals=None):
        r, _ = Node.call_construct_eval(f"DowOfWeekNew({id_sexp(self.input_view('day1'))}, "
                                        f"{id_sexp(self.input_view('week'))})", self.context)
        date1 = r.res

        new_range, _ = Node.call_construct_eval(f"DateRange(start={id_sexp(date1)}, "
                                                f"end={id_sexp(self.input_view('week').input_view('end'))})", self.context)
        r, _ = Node.call_construct_eval(f"DowOfWeekNew({id_sexp(self.input_view('day2'))}, "
                                        f"{id_sexp(new_range)})", self.context)
        date2 = r.res

        g, _ = Node.call_construct_eval(f"DateRange(start={id_sexp(date1)}, end={id_sexp(date2)})", self.context)

        self.set_result(g)


class WeekOfDateNew(Node):
    """
    Returns the week contain the date.
    """

    def __init__(self):
        super().__init__(DateRange)
        self.signature.add_sig(posname(1), [Date, DateTime], True, alias='date')

    def exec(self, all_nodes=None, goals=None):
        sexp = get_week_start_end_sexp(self.input_view("date").res.to_Pdate())
        d, e = self.call_construct_eval(sexp, self.context)
        self.set_result(d)


class MonthDayToDay(Node):

    def __init__(self):
        super().__init__(DateRange)
        self.signature.add_sig('month', [Str, Int], True)
        self.signature.add_sig('num1', Int, True)
        self.signature.add_sig('num2', Int, True)

    def valid_input(self):
        if "month" not in self.inputs:
            raise MissingValueException("month", self)
        if "num1" not in self.inputs:
            raise MissingValueException("num1", self)
        if "num2" not in self.inputs:
            raise MissingValueException("num2", self)

        num1 = self.input_view("num1").dat
        num2 = self.input_view("num2").dat
        if num1 >= num2:
            raise IncompatibleInputException(
                f"Expected the first number to be less than the second number, got {num1} and {num2}", self)
        month = self.input_view("month").dat
        if isinstance(month, str):
            month = name_to_month(month)

        last_day = last_month_day(get_system_date().year, month)
        if num1 < 1:
            raise InvalidValueException(f"Expected the first number to greater than 0, got {num1}", self)
        if num2 > last_day:
            raise InvalidValueException(
                f"Expected the second number to less than or equal to the last day of the month "
                f"({last_day}), got {num2}", self)

    def exec(self, all_nodes=None, goals=None):
        month, day1, day2 = self.get_input_views(['month', 'num1', 'num2'])
        month = month.dat
        if isinstance(month, str):
            month = name_to_month(month)
        year = get_system_date().year
        g, e = self.call_construct_eval(f"DateRange(start=Date(year={year}, month={month}, day={day1.dat}), "
                                        f"end=Date(year={year}, month={month}, day={day2.dat}))", self.context)
        self.set_result(g)


class nextDayOfMonth(Node):
    """
    Returns the date for the next day of month, after the date.
    """

    def __init__(self):
        super().__init__(Date)
        self.signature.add_sig(posname(1), Date, True, alias='date')
        self.signature.add_sig(posname(2), Int, True, alias='number')

    def valid_input(self):
        number = self.input_view("number")
        if number is None or not 0 < number.dat < 32:
            raise InvalidValueException(
                f"Invalid value {number} for number. It should be a number between 1 and 31, inclusive.", self)

    def exec(self, all_nodes=None, goals=None):
        d, number = self.get_input_views(['date', 'number'])
        day: date = d.to_Pdate()
        number = number.dat
        month = day.month
        year = day.year
        month_end = last_month_day(year, month)
        if day.day < number <= month_end:
            result = date_sexp(year, month, number)
        else:
            result = None
            while result is None:
                if month == 12:
                    month = 1
                    year += 1
                else:
                    month += 1
                month_end = last_month_day(year, month)
                if number <= month_end:
                    result = date_sexp(year, month, number)

        g, e = self.call_construct_eval(result, self.context)
        self.set_result(g)


class previousDayOfMonth(Node):
    """
    Returns the date for the previous day of month, before the date.
    """

    def __init__(self):
        super().__init__(Date)
        self.signature.add_sig(posname(1), Date, True, alias='date')
        self.signature.add_sig(posname(2), Int, True, alias='number')

    def valid_input(self):
        number = self.input_view("number")
        if number is None or not 0 < number.dat < 32:
            raise InvalidValueException(
                f"Invalid value {number} for number. It should be a number between 1 and 31, inclusive.", self)

    def exec(self, all_nodes=None, goals=None):
        d, number = self.get_input_views(['date', 'number'])
        day: date = d.to_Pdate()
        number = number.dat
        month = day.month
        year = day.year
        month_end = last_month_day(year, month)
        if day.day > number and number <= month_end:
            result = date_sexp(year, month, number)
        else:
            result = None
            while result is None:
                if month == 1:
                    month = 12
                    year -= 1
                else:
                    month -= 1
                month_end = last_month_day(year, month)
                if number <= month_end:
                    result = date_sexp(year, month, number)

        g, e = self.call_construct_eval(result, self.context)
        self.set_result(g)


class nextMonthDay(Node):
    """
    Returns the date for the next day of month, after date, for a specific month.
    """

    def __init__(self):
        super().__init__(Date)
        self.signature.add_sig(posname(1), Date, True, alias='date')
        self.signature.add_sig(posname(2), [Str, Int], True, alias='month')
        self.signature.add_sig(posname(3), Int, True, alias='number')

    def exec(self, all_nodes=None, goals=None):
        d, month, number = self.get_input_views(['date', 'month', 'number'])
        day: date = d.to_Pdate()
        date_month = day.month
        number = number.dat
        month = month.dat
        if isinstance(month, str):
            month = name_to_month(month)

        if date_month < month or (date_month == month and day.day < number):
            year = day.year
        else:
            year = day.year + 1

        g, e = self.call_construct_eval(date_sexp(year, month, number), self.context)
        self.set_result(g)


class previousMonthDay(Node):
    """
    Returns the date for the previous day of month, before date, for a specific month.
    """

    def __init__(self):
        super().__init__(Date)
        self.signature.add_sig(posname(1), Date, True, alias='date')
        self.signature.add_sig(posname(2), [Str, Int], True, alias='month')
        self.signature.add_sig(posname(3), Int, True, alias='number')

    def exec(self, all_nodes=None, goals=None):
        d, month, number = self.get_input_views(['date', 'month', 'number'])
        day: date = d.to_Pdate()
        date_month = day.month
        number = number.dat
        month = month.dat
        if isinstance(month, str):
            month = name_to_month(month)

        if date_month > month or (date_month == month and day.day > number):
            year = day.year
        else:
            year = day.year - 1

        g, e = self.call_construct_eval(date_sexp(year, month, number), self.context)
        self.set_result(g)


class ClosestMonthDayToDate(Node):

    def __init__(self):
        super().__init__(Date)
        self.signature.add_sig(posname(1), Date, True, alias='date')
        self.signature.add_sig(posname(2), Int, True, alias='day')
        self.signature.add_sig(posname(3), [Int, Str], True, alias='month')

    def exec(self, all_nodes=None, goals=None):
        dt, day, month = self.get_input_views(['date', 'day', 'month'])

        prev_node, _ = Node.call_construct_eval(
            f"previousMonthDay(date={id_sexp(dt)}, month={id_sexp(month)}, number={id_sexp(day)})", self.context)
        next_node, _ = Node.call_construct_eval(
            f"nextMonthDay(date={id_sexp(dt)}, month={id_sexp(month)}, number={id_sexp(day)})", self.context)

        prev_date = prev_node.res.to_Pdate()
        next_date = next_node.res.to_Pdate()

        target_date = dt.to_Pdate()

        if (target_date - prev_date).days < (next_date - target_date).days:
            self.set_result(prev_node.res)
        else:
            self.set_result(next_node.res)


class ClosestDay(Node):
    """
    Returns the date for the next day of month.
    """

    def __init__(self):
        super().__init__(Date)
        self.signature.add_sig('date', Date, True)
        self.signature.add_sig('day', Int, True)

    def exec(self, all_nodes=None, goals=None):
        dt, day = self.get_input_views(['date', 'day'])
        prev_node, _ = self.call_construct_eval(f"previousDayOfMonth({id_sexp(dt)}, {id_sexp(day)})", self.context)
        next_node, _ = self.call_construct_eval(f"nextDayOfMonth({id_sexp(dt)}, {id_sexp(day)})", self.context)

        prev_date = prev_node.res.to_Pdate()
        next_date = next_node.res.to_Pdate()

        target_date = dt.to_Pdate()

        if (target_date - prev_date).days < (next_date - target_date).days:
            self.set_result(prev_node.res)
        else:
            self.set_result(next_node.res)


class LastDayOfMonth(Node):
    """
    Returns the date for the last day of month.
    """

    def __init__(self):
        super().__init__(Date)
        self.signature.add_sig(posname(1), [Int, Str], True, alias='month')

    def exec(self, all_nodes=None, goals=None):
        month = self.get_dat("month")
        if isinstance(month, str):
            month = name_to_month(month)
        year = get_system_date().year
        month_end = last_month_day(year, month)
        g, _ = Node.call_construct_eval(date_sexp(year, month, month_end), self.context)
        self.set_result(g)


class NextMonth(Node):
    """
    Returns the next month.
    """

    def __init__(self):
        super().__init__(Str)

    def exec(self, all_nodes=None, goals=None):
        month = monthname_full[get_system_date().month % 12]
        # we don't need to sum 1 because the index of month_full name starts from 0

        d, e = self.call_construct_eval(f"Str({month})", self.context)
        self.set_result(d)


class FullMonthofPreviousMonth(Node):
    """
    Returns DateRange() for a previous month.
    """

    def __init__(self):
        super().__init__(DateRange)
        self.signature.add_sig(posname(1), [Str, Int], True, alias="month")

    def exec(self, all_nodes=None, goals=None):
        mn = self.get_dat(posname(1))
        if isinstance(mn, str):
            mn = name_to_month(mn)
        today = get_system_date()
        if today.month <= mn:
            year = today.year - 1
        else:
            year = today.year
        dy = last_month_day(year, mn)
        d, e = self.call_construct_eval(
            'DateRange(start=Date(year=%d, month=%d, day=1), end=Date(year=%d, month=%d, day=%d))' %
            (year, mn, year, mn, dy), self.context)
        self.set_result(d)


class FullMonthofMonth(Node):
    """
    Returns DateRange() for a given month.
    """

    def __init__(self):
        super().__init__(DateRange)
        self.signature.add_sig(posname(1), [Str, Int], True, alias="month")
        self.signature.add_sig('year', Int)  # optional year

    def valid_input(self):
        mn = self.get_dat(posname(1))
        if isinstance(mn, int) and (mn < 1 or mn > 12):
            raise InvalidInputException('Wrong month number as input : %d' % mn, self)
        if isinstance(mn, str) and name_to_month(mn) < 1:
            raise InvalidInputException('Wrong month name as input : %d' % mn, self)

    def exec(self, all_nodes=None, goals=None):
        mn = self.get_dat(posname(1))
        if isinstance(mn, str):
            mn = name_to_month(mn)
        if 'year' in self.inputs:
            year = self.get_dat('year')
        else:
            yr0, mn0, dy0 = todays_date()
            year = yr0 + 1 if mn < mn0 else yr0
        dy = last_month_day(year, mn)
        d, e = self.call_construct_eval(
            'DateRange(start=Date(year=%d, month=%d, day=1), end=Date(year=%d, month=%d, day=%d))' %
            (year, mn, year, mn, dy), self.context)
        self.set_result(d)


class FullMonthofLastMonth(Node):
    """
    Returns DateRange() for last month.
    """

    def __init__(self):
        super().__init__(DateRange)

    def exec(self, all_nodes=None, goals=None):
        yr, mn, _ = todays_date()
        if mn == 1:
            mn = 12
            yr -= 1
        else:
            mn -= 1
        d, e = self.call_construct_eval(f"FullMonthofMonth(month=Int({mn}), year={yr})", self.context)
        self.set_result(d)


class SeasonWinter(Node):
    """
    Returns DateRange() for this winter.
    """

    def __init__(self):
        super().__init__(DateRange)

    def exec(self, all_nodes=None, goals=None):
        today = get_system_date()

        if today < date(today.year, 3, 21):
            # It is still winter, the winter started last year and will end this year
            start_year = today.year - 1
        else:
            start_year = today.year

        d, e = self.call_construct_eval(f"DateRange("
                                        f"start=Date(year={start_year}, month=12, day=21), "
                                        f"end=Date(year={start_year + 1}, month=3, day=20))", self.context)
        self.set_result(d)


class SeasonSpring(Node):
    """
    Returns DateRange() for this spring.
    """

    def __init__(self):
        super().__init__(DateRange)

    def exec(self, all_nodes=None, goals=None):
        today = get_system_date()

        if today < date(today.year, 6, 21):
            # It is still spring, the season started this year
            year = today.year
        else:
            # It is after this year season, the next season starts next year
            year = today.year + 1

        d, e = self.call_construct_eval(f"DateRange("
                                        f"start=Date(year={year}, month=3, day=21), "
                                        f"end=Date(year={year + 1}, month=6, day=20))", self.context)
        self.set_result(d)


class SeasonSummer(Node):
    """
    Returns DateRange() for this summer.
    """

    def __init__(self):
        super().__init__(DateRange)

    def exec(self, all_nodes=None, goals=None):
        today = get_system_date()

        if today < date(today.year, 9, 21):
            # It is still summer, the season started this year
            year = today.year
        else:
            # It is after this year season, the next season starts next year
            year = today.year + 1

        d, e = self.call_construct_eval(f"DateRange("
                                        f"start=Date(year={year}, month=6, day=21), "
                                        f"end=Date(year={year + 1}, month=9, day=20))", self.context)
        self.set_result(d)


class SeasonFall(Node):
    """
    Returns DateRange() for this fall.
    """

    def __init__(self):
        super().__init__(DateRange)

    def exec(self, all_nodes=None, goals=None):
        today = get_system_date()

        if today < date(today.year, 12, 21):
            # It is still fall, the season started this year
            year = today.year
        else:
            # It is after this year season, the next season starts next year
            year = today.year + 1

        d, e = self.call_construct_eval(f"DateRange("
                                        f"start=Date(year={year}, month=9, day=21), "
                                        f"end=Date(year={year + 1}, month=12, day=20))", self.context)
        self.set_result(d)


class FullYearofYear(Node):
    """
    Returns DateRange() for a given year.
    """

    def __init__(self):
        super().__init__(DateRange)
        self.signature.add_sig(posname(1), Int, True, alias="year")

    def exec(self, all_nodes=None, goals=None):
        year = self.get_dat('year')
        d, e = self.call_construct_eval(
            f"DateRange(start=Date(year={year}, month=1, day=1), end=Date(year={year}, month=12, day=31))", self.context)
        self.set_result(d)


class LastYear(Node):

    def __init__(self):
        super().__init__(Int)

    def exec(self, all_nodes=None, goals=None):
        d, _ = self.call_construct_eval(f"Int({get_system_date().year - 1})", self.context)
        self.set_result(d)


class NextYear(Node):

    def __init__(self):
        super().__init__(Int)

    def exec(self, all_nodes=None, goals=None):
        d, _ = self.call_construct_eval(f"Int({get_system_date().year + 1})", self.context)
        self.set_result(d)


class toFourDigitYear(Node):

    def __init__(self):
        super().__init__(Int)
        self.signature.add_sig(posname(1), Int, True)

    def valid_input(self):
        if posname(1) not in self.inputs:
            raise MissingValueException("year", self)
        number = self.inputs[posname(1)].dat
        if number > 99:
            raise InvalidValueException(f"Expected, at most, a two number digits number, got {number}", self)

    def exec(self, all_nodes=None, goals=None):
        number = self.inputs[posname(1)].dat
        threshold = int(str(get_system_date().year + 5)[-2:])
        if number > threshold:
            year = 1900 + number
        else:
            year = 2000 + number
        d, _ = self.call_construct_eval(f"Int({year})", self.context)
        self.set_result(d)


class NumberPM(Node):
    """
    Converts number (hours) to PM Time.
    """

    def __init__(self):
        super().__init__(Time)
        self.signature.add_sig(posname(1), Int)

    def exec(self, all_nodes=None, goals=None):
        number = self.get_dat(posname(1))
        if number < 12:
            number += 12
        s = time_sexp(number, 0)
        d, e = self.call_construct_eval(s, self.context)
        self.set_result(d)


class NumberAM(Node):
    """
    Converts number (hours) to AM Time.
    """

    def __init__(self):
        super().__init__(Time)
        self.signature.add_sig(posname(1), Int, True)

    def exec(self, all_nodes=None, goals=None):
        number = self.get_dat(posname(1))
        if number > 11:
            number -= 12
        s = time_sexp(number, 0)
        d, e = self.call_construct_eval(s, self.context)
        self.set_result(d)


class HourMinutePm(Node):
    """
    Converts hours, minutes to PM Time.
    """

    def __init__(self):
        super().__init__(Time)
        self.signature.add_sig('hours', Int, True)
        self.signature.add_sig('minutes', Int, True)

    def exec(self, all_nodes=None, goals=None):
        hour = self.get_dat('hours') % 12 + 12
        minute = self.get_dat('minutes')
        d, e = self.call_construct_eval(time_sexp(hour, minute), self.context)
        self.set_result(d)


class HourMinuteAm(Node):
    """
    Converts hours, minutes to AM Time.
    """

    def __init__(self):
        super().__init__(Time)
        self.signature.add_sig('hours', Int, True)
        self.signature.add_sig('minutes', Int, True)

    def exec(self, all_nodes=None, goals=None):
        hour = self.get_dat('hours') % 12
        minute = self.get_dat('minutes')
        d, e = self.call_construct_eval(time_sexp(hour, minute), self.context)
        self.set_result(d)


class ConvertTimeToAM(Node):

    def __init__(self):
        super().__init__(Time)
        self.signature.add_sig('time', Time, True)

    def exec(self, all_nodes=None, goals=None):
        time_node = self.input_view("time")
        hour = time_node.get_dat("hour")
        minute = time_node.get_dat("minute")
        if hour > 11:
            node_str = f"Time(hour={hour - 12}"
            if minute is not None:
                node_str += f", minute={minute}"
            node_str += ")"
            g, _ = Node.call_construct_eval(node_str, self.context)
        else:
            g = time_node
        self.set_result(g)


class ConvertTimeToPM(Node):

    def __init__(self):
        super().__init__(Time)
        self.signature.add_sig('time', Time, True)

    def exec(self, all_nodes=None, goals=None):
        time_node = self.input_view("time")
        hour = time_node.get_dat("hour")
        minute = time_node.get_dat("minute")
        if hour < 12:
            node_str = f"Time(hour={hour + 12}"
            if minute is not None:
                node_str += f", minute={minute}"
            node_str += ")"
            g, _ = Node.call_construct_eval(node_str, self.context)
        else:
            g = time_node
        self.set_result(g)


class HourMilitary(Node):

    def __init__(self):
        super().__init__(Time)
        self.signature.add_sig('hours', Int, True)

    def exec(self, all_nodes=None, goals=None):
        g, _ = Node.call_construct_eval(f"Time(hour={self.get_dat('hours')})", self.context)
        self.set_result(g)


class HourMinuteMilitary(Node):

    def __init__(self):
        super().__init__(Time)
        self.signature.add_sig('hours', Int, True)
        self.signature.add_sig('minutes', Int, True)

    def exec(self, all_nodes=None, goals=None):
        g, _ = Node.call_construct_eval(f"Time(hour={self.get_dat('hours')}, minute={self.get_dat('minutes')})",
                                        self.context)
        self.set_result(g)


class EndOfWorkDay(Node):
    """
    Returns the time of the end of the working day.
    """

    def __init__(self):
        super().__init__(Time)

    def exec(self, all_nodes=None, goals=None):
        d, e = self.call_construct_eval(time_sexp(18, 0), self.context)
        self.set_result(d)


class EarlyDateRange(Node):

    def __init__(self):
        super().__init__(DateRange)
        self.signature.add_sig(posname(1), DateRange, True, alias='dateRange')

    def exec(self, all_nodes=None, goals=None):
        start_node = self.input_view("dateRange").input_view("start").res
        start_date = start_node.to_Pdate()
        end_date = self.input_view("dateRange").input_view("end").res.to_Pdate()

        delta = end_date - start_date
        delta /= 2

        new_end = start_date + delta

        g, _ = Node.call_construct_eval(f"DateRange(start={id_sexp(start_node)}, end={Pdate_to_date_sexp(new_end)})",
                                        self.context)

        self.set_result(g)


class LateDateRange(Node):

    def __init__(self):
        super().__init__(DateRange)
        self.signature.add_sig(posname(1), DateRange, True, alias='dateRange')

    def exec(self, all_nodes=None, goals=None):
        start_date = self.input_view("dateRange").input_view("start").res.to_Pdate()
        end_node = self.input_view("dateRange").input_view("end").res
        end_date = end_node.to_Pdate()

        delta = end_date - start_date
        delta /= 2

        new_start = start_date + delta

        g, _ = Node.call_construct_eval(f"DateRange(start={Pdate_to_date_sexp(new_start)}, end={id_sexp(end_node)})",
                                        self.context)

        self.set_result(g)


class EarlyTimeRange(Node):

    def __init__(self):
        super().__init__(TimeRange)
        self.signature.add_sig(posname(1), TimeRange, True, alias='timeRange')

    def exec(self, all_nodes=None, goals=None):
        start_node = self.input_view("timeRange").input_view("start").res
        start_date = start_node.to_Ptime()
        end_date = self.input_view("timeRange").input_view("end").res.to_Ptime()

        t = get_system_date()
        start_date = datetime(year=t.year, month=t.month, day=t.day, hour=start_date.hour, minute=start_date.minute)
        end_date = datetime(year=t.year, month=t.month, day=t.day, hour=end_date.hour, minute=end_date.minute)

        delta = end_date - start_date
        delta /= 2

        new_end = start_date + delta

        g, _ = Node.call_construct_eval(
            f"TimeRange(start={id_sexp(start_node)}, end=Time(hour={new_end.hour}, minute={new_end.minute}))",
            self.context)

        self.set_result(g)


class LateTimeRange(Node):

    def __init__(self):
        super().__init__(TimeRange)
        self.signature.add_sig(posname(1), TimeRange, True, alias='timeRange')

    def exec(self, all_nodes=None, goals=None):
        start_date = self.input_view("timeRange").input_view("start").res.to_Ptime()
        end_node = self.input_view("timeRange").input_view("end").res
        end_date = end_node.to_Ptime()

        t = get_system_date()
        start_date = datetime(year=t.year, month=t.month, day=t.day, hour=start_date.hour, minute=start_date.minute)
        end_date = datetime(year=t.year, month=t.month, day=t.day, hour=end_date.hour, minute=end_date.minute)

        delta = end_date - start_date
        delta /= 2

        new_start = start_date + delta

        g, _ = Node.call_construct_eval(
            f"TimeRange(start=Time(hour={new_start.hour}, minute={new_start.minute}), end={id_sexp(end_node)})",
            self.context)

        self.set_result(g)


# TODO: do we really need the toDays/toHours...?
#        OR - we could instead directly use RawDateTime(day/hour/...=...) - same load on ML
#             we could also do directly Period(day/hour...) instead of periodDuration(RawDateTime(day/hour...))

class toDays(Node):
    """
    Converts number to raw days.
    """

    def __init__(self):
        super().__init__(Period)
        self.signature.add_sig(posname(1), Int)

    def exec(self, all_nodes=None, goals=None):
        number = self.get_dat(posname(1))
        d, e = self.call_construct_eval('Period(day=%d)' % number, self.context)
        self.set_result(d)


class toWeeks(Node):
    """
    Converts number to raw weeks.
    """

    def __init__(self):
        super().__init__(Period)
        self.signature.add_sig(posname(1), Int)

    def exec(self, all_nodes=None, goals=None):
        number = self.get_dat(posname(1))
        d, e = self.call_construct_eval('Period(week=%d)' % number, self.context)
        self.set_result(d)


class toMonths(Node):
    """
    Converts number to raw months.
    """

    def __init__(self):
        super().__init__(Period)
        self.signature.add_sig(posname(1), Int)

    def exec(self, all_nodes=None, goals=None):
        number = self.get_dat(posname(1))
        d, e = self.call_construct_eval('Period(month=%d)' % number, self.context)
        self.set_result(d)


class toYears(Node):
    """
    Converts number to raw years.
    """

    def __init__(self):
        super().__init__(Period)
        self.signature.add_sig(posname(1), Int)

    def exec(self, all_nodes=None, goals=None):
        number = self.get_dat(posname(1))
        d, e = self.call_construct_eval('Period(year=%d)' % number, self.context)
        self.set_result(d)


class toHours(Node):
    """
    Converts number to raw hours.
    """

    def __init__(self):
        super().__init__(Period)
        self.signature.add_sig(posname(1), Int)

    def exec(self, all_nodes=None, goals=None):
        number = self.get_dat(posname(1))
        d, e = self.call_construct_eval('Period(hour=%d)' % number, self.context)
        self.set_result(d)


class toMinutes(Node):
    """
    Converts number to raw minutes.
    """

    def __init__(self):
        super().__init__(Period)
        self.signature.add_sig(posname(1), Int)

    def exec(self, all_nodes=None, goals=None):
        number = self.get_dat(posname(1))
        d, e = self.call_construct_eval('Period(minute=%d)' % number, self.context)
        self.set_result(d)


# TODO: do we also need classes for "toHoursMinutes" which converts two numbers to hours, minutes...?
#  e.g if the user says - "the meeting should last 2h30m"
#  OR - should we directly translate this to RawTime(hours=2, minutes=30)?

class PeriodDuration(Node):
    """
    Converts RawTime to Period.
    """

    def __init__(self):
        super().__init__(Period)
        self.signature.add_sig('pos1', RawDateTime)
        # TODO: should we also allow 'days', 'hours'... inputs?

    def exec(self, all_nodes=None, goals=None):
        period = self.input_view('pos1')
        durs = {i: 0 if i not in period.inputs else period.get_dat(i) for i in period_components}
        s = ', '.join(['%s=%d' % (i, durs[i]) for i in durs])
        d, e = self.call_construct_eval('Period(' + s + ')', self.context)
        self.set_result(d)


class NextPeriodDuration(Node):
    """
    Gets a DateTimeRange with specified duration starting NOW.
    """

    def __init__(self):
        super().__init__(DateTimeRange)
        self.signature.add_sig('period', Period)

    def exec(self, all_nodes=None, goals=None):
        p = self.input_view('period')
        dur = p.period_to_Ptimedelta()
        end_year, end_month, end_day, end_hour, end_minute, dw = Pdatetime_to_values(get_system_datetime() + dur)
        s = datetime_sexp(end_year, end_month, end_day, end_hour, end_minute, dw)
        d, e = self.call_construct_eval('DateTimeRange(start=Now(),end=%s)' % s, self.context)
        self.set_result(d)


class Now(Node):
    """
    DateTime of NOW.
    """

    def __init__(self):
        super().__init__(DateTime)

    def exec(self, all_nodes=None, goals=None):
        year, month, day = todays_date()
        hour, minute = nows_time()
        s = datetime_sexp(year, month, day, hour, minute)
        d, e = self.call_construct_eval(s, self.context)
        self.set_result(d)


class ClosestDayOfWeek(Node):
    """
    Gets the Date (preferably in the future) with the given DOW, closest to the given date. (either before or after).
    """

    # if date is Wednesday, "closest Tuesday" is the previous day (given it's in the future)
    # if date is Monday, "closest Tuesday" is the following day
    # if date is omitted - assume it's today
    # TODO: change logic (it's still the logic for the previous definition)
    def __init__(self):
        super().__init__(Date)
        self.signature.add_sig('date', Date)
        self.signature.add_sig('dow', DayOfWeek, True)

    def exec(self, all_nodes=None, goals=None):
        dt = self.input_view('date')
        td = get_system_date()
        p = dt.to_Pdate() if dt else td
        d = name_to_dow(self.get_dat('dow'))
        w = p.isoweekday()
        df = w - d
        if df != 0:
            ndf = d - w if d > w else d + 7 - w
            pdf = d - w if w > d else d - (w + 7)
            nd = p + timedelta(days=ndf)
            pd = p + timedelta(days=pdf)
            if p >= td:  # if date is in the past - don't worry about changing it to a past date.
                # otherwise - try to fix it
                if pd < td:  # if prev dow is in past - ignore it
                    pdf, pd = ndf, nd
                df = ndf if abs(ndf) <= abs(pdf) else pdf  # choose closest between prev and next dow
        p += timedelta(days=df)
        yr, mn, dy = Pdate_to_values(p)
        d, e = self.call_construct_eval('Date(year=%d,month=%d,day=%d)' % (yr, mn, dy), self.context)
        self.set_result(d)


class NextDOW(Node):
    """
    Gets the NEXT dow.
    """

    # get the date of the closest FUTURE day with the given DOW
    #   if today is Wednesday, "nextDOW(Tuesday)" is next week
    #   if today is Monday, "nextDOW(Tuesday)" is tomorrow
    def __init__(self):
        super().__init__(Date)
        self.signature.add_sig('pos1', [DayOfWeek, Str], True, alias='dow')

    def exec(self, all_nodes=None, goals=None):
        # get input
        d = name_to_dow(self.get_dat('dow'))
        t = get_system_date()
        w = t.isoweekday()
        if w >= d:
            df = d + 7 - w
        else:
            df = d - w
        t += timedelta(days=df)
        s = Pdate_to_date_sexp(t)
        d, e = self.call_construct_eval(s, self.context)
        self.set_result(d)

    def transform_graph(self, top):
        inp = self.input_view(posname(1))
        if inp and inp.typename() == 'Str':
            self.wrap_input(posname(1), 'DayOfWeek(', do_eval=False)
        return self, None


class DateAtTimeWithDefaults(Node):
    """
    Returns DateTime, where missing date and time are filled with defaults.
    """

    # if date is omitted - assume today
    # if time is omitted - assume 12 noon. if partial fields of time missing - fill by 'now'
    def __init__(self):
        super().__init__(DateTime)
        self.signature.add_sig('date', Date)
        self.signature.add_sig('time', Time)

    def exec(self, all_nodes=None, goals=None):
        # get input
        if 'time' in self.inputs:
            hr, mt = self.input_view('time').get_time_values_with_default()
        else:
            hr, mt = 12, 0

        if 'date' in self.inputs:
            yr, mn, dy = self.input_view('date').get_date_values_with_default()
        else:
            yr, mn, dy = todays_date()

        s = datetime_sexp(yr, mn, dy, hr, mt)
        d, e = self.call_construct_eval(s, self.context)
        self.set_result(d)


class WeekEndDays(Node):
    def __init__(self):
        super().__init__(Date)

    def exec(self, all_nodes=None, goals=None):
        d, e = self.call_construct_eval('ANY(DayOfWeek(Saturday), DayOfWeek(Sunday))', self.context)
        self.set_result(d)


class WeekDays(Node):
    def __init__(self):
        super().__init__(DayOfWeek)

    def exec(self, all_nodes=None, goals=None):
        d, e = self.call_construct_eval(
            'ANY(DayOfWeek(Monday), DayOfWeek(Tuesday), DayOfWeek(Wednesday), DayOfWeek(Thursday), DayOfWeek(Friday))',
            self.context)
        self.set_result(d)


class NextTime(Node):
    """
    Gets the coming DateTime with the given Time.
    """

    # NextTime(3PM) is 3PM today, if now is before 3PM, otherwise - 3PM tomorrow
    def __init__(self):
        super().__init__(DateTime)
        self.signature.add_sig('time', [Time, TimeRange], True)

    def exec(self, all_nodes=None, goals=None):
        # get input
        hr, mt = nows_time()
        tm = self.input_view('time')
        if tm.typename()=='TimeRange':
            tm = tm.input_view('start')
        hr1, mt1 = tm.get_time_values_with_default(hr, mt)
        yr, mn, dy = todays_date()

        if hr1 < hr or (hr1 == hr and mt1 < mt):
            t = get_system_date() + timedelta(days=1)
            yr, mt, dy = t.year, t.month, t.day
        s = datetime_sexp(yr, mn, dy, hr1, mt1)
        d, e = self.call_construct_eval(s, self.context)
        self.set_result(d)


class MD(Node):

    def __init__(self):
        super().__init__(Date)
        self.signature.add_sig(posname(1), Str, True, alias='month')
        self.signature.add_sig(posname(2), Int, True, alias='day')

    def exec(self, all_nodes=None, goals=None):
        d, m = self.get_input_views(['day', 'month'])
        g, _ = self.call_construct_eval(f"Date?(month={name_to_month(m.dat)}, day={d.dat})", self.context)
        self.set_result(g)


class MDY(Node):

    def __init__(self):
        super().__init__(Date)
        self.signature.add_sig(posname(1), Str, True, alias='month')
        self.signature.add_sig(posname(2), Int, True, alias='day')
        self.signature.add_sig(posname(3), Int, True, alias='year')

    def exec(self, all_nodes=None, goals=None):
        d, m, y = self.get_input_views(['day', 'month', 'year'])
        g, _ = self.call_construct_eval(f"Date?(month={name_to_month(m.dat)}, day={d.dat}, year={y.dat})", self.context)
        self.set_result(g)


def Pdates_to_daterange_sexp(s, e):
    ss = Pdate_to_date_sexp(s)
    se = Pdate_to_date_sexp(e)
    sexp = 'DateRange(start=%s,end=%s)' % (ss, se)
    return sexp


def get_week_start_end_sexp(p):
    dw = p.isoweekday()
    s = p + timedelta(days=1 - dw)
    e = s + timedelta(days=6)
    return Pdates_to_daterange_sexp(s, e)


class ThisWeek(Node):
    """
    Gets DateRange corresponding to current week.
    """

    def __init__(self):
        super().__init__(DateRange)

    def exec(self, all_nodes=None, goals=None):
        sexp = get_week_start_end_sexp(get_system_date())
        d, e = self.call_construct_eval(sexp, self.context)
        self.set_result(d)


class LastWeekNew(Node):
    """
    Gets DateRange corresponding to prev week.
    """

    def __init__(self):
        super().__init__(DateRange)

    def exec(self, all_nodes=None, goals=None):
        sexp = get_week_start_end_sexp(get_system_date() - timedelta(days=7))
        d, e = self.call_construct_eval(sexp, self.context)
        self.set_result(d)


class NextWeekList(Node):
    """
    Gets DateRange corresponding to next week.
    """

    def __init__(self):
        super().__init__(DateRange)

    def exec(self, all_nodes=None, goals=None):
        sexp = get_week_start_end_sexp(get_system_date() + timedelta(days=7))
        d, e = self.call_construct_eval(sexp, self.context)
        self.set_result(d)


class ThisWeekEnd(Node):
    """
    Gets DateRange corresponding to current week.
    """

    def __init__(self):
        super().__init__(DateRange)

    def exec(self, all_nodes=None, goals=None):
        p = get_system_date()
        dw = p.weekday()
        s = p + timedelta(days=5 - dw)
        e = s + timedelta(days=2)
        sexp = Pdates_to_daterange_sexp(s, e)
        d, e = self.call_construct_eval(sexp, self.context)
        self.set_result(d)


# =================================

# these nodes still need to be implemented

class AroundDateTime(Node):
    def __init__(self):
        super().__init__(DateTime)
        #super().__init__(DateTimeRange)
        self.signature.add_sig(posname(1), DateTime, True, alias='dateTime')

    def exec(self, all_nodes=None, goals=None):
        dt = self.input_view(posname(1))
        self.set_result(dt)

class TimeAround(Node):
    def __init__(self):
        #super().__init__(TimeRange)
        super().__init__(Time)
        self.signature.add_sig(posname(1), Time, True)

    def exec(self, all_nodes=None, goals=None):
        dt = self.input_view(posname(1))
        self.set_result(dt)
