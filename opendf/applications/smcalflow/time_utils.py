"""
File to hold time related class/functions.
"""

import calendar
from abc import ABC
from datetime import datetime, timedelta, date
from typing import Iterable, Iterator, List

from opendf.applications.core.nodes.time_nodes import Pdatetime_to_datetime_sexp
from opendf.applications.smcalflow.domain import Ptimedelta_to_period_sexp

# TODO: replace hard-coded values by defined constants
from opendf.exceptions.python_exception import InvalidDataException
from opendf.applications.core.exceptions.python_exception import BadConstructionException, BadRangeException


def has_out_time(flt):
    ts = flt.get_subnodes_of_type('Time')
    for t in ts:
        if 'hour' in t.inputs and not 9 <= t.get_dat('hour') <= 17:
            return True
    return False


class DayOfTheWeekPossibility:
    """
    Class to handle the possible days of the week.
    """

    def __init__(self, monday=False, tuesday=False, wednesday=False, thursday=False, friday=False,
                 saturday=False, sunday=False):
        self._allowed_days = (monday, tuesday, wednesday, thursday, friday, saturday, sunday)
        self._all = all(self._allowed_days)
        self._none = not any(self._allowed_days)

    @property
    def allowed_days(self):
        return self._allowed_days

    @property
    def all(self):
        return self._all

    @property
    def none(self):
        return self._none

    def __contains__(self, item):
        """
        Checks if `item` is allowed by the constraints.

        :param item: the date
        :type item: date or datetime
        :return: `True`, if the item is allowed; otherwise, `False`
        :rtype: bool
        """
        return self.allowed_days[item.weekday()]

    @staticmethod
    def all_days():
        """
        Returns an empty constraint that allows all the days of the week.

        :return: an empty constraint that allows all the days of the week
        :rtype: DayOfTheWeekPossibility
        """
        return DayOfTheWeekPossibility(
            monday=True,
            tuesday=True,
            wednesday=True,
            thursday=True,
            friday=True,
            saturday=True,
            sunday=True
        )

    def step_to_next_valid_day(self, after_day):
        """
        Computes the minimal step necessary to hit the next possible day after `after_day`.

        The minimal step is the smallest number t \\in [1, 7] such as `after_day` + t (days) is a valid week day.

        :param after_day: the current day to compute the step
        :type after_day: date or datetime
        :return: the minimal step necessary to hit the next possible day, given the day of the week constraints
        :rtype: int
        """
        if self.none:
            return None

        step = 1
        day_of_the_week = after_day.weekday()
        while not self.allowed_days[(step + day_of_the_week) % 7]:
            step += 1

        return step


class DateTimeFieldIterator(ABC, Iterator[int], Iterable[int]):
    """
    Class to define an iterator for date and time fields.

    Each implementation of this class should concern to a specific field of a date time value, in order: year, month,
    day, hour and minute. The implementation of a field might depend on specif values of the previous fields.
    """

    MINIMUM_STEP = 1

    def __init__(self, begin, end=None, step=MINIMUM_STEP):
        if end is not None and begin > end:
            raise BadRangeException(begin, end)
        if step < self.MINIMUM_STEP:
            raise BadConstructionException(f"Step should be greater than or equal to {self.MINIMUM_STEP}, step: {step}")
        self.begin = begin
        self.end = end
        self.step = step
        self._current = None
        self._started = False
        self._earliest = None

    @property
    def current(self):
        if self._current is not None and self._current < self.begin:
            return None
        return self._current

    def restart_iterator(self, previous_fields):
        """
        Re-starts the iterator based on the value of the previous fields.

        The idea is that a given iterator may depend on the values of previous iterators, for instance,
        the day iterator may depend on the values from the month and the year in order to account for the numbers of
        days in the month, e.g. february may have 28 or 29 days, depending on the year.

        The iterator must only look at the values of the previous fields, since the values of other fields could be
        invalid at the time this function is called

        :param previous_fields: the value of the previous fields
        :type previous_fields: datetime
        """
        if self._earliest is None:
            self._current = self.begin - self.step
        else:
            self._current = self._earliest - self.step
            self._earliest = None

        self._started = True

    def __iter__(self):
        return self

    def has_next(self):
        """
        Checks if the iterator has a next value.

        :return: `True`, if there is a next value; otherwise, `False`
        :rtype:  bool
        """
        return self._started

    def __next__(self):
        if self.has_next():
            self._current += self.step
            self._started = self._current + self.step <= self.end
            if self.begin <= self._current <= self.end:
                return self._current

        raise StopIteration()

    def __repr__(self):
        return str(f"{type(self).__name__}: {self.current} in [{self.begin}, {self.end}]")

    def set_earliest(self, value):
        """
        Sets the earliest possible value of the iterator.

        :param value: the earliest possible value
        :type value: int
        """
        if value < self.begin:
            raise InvalidDataException(
                f"Earliest value must be greater than or equal to begin, value: {value}, begin: {self.begin}")
        self._earliest = value


