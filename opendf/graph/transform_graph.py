"""
Functions to translate a simplified graph into a fully expanded computation.
"""

from opendf.graph.nodes.node import *

# we translate by traversing the graph (bottom up)
# There are some important differences with eval:
#  - when translating, the input is an isolated graph - not connected to any other graph;
#  - the graph is a strictly a tree (but later we may allow node name assignment and reuse);
#  - we are not EXECUTING any node (hence creating results based on global graph context or external DB)
#       we are just adding computational steps (without executing them!);
#  - the added computational steps may depend on context (i.e. we look UP the graph and possibly behave differently,
#       depending on the node's ancestors);
#  - the translation modifies only INPUTS - it does not create outputs.


# init type info
from opendf.defs import posname

logger = logging.getLogger(__name__)

node_fact = NodeFactory.get_instance()

NO_YIELD = ['revise', 'refer', 'AcceptSuggestion', 'RejectSuggestion', 'MODE', 'TEE', 'ModifyEventRequest']


def do_transform_graph(nd, add_yield=False):
    """
    Recursive, top down, in place transformation of a simple graph.
    """
    logger.debug('==Recursively Translate simple graph %s', nd)
    if add_yield and nd.typename() not in NO_YIELD and nd.not_operator():
        y = node_fact.create_node_from_type_name(nd.context, 'Yield', True, tags=WRAP_COLOR_TAG)
        nd.connect_in_out(posname(1), y)
    else:
        y = nd
    # e = recursive_transform(nd, y, None)
    # return y, e

    d, e = Node.call_construct('DummyRoot(%s)' % id_sexp(y), nd.context, no_exit=True, no_post_check=True)
    e = recursive_transform(d, d, None)
    mm = d.inputs['pos1']
    return mm, e


# for now - translation stops when an error occurs - maybe we should continue anyway (and report just one error)?
# important - if the trans_simple replaces the node it is called on,
#             it must return the new node from which to continue traversing the graph
def recursive_transform(n, top, e):
    """
    Transforms a node, and then transforms its children (top to bottom).
    """
    if not e:
        m, e = n.transform_graph(top)
        for i in m.inputs:
            if not e:
                e = recursive_transform(m.input_view(i), top, e)  # use input_view - then can be called dynamically
    return e
