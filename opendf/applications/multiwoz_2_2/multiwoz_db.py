"""
Class to handle a SQL database for MultiWOZ.
"""
import datetime
import json
import os
import time
from typing import Optional, Dict, Tuple

import sqlalchemy
from sqlalchemy import create_engine, MetaData, Table, Column, Integer, String, ForeignKey, DateTime, insert, \
    Boolean, select, func, update, delete, text, and_, or_, not_, cast, Date, Float

from opendf.applications.multiwoz_2_2.domain import FILE_NAMES
from opendf.defs import database_connection, database_log, database_future, EnvironmentDefinition
from opendf.exceptions.python_exception import SingletonClassException
from opendf.graph.dialog_context import DialogContext
from opendf.graph.nodes.node import Node

environment_definition = EnvironmentDefinition.get_instance()


class MultiWozSqlDB:
    __instance = None

    metadata = MetaData()

    ATTRACTION_TABLE = Table(
        "attraction", metadata,
        Column("id", Integer, primary_key=True),
        Column("address", String),
        Column("area", String),
        Column("entrancefee", Float),
        Column("latitude", Float),
        Column("longitude", Float),
        Column("name", String),
        Column("openhours", String),
        Column("phone", String),
        Column("postcode", String),
        Column("pricerange", String),
        Column("type", String),
    )

    HOSPITAL_TABLE = Table(
        "hospital", metadata,
        Column("id", Integer, primary_key=True),
        Column("phone", String),
        Column("department", String),
    )

    HOTEL_TABLE = Table(
        "hotel", metadata,
        Column("id", Integer, primary_key=True),
        Column("address", String),
        Column("area", String),
        Column("internet", String),
        Column("parking", String),
        Column("latitude", Float),
        Column("longitude", Float),
        Column("name", String),
        Column("phone", String),
        Column("postcode", String),
        Column("pricerange", String),
        Column("stars", String),
        Column("takesbookings", String),
        Column("type", String),
    )

    POLICE_TABLE = Table(
        "police", metadata,
        Column("id", Integer, primary_key=True),
        Column("address", String),
        Column("name", String),
        Column("phone", String),
    )

    RESTAURANT_TABLE = Table(
        "restaurant", metadata,
        Column("id", Integer, primary_key=True),
        Column("address", String),
        Column("area", String),
        Column("food", String),
        Column("introduction", String),
        Column("latitude", Float),
        Column("longitude", Float),
        Column("name", String),
        Column("phone", String),
        Column("postcode", String),
        Column("pricerange", String),
        Column("type", String),
    )

    TAXI_TABLE = Table(
        "taxi", metadata,
        Column("id", Integer, primary_key=True),
        Column("color", String),
        Column("type", String),
        Column("phone", String),
    )

    TRAIN_TABLE = Table(
        "train", metadata,
        Column("id", String, primary_key=True),
        Column("arriveby", DateTime),
        Column("day", String),
        Column("departure", String),
        Column("destination", String),
        Column("duration", String),
        Column("leaveat", DateTime),
        Column("price", Float),
        Column("trainid", String),
    )

    TABLE_BY_DOMAIN = {
        "Attraction": ATTRACTION_TABLE,
        "Hospital": HOSPITAL_TABLE,
        "Hotel": HOTEL_TABLE,
        "Police": POLICE_TABLE,
        "Restaurant": RESTAURANT_TABLE,
        "Taxi": TAXI_TABLE,
        "Train": TRAIN_TABLE,
    }

    # Nodes in this set will be matched again after the SQL because their match logic is not fully
    # implemented in the SQL conversion, the SQL should return a superset of the nodes that match the constraint.
    # As more restricted the super set, the better
    CUSTOM_MATCH = {
        "Hotel",
        "Attraction",
        "Police",
        "Hospital",
        'Restaurant',
    }

    @staticmethod
    def get_instance():
        """
        Static access method.

        :return: the database instance
        :rtype: Database or None
        """
        if MultiWozSqlDB.__instance is None:
            MultiWozSqlDB.__instance = MultiWozSqlDB()
        return MultiWozSqlDB.__instance

    def __init__(self, connection_string=None):
        """
        Create the database class.
        """
        if MultiWozSqlDB.__instance is not None:
            raise SingletonClassException()
        if connection_string is None:
            connection_string = database_connection
        MultiWozSqlDB.__instance = self
        self.engine: sqlalchemy.engine.base.Engine = \
            create_engine(connection_string, echo=database_log, future=database_future)
        self._create_database()

        # cache for the node representation of the entities
        # self.cached_graphs: Dict[str, Dict[int, Node]] = {}

    def erase_database(self):
        """
        Erases the database.
        This method only touches the tables created by this class.
        """
        self.metadata.drop_all(self.engine)
        self.metadata.clear()  # clear the tables known by the metadata

    def clear_cache(self):
        # self.cached_graphs: Dict[str, Dict[int, Node]] = {}
        pass

    def clear_database(self):
        """
        Erase all data from the database, but does not delete the scheme.
        This method only touches the tables created by this class.
        """
        with self.engine.connect() as connection:
            transaction = connection.begin()
            for table in reversed(self.metadata.sorted_tables):
                connection.execute(table.delete())
            transaction.commit()
        self.clear_cache()

    def _create_database(self):
        """
        Create the database for the application. During testing, we will create the database whenever the application is
        lunched and destroy it whenever it finishes, this behaviour must be changed on production phase.
        """
        self.metadata.create_all(self.engine)

    def find_elements_that_match(self, operator, d_context, match_miss=False, maximum_number_of_elements=20):
        values = []
        typename = operator.typename()
        custom_match = typename in self.CUSTOM_MATCH
        try:
            if operator is not None:
                selection = operator.generate_sql(match_miss=match_miss)
                # unconstrained searches can return a very large number of objects, limit it to 20 by now
                if maximum_number_of_elements and not custom_match:
                    selection = selection.limit(maximum_number_of_elements)
                if selection is not None:
                    values = self._find_recipient_from_operator_query(operator, selection, d_context)

                filtered_values = []
                if custom_match:
                    for i, value in enumerate(values):
                        if maximum_number_of_elements and i >= maximum_number_of_elements:
                            break
                        if operator.match(value, match_miss=match_miss):
                            filtered_values.append(value)
                    return filtered_values
                else:
                    return values
        except Exception as ex:
            if environment_definition.raise_db_optimization_exception:
                raise ex

        table_name = MultiWozSqlDB.TABLE_BY_DOMAIN.get(typename)
        if table_name is None:
            return None
        selection = select(table_name)
        with self.engine.connect() as connection:
            for i, row in enumerate(connection.execute(selection)):
                # unconstrained searches can return a very large number of objects, limit it to 20 by now
                if maximum_number_of_elements and i >= maximum_number_of_elements:
                    break
                value = operator.graph_from_row(row, d_context)
                if operator is None or operator.match(value, match_miss=match_miss):
                    values.append(value)

        return values

    def _find_recipient_from_operator_query(self, operator, selection, d_context):
        values = []
        with self.engine.connect() as connection:
            for i, row in enumerate(connection.execute(selection)):
                value = operator.graph_from_row(row, d_context)
                values.append(value)

        return values


