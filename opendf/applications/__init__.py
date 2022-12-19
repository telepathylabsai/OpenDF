"""
Package containing logic concerning different applications on top of the dataflow graph.
"""
import abc

from opendf.applications.multiwoz_2_2.domain import fill_multiwoz_db, MultiWOZContext
from opendf.applications.multiwoz_2_2.multiwoz_db import fill_multiwoz_sql_db, MultiWozSqlDB
from opendf.applications.fill_type_info import fill_type_info
from opendf.defs import use_database
from opendf.graph.dialog_context import DialogContext
from opendf.graph.node_factory import NodeFactory


class EnvironmentClass(abc.ABC):

    @abc.abstractmethod
    def get_new_context(self) -> DialogContext:
        pass

    @abc.abstractmethod
    def __enter__(self):
        pass

    @abc.abstractmethod
    def __exit__(self):
        pass


class SMCalFlowEnvironment(EnvironmentClass):
    DEFAULT_NODES = [
        "opendf.applications.smcalflow.nodes.functions",
        "opendf.applications.sandbox.sandbox"
    ]
    SIMPLIFICATION_NODES = ["opendf.applications.simplification.nodes.smcalflow_nodes"]

    def get_new_context(self):
        return DialogContext()

    # d_context is only used for graph_db
    def __init__(self, d_context=None, simplification=False, additional_paths=()):
        super(SMCalFlowEnvironment, self).__init__()
        self.d_context = d_context
        self.simplification = simplification
        self.stub_data_file = "opendf/applications/smcalflow/data_stub.json"
        self.additional_paths = list(additional_paths)

    def load_node_factory(self):
        # init type info
        node_fact = NodeFactory.get_instance()
        nodes = self.SIMPLIFICATION_NODES if self.simplification else self.DEFAULT_NODES
        nodes = list(nodes) + self.additional_paths
        fill_type_info(node_fact, node_paths=nodes)

    def __enter__(self):
        from opendf.applications.smcalflow.database import populate_stub_database, Database
        from opendf.applications.smcalflow.domain import fill_graph_db
        self.load_node_factory()
        if use_database:
            populate_stub_database(self.stub_data_file)
        else:
            fill_graph_db(self.d_context)

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        from opendf.applications.smcalflow.database import Database
        if use_database:
            database = Database.get_instance()
            if database:
                database.clear_database()


class MultiWOZEnvironment(EnvironmentClass):
    NODES = ["opendf.applications.multiwoz.simplication.multiwoz_nodes"]

    def get_new_context(self):
        return DialogContext()

    def __init__(self, d_context=None, simplification=False):
        super(MultiWOZEnvironment, self).__init__()
        self.d_context = d_context
        self.simplification = simplification

    def load_node_factory(self):
        # init type info
        node_fact = NodeFactory.get_instance()
        fill_type_info(node_fact, node_paths=self.NODES)

    def __enter__(self):
        self.load_node_factory()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


class MultiWOZEnvironment_2_2(EnvironmentClass):
    NODES = ["opendf.applications.multiwoz_2_2.nodes.multiwoz",
             "opendf.applications.multiwoz_2_2.nodes.hotel",
             "opendf.applications.multiwoz_2_2.nodes.taxi",
             "opendf.applications.multiwoz_2_2.nodes.restaurant",
             "opendf.applications.multiwoz_2_2.nodes.attraction",
             "opendf.applications.multiwoz_2_2.nodes.train",
             "opendf.applications.multiwoz_2_2.nodes.police",
             "opendf.applications.multiwoz_2_2.nodes.hospital",
             ]

    def get_new_context(self):
        return MultiWOZContext()

    def __init__(self, d_context=None, data_path=None, domains=None, clean_database=False):
        super(MultiWOZEnvironment_2_2, self).__init__()
        self.d_context = d_context
        self.data_path = data_path
        self.domains = None
        self.clean_database = clean_database

    def load_node_factory(self):
        # init type info
        node_fact = NodeFactory.get_instance()
        fill_type_info(node_fact, node_paths=self.NODES)

    def load_data(self):
        if use_database:
            fill_multiwoz_sql_db(self.data_path, self.d_context, domains=self.domains)
        else:
            fill_multiwoz_db(self.data_path, self.d_context, domains=self.domains)

    def __enter__(self):
        self.load_node_factory()
        self.load_data()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if use_database and self.clean_database:
            database = MultiWozSqlDB.get_instance()
            database.clear_database()
