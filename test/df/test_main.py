"""
Tests the examples for the main entry point.
"""
import unittest

from opendf.applications.smcalflow.database import Database, populate_stub_database
from opendf.applications.smcalflow.domain import fill_graph_db
from opendf.applications.smcalflow.fill_type_info import fill_type_info
from opendf.applications.smcalflow.nodes.functions import DeleteCommitEventWrapper, UpdateCommitEventWrapper, \
    FindEvents, \
    WillSnow
from opendf.applications.smcalflow.nodes.modifiers import with_attendee, starts_at
from opendf.applications.smcalflow.nodes.objects import Event
from opendf.defs import use_database, posname, config_log
from opendf.applications.smcalflow.exceptions.df_exception import BadEventConstraintException, \
    NoEventSuggestionException
from opendf.graph.node_factory import NodeFactory
from opendf.graph.nodes.framework_functions import Yield, revise
from opendf.graph.nodes.framework_objects import Bool
from opendf.graph.nodes.framework_operators import GTf
from opendf.graph.nodes.node import Node
from opendf.main import dialog, environment_definitions
from opendf.graph.dialog_context import DialogContext
from opendf.utils.utils import get_subclasses


class TestMain(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        config_log('INFO')
        NodeFactory.__instance = None
        node_factory = NodeFactory.get_instance()
        nodes = list(filter(lambda x: 'opendf.applications.simplification' not in x.__module__, get_subclasses(Node)))
        fill_type_info(node_factory, nodes)
        cls.d_context = DialogContext()
        if use_database:
            populate_stub_database("opendf/applications/smcalflow/data_stub.json")
        else:
            fill_graph_db(cls.d_context)
        environment_definitions.event_fallback_force_curr_user = False

    @classmethod
    def tearDownClass(cls) -> None:
        if use_database:
            database = Database.get_instance()
            if database:
                database.clear_database()

    def test_input_with_id_1(self):
        graph, ex = dialog(1, self.d_context, draw_graph=False)

        # checking value
        value = graph.typename()
        expected = DeleteCommitEventWrapper.__name__
        self.assertEqual(graph.typename(), expected, f"Expected {expected}, found {value}!")

        # checking exception
        self.assertEqual(len(ex), 1, f"Only one exception expected, got {len(ex)}")

        exception_len = len(ex[0].suggestions)
        expected_len = 2
        self.assertGreaterEqual(
            exception_len, expected_len,
            f"Expected an confirmation exception with more than {expected_len} arguments, found {exception_len}")

    def test_input_with_id_2(self):
        graph, ex = dialog(2, self.d_context, draw_graph=False)

        # checking value
        value = graph.typename()
        expected = revise.__name__
        self.assertEqual(graph.typename(), expected, f"Expected {expected}, found {value}!")

        graph = graph.inputs["new"]
        value = graph.typename()
        expected = with_attendee.__name__
        self.assertEqual(value, expected, f"Expected {expected}, found {value}!")

        # checking exception
        self.assertEqual(len(ex), 1, f"Only one exception expected, got {len(ex)}")

        exception_len = len(ex[0].suggestions)
        expected_len = 2
        self.assertGreaterEqual(
            exception_len, expected_len,
            f"Expected an confirmation exception with more than {expected_len} arguments, found {exception_len}")

    def test_input_with_id_3(self):
        graph, ex = dialog(3, self.d_context, draw_graph=False)

        # checking value
        value = graph.typename()
        expected = UpdateCommitEventWrapper.__name__
        self.assertEqual(graph.typename(), expected, f"Expected {expected}, found {value}!")

        # checking exception
        self.assertEqual(len(ex), 1, f"Only one exception expected, got {len(ex)}")

        exception_type = NoEventSuggestionException
        self.assertTrue(isinstance(ex[0], exception_type),
                        f"Expected an exception of type {exception_type.__name__}, found {ex[0].__class__.__name__}")

    def test_input_with_id_4(self):
        graph, ex = dialog(4, self.d_context, draw_graph=False)

        # checking value
        value = graph.typename()
        expected = UpdateCommitEventWrapper.__name__
        self.assertEqual(graph.typename(), expected, f"Expected {expected}, found {value}!")

        # checking exception
        exception_len = len(ex[0].suggestions)
        expected_len = 2
        self.assertGreaterEqual(
            exception_len, expected_len,
            f"Expected an confirmation exception with more than {expected_len} arguments, found {exception_len}")

    def test_input_with_id_5(self):
        root, ex = dialog(5, self.d_context, draw_graph=False)

        # checking value
        graph = root
        value = graph.typename()
        expected = revise.__name__
        self.assertEqual(graph.typename(), expected, f"Expected {expected}, found {value}!")

        graph = graph.inputs["new"]
        value = graph.typename()
        expected = starts_at.__name__
        self.assertEqual(value, expected, f"Expected {expected}, found {value}!")

        # checking exception
        events_len = len(root.res.inputs)
        expected_len = 5
        self.assertEqual(events_len, expected_len, f"Expected {expected_len} arguments, found {events_len}")

    def test_input_with_id_6(self):
        root, ex = dialog(6, self.d_context, draw_graph=False)

        # checking value
        graph = root
        value = graph.typename()
        expected = FindEvents.__name__
        self.assertEqual(graph.typename(), expected, f"Expected {expected}, found {value}!")

        # checking exception
        graph = root.res
        value = graph.typename()
        expected = Event.__name__
        self.assertEqual(value, expected, f"Expected {expected}, found {value}!")

    def test_input_with_id_7(self):
        root, ex = dialog(7, self.d_context, draw_graph=False)

        # checking value
        graph = root
        value = graph.typename()
        expected = WillSnow.__name__
        self.assertEqual(graph.typename(), expected, f"Expected {expected}, found {value}!")

        # checking exception
        graph = root.res
        value = graph.typename()
        expected = Bool.__name__
        self.assertEqual(value, expected, f"Expected {expected}, found {value}!")

    def test_input_with_id_8(self):
        root, ex = dialog(8, self.d_context, draw_graph=False)

        # checking value
        graph = root
        value = graph.typename()
        expected = FindEvents.__name__
        self.assertEqual(graph.typename(), expected, f"Expected {expected}, found {value}!")

        # checking number of events
        value = sum(map(lambda x: isinstance(x, Event), graph.res.inputs.values()))
        expected = 3
        self.assertEqual(value, expected, f"Expected {expected} event, found {value}!")

    def test_input_with_id_9(self):
        root, ex = dialog(9, self.d_context, draw_graph=False)

        # checking value
        graph = root
        value = graph.typename()
        expected = FindEvents.__name__
        self.assertEqual(graph.typename(), expected,
                         f"Expected {expected}, found {value}!")

        # checking number of events
        value = sum(map(lambda x: isinstance(x, Event), graph.res.inputs.values()))
        expected = 5
        self.assertEqual(value, expected, f"Expected {expected} event, found {value}!")

    def test_input_with_id_10(self):
        root, ex = dialog(10, self.d_context, draw_graph=False)

        # checking value
        graph = root
        value = graph.typename()
        expected = GTf.__name__
        self.assertEqual(graph.typename(), expected,
                         f"Expected {expected}, found {value}!")

        graph = root.res
        value = graph.typename()
        expected = Bool.__name__
        self.assertEqual(value, expected, f"Expected {expected}, found {value}!")

        data = graph.dat
        expected = False
        self.assertEqual(data, expected, f"Expected {expected}, found {value}!")

    def test_input_with_id_11(self):
        root, ex = dialog(11, self.d_context, draw_graph=False)

        # checking value
        graph = root
        value = graph.typename()
        expected = GTf.__name__
        self.assertEqual(graph.typename(), expected,
                         f"Expected {expected}, found {value}!")

        expected = 3
        self.assertEqual(len(ex), expected, f"{expected} exception expected, got {len(ex)}")

        expected = BadEventConstraintException
        self.assertTrue(isinstance(ex[-1], expected),
                        f"Expected an exception of type {expected}, found {type(ex[-1])}")
