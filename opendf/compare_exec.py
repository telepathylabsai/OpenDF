"""
compare execution of SMCalFlow ground-truth Pexps and translated Pexps
"""


# to run this from the command line (assuming running from the repository's root directory) , use:
# PYTHONPATH=$(pwd) python opendf/compare_exec.py -i train/valid -c resources/populate_smcalflow_config.yaml workdir


import json
import argparse

from opendf.graph.constr_graph import construct_graph, check_constr_graph
from opendf.graph.eval import evaluate_graph, check_dangling_nodes
from opendf.graph.node_factory import NodeFactory
from opendf.defs import *
from opendf.graph.dialog_context import DialogContext
from opendf.utils.arg_utils import add_environment_option
from opendf.utils.io import load_jsonl_file
from opendf.utils.utils import to_list
from opendf.graph.transform_graph import do_transform_graph
from opendf.graph.draw_graph import draw_all_graphs
from opendf.misc.populate_utils import init_db, get_all_db_events
from opendf.applications.smcalflow.domain import get_stub_data_from_json
from opendf.exceptions import re_raise_exc
from opendf.exceptions.df_exception import DFException
from opendf.applications.smcalflow.domain import DBevent, DBPerson, WeatherPlace
import yaml
from random import randint, seed, random
import re

seed(100)

logger = logging.getLogger(__name__)


def clear_pop_context(context):
    context.agent_context = None  # pointer to agent context (needed?)
    context.agent_words = []
    context.agent_templs = []
    context.agent_vals = []
    # context.templates = None
    context.user_vals = []
    context.db_people = None  # temp storage of db stub data
    context.db_events = None
    context.db_places = None
    context.user_txt = None
    context.agent_txt = None
    context.populated_events = []  # keep the id's of recipients which were added by populate (i.e. not by create)
    context.init_stub_file = None


def conv_obj(objs):
    return [o if isinstance(o, str) else o.show() for o in objs]


# compare execution results of two runs, each represented by a d_context - initial implementation
# TODO This function will also be used to compare execution of ground-truth Pexp and translated NL->Pexp
# one possible way to compare is to look only at the response of the agent - ignore the internal structure
#   (this ignores the source of the error - we may get a wrong execution which generates a correct answer -
#     error may manifest in later turns!)
# - focus on the last turns
# - look at result pointers
# - see that object id's match (for now, just that the same object id appears "somewhere" in the same turn's results)
# - see that the same values appear in results of specific functions
# mode - to remind that there can be multiple modes of comparison
def compare_graph_exec(ctx1, ctx2, evs1=None, evs2=None, mode=None):
    evs1 = evs1 if evs1 else []
    evs2 = evs2 if evs2 else []
    if len(evs1) != len(evs2) or not all([i in evs2 for i in evs1]):
        print('      MISmatched events')
        print(evs1)
        print('   :::')
        print(evs2)
        return False
    turn1, exc1, msg1 = ctx1.get_exec_status()
    turn2, exc2, msg2 = ctx2.get_exec_status()
    if turn1!=turn2 or (exc1 and not exc2) or (exc2 and not exc1):
        return False
    if exc1:  # both have exceptions
        # n1, n2 = exc1[-1][0], exc2[-1][0]
        e1, e2 = exc1[-1], exc2[-1]
        o1, o2 = e1.objects if e1.objects else [], e2.objects if e2.objects else []
        o1, o2 = conv_obj(o1), conv_obj(o2)
        ok = len(o1)==len(o2) and all([o in e2.objects for o in e1.objects])
        return ok

    if (msg1 and not msg2) or (msg2 and not msg1):
        return False
    if msg1:  # both have messages
        n1, n2 = msg1[-1][0], msg2[-1][0]
    if msg1 and n1.typename() == n2.typename() == 'Yield':
        y1 = n1.result.yield_msg()
        s1, o1 = y1 if isinstance(y1, tuple) and len(y1)==2 else (y1, ['999'])  # temp check, until all yields return objs
        y2 = n2.result.yield_msg()
        s2, o2 = y2 if isinstance(y2, tuple) and len(y2)==2 else (y2, ['999'])  # temp check, until all yields return objs
        o1, o2 = conv_obj(o1), conv_obj(o2)
        ok = all([o in o2 for o in o1])
        # print(o1)
        # print(o2)
        if True:
            for o in o1:
                if o in o2:
                    print('      matched: %s' % o)
                else:
                    print('      MISmatched: %s' % o)
        return ok
    return False


node_fact = NodeFactory.get_instance()

environment_definitions = EnvironmentDefinition.get_instance()


