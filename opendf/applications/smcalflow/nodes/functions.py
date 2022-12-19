"""
Application specific function nodes.
"""
from opendf.applications.smcalflow.exceptions.df_exception import EventConfirmationException, \
    BadEventDeletionException, WeatherInformationNotFoundException, AttendeeNotFoundException, EventNotFoundException, \
    PlaceNotFoundException, PlaceNotFoundForUserException
from opendf.applications.smcalflow.nodes.modifiers import *
from opendf.applications.smcalflow.weather import time_filter_weather_dict, wtable_to_dict, dict_to_wtable, \
    get_weather_prediction, upper_case_first_letter
from opendf.exceptions.df_exception import DFException, InvalidTypeException, IncompatibleInputException, \
    WrongSuggestionSelectionException, InvalidResultException
from opendf.graph.node_factory import NodeFactory
from opendf.utils.utils import comma_id_sexp, geo_distance
from opendf.defs import posname, get_system_datetime
from opendf.exceptions import parse_node_exception, re_raise_exc

logger = logging.getLogger(__name__)

storage = StorageFactory.get_instance()
node_fact = NodeFactory.get_instance()
environment_definitions = EnvironmentDefinition.get_instance()


# ########################################################################################################
# ##############################################  location  ##############################################


class Here(Node):

    def __init__(self):
        super().__init__(Place)

    def exec(self, all_nodes=None, goals=None):
        location = storage.get_current_recipient_location()

        if not location:
            raise PlaceNotFoundForUserException(self)

        s = location_to_str_node(location)
        d, e = self.call_construct_eval(s, self.context, constr_tag=DB_NODE_TAG)
        self.set_result(d)

    def yield_msg(self, params=None):
        m = self.res.describe()
        return Message(f"You are listed to be at {m.text}", objects=m.objects)


class FindPlaceAtHere(Node):
    """
    Finds a place near a location.
    """

    def __init__(self):
        super().__init__(Place)
        self.signature.add_sig('place', [LocationKeyphrase, Str])
        self.signature.add_sig('radiusConstraint', GeoCoords)

    def valid_input(self):
        if not self.input_view('place'):
            raise MissingValueException('place', self)
        if not self.input_view('radiusConstraint'):
            raise MissingValueException('radiusConstraint', self)

    def exec(self, all_nodes=None, goals=None):
        operator = self.input_view('place')
        locations = storage.find_locations_that_match(operator)

        if not locations:
            raise PlaceNotFoundException(operator.dat, self)

        latitude = self.input_view("radiusConstraint").get_dat("lat")
        longitude = self.input_view("radiusConstraint").get_dat("long")

        locations = filter(lambda x: x.latitude is not None and x.longitude is not None, locations)
        radius = environment_definitions.radius_constraint
        locations = list(filter(lambda x: geo_distance(latitude, longitude, x.latitude, x.longitude) < radius,
                                locations))

        if len(locations) > 1:
            s = f"SET({', '.join(map(lambda x: location_to_str_node(x), locations))})"
        else:
            s = location_to_str_node(locations[0])

        d, e = self.call_construct_eval(s, self.context)
        self.set_result(d)


class FindPlace(Node):
    """
    Convert NL description of place (keyphrase) to Place.
    """

    def __init__(self):
        super().__init__(Place)
        self.signature.add_sig(posname(1), [Str, LocationKeyphrase], True, alias='keyphrase')

    def trans_simple(self, top):
        pl = self.input_view('keyphrase')
        if pl.typename() == 'Str':
            self.wrap_input('keyphrase', 'LocationKeyphrase(')

        return self, None

    def exec(self, all_nodes=None, goals=None):
        operator = self.input_view('keyphrase')
        locations = storage.find_locations_that_match(operator)

        if not locations:
            raise PlaceNotFoundException(operator.dat, self)

        location = locations[0]

        s = location_to_str_node(location)
        d, e = self.call_construct_eval(s, self.context, constr_tag=NODE_COLOR_DB)
        d.tags[DB_NODE_TAG] = 0  # draw the root place node darker
        self.set_result(d)


class FindPlaceMultiResults(Node):
    """
    Convert NL description of place (keyphrase) to Places.
    """

    def __init__(self):
        super().__init__(Place)
        self.signature.add_sig(posname(1), [Str, LocationKeyphrase], True, alias='keyphrase')

    def trans_simple(self, top):
        pl = self.input_view('keyphrase')
        if pl.typename() == 'Str':
            self.wrap_input('keyphrase', 'LocationKeyphrase(')

        return self, None

    def exec(self, all_nodes=None, goals=None):
        operator = self.input_view('keyphrase')
        locations = storage.find_locations_that_match(operator)

        if not locations:
            raise PlaceNotFoundException(operator.dat, self)

        if len(locations) > 1:
            s = f"SET({', '.join(map(lambda x: location_to_str_node(x), locations))})"
        else:
            s = location_to_str_node(locations[0])

        d, e = self.call_construct_eval(s, self.context)
        self.set_result(d)


class PlaceDescribableLocation(Node):
    """
    Describes a place.
    """

    def __init__(self):
        super().__init__(PlaceDescribableLocation)
        self.signature.add_sig(posname(1), [Place, Str], True, alias='place')

    def trans_simple(self, top):
        pl = self.input_view('place')
        if pl.typename() == 'Str':
            self.wrap_input('place', 'FindPlace(keyphrase=')

        return self, None

    def yield_msg(self, params=None):
        place_name = upper_case_first_letter(self.input_view('place').get_dat('name'))
        location = self.input_view('place').get_dat('address')
        if not location:
            coordinates = self.input_view('place').input_view('coordinates')
            if coordinates:
                latitude = coordinates.get_dat("lat")
                longitude = coordinates.get_dat("long")
                location = f"{latitude}, {longitude}"

        if location:
            return Message(f"{place_name} is located at {location}", objects=['PL#'+place_name, 'PL#'+location])
        else:
            return Message(f"I cannot find a location for {place_name}")


class AtPlace(Node):
    """
    Converts `Place` to `GeoCoords`.
    """

    def __init__(self):
        super().__init__(GeoCoords)
        self.signature.add_sig("place", Place, True)

    def exec(self, all_nodes=None, goals=None):
        place = re.sub(' ', '_', self.input_view("place").get_dat("name"))  # TODO - verify '_' is needed
        g = self.input_view("place").input_view("coordinates")
        if g:
            self.set_result(g)
        else:
            raise InvalidResultException('Error - Can not convert location (%s) to geo coordinates' % place, self)


class PlaceFeature(Node):
    """
    Represents features for places.
    """

    POSSIBLE_VALUES = {
        "casual", "familyfriendly", "fullbar", "goodforgroups", "happyhour", "outdoordining", "takeout",
        "waiterservice"}

    def __init__(self):
        super().__init__(PlaceFeature)
        self.signature.add_sig('pos1', Str, True)

    def valid_input(self):
        feat = self.dat
        if feat is not None:
            if feat.lower() not in self.POSSIBLE_VALUES:
                raise InvalidOptionException(posname(1), feat, self.POSSIBLE_VALUES, self, hints='PlaceFeature')
        else:
            raise MissingValueException(posname(1), self)


class PlaceHasFeature(Node):
    """
    Checks if place has feature.
    """

    def __init__(self):
        super().__init__()
        self.signature.add_sig('feature', PlaceFeature, True)
        self.signature.add_sig('place', Place, True)

    def valid_input(self):
        if not self.input_view('feature'):
            raise MissingValueException('feature', self)
        if not self.input_view('place'):
            raise MissingValueException('place', self)

    def exec(self, all_nodes=None, goals=None):
        place = self.input_view('place')
        feat = self.input_view('feature')

        has_feature = bool(storage.find_feature_for_place(place.get_dat("id"), feat.get_dat(posname(1))))

        s = f"Bool({has_feature})"
        d, e = self.call_construct_eval(s, self.context)
        self.set_result(d)

    def yield_msg(self, params=None):
        has_feature = self.res.dat
        place = upper_case_first_letter(self.input_view('place').get_dat('name'))
        feat = self.input_view('feature').get_dat(posname(1))
        if has_feature:
            return Message(f"{place} is good for {feat}.", objects=['PL#'+place, 'FT#'+feat, 'VAL#Yes'])
        else:
            return Message(f"{place} is not good for {feat}.", objects=['PL#'+place, 'FT#'+feat, 'VAL#No'])