class YearIterator(DateTimeFieldIterator):
    """
    Class to iterate over the years.
    """

    MINIMUM_VALUE = 1

    def __init__(self, begin=MINIMUM_VALUE, end=None, step=1):
        if begin < self.MINIMUM_VALUE:
            raise BadConstructionException(
                f"Begin should be grater than or equal to {self.MINIMUM_VALUE}, begin: {begin}")
        super().__init__(begin, end=end, step=step)
        self._current = begin - self.step

    def restart_iterator(self, previous_fields):
        if self._earliest is not None:
            self._current = self._earliest
            self._earliest = None

    def has_next(self):
        return self.end is None or self._current + self.step < self.end

    def __next__(self):
        if self.has_next():
            self._current += 1
            return self._current

        raise StopIteration()

    def set_earliest(self, value):
        if value is not None and self.begin <= value and (self.end is None or value <= self.end):
            self._current = value - self.step


class MonthFieldIterator(DateTimeFieldIterator):
    """
    Class to iterate over the months of the years.
    """

    MINIMUM_VALUE = 1
    MAXIMUM_VALUE = 12

    def __init__(self, begin=MINIMUM_VALUE, end=MAXIMUM_VALUE, step=1):
        if begin < self.MINIMUM_VALUE:
            raise BadConstructionException(
                f"Begin should be grater than or equal to {self.MINIMUM_VALUE}, begin: {begin}")
        if end > self.MAXIMUM_VALUE:
            raise BadConstructionException(f"End should be less than or equal to {self.MAXIMUM_VALUE}, end: {end}")
        if begin > end:
            raise BadRangeException(begin, end)
        super().__init__(begin, end=end, step=step)
        self._started = False


