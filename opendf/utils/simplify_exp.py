"""
Simplify expression.
"""

from opendf.utils.sexp import parse_sexp
from opendf.parser.pexp_parser import escape_string
import re

from opendf.defs import simplify_MultiWoz

func_map = {
    '?=': 'EQ',
    '==': 'EQf',
    '?<': 'LT',
    '?>': 'GT',
    '?<=': 'LE',
    '?>=': 'GE',
    '>': 'GTf',
    '+': 'Add',
    '-': 'Sub',
    'not': 'NOTf',
    'or': 'ORf',
    '>=': 'GEf',
    '<=': 'LEf',
    '<': 'LTf',
    '?~=': 'LIKE',
    # 'andConstraint': 'AND',
    # 'orConstraint': 'OR',
}



def trans_func(func, no_constr=False):
    if func.startswith('Constraint[Constraint['):
        func = re.sub('[\[\]]', ' ', func).split()[-1] + ('' if no_constr else '??')
    elif func.startswith('Constraint['):
        func = re.sub('[\[\]]', ' ', func).split()[-1] + ('' if no_constr else '?')
    if no_constr and '[' in func and len(func) > 2:
        if func[0] == '[':
            func = re.sub('[\[\]]', '', func)
        else:
            func = func.split('[')[0]
    else:
        func = re.sub('\[', '_', func)
        func = re.sub(']', '', func)
    if func in func_map:
        func = func_map[func]
    if simplify_MultiWoz:
        func = re.sub('-', '_', func)

    return func


def get_args(prs, no_constr=False):
    while isinstance(prs, list) and len(prs) == 1:
        prs = prs[0]
    org_prs = prs
    if not isinstance(prs, list):
        prs = escape_string(reduce_quotes(prs))
        prs = [prs]

    if simplify_MultiWoz and isinstance(prs, list) and len(prs)==2 and isinstance(prs[1], str) and prs[1].startswith('"') and prs[0]!= 'String':
        prs = [prs[0], '#', ['String', org_prs[1]]]

    is_leaf = False
    if prs[0] == '#':
        prs = prs[1:][0]
        is_leaf = True
    elif prs[0][0] == '#':
        prs[0] = prs[0][1:]
        is_leaf = True

    func = prs[0]
    args = {}

    pos = 1
    if len(prs) > 1:
        i = 1
        while i < len(prs):
            s = prs[i]
            if isinstance(s, str) and s[0] == ':':
                if i < len(prs) - 1 and prs[i + 1] == '#':
                    args[s[1:]] = ['#', prs[i + 2]]
                    i += 2
                else:
                    args[s[1:]] = prs[i + 1]
                    i += 1
            else:  # positional
                if s == '#' and i < len(prs) - 1:  # special case - '#' - add brackets
                    if isinstance(prs[i + 1], list) and len(prs[i + 1]) > 1:
                        args['pos%d' % pos] = ['#' + prs[i + 1][0], prs[i + 1][1:]]
                    else:
                        args['pos%d' % pos] = prs[i + 1]
                    i += 1
                    pos += 1
                else:
                    args['pos%d' % pos] = s
                    pos += 1
            i += 1
    if func[0] == ':':  # sugared get
        a1 = 'String' if no_constr else '##' + func[1:]
        args = {'pos1': a1, 'pos2': args['pos1']}
        func = 'getattr'  # should we keep it "closed"? - will be opened by construct anyway

    func = trans_func(func, no_constr)

    return func, args, is_leaf


class ExpNode:
    def __init__(self, name=None, role=None, parent=None, is_leaf=False):
        #self.name = re.sub(' ', '_', name)
        self.name = name
        self.role = role  # role is the param name which this node plays as input to its parent. Used only for printing
        self.inputs = {}
        self.parent = parent
        self.is_leaf = is_leaf  # True if input is data (corresponds to having '#' in the orig dataset)

    def __repr__(self):
        s = '%s (%s)  -->  %s' % (self.name, self.role if self.role else '?', self.parent if self.parent else '?')
        return s

    def is_data(self):
        return len(self.inputs) == 0 and ((self.parent and self.parent.is_leaf) or self.name[0] == '#')