# #######################################################################################################
# ##############################################  weather  ##############################################

# TODO: implement IsHighUV
class WeatherQueryApi(Node):
    """
    Gets weather at (possibly multiple) time and place.
    """

    def __init__(self):
        super().__init__(WeatherTable)
        self.signature.add_sig('place', [GeoCoords, Place, LocationKeyphrase, Str])
        self.signature.add_sig('time', [DateTime, Date, DateRange, Time, TimeRange])
        self.signature.add_sig('pos1', Event, alias='event')

    def trans_simple(self, top):
        if "event" not in self.inputs:
            pl = self.input_view('place')
            if pl.typename() == 'Str' or pl.typename() == 'LocationKeyphrase':
                self.wrap_input('place', 'AtPlace(place=FindPlace(keyphrase=', do_eval=False)
            elif pl.typename() == 'Place':
                self.wrap_input('place', 'AtPlace(place=', do_eval=False)

            tm = self.input_view('time')
            if tm and (tm.typename() == 'Date' or tm.out_type.__name__ == 'Date'):
                self.wrap_input('time', 'DateTime(date=', do_eval=False)

        return self, None

    def valid_input(self):
        if 'event' in self.inputs:
            if 'place' in self.inputs or 'time' in self.inputs:
                raise IncompatibleInputException('Please, provide either event or (place, time)', self)
        elif not self.input_view('place'):
            raise MissingValueException('place', self)

    def exec(self, all_nodes=None, goals=None):
        place, tm, event = self.get_input_views(['place', 'time', 'event'])
        if not place:
            location = event.input_view("location")
            if not location:
                raise InvalidResultException('Could not find a location for the event.', self)
            place, _ = Node.call_construct_eval(f"AtPlace(place=FindPlace(keyphrase={id_sexp(location)}))", self.context)
            if place:
                place = place.res
        coors = place.input_view('coordinates')
        longitude, latitude = (coors.get_dat("long"), coors.get_dat("lat")) if coors else (None, None)

        _, _, _, _, _, _, _, WEATHER_TABLE = get_stub_data_from_json(self.context.init_stub_file)
        wtab = get_weather_prediction(latitude, longitude, WEATHER_TABLE)

        if not tm:
            tm = event.get_ext_view("slot.start")
            if not tm:
                raise InvalidResultException('Could not find a time for the event.', self)

        wdc = wtable_to_dict(wtab)
        if tm:
            wdc = time_filter_weather_dict(wdc, tm)
            wtab = dict_to_wtable(wdc)

        if not wtab:
            raise WeatherInformationNotFoundException('Could not find weather information for this.', self)

        s = 'WeatherTable(table=%s)' % wtab
        d, e = self.call_construct_eval(s, self.context)
        self.set_result(d)

    def yield_msg(self, params=None):
        return self.res.describe()


# Should probably handle this at simplify (convert to a WeatherQueryApi)
class WeatherForEvent(WeatherQueryApi):
    """
    Gets the weather for an event.
    """
    pass


class WeatherAggregate(Node):
    """
    Aggregates information about the weather.
    """

    def __init__(self):
        super().__init__(Float)
        self.signature.add_sig('property', WeatherProp)
        self.signature.add_sig('quantifier', WeatherQuantifier)
        self.signature.add_sig('table', [WeatherTable, Str])

    def trans_simple(self, top):
        table = self.input_view('table')
        if table is not None and table.typename() == 'Str':
            self.wrap_input('table', 'WeatherQueryApi(place=', do_eval=False)

        return self, None

    def valid_input(self):
        if not self.input_view('property'):
            raise MissingValueException('property', self)
        if not self.input_view('quantifier'):
            raise MissingValueException('quantifier', self)
        if not self.input_view('table'):
            raise MissingValueException('table', self)

    def exec(self, all_nodes=None, goals=None):
        w = self.get_dat('table')
        dc = wtable_to_dict(w)

        values = self.extract_values_from_table(dc)
        result = self.compute_result(values)

        s = 'Float(%s)' % result
        d, e = self.call_construct_eval(s, self.context)
        self.set_result(d)

    def extract_values_from_table(self, dc):
        prop = self.get_dat("property")
        if prop != "temperature":
            raise InvalidResultException(f"Unsupported property {prop}", self)
        values = []
        for temperatures_ in dc.values():
            for temperatures in temperatures_.values():
                for temperature, condition in temperatures.values():
                    values.append(temperature)

        return values

    def compute_result(self, values):
        quantifier = self.get_dat("quantifier").lower()
        if quantifier == "summarize":
            # TODO: for now, do the same as average
            return sum(values) / len(values)
        elif quantifier == "average":
            return sum(values) / len(values)
        elif quantifier == "sum":
            return sum(values)
        elif quantifier == "min":
            return min(values)
        elif quantifier == "max":
            return max(values)
        else:
            InvalidResultException(f"Unsupported quantifier {self.get_dat('quantifier')}", self)

    def yield_msg(self, params=None):
        value = self.res.dat
        quantifier = self.get_dat("quantifier").lower()
        quant = "average "
        if quantifier == "sum":
            quant = "summed "
        elif quantifier == "min":
            quant = "minimum "
        elif quantifier == "max":
            quant = "maximum "

        table = self.get_dat('table')
        place = table[:table.find("+")]
        dates = sorted(wtable_to_dict(table)[place].keys())
        interval = f" {describe_Pdate(dates[0], ['prep'])}"
        if len(dates) > 1:
            interval = f"from {describe_Pdate(dates[0])} to {describe_Pdate(dates[-1])}"

        return Message(f"The {quant}temperature in {upper_case_first_letter(place)} {interval} is {value:.1f}°C",
                       objects=['PL#'+place, 'VAL#%.1f'%value])


class IsCold(Node):
    """
    Will it be cold in the given weather table?
    """

    # for now - enough that just one point is "cold"
    def __init__(self):
        super().__init__(Bool)  # Str would allow more detailed answers
        self.signature.add_sig(posname(1), WeatherTable, True, alias='table')

    def exec(self, all_nodes=None, goals=None):
        w = self.get_dat('table')
        dc = wtable_to_dict(w)
        cold = self.is_cold(dc, 15)
        s = 'Bool(%s)' % cold
        d, e = self.call_construct_eval(s, self.context)
        self.set_result(d)

    def is_cold(self, dc, threshold):
        for l in dc:
            for dt in dc[l]:
                for i in dc[l][dt]:
                    if dc[l][dt][i][0] < threshold:
                        return True
        return False

    def yield_msg(self, params=None):
        r = self.res.dat
        location = upper_case_first_letter(self.input_view("table").dat.split("+", 1)[0])
        if r:
            return Message('Yes, it is cold in %s' % location, objects=['PL#'+location, 'VAL#Yes'])
        else:
            return Message('No, it\'s not predicted to be cold in %s' % location, objects=['PL#'+location, 'VAL#No'])


class IsHot(Node):
    """
    Will it be hot in the given weather table?
    """

    # for now - enough that just one point is "hot"
    def __init__(self):
        super().__init__(Bool)  # Str would allow more detailed answers
        self.signature.add_sig('table', WeatherTable, True)

    def exec(self, all_nodes=None, goals=None):
        w = self.get_dat('table')
        dc = wtable_to_dict(w)
        hot = self.is_hot(dc, 20)
        s = 'Bool(%s)' % hot
        d, e = self.call_construct_eval(s, self.context)
        self.set_result(d)

    def is_hot(self, dc, threshold):
        for l in dc:
            for dt in dc[l]:
                for i in dc[l][dt]:
                    if dc[l][dt][i][0] > threshold:
                        return True
        return False

    def yield_msg(self, params=None):
        r = self.res.dat
        location = upper_case_first_letter(self.input_view("table").dat.split("+", 1)[0])
        return Message('Yes, it is hot in %s' % location if r else 'No, it\'s not predicted to be hot in %s' % location)


