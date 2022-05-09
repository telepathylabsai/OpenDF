"""
compare results of translation to ground truth - tree comparison
"""

import os

# from opendf.examples.simplify_examples import dialogs
from opendf.graph.constr_graph import construct_graph
# from opendf.graph.eval import evaluate_graph, check_dangling_nodes
# from opendf.graph.draw_graph import draw_all_graphs, draw_graphs
from opendf.applications.simplification.fill_type_info import fill_type_info
from opendf.graph.node_factory import NodeFactory
from opendf.defs import *
from opendf.graph.dialog_context import DialogContext
# from opendf.utils.arg_utils import add_environment_option
# from opendf.utils.io import load_jsonl_file
# from opendf.utils.simplify_exp import indent_sexp, tokenize_pexp, sexp_to_tree, print_tree
# from opendf.exceptions import parse_node_exception, re_raise_exc
# from opendf.graph.simplify_graph import simplify_graph, pre_simplify_graph, clean_operators
from opendf.parser.pexp_parser import parse_p_expressions

working_dir = '../../analyze'

# init type info
node_fact = NodeFactory.get_instance()
d_context = DialogContext()
d_context.suppress_exceptions = True  # avoid exit
d_context.show_print = False  # supress construct printouts

environment_definitions = EnvironmentDefinition.get_instance()

fill_type_info(node_fact)

logger = logging.getLogger(__name__)


def mismatched_parens(s):
    n = 0
    for c in s:
        n = n - 1 if c == ')' else n + 1 if c == '(' else n
        if n < 0:
            return True
    if n > 0:
        return True
    return False


def compare_trees(working_dir):
    conv_dir = os.path.join(working_dir, 'conv')
    report = [l.strip() for l in open(conv_dir + '/valid.prediction_report.txt', 'r').readlines()]
    block_len = 9  # report block for one turn
    n_dia = 0
    n_exact = 0
    n_equiv = 0
    n_except = 0
    n_mismatch = 0  # mismatched parens
    for i in range(len(report) // block_len):
        n_dia += 1
        gold = ''.join(report[i * block_len + block_len - 2].split()[1:])
        hypo = ''.join(report[i * block_len + block_len - 1].split()[1:])

        g = ' '.join(report[i * block_len + block_len - 2].split()[1:])
        pp = parse_p_expressions(g)
        if gold == hypo:
            n_exact += 1
        else:  # expressions differ - build graphs and compare
            try:
                tgold, exg = construct_graph(gold, d_context, constr_tag=OUTLINE_SIMP, no_post_check=True, no_exit=True)
                thypo, exh = construct_graph(hypo, d_context, constr_tag=OUTLINE_SIMP, no_post_check=True, no_exit=True)

                if 'Scarlet' in gold:
                    x = 1

                try:
                    diffs = tgold.compare_tree(thypo, [])
                except:
                    x = 1
                if not diffs:
                    n_equiv += 1

            except:
                n_except += 1
                if mismatched_parens(hypo):
                    n_mismatch += 1
                else:
                    x = 1
            x = 1

    logger.info(
        ' n_dialogs = %d\n n_exact   = %d \n n_equiv   = %d \n ->  %.3f (%.3f) \n\n n_except=%d \n n_mismatch=%d ',
        n_dia, n_exact, n_equiv, 1.0 * n_exact / n_dia, 1.0 * (n_exact + n_equiv) / n_dia, n_except, n_mismatch)


if __name__ == "__main__":
    try:
        config_log('DEBUG')
        compare_trees(working_dir)
    except:
        pass
    finally:
        logging.shutdown()
