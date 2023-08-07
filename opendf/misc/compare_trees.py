"""
compare results of translation to ground truth - tree comparison
"""
import logging
import sys
import traceback

from opendf.defs import config_log
from opendf.parser.pexp_parser import parse_p_expressions

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


def compare_trees(input_path):
    report = [l.strip() for l in open(input_path, 'r').readlines()]
    block_len = 9  # report block for one turn
    n_dia = 0
    n_exact = 0
    n_equiv = 0
    n_except = 0
    n_mismatch = 0  # mismatched parens
    for i in range(len(report) // block_len):
        block = report[i*block_len: (i+1)*block_len]
        n_dia += 1
        gold = report[i * block_len + block_len - 2].split(maxsplit=1)[-1]
        hypo = report[i * block_len + block_len - 1].split(maxsplit=1)[-1]

        if gold == hypo:
            n_exact += 1
        else:  # expressions differ - build graphs and compare
            try:
                ast1 = parse_p_expressions(gold)
                ast2 = parse_p_expressions(hypo)
                equivalent = ast1 == ast2
                if equivalent:
                    n_equiv += 1

            except Exception as ex:
                n_except += 1
                if mismatched_parens(hypo):
                    n_mismatch += 1

    logger.info(f"n_dialogs = {n_dia}")
    logger.info(f"n_exact   = {n_exact}")
    logger.info(f"n_equiv   = {n_equiv}")
    logger.info(f" ->  {1.0 * n_exact / n_dia:.5f} ({1.0 * (n_exact + n_equiv) / n_dia:.5f})")
    logger.info("")
    logger.info(f"n_except={n_except}")
    logger.info(f"n_mismatch={n_mismatch}")


if __name__ == "__main__":
    try:
        config_log('DEBUG')
        if len(sys.argv) < 2:
            raise Exception("No input file!")
        for path in sys.argv[1:]:
            logger.info(path)
            compare_trees(path)
    except:
        traceback.print_exc()
    finally:
        logging.shutdown()