class IsWeatherCondition(Node):
    """
    Checks if the weather condition holds for the place and time.
    """

    def __init__(self, condition_name=None, condition_noun=None, condition_adjective=None):
        super(IsWeatherCondition, self).__init__(Bool)
        self.signature.add_sig('table', WeatherTable, True)
        # shortcut notation - allow to directly input time and place - save need to explicitly call WeatherQueryApi
        self.signature.add_sig('place', [GeoCoords, Place, LocationKeyphrase, Str])
        self.signature.add_sig('time', DateTime)

        self.condition_name = condition_name
        if self.condition_name:
            self.condition_noun = condition_noun
            if self.condition_noun is None:
                self.condition_noun = condition_name.lower()
            self.condition_adjective = condition_adjective
            if self.condition_adjective is None:
                self.condition_adjective = self.condition_noun + 'y'

    def valid_input(self):
        if not self.input_view('table'):
            if not self.input_view('place'):
                raise MissingValueException('place', self)
            if not self.input_view('time'):
                raise MissingValueException('time', self)
            pl, tm = self.input_view('place'), self.input_view('time')
            d, e = self.call_construct_eval('WeatherQueryApi(place=%s,time=%s)' % (id_sexp(pl), id_sexp(tm)), self.context)
            self.add_linked_input('table', d)
        else:
            if self.input_view('place') or self.input_view('time'):
                raise IncompatibleInputException(f"Please, provide only table or (place and time)", self)

    def has_condition(self):
        w = self.get_dat('table')
        dc = wtable_to_dict(w)
        for l in dc:
            for dt in dc[l]:
                w = list(set([dc[l][dt][i][1] for i in dc[l][dt]]))
                if self.condition_name in w:
                    return True
        return False

    def condition_times(self):
        w = self.get_dat('table')
        dc = wtable_to_dict(w)
        st = []
        for l in dc:
            for dt in dc[l]:
                w = list(set([dc[l][dt][i][1] for i in dc[l][dt]]))
                if self.condition_name in w:
                    st.append((l, dt))
        return st

    def exec(self, all_nodes=None, goals=None):
        s = f"Bool({self.has_condition()})"
        d, e = self.call_construct_eval(s, self.context)
        self.set_result(d)

    def yield_msg(self, params=None):
        r = self.res.dat
        location = upper_case_first_letter(self.input_view("table").dat.split("+", 1)[0])
        inf = location
        if r:
            # TODO: add place / date / time description, get it from the weather table
            st = self.condition_times()
            inf = f"{location} {describe_Pdate(st[0][1], ['prep'])}"
        if r:
            return Message(f"Yes, it is {self.condition_adjective} in %s" % inf, objects=['PL#'+location, 'VAL#Yes'])
        else:
            return Message(f"No, there is no prediction of {self.condition_noun} in %s" % inf,
                           objects=['PL#'+location, 'VAL#No'])


class IsRainy(IsWeatherCondition):
    """
    Checks if there is rain in the weather forecast.
    """

    def __init__(self):
        super().__init__("rain")


class IsSnowy(IsWeatherCondition):
    """
    Checks if there is snow in the weather forecast.
    """

    def __init__(self):
        super().__init__("snow")


class IsStormy(IsWeatherCondition):
    """
    Checks if there is storm in the weather forecast.
    """

    def __init__(self):
        super().__init__("storm")


class IsClear(IsWeatherCondition):
    """
    Checks if it is a clear weather, according to the forecast.
    """

    def __init__(self):
        super().__init__("clear", condition_noun="clear weather", condition_adjective="clear")


class IsSunny(IsClear):
    """
    An alias for `IsClear`.
    """
    pass


class IsWindy(IsWeatherCondition):
    """
    Checks if there is wind in the weather forecast.
    """

    def __init__(self):
        super().__init__("wind")


class IsCloudy(IsWeatherCondition):
    """
    Checks if there is cloud in the weather forecast.
    """

    def __init__(self):
        super().__init__("cloud")


class IsSleety(IsWeatherCondition):
    """
    Checks if there is sleet in the weather forecast.
    """

    def __init__(self):
        super().__init__("sleet")


class WillRain(IsRainy):
    """
    An alias for `IsRainy`.
    """
    pass


class WillSleet(IsSleety):
    """
    An alias for `IsSleety`.
    """
    pass


class WillSnow(IsSnowy):
    """
    An alias for `IsSnowy`.
    """
    pass


class NeedsJacket(IsCold):
    """
    An alias for `IsCold`.
    """
    pass


class inFahrenheit(Node):

    def __init__(self):
        super().__init__(Float)
        self.signature.add_sig(posname(1), Float, True)

    def exec(self, all_nodes=None, goals=None):
        celsius = self.get_dat(posname(1))
        fahrenheit = celsius * 1.8 + 32

        g, _ = Node.call_construct_eval(f"Float({fahrenheit})", self.context)

        self.set_result(g)


class toFahrenheit(inFahrenheit):
    pass


class inCelsius(Node):

    def __init__(self):
        super().__init__(Float)
        self.signature.add_sig(posname(1), Float, True)

    def exec(self, all_nodes=None, goals=None):
        fahrenheit = self.get_dat(posname(1))
        celsius = (fahrenheit - 32) / 1.8

        g, _ = Node.call_construct_eval(f"Float({celsius})", self.context)

        self.set_result(g)


class inInches(Node):

    def __init__(self):
        super().__init__(Float)
        self.signature.add_sig(posname(1), Float, True)  # in meters

    def exec(self, all_nodes=None, goals=None):
        centimeter = self.get_dat(posname(1)) * 100
        inches = centimeter / 2.54

        g, _ = Node.call_construct_eval(f"Float({inches})", self.context)

        self.set_result(g)


class inUsMilesPerHour(Node):

    def __init__(self):
        super().__init__(Float)
        self.signature.add_sig(posname(1), Float, True)  # in Km/h

    def exec(self, all_nodes=None, goals=None):
        km_h = self.get_dat(posname(1))
        m_h = km_h / 1.609

        g, _ = Node.call_construct_eval(f"Float({m_h})", self.context)

        self.set_result(g)


# ######################################################################################################
# ##############################################  person  ##############################################


class CurrentUser(Node):

    def __init__(self):
        super().__init__(Recipient)

    def exec(self, all_nodes=None, goals=None):
        d = storage.get_current_recipient_graph(self.context)
        self.set_result(d)


class FindManager(Node):
    def __init__(self):
        super().__init__(Recipient)
        self.signature.add_sig(posname(1), [Recipient, PersonName, Str], True)

    def exec(self, all_nodes=None, goals=None):
        rcpt = self.input_view('pos1')
        if not rcpt or rcpt.typename() != 'Recipient':
            raise InvalidResultException("Recipient not found", self)
        idx = rcpt.get_dat('id')
        if not idx:
            raise InvalidResultException("Error - Recipient has no id", self)
        p = storage.get_manager(idx)
        if not p:
            raise InvalidResultException("Error - Could not find manager of #%d" % idx, self)
        d, e = self.call_construct_eval(recipient_to_str_node(p), self.context, constr_tag=NODE_COLOR_DB)
        self.set_result(d)

    def trans_simple(self, top):
        if posname(1) in self.inputs and (
                self.inputs[posname(1)].typename() == 'Str' or self.inputs[posname(1)].outypename() == 'Str'):
            self.wrap_input(posname(1), 'Recipient?(', do_eval=False)  # Recipient.trans_simple will expand this further
        return self, None


