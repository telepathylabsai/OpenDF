"""
Construct the dialog graph from the S-expression.
"""
from opendf.exceptions.python_exception import SemanticException, UnknownNodeTypeException

from opendf.graph.node_factory import NodeFactory
import re
from opendf.defs import *
from opendf.utils.utils import cast_str_val, get_type_and_clevel
from opendf.defs import is_pos, posname, posname_idx
from opendf.exceptions import re_raise_exc
from opendf.parser.pexp_parser import parse_p_expressions, ASTNode
from opendf.graph.dialog_context import DialogContext

# Intentionally does not formally depend on Node

logger = logging.getLogger(__name__)

node_fact = NodeFactory.get_instance()


# TODO - after moving to new construct code
#   new syntax description + handle special features!
#   the new construct has a new syntax for special features:
#   special features are surrounded by angled brackets. still to define the syntax inside the brackets -
#           we could have a simple mapping from single chars to a feature, or allow e.g. multi char feature
#           names separated by a delimiter...

# extra syntax:
# sugared get -       :arg(...)
# assign name -       {xx} - assigns name 'xx' to following node. {xx} - assigns name 'xx' to RESULT of following node.
# use assigned name:  $xx
# numbered node       $#17
# tags                ^xxx / ^xxx=3
# auto value type     #John / #12 / #Yes
# eval_res            '!' :  ...=func!
# block_res           '|':  if res is evaluated and an error is thrown, then stop evaluation of consuming parent
# INP/REF intension   '@' :  prm=func@      use the node itself (not the result) as the value for this input
# INP/REF extension   '~' :  prm=func~      use the result of this node as the value for this input
# OBJ intension       '<':  mark constraint as applying to candidate node itself
# OBJ extension       '>':  mark constraint as applying to candidate's result
# hide node           '/':  name=Node/(...)  - exclude this node (and its subgraph) from searches
# mutable node        '&':  Mem& - make this node mutable
# explicit type / out type:  SET(...) / refer(...)
# node.inputs['aka']
# FN(fname=..., farg=...)
# continuation turn:  '||' (CONT_TURN)  in the beginning of the sexp (this gets stripped already before getting to construct)


def construct_graph(sexp, d_context, register=True, top_only=False, constr_tag=RES_COLOR_TAG, no_post_check=False,
                    no_exit=False):
    """
    Constructs a graph from user input sexp.

    If something is wrong with the input sexp, it means the natural language module got something wrong,
    it is not something that can be negotiated with the user. So, for now, we simply discard the new goal,
    do not add it to the dialog context, and the nodes hanging from it will be unreachable.

    Note: we do not add goals to dialog context here, for now.

    :param sexp: the S-expression
    :type sexp: str
    :type register: bool  # TODO - do we really need register=False???
    :type top_only: bool
    :param no_post_check: if `True`, don't perform post construction test
    :type no_post_check: bool
    :return: new goal, if valid, else `None`; and exception or `None`
    :rtype: Tuple[Optional["Node"], Optional[Exception]]
    """
    if d_context and d_context.supress_exceptions:
        no_exit = True

    root = None
    if sexp.startswith('$#'):  # if sexp is a link to an existing node, just return it, don't construct
        # todo - same for '$name'
        ss = re.sub('[)(]', '', sexp[2:])
        if ss.isnumeric() and d_context.get_node(int(ss)):
            return d_context.get_node(int(ss)), None
        if ')' in sexp:  # syntax fix: "$#17" --> "$#17()"
            sexp += '()'

    logger.debug('::::::: ' + sexp)

    d_context = d_context if d_context or register == False else DialogContext()
    try:
        prs = parse_p_expressions(sexp)
        root = ast_top_down_construct(prs[0], None, d_context, register=register, top_only=top_only,
                                      constr_tag=constr_tag)
    except Exception as ex:
        if no_exit:  # do not exit on exception (force continue even if failed)
            raise ex
        re_raise_exc(ex)

    if no_post_check:
        return root, None

    try:
        # TODO: bottom up infer out type
        check_constr_graph(root)
        return root, None
    except Exception as ex:  # do NOT add new goal to graph -> so can't add the exception!
        if no_exit:  # do not exit on exception (force continue even if failed)
            raise ex
        try:
            re_raise_exc(ex)
        except Exception as ex:
            logger.warning(ex)
            return None, ex