def top_down_build_tree(prs, parent, role):
    # disable this for now - we don't handle simplification of these expressions yet TODO:
    if len(prs) == 1 and isinstance(prs[0], str) and \
            (prs[0].startswith('AlwaysTrueConstraint') or prs[0].startswith('AlwaysTrueConstraintConstraint') or
             prs[0].startswith('xAlwaysFalseConstraint') or prs[0].startswith('xAlwaysFalseConstraintConstraint') or
             prs[0].startswith('Listxx')):  # special case - '#(List[Recipient][])' ... TODO:
        s = re.sub('[\[\]]', ' ', prs[0]).split()
        if len(s) == 2:
            prs = [s[0], [s[1]]]
    func, args, is_leaf = get_args(prs)

    if parent is None:  # root
        root = ExpNode(func, is_leaf=is_leaf)
        for i in args:
            root.inputs[i] = top_down_build_tree(args[i], root, i)
        return root

    node = ExpNode(func, role, parent, is_leaf=is_leaf)
    for i in args:
        node.inputs[i] = top_down_build_tree(args[i], node, i)

    return node


def top_down_collect_prms(prs, parent, role, params, leaves):
    func, args, is_leaf = get_args(prs, no_constr=True)
    if not parent or not parent.is_leaf and '"' not in func and ' ' not in func and func[0] not in '0123456789':
        if func not in params:
            params[func] = {}
            if is_leaf:
                leaves.append(func)
        for i in args:
            if i not in params[func]:
                params[func][i] = []
        if parent and func not in params[parent.name][role]:
            params[parent.name][role].append(func)

    if parent is None:  # root
        if func != 'Yield':  # TODO: fix for LET
            return ExpNode(func), params, leaves
        root = ExpNode(func, is_leaf=is_leaf)
        for i in args:
            root.inputs[i], params, leaves = top_down_collect_prms(args[i], root, i, params, leaves)
        return root, params, leaves

    node = ExpNode(func, role, parent, is_leaf=is_leaf)
    for i in args:
        node.inputs[i], params, leaves = top_down_collect_prms(args[i], node, i, params, leaves)

    return node, params, leaves


def print_tree(node):
    t = node.name
    inps = []
    for i in node.inputs:
        j = '' if i[:3] == 'pos' else i + '='
        r = print_tree(node.inputs[i])
        inps.append(j + r)
    if inps:
        if simplify_MultiWoz and t== 'String' and len(inps)==1:
            return inps[0]
        if simplify_MultiWoz and t== 'EQ':
            return inps[0]
        return t + '(' + ', '.join(inps) + ')'
    if node.is_data():
        if t and t[0]=='#':
            t = t[1:]
        t = escape_string(reduce_quotes(t))
        return t
        #return escape_string(t)
    return t + '()'


def has_one_term(s):
    if ')' not in s:
        return False
    for i in range(s.index(')')):
        if s[i] in ' ,(:':
            return False
    return True


# indent sexp for pretty printing.
#  org_sexp - mode for indenting original-style expressions - not quite there, but good enough...
def indent_sexp(tt, org_sexp=False, sep_brack=False):
    if not tt:
        return tt
    t = re.sub('[\n\t ]+', ' ', tt)
    if not t:
        return t
    l = len(t)
    i = 0
    p = 0
    ind = 3
    s = ''
    prev_close = False
    start_param = False
    while i < l:
        c = t[i]
        if c == ')':
            p -= ind
            if sep_brack:
                s += '\n' + ' ' * p
            s += c
            prev_close = True
            start_param = False
        elif c == '(':
            if i < l - 1 and has_one_term(t[i + 1:]):
                p += ind
                s += c
            else:
                if org_sexp:
                    if prev_close:
                        s += '\n' + ' ' * p + c
                    else:
                        if i > 0 and t[i - 1] == '#':
                            s += c
                        elif start_param:
                            s += c
                        else:
                            s += '\n' + ' ' * p + c
                    p += ind
                else:
                    if prev_close:
                        s += ' ' * p
                    s += c + '\n'
                    p += ind
                    s += ' ' * p
                prev_close = False
            start_param = False
        elif c == ',':
            s += c + '\n' + ' ' * p
            prev_close = False
            start_param = False
        elif c == ':' and org_sexp:
            if i == 0 or t[i - 1] != '(':
                start_param = True
                s += '\n' + ' ' * p
            s += c
            prev_close = False
        elif c in ' \n':
            s += ' '
        else:
            if prev_close:
                s += '\n' + ' ' * p
            s += c
            prev_close = False
        i += 1
    return s