class prefer_friends(Node):
    """
    If possible, filter set of recipients to only friends.
    """

    def __init__(self):
        super().__init__(Recipient)
        self.signature.add_sig(posname(1), Node, True)  # one or multiple Recipients

    def valid_input(self):
        inp = self.input_view('pos1')
        if inp.not_operator() and inp.typename() != 'Recipient':
            raise InvalidTypeException("Invalid input - expecting one or multiple Recipients, got %s" % inp, self)
        if inp.is_operator():
            objs = inp.get_op_objects()
            if any([i for i in objs if i.typename() != 'Recipient']):
                raise InvalidTypeException("Invalid input - aggregation of Recipients - got %s" % inp, self)

    def exec(self, all_nodes=None, goals=None):
        inp = self.input_view('pos1')
        if inp.is_operator():
            friends = storage.get_friends(storage.get_current_recipient_id())
            objs = inp.get_op_objects()
            fr = [i for i in objs if i.get_dat('id') and i.get_dat('id') in friends]
            if 0 < len(fr) < len(objs):
                if len(fr) == 1:
                    self.set_result(fr[0])
                else:
                    r, e = self.call_construct_eval('SET(' + comma_id_sexp(fr) + ')', self.context)
                    self.set_result(r)
            else:
                self.set_result(inp)
        else:  # single object
            self.set_result(inp)


# ####################################################################################################
# ############################################## Recipient  ###########################################

# similar to recursive wrap_input, but duplicate nodes - do it during exec, and go inside aggregations
# class MapFunc(Node):
#     def __init__(self):
#         super().__init__(Node)
#         self.signature.add_sig(posname(1), Node, True)
#         self.signature.add_sig(posname(2), Str, True, alias='func')
#
#     @staticmethod
#     def get_wrapped_expr(nd, fn):
#         if nd.is_operator():
#             ii = [MapFunc.get_wrapped_expr(nd.input_view(i), fn) for i in nd.inputs]
#             return nd.typename() + '(' + ','.join(ii) + ')' if ii else ''
#         fn = fn[:-1] if fn[-1]=='(' else fn
#         prnt = ')' * (fn.count('(') - fn.count(')'))
#         return '%s(%s)%s' % (fn, id_sexp(nd), prnt)
#
#     def exec(self, all_nodes=None, goals=None):
#         nd = self.input_view(posname(1))
#         fn = self.input_view(posname(2))
#         s = self.get_wrapped_expr(nd, fn)
#         d, _ = self.call_construct_eval(s)
#         self.set_result(d)

# todo - this is a minimal implementation - needs to cover more cases
class toRecipientConstr(Node):
    def __init__(self):
        super().__init__(Event)
        self.signature.add_sig(posname(1), Node, True)

    def exec(self, all_nodes=None, goals=None):
        inp = self.input_view(posname(1))
        if inp.is_operator():
            objs = inp.get_op_objects()
        else:
            objs = [inp]
        rcps = []
        for o in objs:
            if o.typename() == 'Attendee' and 'recipient' in o.inputs:
                r = o.input_view('recipient')
                if 'id' in r.inputs:
                    rcps.append('Recipient?(id=%d)' % r.get_dat('id'))
        if not rcps:
            raise RecipientNotFoundException(self)
        s = rcps[0] if len(rcps) == 1 else 'OR(' + ','.join(rcps) + ')'
        d, _ = self.call_construct_eval(s, self.context)
        self.set_result(d)


class ModifyRecipientRequest(Node):
    """
    Convenience function for revising an attendee constraint.
    """

    # gets translated to a revise call
    def __init__(self):
        super().__init__(Event)
        self.signature.add_sig(posname(1), Node, True)

    def valid_input(self):
        inp = self.input_view(posname(1))
        if inp and not inp.is_constraint_tree('Recipient'):  # use is_constraint_tree here - after eval
            raise InvalidTypeException('Wrong input to ModifyRecipient - expecting a modifier tree', self)

    def trans_simple(self, top):
        n = self
        inp = self.input_view(posname(1))
        nd, nm = inp, posname(1)
        prm = 'recipient' if 'recipient' in self.tags else 'rcpconstraint'
        if nd and inp.is_modifier_tree('Recipient'):
            # we want to connect the modifier, not its result. (new_beg's view mode...)
            # TODO: in case of 'event' - need different expression
            self.wrap_input(nm, 'revise(hasParam=%s, new=' % prm, suf=', newMode=modif)', do_eval=False)
            if self.outputs:
                nn, par = self.outputs[-1]
                self.cut_node(posname(1), nn, par)
                n = par  # this will remove self from transformed sexp
        return n, None


class FindRecipients(Node):
    """
    Finds recipients, given a constraint made of modifiers.
    """

    def __init__(self):
        super().__init__(Event)
        self.signature.add_sig(posname(1), Node, True, alias='rcpconstraint')
        self.signature.add_sig('tmp', Node, ptags=['omit_dup'])  # tmp is used for debugging - to draw the pruned tree
        self.signature.set_multi_res(True)  # may return multiple objects as result

    def exec(self, all_nodes=None, goals=None):
        constr = self.input_view('rcpconstraint')

        if constr:
            cp, _ = constr.duplicate_res_tree(keep_turn=True)

            # 1. convert modifiers
            cp.convert_modifiers(self)  # maybe convert BEFORE copy? <<

            # 2. prune contradictions
            cp.prune_modifiers()
        else:
            cp, _ = self.call_construct('Recipient?()', self.context)

        if environment_definitions.show_dbg_constr:
            d, e = self.call_construct('Dummy()', self.context)
            d.connect_in_out('tmp', self)

        if cp.is_constraint_tree('Attendee'):
            s = cp.get_wrapped_expr('toRecipientConstr(FindAttendees')
            cp, _ = self.call_construct(s,
                                        self.context)  # first construct and connect to graph, then eval (in case eval raises exception)
            if environment_definitions.show_dbg_constr:
                self.inputs['tmp'].set_result(cp)
            cp.call_eval(add_goal=False)

        if environment_definitions.show_dbg_constr and self.inputs['tmp'].result and self.inputs['tmp'].result != \
                self.inputs['tmp']:
            self.inputs['tmp'].set_result(cp)

        if environment_definitions.show_SQL:
            msg = str(cp.generate_sql().compile(compile_kwargs={"literal_binds": True}))
            logger.debug('\nSQL statement:\n %s\n', msg)
            msg = msg.replace("<", "&lt;")
            msg = msg.replace(">", "&gt;")
            self.context.add_message(self, MSG_SQL + msg)

        # we want ALL objects from the external DB which match the constraint. not just those in the graph.
        #      and we want to get a fresh copy of these - the DB might have been changed "externally"
        results = Recipient.fallback_search(cp, all_nodes, goals, do_eval=True, params=['ignore_friendship'])

        if not results:
            raise RecipientNotFoundException(self)

        r = node_fact.make_agg(results)
        r.call_eval(add_goal=False)  # pedantic
        self.set_result(r)

    # base function - yielding message from top node
    def yield_msg(self, params=None):
        m = self.res.describe_set(params=params)
        return Message('This is what I could find: NL ' + m.text, objects=m.objects)


# ####################################################################################################
# ############################################## attendee  ###########################################

class ModifyAttendeeRequest(Node):
    """
    Convenience function for revising an attendee constraint.
    """

    # gets translated to a revise call
    def __init__(self):
        super().__init__(Event)
        self.signature.add_sig(posname(1), Node, True)

    def valid_input(self):
        inp = self.input_view(posname(1))
        if inp and not inp.is_constraint_tree('Attendee'):  # use is_constraint_tree here - after eval
            raise InvalidTypeException('Wrong input to ModifyAttendee - expecting a modifier tree', self)

    def trans_simple(self, top):
        n = self
        inp = self.input_view(posname(1))
        nd, nm = inp, posname(1)
        prm = 'attendee' if 'attendee' in self.tags else 'attconstraint'
        if nd and inp.is_modifier_tree('Attendee'):
            # we want to connect the modifier, not its result. (new_beg's view mode...)
            # TODO: in case of 'event' - need different expression
            self.wrap_input(nm, 'revise(hasParam=%s, new=' % prm, suf=', newMode=modif)', do_eval=False)
            if self.outputs:
                nn, par = self.outputs[-1]
                self.cut_node(posname(1), nn, par)
                n = par  # this will remove self from transformed sexp
        return n, None


