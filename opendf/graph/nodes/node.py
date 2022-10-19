import re
from typing import Tuple, Any, Optional, List

from opendf.exceptions.debug_exception import DebugDFException
from opendf.exceptions.df_exception import ElementNotFoundException
from opendf.graph.dialog_context import DialogContext
from opendf.graph.nlu_framework import NLU_TYPE
from opendf.graph.node_factory import NodeFactory
from opendf.utils.utils import compatible_clevel, parse_hint, to_list, id_sexp, \
    is_assign_name, strings_similar, flatten_list
from opendf.exceptions import re_raise_exc
from opendf.graph.signature import *
from opendf.defs import *
from opendf.parser.pexp_parser import escape_string
from opendf.exceptions.python_exception import SemanticException
from opendf.exceptions.df_exception import NoPropertyException, MissingValueException, NotImplementedYetDFException
from collections import defaultdict

node_fact = NodeFactory.get_instance()
environment_definitions = EnvironmentDefinition.get_instance()

logger = logging.getLogger(__name__)


class Node:
    """
    This is the base class for the different objects and functions. Node holds the logic of the graph - it keeps track
    of input, output and result links. It may hold data (only for base type nodes), some additional memory, and
    features which control the way the nodes behave and use other others.
    """

    def __init__(self, out_type=None):
        self.id = None
        self.signature = Signature()  # definitions of input parameters - {name : InputParam}
        self.inputs = AliasODict()  # inputs PRESENT in the graph - {name : node}
        # using OrderedDict - so that evaluation goes in left-to-right order (relative to construction order)
        # inputs (also outputs, view_mode) use the "real" name - not aliases

        self.view_mode = {}  # per input - which value to use - the input itself or its result
        self.out_type = Node if out_type is None else out_type
        # for type-node will be that type, for function could be any type

        self.copy_in_type = None
        # `True` for dynamic type where out type is same as in type - in that case - give NAME of input not used anymore

        self.evaluated = False  # `True` after a successful (i.e. no exception) eval of the node.
        # A node marked as evaluated will not be evaluated again.

        self.result = self  # pointer to result node (self if constructor)
        self.outputs = []  # which nodes use this node as input, and the name of the input - list of (name, node).
        # As graph grows, node may be used several times, possibly with the same input name

        self.tags = {}  # additional memory. Tags can be associated with special behavior / common traits...
        # non-tag info (i.e. fields of Node) need specific syntax to be able to set them.
        # tags don't - that's why new tags can be added without code change in the base system
        # tags with '*' are required, tags with TAG_NO_COPY are not copied, tags with TAG_NO_SHOW are not displayed,
        # tags with TAG_NO_MATCH are not matched

        self.type_tags = []  # names of tags which are created per type (in __init__) (i.e. not added per node instance)

        self.res_out = []  # pointers to nodes this node is a direct result of
        self.check_node = True  # allows turning off formal (general) tests for nodes with variable inputs.
        # TODO: still needed?

        self.data = None  # only for base types (Int, Str, Float, Bool)

        # for constraints
        self.constraint_level = 0  # 0: real object, 1: query for real object, 2: query for query for real object...
        self.constr_obj_view = VIEW.EXT  # when matching a constraint - match constraint to object's specified view

        # these are not tags, because they directly involve code in the base system (and have syntax to set them)
        self.eval_res = False  # in case we want to explicitly require evaluation of result - not done yet!
        self.res_block = False  # error in result evaluation blocks further evaluation
        self.mutable = False  # mutable nodes are not duplicated during revise - there is one copy
        self.hide = False  # exclude this node (and its subgraph) from searches
        self.no_revise = False  # don't consider this node for revise candidate
        self.add_goal = None  # add this node to goals - as either int/ext
        self.stop_eval_on_exception = False  # do not evaluate further sibling inputs if failed on an input
        self.detach = False  # this node will be detached from input and replaced by its result, once result created
        self.detached_nodes = []  # not used anymore
        # list of (nm, nd) - nodes which used to be inputs, but got detached. Used only for drawing

        self.just_dup = False
        # flags node as being duplicated - should be on ONLY during the duplication process i.e. turned on and off
        #   inside the duplication.

        self.dup_of = None  # if node is duplicated, point to node it's a duplicate of
        self.inited = False  # for nodes which need to do something different the first time they appear
        self.created_turn = None
        # remember which turn the node was created - may be useful for scoring by age. Just finding ancestor goal_id
        #   may not be enough
        self.inp_reason = {}  # (text, optional) explain to user why this input is needed (keys - same as for 'input')
        self.reason = ''
        # (text, optional) explain to user why this node is needed. This explanation is independent of where the
        # node is used

        self.context: Optional[DialogContext] = None
        # link to the dialog context this node is part of (avoid need to pass d_context everywhere)

        self.counters = {'dup': 1}
        self.obj_name_singular = self.typename()
        self.obj_name_plural = self.typename() + 's'
        self.pack_counters = None  # a list of counters to pack (when packing context)

    # #############################################################################################
    # ##################### some simple functions with self explanatory names #####################

    def is_base_type(self):
        """
        `self` is one of the base types [Int, Str, Float, Bool], the only types which can have actual data.
        """
        return self.typename() in base_types

    def is_operator(self):
        return self.typename() in node_fact.operators

    def not_operator(self):
        # too lazy to write `not self.is_operator()`
        return self.typename() not in node_fact.operators

    def is_aggregator(self):
        return self.typename() in node_fact.aggregators

    def is_qualifier(self):
        return self.typename() in node_fact.qualifiers

    def is_modifier(self):
        return self.typename() in node_fact.modifiers

    # #############################################################################################

    # access to self.view_mode, with wrapper for parameter aliases
    # TODO: move all use of self.view_mode[x] to self.get_view_mde(x)

    def get_view_mode(self, nm):
        if nm in self.view_mode:
            return self.view_mode[nm]
        if nm in self.signature.aliases:
            return self.view_mode[self.signature.real_name(nm)]
        return self.view_mode[nm]  # will raise exception

    # shorthand
    def real_name(self, nm):
        return self.signature.real_name(nm)

    #############################################################################################

    def get_result_trans(self):
        """
        Gets the result by following result pointers until result points to itself.
        """
        if self.result is None:  # should not happen
            return None  # TODO: or return self?
        if self.result == self:
            return self
        return self.result.get_result_trans()

    def get_all_res_nodes(self, nodes=None):
        nodes = nodes if nodes else []
        if self in nodes:
            return nodes
        nodes += [self]
        return self.result.get_all_res_nodes(nodes)

    @property
    def res(self):
        return self.get_result_trans()

    def show(self, with_id=False):
        from opendf.utils.simplify_exp import indent_sexp
        return indent_sexp(self.print_tree(None, ind=None, with_id=with_id, with_pos=False,
                                           trim_leaf=True, trim_sugar=True, mark_val=True)[0])

    # get string describing one path from node up
    def show_up(self, with_id=True):
        s = '' if self.dat is None else str(self.dat)
        if with_id and self.id is not None:
            s = '[' + str(self.id) + ']-' + s
        n = self
        while n is not None:
            s = s + n.typename()
            if len(n.outputs) > 0:
                nm, nd = n.outputs[0]
                s = s + ':%s->' % nm
                if with_id and nd.id is not None:
                    s += '[%d]' % nd.id
                n = nd
            else:
                n = None
        return s

    # print node and path up
    def __repr__(self):
        if environment_definitions.repr_down:
            from opendf.utils.simplify_exp import indent_sexp
            return indent_sexp(self.print_tree(None, ind=None, with_id=True, with_pos=False,
                                               trim_leaf=True, trim_sugar=True, mark_val=True)[0])
        else:
            return self.show_up()

    def get_leaf_data(self):
        """
        Gets data if self is a base node, or leaf node with a base node, else, return `None`. Does not look at
        result, only base types (Int, Str, Float, Bool) actually hold data.

        `Leaf types`, although not actually holding data, are considered as holding data if they have an input base
        node.

        Note: for now, not checking for constraint level - so will also get data from constraint. Since the input to
        a leaf node is a base type, no need to check view mode.
        """
        if self.data is not None:
            return self.data
        if self.typename() in node_fact.leaf_types:  #
            if len(self.inputs) == 1:  # if data actually there
                k = list(self.inputs.keys())[0]
                return self.inputs[k].res.data
        return None

    @property
    def dat(self):
        """
        Shorthand for `self.get_leaf_data()`.
        """
        return self.get_leaf_data()

    def get_dat(self, inp):
        """
        Gets the data for the selected view of the named input.
        """
        if inp not in self.inputs:
            # TODO: check for property? (as short-hand)
            return None
        if self.get_view_mode(inp) == VIEW.INT:
            return self.inputs[inp].dat
        else:
            return self.inputs[inp].res.dat

    def get_dats(self, inp):
        inp = to_list(inp)
        dats = [self.get_dat(i) for i in inp]
        return dats[-1] if len(dats) == 1 else None if len(dats) == 0 else tuple(dats)

    def get_ext_view(self, txt):
        """
        Follows input_view with multistep traverse. Returns `None` if missing inputs:
            e.g. `n.get_ext_view('aaa.bbb.ccc') == self.input_view('aaa').input_view('bbb').input_view('ccc')`
        """
        t = txt.split('.')
        if len(t) < 1:
            return None
        n = self
        for i in t:
            if i not in n.inputs:
                return None
            n = n.input_view(i)
        return n

    def get_input_path_by_name(self, txt, return_part=False):
        """
        Follows inputs with multistep traverse. Returns `None` if missing inputs, else all nodes along the chain.
        """
        inps = []
        t = txt.split('.')
        if len(t) < 1:
            return None
        n = self
        for i in t:
            if i not in n.inputs:
                return inps if return_part else None
            n = n.inputs[i]
            inps.append(n)
        return inps

    def get_input_path_by_type(self, txt, return_part=False):
        """
        Checks if node has an input path consisting of the given node types (linear chain, no splits allowed).
        Returns `None` if not, else returns both the nodes in the chain, as well as their input names.
        """
        # if path is not unique, will arbitrarily choose one!
        inps, names = [], []
        t = txt.split('.')
        if len(t) < 1:
            return None, None
        n = self
        for i in t:
            nm = [j for j in n.inputs if n.inputs[j].typename() == i]
            if not nm:
                return (inps, names) if return_part else (None, None)
            n = n.inputs[nm[0]]
            inps.append(n)
            names.append(nm[0])
        return inps, names

    def do_get_path(self, steps, path, names, return_part=False):
        if not steps:
            return path, names, True
        i = steps[0]
        if i[0] == ':':
            ii = i[1:]
            nm = [j for j in self.inputs if self.inputs[j].typename() == ii]
        else:
            nm = [i] if i in self.inputs else []
        if not nm:
            return (path, names, False) if return_part else (None, None, False)
        for n in nm:
            pp, nn, ok = self.inputs[n].do_get_path(steps[1:], path, names, return_part)
            if ok:
                return [self.inputs[n]] + pp, [n] + nn, True
        return path, names, False

    # gets path nodes+input names - like get_input_path_by_type/name.
    # format: e.g. txt = 'aa.:bb.cc' - the ':' indicates bb is a type name, while aa, cc are input names
    def get_input_path(self, txt, return_part=False):
        """
        Checks if node has an input path consisting of the given node names/types. ':' specifies type.
        """
        # if path is not unique, will arbitrarily choose one!
        t = txt.split('.')
        if len(t) < 1:
            return None, None
        path, names, ok = self.do_get_path(t, [], [], return_part)
        return path, names

    # shorthand function to get data with multiple input VIEW steps
    # e.g. n.txt_view_dat('aaa.bbb.ccc')  is equivalent to n.input_view('aaa').input_view('bbb').get_dat('ccc')
    def get_ext_dat(self, txt):
        """
        `get_dat` with multistep traverse, using selected views. Returns `None` if no data available, or missing inputs
        e.g. `n.get_ext_dat('aaa.bbb.ccc')  ==  n.input_view('aaa').input_view('bbb').get_dat('ccc')`.
        """
        t = txt.split('.')
        if len(t) < 1:
            return None
        n = self
        for i in t:
            if i not in n.inputs:
                return None
            n = n.inputs[i] if n.get_view_mode(i) == VIEW.INT else n.inputs[i].res
        return n.dat

    # get a printable string - like get_dat, but adds op
    def simple_desc(self, inp):
        """
        Gets a simplified printable string representing node.
        """
        if inp not in self.inputs:
            return ''
        n = self.input_view(inp)
        tp = n.typename()
        s = n.dat
        c = '?' if n.constraint_level > 0 else ''
        if s is not None:
            s = '%s' % s
            return s + c

        if n.is_operator():
            if posname(1) in n.inputs and posname(2) not in n.inputs:
                s = n.get_dat(posname(1))
                if s is not None:
                    s = '%s' % s
                    if tp in ['NOT', 'NEQ', 'LIKE', 'NONE']:
                        s = tp + '(' + s + ')'
                    return s + c
        return c

    # get the input node corresponding to that input's int/ext mode
    def input_view(self, inp):
        """
        Gets the selected view of the named input.

        :rtype: Node
        """
        if inp not in self.inputs:
            return None
        if self.get_view_mode(inp) == VIEW.INT:
            return self.inputs[inp]
        else:
            return self.inputs[inp].res

    def get_inp_view_and_mode(self, inp, unroll_set=False) -> Tuple["Node", Any]:
        """
        Gets a named input and its view mode. If SET - unroll and get just one.
        """
        if inp not in self.inputs:
            return None, None
        view = self.get_view_mode(inp)
        nd = self.input_view(inp)
        if unroll_set:
            while nd.typename() == 'SET':
                view = nd.view_mode[posname(1)]
                nd = nd.input_view(posname(1))
        return nd, view

    # called if an exception was raised in or under inputs.
    # some nodes allow evaluation to resume even if exceptions happened under them.
    # This depends on the node / exception  (see eval.recursive_eval)
    def allows_exception(self, e):
        """How should evaluation proceed when there was an exception in inputs?   Returns:
        1. should the node be evaluated despite exception?
        2. original or follow-up exception."""
        return False, e

    # base implementation.
    # overriding will allow a node to rearrange the exceptions (or remove all/some)...
    def do_add_exception(self, e, exs):
        self.context.add_exception(e)
        exs.append(e)
        return exs

    # TODO: should we check signature to make sure this is a legal input name?
    def add_linked_input(self, nm, nd, view=VIEW.EXT):
        """
        Sets input, view_mode for input, and output link.

        Adds nd` to inputs (under key 'nm') and add self to the outputs of `nd`.
        Note: this assumes the input does not exist yet! if it exists - use `replace_input`.
        """
        nm = self.real_name(nm)
        self.inputs[nm] = nd
        self.view_mode[nm] = view
        nd.add_output(nm, self)

    # add input and output links needed to add self as input[name] of parent
    def connect_in_out(self, name, parent, view=None, force=False):
        """
        Adds input and output links needed to add `self` as `input[name]` of `parent`.
        """
        name = parent.real_name(name)
        if not force and name in parent.inputs:
            raise DebugDFException('sexp inputs of %s already have %s' % (parent, name), parent)
        self.add_output(name, parent)
        parent.inputs[name] = self
        if view is None:
            view = VIEW.EXT if parent.is_operator() or name not in parent.signature else parent.signature[name].view
        parent.view_mode[name] = view

    def replace_input(self, nm, new_node, view=None):
        nm = self.real_name(nm)
        if nm in self.inputs:
            if self.inputs[nm] == new_node:  # trying to replace with the same node
                if view and self.view_mode[nm] != view:
                    self.view_mode[nm] = view
                return
            old = self.inputs[nm]
            old.outputs = [(m, d) for (m, d) in old.outputs if m != nm or d != self]
            self.inputs.pop(nm)
        new_node.connect_in_out(nm, self, view)

    def add_output(self, nm, parent):
        nm = parent.real_name(nm)
        if (nm, parent) not in self.outputs:
            self.outputs.append((nm, parent))

    def set_result(self, n):
        """
        Sets `self.result`, and update `res_out` link list of `result`.
        """
        res = self.result
        if n != res:  # change
            rs = n.get_all_res_nodes()
            if self in rs:  # do not set result if this will create a result loop (should we throw an exception?)
                return
            if res != self:  # remove self from res' list of out_res links
                res.res_out = [r for r in res.res_out if r != self]
            self.result = n
            if n != self:  # add self to n's list of out_res links (unless n==self)
                n.res_out.append(self)
        self.out_type = self.res.get_op_type(no=Node)  # TODO: check no bad effects!

    # ast flag - use AST stype features
    def set_feats(self, nfeats=None, ast_feats=None, context=None, register=None):
        if ast_feats is not None:
            for f in ast_feats.split(','):
                if f in ['!', 'evres']:
                    self.eval_res = True
                elif f in ['|', 'resblk']:
                    self.res_block = True
                elif f in ['&', 'mut']:
                    self.mutable = True
                elif f in ['norev']:
                    self.no_revise = True
                elif f in ['stpev']:
                    self.stop_eval_on_exception = True
                elif f[0] == '#' and context:  # <#17.3> means set this node's id to 17, and set the created turn to 3
                    s = f[1:].split('.')
                    nm, trn = (int(s[0]), int(s[1])) if len(s)>1 else (int(s[0]), None)
                    if register:
                        context.register_node(self, renumber=nm)
                    if trn is not None:
                        self.created_turn = trn
                elif f.startswith('E:'):
                    self.set_extra_attr(f[2:])
                elif f=='*':
                    self.evaluated = True
                    self.result = self

    # used e.g. in compr_tree, when we want to make a string representation of the graph
    #  this should include all node fields which are NOT set by default (assignment in base Node, or in the derived
    #    node's __init__) or by the construction. (excluding result!)
    #  (some are not covered yet, since not needed (?))
    def get_feat_str(self):
        feats = []
        if self.id is not None:
            feats.append('#%d.%d' % (self.id, self.created_turn))
        if self.mutable:
            feats.append('&')
        if self.eval_res:
            feats.append('!')
        if self.res_block:
            feats.append('|')
        if self.no_revise:
            feats.append('norev')
        if self.stop_eval_on_exception:
            feats.append('stpev')
        s = self.get_extra_attr_str()
        if s:
            feats.append('E:'+s)
        if self.evaluated:
            feats.append('*')
        return','.join(feats)

    # get counter names from counters starting with 'max_'
    def get_counters_from_max(self):
        return [c[4:] for c in self.counters if c.startswith('max_')]

    def counters_to_str(self):
        if not self.pack_counters:
            return ''
        c = [str(self.counters[i]) if i in self.counters else '0' for i in self.pack_counters]
        return ':'.join(c)

    def str_to_counters(self, s, cnts=None):
        if s and (self.pack_counters or cnts):
            vs = s.split(':')
            cnts = cnts if cnts else self.pack_counters
            for c, v in zip(cnts, vs):
                self.counters[c] = int(v)

    # base class - do nothing
    def get_extra_attr_str(self):
        if self.pack_counters:
            return self.counters_to_str()
        return ''

    def set_extra_attr(self, attr_str):
        if attr_str and self.pack_counters:
            self.str_to_counters(attr_str)

    # get counter names from counters starting with 'max_'
    def get_counters_from_max(self):
        return [c[4:] for c in self.counters if c.startswith('max_')]

    def detach_node(self):
        """
        Detaches a node and replaces it by its result.
        """
        if self != self.result:
            res = self.res  # .result?
            for (nm, nd) in self.outputs:
                nd.inputs[nm] = res  # what about nd.view_mode?
                res.add_output(nm, nd)
                nd.detached_nodes.append((nm, self))
            self.outputs = []  # this node is not used as input anymore

    def disconnect_node_from_parents(self):
        """
        Removes itself from the input of all its parent.
        """
        self.replace_node_on_parents()

    def replace_node_on_parents(self, replacement=None):
        """
        Removes itself from the input of all its parent and replaces it (in the parents) by `replacement`, if given.

        :param replacement: the replacement
        :type replacement: Node or None
        """
        for name, node in self.outputs:
            node.disconnect_input(name)
            if replacement is not None:
                replacement.connect_in_out(name, node)

    # tags is a general memory mechanism for nodes.
    # tags can have a value (all values are strings!), or have an empty value ('').
    # They can be used for any kind of storage/labeling/search, but there are some special cases:
    # - for tagging a set of node types as belonging to a group
    # - for labeling a node as having special behavior - this could be general behavior (base class) or per type
    #   example - 'Mut' - mutable
    #           TODO:  maybe (in future) automatically connecting a specific shared memory...?
    # for search, default behavior is that when constraint mentions a tag, the search will try to match it,
    #   but when not mentioning it, we ignore it. If constraint mentions the value of the tag, it must match,
    #   otherwise we just care the tag exists.
    #   - special case: when tag name includes '*', then we require exact match even if not mentioned in constraint
    # `beg_tags` just holds the tags which are automatic for the type (i.e. created at the __init__)
    # - so we know not to draw them for constraint nodes (avoid clutter)
    def add_type_tags(self, key, val=''):
        self.tags[key] = val
        if key not in self.type_tags:
            self.type_tags.append(key)

    def add_tags(self, tags):
        if tags:
            if isinstance(tags, dict):
                self.tags.update(tags)
            else:
                for t in to_list(tags):
                    if isinstance(t, tuple):
                        k,v = t
                        if k is not None:
                            self.tags[k] = v
                        else:   # TODO - fix this - parsing of tags with no values
                            self.tags[v] = ''
                    else:
                        self.tags[t] = ''

    def get_tags_str(self, no_deco=True):
        tags = []
        for t in self.tags:
            if not no_deco or (TAG_NO_NO_NO not in t and 'db_node' not in t):
                if self.tags[t]!='':
                    tags.append('^%s=%s' % (t, self.tags[t]))
                else:
                    tags.append('^%s' % t)
        return ','.join(tags)

    # post graph construction (i.e. after all nodes were constructed) sanity check
    # TODO: is this post construction OR pre evaluation? (could be considered a part of either?)
    def post_construct_check(self):
        """
        Checks if the given inputs are the right parameter names and right types. If there is a problem with the
        natural language function, then the given program might be wrong. This is not something that can be fixed by
        negotiating with the user. This check can be done at the NLP side, but the logic is here.
        """
        if self.check_node:
            for nm in self.inputs:
                inp = self.inputs[nm]  # there are no results yet (?), so no need for view (?)
                if self.is_operator() and is_pos(nm):
                    if inp.outypename() != 'Node' and self.outypename() != 'Node' and inp.out_type != self.out_type:
                        logger.debug('Warning - type mismatch for operator input  %s / %s', self, inp.outypename())

                if nm in ['_aka', '_out_type']:
                    if inp.outypename() != 'Str':
                        raise SemanticException(
                            'ConstructError - input "_aka/_out_type" need an input of type Str  %s / %s' % (
                                self, inp.outypename()))
                elif nm in ['fname', 'farg'] and self.typename() == 'FN':
                    if nm == 'fname' and inp.outypename() != 'Str':
                        raise SemanticException('ConstructError - input "fname" needs an input of type Str  %s / %s' % (
                            self, inp.outypename()))  # TODO: check for okarg
                elif self.typename() != 'Node':  # for 'Any' - don't check signature
                    if nm in self.signature and self.signature[nm].prop:  # get property - should not be set
                        logger.debug('Property set : %s.%s', self.typename(), nm)  # reminder - needs to be converted!
                        # for now, property is constructed as normal input, and converted "later" (e.g. valid_input)
                        # we may want to add HERE a call to a function to convert property inputs
                        # (or do this in construct?)
                    if not self.signature.allows_prm(nm) and not (self.is_operator() and is_pos(nm)):
                        raise SemanticException(
                            'ConstructError - Unexpected param - %s - to  %s' % (nm, self.typename()))
                    if nm in self.signature and not self.signature[nm].match_types([inp.out_type, Node]):
                        if inp.out_type != Node:  # don't complain about dynamic type - check!
                            raise SemanticException('ConstructError - Unexpected param type - %s/%s' %
                                                    (nm, self.signature[nm].type_name()))

    def is_strict_pos(self, nm):
        return is_pos(nm) and not self.signature.has_alias(nm)

    def valid_input(self):
        pass  # default: nothing specific for this class

    def valid_constraint(self):
        pass

    def get_missing_value(self, nm, as_node=True):
        """
        Gets value for some missing inputs which have default values - base functions to override. This function is
        called after we verified the specified input is missing.

        If `as_node` it `True`, this input will be created, and the value returned in the created node.
        """
        return None

    def get_property(self, nm):
        """
        Gets property value.
        """
        raise NoPropertyException(
            '%s %s does not have property %s' % (self.obj_name_singular, self.describe(), nm), self)

    # General checks:
    #  - give general message for missing inputs (which were not handled by custom)
    #  - collect implicit parameters

    def remove_out_link(self, nm, nd):
        """
        Removes output link from node.
        """
        nm = nd.real_name(nm)
        o = [(m, d) for (m, d) in self.outputs if d != nd or m != nm]
        self.outputs = o

    def del_input(self, nm):
        if nm in self.inputs:
            del self.inputs[nm]
        if nm in self.view_mode:
            del self.view_mode[nm]
        # TODO: handle output nodes as well?

    def disconnect_input(self, nm):
        """
        Disconnects input with a given name, if name exists; else, does nothing.
        """
        nm = self.real_name(nm)
        if nm in self.inputs:
            nd = self.inputs[nm]
            del self.inputs[nm]
            if nm in self.view_mode:
                del self.view_mode[nm]
            nd.outputs = [(m, n) for (m, n) in nd.outputs if m != nm or n != self]

    def disconnect_input_nodes(self, nds):
        """
        Disconnects input with a set of nodes, if they are inputs; else, does nothing.
        """
        nms = list(self.inputs.keys())
        for nm in nms:
            inp = self.inputs[nm]
            if inp in nds:
                self.disconnect_input(nm)

    def disconnect_input_nodes_recursively(self, node):
        """
        Disconnects input with a set of nodes, recursively for each node under self, if exists.
        """
        for nm, inp in self.inputs.items():
            if inp.id == node.id:
                self.disconnect_input(nm)
            else:
                inp.disconnect_input_nodes_recursively(node)

    # #############################################################################################
    # ###################################### Match functions ######################################

    # we implement explicitly just func_LT and func_EQ, and the rest of the qualifiers are, by default, defined
    #    in terms of LT and EQ. This allows to re-implement only LT/EQ for subtypes

    def func_EQ(self, ref):
        sl, rf = self.dat, ref.dat
        if sl is not None and rf is not None:
            if rf == sl:
                return True
        return False

    def func_LT(self, ref):
        sl, rf = self.dat, ref.dat
        if sl is not None and rf is not None:
            if rf < sl:
                return True
        return False

    def func_NEQ(self, ref):
        return not self.func_EQ(ref)

    def func_GT(self, ref):
        return not self.func_EQ(ref) and not self.func_LT(ref)

    def func_LE(self, ref):
        return self.func_LT(ref) or self.func_EQ(ref)

    def func_GE(self, ref):
        return not self.func_LT(ref)


    # TODO - do we need to add a max_val and min_val functions - in order to allow comparison of time and event
    # specifically - min_val of the OBJ. e.g. min_val(event) = slot.start  (or maybe call time_slot's min_val?)
    # and maybe this should depend on the type of SELF as well?
    # for "normal" cases, these functions just return self.

    # #############################################################################################

    def func_FN(self, obj, fname=None, farg=None, op=None, mode=None):
        if farg is not None:  # by default, use the 'aka' function
            val = farg.dat
            if val is not None and val in obj.aka():
                return True
        return False

    # is `self` equivalent to `other`?
    # if `other` is a list, then: is `self` equivalent to ANY object in the list?
    # base implementation - 'no'
    # returns - a list of all the matching objects in `other`. (empty list if no equiv)
    def equivalent_obj(self, other):
        return [i for i in to_list(other) if i.id == self.id]

    # base function
    def strings_are_similar(self, rf, sl):
        return strings_similar(rf, sl)

    # sample implementation of fuzzy "like" - this can depend on custom type - so overridden
    # called on parent, assuming the comparison is applied to its positional input
    # TODO: verify view modes
    def func_LIKE(self, ref):
        sl, rf = self.res.inputs[posname(1)].dat, ref.res.dat
        if sl is not None and rf is not None:
            if rf == sl:
                return True
            if isinstance(rf, str) and isinstance(sl, str):
                if self.strings_are_similar(rf, sl):
                    return True
        return False

    # TODO: do we also need a NOT_LIKE function?

    # ref is a string (or tree of strings) - compare this tree to the (set of) aka strings describing the obj
    def match_aka(self, obj):
        if self.not_operator():
            d = self.res.dat
            return True if d is not None and d in obj.aka() else False
        op = self.typename()
        if op == 'NOT':
            inp = self.input_view(posname(1))
            return not inp.match_aka(obj)
        elif op == 'AND':
            for i in self.inputs:
                if is_pos(i) and not self.input_view(i).match_aka(obj):
                    return False
            return True
        elif op == 'OR':
            for i in self.inputs:
                if is_pos(i) and self.input_view(i).match_aka(obj):
                    return True
            return False
        return False

    # base function for custom match.
    # possible uses: e.g. when one input field in the constraint needs to be compared with other fields in the object,
    # we pass all the params as in the call to match() - in case custom_match needs to recursively call match()
    # NOTE - it is not recommended having complex constraints under a custom match field!
    #   it up to the derived class implementation to make sure that this will work!
    #       (it may be difficult / need some changes to the custom match pattern!
    #         e.g. passing some flag recursively through the normal match)
    def custom_match(self, nm, obj, iview=VIEW.INT, oview=None, check_level=False, match_miss=False):
        return True

    # perform tree match between a constraint tree (self) and an object (obj)
    # the constraint may have operators, but the object should be a simple structure - no operators
    # takes care of intension/extension for both ref (self) and obj
    # check level - done only for the top level match - not done for deeper matches
    # iview - specifies if ref should be used as intension/extension
    # oview - specifies if obj should be used as intension/extension
    #        `oview `is usually `None` (in which case we get it from `ref.constr_obj_view`). If it's not None, it
    #        overrides the value from `constr_obj_view`. This happens in case `iview` is extension - we still take the
    #        `oview` from the intension, so need to pass it into `match()` to override the value from the extension.
    #        the reason we don't take the extension `oview` is that often we don't put this info in results
    # TODO: remove 'res' from input params
    # TODO: mode to input_view instead of explicitly checking for view?? <<<
    def match(self, obj, iview=VIEW.INT, oview=None, check_level=False, match_miss=False):
        """
        Match function for NON operator nodes.
        """

        if oview is None:
            # take oview from self. oview is not None only if we switched from ref intension to extension -
            #    in that case, we keep the oest of the intension
            oview = self.constr_obj_view

        if iview == VIEW.EXT and self.res != self:
            return self.res.match(obj, iview=VIEW.INT, oview=oview, check_level=check_level, match_miss=match_miss)

        # if the constraint specifies it should apply to the result of the object, switch object to its result
        if oview == VIEW.EXT:
            obj = obj.res

        if check_level and obj.not_operator():
            if not compatible_clevel(self.constraint_level, obj.constraint_level):
                return False

        if self.typename() == 'Empty':
            return False

        if self.typename() != 'Node':
            tp = type(obj)  #
            if tp.__name__ in node_fact.operators:  # in principle, obj should be a simple object without operators
                tp = obj.get_op_type()
            if tp != type(self) and tp not in node_fact.operators:
                if not issubclass(tp, type(self)):
                    return False
            if obj.is_operator():
                os = obj.get_op_objects()
                for o in os:
                    if o.typename()!='Node' and o.typename()!=self.typename():
                        return False
                    if check_level and not compatible_clevel(self.constraint_level, o.constraint_level):
                        return False

        if self.typename() == 'Node' and len(self.inputs) == 0:  # Any() matches any node. TODO: constraint_level
            return True

        # at this point, both object and constraint point to the right nodes - no need to refer to .result for either

        if self.id == obj.id:  # a node matches itself  TODO: - really? - constraint level would not match
            return True

        # default tag match - if tag specified in constraint, verify match. Ignore additional tags in obj
        if len(self.tags) > 0:
            for t in self.tags:
                if TAG_NO_MATCH not in t and (t not in obj.tags or (self.tags[t] and self.tags[t] != obj.tags[t])):
                    return False
        if len(obj.tags) > 0:  # required tags (tag name has '*' in it) - require all tags of obj to match constraint
            for t in obj.tags:
                if '*' in t and (t not in self.tags or obj.tags[t] != self.tags[t]):
                    return False

        if self.data is not None:  # leaf
            return self.func_EQ(obj)

        # allow object with SET only if it's a wrapper (or recursive wrappers) around just one real object
        # obj SETs with more than one element - should be handled explicitly in ref (using ANY/ALL)
        if obj.typename() == 'SET':
            if posname(1) in obj.inputs and len(obj.inputs) == 1:
                return self.match(obj.input_view(posname(1)), iview=VIEW.INT,
                                  check_level=check_level, match_miss=match_miss)
            else:
                return False  # no match, or multiple objects in set

        for nm in self.inputs:
            if self.typename()=='Node':
                if nm=='_inp':
                    for onm in obj.inputs:
                        if onm not in self.inputs:  # (as long as not explicitly given for self)
                            if self.input_view(nm).match(obj.input_view(onm), iview=self.view_mode[nm],
                                                         match_miss=match_miss):
                                return True
                    return False
                else:
                    if nm not in obj.inputs or not \
                            self.input_view(nm).match(obj.input_view(nm), iview=self.view_mode[nm],match_miss=match_miss):
                        return False
            elif nm in self.signature:
                if self.signature[nm].prop:
                    pass  # don't try to match prop
                elif self.signature[nm].custom:
                    if not self.custom_match(nm, obj, iview=self.view_mode[nm], match_miss=match_miss):
                        return False
                elif self.input_view(nm).typename() == 'Clear':  # do we really want it here...
                    pass  # cleared constraint about this field - match succeeds no matter what the input is
                elif nm in obj.inputs:
                    if not self.signature[nm].excl_match:
                        if not self.input_view(nm).match(obj.input_view(nm), iview=self.view_mode[nm],
                                                         match_miss=match_miss):
                            return False
                elif self.signature[nm].match_miss and match_miss:
                    pass
                elif self.input_view(nm).typename() == 'Empty':
                    pass
                elif nm not in obj.signature or nm not in obj.inputs:
                    return False
            else:  # nm not in self.signature - 'special cases'
                if nm == '_out_type':
                    if not obj.outypename() == self.get_dat(nm):
                        return False
                elif nm == '_aka':
                    if not self.input_view(nm).match_aka(obj):
                        return False
                else:
                    return False

        return True

    # compare two graphs - used for comparing two unevaluated expressions
    # customize this part
    def custom_compare_tree(self, other, diffs):
        for nm in self.inputs:
            if nm not in other.inputs:
                diffs.append('Missing:%s(%s)' % (self.typename(), nm))
            else:
                diffs = self.inputs[nm].compare_tree(other.inputs[nm], diffs)
        for nm in other.inputs:
            if nm not in self.inputs:
                diffs.append('Extra:%s(%s)' % (self.typename(), nm))
        return diffs

    # compare two graphs - used for comparing two unevaluated expressions!
    def compare_tree(self, other, diffs):
        if self.data is not None or other.data is not None:
            if self.data != other.data:
                if isinstance(self.data, str) and isinstance(other.data, str) \
                        and len(self.data) > 3 and len(other.data) > 3 and \
                        (self.data.lower() in other.data.lower() or other.data.lower() in self.data.lower()):
                    return diffs
                diffs.append('data:[%s,%s]' % (re.sub('[ \n]', '', self.data), re.sub('[ \n]', '', other.data)))
            return diffs

        if self.typename() != other.typename():
            diffs.append('NodeTypes:%s/%s/[%s//%s]' % (self.typename(), other.typename(),
                                                       re.sub('[ \n]', '', self.show()),
                                                       re.sub('[ \n]', '', other.show())))
            return diffs

        return self.custom_compare_tree(other, diffs)

    # no match found in the graph - try harder, typically search external DB
    # parent - used, but not consistently
    # all_nodes, goals - graph context - filled by the evaluation process (when calling exec())
    # params - additional parameters - free to define, (refer.exec does NOT supply these)
    def fallback_search(self, parent, all_nodes=None, goals=None, do_eval=True, params=None):
        return []

    def fallback_search_harder(self, parent, all_nodes=None, goals=None, do_eval=True, params=None):
        return []

    def populate_update(self, nm):
        return False

    # #############################################################################################
    # ###################################### Match functions ######################################

    def order_score_offset(self, path):
        return 0

    # score by order
    def score_by_order(self, goals, follow_res, exc=-50):
        """
        Finds all parent nodes of current node and their distance. Score is a combination of distance to goal and how
        recent that goal is (return lowest score).
        """
        depths, orig = self.parent_nodes(res=follow_res)
        b = 999999
        cturn = self.context.turn_num
        for ig, g in enumerate(reversed(goals)):
            if g in depths:
                s = ig * 100 + depths[g]
                s += 10 * (cturn - g.created_turn)  # added - prefer nodes created more recently - todo: check!
                path = self.get_path(g, orig)
                for p in path:
                    s += p.order_score_offset(path)
                if s < b:
                    b = s
        if self in self.context.exception_nodes + self.context.copied_exceptions:
            b += exc
        return b

    @staticmethod
    def rank_by_order(matches, goals, follow_res):
        """
        Ranks a set of matching nodes according to their order in the history of the dialog graphs.
        """
        scores = {}
        for n in matches:
            scores[n] = n.score_by_order(goals, follow_res)
        return sorted(scores, key=scores.get)

    # error message when search did not find a match
    # can be customized per type (e.g. recursively describing the constraint)
    def search_error_message(self, node):
        tp = self.typename()
        if self.is_operator():
            tp += '[%s]' % self.get_op_type().__name__
        return ElementNotFoundException("Search for %s did not return any results" % tp, node)

    # for functions - custom execution for functions
    # exec may generate new goals. in that case:  TODO: review this! may be out of date!
    #  1) it's responsible to add the new goal(s) to the context dialog
    #  2) it's responsible to evaluate the new goals
    def exec(self, all_nodes=None, goals=None):
        pass

    def fix_counters(self):
        for i in list(self.counters.keys()):
            if i.startswith('max_'):
                s = i[4:]
                if s not in self.counters:
                    self.counters[s] = 0

    def count_ok(self, nm):
        if nm in self.counters:
            s = 'max_' + nm
            if s in self.counters and self.counters[nm] >= self.counters[s]:
                return False
        return True

    def inc_count(self, nm, inc=1):
        if nm in self.counters:
            self.counters[nm] += inc
        else:
            self.counters[nm] = inc

    def reset_count(self, nm, val=0):
        self.counters[nm] = val

    # validate input
    # execute function (if applicable) set result pointer (possibly create result node(s))
    # raise exception on error
    def evaluate(self, all_nodes=None, goals=None):
        if self.evaluated:  # no need to repeat TODO: make sure this holds!
            return

        self.fix_counters()

        # 1. custom input validity checks - called after verified no obligatory input is missing
        if self.constraint_level > 0:
            self.valid_constraint()
            # elif TODO: ?
        else:
            if self.check_node:  # and self.not_operator():# no further check if this just aggregates multiple instances
                self.valid_input()

        # 2. check for obligatory inputs which were not given (in case custom valid_input did not find custom problems)
        # TODO: turn check off for constraint?
        if self.check_node and self.constraint_level == 0 and self.not_operator():
            for name in self.signature:
                p = self.signature[name]
                if p.oblig and name not in self.inputs:
                    raise MissingValueException.make_exc(name, self, hints=p.type_name())

        # 4. execute function (for non-type nodes)
        # this will set self.result
        # exec may generate new goals (but usually just return None)
        if self.constraint_level == 0:  # function nodes which are used as type constraint - don't exec
            self.exec(all_nodes, goals)

        # 5. if result not set by now (i.e. not a function) then set it to self
        if self.result is None:  # TODO: in case of a function constraint...
            self.result = self

        # set assigned result nodes
        d_context = self.context
        if d_context and self in d_context.res_assign.values():
            for i in list(d_context.res_assign.keys()):
                if d_context.res_assign[i] == self:
                    d_context.assign[i] = self.res
                    del d_context.res_assign[i]
                    if self.res != self and not self.res.evaluated:  # in case result has not yet been evaluated
                        d_context.res_assign[i] = self.res
                        # TODO: to be safe - maybe remove all res_assign after each turn?

        self.evaluated = True
        self.post_evaluate()
        # TODO: setting result and adding nodes to graph - inside exec?

    def post_evaluate(self):
        pass

    # note - due to aliases, positional indices may not be consecutive
    def num_pos_inputs(self):
        return len([i for i in self.inputs if is_pos(i)])

    def max_pos_input(self):
        return max([0] + [posname_idx(i) for i in self.inputs if is_pos(i)])

    # get nodes for which self is (transitively) a result - create a dict {node, dist} by BFS
    def parent_res(self):
        q = [self]
        depths = {}
        while q:
            n = q.pop()
            d = depths[n] if depths else 0
            for o in n.res_out:
                if o not in depths:
                    depths[o] = d + 1
                    q.insert(0, o)
        return depths

    def get_key_index(self, k):
        i = self.signature.get_key_index(k)
        if i < 0:
            if self.is_operator() and is_pos(k):
                return posname_idx(k)
            return 0
        else:
            return i

    # return set of all nodes connected transitively by output edges - create a dict {node, dist} by BFS
    # TODO: should also include result? no (?)
    def parent_nodes(self, res=False):
        q = [self]
        depths = {self: 0}
        orig = {}  # for each node - from where did we get to ("edge origin") (the first origin) - not used!
        while q:
            n = q.pop()
            d = depths[n]
            if res:
                rdep = n.parent_res()
                for r in rdep:
                    if r not in depths:
                        depths[r] = d + 0.01 * rdep[r]
                        q.insert(0, r)
                        if r not in orig:
                            orig[r] = ('RES', n)
            for m, o in n.outputs:
                if o not in depths:
                    depths[o] = d + 1 + 0.0001 * o.get_key_index(
                        m)  # last element - make score depend on order of inputs
                    if o not in orig:
                        orig[o] = (m, n)
                    q.insert(0, o)
        return depths, orig

    # after calling parent_nodes, use the calculated 'orig' for more efficiently finding path from self to target node
    # (returns just one path)
    def get_path(self, targ, orig):
        path = []
        n = targ
        try:
            while n != self:
                path.append(n)
                n = orig[n][1]
        except:  # if there is no path
            return []
        path.append(n)
        return list(reversed(path))

    # find a path (one path out of multiple possible) from self to dest node. Empty if no path found
    def get_a_path(self, dest, follow_res=True):
        depths, orig = self.parent_nodes(res=follow_res)
        path = self.get_path(dest, orig)
        return path

    def get_parent(self, typ=None, name=None, newest=True):
        """
        Returns (connection name, direct parent) or (None, None). If node has multiple parents - return last.
        """
        if self.outputs:
            if typ and len(self.outputs) > 1:
                for (nm, nd) in reversed(self.outputs) if newest else self.outputs:
                    if (not typ or nd.typename() in to_list(typ)) and (not name or nm == name):
                        return nm, nd
            return self.outputs[-1] if newest else self.outputs[0]
        return None, None

    def follow_nodes(self, parents, follow_res=True, follow_res_trans=False, summarize=None,
                     follow_detached=False, follow_view=False, res_only=False):
        if summarize and self.typename() in summarize:
            return []
        nds = []
        for i in self.inputs:
            n = self.inputs[i].res if res_only else self.input_view(i) if follow_view and not follow_res else \
                self.inputs[i]
            # if self.typename()=='SWITCH' and self.inp_equals('excl', True) and i!=posname(1):  don't add - todo
            if n not in nds:  # avoid adding node twice - could be that two inputs are the same
                nds.append(n)
        if follow_res and not follow_res_trans and self.result is not None and \
                self.result != self and self.result not in nds and self.result not in parents:
            nds.append(self.result)
        if follow_res_trans and self.res is not None and self.res != self and self.res not in nds:
            nds.append(self.res)
        if follow_detached:
            for (nm, nd) in self.detached_nodes:
                if nd not in nds:
                    nds.append(nd)
        return nds

    # switch_ext - experimental - if true, follow result instead of inputs for nodes with node.extension=True
    # full_dfs - DFS order, a node may be added more than once (e.g. a node used multiple times as input) - removed
    # TODO: follow_re_trans - not used?
    def topological_order(self, nodes=None, parents=None, follow_res=True, exclude_neg=False, follow_res_trans=False,
                          summarize=None, follow_detached=False, follow_view=False,
                          res_only=False):
        """
        Creates a list of all nodes in the "tree" rooted at current node. Nodes appear AFTER all their inputs,
        aggregates, results.

        It is possible to incrementally create a list for multiple graphs, but then order matters! Newer graphs may
        depend on older ones, so start with the older ones!

        :param exclude_neg: if ``True, then don't follow nodes with "negative" constraint_op (hacky,
        used for squash_aggregate)
        :type exclude_neg: bool
        :param summarize: used only for draw_graph - list of node type names for which we don't follow inputs
        (reduce clutter in drawing)
        :param res_only: follow only results
        :type res_only: bool
        """
        nodes = nodes if nodes else []
        parents = parents if parents else []
        parents.append(self)
        for n in self.follow_nodes(parents, follow_res, summarize=summarize, follow_detached=follow_detached,
                                   follow_view=follow_view, res_only=res_only):  # TODO: follow_re_trans - not used?
            if n not in nodes and (not exclude_neg or n.typename() not in ['NEQ', 'NOT', 'NONE']):
                nodes = n.topological_order(nodes, parents, follow_res, exclude_neg, follow_res_trans,
                                            summarize, follow_detached, follow_view, res_only)
        if self not in nodes:
            nodes.append(self)
        return nodes

    @staticmethod
    def collect_nodes(goals, follow_res=True, exclude_neg=False, follow_res_trans=False,
                      summarize=None, follow_detached=False, follow_view=False):
        nodes = []
        goals = to_list(goals)
        for gl in goals:
            nodes = gl.topological_order(nodes, None, follow_res, exclude_neg, follow_res_trans, summarize,
                                         follow_detached, follow_view)
        return nodes

    @staticmethod
    def get_nodes_of_typ(nds, typ):
        t = to_list(typ)
        return [n for n in nds if n.typename() in typ]

    def get_subnodes_of_type(self, typ, nodes=None, follow_res=True, exclude_neg=False,
                             follow_res_trans=False, summarize=None, follow_detached=False, follow_view=False):
        """
        Gets all sub-nodes of a given typename.
        """
        nodes = self.topological_order(nodes, None, follow_res, exclude_neg, follow_res_trans,
                                       summarize, follow_detached, follow_view)
        return self.get_nodes_of_typ(nodes, typ)
        # typ = to_list(typ)
        # ns = [n for n in nodes if n.typename() in typ]
        # return ns

    def get_goal_path(self, goal=None, excl=None):
        """
        Gets path from `self` to `goal`. If `goal` is not given, select most recent goal within list of parents of
        `self`, if it exists.

        :param goal: the goal
        :type goal: Optional["Node"]
        """
        dp, og = self.parent_nodes(res=True)
        if not goal:  # no goal specified - so use the most recent goal in the parents
            excl = excl if excl else ['revise']
            gls = [n for n in dp if n in self.context.goals and n.typename() not in excl]
            if gls:
                goal = gls[-1]
            else:  # no goal in parents
                return None, []
        # use og to backtrack from goal to current node along shortest path
        i = goal
        path = []
        while i != self:
            path.append((og[i][0], i))
            i = og[i][1]
        path.append(('', self))
        return goal, path

    # make sure each node has an uniq name (i.e. not in the given list of names)
    # (if not - add an integer index to base name)
    def get_uniq_name(self, names, summarize=None):
        nm = str(type(self)).split('.')[-1].split("'")[0]  # TODO: revisit node naming! (name != type)
        if self.data is not None or self.typename() in summarize:
            nm = str(self.dat)
            if environment_definitions.show_node_type:
                nm = '(' + self.typename() + ')' + nm
        nm = str(self.id) + '=' + nm
        nn, i = nm, 1
        while nn in names:  # add _%d to name to make it unique
            nn = nm + '_%d' % i
            i += 1
        return re.sub(':', '-', nn)

    @staticmethod
    def assign_node_names(nodes, summarize=None):
        """
        Given list of all nodes (usually - in topological order), create dictionary {name : node}.

        :return: a dictionary with nodes per name
        :rtype: Dict[str, "Node"]
        """
        names = []
        node_names = {}
        for n in reversed(nodes):
            nm = n.get_uniq_name(names, summarize=summarize)
            names.append(nm)
            node_names[n] = nm
        return node_names

    @staticmethod
    def duplicate_tree(node, set_dup=False, force_tags=False):
        """
        Makes a new copy of the WHOLE subgraph.
        """
        d_context = node.context
        old_subgraph = node.collect_nodes([node])
        new_subgraph = []
        for n in old_subgraph:
            nw = type(n)()
            nw.copy_info(n, force_tags=force_tags)
            if set_dup:
                nw.just_dup = True
                nw.dup_of = n
            d_context.register_node(nw)
            new_subgraph.append(nw)
            if n in d_context.exception_nodes:
                # if orig node had an exception - mark the new as a copy of an exception one
                d_context.copied_exceptions.append(nw)
        old_idx = {o: i for i, o in enumerate(old_subgraph)}

        # fill/update inputs & outputs for new and old
        for ig, o in enumerate(old_subgraph):
            n = new_subgraph[ig]
            for nm in o.inputs:
                o_in = o.inputs[nm]  # old input node
                if o_in in old_subgraph:  # always true!  input within subgraph (new_beg will not be changed)
                    n_in = new_subgraph[old_idx[o_in]]  # new input node
                    n.inputs[nm] = n_in  # replace by corresponding new node
                    n_in.add_output(nm, n)
                else:  # never true keep old input (already copied), and add output link from old node to new node
                    o_in.add_output(nm, n)

        for n in new_subgraph:
            if n.just_dup:
                n.on_duplicate(dup_tree=True)
                n.just_dup = False

        return new_subgraph

    # use e.g. for debugging, to show a cropped version of some intermediate tree
    def duplicate_res_tree(self, nodes=None, register=True, keep_turn=False):
        """
        Duplicates a tree, replacing input nodes by their results.
        """
        d_context = self.context
        if nodes is None:
            nodes = {}
        nw = node_fact.create_node_from_type_name(d_context, self.typename(), register)
        if register:
            d_context.register_node(nw)
        nw.data = self.data
        nw.constraint_level = self.constraint_level
        nw.out_type = self.out_type
        if keep_turn:
            nw.created_turn = self.created_turn
        for i in self.inputs:
            s = self.inputs[i].res
            if s in nodes:
                n = nodes[s]
            else:
                n, nodes = s.duplicate_res_tree(nodes, register, keep_turn)
                nodes[s] = n
            n.connect_in_out(i, nw)

        return nw, nodes

    def add_dup_goal(self, save=True):
        if save:
            dup = Node.duplicate_tree(self, force_tags=True)
            self.context.add_goal(dup[-1])

    # get the nodes "between" current and root - the subgraph which needs to be duplicated by revise()
    #   all the nodes which (transitively) feed from this node, AND (transitively) feed into the root
    #   (other nodes which feed into the root will just be linked to - in order to reduce duplication to minimum)
    def get_subgraph(self, root, follow_res=False, btm_sort=False, with_dist=False, typs=None):
        """
        Gets the nodes "between" current and root - the subgraph which needs to be duplicated by `revise()`.
        All the nodes which (transitively) feed from this node, AND (transitively) feed into the root (other nodes
        which feed into the root will just be linked to - in order to reduce duplication to minimum).
        """
        root_nodes = root.collect_nodes([root], follow_res=follow_res)  # we do NOT include result nodes
        depths, _ = self.parent_nodes(res=follow_res)
        subgraph = [n for n in root_nodes if
                    n in depths]  # intersect, while keeping topological order (relative to root)
        if btm_sort:  # order nodes by increasing distance from self. (otherwise - topo dist from root)
            dp = sorted(depths, key=depths.get)
            if typs:
                typs = to_list(typs)
                dp = [i for i in dp if i.typename() in typs]
            return [(i, depths[i]) for i in dp if i in subgraph] if with_dist else [i for i in dp if i in subgraph]
        return subgraph

    # called by duplicate_subgraph, when mode starts with 'auto'
    # returns:
    #   new_beg, dup_old_beg, done, ignore, mode
    def create_new_beg(self, new_beg, mode, rev, root, mid, below):
        raise NotImplementedYetDFException(
            'Revise newMode %s not implemented for node type %s' % (mode, self.typename()), self)

    # create a modified node to replace an input in duplicate_subgraph()
    # new_inp input to new_beg.
    # old_inp is input to (copy of) old_beg
    # self - DON'T USE!. Generally the same as new_inp, EXCEPT when new_inp is an operator
    #    (then - self is one 'real' object under new_inp - its type is used for selecting the matching dup_auto_modify)
    # base function - return new input as is
    def dup_auto_modify(self, new_inp, old_beg, inp_nm):
        return new_inp

    # experimental - let the (copy of old beg) node handle the modification by itself
    def dup_auto_modify_top(self, new_beg):
        pass

    # copy_info: used when duplicating a subgraph
    #   given a "fresh" node and a ref node, copy from ref node fields which may have been changed after init
    #   NOTE: by default, outputs are not copied (unless add_outputs) - they will be filled in the duplication process
    def copy_info(self, other, add_outputs=False, force_tags=False):
        self.inputs = other.inputs.duplicate()
        if add_outputs:
            for i in self.inputs:
                if (i, self) not in self.inputs[i].outputs:
                    self.inputs[i].outputs.append((i, self))
        for i in other.view_mode:
            self.view_mode[i] = other.view_mode[i]
        for i in other.tags:
            if force_tags or TAG_NO_COPY not in i:  # tags with TAG_NO_COPY are not copied
                self.tags[i] = other.tags[i]
        self.data = other.data
        self.constraint_level = other.constraint_level
        self.out_type = other.out_type
        self.mutable = other.mutable
        self.hide = other.hide
        self.detach = other.detach
        self.no_revise = other.no_revise
        # we do NOT copy other.detached_nodes
        self.add_goal = other.add_goal
        self.res_block = other.res_block
        self.constr_obj_view = other.constr_obj_view
        self.stop_eval_on_exception = other.stop_eval_on_exception
        self.inited = other.inited
        # not copying created_turn - leave as is
        self.counters = {i: other.counters[i] for i in other.counters}

    def typename(self):
        return type(self).__name__

    def typename_cl(self):
        return type(self).__name__ + '/%s' % self.constraint_level

    def outypename(self):
        if self.out_type is None:
            return 'Node'
        return self.out_type.__name__

    def singleton_multi_error(self, matches):
        s, o = Node.describe_multi(matches)
        return 'Multiple %s objects' % self.typename() + ' NL ' + s, o

    def singleton_no_match_error(self):
        return 'Singleton error - no matching %s objects' % self.typename()

    def singleton_suggestions(self, sid, matches):
        if sid is None:
            return None
        dflt = ['rerun(id=%d)' % sid]
        sg = []
        for i, m in enumerate(matches):
            sg.append('revise(oldNodeId=%d, hasParam=index, new=%d, newMode=extend)' % (sid, i + 1))
        return dflt + sg

    # execute filtering - for a node with (optionally) 'filter'
    # add (optional)- add extra candidates
    def do_filter(self, res, add=None, filter='filter', match_miss=False):
        candidates = res.get_op_objects()
        if add:
            for a in add:
                candidates.append(a)
        if filter in self.inputs:
            filt = self.input_view(filter)
            matches = [c for c in candidates if filt.match(c, match_miss=match_miss)]
        else:  # if no filter specified - all candidates match
            matches = candidates
        return candidates, matches

    def aka(self):
        """
        Returns a list of string aliases for this node. Override per type.
        """
        d = self.dat
        if d is None:
            return []
        return [str(d)]

    # base function - called per node after it has been duplicated (usually - nothing to do)
    # currently - we call this from two places - duplicate(), and duplicate_tree(). We may want different behaviors.
    # typically returns self, but could return create another node instead (or None)
    #           if not self - then needs to make sure that all plumbing is correct!
    def on_duplicate(self, dup_tree=False):
        self.counters['dup'] += 1
        return self

    def print_tree(self, parent, ind=None, seen=None, with_id=True, with_pos=True, trim_leaf=True,
                   trim_sugar=True, mark_val=True, assg=True, with_res=False):
        seen = seen if seen else []
        if self.id in seen:
            return id_sexp(self), seen
        seen.append(self.id)
        s = '%d:' % self.id if with_id and self.id is not None else ''
        ii = ind + 4 if ind else None
        t1 = ' ' * ind if ind else ''
        t2 = ' ' * ii if ii else ''
        if trim_leaf and not with_id and self.is_base_type() and self.dat is not None:
            inps = []
        elif trim_sugar and self.typename() == 'getattr':
            ss, seen = self.inputs['pos2'].print_tree(self, ii, seen, with_id, with_pos, trim_leaf,
                                                      trim_sugar, mark_val, assg, with_res)
            return ':%s(%s)' % (self.get_dat('pos1'), ss), seen
        else:
            tn = self.typename()
            if assg and is_assign_name(self.typename()) and (not parent or parent.typename() != 'let'):
                tn = '$' + tn
            s += tn + '?' * self.constraint_level
            inps = []
            for i in self.inputs:
                ss, seen = self.inputs[i].print_tree(self, ii, seen, with_id, with_pos, trim_leaf,
                                                     trim_sugar, mark_val, assg, with_res)
                inps.append('%s%s%s' % (t2, show_prm_nm(i, with_pos, self.signature), ss))
            if with_res and self.result != self:
                ss, seen = self.result.print_tree(self, ii, seen, with_id, with_pos, trim_leaf,
                                                  trim_sugar, mark_val, assg, with_res)
                inps.append('%sresult=%s' % (t2, ss))
        if inps:
            b = '(\n' if ind else '('
            e = '\n%s)' % t1 if ind else ')'
            d = ',\n' if ind else ','
            s += b + d.join(inps) + e
        elif self.data is not None or (trim_leaf and self.dat is not None):
            if with_id:
                # s += '<%s>' % self.data
                s += '(%s)' % self.data
            else:
                # ss = '%s' % re.sub(' ', '_', str(self.data))
                ss = str(self.data)
                if mark_val and parent:
                    nm = [n for (n, m) in self.outputs if m == parent][0]
                    # tp = parent.signature[nm].type
                    if self.typename()[:3].lower() == 'str':  # <<< hack!
                        ss = escape_string(ss)
                        # ss = ss if ss[0]=='"' else '"' + re.sub('"', '\\"', ss) + '"'
                    # elif isinstance(tp, list) or tp != type(self):
                    #     ss = '#' + ss
                    ss = ss.replace('#', '')
                s += ss if trim_leaf else '(%s)' % ss
        else:
            if s[0] != '$':
                s += '()'
        return s, seen

    def compr_tree(self, seen=None):
        seen = seen if seen else []
        if self.id in seen:
            return id_sexp(self), seen
        seen.append(self.id)
        feats = self.get_feat_str()
        s = '<' + feats + '>' if feats else ''
        tn = self.typename()
        s += tn + '?' * self.constraint_level
        inps = []
        show_pos = False  # show name of pos param if input order does not respect it
        nn = len(self.inputs)
        for i in range(nn):
            for j in range(i+1, nn):
                if is_pos(i) and is_pos(j) and posname_idx(i)>posname_idx(j):
                    show_pos=True
        for i in self.inputs:
            ss, seen = self.inputs[i].compr_tree(seen)
            inps.append('%s%s' % (show_prm_nm(i, show_pos, self.signature), ss))
        t = self.get_tags_str()
        if t:
            inps.append(t)
        if inps:
            s += '(' + ','.join(inps) + ')'
        elif self.data is not None:
            s += '(%s)' % self.data
        else:
            s += '()'
        return s, seen

    # describe - returns text (possibly empty), and list of objects/values (possibly empty)
    def describe(self, params=None):
        """
        Describes node in text. Override per type.
        """
        if self.data:
            return Message(str(self.data))
        if self.result != self:
            return self.result.describe(params)
        return Message('')

    # base function - yielding message+objects from top node
    # message - text to user
    # objects - a list of strings/nodes (or paired (str,node) ?) - TBD
    def yield_msg(self, params=None):
        return self.describe(params=params)

    # returns msg and objs
    def yield_failed_msg(self, params=None):
        return Message('')

    # fairly natural text description for a SET of objects.
    # It handles SOME aggr/quals, but not really designed for that (complex logical expressions are not natural in text)
    # nl: new_line indicator. by default ' NL ' - which is understood by draw_graph (depending on graphviz env!)
    # 'compact' is a mode used for showing summarized nodes in the graph drawing
    # returns msg and objs
    def describe_set(self, nl=' NL ', params=None):
        cont_typs = ['SET', 'OR', 'LIKE', 'ANY', 'NONE']
        params = [] if params is None else params
        if self.constraint_level == 0 or 'compact' in params or self.typename() in cont_typs:
            if self.typename() in cont_typs:
                found = self.get_op_objects([], exclude_neg=True)
                if found:
                    if len(found) == 1:
                        return found[0].describe()  # self.describe()
                    else:
                        if 'compact' in params:
                            return '/'.join([o.describe(params).text for o in found])
                        s = '%d %s' % (len(found), found[0].obj_name_plural) + nl
                        objs = []
                        for o in found:
                            m = o.describe()
                            s = s + m.text + nl
                            objs += m.objects if m.objects else []
                        return Message(s, objects=objs)
            elif self.constraint_level > 0:
                m = self.describe(params)
                return Message(self.typename() + ' NL ' + m.text, objects=m.objects)
            else:
                return self.describe(params)
        return Message('')

    # text description for a list of objects (assumed to be of the same type!)
    # also accepts an aggregate (SET only) of objects
    @staticmethod
    def describe_multi(matches, nl=' NL '):
        if not isinstance(matches, list):  # an aggregate given
            if isinstance(matches, Node) and matches.typename() == 'SET':
                matches = [matches.inputs[n] for n in matches.inputs if type(matches.inputs[n]) == type(matches)]
            else:
                logger.warning('Error - describe multi unexpected input %s' % matches)
                exit(1)
        n = len(matches)
        if n == 1:
            return matches[0].describe()
        elif n > 1:
            s = '%d %s' % (n, matches[0].obj_name_plural) + nl
            objs = []
            for o in matches:
                m = o.describe()
                s = s + m.text + nl
                objs += m.objects if m.objects else []
            return Message(s, objects=objs)
        return Message('')

    # default implementation
    # translate an entity, to new_beg (sexp to be used e.g. in a revise expression)
    # new_md - is (typically) revise mode - in case the entity value might change it. Normally just return it back
    # i_nlu - index of entity
    # h - the hint to follow
    def trans_slot_newBeg(self, nlu, i_nlu, new_md, h):
        clevel = 0
        ent = nlu[i_nlu]
        if ent.consumed:
            return None, nlu, new_md
        ent_nm = list(ent.keys())[0]
        val = ent[ent_nm]
        if h:
            tp, clevel, opts, prog = parse_hint(h)
            if 'conv' in opts:
                if val not in opts['conv']:
                    if '*' not in opts['conv']:  # '*' means 'other value'
                        raise SemanticException(
                            'Bad translation - value "%s" for entity "%s" not in conv table for %s : %s' %
                            (val, ent_nm, self.typename(), opts['conv']))
                        # return None, intent, entities, new_md
                        # return None, consumed, new_md
                    else:  # * -> * means copy NLU entity name.  * -> xxx means use xxx for 'other values'
                        val = val if opts['conv']['*'] == '*' else opts['conv']['*']
                else:
                    val = opts['conv'][val]
        nlu[i_nlu].consumed = True
        return '%s%s(%s)' % (self.typename(), '?' * clevel, val), nlu, new_md

    # default implementation
    # make inputs for program.
    def trans_slot_prog(self, nlu, i_nlu, new_md, h):
        s, nlu, _ = self.trans_slot_newBeg(nlu, i_nlu, new_md, h)
        return s, nlu

    # default implementation
    # translate unconsumed nlu entry given a hint ('h').
    # hints - list of hints - not used in default implementation, but may be used in some derived class
    # if i_nlu is given, try translating only that nlu entry, else - try all.
    def translate_slot(self, nlu, hints, h, i_nlu=None, prog=False):
        tp, cl, opts, prog = parse_hint(h)
        i_nlu = to_list(i_nlu) if i_nlu else list(range(len(nlu)))  # list of entity indices
        for i in i_nlu:
            if nlu[i].typ == NLU_TYPE.NLU_SLOT and not nlu[i].consumed:
                if 'tname' in opts:
                    old_md = 'hasParam' if 'omode' not in opts else opts['omode']
                    new_md = opts['nmode'] if 'nmode' in opts else 'extend' if old_md == 'hasParam' else 'new'
                    if prog:
                        s, nlu = self.trans_slot_prog(nlu, i, new_md, h)
                        return s, nlu
                    else:
                        vstr, nlu, new_md = self.trans_slot_newBeg(nlu, i, new_md, h)
                        if vstr:
                            otyp = 'oldType=%s,' % opts['otype'] if 'otype' in opts else ''
                            s = 'revise(%s%s=%s, new=%s, newMode=%s)' % (otyp, old_md, opts['tname'], vstr, new_md)
                            return s, nlu
        return None, nlu

    def get_wrapped_expr(self, fn):
        if self.is_operator():
            ii = [self.input_view(i).get_wrapped_expr(fn) for i in self.inputs]
            return self.typename() + '(' + ','.join(ii) + ')' if ii else ''
        fn = fn[:-1] if fn[-1] == '(' else fn
        prnt = ')' * (fn.count('(') - fn.count(')'))
        return '%s(%s)%s' % (fn, id_sexp(self), prnt)

    def map_func(self, fn):
        s = self.get_wrapped_expr(fn)
        d, _ = Node.call_construct_eval(s, self.context)
        return d

    # base function - to be overridden
    # translate an unconsumed intent into a sexp - may greedily consume additional nlu entries
    def translate_intent(self, nlu, hints, h, i_nlu=None, prog=False):
        raise SemanticException('Error - translate_intent not implemented for base class')

    # base function - to be overridden
    # translate an unconsumed entity tree into a sexp
    def translate_tree(self, nlu, hints, h, i_nlu=None, prog=False):
        raise SemanticException('Error - translate_tree not implemented for base class')

    def inp_equals(self, inp, val):
        if inp in self.inputs and self.get_dat(inp) == val:
            return True
        return False

    def get_op_parents(self, par, nm):
        if self.not_operator():
            return par if (self, nm) in par else par + [(self, nm)]
        for (nm, nd) in self.outputs:
            par = nd.get_op_parents(par, nm)
        return par

    def get_op_parent(self):
        if self.is_operator():
            par = self.get_op_parents([], '')
            par = par[0] if par else (self, None)
        else:
            par = (self, None)
        return par

    def get_op_types(self, types):
        """
        Recursively gets all "real" object (non operator) types DIRECTLY under current node.
        """
        if self.not_operator():
            return types if type(self) in types else types + [type(self)]
        for i in self.inputs:
            if is_pos(i):
                types = self.inputs[i].get_op_types(types)
        return types

    def get_op_type(self, no=None):
        """
        Gets ONE real object type DIRECTLY under current node.
        """
        if self.is_operator():
            typ = self.get_op_types([])
            typ = typ[0] if typ else no
        else:
            typ = type(self)
        return typ

    def get_op_outypes(self, excl_typs=None):
        tps = self.get_op_types([])
        if tps:
            otps = list(set([node_fact.sample_nodes[t.__name__].out_type.__name__ for t in tps]))
            if excl_typs:
                otps = [t for t in otps if t not in excl_typs]
            return otps
        return []

    def get_op_objects(self, objs=None, exclude_neg=False, typs=None, view=None):
        """
        Gets all objects directly under operator tree (it may be of different types!)
        """
        objs = [] if objs is None else objs
        typs = to_list(typs) if typs else None
        if self.not_operator():
            return objs if self in objs or (typs and self.typename() not in typs) else objs + [self]
        if exclude_neg and self.typename() in ['NOT', 'NEQ', 'NONE', 'negate']:
            return objs
        for i in self.inputs:
            n = self.inputs[i] if view==VIEW.INT else self.inputs[i].res if view==VIEW.EXT else self.input_view(i)
            objs = n.get_op_objects(objs, exclude_neg, typs, view)
        return objs

    def get_op_object(self, exclude_neg=False, typs=None, view=None):
        """
        Gets one object under operator tree.
        """
        if self.is_operator():
            obj = self.get_op_objects([], exclude_neg, typs, view)
            obj = obj[0] if obj else None
        else:
            obj = self
        return obj

    def get_op_object_try(self):
        """
        Returns object if exists; otherwise, return `self`.
        """
        obj = self.get_op_object()
        return obj if obj else self

    def unroll_set_objects(self, objs=None):
        """
        Gets all objects directly under SET.
        """
        objs = [] if objs is None else objs
        if not self.typename() == 'SET':
            return objs if self in objs else objs + [self]
        for i in self.inputs:
            if is_pos(i):
                n = self.input_view(i)
                objs = n.unroll_set_objects(objs)
        return objs

    def unroll_set_object(self):
        """
        Gets one object directly under SET tree, or `self` if `self` is not SET.
        """
        if self.typename() == 'SET':
            obj = self.unroll_set_objects([])
            obj = obj[0] if obj else None
        else:
            obj = self
        return obj

    # base method - given a node, decide how many objects it represents
    #  by default - 1, unless it's a SET, then it's the number of elements in the set.
    # depending on node type, different input fields may have different semantics
    @staticmethod
    def get_plurality(fld, obj):
        return len(to_list(obj.unroll_set_objects()))

    # TODO: not using MODE anymore - revert to old version?
    # TODO: do we need special care to exclude some objects from BOTH pos and neg? (e.g. below FN?)
    # use operator BLOCK
    def recurse_get_pos_neg_mode_objs(self, pos=None, neg=None, state=True, mode=None,
                                      typ=None, mult_neg=False, op_path=False, no_block=False):
        """
        Unrolls operator tree into positive and negative objects, and their modes.
        """
        pos = {} if pos is None else pos
        neg = {} if neg is None else neg
        mode1 = [] if mode is None else mode
        if self.typename() in BLOCK_TRAVERSE and not no_block:
            return pos, neg
        if (typ and self.typename() in typ) or (not typ and self.not_operator()):
            if state is not None:
                # avoid having same object in both pos and neg (theoretically possible)
                if state and self not in pos and self not in neg:
                    pos[self] = mode1
                if not state and self not in neg and self not in pos:
                    neg[self] = mode1
            return pos, neg
        if op_path and self.is_operator():
            mode1 = mode1 + [self.typename()]
        if state is not None and self.typename() in ['NEQ', 'NOT', 'NONE', 'negate']:
            state = not state if mult_neg else False
        if not op_path and self.is_modifier():
            mode1 = self  # not expecting recursive modifiers, so just keep the latest one
        for i in self.inputs:
            if is_pos(i):
                n = self.input_view(i)
                pos, neg = n.recurse_get_pos_neg_mode_objs(pos, neg, state, mode1, typ, mult_neg, op_path)
        return pos, neg

    # TODO: what to do if there are operator nodes other than SET/EQ/NEQ? - currently - ignore
    def get_pos_neg_mode_objs(self, state=True, mode=None, typ=None, mult_neg=False, do_sort=False):
        """
        Unrolls operator tree into positive and negative objects, and their modes. Gets a list of `real` objects in an
        operator tree.

        Separate the objects to a list of positive, and a list of negative (positive/negative state switches when
        passing through a negation operator).

        Additionally, collect `mode` info for each object (set when traversing a MODE operator, `None` if not seen).

        :param typ: if given, collect only objects of the types specified in `typ`
        :param mult_neg: if set, then e.g. `NEQ(NEQ(x))` -> `x`; otherwise, ALL nodes under NEQ stay negative
        :type mult_neg: bool
        :param do_sort: both positives and negatives are sorted in REVERSE topological order (root first)
        :type do_sort: bool
        :return: List of positive and negative nodes, respectively
        :rtype: Tuple[List["Node"], List["Node"]]
        """
        pos, neg = self.recurse_get_pos_neg_mode_objs(None, None, state, mode, typ, mult_neg)
        if do_sort:
            nodes = self.topological_order()
            pos = reversed([(n, pos[n]) for n in nodes if n in pos])
            neg = reversed([(n, neg[n]) for n in nodes if n in neg])
        else:
            pos, neg = [(n, pos[n]) for n in pos], [(n, neg[n]) for n in neg]
        return pos, neg

    def get_pos_neg_objs(self, state=True, typ=None, mult_neg=False, do_sort=False):
        """
        Unrolls operator tree into positive and negative objects.
        Similar to `get_pos_neg_mode_objs`, but omit mode info.
        """
        typ = to_list(typ) if typ else []
        pos, neg = self.get_pos_neg_mode_objs(state, None, typ, mult_neg, do_sort)
        pos = [n for (n, m) in pos]
        neg = [n for (n, m) in neg]
        return pos, neg

    def get_tree_pos_neg_fields(self, typ, field, dat=False):
        opos, oneg = self.get_pos_neg_objs(typ=to_list(typ))
        pos, neg = [], []
        for o in opos + oneg:
            f = o.input_view(field)
            if f:
                p, n = f.get_pos_neg_objs()
                if p:
                    if o in opos:
                        pos.extend(p)
                    else:
                        neg.extend(p)
                if n:
                    if o in opos:
                        neg.extend(n)
                    else:
                        pos.extend(n)
        if dat:
            pos, neg = [i.dat for i in pos], [i.dat for i in neg]
        return list(set(pos)), list(set(neg))

    def del_childless_ops(self, nm=None, parent=None):
        """
        Cleans childless operator nodes (typically after pruning). Removes operators which have no children anymore.
        """
        if self.is_operator():
            for i in list(self.inputs.keys()):
                self.input_view(i).del_childless_ops(i, self)
            if len(self.inputs) == 0:
                if parent is None:
                    return None
                parent.disconnect_input(nm)
                return None
        return self

    # do a pruning of a turn tree.
    # prune_nodes - objects to be removed
    # WHOLE objects (constraints) of type 'typ' are pruned, not just some fields
    #  e.g. prune_node=Recipient, typ=Event: would remove the Event?() parent of this Recipient
    #                                        (or the modifier parent of the Event?(), if one exists)
    # if just one branch of the tree can be pruned:
    #   - do that (in place), and return self (the root of the turn tree)
    #   - we just remove the branch, keep operator even if one branch remains
    #   - finally, remove empty branches
    # otherwise, just return None
    def prune_field_values(self, typ, prune_nodes):
        if not prune_nodes:  # no nodes specified for pruning - do nothing
            return self
        if self.not_operator():  # single branch, prune whole tree.
            # TODO: should we check if it really contains the prune node?
            return None
        for p in prune_nodes:
            dp, _ = p.parent_nodes()
            o = [i for i in sorted(dp, key=dp.get) if i.typename() == typ]
            if o:
                for (nm, nd) in o[0].outputs:
                    # for modifiers trees, we typically have the object under a modifier under an operator
                    if nd.is_modifier():
                        nm, nd = nd.outputs[-1]
                    nd.disconnect_input(nm)
        return self.del_childless_ops(None)

    def recurse_sep_inp_constr(self, typ, nm, qual=None):
        if self.is_operator():
            tn = self.typename()
            qual = tn if self.is_qualifier() else None
            prms = [self.inputs[i].recurse_sep_inp_constr(typ, nm, qual) for i in self.inputs]
            if not prms:
                return None
            if len(prms) < 2 and (tn in ['AND', 'OR', 'EQ'] or self.is_qualifier()):
                return prms[0]
            return tn + '(' + ','.join(prms) + ')'
        else:
            if qual:
                return '%s?(%s=%s(%s))' % (typ, nm, qual, id_sexp(self))
            else:
                return '%s?(%s=%s)' % (typ, nm, id_sexp(self))

    def to_separate_input_constr_str_prms(self):
        """
        Makes a sexp with AND of separate constraints for each input.
        """
        typ = self.typename()
        c = []
        for i in self.signature:
            if i in self.inputs:
                n = self.inputs[i]
                c.append(n.recurse_sep_inp_constr(typ, i))
        return c

    def to_separate_input_constr_str(self, combine=None):
        """
        Makes a sexp with AND of separate constraints for each input. If `combine` is given (one node or a list), the
        constraints from all the nodes will be added as one big AND.
        """
        c = self.to_separate_input_constr_str_prms()
        if combine:
            combine = to_list(combine)
            for cmb in combine:
                if cmb.typename() == self.typename():
                    cc = combine.to_separate_input_constr_str_prms()
                    c += cc
        if len(c) == 1:
            return c[0]
        if len(c) > 1:
            return 'AND(' + ','.join(c) + ')'
        return ''

    # ############################################################################################################
    # these functions are defined in a way to avoid circular dependencies, we hide the import inside the functions

    @staticmethod
    def call_construct(sexp, d_context, register=True, top_only=False,
                       constr_tag=RES_COLOR_TAG, no_post_check=False, do_trans_simp=False, no_exit=False):
        """
        :return:
        :rtype: Tuple[Node, List[Exception]]
        """
        from opendf.graph.constr_graph import construct_graph
        g, ex = construct_graph(sexp, d_context, register=register, top_only=top_only, constr_tag=constr_tag,
                                no_post_check=no_post_check, no_exit=no_exit)
        if do_trans_simp:
            from opendf.graph.transform_graph import trans_graph
            g, e = trans_graph(g, add_yield=False)

        return g, ex

    @staticmethod
    def call_construct_eval(sexp, d_context, do_eval=True, register=True, top_only=False, add_goal=False,
                            constr_tag=RES_COLOR_TAG, no_post_check=False, do_trans_simp=False, no_exit=False):
        """
        Constructs the node from the P-expression.

        :return: the constructed nodes and the list of exceptions
        :rtype: Tuple[Node, List[Exception]]
        """
        logger.debug('===constructing: %s' % sexp)
        from opendf.graph.constr_graph import construct_graph
        g, ex = construct_graph(sexp, d_context, register=register, top_only=top_only, constr_tag=constr_tag,
                                no_post_check=no_post_check, no_exit=no_exit)
        if ex is not None:  # re-throw exception
            re_raise_exc(ex)

        if do_trans_simp:
            from opendf.graph.transform_graph import trans_graph
            g, ex = trans_graph(g, add_yield=False)

        e = None
        if do_eval:
            from opendf.graph.eval import evaluate_graph
            e = evaluate_graph(g, add_goal=add_goal)
        return g, e

    def call_eval(self, add_goal, ext_only=False, reeval=False):
        from opendf.graph.eval import evaluate_graph
        if reeval:
            self.evaluated = False
        e = evaluate_graph(self, add_goal=add_goal)
        return e

    def explain(self, goal=None, msg=None):
        """
        Explains why an input is needed. Gives the chain of reasons (from goal, down to this node [possibly - for the
        specified input name]). There may be more than one route from this node to goal - choose one (preferably the
        shortest).
        """
        expl = []
        goal, path = self.get_goal_path(goal)
        if not goal:
            return expl
        logger.debug('Explain call chain:')
        for i, (m, n) in enumerate(path):
            logger.debug('  %d: %s  [%s] -->', i, n, m)
            if m and m != 'RES':
                r = '' if not n.reason else 'in order to %s, ' % n.reason \
                    if m in n.inp_reason else 'I\'m trying to %s' % n.reason
                ir = ''
                if m in n.inp_reason:
                    if n.inp_reason[m] == 'CHILD':  # 'CHILD' --> use the child's reason instead
                        if m in n.inputs and n.inputs[m].reason:
                            ir = 'I need to %s' % n.inputs[m].reason
                    else:
                        ir = 'I need to %s' % n.inp_reason[m]
                if r or ir:
                    logger.debug('    >>>  %s%s', r, ir)
                    expl.extend([r, ir, ''])
        if msg and self.reason:
            logger.debug('    >>>  I\'m trying to %s. %s', self.reason, msg)
            expl.extend(['I\'m trying to %s.' % self.reason, msg])

        logger.debug(':::: %s', ' NL '.join(expl))
        return expl

    # #############################################################################################

    # TODO: may need to change input view for self and/or inp!
    # TODO: need do_constr_check flag? (to disable post construct checks during trans_simple)?
    def wrap_input(self, inp_nm, pref, new_nm=None, suf=None, register=True, iview=None, do_eval=True,
                   do_trans_simp=False):
        """
        Auxiliary function to modify an input - wrap it in a sexp (could be a simple conversion or a complex calc...).

        Example: in TimeSlot().valid_input(), convert an input X of type Time to DateTime?():
                self=TimeSlot, inp_nm='start', par_nm='time', pref='DateTime?(time=', suf=')'

        Note: if the wrapped input node is not registered, it will be registered.

        Node: if called from trans_simple, consider adding do_eval=False

        Note: this is typically called during the evaluation process - either from validate_input or from exec.
              At this stage the initial graph has already been constructed, and we're doing bottom-up eval.
              Adding nodes at this point, means that they are NOT included in the list of nodes to be evaluated, so
              `do_eval` is needed if they are to be evaluated, all their inputs would be evaluated already.

        :param inp_nm: name of parameter to wrap
        :param pref: prefix of sexp
        :param new_nm: if given, then the wrapped input will be put into another name
        :param suf: suffix of sexp, if `None`, closing brackets will automatically be added to match prefix
        :return: self[inp_nm] = construct([pref] + [$# id of curr inp] + [suf])
        """
        suf = suf if suf else ')' * (pref.count('(') - pref.count(')'))  # auto close brackets from prefix
        inp = self.inputs[inp_nm]
        d_context = self.context
        if not inp:
            logger.debug('Warning -Trying to wrap non-existing input %s', inp_nm)
            return
        if inp.id is None:
            d_context.register_node(inp)
        # we use the wrapped 'inp' ONLY for self.
        #   alternatively, we could replace EVERY place 'inp' is used by the wrapped 'inp', but do we always want that?
        #   if we do want to replace all - then use a TEE above the input
        inp.remove_out_link(inp_nm, self)
        sexp = pref + '$#%d' % inp.id + suf
        logger.debug(' - - -Wrapping %d: %s:%d[%s]->%s:%d : %s',
                     inp.id, self.typename(), self.id, inp_nm, inp.typename(), inp.id, sexp)
        iv = iview if iview else self.get_view_mode(inp_nm)  # view_mode of orig inp should be taken care of
        # by the wrapping sexp
        if new_nm and new_nm != inp_nm:
            self.del_input(inp_nm)

        p = d_context.num_registered()
        d, e = self.call_construct(sexp, d_context, register=register, constr_tag=WRAP_COLOR_TAG,
                                   do_trans_simp=do_trans_simp)  #
        if register and d_context.num_registered() > p:
            logger.debug('   - - wrap added nodes %d-%d  %s', p, d_context.num_registered() - 1, sexp)
        nm = new_nm if new_nm else inp_nm
        self.add_linked_input(nm, d, iv)
        if self.typename() == 'TEE':
            self.result = d  # TODO: use set_result()
        if do_eval:
            e = d.call_eval(add_goal=False)
            if e:
                raise to_list(e)[0]

    def wrap_input_multi(self, inp_nm, new_nm, pref, suf=None, register=True, iview=None, do_eval=False,
                         no_post_check=False, do_trans_simp=False):
        """
        Wraps multiple inputs into one input. Prefix must have '%s' to indicate where to put the links to exiting nodes.
        """
        suf = suf if suf else ')' * (pref.count('(') - pref.count(')'))  # auto close brackets from prefix
        inp_nm = to_list(inp_nm)
        inps, ids = [], []

        d_context = self.context
        for nm in inp_nm:
            n = self.inputs[nm]
            if not n:
                logger.debug('Warning -Trying to wrap non-existing input %s', nm)
                return
            if n.id is None:
                d_context.register_node(n)
            inps.append(n)
            ids.append('$#%d' % n.id)
        for i in range(len(inp_nm)):
            inps[i].remove_out_link(inp_nm[i], self)

        sexp = pref % tuple(ids) + suf
        logger.debug('- - -wrapping Mult : %s:%d[%s] : %s', self.typename(), self.id, inp_nm, sexp)

        for nm in inp_nm:
            self.del_input(nm)

        d, e = self.call_construct(sexp, d_context, register=register, constr_tag=WRAP_COLOR_TAG,
                                   no_post_check=no_post_check, do_trans_simp=do_trans_simp)  #
        iv = iview if iview else VIEW.EXT
        self.add_linked_input(new_nm, d, iv)
        if e:
            re_raise_exc(e)
        if do_eval:
            e = d.call_eval(add_goal=False)
            if e:
                re_raise_exc(e)

    def rec_wrap_help(self, pref, typs, skip, suf, register=True, iview=None, only_incompl=False, excl_typs=None,
                      do_trans_simp=False):
        """
        Does recursive wrapping, looking at ALL the inputs of `self`. Continues going deeper into the tree as long as
        it's node types in skip; otherwise, stops.
        """
        for i in self.inputs:
            n = self.input_view(i)
            tn = n.typename()
            if tn in typs or (excl_typs and tn not in excl_typs):  # wrap, but do not eval (we eval only in the end)
                if not only_incompl or not n.is_complete():
                    self.wrap_input(i, pref, suf=suf, register=register, iview=iview, do_eval=False,
                                    do_trans_simp=do_trans_simp)
            elif tn in skip:  # keep going deeper
                n.rec_wrap_help(pref, typs, skip, suf, register, iview,
                                only_incompl, excl_typs=excl_typs, do_trans_simp=do_trans_simp)

    def recursive_wrap_input(self, inp_nm, pref, typs, skip=None, suf=None, register=True, iview=None,
                             only_incompl=False, excl_typs=None, do_eval=True, do_trans_simp=False):
        """
        Recursively descends a tree, following one specific input. Wraps any occurrence of typ (as input view) in the
        given wrapper. Continues going deeper into the tree as long as it's node types in skip; otherwise, stops.
        """
        suf = suf if suf else ')' * (pref.count('(') - pref.count(')'))  # auto close brackets from prefix
        skip = skip if skip else node_fact.operators
        typs = to_list(typs)

        # corner cases - no such input node, or just wrap the input node
        n = self.input_view(inp_nm)
        if not n:
            return
        if n.typename() in typs:
            self.wrap_input(inp_nm, pref, None, suf, register, iview, do_trans_simp=do_trans_simp)
            return

        n.rec_wrap_help(pref, typs, skip, suf, register, iview, only_incompl,
                        excl_typs=excl_typs, do_trans_simp=do_trans_simp)
        if do_eval:
            e = self.call_eval(add_goal=False)
            if e:
                re_raise_exc(e)

    # this is used for trans_simple
    def wrap_otype_cast_obj(self, parent, inp_nm, pref, otyp, suf=None, register=True, iview=None, do_trans_simp=False):
        """
        Recursive wrapping of objects in an operator tree - add a type cast marker. Wraps every `real` object which
        does NOT have an output type of `otyp`.
        """
        logger.debug('- - wrap_otype_cast_obj - %d  %d-%s[%s] %s / %s',
                     self.id, parent.id, parent.typename(), inp_nm, pref, otyp)
        otyp = to_list(otyp)
        if self.is_operator():
            for i in self.inputs:
                if self.is_strict_pos(i):  # only positional inputs of operators
                    n = self.inputs[i]
                    if n.typename() != 'TEE':
                        n = self.input_view(i)
                    n.wrap_otype_cast_obj(self, i, pref, otyp, suf, register, iview, do_trans_simp=do_trans_simp)
        else:
            otn = self.outypename()
            if otn not in otyp:  # if out type mismatches, wrap it with the desired type - it will be auto fixed later
                parent.wrap_input(inp_nm, pref, suf=suf, register=register, iview=iview, do_eval=False,
                                  do_trans_simp=do_trans_simp)

    # add objects to an input -
    # the input may currently have 0, 1, or multiple objects
    def add_objects(self, nm, objs, agg=None):
        if not objs:
            return
        agg = agg if agg else 'SET'
        objs = to_list(objs)
        if nm not in self.inputs:
            oo = objs[0]
            if len(objs)>1:
                s = 'SET(' + ','.join([id_sexp(o) for o in objs]) + ')'
                oo = self.call_construct(s, self.context)
            oo.connect_in_out(nm, self)
        else:
            n = self.inputs[nm]  # NOT view - we don't want to modify the result!
            if n.typename()==agg:  # already has multi objects
                for o in objs:
                    n.add_pos_input(o)
            else:  # single object
                self.disconnect_input(nm)
                s = 'SET(' + ','.join([id_sexp(o) for o in [n]+objs]) + ')'
                oo, _ = self.call_construct(s, self.context)
                oo.connect_in_out(nm, self)

    # #############################################################################################

    # base function. TODO: should we allow to perform implicit accept of prev turn's suggestion?
    def contradicting_commands(self, other):
        return False  # used to be True - verify!

    # convenience function
    def sugg_confirm_acts(self):
        if self.id is None:
            return []
        return ['rerun(id=%d)' % self.id,
                'revise(hasParam=confirm, oldNodeId=%d, new=#True, newMode=extend)' % self.id]

    # base function. Need to implement for each type separately
    # Expresses the idea that this object is complete / validated / ...
    # >> this is different from the object being valid or being evaluated <<
    # e.g. for objects which can hold either a spec (e.g. to external API) or the object representation of
    #      the instance returned object (e.g. again - the object returned from the external API)
    # so far not widely used
    def is_complete(self):
        return False

    # base function - the message to present to the user when Yielding a get_attr()
    #   if val is None, just the 'slot' message, not including the value
    # Note: no need to check if attribute exists - it was already checked by getattr's exec()
    # this is an example of giving a fuller description for an answer, based on the graph
    #    is this too specific? (i.e. logic just for getattr)
    def getattr_yield_msg(self, attr, val=None, plural=None, params=None):
        if val:
            return Message(attr + ' : '  + val)
        return Message(attr)

    # ############################################################################################
    # ########################################### SQL  ###########################################

    def generate_sql(self, **kwargs):
        """
        Generate an SQL query to retrieve the node object from a database.

        :return: the SQL query
        :rtype: Any
        """
        obj = self
        query = None
        if self.is_operator():
            obj = self.get_op_object()
        if obj is not None:
            query = obj.generate_sql_select()
        if query is not None:
            query = self.generate_sql_where(query, None, **kwargs)

        return query

    def generate_sql_select(self):
        """
        Generates the select part of the SQL query, including the FROM clause and, possibly, the JOINs.

        :return: the select part of the SQL query
        :rtype: Any
        """
        return None

    def generate_sql_where(self, selection, parent_id, **kwargs):
        """
        Generates the WHERE clause of the SQL, based on the selection.

        This method may also add fields to the select statement and tables to the FROM/JOIN clauses.

        :param selection: the selection
        :type selection: Any
        :param parent_id: the id of the parent
        :type parent_id: Any
        :param kwargs: additional parameters to be specified by the implementation
        :type kwargs: Dict[str, Any]
        :return: the SQL where clause
        :rtype: Any
        """
        return None

    # ############################################################################################

    # convenience func - get sexp list with param names linked to the (view of the) input nodes
    def inp_list_sexp(self, excl=None):
        excl = excl if excl else []
        return ['%s=$#%d' % (i, self.input_view(i).id) for i in self.inputs
                if i not in excl and self.signature.pretty_name(i) not in excl]

    # transformation of simple graphs (into fuller graphs) - base function
    # returns exception (if any) or None
    # nodes are the nodes in the graph which is being transformed (topological order)
    #       - the transformation may need the graph context - old - given top instead
    # top - top node (goal) in the graph which is now being transformed - (ancestor of self)
    # returns:
    #    node - the node that we'll continue traversing from
    #           normally - self, but possibly another (e.g. if we delete the node, it may be its parent of an input)
    #    error
    # default implementation -
    #   if current node expect a specific, unique input type, then wrap all input objects which are NOT
    #   of that type (going recursively on tree, skipping operators...)
    # note - if using wrap_input inside trans_simple, consider adding the argument: do_eval=False  (wait for
    #        trans_simple to finish recursively traversing the whole graph before evaluating)
    def trans_simple(self, top):
        if self.is_base_type():
            return self, None
        # TODO: maybe have a positive list of types for which we auto wrap?
        for i in self.inputs:
            if i in self.signature:
                typ = to_list(self.signature[i].type)
                if len(typ) == 1 and typ[0].__name__ != 'Node':  # not in NODE:  # one input type which is not generic
                    t = typ[0].__name__
                    if t not in base_types:
                        n = self.input_view(i)
                        n.wrap_otype_cast_obj(self, i, t + '?(', [t] + [
                            'Node'])  # NODE)  # TODO: add the '?' or not - need another flag in signature?
        return self, None

    # remove node from graph,
    # where: parent.inputs[pnm] == self; self.inputs[inm] = nd0
    # after execution, we'll have parent[pnm] = nd0
    def cut_node(self, inm, pnm, parent):
        if inm in self.inputs and pnm in parent.inputs and parent.inputs[pnm] == self:
            nd0 = self.inputs[inm]
            self.disconnect_input(inm)
            parent.disconnect_input(pnm)
            nd0.connect_in_out(pnm, parent)

    # simplify graph - replace self by a different node type - basically renaming from old to new node
    # inp_map - if parameter names are changed. otherwise, will keep same names
    # add checks for valid param names?
    def simplify_rename(self, nm, inp_map=None):
        pnm, parent = self.get_parent()
        prms, nds = [], []
        d_context = self.context
        for i in list(self.inputs.keys()):
            j = inp_map[i] if inp_map and i in inp_map else i
            ii = self.inputs[i]
            prms.append('%s%s' % ('' if is_pos(j) else j + '=', id_sexp(ii)))
            nds.append(ii)
        self.disconnect_input_nodes(nds)
        d, e = self.call_construct('%s(%s)' % (nm, ','.join(prms)), d_context)
        d_context.replace_assign(self, d)
        parent.replace_input(pnm, d)
        return d, e

    # for simplify - in place replacement -
    #   parent will connect to the new node (using the same name as that connecting self)
    # note - if replacing a node which is assigned a name, the name will be reassigned to the new node!
    def replace_self(self, nd):
        self.context.replace_assign(self, nd)
        pnm, parent = self.get_parent()
        self.disconnect_input_nodes([nd])
        parent.replace_input(pnm, nd)

    # in simplify - remove cast node which wraps a leaf (with data)
    # give name of input to check (inp)
    # optionally - check if the wrapper (cast) is in a specified list of types
    # the data is under 'pos1', unless dt is given
    # Note: if replacing a node which is assigned a name, the name will be reassigned to the new node!
    def cut_cast(self, inp, typ=None, dt=None):
        if inp in self.inputs and (not typ or self.inputs[inp].typename() in to_list(typ)) and self.inputs[inp].dat:
            dt = dt if dt else 'pos1'
            self.context.replace_assign(inp, self.inputs[inp].inputs[dt])
            self.replace_input(inp, self.inputs[inp].inputs[dt])

    # similar to trans_simple, but typically used in the opposite direction - going from complex to simple
    # for simplify - we know that NO evaluation is run (at least for now)  (any reason/case we should?)
    #  - so free to use inputs[i] instead of input_view(i)
    def simplify(self, top, mode):
        return self, None, mode

    # like simplify - but called bottom up, does more local changes
    def pre_simplify(self, top, mode):
        return self, None, mode

    # add one more positional input to an operator
    # convenience function
    # Note: it does NOT check that it's legal to add the additional positional input to operator - user's
    #       responsibility!
    def add_pos_input(self, nd, view=None):
        if self.is_operator() or POS in self.signature:
            n = self.max_pos_input() + 1
            nd.connect_in_out(posname(n), self, view)

    # should use this one instead - there COULD be nested operator
    # this is used BEFORE the modifier has been converted (in eval) to a constraint (is False after conversion)
    def is_modifier_tree(self, outyp=None):
        outyp = to_list(outyp) if outyp else []
        if self.is_modifier() and (not outyp or self.outypename() in outyp):
            return True
        obs = self.get_op_objects()
        m = [i for i in obs if i.is_modifier() and (not outyp or i.outypename() in outyp)]
        return False if len(obs) != len(m) or not m else True

    # this is used AFTER the modifiers have been converted to constraints (is False before conversion)
    def is_constraint_tree(self, typ):
        obs = self.get_op_objects()
        return all([i.typename() == typ and i.constraint_level > 0 for i in obs])

    # #############################################################################################
    # ######################################### modifiers #########################################

    # return a list of subfields :
    def get_present_subfields(self, pref=None, fields=None):
        pref = pref if pref else ''
        dlm = '' if not pref else '.'
        fields = fields if fields else []
        if self.typename() in base_types + node_fact.leaf_types + ['Empty', 'Clear']:
            if pref and pref not in fields:
                fields.append(pref)
            return fields
        for i in self.inputs:
            p = pref if self.is_operator() else pref + dlm + i
            n = self.input_view(i)
            fields = n.get_present_subfields(p, fields)
        return fields

    def get_subfields_with_level(self, levels, pref=None):
        fields = self.get_present_subfields(pref=pref)
        if not levels:
            return fields
        levels = to_list(levels)
        ff = list(set(flatten_list([['.'.join(i.split('.')[:j]) for i in fields] for j in levels])))
        return ff

    def get_tree_subfields(self, typ=None):
        objs = self.get_op_objects(typs=typ)
        fields = []
        for o in objs:
            fields = o.get_present_subfields('', fields)
        return fields

    # self is a constraint tree, possibly made of multiple trees (each corresponding to a different conversation turn)
    # return a list of trees - one per turn
    # makes some strong assumptions on how the tree was created (esp - relying on node.create_turn)
    #       - may need to be made more robust! (e.g. additional wrapper per turn, added tags, ...)
    #        hack - if created_turn<0 then same effect as force_multi
    def get_tree_turns(self, force_multi=False):
        if self.typename() != 'AND':  # assuming AND is always the root of multi turn tree
            return [self]
        # it could be a single turn tree, with AND at its root - check if all objects are from the same turn
        if not force_multi:
            found, turns = False, []
            for i in self.inputs:
                if not found:
                    m = self.input_view(i).get_op_object()
                    if m:
                        t = m.created_turn
                        if t < 0 or turns and t not in turns:
                            found = True
                        else:
                            turns.append(t)
            if not found:
                return [self]
        return [self.input_view(i) for i in self.inputs]

    # check if a turn tree is "complex"
    # we define complex as either:
    #   - having an OR
    #   - having nested negative operators
    #   - having a negative operator above another operator (except LIKE, EQ)
    def turn_is_complex(self):
        nodes = self.topological_order()
        if [i for i in nodes if i.typename() == 'OR']:
            return True
        negs = [i for i in nodes if i.typename() in ['NOT', 'NEQ']]
        for i, n in enumerate(negs):
            dp, _ = n.parent_nodes()
            for j, m in enumerate(negs):
                if j > i and m in dp:
                    return True
        for i in negs:
            for j in i.inputs:
                k = i.inputs[j]
                if k.is_operator() and k.typename() not in ['LIKE', 'EQ']:
                    return True
        return False

    # true if other modifier contradicts this modifier
    def modifier_contradiction(self, other):
        return False

    # convert a modifier:
    # self - modifier, constr - all the modifiers, parent - the parent of constraint
    # this is run during the evaluation of the node, after all the inputs have been evaluated
    # it's possible to do some additional wrapping and transformations which were not possible after the initial
    # construction. It's not the same as using valid_input, since convert_modifier runs after ALL inputs of the parent
    # have been evaluated, while valid_input can not guarantee sibling inputs have been evaluated
    def convert_modifier(self, parent, constr, obj=None):
        pass

    # self - constraint tree (multi turn), parent - parent of constraint
    def convert_modifiers(self, parent, obj=None):
        mods = [m for m in self.get_op_objects() if m.is_modifier()]
        for m in mods:
            m.convert_modifier(parent, self, obj)

    # 1. decide if pruning of a previous modifier (prev) is needed (and to what degree) - depending on if it contradicts
    #     (completely or partially) self (a later turn modifier). (curr is "current" ("later") tree)
    # 2. if necessary - prune the prev modifier (completely or partially)
    # return - 2 cases:
    #  1) None - means completely discard prev modifier
    #  2) the pruned prev modifier (i.e. already modified (in place) if applicable, or unmodified if not)
    # should this be cut to smaller base functions (e.g. decide / prune)?
    @staticmethod
    def prune_modifier_tree(prev, curr, prep, curr_idx, prm=None):
        return prev

    # base function - in case any pre-processing needs to be done before pruning
    @staticmethod
    def prepare_prune(turns):
        return None

    # base function - in case any post-processing needs to be done before pruning
    @staticmethod
    def post_prune(root, turns):
        return None

    # prune multi-turn modifier tree, relative to the newest turn
    # self is the root of the tree
    # force_multi - force to interpret modifier tree as multi turn, if it has AND at root
    def prune_modifiers(self, prm=None, force_multi=False):
        turns = self.get_tree_turns(force_multi=force_multi)
        # TODO: we should go over all turns (even if only one) which have multi terms and prune them in case of
        #   internal contradiction (either completely, or partially). (a turn may be complex - with ORs etc)
        if len(turns) < 2:
            return  # single modifier - nothing to do
        typ = turns[0].get_op_object()
        prep = typ.prepare_prune(turns)
        k = list(self.inputs.keys())
        for i1, k1 in enumerate(k):
            if k1 in self.inputs:  # not pruned yet
                for i2, k2 in enumerate(k):
                    if k2 in self.inputs:
                        if i1 > i2:
                            t1, t2 = turns[i1], turns[i2]
                            m = typ.prune_modifier_tree(t2, t1, prep, i1, prm)
                            #  m is None means nothing is left of the turn - remove it.
                            #  if m is not None - then it has already been modified (in place) - nothing to do
                            if not m:
                                self.disconnect_input(k2)
        # finally - there may be some additional post-proc, e.g. not just pair-wise on turns...
        typ.post_prune(self, turns)

    # if a branch of the tree is dead (AND/OR/NOT with no children) - prune it
    # if AND/OR with one child, then remove the AND/OR and reconnect the child with the parent directly
    def prune_tree_ops(self):
        if self.is_operator() and len(self.inputs) == 0:
            pnm, parent = self.get_parent()
            parent.disconnect_input(pnm)
            return
        if self.typename() in ['AND', 'OR'] and len(self.inputs) == 1:
            nm = list(self.inputs.keys())[0]
            self.replace_self(self.inputs[nm])
        for i in self.inputs:
            self.inputs[i].prune_tree_ops()

    # self is root of turn tree. Clean unused nodes/branches. May leave top AND even not needed
    def clean_turn_tree(self):
        if self.not_operator():
            return
        objs = self.get_op_objects()
        for o in objs:
            if len(o.inputs) == 0:
                pnm, parent = o.get_parent()
                if parent:
                    parent.disconnect_input(pnm)
        for i in list(self.inputs.keys()):
            if i in self.inputs:
                self.inputs[i].prune_tree_ops()

    # truncate a constraint tree to include only one field of the original type. creates a sexp
    @staticmethod
    def trunc_constr_recurse(root, ptype, ctype, field, allow_single):
        if root.is_operator():
            chld = [Node.trunc_constr_recurse(root.input_view(i), ptype, ctype, field, allow_single) for i in
                    root.inputs if
                    is_pos(i)]
            children = [i for i in chld if i]
            l = len(children)
            if l > 1 or ((root.is_qualifier() or root.typename() in allow_single) and l > 0):
                return '%s(%s)' % (root.typename(), ','.join(children))
            elif l == 1:
                return children[0] + '()' if '(' not in children[0] and not children[0].startswith('$') else children[0]
            else:
                return ''
        tp = root.typename()
        if tp == ptype:
            if field in root.inputs:
                return Node.trunc_constr_recurse(root.input_view(field), ptype, ctype, field, allow_single)
            return ''
        if ctype is None or tp == ctype:  # should check if parent is really ptype...
            return id_sexp(root)
        return ''

    # call creation of sexp describing a constraint tree including only one field of the original type
    # e.g. get_truncated_constraint_tree('Event', 'TimeSlot', 'slot')
    #   takes only the 'slot' input nodes from an Event?() tree, and creates a new TimeSLot?() tree with those nodes,
    #   keeping the (relevant surviving) operators of original tree.
    # in practice, this function first creates a sexp (where the original objects - DateTime objects in the example)
    #   are linked to (they are not duplicated), and then constructs it.
    # the truncation also removes unnecessary aggregators (aggs which have only one surviving child)
    #   - if this is not wanted, use allow_single to indicate which aggs should be kept - remember to include 'NOT'
    @staticmethod
    def get_truncated_constraint_tree(root, ptype, ctype, field, allow_single=None, copy_turn=True):
        allow_single = allow_single if allow_single else ['NOT']
        sexp = Node.trunc_constr_recurse(root, ptype, ctype, field, allow_single)
        if sexp:
            d_context = root.context
            if sexp.startswith('$#'):
                r = d_context.get_node(int(re.sub('[)(]', '', sexp[2:])))
            else:
                r, e = Node.call_construct(sexp, d_context)
            if copy_turn:
                r.created_turn = root.created_turn
            return r
        return None

    def get_inputs(self, inp):
        inp = to_list(inp)
        inps = [self.inputs[i] if i in self.inputs else None for i in inp]
        return inps[-1] if len(inps) == 1 else None if len(inps) == 0 else tuple(inps)

    def get_input_views(self, inp):
        inp = to_list(inp)
        inps = [self.input_view(i) if i in self.inputs else None for i in inp]
        return inps[-1] if len(inps) == 1 else None if len(inps) == 0 else tuple(inps)

    def reorder_inp(self):
        ii = list(self.inputs.keys())
        nms = [i for i in ii if not is_pos(i)]
        pos = sorted([i for i in ii if is_pos(i)])
        inps = AliasODict()
        for i in self.signature:
            if i in nms:
                inps[i] = self.inputs[i]
        for i in pos:
            inps[i] = self.inputs[i]
        self.inputs = inps
        # sanity check
        for i in ii:
            if i not in self.inputs:
                raise SemanticException('Error - reorder inputs - missing input: %s' % i)

    def reorder_inputs_recurr(self, follow_res=False):
        self.reorder_inp()
        for i in self.inputs:
            self.inputs[i].reorder_inputs_recurr(follow_res)
        if follow_res:
            self.result.reorder_inputs_recurr(follow_res)

    def get_single_inp_name(self):
        if len(self.inputs) == 1:
            nm = list(self.inputs.keys())[0]
            return self.signature.pretty_name(nm)
        return None

    def get_single_input_view(self):
        if len(self.inputs) == 1:
            nm = self.get_single_inp_name()
            return self.input_view(nm)
        return None

    # select an exception e from a list of exceptions (excs), such that e is attached to the "highest" node under self
    def get_top_exceptions(self, excs):
        ex_nds = [e.node for e in excs]
        nds = self.topological_order()
        es = [n for n in nds if n in ex_nds]
        if es:
            return [e for e in excs if e.node==es[-1]]
        return []

