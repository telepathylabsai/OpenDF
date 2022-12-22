"""
The main entry point to run the dataflow graphs in an interactive way.
"""
import logging
import sys
import traceback

from opendf.applications.smcalflow.database import populate_stub_database, Database
from opendf.applications.smcalflow.domain import fill_graph_db
from opendf.applications.fill_type_info import fill_type_info
from opendf.defs import EnvironmentDefinition, OUTLINE_SIMP, SUGG_IMPL_AGR, SUGG_MSG, use_database
from opendf.dialog import d_context
from opendf.exceptions import DFException, parse_node_exception
from opendf.graph.constr_graph import construct_graph, check_constr_graph
from opendf.graph.dialog_context import DialogContext
from opendf.graph.draw_graph import draw_all_graphs
from opendf.graph.eval import evaluate_graph
from opendf.graph.node_factory import NodeFactory
from opendf.graph.transform_graph import do_transform_graph

logger = logging.getLogger(__name__)

# init type info
node_fact = NodeFactory.get_instance()
environment_definitions = EnvironmentDefinition.get_instance()
fill_type_info(node_fact)


class ClearContextException(Exception):
    """
    Exception to clear the dialog context.
    """
    pass


def clear_context_command(*args, **kwargs):
    """
    finishes the dialog and starts a new one
    """
    raise ClearContextException()


def draw_graph_command(dialog_context, *args, **kwargs):
    """
    draws the graph
    """
    try:
        draw_all_graphs(dialog_context)
    except:
        pass


def quit_command(*args, **kwargs):
    """
    quits the program
    """
    raise KeyboardInterrupt("Bey!")


def help_command(*args, **kwargs):
    """
    prints this help message
    """
    print("This is the help:")
    print("it start from a clean context,")
    print("enter an OpenDF P-Expression to run it.")
    print("")
    print("Possible commands are:")
    for k, v in sorted(COMMANDS.items(), key=lambda x: x[0]):
        print(f"-{k}:\t{v.__doc__.strip()}")


COMMANDS = {
    'c': clear_context_command,
    'd': draw_graph_command,
    'h': help_command,
    'q': quit_command,
}


def run_turn(expression, dialog_context):
    """
    Runs the expression with the dialog context.

    :param expression: the P-expression
    :type expression: str
    :param dialog_context: the dialog context
    :type dialog_context: DialogContext
    :return: the graph and the exceptions
    :rtype: Tuple[List[Node], List[Exception]]
    """
    if environment_definitions.clear_exc_each_turn:
        dialog_context.clear_exceptions()
    if environment_definitions.clear_msg_each_turn:
        dialog_context.reset_messages()

    igl, ex = construct_graph(expression, dialog_context, constr_tag=OUTLINE_SIMP, no_post_check=True)

    gl, ex = do_transform_graph(igl)  # for drawing without yield

    check_constr_graph(gl)

    # apply implicit accept suggestion if needed. This is when prev turn gave suggestions, and one of them was
    #   marked as implicit-accept (SUGG_IMPL_AGR) (i.e. apply it if the user moves to another topic without accept or reject)
    if dialog_context.prev_sugg_act:
        j = [s[2:] for s in dialog_context.prev_sugg_act if s.startswith(SUGG_IMPL_AGR)]
        if j and not expression.startswith('AcceptSuggestion') and not expression.startswith('RejectSuggestion'):
            sx, ms = j[0], None
            if SUGG_MSG in sx:
                s = sx.split(SUGG_MSG)
                sx, ms = s[0], s[1]
            gl0, ex0 = construct_graph(sx, dialog_context)
            if ex0 is None:
                if not gl.contradicting_commands(gl0):
                    evaluate_graph(gl0)
                    if ms:
                        expression.add_message(gl0, ms)

    if ex is None:
        ex = evaluate_graph(gl)  # send in previous graphs (before curr_graph added)

    # unless a continuation turn, save last exception (agent's last message + hints)
    dialog_context.set_prev_agent_turn(ex)

    dialog_context.inc_turn_num()

    if dialog_context.exceptions:
        msg, nd, _, _ = parse_node_exception(dialog_context.exceptions[-1])
        nd.explain(msg=msg)

    return gl, ex


def main():
    print("This is the iterative version of OpenDF.")
    print("Enter an OpenDF P-Expression; or -h for help:")
    restart_dialog = True
    dialog_context = DialogContext()
    while True:
        if restart_dialog:
            dialog_context = DialogContext()
            if use_database:
                Database.get_instance().clear_database()
                populate_stub_database()
            else:
                fill_graph_db(d_context)
            restart_dialog = False

        try:
            print("# ", end="")
            read = input()
            if read[0] == '-':
                command_name = read[1:]
                command = COMMANDS.get(command_name)
                if command:
                    command(dialog_context)
                else:
                    raise Exception(f"Command not found: {command_name}")
            else:
                gl, ex = run_turn(read, dialog_context)
                if ex:
                    print(ex[-1].args[0], file=sys.stderr)
                elif dialog_context.messages:
                    print(dialog_context.messages[-1][1])
        except BaseException as e:
            if isinstance(e, ClearContextException):
                restart_dialog = True
                continue
            if len(e.args) > 0:
                print(e.args[0])
            if not isinstance(e, DFException):
                print(traceback.format_exc())
            if isinstance(e, KeyboardInterrupt):
                break


if __name__ == '__main__':
    try:
        main()
    except:
        pass
    finally:
        if use_database:
            database = Database.get_instance()
            if database:
                database.erase_database()
        logging.shutdown()
