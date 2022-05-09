"""
Functions to translate user text to S-expressions.
"""

from opendf.examples.text_examples import dialogs, nlu_results
from opendf.exceptions.python_exception import EvaluationError
from opendf.graph.nlu_framework import NLU_INTENT, NLU_TREE, nlu_out, NLU
from opendf.graph.nodes.node import *
from opendf.graph.node_factory import NodeFactory
from opendf.utils.utils import parse_hint, to_list
import copy

logger = logging.getLogger(__name__)

# init type info
node_fact = NodeFactory.get_instance()

# ################################################################################################
# ################################## MS application definitions ##################################

trans_pass = {
}

default_entity_hints = {
    'confirm': '',  # confirm is disabled for default hints - it should only be used by an agent hint
}

default_intent_sexp = {
}

# intent name -> node type to translate it to sexp
intent_hints = {
    'findEvent': 'FindEvents',
}


# ################################################################################################


# ################################################################################################
# ################################################################################################


def get_user_txt(dialog_id, turn):
    if dialog_id < len(dialogs) and turn < len(dialogs[dialog_id]):
        d = dialogs[dialog_id][turn]
        return d
    return None


def print_dialog(dialog_id):
    if dialog_id < len(dialogs):
        for d in dialogs[dialog_id]:
            logger.info(d)


def get_sexp_cont(s):
    return (s[2:], True) if s.startswith(CONT_TURN) else (s, False)


def process_user_txt(txt, d_context):
    if txt in trans_pass:  # copy fixed translation
        return [trans_pass[txt]]
    # lookup table. TODO: actually call the NLU module. Potentially - pass hints to NLU
    if txt not in nlu_results:
        logger.warning('Error - can not find NLU for: "%s"', txt)
        exit(1)
    nlu = copy.deepcopy(nlu_results[txt])  # we need deep copy, since we destructively modify the NLU result

    # now, fill a list of nlu entries. Here, we fill it sorted by type, but we don't rely on that later
    nl = NLU()
    if 'intent' in nlu:
        for n in to_list(nlu['intent']):
            nm, v = n, None
            if ':' in n:
                s = n.split(':')
                nm, v = s[0], s[1:]
            nl.append(nlu_out(NLU_INTENT, nm, v))
    if 'entity' in nlu:
        for n in nlu['intent']:
            nl.append(nlu_out(NLU_SLOT, n, nlu['intent'][n]))
    if 'tree' in nlu:
        for n in to_list(nlu['intent']):
            nm = n.split('(')[0]
            nl.append(nlu_out(NLU_TREE, nm, n))

    return nlu_to_sexp(nl, d_context)


def make_prog(h, inp, d_context):
    tp, cl, opts, prog = parse_hint(h)
    if not prog:  # was already tested before being called
        raise EvaluationError('Error - hint does not have a program - %s', h)
    if '_INP' not in prog:
        raise EvaluationError('Error - program does not have _INP\n %s', prog)
    pr = re.sub('_INP', 'inp=%s' % inp, prog)
    p, ex = Node.call_construct(pr, d_context, register=False)
    if ex is not None:
        raise ex
    return p


# try to use hints to translate intent + entities.
# without hints, the default behavior is to map an entity (name, value) to a 'revise' sexp,
# where 'entity name' is converted to its default translation, and no specific type is mentioned
# i.e. if there are two types with the same input parameter, the graph will decide (by position in current graph)
# with hint, we can:
#   1. give priority to one type over another
#      - we could have the same entity name handled by different types;
#      - e.g. entity:{'attendee': 'Dan'} could be translated either to
#           Attendee(Dan), or to Event?(attendee=Attendee(Dan)).
#   2. generate a sexp different from the default revise().
# after entities (and potentially intent) are "used up", they are removed, so that we don't try to translate them
# again later


