"""
Useful function to deal with the database.
"""
from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict

import sqlalchemy
from sqlalchemy import func, cast, Integer, String, Interval, Time, Date, DateTime

from opendf.defs import database_connection


class DatabaseSystem(Enum):
    """
    Enumerates the supported database systems.

    Note: other system might be supported, but were not tested.
    """

    SQLITE = "sqlite"
    POSTGRES = "postgresql"  # not supported yet
    UNKNOWN = None

    @classmethod
    def get_database_system(cls):
        """
        Gets the database system given the database connection string.

        :return: the database system value
        :rtype: "DatabaseSystem"
        """
        values = database_connection.split(":", maxsplit=1)[0].split("+")
        for item in cls:
            if item.value in values:
                return item
        return cls.UNKNOWN


DATABASE_SYSTEM = DatabaseSystem.get_database_system()


class DatabaseDateTimeHandler(ABC):
    """
    Class to handle database specific logic.
    """

    def __init__(self):
        """
        Default constructor with no parameters.
        """

    @abstractmethod
    def to_database_datetime(self, value):
        """
        Converts the value to the database specific datetime.

        :param value: the value
        :type value: Any
        :return: the database specific datetime
        :rtype: Any
        """
        pass

    @abstractmethod
    def to_database_date(self, value):
        """
        Converts the value to the database specific date.

        :param value: the value
        :type value: Any
        :return: the database specific date
        :rtype: Any
        """
        pass

    @abstractmethod
    def to_database_time(self, value):
        """
        Converts the value to the database specific time.

        :param value: the value
        :type value: Any
        :return: the database specific time
        :rtype: Any
        """
        pass

    @abstractmethod
    def database_date_to_minute(self, value):
        """
        Extracts the minute value from the database specific time.

        :param value: the database value
        :type value: Any
        :return: the minute value
        :rtype: Any
        """
        pass

    @abstractmethod
    def database_date_to_hour(self, value):
        """
        Extracts the hour value from the database specific time.

        :param value: the database value
        :type value: Any
        :return: the hour value
        :rtype: Any
        """
        pass

    @abstractmethod
    def database_date_to_day(self, value):
        """
        Extracts the day value from the database specific time.

        :param value: the database value
        :type value: Any
        :return: the day value
        :rtype: Any
        """
        pass

    @abstractmethod
    def database_date_to_month(self, value):
        """
        Extracts the month value from the database specific time.

        :param value: the database value
        :type value: Any
        :return: the month value
        :rtype: Any
        """
        pass

    @abstractmethod
    def database_date_to_year(self, value):
        """
        Extracts the year value from the database specific time.

        :param value: the database value
        :type value: Any
        :return: the year value
        :rtype: Any
        """
        pass

    @abstractmethod
    def database_date_to_day_of_week(self, value):
        """
        Extracts the day of the week value from the database specific time. Such as Sunday = 0 and Saturday = 6.

        :param value: the database value
        :type value: Any
        :return: the day of the week value
        :rtype: Any
        """
        pass

    @abstractmethod
    def database_datetime_offset(self, value, offset):
        """
        Computes a datetime column based on `value` and `offset`. Where `value` is a column of type datetime; and
        `offset` is a column of type int, which represents the offset in minutes.

        :param value: the datetime column
        :type value: Any
        :param offset: the offset column
        :type offset: Any
        :return: the offset datetime column
        :rtype: Any
        """
        pass

    @abstractmethod
    def get_database_duration_column(self, start_column, end_column):
        """
        Creates a duration column representation from the start and end columns, in seconds.

        :param start_column: the start column
        :type start_column: Any
        :param end_column: the end column
        :type end_column: Any
        :return: the duration column
        :rtype: Any
        """
        pass


database_handlers: Dict[DatabaseSystem, DatabaseDateTimeHandler] = dict()


def registry(func, identifier, func_dict):
    """
    Registries the function or class.

    :param func: the function
    :type func: Callable
    :param identifier: the function identifier
    :type identifier: DatabaseSystem
    :param func_dict: the dictionary to registry the function in
    :type func_dict: dict[DatabaseSystem, DatabaseDateTimeHandler]
    :return: the function
    :rtype: Callable
    """
    func_dict[identifier] = func()
    return func


def database_handler(identifier):
    """
    Decorator to define which class will handle which database system.

    :param identifier: the identifier of the database
    :type identifier: DatabaseSystem
    :return: the decorated function
    :rtype: function
    """
    return lambda x: registry(x, identifier, database_handlers)


@database_handler(DatabaseSystem.SQLITE)
class SQLiteDateTimeHandler(DatabaseDateTimeHandler):
    """
    Class to handle SQLite datetime database specific logic.
    """

    def to_database_datetime(self, value):
        return func.datetime(value)

    def to_database_date(self, value):
        return func.date(value)

    def to_database_time(self, value):
        return func.time(value)

    def database_date_to_minute(self, value):
        return cast(func.strftime('%M', value), Integer)

    def database_date_to_hour(self, value):
        return cast(func.strftime('%H', value), Integer)

    def database_date_to_day(self, value):
        return cast(sqlalchemy.func.strftime('%d', value), Integer)

    def database_date_to_month(self, value):
        return cast(sqlalchemy.func.strftime('%m', value), Integer)

    def database_date_to_year(self, value):
        return cast(sqlalchemy.func.strftime('%Y', value), Integer)

    def database_date_to_day_of_week(self, value):
        return cast(sqlalchemy.func.strftime('%w', value), Integer)

    def database_datetime_offset(self, value, offset):
        offset_column = "+" + cast(offset, String) + " minutes"
        return func.datetime(value, offset_column)

    def get_database_duration_column(self, start_column, end_column):
        # computing duration in sqlite is a little tricky
        start_julian = sqlalchemy.func.julianday(start_column)
        end_julian = sqlalchemy.func.julianday(end_column)
        duration_julian = end_julian - start_julian  # now we have the duration in day
        duration_seconds = duration_julian * 24 * 60 * 60  # duration in seconds
        duration_column = sqlalchemy.func.round(duration_seconds)

        return duration_column


@database_handler(DatabaseSystem.POSTGRES)
class PostgresDateTimeHandler(DatabaseDateTimeHandler):
    """
    Class to handle Postgres datetime database specific logic.
    """

    def to_database_datetime(self, value):
        return cast(value, DateTime)

    def to_database_date(self, value):
        return cast(value, Date)

    def to_database_time(self, value):
        return cast(value, Time)

    def database_date_to_minute(self, value):
        return func.date_part("minute", value)

    def database_date_to_hour(self, value):
        return func.date_part("hour", value)

    def database_date_to_day(self, value):
        return func.date_part("day", value)

    def database_date_to_month(self, value):
        return func.date_part("month", value)

    def database_date_to_year(self, value):
        return func.date_part("year", value)

    def database_date_to_day_of_week(self, value):
        return func.mod(cast(func.date_part("isodow", value), Integer), 7)

    def database_datetime_offset(self, value, offset):
        offset_column = cast(cast(offset, String) + " minutes", Interval)
        return value + offset_column

    def get_database_duration_column(self, start_column, end_column):
        return func.date_part("epoch", end_column - start_column)


def get_database_handler():
    """
    Gets the database datetime handler for the used database.

    If there is no handler for the used database, it returns the default handler instead.

    :return: the database datetime handler
    :rtype: DatabaseDateTimeHandler
    """
    handler = database_handlers.get(DATABASE_SYSTEM)
    if handler is None:
        handler = database_handlers[DatabaseSystem.SQLITE]

    return handler