# TODO: Improve the DayIterator to account for holidays
class DayFieldIterator(DateTimeFieldIterator):
    """
    Class to iterate over days of the month.
    """

    MINIMUM_VALUE = 1
    MAXIMUM_VALUE = 31  # maximum possible number of days in a month for the Gregorian calendar

    # The step parameter here would allow something like: 'create a meeting ever other day, except on sundays.'
    # This would create meetings on monday, wednesday, friday, tuesday, thursday, saturday, monday ...
    def __init__(self, begin=MINIMUM_VALUE, end=MAXIMUM_VALUE, days_of_the_week=None, step=1):
        """
        Create a day iterator.

        :param begin: the initial number of the day in the month
        :type begin: int
        :param end: the final number of the day in the month. When bigger than the real number of days in the month,
        the real number will be used
        :type end: int
        :param days_of_the_week: the possibles days of the week
        :type days_of_the_week: DayOfTheWeekPossibility
        :param step: the step to increment de days
        :type step: int
        """
        if begin < self.MINIMUM_VALUE:
            raise BadConstructionException(
                f"Begin should be grater than or equal to {self.MINIMUM_VALUE}, begin: {begin}")
        if end > self.MAXIMUM_VALUE:
            raise BadConstructionException(f"End should be less than or equal to {self.MAXIMUM_VALUE}, end: {end}")
        if begin > end:
            raise BadRangeException(begin, end)

        super().__init__(begin, end, step=step)
        self._original_end = end
        self.days_of_the_week = days_of_the_week if days_of_the_week is not None else DayOfTheWeekPossibility.all_days()
        self._current_month = None
        self._current_year = None
        self._started = False

    def restart_iterator(self, previous_fields):
        if self.days_of_the_week.none:
            return
        self._current_month = previous_fields.month
        self._current_year = previous_fields.year
        _, month_end = calendar.monthrange(previous_fields.year, previous_fields.month)
        # If there is a constraint on the last day of the month, keep the minimum between the constraint and the
        # number of days in the month
        self.end = min(self._original_end, month_end)
        self._current = None
        self._started = True

    def find_next_valid_day(self, from_day):
        """
        Finds the next valid day number, after `from_day` (inclusive), if exists.

        :param from_day: the day from which to start the search
        :type from_day: int
        :return: the next valid day number, after `from_day`, if exists
        :rtype: int or None
        """
        if self._current_month is None or self._current_year is None:
            return None

        if from_day > self.end:
            # checks if the day is in range
            return None

        possible_day = self.create_date(from_day)
        if possible_day in self.days_of_the_week:
            # the day is allowed by the days of the week constraints
            return from_day

        next_day = from_day
        while next_day < self.end:
            delta = self.days_of_the_week.step_to_next_valid_day(possible_day)
            # delta is the number of days until the next valid day of the week, we must check if we can get there.
            # in order to get to the next valid day of the week, it must meet two constraints:
            #  1. it must be within the valid range of days in the current month;
            #  2. it must be reached by N * self.step, where N is an integer.
            next_day = from_day + delta

            if next_day > self.end:
                # day is out of range, nothing else we can do, the iterator must restart from another (month, year) pair
                return None

            if delta % self.step == 0:
                # we found a possible day, return it
                return next_day

            # No day was found, but there still hope, update `possible_day` with a step and go to next iteration
            possible_day = self.create_date(from_day + self.step)

        return None

    def create_date(self, from_day):
        return date(self._current_year, self._current_month, from_day)

    def __next__(self):
        if self.current is None:
            if self._earliest is None:
                from_day = self.begin
            else:
                from_day = self._earliest
                self._earliest = None
        else:
            from_day = self.current + self.step
        if self.has_next():
            # If there is a constraint in the day of the week, check the required step to get to the next valid day
            self._current = self.find_next_valid_day(from_day)
            self._started = self._current is not None  # If current is None, there is no valid day in this month,
            # the iterator must be restarted for the next month

        if self._current is not None:
            return self._current

        raise StopIteration()


# TODO: HourIterator can be improved to account for specific limitations on the hour range, such as partial holidays
class HourFieldIterator(DateTimeFieldIterator):
    """
    Class to iterate over hours of the day.
    """

    MINIMUM_VALUE = 0
    MAXIMUM_VALUE = 23

    def __init__(self, begin=MINIMUM_VALUE, end=MAXIMUM_VALUE, step=1):
        if begin < self.MINIMUM_VALUE:
            raise BadConstructionException(
                f"Begin should be grater than or equal to {self.MINIMUM_VALUE}, begin: {begin}")
        if end > self.MAXIMUM_VALUE:
            raise BadConstructionException(f"End should be less than or equal to {self.MAXIMUM_VALUE}, end: {end}")
        if begin > end:
            raise BadRangeException(begin, end)
        super().__init__(begin, end=end, step=step)
        self._started = False


class MinuteFieldIterator(DateTimeFieldIterator):
    """
    Class to iterate over minutes of the hour.
    """

    MINIMUM_VALUE = 0
    MAXIMUM_VALUE = 59

    def __init__(self, begin=MINIMUM_VALUE, end=MAXIMUM_VALUE, step=1):
        if begin < self.MINIMUM_VALUE:
            raise BadConstructionException(
                f"Begin should be grater than or equal to {self.MINIMUM_VALUE}, begin: {begin}")
        if end > self.MAXIMUM_VALUE:
            raise BadConstructionException(f"End should be less than or equal to {self.MAXIMUM_VALUE}, end: {end}")
        if begin > end:
            raise BadRangeException(begin, end)

        super().__init__(begin, end=end, step=step)
        self._started = False