# try to translate unconsumed nlu entries using hints
# if i_nlu is given, then only try translating this specific nlu entry, else - try all
# if translation succeeded:
#   - return the translation result (sexp)
#   - mark matching nlu entry as consumed
def translate_slot_hints(nlu, hints, i_nlu=None):
    for ih, h in enumerate(hints):
        tp, cl, opts, prog = parse_hint(h)
        if tp and tp in node_fact.node_types:
            s, nlu = node_fact.sample_nodes[tp].translate_slot(nlu, hints, h, i_nlu)
            if s:
                return s, nlu
    return None, nlu


# TODO: check!  also, not sure if needed
def translate_tree_hints(nlu, hints, i_nlu=None):
    """
    Translates tree by using hints.
    """
    for ih, h in enumerate(hints):
        tp, cl, opts, prog = parse_hint(h)
        if tp and tp in node_fact.node_types:
            s, nlu = node_fact.sample_nodes[tp].translate_tree(nlu, hints, h, i_nlu)
            if s:
                return s, nlu
    return None, nlu


def add_cont(exps):
    sexps = []
    for i, s in enumerate(exps):
        e = CONT_TURN if i < len(exps) - 1 else ''
        sexps.append(e + s)
    return sexps


# convert NLU parse to sexp
# for now - simple implementation:
# - if hint/program TODO:
# - else treat everything as revise
#   - for each entity - revise(hasParam=prm, new=val, mode=mod)
#                       where prm, val, mod - are calculated from entity name & val
#   - if there is an intent, add a midResult to the FIRST entity revise
#        - if there is an intent without an entity... - (can there be?) - maybe we just do a refer+eval (to bring the
#        goal up)
# for multi sexp output - mark all but last as continuation
def nlu_to_sexp(nlu, d_context):
    sexps = []
    prev_hints = to_list(d_context.prev_agent_hints)
    logger.info('Hints: %s', prev_hints)

    # 1. translate intents
    #  consumes translated intents, and may also greedily consume related entities (slots/trees)
    for i, n in enumerate(nlu):
        if n.typ == NLU_INTENT and not n.consumed:
            if n.name in intent_hints:
                tp = intent_hints[n.name]
                if tp in node_fact.sample_nodes:
                    s, nlu = node_fact.sample_nodes[tp].translate_intent(nlu, prev_hints, tp, i)
                    if s:
                        sexps = to_list(s) + sexps  # by convention - put intent sexps first
                else:
                    raise SemanticException('Error - invalid intent hint class: %s / %s' % (n.name, tp))
            elif n.name in default_intent_sexp:
                sexps = [default_intent_sexp[n.name]] + sexps
            else:
                raise SemanticException('Error - Unknown translation for intent %s' % n.name)

    # 2. try to consume slots/trees corresponding to prev_hints
    if prev_hints:
        s = ' '
        while s and nlu.has_unconsumed(NLU_SLOT):
            s, nlu = translate_slot_hints(nlu, prev_hints)
            if s:
                sexps.extend(to_list(s))
        s = ' '
        while s and nlu.has_unconsumed(NLU_TREE):
            s, nlu = translate_tree_hints(nlu, prev_hints)
            if s:
                sexps.extend(to_list(s))

    # 3. consume leftover entities without prev hints (using default hints)
    for i, e in enumerate(nlu):
        if not e.consumed:
            if e.name in default_entity_hints:
                def_hints = [h for h in to_list(default_entity_hints[e.name])]
                logger.info('Default hints: %s', def_hints)
            else:
                def_hints = []
                logger.info('No default entity hint for %s', e.name)
            s = ' '
            if e.typ == NLU_SLOT:
                while def_hints and s:
                    s, nlu = translate_slot_hints(nlu, def_hints, i)
                    if s:
                        sexps.extend(to_list(s))
            elif e.typ == NLU_TREE:
                while def_hints and s:
                    s, nlu = translate_tree_hints(nlu, def_hints, i)
                    if s:
                        sexps.extend(to_list(s))
            if not nlu[i].consumed:
                logger.info('>>>>>> Could not translate nlu entry %s - omitting it from Sexp translation!', e)

    return add_cont(sexps)
