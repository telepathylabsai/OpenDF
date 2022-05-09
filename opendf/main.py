"""
The main entry point to run the dataflow graphs.
"""
import argparse
import time

from opendf.applications.smcalflow.database import Database, populate_stub_database
from opendf.applications.smcalflow.domain import fill_graph_db

from opendf.examples.main_examples import dialogs
from opendf.graph.constr_graph import construct_graph, check_constr_graph
from opendf.graph.eval import evaluate_graph, check_dangling_nodes
from opendf.graph.draw_graph import draw_all_graphs
from opendf.applications.smcalflow.fill_type_info import fill_type_info
from opendf.graph.node_factory import NodeFactory
from opendf.defs import *
from opendf.graph.dialog_context import DialogContext
from opendf.utils.arg_utils import add_environment_option
from opendf.exceptions import parse_node_exception
from opendf.graph.transform_graph import trans_graph
from opendf.utils.simplify_exp import indent_sexp

# to run this from the command line (assuming running from the repository's root directory) , use:
# PYTHONPATH=$(pwd) python opendf/main.py

# the main function gets S-exps as input, and executes them one by one.
# input is taken from dialogs in opendf.examples.main_examples

logger = logging.getLogger(__name__)

# init type info
node_fact = NodeFactory.get_instance()
environment_definitions = EnvironmentDefinition.get_instance()
fill_type_info(node_fact)


def create_arguments_parser():
    """
    Creates the argument parser for the file.

    :return: the argument parser
    :rtype: argparse.ArgumentParser
    """
    parser = argparse.ArgumentParser(
        description="The main entry point to run the dataflow graphs. It runs examples from the "
                    "`opendf/examples/main_examples.py` file.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument(
        "--dialog_id", "-d", metavar="dialog_id", type=int, required=False, default=0,
        help="the dialog id to use. "
             "This should be the index of a dialog defined in the `opendf/examples/main_examples.py` file"
    )

    parser.add_argument(
        "--expression", "-e", metavar="exp", type=str, required=False, default=None, nargs="+",
        help="the expression to run. If set, `dialog_id` will be ignored"
    )

    parser.add_argument(
        "--output", "-o", metavar="output", type=str, required=False, default=None,
        help="Serializes the context of the graph to the given filepath"
    )

    parser.add_argument(
        "--log", "-l", metavar="log", type=str, required=False, default="DEBUG",
        choices=LOG_LEVELS.keys(),
        help=f"The level of the logging, possible values are: {list(LOG_LEVELS.keys())}"
    )

    parser = add_environment_option(parser)

    return parser


def get_user_trans(dialog_id, turn):
    if dialog_id < len(dialogs) and turn < len(dialogs[dialog_id]):
        d, cont = dialogs[dialog_id][turn], False
        if d.startswith(CONT_TURN):
            d, cont = d[2:], True
        return d, cont
    return None, False


def print_dialog(dialog_id):
    if dialog_id < len(dialogs):
        for d in dialogs[dialog_id]:
            logger.info(d)


def dialog(dialog_id, d_context, draw_graph=True):
    """
    This main function gets P-exps as input, and executes them one by one.
    The input is taken from `dialogs` in `opendf.examples.main_examples.py`.

    :param dialog_id: the id of the dialog,
    it will take the dialog from the list defined in `opendf.examples.main_examples.py`
    :type dialog_id: int
    :param draw_graph: if `True`, it will draw the resulting graph
    :type draw_graph: bool
    :return: Tuple[Node, Optional[Exception]]
    :rtype: the generated graph and the exception, if exists
    """
    end_of_dialog = False
    d_context.reset_turn_num()
    ex = None
    psexp = None  # prev sexp
    i_utter = 0

    logger.info('dialog #%d', dialog_id)
    print_dialog(dialog_id)
    gl = None
    while not end_of_dialog:
        # 1. get user processed input (sexp format)
        isexp, cont = get_user_trans(dialog_id, i_utter)
        if isexp is None:
            break

        if environment_definitions.clear_exc_each_turn:
            d_context.clear_exceptions()
        if environment_definitions.clear_msg_each_turn:
            d_context.reset_messages()

        # 2. construct new graph - perform SOME syntax checks on input program.
        #    if something went wrong (which means natural language method sent a wrong sexp) -
        #       no goal was added to the dialog (it was discarded) - user can't help resolve this
        #    if no exception, then a goal has been added to the dialog
        psexp = isexp
        igl, ex = construct_graph(isexp, d_context, constr_tag=OUTLINE_SIMP, no_post_check=True)

        gl, ex = trans_graph(igl)  # for drawing without yield

        check_constr_graph(gl)

        # apply implicit accept suggestion if needed. This is when prev turn gave suggestions, and one of them was
        #   marked as implicit-accept (SUGG_IMPL_AGR) (i.e. apply it if the user moves to another topic without accept or reject)
        if d_context.prev_sugg_act:
            j = [s[2:] for s in d_context.prev_sugg_act if s.startswith(SUGG_IMPL_AGR)]
            if j and not isexp.startswith('AcceptSuggestion') and not isexp.startswith('RejectSuggestion'):
                sx, ms = j[0], None
                if SUGG_MSG in sx:
                    s = sx.split(SUGG_MSG)
                    sx, ms = s[0], s[1]
                gl0, ex0 = construct_graph(sx, d_context)
                if ex0 is None:
                    if not gl.contradicting_commands(gl0):
                        evaluate_graph(gl0)
                        if ms:
                            d_context.add_message(gl0, ms)

        # 3. evaluate graph
        if ex is None:
            ex = evaluate_graph(gl)  # send in previous graphs (before curr_graph added)

        # unless a continuation turn, save last exception (agent's last message + hints)
        d_context.set_prev_agent_turn(ex)

        # 4. answer user: generate message to user, and modify graph to reflect given answer
        end_of_dialog = False

        i_utter += 1
        if not cont:
            d_context.inc_turn_num()

        check_dangling_nodes(d_context)  # sanity check - debug only
        if environment_definitions.turn_by_turn and not end_of_dialog:
            if draw_graph:
                draw_all_graphs(d_context, dialog_id)
            input()

    if draw_graph:
        draw_all_graphs(d_context, dialog_id, ex is None, sexp=indent_sexp(psexp))

    if d_context.exceptions:
        msg, nd, _, _ = parse_node_exception(d_context.exceptions[-1])
        nd.explain(msg=msg)

    return gl, ex


def main(dialog_id, draw_graph=True, output_path=None):
    d_context = DialogContext()
    try:
        if use_database:
            populate_stub_database()
        else:
            fill_graph_db(d_context)
        gl, ex = dialog(dialog_id, d_context, draw_graph=draw_graph)

        if output_path:
            # ids = set(sum([g.topological_order() for g in d_context.goals], []))
            import pickle
            with open(output_path, 'wb') as output_file:
                pickle.dump(d_context, output_file)
        return gl, ex
    except Exception as e:
        raise e
    finally:
        if use_database:
            database = Database.get_instance()
            if database:
                database.erase_database()
        logging.shutdown()


if __name__ == "__main__":
    start = time.time()
    try:
        parser = create_arguments_parser()
        arguments = parser.parse_args()
        config_log(level=arguments.log)
        id_arg = arguments.dialog_id
        if arguments.environment:
            environment_definitions.update_values(**arguments.environment)

        if arguments.expression:
            dialogs.append(arguments.expression)
            id_arg = -1

        main(id_arg, output_path=arguments.output)
    except Exception as e:
        raise e
    finally:
        end = time.time()
        logger.info(f"Running time: {end - start:.3f}s")
        logging.shutdown()
