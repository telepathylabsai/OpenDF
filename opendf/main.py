"""
The main entry point to run the dataflow graphs.
"""
import argparse
import time
from typing import List

import yaml
import importlib.machinery

from opendf.applications import EnvironmentClass, SMCalFlowEnvironment
from opendf.graph.constr_graph import construct_graph, check_constr_graph
from opendf.graph.dialog_context import DialogContext
from opendf.graph.eval import check_dangling_nodes, evaluate_graph
from opendf.graph.draw_graph import draw_all_graphs
from opendf.defs import *
from opendf.utils.arg_utils import add_environment_option
from opendf.exceptions import parse_node_exception
from opendf.graph.transform_graph import do_transform_graph
from opendf.utils.simplify_exp import indent_sexp
from opendf.utils.utils import flatten_list, to_list

# to run this from the command line (assuming running from the repository's root directory) , use:
# PYTHONPATH=$(pwd) python opendf/main.py

# the main function gets S-exps as input, and executes them one by one.
# input is taken from dialogs in the examples file, by default `opendf.examples.main_examples`

logger = logging.getLogger(__name__)
environment_definitions = EnvironmentDefinition.get_instance()


class OpenDFDialogue:

    def __init__(self):
        pass

    @staticmethod
    def split_count_turn(p_exp):
        if p_exp:
            d, cont = p_exp, False
            if d.startswith(CONT_TURN):
                d, cont = d[2:], True
            return d, cont

        return None, False

    def _break_cont_exps(self, g):
        if g.typename() == 'cont_turn':
            return flatten_list([self._break_cont_exps(g.inputs[i]) for i in g.inputs if is_pos(i)])
        else:
            return [g]

    def run_single_turn(self, p_exp, d_context, draw_graph, gl, do_trans=True):
        """
        Runs a single turn of the dialogue.

        :param p_exp: the current P-Expression
        :type p_exp: str
        :param d_context: the dialogue context
        :type d_context: DialogContext
        :param draw_graph: whether to draw the intermediary graph
        :type draw_graph: bool
        :param gl: the executed graph
        :type gl: Node
        :return: Tuple[Node, Optional[Exception], DialogContext, List[str]]
        :rtype: (1) the generated graph; (2) the exception; (3) the dialogue context;
        (4) the answers from the agent, for the current turn
        """
        # 1. get user processed input (sexp format)
        isexp, cont = self.split_count_turn(p_exp)
        if environment_definitions.clear_exc_each_turn:
            d_context.clear_exceptions()
        if environment_definitions.clear_msg_each_turn:
            d_context.reset_messages()

        # 2. construct new graph - perform SOME syntax checks on input program.
        #    if something went wrong (which means natural language method sent a wrong sexp) -
        #       no goal was added to the dialog (it was discarded) - user can't help resolve this
        #    if no exception, then a goal has been added to the dialog
        ogl, ex = construct_graph(isexp, d_context, constr_tag=OUTLINE_SIMP, no_post_check=True)

        mgl = self._break_cont_exps(ogl)
        turn_answers = []
        for ix, igl in enumerate(mgl):
            # apply implicit accept suggestion if needed. This is when prev turn gave suggestions, and one of them was
            #   marked as implicit-accept (SUGG_IMPL_AGR) (i.e. apply it if the user moves to another topic without
            #   accept or reject)
            # do this BEFORE transform_graph - since transform_graph may look at context.goals  (e.g. for side_task)
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
            gl, ex = do_transform_graph(igl) if do_trans else (igl, None)
            #gl, ex = do_transform_graph(igl)  # for drawing without yield
            check_constr_graph(gl)

            # 3. evaluate graph
            if ex is None:
                ex = evaluate_graph(gl)  # send in previous graphs (before curr_graph added)

            if ex:
                answer = to_list(ex)[0].message
            else:
                answer = d_context.goals[-1].yield_msg()
                # if isinstance(answer, tuple):
                #     answer = answer[0]
                answer = answer.text
            if not answer:
                answer = ''
            turn_answers.append(answer)

            # unless a continuation turn, save last exception (agent's last message + hints)
            d_context.set_prev_agent_turn(ex)

        self.turn_pos_processing(d_context)

        if not cont:
            d_context.inc_turn_num()
        check_dangling_nodes(d_context)  # sanity check - debug only
        if environment_definitions.turn_by_turn:
            if draw_graph:
                draw_all_graphs(d_context)
            input()
        return gl, ex, d_context, turn_answers

    def run_dialogue(self, p_expressions: List[str], d_context: DialogContext, draw_graph=True, do_trans=True):
        """
        This main function gets P-exps as input, and executes them one by one.

        :param p_expressions: a list of P-Expressions to run, if given, it will override `dialog_id`
        :type p_expressions: Optional[List[str]]
        :param d_context: the dialogue context
        :type d_context: DialogContext
        :param draw_graph: if `True`, it will draw the resulting graph
        :type draw_graph: bool
        :return: Tuple[Node, Optional[Exception], DialogContext]
        :rtype: the generated graph; the exception, if exists; and the dialogue context
        """
        d_context.reset_turn_num()
        ex = None
        p_exp = None
        gl = None

        for p_exp in p_expressions:
            logger.info(p_exp)

        for p_exp in p_expressions:
            gl, ex, d_context, _ = self.run_single_turn(p_exp, d_context, draw_graph, gl, do_trans=do_trans)

        if draw_graph:
            draw_all_graphs(d_context, not ex, sexp=indent_sexp(p_exp))

        if d_context.exceptions:
            msg, nd, _, _ = parse_node_exception(d_context.exceptions[-1])
            nd.explain(msg=msg)

        return gl, ex, d_context

    def turn_pos_processing(self, context):
        """
        Method called at the end of the turn, before increment the turn index.

        It gives implementation of this class the chance of perform a pos-processing after each
        turn.

        :param context: the currenct context
        :type context: DialogContext
        """
        pass


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


