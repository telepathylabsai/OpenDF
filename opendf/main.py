"""
The main entry point to run the dataflow graphs.
"""
import argparse
import time
import yaml
import importlib.machinery

from opendf.applications import EnvironmentClass, SMCalFlowEnvironment
from opendf.graph.constr_graph import construct_graph, check_constr_graph
from opendf.graph.eval import evaluate_graph, check_dangling_nodes
from opendf.graph.draw_graph import draw_all_graphs
from opendf.defs import *
from opendf.graph.dialog_context import DialogContext
from opendf.utils.arg_utils import add_environment_option
from opendf.exceptions import parse_node_exception
from opendf.graph.transform_graph import trans_graph
from opendf.utils.simplify_exp import indent_sexp

# to run this from the command line (assuming running from the repository's root directory) , use:
# PYTHONPATH=$(pwd) python opendf/main.py

# the main function gets S-exps as input, and executes them one by one.
# input is taken from dialogs in the examples file, by default `opendf.examples.main_examples`

logger = logging.getLogger(__name__)
environment_definitions = EnvironmentDefinition.get_instance()


def create_arguments_parser():
    """
    Creates the argument parser for the file.

    :return: the argument parser
    :rtype: argparse.ArgumentParser
    """
    parser = argparse.ArgumentParser(
        description="The main entry point to run the dataflow graphs. It runs examples from the "
                    "examples file.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument(
        "--config", "-c", metavar="config", type=str, required=False, default="resources/smcalflow_config.yaml",
        help="the configuration file for the application"
    )

    parser.add_argument(
        "--dialog_id", "-d", metavar="dialog_id", type=int, required=False, default=0,
        help="the dialog id to use. "
             "This should be the index of a dialog defined in the examples file"
    )

    parser.add_argument(
        "--examples_file", "-ef", metavar="examples_file", type=str, required=False,
        default="opendf/examples/main_examples.py",
        help="the examples files to use, `dialog_id` will specify an example in this file"
    )

    parser.add_argument(
        "--expression", "-e", metavar="exp", type=str, required=False, default=None, nargs="+",
        help="the expression to run. If set, `dialog_id` will be ignored"
    )

    parser.add_argument(
        "--additional_nodes", "-n", metavar="additional_nodes", type=str, required=False,
        default=None, nargs="+",
        help="path for python modules containing additional nodes to be imported. "
             "The path should be in python dot notation "
             "(e.g. `opendf.applications.sandbox.sandbox`) "
             "This argument only works when using `SMCalFlowEnvironment` as environment class"
    )

    parser.add_argument(
        "--output", "-o", metavar="output", type=str, required=False, default=None,
        help="Serializes the context of the graph to the given filepath. "
             "If the extension of the file is .bz2, it will be compressed"
    )

    parser.add_argument(
        "--log", "-l", metavar="log", type=str, required=False, default="DEBUG",
        choices=LOG_LEVELS.keys(),
        help=f"The level of the logging, possible values are: {list(LOG_LEVELS.keys())}"
    )

    parser = add_environment_option(parser)

    return parser


def get_user_trans(dialog_id, turn, dialogs):
    if dialog_id < len(dialogs) and turn < len(dialogs[dialog_id]):
        d, cont = dialogs[dialog_id][turn], False
        if d.startswith(CONT_TURN):
            d, cont = d[2:], True
        return d, cont
    return None, False


def print_dialog(dialog_id, dialogs):
    if dialog_id < len(dialogs):
        for d in dialogs[dialog_id]:
            logger.info(d)


def dialog(dialog_id, dialogs, d_context, draw_graph=True, p_expressions=None):
    """
    This main function gets P-exps as input, and executes them one by one.
    The input is taken from `dialogs` in `examples_file`.

    :param dialog_id: the id of the dialog,
    it will take the dialog from the list defined in `examples_file`
    :type dialog_id: int
    :param dialogs: the list of dialogs, as P-expressions
    :type dialogs: List[List[str]]
    :param draw_graph: if `True`, it will draw the resulting graph
    :type draw_graph: bool
    :param p_expressions: a list of P-Expressions to run, if given, it will override `dialog_id`
    :type p_expressions: Optional[List[str]]
    :return: Tuple[Node, Optional[Exception]]
    :rtype: the generated graph and the exception, if exists
    """
    end_of_dialog = False
    d_context.reset_turn_num()
    ex = None
    psexp = None  # prev sexp
    i_utter = 0

    if p_expressions:
        dialogs.append(p_expressions)
        dialog_id = -1

    logger.info('dialog #%d', dialog_id)
    print_dialog(dialog_id, dialogs)
    gl = None
    while not end_of_dialog:
        # 1. get user processed input (sexp format)
        isexp, cont = get_user_trans(dialog_id, i_utter, dialogs)
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

        # apply implicit accept suggestion if needed. This is when prev turn gave suggestions, and one of them was
        #   marked as implicit-accept (SUGG_IMPL_AGR) (i.e. apply it if the user moves to another topic without
        #   accept or reject)
        # do this BEFORE trans_simple - since trans_simple may look at context.goals  (e.g. for side_task)
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

        gl, ex = trans_graph(igl)  # for drawing without yield

        check_constr_graph(gl)

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

        # check_dangling_nodes(d_context)  # sanity check - debug only
        if environment_definitions.turn_by_turn and not end_of_dialog:
            if draw_graph:
                draw_all_graphs(d_context, dialog_id)
            input()

    if draw_graph:
        draw_all_graphs(d_context, dialog_id, not ex, sexp=indent_sexp(psexp))

    if d_context.exceptions:
        msg, nd, _, _ = parse_node_exception(d_context.exceptions[-1])
        nd.explain(msg=msg)

    return gl, ex


def main(dialog_id, dialogs, environment_class: EnvironmentClass,
         draw_graph=True, output_path=None, p_expressions=None):
    try:
        d_context = environment_class.get_new_context()
        environment_class.d_context = d_context
        with environment_class:
            gl, ex = dialog(dialog_id, dialogs, d_context,
                            draw_graph=draw_graph, p_expressions=p_expressions)

            if output_path:
                from os.path import splitext
                import pickle
                _, ext = splitext(output_path)
                if ext == '.bz2':
                    import bz2
                    with bz2.BZ2File(output_path, 'wb') as output_file:
                        pickle.dump(d_context, output_file)
                else:
                    with open(output_path, 'wb') as output_file:
                        pickle.dump(d_context, output_file)
            return gl, ex
    except Exception as e:
        raise e


if __name__ == "__main__":
    start = time.time()
    try:
        parser = create_arguments_parser()
        arguments = parser.parse_args()
        config_log(level=arguments.log)
        id_arg = arguments.dialog_id

        if arguments.environment:
            environment_definitions.update_values(**arguments.environment)

        application_config = yaml.load(open(arguments.config, 'r'), Loader=yaml.UnsafeLoader)
        environment_class = application_config["environment_class"]

        if isinstance(environment_class, SMCalFlowEnvironment) and arguments.additional_nodes:
            environment_class.additional_paths = arguments.additional_nodes

        loader = importlib.machinery.SourceFileLoader("dialogs", arguments.examples_file)
        examples_file = loader.load_module()
        dialogs = examples_file.dialogs

        main(id_arg, dialogs, environment_class,
             output_path=arguments.output, p_expressions=arguments.expression)
    except Exception as e:
        raise e
    finally:
        end = time.time()
        logger.info(f"Running time: {end - start:.3f}s")
        logging.shutdown()
