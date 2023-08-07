"""
The main entry point to run the dataflow graphs in an interactive way.
"""
import logging
import sys
import traceback

import yaml

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
from opendf.main import OpenDFDialogue

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


def main():
    print("This is the iterative version of OpenDF.")
    print("Enter an OpenDF P-Expression; or -h for help:")
    restart_dialog = True
    dialog_context = DialogContext()
    df_dialogue = OpenDFDialogue()
    gl = None
    while True:
        if restart_dialog:
            dialog_context = DialogContext()
            if use_database:
                Database.get_instance().clear_database()
                populate_stub_database(dialog_context.init_stub_file)
            else:
                fill_graph_db(dialog_context, dialog_context.init_stub_file)
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
                gl, ex, dialog_context, turn_answers = df_dialogue.run_single_turn(read, dialog_context, False, gl)
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
        application_config = yaml.load(open("resources/smcalflow_config.yaml", 'r'), Loader=yaml.UnsafeLoader)
        environment_class = application_config["environment_class"]
        with environment_class:
            main()
    except Exception as e:
        raise e
    finally:
        if use_database:
            database = Database.get_instance()
            if database:
                database.erase_database()
        logging.shutdown()