# or cast to float/int and check for error
def string_is_number(s):
    for i, c in enumerate(s):
        if c == '-' and i != 0:
            return False
        if c not in '1234567890.':
            return False
    if s.count('.') > 1:
        return False
    return True


def str_to_type(val):
    """
    Infers type directly from the given string.
    """
    if len(val) > 1 and val[0] == '#':
        val = val[1:]
    if string_is_number(val):
        if '.' in val:
            return 'Float'
        return 'Int'
    if val.lower() in ['true', 'false', 'yes', 'no']:
        return 'Bool'
    return 'Str'


# this version of construct converts a tree (AST), where all nodes are of type ASTNode, to a tree with custom DF nodes
# ast is the current ASTNode
# parent is the parent DF Node

# rearrange AST tree to allow "sugared get": e.g.  ":name(func(...))" --> "getattr(name, func(...))"
def ast_handle_sugar(ast):
    if ast.name and ast.name[0] == ':':
        if len(ast.inputs) != 1:
            raise SemanticException('Error - sugar get syntax - needs exactly one input')
        nm, p2 = ast.inputs[0]
        g = ASTNode(name='getattr', parent=ast.parent, role=ast.role)
        p1 = ASTNode(name=ast.name[1:], parent=g, role=posname(1), is_terminal=True,
                     set_assign=ast.set_assign, special_features=ast.special_features)
        p2.parent = g
        p2.role = posname(2)
        g.inputs = [(posname(1), p1), (posname(2), p2)]
        return g
    return ast


# handle "special" constructs in the original SMCalFlow:
# let: the original expression is converted into a tree: let( x0(v0, x1(), v1, x2(), v2), mainExp)
#      fix this to be: let( SET ( setx0(v0), setx1(v1), setx2(v2) ), mainExp )
def ast_handle_simplify(ast):
    if ast.name == 'let':
        if len(ast.inputs) != 2:
            raise SemanticException('Bad "let" expression %s' % ast)
        _, xinp = ast.inputs[0]
        if xinp.name[0] != 'x':
            raise SemanticException('Bad "let" expression %s' % ast)
        if len(xinp.inputs) == 1:
            xinp.name = 'set' + xinp.name
            return ast
        inps = []
        a = ASTNode('SET', parent=ast)
        x = ASTNode(xinp.name)
        xinps = [x] + [i for (_, i) in xinp.inputs]
        for i, inp in enumerate(xinps):
            if i % 2 == 0:
                if inp.name[0] != 'x' or (i > 0 and inp.inputs and len(inp.inputs) > 0):
                    raise SemanticException('Bad "let" expression %s' % ast)
                inp.parent = a
                inp.name = 'set' + inp.name
                nxinp = xinps[i + 1]
                inp.inputs = [(None, nxinp)]
                nxinp.parent = inp
                inps.append((None, inp))
        a.inputs = inps
        ast.inputs[0] = (None, a)
        return ast
    elif ast.name.startswith('List_') and ast.inputs and len(ast.inputs) == 1 and ast.inputs[0][1].name == '_':
        a = ASTNode(name=ast.name[5:] + '?', parent=ast)
        ast.inputs = [(None, a)]
        ast.name = 'List'
        return ast
    return ast