def create_node_from_dict(node_name, **kwargs):
    """
    Creates a node string representation from the `node_name` and the (key, value) pairs like:
    `node_name`(`key_1`=`value_1`, ..., `key_n`=`value_n`). In addition, it also filters `None` values and use the id
    of the value, if it is a Node.

    :param node_name: the name of the node
    :type node_name: str
    :param kwargs: the parameters of the node
    :type kwargs: Dict[str, Any]
    :return: the string representation of the node
    :rtype: str
    """
    params = []
    for key, value in kwargs.items():
        if value is None:
            continue
        if isinstance(value, Node):
            value = id_sexp(value)
        params.append(f"{key}={value}")

    return f"{node_name}({', '.join(params)})"


def search_for_types_in_parents(node, types=()):
    """
    Searches for the node types (defined in `types`) on the list of parent nodes. If found, returns the type of the
    first parent node, whose type is in `types`.

    :param node: the current node
    :type node: Node
    :param types: the possible types
    :type types: Set[str]
    :return: the first type found in the parents list, if exists; otherwise, `None`
    :rtype: str or None
    """
    _, parent = node.get_parent()
    while parent:
        typename = parent.typename()
        if typename in types:
            return typename
        _, parent = parent.get_parent()

    return None


# get differentiating fields in a list of objects
def get_diff_fields(objs, ignore_fields=None):
    fields = defaultdict(set)
    for o in objs:
        for i in o.inputs:
            v = o.get_dat(i)
            if v is not None:
                fields[i].add(v)
    dfields = {}
    ignore_fields = ignore_fields if ignore_fields else []
    for f in fields:
        if f not in ignore_fields:
            if len(fields[f])>1:
                dfields[f] = fields[f]
    return dfields


# collect all the different values multiple objects have for a specific input name
def collect_values(objs, field):
    return list(set([o.get_dat(field) for o in objs if o.get_dat(field)]))