def sexp_to_tree(sexp):
    prs = parse_sexp(sexp)
    tree = top_down_build_tree(prs, None, None)
    return tree


def until_sep(s, in_quote, sep_equal=True):
    l = len(s)
    i = 0
    dlm = '"#()*,=$ \n\t'
    if in_quote:
        while i < l and (s[i] not in '"' or (i>0 and s[i-1]=='\\')):
            i += 1
    else:
        while i < l and s[i] not in dlm:
            i += 1
    if s[i] == '=' and not sep_equal:
        i += 1
    nxt = s[i]
    while i < l and nxt == ' ':
        i += 1
        nxt = s[i]
    return s[:i], nxt

def get_quote(s):
    i=1
    while i<len(s) and (s[i]!='"' or (i>0 and s[i-1]=='\\')):
        i+=1
    if s[i]=='"':
        i+=1
    return s[:i]


def reduce_quotes(s):
    done = False
    while not done:
        done = True
        if len(s)>1 and s[0]=='"' and s[-1]=='"':
            s = s[1:-1]
            done=False
        if len(s)>1 and s[0]=="'" and s[-1]=="'":
            s = s[1:-1]
            done=False
    return s

def tokenize_pexp(s, sep_equal=True):
    s += '****'
    l = len(s)
    t = ''
    i = 0
    in_quote = False
    while i < l:
        c = s[i]
        if c=='"':
            tok = get_quote(s[i:])
            i += len(tok)
            t += ' ' + escape_string(reduce_quotes(tok)) + ' '
        else:
            tok, nxt = until_sep(s[i:], in_quote, sep_equal)

            if c == '(':
                t += '( '
            elif c in ')#,$=':
                t += ' ' + c + ' '
            elif c == '*':
                pass
            elif c in ' \n\t':
                t += ' '
            elif len(tok) > 0:
                if i > 0 and nxt != '(':
                    ts = tok.split('_')
                    t += ' ' + ' '.join(ts) + ' '
                    i += len(tok) - 1
                else:
                    t += ' ' + tok
                    i += len(tok) - 1
        i += 1

    t = re.sub('  ', ' ', t)
    return t


# def tokenize_pexp0(s, sep_equal=True):
#     s += '****'
#     l = len(s)
#     t = ''
#     i = 0
#     in_quote = False
#     while i < l:
#         c = s[i]
#         tok, nxt = until_sep(s[i:], in_quote, sep_equal)
#         if c == '"':
#             t += ' " '
#             in_quote = not in_quote
#         elif in_quote:
#             ts = tok.split('_')
#             t += ' ' + ' '.join(ts) + ' '
#             i += len(tok)
#         elif c == '(':
#             t += '( '
#         elif c in ')#,$=':
#             t += ' ' + c + ' '
#         elif c == '*':
#             pass
#         elif c in ' \n\t':
#             t += ' '
#         elif len(tok) > 0:
#             if i > 0 and nxt != '(':
#                 ts = tok.split('_')
#                 t += ' ' + ' '.join(ts) + ' '
#                 i += len(tok) - 1
#             else:
#                 t += ' ' + tok
#                 i += len(tok) - 1
#         i += 1
#
#     t = re.sub('  ', ' ', t)
#     return t
