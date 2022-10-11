"""
Weather related functions.
"""
import math
from datetime import date, timedelta
from opendf.applications.core.nodes.time_nodes import Pdate_to_Pdatetime, DateTime, Pdate_to_values, dow_to_name, monthname
from opendf.graph.nodes.node import Node
from opendf.defs import get_system_date


def time_filter_weather_dict(dct, filt: DateTime):
    fdc = {}
    # d_context = DialogContext()
    if filt.get_ext_dat("time.minute"):
        filt: Node = Node.duplicate_tree(filt)[-1]
        filt.input_view("time").disconnect_input("minute")

    for l in dct:
        dc = dct[l]
        for dt in dc:
            pdt = Pdate_to_Pdatetime(dt)
            n = DateTime.from_Pdatetime(pdt, None, register=False)
            for h in dc[dt]:
                n.inputs['time'].inputs['hour'].data = h  # more efficient, in-place mod instead of create new node
                if filt.match(n, match_miss=True):
                    if l not in fdc:
                        fdc[l] = {}
                    if dt not in fdc[l]:
                        fdc[l][dt] = {}
                    fdc[l][dt][h] = dc[dt][h]
    return fdc


# weather table format:
# "Zurich+2021-08-30|9:12:-,10:14:cloudy,11:15:rain/Bern+2021-08-30|9:10:snow,10:11:-,11:15:rain"
def wtable_to_dict(ws):
    """
    Converts weather table (string) to dict of dicts.
    """
    locs = {}
    for row in ws.split('/'):
        s = row.split('|')
        [loc, dt] = s[0].split('+')
        dt = date.fromisoformat(dt)
        s1 = s[1].split(';')
        if loc not in locs:
            locs[loc] = {}
        locs[loc][dt] = {}
        for p in s1:
            [h, t, w] = p.split(':')
            locs[loc][dt][int(h)] = (int(t), w)
    return locs


def dict_to_wtable(d):
    """
    Converts weather dict to table (string format).
    """
    w = []
    for l in d:
        for dt in d[l]:
            s = ';'.join(['%d:%d:%s' % (h, d[l][dt][h][0], d[l][dt][h][1]) for h in d[l][dt]])
            w.append(l + '+' + dt.isoformat() + '|' + s)
    return '/'.join(w)


def upper_case_first_letter(string):
    """
    Returns the string with the first letter in upper case form.

    :param string: the string
    :type string: str
    :return: the string, with the first letter in upper case form
    :rtype: str
    """
    return string[0].upper() + string[1:]


def wtab_row_summary(dc, l, dt):
    """
    Returns a pretty-printable string summary of weather table row.
    """

    loc = upper_case_first_letter(l)
    h = [i for i in dc[l][dt]]
    t = sorted([dc[l][dt][i][0] for i in dc[l][dt]])
    w = list(set([dc[l][dt][i][1] for i in dc[l][dt]]))
    yr, mn, dy = Pdate_to_values(dt)
    dow = dow_to_name(dt.weekday() + 1)[:3]
    mn = monthname[mn - 1]
    tstr = ' / %d:00' % h[0] if h[0] == h[-1] else '' if h[0] == 0 and h[-1] == 23 else ' / %d:00~%d' % (h[0], h[-1])
    s = '%s / %s %s %d%s: low %d, high %d, %s' % (loc, dow, mn, dy, tstr, t[0], t[-1], '/'.join(w))
    return s


def compute_distance(x, y):
    """
    Computes the Euclidean distance between to points `x` and `y` in an n-dimensional space.

    :param x: the point x
    :type x: List[int]
    :param y: the point y
    :type y: List[int]
    :return: the distance between `x` and `y`
    :rtype: float
    """

    if x is None or y is None:
        return 9999999.9
    total = 0.0
    for i, j in zip(x, y):
        if i is None or j is None:
            return 9999999.9
        total += (i - j) ** 2

    return math.sqrt(total)


def find_closest_weather_information(latitude, longitude, WEATHER_TABLE):
    """
    Finds the weather information of the closest location based on the `latitude` and `longitude`.

    :param latitude: the latitude
    :type latitude: float
    :param longitude: the longitude
    :type longitude: float
    :return: the weather information of the closest location
    :rtype: Tuple[str, List[Tuple[int, str]]
    """
    smaller_distance = None
    closest_weather = None

    for coordinates, weather in WEATHER_TABLE.items():
        distance = compute_distance(coordinates, (latitude, longitude))
        if smaller_distance is None or distance < smaller_distance:
            smaller_distance = distance
            closest_weather = weather

    return closest_weather


def create_weather_prediction(weather):
    """
    Creates a FAKE hourly weather prediction based on `weather`. The output format is:
    <place name>+<date>|<hour>:<temperature>:<condition>[;<hour>:<temperature>:<condition>]*[/<place
    name>+<date>|<hour>:<temperature>:<condition>[;<hour>:<temperature>:<condition>]*]*

    Where the names between <> (angle brackets) are replaced by their corresponding values and the expressions
    between []* may appear zero or more times, depending on the number of values.

    :param weather: the weather base for the random prediction. It is a tuple containing the name of the city and a
    list of tuples containing the base temperature and the weather condition for each day
    :type weather: Tuple[str, List[Tuple[int, str]]
    :return: the weather prediction
    :rtype: str
    """
    weather_offs = [-int(math.cos(i * 2 * 3.14 / 24.0) * 5) for i in range(24)]
    if weather:
        d = []
        system_date = get_system_date()
        for i, (temp, cond) in enumerate(weather[1]):
            s = weather[0] + '+' + str(system_date + timedelta(days=i))
            p = ';'.join(['%d:%d:%s' % (j, temp + weather_offs[j], cond) for j in range(24)])
            d.append(s + '|' + p)
        return '/'.join(d)
    else:
        return ''


def get_weather_prediction(latitude, longitude, WEATHER_TABLE):
    """
    Gets the other information for the coordinates.

    :param latitude: the latitude
    :type latitude: float
    :param longitude: the longitude
    :type longitude: float
    :return: the weather prediction
    :rtype: str
    """
    weather = find_closest_weather_information(latitude, longitude, WEATHER_TABLE)
    return create_weather_prediction(weather)
