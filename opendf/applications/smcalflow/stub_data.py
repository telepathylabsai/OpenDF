"""
Holds the stub data (concerning the smcalflow application) to test the system.
"""

from collections import namedtuple
from datetime import timedelta

from opendf.defs import get_system_date

CURRENT_RECIPIENT_ID = 1007
CURRENT_RECIPIENT_LOCATION_ID = 7

# not bothering with nicknames for now
DBPerson = namedtuple(
    'DBPerson', ['fullName', 'firstName', 'lastName', 'id', 'phone_number', 'email_address',
                 'manager_id', 'friends'])
db_persons = [
    DBPerson('John Doe', 'John', 'Doe', 1001, '41761231001', 'john.doe@opendf.com', 1006, []),  # friend of Adam (current user)
    DBPerson('Jane Doe', 'Jane', 'Doe', 1002, '41761231002', 'jane.doe@opendf.com', 1003, []),
    DBPerson('Jon Smith', 'Jon', 'Smith', 1003, '41761231003', 'jon.smith@opendf.com', 1004, []),  # friend of Adam (current user)
    # DBPerson('John_Smith', 'John', 'Smith', 1003, '41761231004', 'john.smith@opendf.com', 1004, []),  # friend of Adam (current user)
    DBPerson('Jane Smith', 'Jane', 'Smith', 1004, '41761231004', 'jane.smith@opendf.com', 1004, []),
    DBPerson('Jerry Skinner', 'Jerry', 'Skinner', 1005, '41761231005', 'jerry.skinner@opendf.com', 1004, []),  # friend of Adam (current user)
    DBPerson('Dan Smith', 'Dan', 'Smith', 1006, '41761231006', 'dan.smith@opendf.com', 1004, []),
    DBPerson('Adam Smith', 'Adam', 'Smith', 1007, '41761231007', 'adam.smith@opendf.com', 1004, [1001, 1003, 1004]),  # <<<< current user!
    DBPerson('Janice  Kang', 'Janice', 'Kang', 1008, '41761231007', 'Janice.Kang@opendf.com', 1004, [1001, 1003, 1004]),
    DBPerson('Cher  Rob', 'Cher', 'Rob', 1009, '41761231007', 'Cher.Rob@opendf.com', 1004, [1001, 1003, 1004]),
]
# when looking for a name - if friendship is considered, then "John" is ambiguous, but "Jane" means Jane Smith.

# for demos - we fill the dummy database with values relative to system's date, to avoid having to manually change the
# dates remember that the coming Friday may be before the coming Wednesday...
# all of these days are AFTER system's date
td = get_system_date()
d0 = td + timedelta(days=[i for i in range(1, 8) if (td + timedelta(days=i)).isoweekday() == 2][0])  # next Tuesday
d1 = td + timedelta(days=[i for i in range(1, 8) if (td + timedelta(days=i)).isoweekday() == 3][0])  # next Wednesday
d2 = td + timedelta(days=[i for i in range(1, 8) if (td + timedelta(days=i)).isoweekday() == 4][0])  # next Thursday
d3 = td + timedelta(days=[i for i in range(1, 8) if (td + timedelta(days=i)).isoweekday() == 5][0])  # next Friday
d5 = td + timedelta(days=[i for i in range(1, 8) if (td + timedelta(days=i)).isoweekday() == 7][0])  # next Sunday

dTue = '%d/%d/%d/' % (d0.year, d0.month, d0.day)  # the coming Tuesday
dWed = '%d/%d/%d/' % (d1.year, d1.month, d1.day)  # the coming Wednesday
dThu = '%d/%d/%d/' % (d2.year, d2.month, d2.day)  # the coming Thursday
dFri = '%d/%d/%d/' % (d3.year, d3.month, d3.day)  # the coming Friday
dSun = '%d/%d/%d/' % (d5.year, d5.month, d5.day)  # the coming Sunday

# TODO: separate between events and calendar
#   each user should have a personal calendar, which has events, and for each event has
#      showAs status and accept/reject flag
#   each event has invitees (and inviter?), but not the status/reply per user

# for multiple attendees - semicolon separated (NOT comma - this interferes with sexp parsing!!)
DBevent = namedtuple('DBevent', ['id', 'subject', 'start', 'end', 'location', 'attendees', 'accepted', 'showas'])

