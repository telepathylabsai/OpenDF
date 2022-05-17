"""
Entry point to run the system with dialogs coming from user text.
"""
import argparse

from opendf.graph.constr_graph import construct_graph
from opendf.graph.eval import evaluate_graph, check_dangling_nodes
from opendf.graph.draw_graph import draw_all_graphs
from opendf.applications.smcalflow.fill_type_info import fill_type_info
from opendf.graph.node_factory import NodeFactory
from opendf.defs import *
from opendf.graph.dialog_context import DialogContext
from opendf.graph.translate import process_user_txt, get_user_txt, print_dialog, get_sexp_cont
from opendf.utils.arg_utils import add_environment_option
from opendf.exceptions import parse_node_exception

# run non-dataflow dialogues in a dataflow system - following SM's idea of executing MultiWOZ with dataflow.

# the main function takes as input user text.
# it performs a mock NLU, and translates it into S-exp's
# the input is taken from dialogs in opendf.examples.text_examples

# this program does not work right now, as the original application (nodes) it was developed for are not part of this
# release.

logger = logging.getLogger(__name__)

# init type info
node_fact = NodeFactory.get_instance()
d_context = DialogContext()
environment_definitions = EnvironmentDefinition.get_instance()

fill_type_info(node_fact)


def dialog_txt(dialog_id):
    end_of_dialog = False
    d_context.reset_turn_num()
    ex = None
    i_utter = 0
    conversation = []

    logger.info('dialog #%d', dialog_id)
    print_dialog(dialog_id)
    while not end_of_dialog:
        # if any initialization of the graph is needed, for now we assume there is a text command to do it
        # (can be application specific...) - hack, avoids need for special init code

        # 1. get user input, do NLP to extract sexp(s)
        txt = get_user_txt(dialog_id, i_utter)
        if txt is None:
            break
        logger.info('_' * 40 + '\n' + txt + '\n' + '-' * 40)
        ptxt = txt
        sexps = process_user_txt(txt, d_context)  # for now - assuming one user txt per turn - TODO:
        conversation += sexps
        if not sexps:
            logger.info('>>> I did not understand that. (empty Sexp)')
            if d_context.exceptions:
                msg, nd, _, _ = parse_node_exception(d_context.exceptions[0])
                logger.info('>>> %s', msg)
            i_utter += 1
            continue
        if sexps is None:
            break
        logger.info('Sexp : %s', sexps)
        psexp = sexps

        d_context.reset_messages()
        cont = None
        for s in sexps:
            sexp, cont = get_sexp_cont(s)  # if one txt per turn, then the all but the last sexp per turn are cont

            d_context.continued_turn = cont  # continued turn - tells agent to "wait" until user is done
            # 2. construct new graph - perform SOME syntax checks on input program.
            #    if something went wrong (which means natural language method sent a wrong sexp) -
            #       no goal was added to the dialog (it was discarded) - user can't help resolve this
            #    if no exception, then a goal has been added to the dialog
            gl, ex = construct_graph(sexp, d_context)

            # 3. evaluate graph
            if ex is None:
                ex = evaluate_graph(gl)  # send in previous graphs (before curr_graph added)

            # if one txt per turn - last sexp is no cont.
            # unless a continuation turn, save last exception (agent's last message + hints)
            d_context.set_prev_agent_turn(ex)

        # 4. answer user: generate message to user, and modify graph to reflect given answer
        end_of_dialog = False

        i_utter += 1
        if not cont:
            d_context.inc_turn_num()

        check_dangling_nodes(d_context)  # sanity check - debug only
        if environment_definitions.turn_by_turn and not end_of_dialog:
            draw_all_graphs(d_context, dialog_id)
            input()

    draw_all_graphs(d_context, dialog_id, not ex, psexp, ptxt)
    if d_context.exceptions:
        msg, nd, _, _ = parse_node_exception(d_context.exceptions[-1])
        nd.explain(msg=msg)

    with open('conv_sexps.txt', 'w') as f:
        f.write(',\n'.join(["'%s'" % i for i in conversation]))


def create_arguments_parser():
    """
    Creates the argument parser for the file.

    :return: the argument parser
    :rtype: argparse.ArgumentParser
    """
    parser = argparse.ArgumentParser(
        description="The entry point to run the system with dialogs coming from user text. "
                    "It runs examples from the  `opendf/examples/text_examples.py` file.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument(
        "--dialog_id", "-d", metavar="dialog_id", type=int, required=False, default=0,
        help="the dialog id to use. "
             "This should be the index of a dialog defined in the `opendf/examples/text_examples.py` file"
    )

    parser.add_argument(
        "--log", "-l", metavar="log", type=str, required=False, default="DEBUG",
        choices=LOG_LEVELS.keys(),
        help=f"The level of the logging, possible values are: {list(LOG_LEVELS.keys())}"
    )

    parser = add_environment_option(parser)

    return parser


if __name__ == "__main__":
    try:
        parser = create_arguments_parser()
        arguments = parser.parse_args()
        config_log(arguments.log)
        id_arg = arguments.dialog_id
        if arguments.environment:
            environment_definitions.update_values(**arguments.environment)

        dialog_txt(id_arg)
    except:
        pass
    finally:
        logging.shutdown()