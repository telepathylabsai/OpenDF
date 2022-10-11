"""
Entry point to transform original S-exps into simplified P-exps.
"""

import os
import json
import re
import argparse

import yaml

from opendf.examples.simplify_examples import dialogs
from opendf.exceptions.python_exception import SemanticException
from opendf.graph.constr_graph import construct_graph, check_constr_graph
from opendf.graph.eval import evaluate_graph, check_dangling_nodes
from opendf.graph.draw_graph import draw_all_graphs, draw_graphs
from opendf.defs import *
from opendf.graph.dialog_context import DialogContext
from opendf.utils.arg_utils import add_environment_option
from opendf.utils.io import load_jsonl_file
from opendf.utils.simplify_exp import indent_sexp, tokenize_pexp, sexp_to_tree, print_tree
from opendf.exceptions import parse_node_exception, re_raise_exc
from opendf.graph.simplify_graph import simplify_graph, pre_simplify_graph, clean_operators

logger = logging.getLogger(__name__)

# to run this from the command line (assuming running from the repository's root directory) , use:
# PYTHONPATH=$(pwd) python opendf/dialog_simplify.py [-i train/valid] workdir


# NOTE: the following imports are typically not used (see comment on use below), so are commented out.
#       In case you DO want to use it, download the repository:
#              git clone https://github.com/microsoft/task_oriented_dialogue_as_dataflow_synthesis.git
#              cd task_oriented_dialogue_as_dataflow_synthesis/
#              git checkout 6c08d2d690cb063cb5674650a9a145756acfebba
#       and then either:
#          1) Install the sm-dataflow package and its core dependencies:
#              python setup.py install
#              pip install more_itertools pydantic
#          OR
#          2) set the SMC_SRC_DIR to point to the location of the code, and add it to the path:
#               SMC_SRC_DIR = '../../dataflow/src'
#               sys.path.insert(0, SMCDIR)  # if not installed package
#
#       now the following imports should work
# from dataflow.core.lispress import parse_lispress
# from dataflow.core.linearize import lispress_to_seq


# NOTE: simplification data: set working_dir to point to the main directory (e.g. '.../smcalflow')
#       under that, there should be two subdirectories:
#          - data: this should have the original annotation files downloaded from microsoft's
#            task_oriented_dialogue_as_dataflow_synthesis GitHub page. this will include two files:
#               train.dataflow_dialogues.jsonl, valid.dataflow_dialogues.jsonl
#            make sure to download version V1 of the data!
#                 SMCalFlow 1.0 links  ->  smcalflow.full.data.tgz
#          - conv: results of the simplification process (and some extra outputs) will go here.

# when these node types appear in the original expression, we skip the expression
# these have syntax which is different from the usual expressions, and at the same time they are very rare
# exclude them to save some work in simplification, and save learning capacity in the NL->sexp translation
EXCLUDE_TYPES = ['update', 'get']


# the main function gets original S-exps as input, and generates a simplified python-style expression (P-exp)
# input is taken from dialogs in opendf.examples.simplify_examples for now.
#   Later - this should run automatically on the original dataset

def get_turn_list(dialog_id):
    if dialog_id < len(dialogs):
        return list(range(len(dialogs[dialog_id])))
    else:
        return []


def prep_turn(d):
    tree = sexp_to_tree(d)
    s = print_tree(tree)
    # dd = re.sub('[ ]+', '\n', d)
    return s, d


# get an original Sexp from the dataset, and transform it into a Pexp
def get_orig_pexp(dialog_id, turn):
    if dialog_id < len(dialogs) and turn < len(dialogs[dialog_id]):
        d, cont = dialogs[dialog_id][turn], False
        s, dd = prep_turn(d)
        return s, dd
    return None, None


def print_dialog(dialog_id):
    if dialog_id < len(dialogs):
        for d in dialogs[dialog_id]:
            logger.info(d)


def get_sexp_cont(s):
    return (s[2:], True) if s.startswith(CONT_TURN) else (s, False)


draw_one_graph = None

# init type info
# node_fact = NodeFactory.get_instance()
# d_context = DialogContext()
# d_context.suppress_exceptions = True  # avoid exit in

environment_definitions = EnvironmentDefinition.get_instance()

# fill_type_info(node_fact)