class DateTimeIterator(Iterator[datetime], Iterable[datetime]):
    """
    Class to iterate over possible date and times, given the constraints.
    """

    YEAR_ITERATOR = 0
    MONTH_ITERATOR = 1
    DAY_ITERATOR = 2
    HOUR_ITERATOR = 3
    MINUTE_ITERATOR = 4

    FIELD_NAMES = ["year", "month", "day", "hour", "minute"]

    def __init__(self, earliest=None, latest=None):
        self.iterators: List[DateTimeFieldIterator] = [
            YearIterator(),
            MonthFieldIterator(),
            DayFieldIterator(),
            HourFieldIterator(),
            MinuteFieldIterator()
        ]
        self.iterators_length = len(self.iterators)
        self.field_index = self.iterators_length - 1
        self._latest = None
        if earliest:
            self.set_earliest_datetime(earliest)
        if latest:
            self.set_latest_datetime(latest)

    def generate_date(self, until_iterator=None):
        values = {
            "year": None,
            "month": 1,
            "day": 1,
            "hour": 0,
            "minute": 0
        }
        if until_iterator == 0:
            return None
        elif until_iterator is None:
            until_iterator = self.iterators_length

        for i in range(until_iterator):
            values[DateTimeIterator.FIELD_NAMES[i]] = self.iterators[i].current

        return datetime(**values)

    def get_next_value(self):
        index = self.field_index
        while 0 <= index <= self.field_index:
            current_iterator = self.iterators[index]
            if current_iterator.has_next():
                try:
                    next(current_iterator)
                    index += 1
                    if index < self.iterators_length:
                        current_datetime = self.generate_date(index)
                        self.iterators[index].restart_iterator(current_datetime)
                except (TypeError, StopIteration):
                    index -= 1
                    continue
            else:
                index -= 1

        if index > self.field_index:
            return self.generate_date()

        return None

    def __next__(self) -> datetime:
        value = self.get_next_value()
        if value is None or (self._latest is not None and value > self._latest):
            raise StopIteration()

        return value

    def set_earliest_datetime(self, value):
        """
        Sets the earliest possible date and/or time for the iterator.

        :param value: the date and time
        :type value: datetime or time
        """
        if isinstance(value, datetime):
            hour = value.hour
            minute = value.minute
        else:
            hour = 0
            minute = 0

        self.iterators[self.YEAR_ITERATOR].set_earliest(value.year)
        self.iterators[self.MONTH_ITERATOR].set_earliest(value.month)
        self.iterators[self.DAY_ITERATOR].set_earliest(value.day)
        self.iterators[self.HOUR_ITERATOR].set_earliest(hour)
        self.iterators[self.MINUTE_ITERATOR].set_earliest(minute)

    def set_latest_datetime(self, value):
        if isinstance(value, datetime):
            hour = value.hour
            minute = value.minute
            second = value.second
        else:
            hour = 23
            minute = 59
            second = 59
        self._latest = datetime(year=value.year, month=value.month, day=value.day,
                                hour=hour, minute=minute, second=second)


# input: start, end, duration - format
def get_event_times_str(start, end, duration, default_dur=None):
    """
    Creates a string representation of the parameters of the event.

    :param start: the start of the event
    :type start: datetime
    :param end: the end of the event
    :type end: datetime
    :param duration: the duration of the event
    :type duration: timedelta
    :param default_dur: a possible default duration
    :type default_dur: Optional[timedelta]
    :return: the string representation of the start, end and duration of the event, respectively
    :rtype: Tuple[str, str, str]
    """
    if duration is None:
        if start and end:
            duration = end - start
        else:
            duration = default_dur if default_dur else timedelta(minutes=30)
    if not start:
        start = end - duration
    if not end:
        end = start + duration
    st = 'start=%s' % Pdatetime_to_datetime_sexp(start)
    en = 'end=%s' % Pdatetime_to_datetime_sexp(end)
    dur = 'duration=%s' % Ptimedelta_to_period_sexp(duration)
    return st, en, dur


def skip_minutes(current_time, iterator, minutes):
    """
    Returns a new date, from `iterator`, that is at least `minutes` after `current_time`.

    :param current_time: the current time
    :type current_time: datetime
    :param iterator: the iterator
    :type iterator: Iterator[datetime]
    :param minutes: the number of minutes
    :type minutes: timedelta
    :return: a new datetime object that is at least `minutes` after `current_time`
    :rtype: datetime
    :raise StopIteration: if the iterator ends before a datetime `minutes` after `current_time` can be reached
    """
    next_time = current_time
    while next_time - current_time < minutes:
        next_time = next(iterator)

    return next_time