def run_dialogue(dialog_id, dialogs, environment_class: EnvironmentClass,
                 draw_graph=True, output_path=None, p_expressions=None, do_trans=True):
    try:
        d_context = environment_class.get_new_context()
        if not do_trans:
            d_context.no_trans = True
        environment_class.d_context = d_context
        with environment_class:
            df_dialogue = OpenDFDialogue()
            if not p_expressions:
                p_expressions = dialogs[dialog_id]
            gl, ex, ctx = df_dialogue.run_dialogue(p_expressions, d_context, draw_graph=draw_graph, do_trans=do_trans)

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
            return gl, ex, ctx
    except Exception as e:
        raise e


def run_dialogue_from_arguments(arguments, id_arg=None, draw_graph=True, do_trans=True):
    if id_arg is None:
        id_arg = arguments.dialog_id
    if isinstance(id_arg, str):
        id_arg = int(id_arg)

    if arguments.environment:
        environment_definitions.update_values(**arguments.environment)

    application_config = yaml.load(open(arguments.config, 'r'), Loader=yaml.UnsafeLoader)
    environment_class: EnvironmentClass = application_config["environment_class"]

    if isinstance(environment_class, SMCalFlowEnvironment) and arguments.additional_nodes:
        environment_class.additional_paths = arguments.additional_nodes

    if isinstance(environment_class, SMCalFlowEnvironment):
        if 'examples_file' not in arguments:
            arguments.examples_file = "opendf/examples/main_examples.py"
        if 'expression' not in arguments:
            arguments.expression = None
    loader = importlib.machinery.SourceFileLoader("dialogs", arguments.examples_file)
    examples_file = loader.load_module()
    dialogs = examples_file.dialogs

    gl, ex, ctx = run_dialogue(id_arg, dialogs, environment_class, draw_graph=draw_graph,
                               output_path=arguments.output, p_expressions=arguments.expression, do_trans=do_trans)
    return ctx


if __name__ == "__main__":
    start = time.time()
    try:
        parser = create_arguments_parser()
        arguments = parser.parse_args()
        config_log(level=arguments.log)
        run_dialogue_from_arguments(arguments)
    except Exception as e:
        raise e
    finally:
        end = time.time()
        logger.info(f"Running time: {end - start:.3f}s")
        logging.shutdown()