class FindAttendees(Node):
    """
    Finds an event, given a constraint made of modifiers.
    """

    # TODO: first do refer() (without fallback, only complete events?)
    def __init__(self):
        super().__init__(Event)
        self.signature.add_sig(posname(1), Node, True, alias='attconstraint')
        self.signature.add_sig('tmp', Node, ptags=['omit_dup'])  # tmp is used for debugging - to draw the pruned tree
        self.signature.set_multi_res(True)  # may return multiple objects as result

    def exec(self, all_nodes=None, goals=None):
        constr = self.input_view('attconstraint')

        if constr:
            cp, _ = constr.duplicate_res_tree(keep_turn=True)

            # 1. convert modifiers
            cp.convert_modifiers(self)  # maybe convert BEFORE copy? <<

            # 2. prune contradictions
            cp.prune_modifiers()
        else:
            cp, _ = self.call_construct('Attendee?()', self.context)

        if environment_definitions.show_dbg_constr:
            d, e = self.call_construct('Dummy()', self.context)
            d.connect_in_out('tmp', self)
            self.inputs['tmp'].set_result(cp)

        # cp, _ = Node.call_construct('AND(%s, Event?(attendees=ANY(Attendee(recipient=Recipient?(id=%d)))))' %
        #                             (id_sexp(cp), storage.get_current_recipient_id()), register=False)

        if environment_definitions.show_SQL:
            msg = str(cp.generate_sql().compile(compile_kwargs={"literal_binds": True}))
            logger.debug('\nSQL statement:\n %s\n', msg)
            msg = msg.replace("<", "&lt;")
            msg = msg.replace(">", "&gt;")
            self.context.add_message(self, MSG_SQL + msg)

        # we want ALL objects from the external DB which match the constraint. not just those in the graph.
        #      and we want to get a fresh copy of these - the DB might have been changed "externally"
        results = Attendee.fallback_search(cp, all_nodes, goals, do_eval=True, params=['ignore_friendship'])

        if not results:
            raise AttendeeNotFoundException(self)

        r = node_fact.make_agg(results)
        r.call_eval(add_goal=False)  # pedantic
        self.set_result(r)

    # base function - yielding message from top node
    def yield_msg(self, params=None):
        m = self.res.describe_set(params=params)
        return Message('This is what I could find: NL ' + m.text, objects=m.objects)


# ####################################################################################################
# ############################################## event  ##############################################


def fields_to_msg(prms, d_context):
    """
    Auxiliary function used by `make_dbg_update_tree`.
    """
    if not prms:
        return None
    ps = []
    for p in prms:
        s = p.split('=')
        k, v = s[0], ':'.join(s[1:])
        t = v.split('$#')
        n = t[1] if len(t) == 2 else ''
        if n:
            if ')' in n:
                n = re.sub('\)', '', n)
            n = d_context.get_node(int(n))
            if n:
                m = n.describe().text
                if m:
                    ps.append('%s: %s' % (k, m))
    s = DEBUG_MSG + ' NL '.join(ps)  # mark this to be displayed with message formatting
    d, _ = Node.call_construct('Str("%s")' % s, d_context)
    return d


def make_dbg_update_tree(root):
    """
    Makes temp tree for pretty printing of pruned constraint tree WITH original event (in UpdateEvent).
    """
    tt = root.get_tree_turns()
    org = [t for t in tt if t.created_turn == -1 and t.typename() == 'Event']
    prms = []
    for t in org:
        prms.extend(t.event_ctree_str(sep_date=False, return_prm=True, open_slot=True))
    cc = [fields_to_msg(prms, root.context)] if prms else []
    cc += [t for t in tt if t.created_turn != -1]
    return node_fact.make_agg(cc, agg='AND')


class EventToTimeInput(Node):
    """
    Converts an Event to an expression of time.
    """

    def __init__(self):
        super().__init__(Node)
        self.signature.add_sig(posname(1), Node)

    def valid_input(self):
        n = self.input_view(posname(1))
        tp = n.outypename()
        if self.constraint_level > 0 or tp not in ['Event', 'LT', 'LE', 'GT', 'GE']:
            raise InvalidTypeException('Error - EventToTimeInput wrong input : %s / %s' % (n, n.show()), self)
        obj = n.get_op_object(typs='Event').res
        if not obj:
            raise InvalidValueException('Error - EventToTimeInput wrong input : %s / %s' % (n, n.show()), self)
        st, en = obj.get_ext_view('slot.start'), obj.get_ext_view('slot.end')
        if not st:
            raise InvalidValueException(f"Wrong input for start: {st}", self)
        if not en:
            raise InvalidValueException(f"Wrong input for end: {en}", self)

    def exec(self, all_nodes=None, goals=None):
        n = self.input_view(posname(1))
        tp = n.typename()
        obj = n.get_op_object(typs='Event').res
        st, en = obj.get_ext_view('slot.start'), obj.get_ext_view('slot.end')
        s = ""
        if tp == 'Event':
            s = 'DateTimeRange(start=%s, end=%s)' % (id_sexp(st), id_sexp(en))
        elif tp in ['LT', 'LE']:
            s = tp + '(%s)' % id_sexp(st)
        elif tp in ['GT', 'GE']:
            s = tp + '(%s)' % id_sexp(en)

        g, e = self.call_construct_eval(s, self.context)
        self.set_result(g)


class DateTimeAndConstraintBetweenEvents(Node):
    def __init__(self):
        super().__init__(Node)
        self.signature.add_sig('event1', Node)
        self.signature.add_sig('event2', Node)

    def valid_input(self):
        ev1, ev2 = self.get_input_views(['event1', 'event2'])
        if not ev1:
            raise MissingValueException('event1', self)
        if not ev2:
            raise MissingValueException('event2', self)
        st, en = ev1.get_ext_view('slot.end'), ev2.get_ext_view('slot.start')
        if not st:
            raise InvalidValueException(f"Wrong input for event1 end: {st}", self)
        if not en:
            raise InvalidValueException(f"Wrong input for event2 start: {en}", self)

    def exec(self, all_nodes=None, goals=None):
        ev1, ev2 = self.get_input_views(['event1', 'event2'])
        st, en = ev1.get_ext_view('slot.end'), ev2.get_ext_view('slot.start')
        s = 'DateTimeRange(start=%s, end=%s)' % (id_sexp(st), id_sexp(en))
        g, e = self.call_construct_eval(s, self.context)
        self.set_result(g)


# this applies to the 'constraint' parameter of create/update - not to the 'event' parameter
# we could allow an additional parameter - 'event' (possibly have both or either one) - and wrap the request
# depending on supplied parameters
# but revising both would need to create TWO separate calls for revise, wrapped by multi()...
# e.g.: "change the event at 8 to start at 10", then: "I meant the event at 9, should start at 11" ->
#       ModifyEventRequest(event=starts_at(9), starts_at(11))
# for now: allowing only one. By default, it's the constraint param. To modify the event param - add a tag
#          ^event  - e.g. ModifyEventRequest(event=starts_at(9),^event). (shorter than 'mode=event'. experimenting. )
# we could limit the set of matching nodes (to avoid revise selecting the wrong node to modify) in a couple of ways:
# - demand that the matching nodes' types are in a given set of typenames
#   - e.g. use revise(oldTypes=SET(find,create,update,delete))
# - add a specific (type) tag to the target types of nodes
#   - e.g. self.add_type_tags('modifyEvent')  in that type's __init__, and then do revise(hasTag=modifyEvent)
class ModifyEventRequest(Node):
    """
    Convenience function for revising an event constraint.
    """

    # gets translated to a revise call
    def __init__(self):
        super().__init__(Event)
        self.signature.add_sig(posname(1), Node, True)

    def valid_input(self):
        inp = self.input_view(posname(1))
        if inp and not inp.is_constraint_tree('Event'):  # use is_constraint_tree here - after eval
            raise InvalidTypeException('Wrong input to ModifyEvent - expecting a modifier tree', self)

    def trans_simple(self, top):
        n = self
        inp = self.input_view(posname(1))
        nd, nm = inp, posname(1)
        prm = 'event' if 'event' in self.tags else 'constraint'
        if nd and (inp.is_modifier_tree('Event') or inp.is_constraint_tree('Event')):
            # we want to connect the modifier, not its result. (new_beg's view mode...)
            # TODO: in case of 'event' - need different expression
            self.wrap_input(nm, 'revise(hasParam=%s, new=' % prm, suf=', newMode=modif)', do_eval=False)
            if self.outputs:
                nn, par = self.outputs[-1]
                self.cut_node(posname(1), nn, par)
                n = par  # this will remove self from transformed sexp
        return n, None


