"""
Evaluates the graph.
"""

import traceback

from opendf.defs import *
from opendf.exceptions import DFException
from opendf.exceptions.python_exception import EvaluationError
from opendf.graph.nodes.node import Node

logger = logging.getLogger(__name__)


# TODO: this function may finally go back into the Graph class
# TODO: handle multiple goals (for request with multi goals)
# TODO: maybe ALWAYS check for pre_eval, run on those, and then run on all?
def evaluate_graph(goal, add_goal=True):
    logger.debug('==Eval %s', goal)
    d_context = goal.context
    e = None
    if goal is None:
        logger.debug('graph has no goals!')
    else:
        goals = d_context.goals if d_context else []
        prev_nodes = Node.collect_nodes(goals)
        if add_goal:
            goal.context.add_goal(goal)  # construction succeeded, so we add the new goal
        # TODO: revise nodes (any others?) should not really be added to the graph (should not be candidates for
        #  search). We add them anyway, just so we can draw the graphs, but in revise nodes exec - we explicitly
        #  exclude them
        o, e = recursive_eval(goal, prev_nodes, goals)
    return e


# recursive eval:
# Evaluation proceeds bottom up.
# As a rule, we assume that when a node is evaluated, all of its children have already been SUCCESSFULLY evaluated.
# This removes the need for each node's exec() logic to test if its inputs have been successfully evaluated.
# From this assumption, it follows that once an exception has been raised:
#   - the exception is stored in the dialog_context (attached to the node which raised it)
#   - evaluation is "blocked" from this node up, but sibling nodes, and theit children, WILL be evaluated.
#     (the first found exception is the one which will be reported to user, later exceptions may be stored or not,
#     depending on config flags).
#   - (in case this was called from the "main") this exception will be reported to the user.
# Note that the inputs of a node are held in an ORDERED dictionary - this way the developer can control the
#      order of evaluation.
#
# Note: the presence of exceptions may affect the behavior of the "salience model" in prioritizing candidate
#       nodes for revise/refer
#
# A node can override the default logic of exception/evaluation - the function node.allows_exception(e) lets the node
# do two things (typically at most one of these per node):
#   1. given the exception, decides if the node should be evaluated of not
#     - In this case, the node has to handle exceptions in its inputs
#   2. given the exception, create a follow-up exception
#     - This will be an exception of a different type, "chained" to the original exception,
#       and attached to the current node
#
# Note: if node.eval_res is set to True, then its result will be evaluated.
#       if an exception is then raised, and node.res_block is True, then it will be treated as if
# 	       the exception was raised by the current node  (otherwise, execution will continue normally)
#
# Returns:
#   - ok: True if this node was evaluated and no exceptions were raised
#   - e:  a LIST of exceptions which occurred under the current node
#         - possibly under result nodes as well
#         - possibly modified list
def recursive_eval(node, prev_nodes, prev_goals):
    d_context = node.context
    logger.debug(node)
    ok = True
    exs = []
    if not node.evaluated:  # TODO: verify not needed!
        keys = list(node.inputs.keys())
        for i in keys:
            if i in node.inputs:
                # we evaluate all children - even if one has exception - promote graph development - their
                #   computations are independent
                if not ok and node.stop_eval_on_exception:
                    break
                o, e = recursive_eval(node.inputs[i], prev_nodes, prev_goals)
                ok = ok and o
                for ee in e:
                    if ee not in exs:
                        exs.append(ee)
    if not ok:  # exception(s) in inputs
        ok, exs = node.allows_exception(exs)  # decide: evaluate node despite exception? / raise follow-up exception?
    if not node.evaluated and ok:
        try:
            node.evaluate(prev_nodes, prev_goals)
        except Exception as ex:
            ok = False
            logger.debug('> > > exception : %s \n      %s', ex, node)
            if not isinstance(ex, DFException):
                logger.warning(traceback.format_exc())
                if d_context and d_context.supress_exceptions:
                    raise EvaluationError('eval error')
                exit(1)
            exs = node.do_add_exception(ex, exs)
            # e = d_context.add_exception(ex)
    if ok and node.result != node and node.eval_res:
        o, e = recursive_eval(node.res, prev_nodes, prev_goals)
        for ee in e:
            if ee not in exs:
                exs.append(ee)
        if node.res_block:  # block further computation if error in result evaluation
            ok = o
    # if node.detach and node.result != node:  #we're not using detach anymore...
    #     # if error in evaluating result of detachable node - treat it as an exception in an input node
    #     o, e = recursive_eval(node.res, prev_nodes, prev_goals, e)
    #     node.detach_node()
    #     ok = ok and o
    # if node.add_goal == VIEW_INT:  # special-feature, not used anymore
    #     d_context.add_goal(node)
    # elif node.add_goal == VIEW_EXT:
    #     d_context.add_goal(node.res)
    return ok, exs


def check_dangling_nodes(d_context):
    """
    Checks that outputs match inputs.
    """
    nodes = Node.collect_nodes(d_context.goals)
    for n in nodes:
        for (nm, nd) in n.outputs:
            if nm not in nd.inputs or nd.inputs[nm] != n:
                logger.debug('>>> dangling output: %s  [%s] --->  %s \n// %s', n, nm, nd, nd.inputs[nm])
        for i in n.inputs:
            if (i, n) not in n.inputs[i].outputs:
                logger.debug('>>> dangling input: %s: %s / %s \n// %s', n, i, n.inputs[i], n.inputs[i].outputs)
            if i not in n.view_mode:
                logger.debug('>>> missing view_mode: [%s] : %s \n', i, n)


# ###################################################################################################
# ###################################################################################################