# execute the pexp
# returns False if an unintended error happened, else True
def exec_turn(pexp, d_context, fout=None, cont=False):
    try:
        igl, ex = construct_graph(pexp, d_context, constr_tag=OUTLINE_SIMP, no_post_check=True, no_exit=True)
        gl, ex = do_transform_graph(igl, add_yield=True)
        check_constr_graph(gl)
        # evaluate graph
        if ex is None:
            ex = evaluate_graph(gl)  # send in previous graphs (before curr_graph added)

        # unless a continuation turn, save last exception (agent's last message + hints)
        d_context.set_prev_agent_turn(ex)
        if not cont:
            d_context.inc_turn_num()
        check_dangling_nodes(d_context)  # sanity check - debug only
        if ex:
            if fout:
                fout.write("EXC: %s\n" % to_list(ex)[0].message)
            else:
                print("EXC: %s" % to_list(ex)[0].message)
        elif gl.typename() == 'Yield' and gl.evaluated:
            y = gl.inputs['output'].yield_msg()
            s, o = y if isinstance(y, tuple) and len(y)==2 else (y, [-999])  # temp check, until all yields return objs
            if fout:
                fout.write('YIELD: %s\n' % s)
            else:
                print('YIELD: %s' % s)
        return True
    except Exception as ex:
        msg = '----------' if len(ex.args) < 1 else '-----===-----' + ex.args[0]
        if fout:
            logger.info(msg)
            fout.write(msg + '\n')
        else:
            print(msg)
        if False and not isinstance(ex, DFException):
            re_raise_exc(ex)
        return True if isinstance(ex, DFException) else False


def gen_turn_logs(user_txt, agent_txt, turn, it, d_id, fout, jout):
    tt = user_txt + ' : [' + agent_txt + ']  '
    fout.write('Turn %d : Dialog %s\n' % (it, d_id))
    fout.write(user_txt + '\n')
    fout.write(turn + '\n')
    fout.write('-AgentAnswer- ' + agent_txt + '\n')
    jout.write(agent_txt + '\n')
    print('\nTurn %d: %s\n' % (it, tt))
    logger.info(turn)


def loc_id_to_name(id, places):
    for l in places:
        for p in l:
            if p.id==id:
                return p.name
    return None


# json loads DB objects as lists - convert back to DB objects
def get_db_objects(aobj):
    people = [DBPerson(*o) for o in aobj[0]]
    events = [DBevent(*o) for o in aobj[1]]
    places = [WeatherPlace(*o) for o in aobj[2]]
    return people, events, places


def dialog(working_dir, inp_name, data_file, dialog_id=None, draw_graph=True, from_id=False, parser_only=False):
    d_context = DialogContext()
    # a_context = DialogContext()

    conv_dir = os.path.join(working_dir, 'conv')
    in_file = os.path.join(working_dir, "conv", f"conv.{inp_name}.jsonl")

    dialogs = load_jsonl_file(in_file, unit=" dialogues")

    l = open(os.path.join(conv_dir, f"{inp_name}_hyps.txt"), 'r').readlines()
    hyps = {}
    for i in l:
        j = i.strip().split('::')
        hyps[j[0].strip()] = j[1].strip()

    added_objects = json.loads(open(os.path.join(conv_dir, f"added.{inp_name}"), 'r').read())
    n_dia, n_ok = 0, 0
    n_diff_pexp = 0
    n_turns, n_cmp_turns = 0, 0
    n_match = 0
    for idia, dia in enumerate(dialogs):
        d_id = dia['dialogue_id']
        if d_id not in added_objects:
            continue
        if dialog_id:
            if d_id[-len(dialog_id):]==dialog_id:  # dialog_id suffix
                if from_id:
                    dialog_id = None
                else:
                    stop = True
            else:
                if stop:  # no need to continue
                    break
                else:
                    continue

        print('\n\n%d %s   '% (idia, d_id) + 'X'*80 + ' \n\n')
        turns = [i['lispress'] for i in dia['turns']]

        # phase 1. load populated db (per dialog) and execute ground truth Pexp
        aobjs = added_objects[d_id]
        apeople, aevents, aplaces = get_db_objects(aobjs)
        turn_contexts = []  # contexts after each turn
        turn_evs = []  # db events after each turn
        d_context.clear()
        clear_pop_context(d_context)
        d_context.prev_nodes = None  # clear prev nodes at start of dialog
        d_context.suppress_exceptions = True  # avoid exit in
        d_context.init_stub_file = data_file
        init_db(d_context, data_file=data_file, additional_objs=(apeople, aevents, aplaces))
        ok = True
        for it, turn in enumerate(turns):
            if ok:
                pexp = turn  # , org = prep_turn(turn)
                user_txt = dia['turns'][it]['user_utterance']['original_text']
                #agent_txt = dia['turns'][it]['agent_utterance']['original_text']
                print('U: ' + user_txt)
                ok = exec_turn(pexp, d_context)  #, user_txt, agent_txt)
                turn_contexts.append(d_context.make_copy_with_pack())  # save d_context after each turn
                turn_evs.append(get_all_db_events())  # save all events in db after each turn

        # phase 2. execute hypothesized Pexps and compare resulting graphs
        if ok:  # compare only if the entire original dialog executed successfully (no partial dialogs!)
            print(' - - - - - - - -')
            d_context.clear()
            clear_pop_context(d_context)
            d_context.prev_nodes = None  # clear prev nodes at start of dialog
            d_context.suppress_exceptions = True  # avoid exit in
            d_context.init_stub_file = data_file
            init_db(d_context, data_file=data_file, additional_objs=(apeople, aevents, aplaces))
            cmp = True
            for it, turn in enumerate(turns):
                if (ok):
                    # print(turn)
                    user_txt = dia['turns'][it]['user_utterance']['original_text']
                    # agent_txt = dia['turns'][it]['agent_utterance']['original_text']
                    print('U: ' + user_txt)
                    pexp = turn.strip()
                    ii = '%s_%d' %(d_id, it)
                    if ii in hyps:
                        if re.sub('[ ]+', ' ', pexp)!=re.sub('[ ]+', ' ', hyps[ii]):
                            print('  >>> .%s.\n    > .%s.' %(pexp, hyps[ii]))
                            n_diff_pexp += 1
                        pexp = hyps[ii]
                    ok = exec_turn(pexp, d_context)  # , user_txt, agent_txt)
                    if ok:
                        evs = get_all_db_events()
                    # compare context and saved turn contexts
                    n_turns += 1 if ok and cmp else 0
                    cmp = cmp and ok and compare_graph_exec(d_context, turn_contexts[it], evs, turn_evs[it])
                    n_cmp_turns += 1 if cmp else 0
            if cmp:
                print('!!Dialog matched!!')
                n_match += 1
        n_dia, n_ok = n_dia+1, n_ok+1 if ok else n_ok
        print('<%d/%d>  %d/%d  diff_pexps=%d   matched dialogs=%d ' % (n_ok, n_dia, n_cmp_turns, n_turns, n_diff_pexp, n_match))

    # save added objects for all dialogs
    if not parser_only:
        open(os.path.join(conv_dir, f"added.{inp_name}"), 'w').write(json.dumps(added_objects))

    return None