# ####################################################################################################
# ######################################## select suggestion  ########################################

# this is not quite a general function - it has Event specific details regarding how the suggestions look like,
# and which part of the suggestion needs to match the filter
# in the original SMCalFlow annotation, there is such a function, but not clear exactly why not just use
# ModifyEventRequest instead. any use case where different?
class SelectEventSuggestion(Node):
    """
    Selects an agent suggestion and execute it.
    """

    # if no index is given, take the first one
    def __init__(self):
        super().__init__()
        self.signature.add_sig(posname(1), Node)  # a constraint (filter) to select an event suggestion

    def exec(self, all_nodes=None, goals=None):
        d_context = self.context
        sugg = d_context.prev_sugg_act
        filt = self.input_view(posname(1))
        if sugg and len(sugg) > 1:
            # go over suggestions, construct, filter by constraint, and if there is a match,
            # take the first one which matches
            for s in sugg[1:]:
                s = '' if SUGG_LABEL in s else s[2:] if s.startswith(SUGG_IMPL_AGR) else \
                    s.split(SUGG_MSG)[0] if SUGG_MSG in s else s
                if s:
                    n = s.split('ModifyEventRequest(')[1][:-1]
                    # the command from the suggestions did not pass through trans_simple - do it here (if dialog_simp)
                    try:
                        g, e = self.call_construct_eval(n, d_context, do_trans_simp=True)
                        if filt.match(g):
                            # the command from the suggestions did not pass through trans_simple -
                            #   do it here (if dialog_simp)
                            g, e = self.call_construct_eval(s, d_context, do_trans_simp=True)
                            self.set_result(g)
                            if e:
                                re_raise_exc(e)  # pass on exception
                    except:
                        pass  # no match - do nothing
        else:
            raise WrongSuggestionSelectionException(self)


# ####################################################################################################
# ############################################### find ###############################################

class FindEvents(Node):
    """
    Finds an event, given a constraint made of modifiers.
    """

    # TODO: first do refer() (without fallback, only complete events?)
    def __init__(self):
        super().__init__(Event)
        self.signature.add_sig(posname(1), Node, True, alias='constraint')
        self.signature.add_sig('tmp', Node, ptags=['omit_dup'])  # tmp is used for debugging - to draw the pruned tree
        self.signature.set_multi_res(True)  # may return multiple objects as result

    def exec(self, all_nodes=None, goals=None):
        constr = self.input_view('constraint')

        if constr:
            cp, _ = constr.duplicate_res_tree(keep_turn=True)

            # 1. convert modifiers
            cp.convert_modifiers(self)  # maybe convert BEFORE copy? <<

            # 2. prune contradictions
            cp.prune_modifiers()
        else:
            cp, _ = self.call_construct('Event?()', self.context)

        if environment_definitions.show_dbg_constr:
            d, e = self.call_construct('Dummy()', self.context)
            d.connect_in_out('tmp', self)
            self.inputs['tmp'].set_result(cp)

        if environment_definitions.event_fallback_force_curr_user:
            cp, _ = Node.call_construct('AND(%s, Event?(attendees=ANY(Attendee(recipient=Recipient?(id=%d)))))' %
                                        (id_sexp(cp), storage.get_current_recipient_id()), self.context, register=False)

        if environment_definitions.show_SQL:
            msg = str(cp.generate_sql().compile(compile_kwargs={"literal_binds": True}))
            logger.debug('\nSQL statement:\n %s\n', msg)
            msg = msg.replace("<", "&lt;")
            msg = msg.replace(">", "&gt;")
            self.context.add_message(self, MSG_SQL + msg)

        # we want ALL event from the external DB which match the constraint. not just those in the graph.
        #      and we want to get a fresh copy of these - the DB might have been changed "externally"
        results = Event.do_fallback_search(cp, all_nodes, goals, do_eval=True)  # , params={"without_curr_user": True})

        if not results:
            if environment_definitions.populating_db:
                if Event.populate(cp):
                    results = Event.do_fallback_search(cp, all_nodes, goals, do_eval=True)
            if not results:
                raise EventNotFoundException(self)

        r = node_fact.make_agg(results)
        r.call_eval(add_goal=False)  # pedantic
        self.set_result(r)

    # base function - yielding message from top node
    def yield_msg(self, params=None):
        m = self.res.describe_set(params=params)
        return Message('This is what I could find: NL ' + m.text, objects=m.objects)

    def allows_exception(self, ee):
        e = to_list(ee)[0]
        if e and isinstance(e, DFException):
            e = e.chain_end()
        msg, node, hint, sg = parse_node_exception(e)
        # The if below, when `True`, means that there was an error on self's inputs,
        # which made a constraint not to be found. In this case, no event can be found.
        if isinstance(e, RecipientNotFoundException):
            ex = EventNotFoundException(self, hint, sg, orig=e)
            if isinstance(e, DFException):
                e.chain = ex
            self.context.add_exception(ex, e)
            ee.append(ex)
            return False, ee
        # The if below, when `True`, means that there was an error on self's constraint.
        # In this case, the search cannot be performed
        if isinstance(e, EventNotFoundException):
            ex = BadEventConstraintException("Failed search for event", self, hint, sg, orig=e)
            if isinstance(e, DFException):
                e.chain = ex
            self.context.add_exception(ex, e)
            ee.append(ex)
            return False, ee
        return False, ee


# ####################################################################################################
# ############################################## create ##############################################

# implementation using modifiers
# constraint is one or more (or NO) modifiers.
# each time we run, we start from scratch (i.e. from an empty event) and build a suggestion from the modifiers.
# subsequent revises will modify self.constraint.
# some missing values will be guessed and selected, and some will need user confirmation/selection.
# once a user makes a selection, that is added as an additional modifier into self.constraint
# the suggestion is kept as a result - not an input - i.e. we do not modify it directly. However, some modifiers may
# need the result as input (e.g. shift_time)
class CreatePreflightEventWrapper(Node):
    """
    Converts an event constraint into an event suggestion (which still needs approval from user).
    """

    def __init__(self):
        super().__init__(Event)
        self.signature.add_sig('constraint', Node)  # event modifier(s)
        self.signature.add_sig('tmp', Node,
                               ptags=['omit_dup'])  # tmp - used for debugging - draw the prunced tree

    def exec(self, all_nodes=None, goals=None):
        constr = self.input_view('constraint')
        if constr:
            constr.convert_modifiers(self)
            cp, _ = constr.duplicate_res_tree(keep_turn=True)

            # # 1. convert modifiers
            # cp.convert_modifiers(self)  # maybe convert BEFORE copy? <<

            # 2. prune contradictions
            cp.prune_modifiers()
        else:
            cp, _ = self.call_construct('Event?()', self.context)

        if environment_definitions.show_dbg_constr:
            d, e = self.call_construct('Dummy()', self.context)
            d.connect_in_out('tmp', self, force=True)
            self.inputs['tmp'].set_result(cp)

        try:
            d = Event.create_suggestion(cp, self)
            self.set_result(d)
            d.event_possible(allow_clash=True)  # verify that the event is possible  - no clashes ...
        except Exception as ex:
            re_raise_exc(ex, node=self)