def ast_top_down_construct(ast, parent, d_context, register=True, top_only=False, constr_tag=None):
    if ast.parent is None and ast.is_terminal:
        raise SemanticException('Bad program - root is terminal')

    ast = ast_handle_sugar(ast)
    ast = ast_handle_simplify(ast)

    logger.debug(ast.name)
    typ, _ = get_type_and_clevel(ast.name)
    ptyp = parent.typename() if parent else None

    if ast.is_assign:
        if not d_context:
            raise SemanticException('Context error - trying to use assign without context')
        n = d_context.get_node(ast.name)
    elif ast.is_terminal:
        # four cases for terminal - depends on the context this terminal ast (with value X) appears in:
        # 1. Int(X) - parent base type is already existing - just fill the data in the parent
        # 2. NumberAM(X) - need to create a parent base type (Int) node, and fill its data with X
        # 3. Person(firstName=X) - (where the signature for firstName is PersonName) - need to create two nodes
        #    - a leaf type node (PersonName), and a base type node (Str), and fill the data of the base node
        # 4. if none of the above, then infer the base type from the format of X, create that node, and fill it
        if ptyp in base_types:  # directly put the value into the parent's data (if compatible)
            v = cast_str_val(parent, ast.name)
            if v is None:
                raise SemanticException('"%s" is not valid data for base node %s' % (ast.name, ptyp))
            parent.data = v
            return None  # no need for further processing - no node was created
        else:  # need to add a base type Node
            tp = str_to_type(ast.name)  # default - inferring type from value format
            is_leaf = False
            if parent and ast.role and ast.role in parent.signature:
                tps = parent.signature.match_tnames(ast.role, base_types)
                if tps:
                    if tp not in tps:
                        tp = tps[0]
                else:
                    tps = parent.signature.match_tnames(ast.role, node_fact.leaf_types)
                    if tps:
                        is_leaf = True
                        if tp not in tps:
                            tp = tps[0]
                        ast.inputs.append(
                            (posname(1), ASTNode(is_terminal=True, name=ast.name, parent=ast, role=posname(1))))
            n = node_fact.gen_node(d_context, tp, register=register, constr_tag=constr_tag)
            if not is_leaf:
                n.data = cast_str_val(n, ast.name)
    else:  # not terminal
        # 1. verify known node type
        if typ not in node_fact.node_types:
            raise UnknownNodeTypeException(typ)
        smp = node_fact.sample_nodes[typ]
        # 2. fix input names (positional / aliases)
        pos = 1
        for i, (nm, nd) in enumerate(ast.inputs):
            alias = ''
            if nm is None:
                nm = posname(pos)
            # check input name is allowed
            if not smp.signature.allows_prm(nm) and not (smp.is_operator() and is_pos(nm)) and not smp.is_base_type():
                raise SemanticException('Unexpected input name %s to node %s' % (nm, typ))
            if smp.signature.is_alias(nm):
                alias = nm
                nm = smp.signature.real_name(nm)
            if is_pos(nm):  # advance auto positional name to next position
                j = posname_idx(nm)
                if j < pos:  # this can happen if explicitly gave positional name - e.g. Node(pos3=x, pos2=y)
                    if alias:
                        raise SemanticException('alias usage should respect positional order : %s.%s' % (typ, alias))
                    else:
                        raise SemanticException('Positional parameters out of order : %s.%s' % (typ, nm))
                pos = j + 1
            ast.inputs[i] = (nm, nd)
            nd.role = nm
        # create node
        n = node_fact.gen_node(d_context, ast.name, register=register, constr_tag=constr_tag)

    n.set_feats(ast_feats=ast.special_features)
    if not ast.is_assign:
        n.add_tags(constr_tag)
    n.add_tags(ast.tags)

    if ast.set_assign:
        if not d_context:
            raise SemanticException('Context error - trying to use assign without context')
        d_context.add_assign(ast.set_assign, n)
    if ast.parent is None and top_only:  # create only the top node
        return n

    if parent:
        n.connect_in_out(ast.role, parent, VIEW_INT if ast.special_features and 'I' in ast.special_features else None)
        if parent.typename() == 'Let' and ast.role == 'pos2':  # set assign indicated by 'Let'
            if not d_context:
                raise SemanticException('Context error - trying to use assign without context')
            d_context.add_assign(parent.get_dat('pos1'), n)

    for (nm, nd) in ast.inputs:
        _ = ast_top_down_construct(nd, n, d_context, register, False, constr_tag)

    if n.is_operator() and n.outypename() == 'Node' and n.copy_in_type and n.copy_in_type in n.inputs and \
            n.input_view(n.copy_in_type).outypename() != 'Node':
        n.out_type = n.input_view(n.copy_in_type).out_type

    return n


# TODO: bottom up inference for out_type!!


# TODO: non-recursive - loop on topological list
# post construction node check - DFS order
def check_constr_graph(node):
    for name in node.inputs:
        check_constr_graph(node.inputs[name])
    node.post_construct_check()