LOADED_DATA = set()


def fill_multiwoz_sql_db(data_directory, d_context: DialogContext, domains=None):
    def load_attractions(connection):
        if "attraction" in LOADED_DATA:
            return

        with open(os.path.join(data_directory, FILE_NAMES['attraction'])) as input_file:
            dicts = json.load(input_file)
            data = []
            for item in dicts:
                item = dict(map(lambda x: (x[0], x[1] if x[1] != "?" else None), item.items()))
                if item["entrance fee"]:
                    item["entrance fee"] = item["entrance fee"].replace(
                        "pounds", "").replace("pound", "").strip()
                data.append({
                    "id": item["id"],
                    "address": item["address"],
                    "area": item["area"],
                    "entrancefee": item["entrance fee"] if item["entrance fee"] != "free" else 0.0,
                    "latitude": item["location"][0],
                    "longitude": item["location"][1],
                    "name": item["name"],
                    "openhours": item["openhours"],
                    "phone": item["phone"],
                    "postcode": item["postcode"],
                    "pricerange": item["pricerange"],
                    "type": item["type"],
                })

            connection.execute(insert(MultiWozSqlDB.ATTRACTION_TABLE), data)
            connection.commit()

        LOADED_DATA.add("attraction")

    def load_hospitals():
        if "hospital" in LOADED_DATA:
            return
        with open(os.path.join(data_directory, FILE_NAMES['hospital'])) as input_file:
            dicts = json.load(input_file)
            data = []
            for item in dicts:
                item = dict(map(lambda x: (x[0], x[1] if x[1] != "?" else None), item.items()))
                data.append({
                    "id": item["id"],
                    "department": item["department"],
                    "phone": item["phone"],
                })

            connection.execute(insert(MultiWozSqlDB.HOSPITAL_TABLE), data)
            connection.commit()

        LOADED_DATA.add("hospital")

    def load_hotels():
        if "hotel" in LOADED_DATA:
            return
        with open(os.path.join(data_directory, FILE_NAMES['hotel'])) as input_file:
            dicts = json.load(input_file)
            data = []
            for item in dicts:
                item = dict(map(lambda x: (x[0], x[1] if x[1] != "?" else None), item.items()))
                data.append({
                    "id": item["id"],
                    "address": item["address"],
                    "area": item["area"],
                    "internet": item["internet"],
                    "parking": item["parking"],
                    "latitude": item["location"][0],
                    "longitude": item["location"][1],
                    "name": item["name"],
                    "phone": item["phone"],
                    "postcode": item["postcode"],
                    "pricerange": item["pricerange"],
                    "stars": item["stars"],
                    "takesbookings": item.get("takesbookings"),
                    "type": item["type"],
                })

            connection.execute(insert(MultiWozSqlDB.HOTEL_TABLE), data)
            connection.commit()

        LOADED_DATA.add("hotel")

    def load_polices():
        if "police" in LOADED_DATA:
            return
        with open(os.path.join(data_directory, FILE_NAMES['police'])) as input_file:
            dicts = json.load(input_file)
            data = []
            for item in dicts:
                item = dict(map(lambda x: (x[0], x[1] if x[1] != "?" else None), item.items()))
                data.append({
                    "id": item["id"],
                    "name": item["name"],
                    "address": item["address"],
                    "phone": item["phone"],
                    # "postcode": item["postcode"],
                })

            connection.execute(insert(MultiWozSqlDB.POLICE_TABLE), data)
            connection.commit()

        LOADED_DATA.add("police")

    def load_restaurants():
        if "restaurant" in LOADED_DATA:
            return
        with open(os.path.join(data_directory, FILE_NAMES['restaurant'])) as input_file:
            dicts = json.load(input_file)
            data = []
            for item in dicts:
                item = dict(map(lambda x: (x[0], x[1] if x[1] != "?" else None), item.items()))
                data.append({
                    "id": item["id"],
                    "address": item["address"],
                    "area": item["area"],
                    "food": item["food"],
                    "introduction": item.get("introduction"),
                    "latitude": item["location"][0],
                    "longitude": item["location"][1],
                    "name": item["name"],
                    "phone": item.get("phone"),
                    "postcode": item["postcode"],
                    "pricerange": item["pricerange"],
                    "type": item["type"],
                })

            connection.execute(insert(MultiWozSqlDB.RESTAURANT_TABLE), data)
            connection.commit()

        LOADED_DATA.add("restaurant")

    def load_taxis():
        if "taxi" in LOADED_DATA:
            return
        with open(os.path.join(data_directory, FILE_NAMES['taxi'])) as input_file:
            values = json.load(input_file)
            data = []
            color_numbers = {}
            type_numbers = {}
            counter = 0
            for color in values["taxi_colors"]:
                for taxi_type in values["taxi_types"]:
                    color_number = color_numbers.setdefault(color, str(len(color_numbers)))
                    type_number = type_numbers.setdefault(taxi_type, str(len(type_numbers)))
                    phone = f"01223{'0' * (5 - len(color_number) - len(type_number))}{color_number}{type_number}"
                    data.append({
                        "id": counter,
                        "color": color,
                        "type": taxi_type,
                        "phone": phone,
                    })
                    counter += 1

            connection.execute(insert(MultiWozSqlDB.TAXI_TABLE), data)
            connection.commit()

        LOADED_DATA.add("taxi")

    def load_trains(connection):
        if "train" in LOADED_DATA:
            return

        with open(os.path.join(data_directory, FILE_NAMES['train'])) as input_file:
            dicts = json.load(input_file)
            data = []
            counter = 0
            for item in dicts:
                item = dict(map(lambda x: (x[0], x[1] if x[1] != "?" else None), item.items()))
                if item["price"]:
                    item["price"] = item["price"].replace("pounds", "").replace("pound", "").strip()
                    time.time()
                hour, minute = item["arriveBy"].split(":")
                item["arriveBy"] = datetime.datetime.now().replace(
                    hour=int(hour) % 24, minute=int(minute) % 60, second=0, microsecond=0)
                hour, minute = item["leaveAt"].split(":")
                item["leaveAt"] = datetime.datetime.now().replace(
                    hour=int(hour) % 24, minute=int(minute) % 60, second=0, microsecond=0)
                data.append({
                    "id": counter,
                    "arriveby": item["arriveBy"],
                    "leaveat": item["leaveAt"],
                    "day": item["day"],
                    "departure": item["departure"],
                    "destination": item["destination"],
                    "duration": item["duration"],
                    "price": item["price"],
                    "trainid": item["trainID"],
                })
                counter += 1

            connection.execute(insert(MultiWozSqlDB.TRAIN_TABLE), data)
            connection.commit()

        LOADED_DATA.add("train")

    multiwoz_db = MultiWozSqlDB.get_instance()

    if domains is None:
        domains = set(FILE_NAMES.keys())

    with multiwoz_db.engine.connect() as connection:
        if "attraction" in domains:
            load_attractions(connection)
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
            load_trains(connection)