def create_arguments_parser():
    """
    Creates the argument parser for the file.

    :return: the argument parser
    :rtype: argparse.ArgumentParser
    """
    parser = argparse.ArgumentParser(
        description="Entry point to transform original S-exps into simplified P-exps.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument(
        "--config", "-c", metavar="config", type=str, required=False, default="resources/populate_smcalflow_config.yaml",
        help="the configuration file for the application"
    )

    parser.add_argument(
        "working_dir", metavar="working_dir", type=str,
        help="the path for the simplification data directory (e.g. '.../smcalflow'). "
             "Under that, there should be two subdirectories: "
             "`data`: this should have the original annotation files downloaded from microsoft's "
             "task_oriented_dialogue_as_dataflow_synthesis GitHub page. This will include two files: "
             "`train.dataflow_dialogues.jsonl` and `valid.dataflow_dialogues.jsonl`. "
             "Make sure to download version V1 of the data! SMCalFlow 1.0 links -> smcalflow.full.data.tgz; and "
             "`conv`: results of the simplification process (and some extra outputs) will go here."
    )

    input_values = ["train", "valid"]
    parser.add_argument(
        '--input_file', '-i', metavar='input_file',
        type=str, required=True, default=None, choices=input_values,
        help=f"the input file of the system, the choices are: {input_values}. "
             "If not set, it will run a dialog from the `opendf/examples/simplify_examples.py` file, "
             "defined by the `dialog_id` argument",
    )

    parser.add_argument(
        "--dialog_id", "-d", metavar="dialog_id", type=str, required=False, default=0,
        help="the dialog id to use, if `input_file` is not provided. "
             "This should be the index of a dialog defined in the `opendf/examples/simplify_examples.py` file"
    )

    # from_id flags signals to iterate STARTING from the given dialog_id (helpful for debugging)
    parser.add_argument(
        "--from_id", "-f", metavar="from_id", type=bool, required=False, default=False,
        help="start processing from the given id. "
    )

    parser.add_argument(
        "--parser_only", "-p", metavar="parser_only", type=bool, required=False, default=False,
        help="test only the parsing of the agent reply "
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
        input_arg = arguments.input_file
        work_arg = arguments.working_dir
        id_arg = arguments.dialog_id
        from_id = arguments.from_id
        parser_only = arguments.parser_only
        if arguments.environment:
            environment_definitions.update_values(**arguments.environment)
        application_config = yaml.load(open(arguments.config, 'r'), Loader=yaml.UnsafeLoader)

        environment_class = application_config["environment_class"]
        environment_class.d_context = DialogContext()  # only for graphDB
        with environment_class:
            dialog(work_arg, input_arg, environment_class.stub_data_file, dialog_id=id_arg, from_id=from_id, parser_only=parser_only)

    except Exception as e:
        logger.exception(e)
    finally:
        logging.shutdown()


