import argparse
import re
import os

from opendf.dialog_simplify import prep_turn
from opendf.graph.constr_graph import construct_graph
from opendf.graph.draw_graph import draw_all_graphs
from opendf.applications.simplification.fill_type_info import fill_type_info
from opendf.graph.node_factory import NodeFactory
from opendf.defs import *
from opendf.graph.dialog_context import DialogContext

# import aux funcs from original MS code - to calculate length (in tokens) of original s-exp
from opendf.utils.simplify_exp import indent_sexp

# to run from command line (in OpenDF):
# PYTHONPATH=$(pwd) python...


draw_one_graph = None

logger = logging.getLogger(__name__)

# init type info
node_fact = NodeFactory.get_instance()
# TODO: check dialog context
d_context = DialogContext.get_instance()
d_context.suppress_exceptions = True  # avoid exit in

fill_type_info(node_fact)


def exp_max_depth(s):
    d = 0
    maxd = 0
    for i in s:
        if i == '(':
            d += 1
            maxd = max(d, maxd)
        if i == ')':
            d -= 1
    return maxd


def dialog(working_dir, input_file):
    working_dir = '../../smcalflow'
    conv_dir = os.path.join(working_dir, 'conv')

    # These files are created by dialog_simplify. choose one - look at valid or train.
    fname = os.path.join(conv_dir, f"convl.{input_file}")
    turns = [i.split('@@@') for i in open(fname, 'r').readlines()]

    count = 0
    skip = False
    if len(sys.argv) > 1:
        if sys.argv[1] == '-skip':
            skip = True

    # we can also see the results of the NL->EXP translation - needs separate preparation - use
    trans = None
    if 'valid' in fname:
        try:
            trans = {}
            corr = {}
            for l in open(conv_dir + '/transl.valid', 'r').readlines():
                did, tid, cr, sxp = l.strip().split('@@@')
                trans[did + ':' + tid] = sxp
                corr[did + ':' + tid] = cr
        except:
            trans = None

    logger.info('got %d turns', len(turns))
    d_context.show_print = False

    nt = len(turns)
    it = 0
    prev = False
    prev_did = None
    while it < nt:
        turn = turns[it]
        try:
            [did, tid, txt, org, simp] = turn
            idx = did + ':' + tid
            simp_nb = re.sub(' ', '', simp)  # simp without spaces

            # set cond to the search condition: on simplified expression, orig expression, size / content / ...

            cond = 'CreateEvent(with_attendee' in simp_nb
            cond = trans and idx in trans and corr[idx] == 'False'
            cond = 'intension' in simp and 'NewClobber' not in simp
            cond = 'ForwardEventWrapper' in simp
            cond = 'ReviseConstraint' in simp
            cond = 'NewClobber' in org
            # cond = exp_max_depth(org) > 12
            # cond = 'NextTime' in org
            cond = 'do' in org
            cond = len(txt) > 100 and int(tid) > 3 and did != prev_did
            cond = 'refer' in org and 'Constraint[Event]' in org
            cond = True
            # cond = 'Update' in org
            if cond or prev:

                txt = re.sub('[\[\]]', '  NL  ', txt)
                d_context.clear()
                org_sexp = org
                isexp, oo = prep_turn(org)
                sexp = indent_sexp(org_sexp, org_sexp=True)
                try:
                    igl, ex = construct_graph(isexp, d_context, constr_tag=OUTLINE_SIMP, no_post_check=True,
                                              no_exit=True)
                    # iipsexp = igl.print_tree(None, ind=None, with_id=False, with_pos=False, trim_leaf=True)
                    igl.add_dup_goal(True)
                except:
                    pass
                    # iipsexp = org

                try:
                    sgl, ex = construct_graph(simp, d_context, constr_tag=OUTLINE_SIMP, no_post_check=True,
                                              no_exit=True)
                    d_context.add_goal(sgl)
                    simpt = indent_sexp(simp)
                except:
                    simpt = simp

                texp = ''
                if trans and idx in trans:
                    texp = trans[idx]
                    t = re.sub(' ', '', re.sub("'", '', texp))
                    try:
                        tgl, ex = construct_graph(t, d_context, constr_tag=OUTLINE_SIMP, no_post_check=True,
                                                  no_exit=True)
                        d_context.add_goal(tgl)
                    except:
                        pass

                count += 1
                if not skip:
                    draw_all_graphs(d_context, 0, sexp=sexp, txt=txt, simp=simpt)
                    # draw_all_graphs(0)
                    # draw_all_graphs(0, sexp=sexp)
                    # draw_all_graphs(0, simp=simpt)

                    open(conv_dir + '/show.txt', 'w').write('%s\n\n%s\n\n%s\n\n%s\n' % (org, simp, texp, txt))

                    logger.info('hit Enter for next one ("p" for prev turn, "n" for next turn  "q" to exit)')
                    k = input()
                    prev = False
                    if k == 'p':
                        prev = True
                        it -= 2
                    if k == 'n':
                        prev = True
                    if k == 'q':
                        raise Exception('exit')
                    if k == 's':
                        skip = True
                prev_did = did

        except Exception as ex:
            if not skip:
                if ex.args and ex.args[0] == 'exit':
                    exit()
                if turn != ['ERR\n']:
                    logger.info(turn)
            pass

        it += 1


def create_arguments_parser():
    """
    Creates the argument parser for the file.

    :return: the argument parser
    :rtype: argparse.ArgumentParser
    """
    parser = argparse.ArgumentParser(
        description="Entry point to show the simplified expression generated by `dialog_simplify.py`.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument(
        "working_dir", metavar="working_dir", type=str,
        help="the path for the simplification data directory (e.g. '.../smcalflow'). "
             "Under that, there should be two subdirectories: "
             "`data`: this should have the original annotation files downloaded from microsoft's "
             "task_oriented_dialogue_as_dataflow_synthesis GitHub page. This will include two files: "
             "`train.dataflow_dialogues.jsonl` and `valid.dataflow_dialogues.jsonl`. "
             "Make sure to download version V1 of the data! SMCalFlow 1.0 links -> smcalflow.full.data.tgz; and "
             "`conv`: results of the simplification process (and some extra outputs) will go here. "
             "The user should run `dialog_simplify.py` to generate the expression used by this file."
    )

    input_values = ["train", "valid"]
    parser.add_argument(
        '--input_file', '-i', metavar='input_file',
        type=str, required=False, default=input_values[0], choices=input_values,
        help=f"the input file of the system, the choices are: {input_values}. "
             "If not set, it will run a dialog from the `opendf/examples/simplify_examples.py` file, "
             "defined by the `dialog_id` argument",
    )

    parser.add_argument(
        "--log", "-l", metavar="log", type=str, required=False, default="DEBUG",
        choices=LOG_LEVELS.keys(),
        help=f"The level of the logging, possible values are: {list(LOG_LEVELS.keys())}"
    )

    return parser


if __name__ == "__main__":
    try:
        parser = create_arguments_parser()
        arguments = parser.parse_args()
        config_log(arguments.log)
        work_arg = arguments.working_dir
        input_arg = arguments.input_file

        dialog(work_arg, input_arg)
    except:
        pass
    finally:
        logging.shutdown()