class CreateCommitEventWrapper(Node):
    """
    Wrapper to committing an event creation.
    """

    # present the suggested event. If confirmation has not been given yet, then ask for it,
    #   else - commit (call creation API)
    # what is the output? - for now - the input event
    def __init__(self):
        super().__init__(Event)
        self.signature.add_sig('sugg', Event, True)  # this is the actual suggested event
        self.signature.add_sig('confirm', Bool)  # 'confirm' will not be duplicated by revise

    def exec(self, all_nodes=None, goals=None):
        ev = self.input_view('sugg')  # we could use constraint.result instead, if no event input -
        # this could allow choosing if we revise suggestion or spec
        clash = False
        try:  # check again no overlap - some time may have passed since the suggested event was checked
            clash = ev.event_possible(allow_clash=True)
        except Exception as ex:
            re_raise_exc(ex)

        msg = ev.describe()
        d, o = msg.text, msg.objects
        if not self.get_dat('confirm'):  # first time we visit
            acts = self.sugg_confirm_acts()
            # add a message to the 'reject' suggestion
            acts[0] = acts[0].split(SUGG_MSG)[0] + SUGG_MSG + 'What would you like to change?'
            mm = 'This suggestion clashes with other events. would you like to continue?' if clash \
                else 'Does this look ok?'
            raise EventConfirmationException(mm + ' - NL %s' % d, self, suggestions=acts, objects=o)
        msg = 'Committing event : %s' % d
        logger.debug(msg)
        self.context.add_message(self, msg)
        att, _ = ev.get_attendee_ids()
        current_recipient_id = storage.get_current_recipient_id()
        if current_recipient_id not in att:
            att.append(current_recipient_id)
        try:
            dbev = storage.add_event(ev.get_dat('subject'), datetime_node_to_datetime(ev.get_ext_view('slot.start')),
                                     datetime_node_to_datetime(ev.get_ext_view('slot.end')), ev.get_dat('location'), att)
        except Exception:
            raise DFException('Database insertion error', self)
        self.set_result(storage.get_event_graph(dbev.identifier, self.context))


class CreateEvent(Node):
    """
    Convenience function for creating an event: spawns two wrappers then gets removed.
    """

    # all this one does is add two wrappers to the actual Event?() input
    def __init__(self):
        super().__init__(Event)
        self.signature.add_sig(posname(1), Node)
        # TODO: further simplify - in case of multiple modifier inputs, instead of needing an explicit AND()
        #   around them, allow multiple positional inputs, then add an AND in trans_simple

    def valid_input(self):
        inp = self.input_view(posname(1))
        if inp and not inp.is_modifier_tree('Event'):
            raise InvalidTypeException('CreateEvent expects event modifier(s) as input', self)
        if not inp:
            raise InvalidTypeException('What should be the name of the event?', self)

    def trans_simple(self, top):
        n = self
        pnm, parent = self.get_parent()
        inp = self.input_view(posname(1))
        if not inp:
            n, _ = self.call_construct('CreateCommitEventWrapper(sugg=CreatePreflightEventWrapper())', self.context)
            if parent:
                parent.replace_input(pnm, n)
                n = parent
        elif inp.is_modifier_tree('Event'):
            self.wrap_input(posname(1), 'CreateCommitEventWrapper(sugg=CreatePreflightEventWrapper(constraint=',
                            do_eval=False)
            if parent:
                self.cut_node(posname(1), pnm, parent)
                n = parent  # this will remove self from transformed sexp

        return n, None


# ####################################################################################################
# ########################################### update event ###########################################

# implementation with modifiers
class UpdatePreflightEventWrapper(Node):
    """
    Given query for an existing event, and an Event constraint describing updates to the event,
    create a modified event suggestion.
    """

    def __init__(self):
        super().__init__(Event)
        self.signature.add_sig('event', Node, True)  # the event to be modified - found in DB
        self.signature.add_sig('constraint', Event)  # the requested updates - modifier tree
        self.signature.add_sig('tmpc', Node,
                               ptags=['omit_dup'])  # tmp - used for debugging - draw the pruned tree

        self.last_tm_sugg = get_system_datetime()

    def trans_simple(self, top):
        inp = self.input_view('event')
        if inp.is_modifier_tree():
            trans_graph(inp, add_yield=False)
            self.wrap_input('event', 'singleton(FindEvents(constraint=', do_eval=False)
        elif inp.typename() == 'FindEvents':
            trans_graph(inp, add_yield=False)
            self.wrap_input('event', 'singleton(', do_eval=False)
        return self, None

    def valid_input(self):
        constr = self.input_view('constraint')
        if not constr:
            raise MissingValueException('constrain', self, message='What changes would you like to make to this event?')

    # the way it works:
    # after the target event is found, it is converted into an event constraint tree, and is input to 'event'
    # the requested updates (modifiers) (per turn) are put into 'constraint', and are converted to an event constraint
    # tree corresponding to this turn.
    # we then move the new turn from 'constraint' to 'event', and prune the constraints (now including both new and old)
    # TODO: make sure the revise doesn't confuse between constraint/event of update, and between constraint of
    #   update/find
    def exec(self, all_nodes=None, goals=None):
        ev = self.input_view('event')  # at this point in the evaluation, a constraint tree representing one event
        constr = self.input_view('constraint')
        if not constr:
            msg = ev.describe()
            d, o = msg.text, msg.objects
            raise InvalidResultException(
                "Please specify the change you would like to make to the following event: %s" % d, self, objects=o)

        s = ev.event_ctree_str()
        evcp, _ = self.call_construct_eval(s, self.context)
        for i in evcp.inputs:
            evcp.input_view(i).created_turn = -1

        cp, _ = constr.duplicate_res_tree(keep_turn=True)
        if cp.typename() == 'AND':
            for i in cp.inputs:
                evcp.add_pos_input(cp.inputs[i])
        else:
            evcp.add_pos_input(cp)
        cp = evcp

        # 1. convert modifiers
        cp.convert_modifiers(self)  # maybe convert BEFORE copy? <<

        # 2. prune contradictions
        cp.prune_modifiers()

        d = None
        if environment_definitions.show_dbg_constr:
            xx = make_dbg_update_tree(cp)
            d, e = self.call_construct('Dummy()', self.context)
            d.connect_in_out('tmpc', self)
            self.inputs['tmpc'].set_result(xx)
        try:
            d = Event.create_suggestion(cp, self, avoid_id=ev.get_dat('id'))
            self.set_result(d)
            d.event_possible(avoid_id=ev.get_dat('id'),
                             allow_clash=True)  # verify that the event is possible  - no clashes ...
        except Exception as ex:
            re_raise_exc(ex, node=self)
        if 'id' in ev.inputs:
            ev.input_view("id").connect_in_out("id", d)


class UpdateCommitEventWrapper(Node):
    """
    Wrapper to committing an event creation.
    """

    def __init__(self):
        super().__init__(Event)
        self.signature.add_sig('sugg', Event, True)
        self.signature.add_sig('confirm', Bool)

    def exec(self, all_nodes=None, goals=None):
        ev = self.input_view('sugg')  # we could use constraint.result instead, if no event input -
        # this could allow choosing if we revise suggestion or spec
        clash = False
        try:  # check again no overlap - some time may have passed since the suggested event was checked
            clash = ev.event_possible(avoid_id=ev.get_dat('id'), allow_clash=True)
        except Exception as ex:
            re_raise_exc(ex)

        msg = ev.describe()
        d, o = msg.text, msg.objects
        if self.get_dat('confirm') != True:
            # TODO: if we keep the original event id, then we could compare to it and highlight what has changed
            # e.g. "meeting with John, at 10 instead of 9"
            acts = self.sugg_confirm_acts()
            acts[0] += SUGG_MSG + 'What would you like to change?'  # instead of/in addition to rerun -
            #    give message and do nothing
            mm = 'This suggestion clashes with other events. would you like to continue?' if clash \
                else 'Does this look ok?'
            raise EventConfirmationException(mm + ' - NL %s' % d, self, suggestions=acts, objects=o)
        msg = 'Committing event : %s' % d
        logger.debug(msg)
        self.context.add_message(self, msg)
        att, _ = ev.get_attendee_ids()
        current_recipient_id = storage.get_current_recipient_id()
        if current_recipient_id not in att:
            att.append(current_recipient_id)
        storage.update_event(ev.get_dat('id'),
                             ev.get_dat('subject'), datetime_node_to_datetime(ev.get_ext_view('slot.start')),
                             datetime_node_to_datetime(ev.get_ext_view('slot.end')), ev.get_dat('location'), att)

        self.set_result(self.input_view('sugg'))


