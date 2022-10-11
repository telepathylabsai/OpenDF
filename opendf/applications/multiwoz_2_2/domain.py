"""
Storage for MultiWOZ application
"""
import json
import os.path
from typing import Optional, Dict

from opendf.defs import NODE_COLOR_DB, DB_NODE_TAG
from opendf.exceptions.python_exception import SingletonClassException
from opendf.graph.dialog_context import DialogContext
from opendf.graph.node_factory import NodeFactory
from opendf.graph.nodes.node import Node
from opendf.parser.pexp_parser import escape_string

FILE_NAMES = {
    "attraction": "attraction_db.json",
    "hospital": "hospital_db.json",
    "hotel": "hotel_db.json",
    "police": "police_db.json",
    "restaurant": "restaurant_db.json",
    "taxi": "taxi_db.json",
    "train": "train_db.json"
}


def get_frame_for_service(service, frames):
    for frame in frames:
        if frame["service"] == service:
            return frame

    return None


class MultiWOZContext(DialogContext):

    def _add_new_turn(self):
        # TODO: instead of always starting the state from the copy of the last turn, copy the last
        #  frame of the service (even if it is from turns before the last one?) into the current
        #  state, ONLY if the frame for the service is being updated.
        # if self.dialog_state["turns"]:
        #     last_frames = deepcopy(self.dialog_state["turns"][-1]["frames"])
        # else:
        #     last_frames = []
        self.dialog_state["turns"].append({"frames": [], "turn_id": str(self.turn_num * 2)})

    def __init__(self):
        super(MultiWOZContext, self).__init__()
        self.agent_text = None
        self.agent_dialog_acts = {}
        self.agent_turn = {}
        self.dialog_state = {"services": [], "turns": []}
        self._add_new_turn()
        self.completed_tasks = []

    def update_last_turn_frame(self, frame):
        frames = self.dialog_state["turns"][-1]["frames"]
        service_frame: Optional[Dict] = get_frame_for_service(frame["service"], frames)
        if service_frame is None:
            frames.append(frame)
        else:
            if 'state' in frame:
                state, sstate = frame['state'], service_frame['state']
                if 'active_intent' in state:
                    sstate['active_intent'] = state['active_intent']
                if 'slot_values' in state:
                    sstate['slot_values'].update(state['slot_values'])
            else:
                service_frame.update(frame)
        return

    def add_frame_to_last_turn(self, frame):
        self.dialog_state["turns"][-1]["frames"].append(frame)

    def update_services(self, service):
        if service not in self.dialog_state["services"]:
            self.dialog_state["services"].append(service)

    def clear_state(self):
        self.dialog_state["turns"][-1]["frames"] = []
        self.dialog_state["services"] = []

    def inc_turn_num(self):
        super(MultiWOZContext, self).inc_turn_num()
        self._add_new_turn()


class MultiWOZDB:
    __instance = None

    @staticmethod
    def get_instance() -> "MultiWOZDB":
        """
        Static access method.

        :return: the GraphDB
        :rtype: GraphDB
        """
        if MultiWOZDB.__instance is None:
            MultiWOZDB.__instance = MultiWOZDB()
        return MultiWOZDB.__instance

    def __init__(self):
        """
        Virtually private constructor.
        """
        if MultiWOZDB.__instance is not None:
            raise SingletonClassException()
        self.attractions = []
        self.hospitals = []
        self.hotels = []
        self.polices = []
        self.restaurants = []
        self.taxis = []
        self.trains = []

    @property
    def all_elements(self):
        return self.attractions + self.hospitals + self.hotels + \
               self.polices + self.restaurants + self.taxis + self.trains

    def find_hotels_that_match(self, operator):
        if operator is None:
            return list(self.hotels)
        return list(filter(operator.match, self.hotels))

    def find_elements_that_match(self, operator, d_context, match_miss=False):
        if operator is None:
            return self.all_elements
        return list(filter(lambda x: operator.match(x, match_miss=match_miss), self.all_elements))


