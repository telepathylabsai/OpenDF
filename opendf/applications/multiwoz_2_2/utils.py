import re
from opendf.parser.pexp_parser import escape_string

HOTEL_PREFIX = "hotel-"
HOTEL_PREFIX_LENGTH = len(HOTEL_PREFIX)

RESTAURANT_PREFIX = "restaurant-"
RESTAURANT_PREFIX_LENGTH = len(RESTAURANT_PREFIX)

ATTRACTION_PREFIX = "attraction-"
ATTRACTION_PREFIX_LENGTH = len(ATTRACTION_PREFIX)

TRAIN_PREFIX = "train-"
TRAIN_PREFIX_LENGTH = len(TRAIN_PREFIX)

HOSPITAL_PREFIX = "hospital-"
HOSPITAL_PREFIX_LENGTH = len(HOSPITAL_PREFIX)

TAXI_PREFIX = "taxi-"
TAXI_PREFIX_LENGTH = len(TAXI_PREFIX)

POLICE_PREFIX = "police-"
POLICE_PREFIX_LENGTH = len(POLICE_PREFIX)

SKIPPED_INTENTS = {'NONE'}

SPECIAL_VALUES = {
    "dontcare": "Clear()"
}

TIME_REGEX = re.compile(r"([0-9]+):([0-9]+)")

SPECIAL_CHARS = {"&"}

PERSIST_SIDE = False



def normalize_time(value):
    value = value.lower()
    value = re.sub('[? ]', '', value)
    value = re.sub('after', '', value)
    if value.lower() == 'lunch':
        value = '12:00'

    match = TIME_REGEX.fullmatch(value)
    if match:
        hour, minute = match.groups()
        value = f"{int(hour) % 24:02d}:{int(minute) % 60:02d}"
    else:
        value = escape_string(value)
    return value


def select_value(values):
    value = ""
    for value in values:
        if not any(map(lambda x: x in value, SPECIAL_CHARS)):
            return value
    return value


def edit_distance(s1, s2):
    m = len(s1) + 1
    n = len(s2) + 1

    tbl = {}
    for i in range(m): tbl[i, 0] = i
    for j in range(n): tbl[0, j] = j
    for i in range(1, m):
        for j in range(1, n):
            cost = 0 if s1[i - 1] == s2[j - 1] else 1
            tbl[i, j] = min(tbl[i, j - 1] + 1, tbl[i - 1, j] + 1, tbl[i - 1, j - 1] + cost)

    return tbl[i, j]