def dialog(working_dir, environment_class, input_file=None, dialog_id=0, draw_graph=True):
    d_context = DialogContext()
    environment_class.d_context = d_context
    environment_class.simplification = True

    simp = None
    with environment_class:
        conv_dir = os.path.join(working_dir, 'conv')
        if not os.path.isdir(conv_dir):
            os.makedirs(conv_dir, exist_ok=True)

        from_jsonl = None
        if input_file:
            from_jsonl = os.path.join(working_dir, "data", f"{input_file}.dataflow_dialogues.jsonl")

        end_of_dialog = False
        d_context.reset_turn_num()

        dialogs = load_jsonl_file(from_jsonl, unit=" dialogues") if from_jsonl else [dialog_id]
        if from_jsonl:
            # d_context.set_print(False)
            fname = from_jsonl.split('/')[-1].split('.')[0]
            fout = open(os.path.join(conv_dir, f"conv.{fname}"), 'w')
            lout = open(os.path.join(conv_dir, f"convl.{fname}"), 'w')
            jout = open(os.path.join(conv_dir, f"conv.{fname}.jsonl"), 'w')
            eout = open(os.path.join(conv_dir, f"err.{fname}.conv"), 'w')
        else:
            logger.info('dialog #%d', dialog_id)
            print_dialog(dialog_id)

        orig_count, new_count = 0, 0

        for dia in dialogs:
            turns = [i['lispress'] for i in dia['turns']] if from_jsonl else get_turn_list(dialog_id)
            new_turns = []
            accum_text = ''
            d_context.prev_nodes = None  # clear prev nodes at start of dialog
            if from_jsonl:
                fout.write(f"{'#' * 30} Dialog {dia['dialogue_id']} {'#' * 30}\n")
            for it, turn in enumerate(turns):
                logger.info(turn)
                if from_jsonl:
                    d_context.clear()
                    if turn == '()':
                        turn = '(GenericPleasantry)'
                    isexp, org = prep_turn(turn)
                    t1 = dia['turns'][it]['user_utterance']['original_text']
                    agent_text = dia['turns'][it]['agent_utterance']['original_text']
                    tt = t1 + ' : [' + agent_text + ']  '
                    accum_text += tt
                    fout.write('Turn %d : Dialog %s\n' % (it, dia['dialogue_id']))
                    fout.write("User:  " + t1 + '\n')
                    fout.write("Agent: " + agent_text + '\n')
                    fout.write(turn + '\n')
                    lout.write('%s@@@%s@@@%s@@@%s@@@' % (dia['dialogue_id'], it, accum_text, turn))
                else:
                    isexp, org = get_orig_pexp(dialog_id, turn)

                if not from_jsonl:
                    d_context.prev_nodes = 'EventFunc'

                org_seq = []
                try:
                    err = False
                    # org_seq is used only for showing statistics about the length of the original Sexps, and this is
                    #   only ever useful if you want to verify you get the same result as reported in their original
                    #   paper.
                    #   org_seq = lispress_to_seq(parse_lispress(org))
                    org_sexp = org
                    igl, ex = construct_graph(isexp, d_context, constr_tag=OUTLINE_SIMP, no_post_check=True,
                                              no_exit=from_jsonl)
                    # iipsexp = igl.print_tree(None, ind=None, with_id=False, with_pos=False, trim_leaf=True)

                    orig_nodes = igl.topological_order()
                    for i in orig_nodes:  # some rare constructs we don't support
                        if i.typename() in EXCLUDE_TYPES:
                            raise SemanticException('excluded type: ' + i.typename())

                    orig_count = len(igl.topological_order())
                    if True:
                        igl.add_dup_goal(environment_definitions.simp_add_init_goal)

                    ex = evaluate_graph(igl)  # some preparations for the simplification

                    bgl, ex = pre_simplify_graph(igl, d_context)
                    if not from_jsonl:
                        bgl.add_dup_goal(environment_definitions.simp_add_interm_goals)

                    gl, ex = simplify_graph(bgl, d_context)

                    if 'let' in isexp:
                        gl, ex = simplify_graph(gl, d_context)

                    clean_operators(gl)
                    gl.reorder_inputs_recurr()
                    d_context.add_goal(gl)

                    new_count = len(gl.topological_order())
                    simp, _ = gl.print_tree(None, ind=None, with_id=False, with_pos=False,
                                            trim_leaf=True, trim_sugar=True, mark_val=True)
                    if from_jsonl:
                        logger.info(simp)
                    else:
                        logger.info("\n %s \n", simp)
                    # if True:
                    #     simp_toks = re.sub('[ \n]+', ' ', simp)  # <<< hack - temp!
                    #     #print('ZZZ  %s\n' % simp_toks)
                    # else:
                    simp_toks = tokenize_pexp(simp, sep_equal=False)
                    simp_toks = re.sub(' [ ]+', ' ', simp_toks)
                    if not from_jsonl:
                        logger.info(simp_toks)

                    if from_jsonl:
                        fout.write('--> ' + simp + '\n')
                        lout.write(simp + '\n')
                    check_constr_graph(gl)

                    d_context.add_goal(gl)

                    logger.info(
                        'counts: %d / %d     %d %d ', orig_count, new_count, len(org_seq), len(simp_toks.split()))
                    if from_jsonl:
                        fout.write('counts: %d / %d     %d / %d\n\n' %
                                   (orig_count, new_count, len(org_seq), len(simp_toks.split())))
                        old_turn = dia['turns'][it]
                        old_turn['lispress'] = simp_toks
                        new_turns.append(old_turn)

                except Exception as ex:
                    err = True
                    msg = '----------' if len(ex.args) < 1 else '-----===-----' + ex.args[0]
                    logger.info(msg)
                    logger.info('counts: %d / XX     %d / XX', orig_count, len(org_seq))
                    if from_jsonl:
                        fout.write(msg + '\n')
                        fout.write('counts: %d / XX     %d / XX\n' % (orig_count, len(org_seq)))
                        eout.write("# %s\n# '%s',\n" % (msg, re.sub('\n', ' ', org)))
                        lout.write('ERR\n')
                    else:
                        re_raise_exc(ex)

                if not from_jsonl:
                    check_dangling_nodes(d_context)  # sanity check - debug only
                    if environment_definitions.turn_by_turn and not end_of_dialog:
                        draw_all_graphs(d_context, dialog_id)
                        input()

                # keep copy of prev turn's nodes (orig and simplified) - for cases where a turn's simplification
                #  depends on the previous turn (this is discouraged. currently - only for NewClobber)
                if from_jsonl:
                    d_context.prev_nodes = None if err else \
                        (d_context.goals[-1].duplicate_res_tree(register=False),
                         d_context.goals[0].duplicate_res_tree(register=False))

            if from_jsonl and len(new_turns) > 0:
                dia['turns'] = new_turns
                jout.write(json.dumps(dia) + '\n')

        if from_jsonl:
            fout.close()
            jout.close()
            eout.close()
            lout.close()

        simp = None
        if not from_jsonl:
            if len(d_context.goals) > 0:
                simp = indent_sexp(d_context.goals[-1].print_tree(None, ind=None, with_id=False, with_pos=False,
                                                                  trim_leaf=True, trim_sugar=True, mark_val=True)[0])
                logger.info(simp)

            sexp = indent_sexp(org_sexp, org_sexp=True)
            if draw_graph:
                if draw_one_graph is None:
                    draw_all_graphs(d_context, dialog_id, sexp=sexp, simp=simp)
                else:
                    if draw_one_graph == -1:
                        draw_graphs([d_context.goals[-1]], None, None, sexp=sexp)
                    elif draw_one_graph == -2:
                        draw_graphs([d_context.goals[-1]], None, None, simp=simp)
                    else:
                        draw_graphs([d_context.goals[draw_one_graph]], None, None)

            if d_context.exceptions:
                msg, nd, _, _ = parse_node_exception(d_context.exceptions[-1])
                nd.explain(msg=msg)

    return simp


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
        "working_dir", metavar="working_dir", type=str,
        help="the path for the simplification data directory (e.g. '.../smcalflow'). "
             "Under that, there should be two subdirectories: "
             "`data`: this should have the original annotation files downloaded from microsoft's "
             "task_oriented_dialogue_as_dataflow_synthesis GitHub page. This will include two files: "
             "`train.dataflow_dialogues.jsonl` and `valid.dataflow_dialogues.jsonl`. "
             "Make sure to download version V1 of the data! SMCalFlow 1.0 links -> smcalflow.full.data.tgz; and "
             "`conv`: results of the simplification process (and some extra outputs) will go here."
    )

    parser.add_argument(
        "--config", "-c", metavar="config", type=str, required=False, default="resources/smcalflow_config.yaml",
        help="the configuration file for the application"
    )

    # input_values = ["train", "valid", "multiwoz"]
    parser.add_argument(
        '--input_file', '-i', metavar='input_file',
        type=str, required=False, default=None,  # choices=input_values,
        help=f"the input file of the system. "
             "If not set, it will run a dialog from the `opendf/examples/simplify_examples.py` file, "
             "defined by the `dialog_id` argument",
    )

    parser.add_argument(
        "--dialog_id", "-d", metavar="dialog_id", type=int, required=False, default=0,
        help="the dialog id to use, if `input_file` is not provided. "
             "This should be the index of a dialog defined in the `opendf/examples/simplify_examples.py` file"
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
        if arguments.environment:
            environment_definitions.update_values(**arguments.environment)

        application_config = yaml.load(open(arguments.config, 'r'), Loader=yaml.UnsafeLoader)

        dialog(work_arg, application_config["environment_class"], input_arg, dialog_id=id_arg)
    except Exception as e:
        logger.exception(e)
    finally:
        logging.shutdown()
# stats on lengths:
#  grep "counts: " conv.train | grep -v XX | awk 'BEGIN{n=0; a=0;  c=0;}{n+=1; a+=$4;  c+=$7;}END{printf("%d - %.2f  %.2f\n", n, 1.0*a/n,  1.0*c/n )}'