# This shows the entries in the schedule of a specific user (not included in the attendees)
db_events = [
    DBevent(1, 'meeting1', dWed + '9/0', dWed + '9/30', 1, [1001, 1004, 1006],
            ['Accepted', 'Accepted', 'Declined'], ['Busy', 'Busy', 'Free']),
    DBevent(2, 'meeting', dThu + '9/30', dThu + '9/45', 1, [1001, 1006],
            ['Accepted', 'Declined'], ['Busy', 'Free']),
    DBevent(3, 'meeting2', dWed + '10/0', dWed + '10/30', 2, [1002],
            ['Accepted'], ['Busy']),
    DBevent(4, 'meeting3', dThu + '9/0', dThu + '10/0', 3, [1001, 1006, 1007],
            ['Accepted', 'Accepted', 'Declined'], ['Busy', 'Busy', 'Free']),
    DBevent(41, None, dThu + '9/0', dThu + '10/0', 3, [1006, 1007], ['Accepted', 'Accepted'], ['Busy', 'Busy']),
    DBevent(5, 'meeting4', dThu + '12/0', dThu + '14/0', 3, [1004, 1006, 1007],
            ['Accepted', 'Accepted', 'Declined'], ['Busy', 'Busy', 'Free']),
    DBevent(6, 'meeting5', dFri + '14/30', dFri + '15/0', 2, [1001],
            ['Declined'], ['Free']),
    DBevent(7, 'meeting6', dFri + '9/0', dFri + '10/0', 3, [1002, 1006],
            ['Accepted', 'Declined'], ['Busy', 'Busy']),
    DBevent(8, 'meeting7', dWed + '9/30', dWed + '12/0', 7, [1003, 1006, 1007],
            ['Accepted', 'Accepted', 'Declined'], ['Busy', 'Busy', 'Free']),
    DBevent(9, 'meeting8', dFri + '16/30', dFri + '17/0', 5, [1005, 1007],
            ['Accepted', 'Declined'], ['Busy', 'Free']),
    DBevent(10, 'party', dSun + '10/0', dSun + '10/30', 6, [1004, 1007],
            ['Accepted', 'Declined'], ['Busy', 'Busy']),
    DBevent(11, 'meeting', dTue + '10/0', dTue + '10/30', 2, [1006, 1007],
            ['Accepted', 'Declined'], ['Busy', 'Busy']),
]

WeatherPlace = namedtuple("WeatherPlace",
                          ['id', 'name', 'address', 'latitude', 'longitude', 'radius', 'always_free', 'is_virtual'])

ZURICH_COORDINATES = 47.374444, 8.541111
BERN_COORDINATES = 46.947633, 7.404997
TOKYO_COORDINATES = 35.701067, 139.755280
BARCELONA_COORDINATES = 41.411023, 2.163190

weather_places = [
    WeatherPlace(0, 'online', "", None, None, None, True, True),
    WeatherPlace(1, 'room1', "Zürich, Zürich, Switzerland", *ZURICH_COORDINATES, 20, True, False),
    WeatherPlace(2, 'room2', "Zürich, Zürich, Switzerland", *BERN_COORDINATES, 20, True, False),
    WeatherPlace(3, 'room3', "Zürich, Zürich, Switzerland", *ZURICH_COORDINATES, 20, True, False),
    WeatherPlace(4, 'room4', "Zürich, Zürich, Switzerland", *BERN_COORDINATES, 20, True, False),
    WeatherPlace(5, 'room5', "Zürich, Zürich, Switzerland", *ZURICH_COORDINATES, 20, True, False),
    WeatherPlace(6, 'jeffs', "Bern, Bern, Switzerland", *BERN_COORDINATES, 20, True, False),

    WeatherPlace(7, 'zurich', "Zürich, Zürich, Switzerland", *ZURICH_COORDINATES, 7500, True, False),
    WeatherPlace(8, 'bern', "Bern, Bern, Switzerland", *BERN_COORDINATES, 8800, True, False),
    WeatherPlace(9, 'tokyo', "Tokyo, Kanto, Japan", *TOKYO_COORDINATES, 17000, True, False),
    WeatherPlace(10, 'barcelona', "Barcelona, Catalonia, Spain", *BARCELONA_COORDINATES, 5700, True, False),
    WeatherPlace(11, 'letzipark', "", 47.386596, 8.499430, 80, False, False),
    WeatherPlace(12, 'home', "Bahnhofstrasse 1, 8001 Zürich, Zürich, Switzerland", 47.367436, 8.539832, 30, False, False),
]

weather_types = ['cloud', 'clear', 'rain', 'snow', 'storm', 'wind', 'sleet']

WEATHER_TABLE = {
    ZURICH_COORDINATES:
        ('zurich', [(-2, 'snow'), (0, 'cloud'), (5, 'rain'), (7, 'storm'), (10, 'wind'), (10, 'clear'), (0, 'sleet')]),
    BERN_COORDINATES:
        ('bern', [(-5, 'clear'), (-2, 'cloud'), (0, 'snow'), (4, 'rain'), (4, 'rain'), (5, 'cloud'), (0, 'clear')]),
    TOKYO_COORDINATES:
        ('tokyo', [(-8, 'snow'), (-6, 'cloud'), (-6, 'snow'), (0, 'cloud'), (-2, 'clear'), (0, 'rain'), (2, 'rain')]),
    BARCELONA_COORDINATES:
        ('barcelona', [(13, 'rain'), (17, 'rain'), (18, 'clear'), (20, 'clear'), (18, 'cloud'), (17, 'rain'), (21, 'clear')]),
}

place_has_features = {
    6: ["HappyHour"]
}
HOLIDAYS = {
    (1, 1): "NewYearsDay",
    (5, 1): "TestDay",  # test purpose
    (25, 12): "Christmas",
    (31, 12): "NewYearsEve"
}