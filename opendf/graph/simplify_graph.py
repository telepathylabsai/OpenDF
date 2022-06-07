"""
Functions to translate a simplified graph into a fully expanded computation.
"""
import logging

from opendf.graph.nodes.node import Node
from opendf.graph.node_factory import NodeFactory
from opendf.utils.utils import to_list, id_sexp, is_assign_name
from opendf.defs import is_pos

# we translate by traversing the graph (bottom up)
# There are some important differences with eval:
#  - when translating, the input is an isolated graph - not connected to any other graph;
#  - the graph is a strictly a tree (but later we may allow node name assignment and reuse);
#  - we are not EXECUTING any node (hence creating results based on global graph context or external DB)
#       we are just adding computational steps (without executing them!);
#  - the added computational steps may depend on context (i.e. we look UP the graph and possibly behave differently,
#       depending on the node's ancestors);
#  - the translation modifies only INPUTS - it does not create outputs.

logger = logging.getLogger(__name__)

# init type info
node_fact = NodeFactory.get_instance()


def simplify_graph(nd, d_context, mode=None):
    """
    Recursive, top down, in place transformation of a simple graph.
    """
    logger.debug('==Recursively simplify graph %s', nd)
    nd0 = nd
    # add dummy root (which will not be deleted), so we are sure we always have a parent above each simplified node
    d, e = Node.call_construct('DummyRoot(%s)' % id_sexp(nd), d_context, no_exit=True)
    m, e = recursive_simplify(d, d_context, d, None, mode)
    mm = d.inputs['pos1']
    if nd != mm:
        if d_context.goals[-1] == nd:
            d_context.goals[-1] = mm
        if nd.typename() == 'let' and mm.typename() == 'do':  # one more pass
            mm, e = simplify_graph(mm, d_context, mode=mode)
        nd = mm

    mm = simplify_unused_assign(nd)
    if nd != mm and (d_context.goals[-1] == nd or d_context.goals[-1] == nd0):
        d_context.goals[-1] = mm
    nd = mm

    return nd, e


# transform a node, and then transform its children (top to bottom)
# for now - translation stops when an error occurs - maybe we should continue anyway (and report just one error)?
# important - if the trans_simple replaces the node it is called on,
#             it must return the new node from which to continue traversing the graph
def recursive_simplify(n, d_context, top, e, mode, avoid=None):
    avoid = [] if not avoid else to_list(avoid)
    if not e:
        m = None
        while m != n and (n not in avoid and m not in avoid):
            n = m if m else n
            m, e, mode = n.simplify(top, mode)
        if m and m not in avoid:
            for i in list(m.inputs.keys()):
                if not e and i in m.inputs:  # m's inputs may change during simplification - check if still exists
                    mm, e = recursive_simplify(m.input_view(i), d_context, top, e, mode,
                                               avoid=avoid)  # use input_view - then can be called dynamically
            return m, e
    return n, e


# call recursive_simplify, but block it from spreading above entry node
def recursive_simplify_limit(n, d_context, top, e, mode):
    d, ee = n.call_construct('DummyRoot(%s)' % id_sexp(n), d_context)
    m, e = recursive_simplify(d, d_context, top, e, mode)
    if m.typename() == 'DummyRoot':
        m = m.input_view('pos1')
    d.disconnect_input('pos1')
    return m, e


def pre_simplify_graph(nd, d_context):
    """
    Recursive, BOTTOM-UP pre-simplifying step.
    """
    logger.debug('==Recursively Pre-simplify graph %s', nd)
    e = recursive_pre_simplify(nd, d_context, nd, None, None)
    return nd, e


# transform a node, and then transform its children (top to bottom)
# for now - translation stops when an error occurs - maybe we should continue anyway (and report just one error)?
# important - if the trans_simple replaces the node it is called on,
#             it must return the new node from which to continue traversing the graph
def recursive_pre_simplify(n, d_context, top, e, mode):
    if not e:
        for i in list(n.inputs.keys()):
            if not e:
                e = recursive_pre_simplify(n.input_view(i), d_context, top, e,
                                           mode)  # use input_view - then can be called dynamically
    if not e:
        m = None
        while m != n:
            n = m if m else n
            m, e, mode = n.pre_simplify(top, mode)
    return e


# nd is a 'do' node with several 'Let' expressions followed by the main expression
def aux_unused(nd):
    nms = list(nd.inputs.keys())
    expnm = nms[-1]  # name of input for main expression (the expression after 'Let's)
    # vars = {i: nd.inputs[i].inputs['pos1'].dat for i in nd.inputs if 'pos1' in nd.inputs[i].inputs}  # e.g. pos1 -> x0
    # dict: input name (of the 'do') -> variable name    e.g. 'pos1' -> 'x0'
    vars = {i: nd.inputs[i].inputs['pos1'].dat for i in nd.inputs if nd.inputs[i].typename() == 'Let'}
    # inverse dict: var name to input name  (of 'do')    e.g. 'x0' -> 'pos1'
    ivars = {vars[i]: i for i in vars if nd.inputs[i].typename() == 'Let'}
    # input name -> assign names (x?'s) used by that input  (including main expression)  e.g.  'pos2' : ['X0']
    used_vars = {i: list(set([j.typename() for j in nd.inputs[i].topological_order() if is_assign_name(j.typename())]))
                 for i in nd.inputs}
    return expnm, vars, ivars, used_vars


# simplify expressions which start with one or more assignment (Let) expressions
def simplify_unused_assign(nd):
    if nd.typename() == 'do':
        if any([is_pos(i) and nd.inputs[i].typename() == 'Let' for i in nd.inputs]):
            expnm, vars, ivars, used_vars = aux_unused(nd)
            used = used_vars[expnm]
            # now - search and add nested variable uses
            done = False
            while not done:
                done = True
                for i in used:
                    for j in used_vars[ivars[i]]:
                        if j not in used:
                            used.append(j)
                            done = False
            for i in ivars:
                if i and i not in used:
                    nd.disconnect_input(ivars[i])

            # any assignment which is used only once should be moved to "non assignment"
            # for now - do it only for the assignments which appear in the main clause
            expnm, vars, ivars, used_vars = aux_unused(nd)
            nds = sorted(used_vars[expnm])
            rms = []
            for i in nds:
                if nds.count(i) == 1 and not any([i in used_vars[j] for j in used_vars if j != expnm]):
                    logger.info('remove %s', i)
                    rms.append(i)
            if rms:
                all_nodes = nd.topological_order()
                for r in rms:
                    n = nd.inputs[ivars[r]]
                    c = [i for i in nd.inputs[expnm].topological_order() if i.typename() == r]
                    if c and len(c) == 1 and len([o for (m, o) in c[0].outputs if o in all_nodes]) == 1:
                        c[0].replace_self(n.inputs['pos2'])

            expnm, vars, ivars, used_vars = aux_unused(nd)
            if not used_vars[expnm]:  # no more assignments used
                return nd.inputs[expnm]

    return nd


def clean_operators(nd):
    if nd.typename() in ['AND', 'OR']:
        n = len(nd.inputs)
        if n == 1:
            i = list(nd.inputs.keys())[0]
            d = nd.input_view(i)
            nd.replace_self(d)
            clean_operators(d)
            return
    for i in list(nd.inputs.keys()):
        if i in nd.inputs:
            clean_operators(nd.inputs[i])