def fill_multiwoz_db(data_directory, d_context: DialogContext, domains=None):
    node_factory = NodeFactory.get_instance()
    multiwoz_db = MultiWOZDB.get_instance()

    def load_attractions():
        if multiwoz_db.attractions:
            return
        fields = set(node_factory.sample_nodes['Attraction'].signature.keys())
        nodes = []
        with open(os.path.join(data_directory, FILE_NAMES['attraction'])) as input_file:
            dicts = json.load(input_file)
            for item in dicts:
                params = filter(lambda x: x[0] in fields, item.items())
                params = map(lambda x: x if x[1] != "?" else (x[0], 'UNK'), params)
                params = map(lambda x: f"{x[0].replace(' ', '_')}={escape_string(x[1])}", params)
                node_str = f"Attraction({', '.join(params)})"
                g, _ = Node.call_construct_eval(node_str, d_context, constr_tag=NODE_COLOR_DB)
                g.tags[DB_NODE_TAG] = 0
                nodes.append(g)

        multiwoz_db.attractions = nodes

    def load_hospitals():
        if multiwoz_db.hospitals:
            return
        fields = set(node_factory.sample_nodes['Hospital'].signature.keys())
        nodes = []
        with open(os.path.join(data_directory, FILE_NAMES['hospital'])) as input_file:
            dicts = json.load(input_file)
            for item in dicts:
                params = filter(lambda x: x[0] in fields, item.items())
                params = map(lambda x: f"{x[0]}={escape_string(x[1])}", params)
                node_str = f"Hospital({', '.join(params)})"
                g, _ = Node.call_construct_eval(node_str, d_context, constr_tag=NODE_COLOR_DB)
                g.tags[DB_NODE_TAG] = 0
                nodes.append(g)

        multiwoz_db.hospitals = nodes

    def load_hotels():
        if multiwoz_db.hotels:
            return
        fields = set(node_factory.sample_nodes['Hotel'].signature.keys())
        nodes = []
        with open(os.path.join(data_directory, FILE_NAMES['hotel'])) as input_file:
            dicts = json.load(input_file)
            for item in dicts:
                params = filter(lambda x: x[0] in fields, item.items())
                params = map(lambda x: f"{x[0]}={escape_string(x[1])}", params)
                node_str = f"Hotel({', '.join(params)})"
                g, _ = Node.call_construct_eval(node_str, d_context, constr_tag=NODE_COLOR_DB)
                g.tags[DB_NODE_TAG] = 0
                nodes.append(g)

        multiwoz_db.hotels = nodes

    def load_polices():
        if multiwoz_db.polices:
            return
        fields = set(node_factory.sample_nodes['Police'].signature.keys())
        nodes = []
        with open(os.path.join(data_directory, FILE_NAMES['police'])) as input_file:
            dicts = json.load(input_file)
            for item in dicts:
                params = filter(lambda x: x[0] in fields, item.items())
                params = map(lambda x: f"{x[0]}={escape_string(x[1])}", params)
                node_str = f"Police({', '.join(params)})"
                g, _ = Node.call_construct_eval(node_str, d_context, constr_tag=NODE_COLOR_DB)
                g.tags[DB_NODE_TAG] = 0
                nodes.append(g)

        multiwoz_db.polices = nodes

    def load_restaurants():
        if multiwoz_db.restaurants:
            return
        fields = set(node_factory.sample_nodes['Restaurant'].signature.keys())
        nodes = []
        with open(os.path.join(data_directory, FILE_NAMES['restaurant'])) as input_file:
            dicts = json.load(input_file)
            for item in dicts:
                params = filter(lambda x: x[0] in fields, item.items())
                params = map(lambda x: f"{x[0]}={escape_string(x[1])}", params)
                node_str = f"Restaurant({', '.join(params)})"
                g, _ = Node.call_construct_eval(node_str, d_context, constr_tag=NODE_COLOR_DB)
                g.tags[DB_NODE_TAG] = 0
                nodes.append(g)

        multiwoz_db.restaurants = nodes

    def load_taxis():
        if multiwoz_db.taxis:
            return
        nodes = []
        with open(os.path.join(data_directory, FILE_NAMES['taxi'])) as input_file:
            values = json.load(input_file)
            color_numbers = {}
            type_numbers = {}
            for color in values["taxi_colors"]:
                for taxi_type in values["taxi_types"]:
                    color_number = color_numbers.setdefault(color, str(len(color_numbers)))
                    type_number = type_numbers.setdefault(taxi_type, str(len(type_numbers)))
                    phone = f"01223{'0' * (5 - len(color_number) - len(type_number))}{color_number}{type_number}"
                    node_str = f"Taxi(color={color}, type={taxi_type}, phone={phone})"
                    g, _ = Node.call_construct_eval(node_str, d_context, constr_tag=NODE_COLOR_DB)
                    g.tags[DB_NODE_TAG] = 0
                    nodes.append(g)

        multiwoz_db.taxis = nodes

    def load_trains():
        if multiwoz_db.trains:
            return
        fields = set(node_factory.sample_nodes['Train'].signature.keys())
        nodes = []
        with open(os.path.join(data_directory, FILE_NAMES['train'])) as input_file:
            dicts = json.load(input_file)
            for item in dicts:
                params = dict(filter(lambda x: x[0] in fields, item.items()))
                price = params.get('price', "0.0").lower().split()
                params['price'] = price[0]

                params = map(lambda x: f"{x[0]}={escape_string(x[1])}", params.items())
                node_str = f"Train({', '.join(params)})"
                g, _ = Node.call_construct_eval(node_str, d_context, constr_tag=NODE_COLOR_DB)
                g.tags[DB_NODE_TAG] = 0
                nodes.append(g)

        multiwoz_db.trains = nodes

    if domains is None:
        # since train domain takes some time to load, it will only be loaded when
        # explicitly requested.
        domains = set(FILE_NAMES.keys()) - {"train"}

    if "attraction" in domains:
        load_attractions()
    if "hospital" in domains:
        load_hospitals()
    if "hotel" in domains:
        load_hotels()
    if "police" in domains:
        load_polices()
    if "restaurant" in domains:
        load_restaurants()
    if "taxi" in domains:
        load_taxis()
    if "train" in domains:
        load_trains()
