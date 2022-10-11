"""
Collect Node type related information here and store in a format which can be passed to a function which does not
have to directly know anything about the node types.
"""
from opendf.graph.nodes.node import Node
from opendf.utils.utils import get_subclasses


def fill_type_info(node_fact):
    all_nodes = list(get_subclasses(Node))  # add recursively inherited nodes
    node_types = {t.__name__: t for t in all_nodes}
    node_types['Any'] = Node  # 'Any' is a synonym for 'Node'
    node_types['Node'] = Node
    node_fact.node_types = node_types  # fill node_fact BEFORE making sample nodes

    # sample nodes: dictionary name -> instance of a node of that type
    sample_nodes = {t.__name__: t() for t in all_nodes}
    sample_nodes['Any'] = Node()
    sample_nodes['Node'] = Node()
    node_fact.sample_nodes = sample_nodes

    node_fact.set_leaf_types()
    node_fact.init_lists()