class UpdateEvent(Node):
    """
    Convenience function for updating an event.
    """

    # all this one does is add two wrappers to the actual Event?() input
    def __init__(self):
        super().__init__(Event)
        self.signature.add_sig(posname(1), Event, True, alias='event')
        self.signature.add_sig(posname(2), Event, alias='constraint')

    def trans_simple(self, top):
        n = self
        inp1, inp2 = self.input_view(posname(1)), self.input_view(posname(2))
        trans = False
        if inp1:
            if inp2:
                t2 = inp2.get_op_outypes()  # in case we inp2 is a modifier / set of modifiers
                if inp1.outypename() == 'Event' and t2 == ['Event']:
                    trans = True
                    self.wrap_input_multi(['event', 'constraint'], 'event',
                                          'UpdateCommitEventWrapper(sugg=UpdatePreflightEventWrapper(event=%s,constraint=%s',
                                          no_post_check=True)
            elif inp1.outypename() == 'Event':
                trans = True
                self.wrap_input('event', 'UpdateCommitEventWrapper(sugg=UpdatePreflightEventWrapper(event=',
                                do_eval=False, do_trans_simp=True)

            if trans and self.outputs:
                nm, par = self.outputs[-1]
                self.cut_node('event', nm, par)
                n = par
        return n, None

    def yield_msg(self, params=None):
        return Message('I\'ve put that on your calendar.')


# ####################################################################################################
# ########################################### delete event ###########################################

class DeleteCommitEventWrapper(Node):
    """
    Wrapper to deleting an event.
    """

    def __init__(self):
        super().__init__(Event)
        self.signature.add_sig('sugg', Event, True)  # this is the actual suggested event
        self.signature.add_sig('confirm', Bool)

    def exec(self, all_nodes=None, goals=None):
        ev = self.input_view('sugg')
        msg = ev.describe()
        d, o = msg.text, msg.objects
        if self.get_dat('confirm') != True:
            acts = self.sugg_confirm_acts()
            acts[0] += SUGG_MSG + 'OK - the event will not be deleted'  # instead of/in addition to rerun -
            #    give message and do nothing
            raise EventConfirmationException('Really delete this event? NL %s' % d, self, suggestions=acts, objects=o)
        if not ev or not ev.is_complete():
            raise BadEventDeletionException('Error - trying to delete an invalid event', self)

        att, _ = ev.get_attendee_ids()
        current_recipient_id = storage.get_current_recipient_id()
        if current_recipient_id not in att:
            att.append(current_recipient_id)
        deleted_event = storage.delete_event(
            ev.get_dat('id'), ev.get_dat('subject'), datetime_to_domain_str(ev.get_ext_view('slot.start')),
            datetime_to_domain_str(ev.get_ext_view('slot.end')), ev.get_dat('location'), att)
        if deleted_event is None:
            raise BadEventDeletionException('Error - Event has changed in the database - not deleting', self)

        msg = ev.get_ext_view('slot.start').describe(params=['add_prep'])
        d, o = msg.text, msg.objects
        msg = 'The event "%s" which was supposed to take place %s has been deleted' % (ev.get_dat('subject'), d)
        logger.debug(msg)
        self.context.add_message(self, msg)


class DeleteEvent(Node):
    """
    Convenience function for deleting an event.
    """

    # all this one does is add wrappers to the given event modifiers. Disappears after trans_simple
    def __init__(self):
        super().__init__(Event)
        self.signature.add_sig(posname(1), Node, True)

    def valid_input(self):
        inp = self.inputs[posname(1)]
        if not inp.is_modifier_tree('Event'):
            raise InvalidTypeException('DeleteEvent expects event modifier(s) as input', self)

    def trans_simple(self, top):
        n = self
        inp = self.inputs[posname(1)]
        if inp:
            self.wrap_input(posname(1), 'DeleteCommitEventWrapper(sugg=singleton(FindEvents(constraint=', do_eval=False)
            if self.outputs:
                nm, par = self.outputs[-1]
                self.cut_node(posname(1), nm, par)
                n = par  # this will remove self from transformed sexp
        return n, None


# ####################################################################################################
# ######################################### fence responses  #########################################

class FenceAggregation(Node):

    def yield_msg(self, params=None):
        return Message("Sorry, I can't handle complex aggregation requests.")


class FenceAttendee(Node):

    def yield_msg(self, params=None):
        return Message("Sorry, I can't handle complex attendee requests.")


class FenceComparison(Node):

    def yield_msg(self, params=None):
        return Message("Sorry, I can't handle complex comparison requests.")


class FenceConditional(Node):

    def yield_msg(self, params=None):
        return Message("Sorry, I can't handle complex conditional requests.")


class FenceConferenceRoom(Node):

    def yield_msg(self, params=None):
        return Message("Sorry, I can't handle complex room requests.")


class FenceDateTime(Node):

    def yield_msg(self, params=None):
        return Message("Sorry, I can't handle complex date and time requests.")


class FenceGibberish(Node):

    def yield_msg(self, params=None):
        return Message("I didn't understand, could you rephrase it?")


class FenceMultiAction(Node):

    def yield_msg(self, params=None):
        return Message("Sorry, I can't handle complex multi-action requests.")


class FenceNavigation(Node):

    def yield_msg(self, params=None):
        return Message("Sorry, I can't handle navigation requests.")


class FenceOther(Node):

    def yield_msg(self, params=None):
        return Message("Sorry, I can't handle this request.")


class FencePeopleQa(Node):

    def yield_msg(self, params=None):
        return Message("Sorry, I can't handle questions about people.")


class FencePlaces(Node):

    def yield_msg(self, params=None):
        return Message("Sorry, I can't handle complex place requests.")


class FenceRecurring(Node):

    def yield_msg(self, params=None):
        return Message("Sorry, I can't handle recurring event requests.")


class FenceReminder(Node):

    def yield_msg(self, params=None):
        return Message("Sorry, I can't handle reminder requests.")


class FenceScope(Node):

    def yield_msg(self, params=None):
        return Message("Sorry, I can't handle this type of request.")


class FenceSpecify(Node):

    def yield_msg(self, params=None):
        return Message("Could you be more specific?")


class FenceSwitchTabs(Node):

    def yield_msg(self, params=None):
        return Message("Sorry, I can't handle this type of request.")


class FenceTeams(Node):

    def yield_msg(self, params=None):
        return Message("Sorry, I can't handle this type of request.")


class FenceTriviaQa(Node):

    def yield_msg(self, params=None):
        return Message("Sorry, I can't answer that.")


class FenceWeather(Node):

    def yield_msg(self, params=None):
        return Message("Sorry, I don't have this information.")


# ####################################################################################################
# ####################################### pleasantry responses #######################################

class GenericPleasantry(Node):

    def yield_msg(self, params=None):
        return Message("I can help you with your calender or answer questions about the weather.")


class PleasantryAnythingElseCombined(Node):

    def yield_msg(self, params=None):
        return Message("Is there something else I can do for you?")


class PleasantryCalendar(Node):

    def yield_msg(self, params=None):
        return Message("I can help you with your calendar")


class WeatherPleasantry(Node):

    def yield_msg(self, params=None):
        return Message("I can answer questions about the weather.")
