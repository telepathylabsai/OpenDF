"""
Tests the examples for the simplify entry point.
"""
import unittest
import re

from opendf.applications import SMCalFlowEnvironment
from opendf.applications.simplification.fill_type_info import fill_type_info
from opendf.applications.smcalflow.database import populate_stub_database, Database
from opendf.applications.smcalflow.domain import fill_graph_db
from opendf.defs import config_log, use_database
from opendf.dialog_simplify import environment_definitions, dialog
from opendf.graph.dialog_context import DialogContext
from opendf.graph.node_factory import NodeFactory
from opendf.parser.pexp_parser import parse_p_expressions

SPACES_REGEX = re.compile("\\s+")


class TestSimplify(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        config_log('INFO')
        cls.d_context = DialogContext()
        cls.application_config = SMCalFlowEnvironment()
        node_factory = NodeFactory.get_instance()
        fill_type_info(node_factory)
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
        simp = dialog("", self.application_config, dialog_id=1, draw_graph=False)
        expected_tree = parse_p_expressions(
            "CreateEvent("
            "   AND("
            "       with_attendee(Jerri Skinner), "
            "       starts_at(NextTime(time=NumberAM(9)))"
            "   )"
            ")")
        simp_tree = parse_p_expressions(simp)
        self.assertEqual(expected_tree, simp_tree)

    def test_input_with_id_2(self):
        simp = dialog("", self.application_config, dialog_id=2, draw_graph=False)
        expected_tree = parse_p_expressions(
            ":start(FindEvents("
            "   AND("
            "       with_attendee(Melissa), "
            "       with_attendee(Chad), "
            "       with_attendee(Ryan), "
            "       with_attendee(Jane), "
            "       has_subject(trivia night)"
            "   )"
            "))")
        simp_tree = parse_p_expressions(simp)
        self.assertEqual(expected_tree, simp_tree)

    # def test_input_with_id_3(self):
    #     simp = dialog("", dialog_id=3, draw_graph=False)
    #     expected_tree = parse_p_expressions("...")
    #     simp_tree = parse_p_expressions(simp)
    #     self.assertEqual(expected_tree, simp_tree)

    def test_input_with_id_4(self):
        simp = dialog("", self.application_config, dialog_id=4, draw_graph=False)
        expected_tree = parse_p_expressions(
            "DeleteEvent("
            "   AND("
            "       starts_at(Tomorrow()),"
            "       with_attendee(FindManager(John))"
            "   )"
            ")")
        simp_tree = parse_p_expressions(simp)
        self.assertEqual(expected_tree, simp_tree)
