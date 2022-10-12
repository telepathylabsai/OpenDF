"""
Framework functions which are part of the graph execution engine framework.
"""
import logging
import re

from opendf.defs import VIEW, POS, MSG_YIELD, SUGG_LABEL, SUGG_MSG, SUGG_IMPL_AGR, is_pos, posname, \
    posname_idx, EnvironmentDefinition, Message  # , NODE
from opendf.exceptions.df_exception import DFException, MissingValueException, \
    WrongSuggestionSelectionException, EmptyEntrySingletonException, IncompatibleInputException, \
    InvalidTypeException, MultipleEntriesSingletonException, NoReviseMatchException, ElementNotFoundException, \
    InvalidResultException
from opendf.exceptions.python_exception import SemanticException
from opendf.graph.node_factory import NodeFactory
from opendf.graph.nodes.framework_objects import Str, Bool, Int
from opendf.graph.nodes.framework_operators import Operator
from opendf.graph.nodes.node import Node
from opendf.utils.utils import get_type_and_clevel, comma_id_sexp, id_sexp, to_list
from opendf.exceptions import re_raise_exc

logger = logging.getLogger(__name__)

node_fact = NodeFactory.get_instance()

environment_definitions = EnvironmentDefinition.get_instance()

# ################################################################################################


# TODO: implement refer as a real function, with dynamic output type
#   - still some leftovers from being a "special function"

# TODO: in case of multiple matches - choose just one, or allow to return multiple?
#     - e.g. input flag 'singleton'[bool] (default value True) ??

# TODO: add flag to limit refer only to result nodes

# basically - the match condition should allow all that a sparql query allows
#  - complex conditions over transitive combinations type, inputs, outputs...
def get_refer_match(d_context, all_nodes0, goals0, is_ref_goal=False, parent=None, pos1=None, pos1view=None, role='',
                    mid=None, midId='', type='', cond=None, condview=None, midtype='', nid='', no_fallback=False,
                    force_fallback=False, multi=True, no_eval=True, match_miss=False, params=None,
                    search_last_goal=False, merge_equiv=True, merge_equiv_res=True, avoid_nodes=None,
                    belowtype=None):
    all_nodes = [n for n in all_nodes0] if all_nodes0 else []
    all_nodes = [n for n in all_nodes if not n.hide]
    goals = [g for g in goals0] if goals0 else []
    if goals and search_last_goal:  # search also on last (current) goal
        last_nodes = Node.collect_nodes([d_context.goals[-1]])  # it is dynamically built, so we need to collect nodes
        all_nodes.extend([n for n in last_nodes if n not in all_nodes])

    if avoid_nodes:
        all_nodes = [i for i in all_nodes if i not in avoid_nodes]
    matches = []
    nodes = all_nodes
    if isinstance(pos1, str):
        pos1, _ = Node.call_construct(pos1, d_context)
    if not force_fallback:
        if pos1:  # type constraint - could be an aggregated constraint (AND/OR/...)
            candidates = [n for n in nodes if
                          pos1.match(n, iview=pos1view, oview=VIEW.INT, check_level=True, match_miss=match_miss)]
            matches = Node.rank_by_order(candidates, goals, follow_res=True)
            nodes = matches  # allow further filtering
        if type:  # TODO: move this before pos1 - for efficiency?
            # tp = type  # type is a string - always get res.dat
            tp, clevel = get_type_and_clevel(type)
            targ_type = re.sub(' ', '_', re.sub('\?', '', tp))
            # TODO: should we complain if this is not a known type name?
            matches = []
            for n in nodes:
                if (targ_type == 'Node' or n.typename() == targ_type) and n.constraint_level == clevel:
                    matches.append(n)
            matches = Node.rank_by_order(matches, goals, follow_res=True)
            nodes = matches  # allow type + role
        if cond:
            t = pos1.typename() if pos1 else type
            # opening matches to list of objects before matching - TODO: is this the general thing to do?
            objs = list(set(sum([n.get_op_objects(typs=[t]) for n in matches], [])))
            candidates = [n for n in objs if
                          cond.match(n, iview=condview, oview=VIEW.INT, check_level=True, match_miss=match_miss)]
            nodes = candidates  # allow further filtering
            matches = candidates
        if midtype:
            tp, clevel = get_type_and_clevel(midtype)
            targ_type = re.sub(' ', '_', re.sub('\?', '', tp))
            # TODO: should we complain if this is not a known type name?
            matches = []
            # allows looking for : midtype=Any? - will match any constraint
            for n in nodes:
                pt = n.parent_nodes(res=True)[0]
                found = False
                for p in pt:
                    if not found:
                        if (targ_type == 'Node' or p.typename() == targ_type) and p.constraint_level == clevel:
                            matches.append(n)
                            found = True
            matches = Node.rank_by_order(matches, goals, follow_res=True)
            nodes = matches  # allow further filtering
        if belowtype:
            tp, clevel = get_type_and_clevel(midtype)
            targ_type = re.sub(' ', '_', re.sub('\?', '', tp))
            matches = []
            for n in nodes:
                ch = n.topological_order()[:-1]  # children. allow res?
                found = False
                for c in ch:
                    if not found:
                        if (targ_type == 'Node' or c.typename() == targ_type) and c.constraint_level == clevel:
                            matches.append(n)
                            found = True
            matches = Node.rank_by_order(matches, goals, follow_res=True)
            nodes = matches  # allow further filtering
        if role:  # role constraint (string) - may come together with type constraint
            # TODO: allow role to be a period separated string, e.g. role='aa.bb.cc' means there is a path to the
            #   candidate node which passed through the inputs labels - i.e there is a node N such that:
            #   N.inputs['aa'].inputs['bb'].inputs['cc'] == candidate
            #   should allow alias! (tricky when "going up"). maybe do this as filtering one step at a time
            matches = {}
            for n in nodes:
                for nm, o in n.outputs:
                    if (nm == role or nm == o.signature.real_name(
                            role)) and n not in matches:  # add each node only once
                        matches[n] = n.score_by_order(goals, follow_res=True)
            matches = sorted(matches, key=matches.get)
        if mid:  # filter nodes which have 'mid' in their parents
            matches = [n for n in matches if mid in n.parent_nodes(res=True)[0]]
        if midId:  # filter nodes which have 'midId' in their parents midId is a string
            nd = d_context.get_node(midId)  # midId is a string
            matches = [n for n in matches if nd in n.parent_nodes(res=True)[0]]
        if nid:
            nd = d_context.get_node(nid, raise_ex=False)  # midId is a string
            matches = [] if nd is None else [nd]

    if not matches and not no_fallback and (pos1 or params and 'fallback_type' in params):  # and not matches1
        # use the constraint given in posname(1) to search external data
        # alternatively, if no pos1 give, but fallback_type specified in params
        # evaluate externally created result, unless explicitly given no_eval=True in inputs
        fbnode = pos1 if pos1 else node_fact.sample_nodes[params['fallback_type']]
        if not pos1:
            params['dummy_filt'] = True  # needed?
            params['context'] = d_context  # sample node does not have a context
        do_eval = not (no_eval or is_ref_goal)
        if fbnode.not_operator():
            matches = fbnode.fallback_search(parent, all_nodes, goals, do_eval=do_eval, params=params)
            if not matches:
                matches = fbnode.fallback_search_harder(parent, all_nodes, goals, do_eval=do_eval, params=params)
        else:
            # for operators - find type they operate on (assuming unique), do fallback search on that
            # (NO consraints - use an "empty" node of that type), open result set, then filter with operator tree
            o = fbnode.get_op_type()
            if o:
                # object found. That type's fallback search should explicitly deal with this case. Pass pos1 as parent
                #   e.g. Recipient: is_sub= self==node_fact.sample_nodes[self.typename()] and parent.is_operator()
                pp = node_fact.sample_nodes[o.__name__]
                matches = pp.fallback_search(fbnode, all_nodes, goals, do_eval=do_eval, params=params)
                if not matches:
                    matches = pp.fallback_search_harder(fbnode, all_nodes, goals, do_eval=do_eval, params=params)
        if cond and matches:
            objs = list(set(sum([n.get_op_objects(typs=[fbnode.typename()]) for n in matches], [])))
            matches = [n for n in objs if
                       cond.match(n, iview=condview, oview=VIEW.INT, check_level=True, match_miss=match_miss)]
    # TODO: review - in case of multiple matches - do we really return a list, or a SET node?
    if merge_equiv:
        m = []
        for ii in matches:
            i = ii.res if merge_equiv_res else ii
            if not any([i.equivalent_obj(j) for j in m]):
                m.append(i)
        matches = m
    if len(matches) > 1 and not (multi or is_ref_goal):
        return [matches[0]]
    return matches


def graph_has_exp(root, d_context, follow_res=True, sexp=None, sub=None):
    """
    Checks if a graph contains an expression (given as either string or root node).
    """
    if not sexp and not sub:
        return None
    nodes = root.topological_order(follow_res=follow_res)
    if sexp:  # overwrite sub
        sub, e = Node.call_construct(sexp, d_context, register=False)
        if e:
            return None
    return get_refer_match(d_context, nodes, root, pos1=sub)


# TODO: allow refer WITHIN the current goal? (e.g. on newly created nodes)
class refer(Node):
    def __init__(self):
        super().__init__()  # Dynamic output type

        self.signature.add_sig(posname(1), Node, view=VIEW.INT)
        # constraint on node type : Constraint[type](optional constraints) - currently just node type

        self.signature.add_sig('role', Str)  # role constraint - match nodes which play this role
        self.signature.add_sig('mid', Node)  # select nodes which have a specified node as one of their ancestors
        self.signature.add_sig('midId', Str)  # select nodes which have a specified node ID as one of their ancestors

        self.signature.add_sig('type', Str)
        # search for node by type, but input is Str - so program does not create a node of this type

        self.signature.add_sig('cond', Node)
        # extra condition to match - useful e.g. when top node is operator (not the target type)

        self.signature.add_sig('midtype', Str)  # like 'type', but looking for midtype in ancesters
        self.signature.add_sig('id', Str)  # node id or name
        self.signature.add_sig('no_fallback', Bool)  # do NOT fall back to external search if no results found
        # for fallback search - only pos1 input makes sense (assuming others not given)
        # TODO: maybe by default should be no fallback?

        self.signature.add_sig('force_fallback', Bool)  # do fallback search only - e.g. force creating a new copy
        self.signature.add_sig('multi', Bool)  # return multiple results

        self.signature.add_sig('no_eval', Bool)
        # don't eval external (by default - we do evaluate externally generated graph)

        self.signature.add_sig('no_res', Bool)

        self.signature.add_sig('match_miss', Bool)  # extra parameter to pass to match
        # TODO: add goal/mid... like in revise()? (currently, refer does not explicitly look at paths)

        self.signature.set_multi_res(True)  # can return multiple objects

    def valid_input(self):
        if posname(1) not in self.inputs and 'role' not in self.inputs and \
                'out' not in self.inputs and 'type' not in self.inputs and 'id' not in self.inputs:
            raise IncompatibleInputException("refer node needs a role/type/out/id constraint", self)
        if 'cond' in self.inputs and not (posname(1) in self.inputs or 'type' in self.inputs):
            raise IncompatibleInputException("refer - cond needs either pos1 or type as input", self)

    # refer - exec
    def exec(self, all_nodes=None, goals=None):
        no_res = self.inp_equals('no_res', True)
        if no_res and goals:
            all_nodes = Node.collect_nodes(goals, follow_res=False)
        all_nodes = all_nodes if all_nodes else []
        all_nodes = [n for n in all_nodes if not n.hide]
        # all_nodes = [n for n in all_nodes if n!=self]  # prevent refer to find itself
        goals = goals if goals else []
        pos1, pos1view = self.get_inp_view_and_mode(posname(1)) if posname(1) in self.inputs else (None, None)
        type = self.get_dat('type') if 'type' in self.inputs else ''
        cond, condview = self.get_inp_view_and_mode('cond') if 'cond' in self.inputs else (None, None)
        midtype = self.get_dat('midtype') if 'midtype' in self.inputs else ''
        role = self.get_dat('role') if 'role' in self.inputs else ''
        mid = self.input_view('mid') if 'mid' in self.inputs else None
        midId = self.get_dat('midId') if 'midId' in self.inputs else ''
        nid = self.get_dat('id') if 'id' in self.inputs else ''
        # is_ref_goal  - self (refer) has a role of 'goal' (as input to revise)
        is_ref_goal = any([True for (m, d) in self.outputs if m in ['goal', 'midGoal']])
        no_fallback = self.inp_equals('no_fallback', True)
        force_fallback = self.inp_equals('force_fallback', True)
        no_eval = self.inp_equals('no_eval', True)
        multi = self.inp_equals('multi', True)
        match_miss = self.inp_equals('match_miss', True)

        matches = get_refer_match(self.context, all_nodes, goals, is_ref_goal, self, pos1, pos1view, role, mid, midId,
                                  type, cond, condview, midtype, nid, no_fallback, force_fallback, multi, no_eval,
                                  match_miss, avoid_nodes=[self])
        if not matches:
            if pos1 is not None:
                raise pos1.search_error_message(self)
            raise self.search_error_message(self)
        if (multi or is_ref_goal) and len(matches) > 1:  # create an aggregate SET with links to the found matches
            sexp = 'SET(' + comma_id_sexp(matches) + ')'
            m, e = self.call_construct(sexp, self.context)
            self.set_result(m)
            if not self.inp_equals('no_eval', True):
                e = m.call_eval(add_goal=False)  # do we need to propagate exception?
                if e:
                    raise e
        else:
            m = matches[0]
            self.set_result(m)

    def yield_failed_msg(self, params=None):
        m = self.inputs[posname(1)].describe(params=params)
        if m.text:
            return Message('I could not find any ' + m.text, objects=m.objects)
        return Message('', objects=m.objects)


# ################################################################################################
# ############################################ revise ############################################


# merge two constraint trees
#  - merge depends on mode
#  - inputs could actually not be trees or constraints - handle that (or do that in a wrapper?)
# remember this actually may not be exactly a tree!
# mode may need two components - logical op (and/or/overwrite), and simplification type (compact/unify/leave as is...)??
# to simplify - assume input IS two constraint trees (of same type),
#               logical op is AND, and we want to unify (e.g. for creating event)
#               also - assume we always look at res
# TODO: disabled "smart" tree modifications
def merge_constraints(old, new, mode):
    """
    Merges two constraint trees.
    """
    d_context = old.context
    op = 'AND' if mode == 'addAnd' else 'OR' if mode == 'addOr' else 'LAST'  # TODO: if mode=='addLast'
    root = node_fact.create_node_from_type_name(d_context, op, False)  # create temp node (don't register yet)
    d_context.register_node(root)
    root.out_type = new.out_type
    root.constraint_level = max(new.constraint_level, old.constraint_level)
    new.connect_in_out(posname(1), root)
    old.connect_in_out(posname(2), root)
    return root


# create a new aggregator, which will have as inputs new_beg and a POINTER to old beg
# (we don't want to copy the old one - it may be big!, and we don't want to modify the old one)
def create_aggregate_node(old_beg, new_beg, mode):
    """
    Create a new aggregator, which will have as inputs `new_beg` and a POINTER to `old_beg`.
    """
    return merge_constraints(old_beg.res, new_beg.res, mode)


# auto reorder inputs - called during graph duplication in revise -
#   reorder inputs in the duplicated nodes if allowed by signature
# this can be useful to shift the focus of the dialog to the most recently mentioned topic
# Note - dataflow in principle does not care about the order the inputs of a node are evaluated (as long as they are
#        not inputs of each other), so changing the order should not break anything. Still, we control this in the
#        signature - both at the node level (currently opt-in), and at the input-pair level.
# nd - is the node whose inputs' order we may want to change
# if an input of nd is one of the nodes in raise_nodes, then try to raise its position in the inputs orderedDict
def auto_reorder_inputs(nd, raise_nodes):
    if nd.signature.allow_reorder:
        inps = list(nd.inputs.keys())
        rs = [i for i in inps if nd.inputs[i] in raise_nodes]  # more recent inputs
        n = len(inps)
        # for now, do a simple bubble-sort-like reordering (any use case where we need more?)
        for i in range(n):
            for j in range(i + 1, n):
                if inps[i] not in rs and inps[j] in rs and (i, j) not in nd.signature.inp_dep:
                    inps[i], inps[j] = inps[j], inps[i]
        nd.inputs = nd.inputs.duplicate(inps)


# rev, mid, below - needed only for custom new_beg
def duplicate_subgraph(root, old_beg, new_beg, mode, rev=None, mid=None, below=None, inp_nm=None, omit_dup='omit_dup'):
    """
    Duplicate a computation subgraph - for revise.

    Given the old subgraph, `old_beg` (the root node corresponding to oldLoc) and `new_beg` (the root node of new),
    duplicate the subgraph from oldLoc up to root.

    Note: subgraph could be of general shape (e.g. not assuming it's a chain)

    Note: nodes with mutable=True are NOT duplicated. This is supposed to support a kind of shared memory. It
    complicates some of the code - so be careful. This still needs to be verified! for now, thinking of use for
    mutable nodes which are 'almost' leaves, and using with 'hasParam' + 'extend'.
    TODO: check other usages!
    TODO: if `old_beg` is mutable, then maybe just modify the mutable node, and then duplicate just the top goal node
        - no need to duplicate the whole graph

    :param root: the root node
    :type root: Node
    :param old_beg: the root node corresponding to oldLoc
    :type old_beg: Node
    :param new_beg: the root node of new
    :type new_beg: Node
    :param mode:
    one of:
        'new' (default) - duplicate graph from oldLoc (NOT including oldLoc) up to root, and place `new_beg` where
                          `old_beg` was;
        'overwrite' - `new_beg` is typically the same type as `old_beg` - they have same input types.
                       Copy `old_beg`, and overwrite its inputs with those of `new_beg`. Other inputs of old_beg
                       are copied unchanged;
                       TODO: not robust to deep graphs!
        - 'extend' - (typically used with `hasParam` for oldLoc) - duplicate including `old_beg`, and then add new
                     UNDER it (as input). `new_beg` is used to extend one input [inp_nm] of `old_beg`. `new_beg` is the
                     same type as `old_beg.inputs[inp_nm]`;
        - 'addAnd' - (for constraint modification) new is added as AND(new, old), which then gets simplified
                     TODO: add simplification mode!
        - 'addOr' - similar to addAnd, but with OR;
        - custom mode (per type) - a string starting with ';'. This will call old_beg.create_new_beg(new_beg, mode),
                                   which may also affect duplication behavior;
        - 'add' - wrap old and new in an aggregator node. TODO: for now it's just adding 'AND' - add other aggs!
    :type mode: str
    :param inp_nm: for hasParam - the name of the param
    :type inp_nm: Optional[str]
    :param omit_dup: inputs with these TAGS will not be connected to the duplicated nodes. It means that when doing
    revision, all the inputs of the specified names "above" the `new` node are removed. By default, don't duplicate
    inputs with an 'omit_dup' tag. This is part of a design pattern more than part of the framework
    :type omit_dup: List[str] or str
    :return: the duplicated graph
    :rtype: List[Node]
    """
    except_on_wrong_inp = True
    d_context = root.context
    inp_nm = inp_nm if inp_nm is not None else ''
    omit_dup = omit_dup if omit_dup else []
    if isinstance(omit_dup, str):
        omit_dup = omit_dup.split(';')
    old_subgraph = old_beg.get_subgraph(root)
    # handle mutable nodes - do not duplicate them, or any node under them
    keep_old = [i.mutable for i in old_subgraph]
    for i, c in enumerate(keep_old):
        if c:
            subnodes = old_subgraph[i].topological_order()
            for j in range(i):
                if old_subgraph[j] in subnodes:
                    keep_old[j] = True

    if mode in ['addAnd', 'addOr', 'addLast']:
        new_beg = create_aggregate_node(old_beg, new_beg, mode)
    new_subgraph = []
    # list of new nodes corresponding to nodes in old subgraph. Keeps order: new[i] corresponds to old[i]

    dup_old_beg = mode in ['extend', 'overwrite', 'auto', 'modif']  # make a duplicate of the old beg?
    # i.e. attach new beg to old beg or replace old beg by new beg

    ignore = []  # for custom `create_new_beg` only. avoids double in/out linking for special cases
    if mode.startswith(';'):
        new_beg, dup_old_beg, done, ignore, mode = old_beg.create_new_beg(new_beg, mode, rev, root, mid, below)
        if done:  # shortcut - in some cases there may be no need to actually duplicate
            # e.g. with a mutable node type, which holds data internally - `create_new_beg` could just do the
            # internal modification, and that may be enough (higher nodes don't need resetting...)
            return old_subgraph
    for i, n in enumerate(old_subgraph):
        if n != old_beg or dup_old_beg:
            if keep_old[i]:  # mutable (or under mutable) - do not duplicate
                # TODO: verify that mutable works correctly in different positions
                nw = n
            else:
                nw = node_fact.create_node_from_type_name(d_context, n.typename(), register=True)
                nw.copy_info(n)
                nw.just_dup = True  # TODO: call `node.on_dup()` for `new_subgraph`, then turn it off!
                nw.dup_of = n
                if n in d_context.exception_nodes:
                    # if orig node had an exception - mark the new as a copy of an exception node
                    d_context.copied_exceptions.append(nw)
        else:  # no need to duplicate `old_beg` - we replace it with the `new_beg`
            nw = new_beg
        new_subgraph.append(nw)
    old_idx = {o: i for i, o in enumerate(old_subgraph)}  # node order in `new_subgraph` same as in `old_subgraph`

    # fill/update inputs & outputs for new and old
    for ig, o in enumerate(old_subgraph):
        n = new_subgraph[ig]
        for nm in o.inputs:
            omit = (nm in o.signature) and set(omit_dup) & set(o.signature[nm].prmtags)
            if omit:
                n.del_input(nm)  # use disconnect_input instead?
            else:  # TODO: verify mut!
                o_in = o.inputs[nm]  # old input node
                if o_in in old_subgraph:  # input within subgraph (`new_beg` will not be changed)
                    n_in = new_subgraph[old_idx[o_in]]  # new input node
                    n.inputs[nm] = n_in  # replace by corresponding new node
                    if (nm, n) not in n_in.outputs:
                        n_in.add_output(nm, n)
                elif o_in not in ignore:
                    # keep old input (already copied), and add output link from old node to new node
                    if n != new_beg or mode not in ['addAnd', 'addOr', 'addLast']:
                        # for aggr mode, no need to link inputs to old_beg
                        # TODO: check! May need to connect if flattened tree?
                        if (nm, n) not in o_in.outputs:
                            o_in.add_output(nm, n)

    # at this point, we duplicated the graph from `root` to `old_beg` (possibly duplicating `old_beg`).
    #  now - we modify the copy of `old_beg`, if needed (mode = overwrite/extend/auto)

    # `new_beg` is used to extend one input of (copy of) `old_beg`
    if mode == 'extend':  # add new_beg into the copy of `old_beg`
        o_in = old_beg.inputs[inp_nm] if inp_nm in old_beg.inputs else None  # keep pointer in case overwritten
        i = old_idx[old_beg]
        nwsb = new_subgraph[i]
        if nwsb.signature.allows_prm(inp_nm):
            new_beg.connect_in_out(inp_nm, nwsb, force=True)
            if o_in:
                o_in.remove_out_link(inp_nm, nwsb)
        elif except_on_wrong_inp:
            raise IncompatibleInputException("revise failed - trying to add %s to %s()" % (inp_nm, nwsb.typename()), nwsb)

    # `new_beg` is a node whose inputs are similar to `old_beg`.
    # overwrite multiple inputs of (copy of) `old_beg`. Other inputs of `old_beg` are copied unchanged
    if mode == 'overwrite':  # TODO: check mutable
        # if (old_beg not in old_idx) or (old_idx[old_beg] >= len(new_subgraph)):
        #     pass
        n = new_subgraph[old_idx[old_beg]]  # copy of `old_beg`
        for i in new_beg.inputs:
            if i in n.inputs:
                # we already connected output links of old inputs to new node - remove those for overwritten inputs
                n.inputs[i].remove_out_link(i, n)
            if n.signature.allows_prm(i):
                n.add_linked_input(i, new_beg.inputs[i], new_beg.view_mode[i])
            elif except_on_wrong_inp:
                raise IncompatibleInputException("revise failed - trying to add %s to %s()" % (i, n.typename()), n)

    # auto mode: `new_beg` is a node whose inputs are similar to `old_beg`'s inputs. (same as overwrite)
    #   However, instead of simply overwriting `old_beg` inputs with `new_beg` inputs, we allow each type to take care
    #   of the needed modification. This could be just a simple overwrite (default implementation), or something more
    #   complicated. For example - the input node may have some flags which direct the modification
    #                e.g. for modifying participant list - have flags for add/remove participant
    if mode == 'auto':
        n = new_subgraph[old_idx[old_beg]]  # copy of `old_beg`
        for i in new_beg.inputs:
            nd = new_beg.input_view(i)
            if i in n.inputs:  # perform modification of old by new, and remove old link
                m = nd.get_op_object_try()  # m - we need a node of the right type, to call the right `dup_auto_modify`
                nd = m.dup_auto_modify(nd, n, i)
                # we already connected output links of old inputs to new node - remove those for overwritten inputs
                n.inputs[i].remove_out_link(i, n)
            if not nd:  # result may be `None` (e.g. remove single attendee of a meeting), then remove this input
                n.del_input(i)
            else:  # add the input
                if n.signature.allows_prm(i):
                    n.add_linked_input(i, nd, new_beg.view_mode[i])
                elif except_on_wrong_inp:
                    raise IncompatibleInputException("revise failed - trying to add %s to %s()" % (i, n.typename()), n)

    # auto2 - let the (copy of the) `old_beg` handle the merging of new into the old
    if mode == 'autotop':
        n = new_subgraph[old_idx[old_beg]]  # copy of `old_beg`
        n.dup_auto_modify_top(new_beg)

    # add modifier - oldBeg is the PARENT node of the constraints (may not have any constraints yet!)
    if mode == 'modif':
        pnm = inp_nm  # not necessarily 'constraint'!
        n = new_subgraph[old_idx[old_beg]]  # copy of `old_beg`
        if pnm in n.inputs:  # we already one or more modifiers
            nn = n.inputs[pnm]
            if nn.typename() != 'AND':  # we have only one modifier previously - add AND on top
                n.wrap_input(pnm, 'AND(', do_eval=False)
                nn = n.inputs[pnm]
            else:  # AND already exists - duplicate it and replace the old AND
                aa, _ = n.call_construct('AND()', d_context)
                for i in nn.inputs:
                    nn.inputs[i].connect_in_out(i, aa)
                n.replace_input(pnm, aa)
                nn = aa
            nn.add_pos_input(new_beg)
        else:  # no modifiers yet
            if n.signature.allows_prm(pnm):
                new_beg.connect_in_out(pnm, n)
            elif except_on_wrong_inp:
                raise IncompatibleInputException("revise failed - trying to add %s to %s()" % (pnm, n.typename()), n)

    gr = []
    new_nodes = [n for n in new_subgraph if n.just_dup]
    for n in new_subgraph:  # hook for action after newly duplicated
        m = n
        if n.just_dup:
            auto_reorder_inputs(n, new_nodes)
            m = n.on_duplicate()  # may return a new node
            n.just_dup = False
        if m:  # on_dup may remove the node - in that case it returns 'None'
            gr.append(m)

    return gr  # new_subgraph


####################################################################################################################
####################################################################################################################


# given a list of nodes, exclude nodes which are under a 'revise' node
def exclude_revise(nodes):
    excl = []
    for n in nodes:
        if isinstance(n, revise):  # n.typename()=='revise':
            excl += n.topological_order()
    return [n for n in nodes if n not in excl]


def add_scored_matches(g, ig, m, matches, d_context, old=None, oiview=None, oclevel=None, oldType=None, oldNodeId=None,
                       oldNode=None, role=None, hasParam=None, hasInput=None, hasTag=None, hasBelow=None):
    """
    Given goal (root) and mid, find and score matches for oldLoc, and add them to `matches`.
    """
    nodes = m.topological_order([], follow_res=False)  # nodes under m
    nodes = [n for n in nodes if not (n.hide or n.no_revise)]
    nodes = exclude_revise(nodes)
    candidates = nodes.copy()
    candidates0 = []
    ml = oclevel  # self.get_dat('oclevel')
    # d_context = self.context
    match_level = 'strict' if not ml or ml not in ['strict', 'prefer', 'any'] else ml
    if old:  # 'old' in self.inputs:
        # old, iview = self.get_inp_view_and_mode('old')
        if match_level != 'strict':
            candidates0 = [n for n in candidates if old.match(n, iview=oiview, oview=VIEW.INT, check_level=False)]
            if match_level == 'any':
                candidates = candidates0
            else:
                candidates = [n for n in candidates if old.match(n, iview=oiview, oview=VIEW.INT, check_level=True)]
        else:
            candidates = [n for n in candidates if old.match(n, iview=oiview, oview=VIEW.INT, check_level=True)]
    if oldType:  # 'oldType' in self.inputs or 'oldTypes' in self.inputs:
        # if 'oldType' in self.inputs:
        #     tp = [self.get_dat('oldType')]
        # else:
        #     o = self.input_view('oldTypes')
        #     tp = [o.get_dat(i) for i in o.inputs]
        tp = to_list(oldType)
        clevel = max([get_type_and_clevel(i)[1] for i in tp])
        told = [re.sub(' ', '_', re.sub('\?', '', i)) for i in tp]
        if match_level != 'strict':
            candidates0 = [n for n in candidates if (told == 'Node' or n.typename() in told)]
            if match_level == 'any':
                candidates = candidates0
            else:
                candidates = [n for n in candidates if
                              (told == 'Node' or n.typename() in told) and n.constraint_level == clevel]
        else:
            candidates = [n for n in candidates if
                          (told == 'Node' or n.typename() in told) and n.constraint_level == clevel]

    if oldNodeId:  # 'oldNodeId' in self.inputs:  # oldNode is a string
        nd = d_context.get_node(oldNodeId)  # (self.get_dat('oldNodeId'))  # oldNode is a string
        candidates = [nd] if nd in candidates else []
    if oldNode:  # 'oldNode' in self.inputs:  # oldNode is a Node
        nd = oldNode  # self.input_view('oldNode')  # most likely it's the result
        candidates = [nd] if nd in candidates else []
        # TODO: if oldNode is result ... (not in candidates)
    if role:  # 'role' in self.inputs:
        # TODO: allow period separated role string to specify multi-step path to candidate nodes
        # role = re.sub(' ', '_', self.get_dat('role'))
        # role = self.get_dat('role')
        candidates = [n for n in candidates for m, o in n.outputs if
                      m == role or m == o.signature.real_name(role)]  # nodes which serve as role
        if not candidates:
            candidates = [n for n in candidates0 for m, o in n.outputs if
                          m == role or m == o.signature.real_name(role)]
    if hasParam:  # 'hasParam' in self.inputs:
        param = hasParam  # self.get_dat('hasParam')
        candidates = [n for n in candidates if n.signature.allows_prm(param)]  # nodes which allow param
        if not candidates:
            candidates = [n for n in candidates0 if n.signature.allows_prm(param)]  # nodes which allow param
    if hasInput:  # 'hasInput' in self.inputs:
        param = hasInput  # self.get_dat('hasInput')
        candidates = [n for n in candidates if n.signature.allows_prm(param) and
                      n.signature.real_name(param) in n.inputs]  # nodes which allow param
        if not candidates:
            candidates = [n for n in candidates0 if n.signature.allows_prm(param) and
                          n.signature.real_name(param) in n.inputs]  # nodes which allow param
    if hasTag:  # 'hasTag' in self.inputs:
        tg = hasTag  # self.get_dat('hasTag')
        candidates = [n for n in candidates if tg in n.tags]  # nodes which have this tag
        if not candidates:
            candidates = [n for n in candidates0 if tg in n.tags]

    # score matches and add to match list    TODO: more elaborate score function - take 'mid' into account?
    below = hasBelow  # 'hasBelow' in self.inputs
    for o in candidates:
        if below:
            oo = [i for i in o.topological_order([], follow_res=True) if below.match(i)]  #  self.inputs['hasBelow'].match(i)]
        if not below or oo:
            score = ig * 100 + len(nodes) - nodes.index(o)  # nodes.index(o) - topological order of candidate
            if o in d_context.exception_nodes + d_context.copied_exceptions:
                # increase priority of node corresponding to exception. Higher priority if immediate exception
                score = score - 50 if o in d_context.exception_nodes else score - 25
            elif o.res in d_context.exception_nodes + d_context.copied_exceptions:
                # same if exception happened for its result
                score = score - 50 if o.res in d_context.exception_nodes else score - 25
            # add order_score_offset (for SWITCH)
            st = oo[0] if below else o
            depths, orig = st.parent_nodes(res=True)
            path = st.get_path(g, orig)
            score += sum([p.order_score_offset(path) for p in path])
            matches[(g, m, o, oo[0] if below else None)] = score
    return matches


def get_goals(slf, g, d_context):
    """
    Gets registered goals 'above' (and including) `g`. If none found, then return `g` itself.

    :param g: the goal
    :type g: Node
    :return: the goals above (including) `g`
    :rtype: List[Node]
    """
    goals = []
    # d_context = self.context
    # TODO: `g.input_view()` instead of `g.inputs[]`?
    r = [g] if g.not_operator() else [g.inputs[i] for i in g.inputs]  # already sorted - most recent first
    for i in r:
        p = list(i.parent_nodes(res=True)[0].keys())
        for j in p:
            if j != slf and j not in goals and j in d_context.goals:
                goals.append(j)
    goals = [g for g in d_context.goals if g in goals]  # sort goals by order in `d_nodes.goals`
    if not goals:  # fallback to base behavior
        goals = r
    return goals


def get_revise_matches(slf, all_nodes, goals, d_context, root=None, riview=VIEW.INT, goal=None,
                       midGoal=None, mid=None, miview=VIEW.INT,
                       old=None, oiview=None, oclevel=None, oldType=None, oldNodeId=None,
                       oldNode=None, role=None, hasParam=None, hasInput=None, hasTag=None, hasBelow=None):
    """
    Finds matching (goal, mid, old) positions in graph:
        - for root: goal nodes of the specified type;
        - for old: nodes of the matching type under the found goals.
    """
    matches = {}
    rgoals = list(reversed(goals))
    new_mid = False
    if goal or midGoal:  # 'goal' in self.inputs or 'midGoal' in self.inputs:  # can't be both
        r = goal if goal else midGoal  # self.input_view('goal') if 'goal' in self.inputs else self.input_view('midGoal')
        rr = get_goals(slf, r, d_context)  # registered goals (if existing)
        if midGoal and r.not_operator() and rr[0] not in all_nodes:  # if 'midGoal' in self.inputs and r.not_operator() and rr[0] not in all_nodes:
            # midGoal node is not under old goals (incl result)
            new_mid = True  # it's a new node - no need to look at the old goals
        if goal or new_mid:  # if goal' in self.inputs or new_mid:
            rgoals = rr
            # else - if not a midGoal matched existing node - then stay with the original goals
    for ig, g in enumerate(rgoals):  # search for root
        ok = g != slf and ((g.typename() not in ['revise'] and not isinstance(g, revise)) or not g.evaluated)
        # TODO: careful with giving a non-empty constraint on out_type!
        # TODO: robustness in combination with fetch - which can return object/constraint/program!
        if ok and root:  # 'root' in self.inputs:
            r, iview = root, riview  # , self.get_inp_view_and_mode('root')
            ok = ok and r.match(g, iview=iview, oview=VIEW.INT, check_level=True)
        if ok:
            if mid or midGoal:  # 'mid' in self.inputs or 'midGoal' in self.inputs:
                mids = g.topological_order([], follow_res=False)  # nodes under g
                if mid:  # 'mid' in self.inputs:  # select nodes which match constraint
                    # mm, miview = mid, miview  # self.get_inp_view_and_mode('mid')
                    mids = [n for n in mids if mid.match(n, iview=miview, oview=VIEW.INT, check_level=True)]
                if midGoal:  # 'midGoal' in self.inputs:  # select nodes which are in midGoal (one or set)
                    mg = midGoal.unroll_set_objects([])  # self.input_view('midGoal').unroll_set_objects([])
                    mids = [n for n in mids if n in mg]
            else:  # if no 'mid' specified - set it to the root
                mids = [g]
            for m in mids:
                # skip if (g, m) were already checked
                if not [1 for (og, om, oo, bb) in matches if og == g and om == m]:
                    matches = add_scored_matches(g, ig, m, matches, d_context, old=old, oiview=oiview, oclevel=oclevel,
                                                 oldType=oldType, oldNodeId=oldNodeId, oldNode=oldNode, role=role,
                                                 hasParam=hasParam, hasInput=hasInput, hasTag=hasTag, hasBelow=hasBelow)

    matches = sorted(matches, key=matches.get)
    # TODO: fallback search?
    return matches


####################################################################################################################
####################################################################################################################

# experimental - this one is used by revise, together with goal/mid_goal: TODO: check, it might be wrong!
# specifically for the case of a creation by reference, where a node chain (process) is created, with the node
# explicitly referred to being in the middle of the process (NOT the root).
# (we COULD just return the root - it would work, but that's not consistent with the explicit request...)
# The problem is that in such a case, revise would fetch the graph only up to the middle node


class revise(Node):
    def __init__(self):
        super().__init__()  # dynamic out type
        self.signature.add_sig('goal', Node)  # if given, then this will be used instead the global goals
        # the goal may not exist yet - will be created on the fly
        self.signature.add_sig('root', Node)  # rootLoc. optional. if not given -> Any?()
        self.signature.add_sig('mid', Node, view=VIEW.INT)  # middle constraint
        # TODO: similar to mid - add 'parent'? Means constraint to direct parent on THIS path
        self.signature.add_sig('midGoal', Node)  # like mid, but if no match found, then fall back to 'try-harder' -
        # create new graph - the new graph will be used as the match result
        # - i.e. ignoring 'root' and 'mid' related constraints. (oldLoc/new still apply)
        self.signature.add_sig('old', Node, view=VIEW.INT)  # oldLoc constraint -
        self.signature.add_sig('oclevel', Str)  # old clevel match mode - strict / prefer / any
        self.signature.add_sig('oldType', Str)  # oldLoc constraint - type of old (as Str, including ?'s)
        self.signature.add_sig('oldTypes', Node)  # like oldType, but expects a SET of strings instead of one string
        self.signature.add_sig('oldNodeId', Str)  # oldLoc- specify existing node NAME, do NOT put '$'/'$#' before name!
        self.signature.add_sig('oldNode', Node)  # oldLoc - specify existing node - needs '$'/'$#' before name!
        self.signature.add_sig('role', Str)  # role constraint for oldLoc - find a node which is USED as input param
        self.signature.add_sig('hasParam', Str)  # means - find a node which ALLOWS this input param
        self.signature.add_sig('hasInput', Str)  # means - find a node which HAS this input param (convenience. same effect as: old=Node?(x=Node?))
        self.signature.add_sig('hasTag', Str)  # means - find a node which has this tag
        self.signature.add_sig('hasBelow', Node, view=VIEW.INT)  # like mid, but means - find a node below old, include results!
        self.signature.add_sig('new', Node, view=VIEW.INT)  # specification of new
        # TODO: check. Should we really use view=VIEW.INT?
        self.signature.add_sig('newMode', Str)  # mode for replacement
        # if newMode starts with ';', then we call a type specific `create_new_beg()`
        self.signature.add_sig('inp_nm', Str)  # name of input to replace - together with oldNode
        self.signature.add_sig('no_add_goal', Bool)  # don't add resulting graph as goal
        self.signature.add_sig('no_eval_res', Bool)  # don't execute result
        self.eval_res = True  # needed?
        # TODO: add flag to allow revising "partial" graphs - i.e. up to internal nodes, which are NOT goals?
        #        e.g. use midGoal, and just set it as root
        # TODO: revise result nodes? - in that case - maybe replace the input node which produced the result
        #                              by the result node, and revise the result?
        #                              add a flag to cause this behavior? (effect on follow_res as well...)

    def valid_input(self):
        if 'goal' in self.inputs and 'midGoal' in self.inputs:
            raise IncompatibleInputException('revise: should not have both "goal" and "midGoal"', self)
        # if 'new' not in self.inputs:
        #     raise MissingValueException('new', self)
        n_o = sum([1 for i in ['old', 'oldType', 'role', 'hasParam', 'hasInput', 'oldNode', 'oldNodeId'] if i in self.inputs])
        if n_o < 1:
            raise IncompatibleInputException("refer node needs at least one of old/role/hasParam constraint", self)
        if ('oldNode' in self.inputs or 'oldNode' in self.inputs) and \
                ('inp_nm' not in self.inputs or self.get_dat('newMode') != 'extend'):
            raise IncompatibleInputException("revise: oldNode needs inp_nm and extend", self)
        if self.get_dat('no_eval_res'):
            self.eval_res = False
        # TODO: should we check that oldLoc mode is compatible with new mode (e.g. old=hasParam with new=extend?)


    def get_matches(self, all_nodes=None, goals=None):
        root, riview = self.get_inp_view_and_mode('root')
        mid, miview = self.get_inp_view_and_mode('mid')
        old, oiview = self.get_inp_view_and_mode('old')
        goal, midGoal = self.get_input_views(['goal', 'midGoal'])
        role, hasParam, hasInput, hasTag = self.get_dats(['role', 'hasParam', 'hasInput', 'hasTag'])
        otyp, oldTypes, oldNodeId, oclevel = self.get_dats(['oldType', 'oldTypes', 'oldNodeId', 'oclevel'])
        otyps, oldNode, hasBelow = self.get_input_views(['oldTypes', 'oldNode', 'hasBelow'])
        oldType = [otyp] if otyp else [otyps.get_dat(i) for i in otyps.inputs] if otyps else None

        matches = get_revise_matches(self, all_nodes, goals, self.context, root=root, riview=riview, goal=goal,
                                     midGoal=midGoal, mid=mid, miview=miview, old=old, oiview=oiview, oclevel=oclevel,
                                     oldType=oldType, oldNodeId=oldNodeId, oldNode=oldNode, role=role,
                                     hasParam=hasParam, hasInput=hasInput, hasTag=hasTag, hasBelow=hasBelow)
        return matches

    def do_revise(self, matches):
        root, mid, old, below = matches[0]  # use only best match
        mode = self.get_dat('newMode') if 'newMode' in self.inputs else 'new'
        inp_nm = self.get_dat('hasParam') if 'hasParam' in self.inputs else \
            self.get_dat('hasInput') if 'hasInput' in self.inputs else \
                self.get_dat('role') if 'role' in self.inputs else ''
        inp_nm = self.get_dat('inp_nm') if 'inp_nm' in self.inputs else inp_nm
        if not inp_nm and mode == 'extend':
            raise IncompatibleInputException("revise: extend needs inp_nm", self)
        omit_dup = self.get_dat('omit_dup') if 'omit_dup' in self.inputs else ['omit_dup']
        try:
            new_subgraph = duplicate_subgraph(root, old, self.input_view('new'), mode, self, mid, below, inp_nm,
                                              omit_dup=omit_dup)
        except Exception as ex:
            re_raise_exc(ex, self)

        if len(new_subgraph) == 0:
            return None
        goal = new_subgraph[-1]  # root of duplicated graph
        self.set_result(goal)  # set result to point to duplicated graph before evaluating it (it might fail)

        ng = self.get_dat('no_add_goal')
        if not ng:
            self.context.add_goal(goal)

    def exec(self, all_nodes=None, goals=None):
        """
        If found matches:
            - rank and choose best (root, mid, old);
            - construct (and evaluate) graph for new;
            - copy necessary nodes between old and root - reuse nodes (point to existing nodes) as much as possible;
            - insert the new graph in the copy (instead of old).
        """
        # todo - allow no 'new' input (and then force 'overwrite' mode) - duplicate without real change

        matches = self.get_matches(all_nodes, goals)
        if len(matches) == 0:
            raise NoReviseMatchException(self)

        self.do_revise(matches)

    def contradicting_commands(self, other):
        if other.typename() != 'revise':
            return False  # if implicit action is not revise - allow (for now it IS always revise)
        snew = self.input_view('new')
        onew = other.input_view('new')
        if snew.typename() != onew.typename():
            return False  # revising two different types - probably no contradiction
        if snew.contradicting_commands(onew):
            return True
        return False


# ################################################################################################
# ################################################################################################


# do nothing
class no_op(Node):
    def __init__(self):
        super().__init__()


class execute(Node):
    """
    Re-evaluates a subgraph. If 'clear' input given as True - set all subnodes' `evaluated` flag to `False`,
    so we force to reevaluate all of them.
    """

    def __init__(self):
        super().__init__()  # dynamic out type
        self.signature.add_sig(posname(1), Node, True)
        self.signature.add_sig('clear', Bool)
        self.signature.add_sig('hide_goal', Bool)

    def exec(self, all_nodes=None, goals=None):
        g = self.input_view(posname(1))
        if g is None:
            raise InvalidResultException("Execute got no subgraph", self)
        if self.get_dat('clear') == True:  # clear all sub nodes before evaluating
            nodes = Node.collect_nodes([g])
            for n in nodes:
                n.evaluated = False
        add = False
        hd = self.get_dat('hide_goal')
        if hd is not None and hd:  # move `g` to the top of the goal list?
            if g in self.context.goals:
                self.context.remove_goal(g)  # TODO: could `g` appear more than once in goal list? and if it does?
                add = True

        # eval again all nodes in path, and their inputs
        g.call_eval(add_goal=add)  # add `g` back to goals (as most recent) if we removed it before
        self.set_result(g)


class getattr(Node):
    """
    Gets attribute of a node by a given param name. No reason to call this explicitly - it's generated by the sugared
    get shorthand.
    """

    def __init__(self):
        super().__init__()  # dynamic out type
        self.signature.add_sig(posname(1), Str, True)
        self.signature.add_sig(posname(2), Node, True)

    def exec(self, all_nodes=None, goals=None):
        nm = self.get_dat(posname(1))
        res = self.input_view(posname(2))
        sig = res.signature
        if environment_definitions.populating_db:
            import opendf.misc.populate_utils as pop
            if pop.is_populate_object(res):  # update object according to agent answer (if the object is a db object)
                                             # Agent may mention additional (unasked for) fields - we update all
                success = res.populate_update(nm)
                # now we continue the usual exec, with the db updated, and res modified
                # (probably in place - in case it was used by several graphs)

        if not sig.allows_prm(nm):
            if nm == 'item':
                val = res
            else:
                raise InvalidResultException(
                    "getattr- %s : signature does not have a field %s" % (self.inputs[posname(2)].typename(), nm), self)
        elif nm not in res.inputs:
            if sig[nm].prop:
                val = res.get_property(nm)
            else:
                # TODO: we can add a default value for some inputs - through a class function
                val = res.get_missing_value(nm, as_node=True)
            if not val and res.constraint_level == 0:
                raise InvalidResultException(
                    "getattr -- %s does not  have an input '%s'" % (self.inputs[posname(2)].typename(), nm), self)
        else:
            val = res.inputs[nm]

        if val:
            self.set_result(val)

    def yield_msg(self, params=None):
        r = self.res
        m1 = r.describe(params=params)
        nd = self.input_view(posname(2))
        attr = self.get_dat(posname(1))
        m2 = nd.getattr_yield_msg(attr, m1.text, params=params)
        return Message(m2.text, objects=m1.objects + m2.objects)

    def trans_simple(self, top):
        nd = self.input_view(posname(2))
        # add a 'singleton' wrapper around input nodes which may return multiple results
        if nd and nd.signature.multi_res == True:  # or maybe even just != False
            self.wrap_input(posname(2), 'singleton(', do_eval=False)
        return self, None


class filtering(Node):
    def __init__(self):
        super().__init__()  # dynamic out type
        self.signature.add_sig('filter', Node)
        self.signature.add_sig(posname(1), Node, True)
        self.signature.add_sig('index', Int)
        # select the i-th result. If it has `index` AND filter - first filter, then index.
        # Careful! 1 based counting (first is 1)

    def valid_input(self):
        if 'filter' not in self.inputs and 'index' not in self.inputs:
            raise MissingValueException.make_exc("filter/index", self)

    def exec(self, all_nodes=None, goals=None):
        res = self.input_view(posname(1))
        if self.outypename() == 'Node':  # set out type, regardless of success of evaluation - copy from pos1
            self.out_type = res.get_op_type(no=Node)
        candidates, matches = self.do_filter(res)
        mul = len(matches)
        if mul < 1:
            raise EmptyEntrySingletonException(res.typename(), self)
        if 'index' in self.inputs:
            idx = self.get_dat('index')
            if idx >= mul or idx < 1:
                raise InvalidResultException('Requested index not in range - %d / %d' % (idx, mul), self)
            self.set_result(matches[idx - 1])
        else:
            if len(candidates) == mul:  # filtering didn't change input
                self.set_result(self.inputs[posname(1)])
            if mul == 1:
                self.set_result(matches[0])
            else:  # multiple objects, but not the same set as input - make new set
                sexp = 'SET(' + comma_id_sexp(matches) + ')'
                g, _ = self.call_construct(sexp, self.context)
                self.set_result(g)
                logger.info('Filtering: %s', g.describe_set('\n'))


# singleton isn't quite a core framework function - it's more like a design pattern
class singleton(Node):
    def __init__(self):
        super().__init__()  # dynamic out type
        self.signature.add_sig('filter', Node)
        self.signature.add_sig(posname(1), Node, True)
        self.signature.add_sig('index', Int)
        # select the i-th result. if it has `index` AND filter - first filter, then index.
        #  Careful! 1 based counting (first is 1)
        self.copy_in_type = posname(1)

    def exec(self, all_nodes=None, goals=None):
        res = self.input_view(posname(1))
        if self.outypename() == 'Node':  # set out type, regardless of success of evaluation - copy from pos1
            self.out_type = res.get_op_type(no=Node)
        candidates, matches = self.do_filter(res)
        mul = len(matches)
        if mul < 1:
            raise EmptyEntrySingletonException(res.typename(), self)
        if 'index' in self.inputs:
            idx = self.get_dat('index')
            if idx > mul or idx < 1:
                raise InvalidResultException('Requested index not in range - %d / %d' % (idx, mul), self)
            self.set_result(matches[idx - 1])
        else:
            if mul == 1:
                self.set_result(matches[0])
            else:  # multiple objects
                sg = matches[0].singleton_suggestions(self.id, matches)
                if sg:
                    raise MultipleEntriesSingletonException(
                        matches[0].singleton_multi_error(matches), self, hints=[], suggestions=sg)
                else:
                    raise MultipleEntriesSingletonException(matches[0].singleton_multi_error(matches), self)


# currently unused
class Select(Node):
    """
    Given several inputs, select one of them, and take its "value" as the result. Each of the inputs is a function
    with two positional arguments:
        - `pos1` - a function which returns `True`/`False`  (when run on `inp`);
        - `pos2` - a value (node) which could be selected and copied (linked to) as the output of 'select'.
    Additionally, Select gets an 'inp' argument:
        - `inp` - is COPIED by each of the sub functions before they are executed.

    Note: because evaluation is bottom up, the first time we evaluate the select sexp, the sub graphs do not have 'inp'
    yet, so they don't really run. only after copying the 'inp' into them, and executing them again, do we get the
    right result.
    """

    def __init__(self):
        super().__init__()
        self.signature.add_sig(POS, Node)
        self.signature.add_sig('inp', Node)  # put user input graph here

    def exec(self, all_nodes=None, goals=None):
        res = ''
        if 'inp' in self.inputs:
            inp = self.input_view('inp')
            for nm in self.inputs:
                if is_pos(nm):
                    n = self.input_view(nm)
                    if 'inp' not in n.inputs:  # normally `n` does not have inp yet
                        inp.connect_in_out('inp', n)
                    n.exec(all_nodes, goals)
                    if n.result != n and n.res.dat == True:
                        res = n.input_view(posname(2))
                        break
        if res:
            self.set_result(res)


class sel_inp(Node):
    """
    Select input - use with `Select()`.
    Result: match pos1 with inp.
    """

    def __init__(self):
        super().__init__(Bool)
        self.signature.add_sig(posname(1), Node)
        self.signature.add_sig(
            posname(2), Str)  # (could be Node for general case, but planning to use only Str for now)
        self.signature.add_sig('inp', Node)  # put user input graph here
        # TODO: add mode: e.g. 'first' (return first that matches), 'only_one' (if more than one matches - no match),
        #  ...

    def exec(self, all_nodes=None, goals=None):
        if 'inp' in self.inputs and posname(1) in self.inputs:
            res = Bool()
            res.data = self.input_view('inp').match(self.input_view(posname(1)))
            # the user input is the query, choosing from several presented options!
            #  (the difference being that the constraint can omit some details and still match, but not the opposite)
            #  e.g.: "do you want wednesday 10AM, or thursday 8AM?" - user: "8AM"... (normal match would work?)
            self.set_result(res)
        # if inp not in inputs - do nothing


class Let(Node):
    """
    Assigns a name to a node (similar to the {~} syntax). When it is evaluated, we know the inputs (and their results)
    have already been evaluated. Unlike the Microsoft's `let`, where there is a final argument which is the sexp
    (context) in which the assignment holds; here, we keep the assignment for the whole length of the dialog (but its
    value can be overwritten).
    """

    def __init__(self):
        super().__init__()
        self.signature.add_sig(posname(1), Str, True)  # name of variable
        self.signature.add_sig(posname(2), Node, True)  # assigned node
        self.signature.add_sig(posname(3), Str)  # optional mode - if 'res' then assign the result of the node

    def exec(self, all_nodes=None, goals=None):
        nd = self.inputs[posname(2)].res if self.get_dat(posname(3)) == 'res' else self.inputs[posname(2)]
        nm = self.get_dat(posname(1))
        self.context.assign[nm] = nd
        self.set_result(nd)


class do(Node):
    """
    A container for multiple sexps (subgraphs). Useful as a way to group several computations together -
    if one fails (exception), execution is stopped for all of them. After the exception is resolved (with revise),
    execution will proceed - for all of them.

    Note: if we want to have a block of sexps which continue even if an exception occurs, then use continued turns.
    """

    def __init__(self):
        super().__init__()
        self.signature.add_sig(POS, Node)  # unlimited number of input graphs
        self.stop_eval_on_exception = True  # ??

    # no need to do anything! the evaluation process already takes care of evaluating the inputs before we get here.
    # result points to result of last input
    def exec(self, all_nodes=None, goals=None):
        n_exp = max([posname_idx(i) for i in self.inputs])
        self.set_result(self.inputs[posname(n_exp)].res)

    # def yield_msg(self, params=None): todo - verify obsolete - do we still use the 'nodes' anywhere?
    #     msg, objects, nodes = [], [], []
    #     for i in self.inputs:
    #         m, o = self.input_view(i).yield_msg(params)
    #         if m:
    #             if isinstance(m, tuple):
    #                 msg.append(m[0])
    #                 if len(m) == 2:
    #                     nodes.append(m[1])
    #         if o:
    #             objects += o
    #     r = '. '.join(msg)
    #     if nodes:
    #         r = (r, nodes)
    #     return r, objects

    def yield_msg(self, params=None):
        msg, objects = [], []
        for i in self.inputs:
            m = self.input_view(i).yield_msg(params)
            if m.text:
                msg.append(m.text)
            if m.objects:
                objects += m.objects
        r = '. '.join(msg)
        return Message(r, objects=objects)


# cont_turn (continuation-turn) holds multiple expressions which should be executed in the same turn.
#      (its effect should be exactly the same as having multiple continuation expressions in one turn)
# unlike do(), ALL expressions should be executed, even if one (or several) fail.
# unlike do(), the expressions do NOT consist of a logical "unit". They are separate expressions, which just happen to
# occur in the same turn. i.e: if a revise is applied later, it should replicate only one expression,
# not the cont_turn wrapper.
# The reason to have cont_turn() at all, is that it may be convenient for the MT module to generate just one expression.
# In practice, cont_turn() is broken to the separate expressions, and each is run separately - TODO
class cont_turn(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig(POS, Node)  # unlimited number of input graphs
        self.stop_eval_on_exception = False  #


class rerun(Node):
    """
    Re-run evaluation of a graph (not just a node). By default, we remove this `rerun` node from `d_nodes` goals.
    inputs:
        - id: if given, evaluate the graph starting at that node. if not given - evaluate the most recent goal in
            `d_nodes`;
        - keep_goal: if `True`, don't remove this `rerun` node from `d_nodes` goals.
    """

    def __init__(self):
        super().__init__()
        self.signature.add_sig('id', Int)
        self.signature.add_sig('keep_goal', Bool)

    def exec(self, all_nodes=None, goals=None):
        if not self.get_dat('keep_goal'):
            self.context.remove_goal(self)
        idx = self.get_dat('id')
        if idx is None and self.context.goals:
            idx = self.context.goals[-1].id
        if idx is not None:
            nd = self.context.get_node(idx)
            if nd:
                self.set_result(nd)
                e = nd.call_eval(add_goal=True)  # add it back in front
                if e:
                    raise e[-1]


# suggestions of agents:
# for now - we put these into `d_nodes.prev_sugg_act` after a turn, in case there was an exception.
# From the convention is that if suggestions are given, then this is a list of sexp's.
#   - the first one (0-th element) is the action in case of rejection (calling RejectSuggestion);
#   - the following ones - can be selected by AcceptSuggestion(index=#)
#     if sexp='-' (given as a choice), then it means do nothing. (useful?).
# Special markers inside the suggestions:
#   - SUGG_IMPL_AGR at the beginning of the suggestion - mark option to run as implicit agreement;
#   - SUGG_MSG - split the suggestion to executable sexp and a message which will be added to the node;
#   - SUGG_LABEL (followed by a name) - named suggestion - used by `MoreSuggestions` (skipped by AcceptSuggestion).

class AcceptSuggestion(Node):
    """
    Executes a sexp suggested by agent in prev turn.
    """

    # if no index is given, take the first one
    def __init__(self):
        super().__init__()
        self.signature.add_sig(posname(1), Int, alias='index')

    def get_missing_value(self, nm, as_node=True):
        return self.res

    def exec(self, all_nodes=None, goals=None):
        prev_sugg = [] if self.context.prev_sugg_act is None else [i for i in self.context.prev_sugg_act if
                                                                   SUGG_LABEL not in i]
        n_sugg = len(prev_sugg) - 1
        # the first suggestion (id=0) is the reject option
        if n_sugg > 0:
            idx = self.get_dat('index')
            if idx is not None:
                if idx > n_sugg or idx < 1:
                    raise WrongSuggestionSelectionException(
                        self, hints=[], suggestions=self.context.prev_sugg_act,
                        message="To select one of the suggestions, please choose one of the %d options" % n_sugg)
            sexp = prev_sugg[idx]
            if sexp and sexp != '-':
                if sexp.startswith(SUGG_IMPL_AGR):  # mark option to run as implicit agreement
                    sexp = sexp[2:]
                if SUGG_MSG in sexp:  # message to user
                    sexp = sexp.split(SUGG_MSG)[0]
                # patch - avoid infinite recursion, e.g. in case where AcceptSuggestion is in a 'do',
                #         and another branch of the 'do' consumes the effect of accept suggestion
                hold_sugg = self.context.prev_sugg_act
                self.context.prev_sugg_act = None
                # the command from the suggestions did not pass through trans_simple - do it here (if dialog_simp)
                g, e = self.call_construct_eval(sexp, self.context, do_trans_simp=True)
                self.set_result(g)
                self.context.prev_sugg_act = hold_sugg  # TODO do we really want to re-use suggestions??
                if e:
                    re_raise_exc(e[-1])  # pass on exception
        else:
            raise WrongSuggestionSelectionException(self)


class RejectSuggestion(Node):
    """
    Executes a sexp suggested by agent in prev turn.
    """

    # if no index is given, take the first one
    def __init__(self):
        super().__init__()

    def exec(self, all_nodes=None, goals=None):
        prev_sugg = [] if self.context.prev_sugg_act is None else [i for i in self.context.prev_sugg_act if
                                                                   SUGG_LABEL not in i]
        n_sugg = len(prev_sugg)
        # the first suggestion (id=0) is the reject option
        if n_sugg:
            sexp = prev_sugg[0]
            if sexp and sexp != '-':
                if SUGG_MSG in sexp:  # message to user
                    s = sexp.split(SUGG_MSG)
                    sexp, ms = s[0], s[1]
                    if ms:
                        self.context.add_message(self, ms)
                if sexp:
                    hold_sugg = self.context.prev_sugg_act
                    self.context.prev_sugg_act = None
                    g, e = Node.call_construct_eval(sexp, self.context, do_trans_simp=True)
                    self.set_result(g)
                    self.context.prev_sugg_act = hold_sugg
                    if e:
                        re_raise_exc(e)
        else:
            raise WrongSuggestionSelectionException(self)


# A 'named suggestion' is a suggestion string which has a special marker ('%;%') followed by a name.
# `MoreSuggestions(name)` will select the named suggestion with the matching name (if present)
# if no name is given, then the first named suggestion will be selected.
# if no match - complain
class MoreSuggestions(Node):
    """
    Execute a sexp suggested by agent in prev turn.
    """

    # if no index is given, take the first one
    def __init__(self):
        super().__init__()
        self.signature.add_sig(posname(1), Str)  # look for a suggestion with this name (e.g. 'prev', 'next' ...)

    def exec(self, all_nodes=None, goals=None):
        prev_sugg = [] if self.context.prev_sugg_act is None else [i for i in self.context.prev_sugg_act if
                                                                   SUGG_LABEL in i]
        name = self.get_dat(posname(1))
        if prev_sugg and name:
            prev_sugg = [i for i in self.context.prev_sugg_act if SUGG_LABEL + name in i]
        n_sugg = len(prev_sugg)
        if n_sugg > 0:
            sexp = prev_sugg[0].split(SUGG_LABEL)[0]
            if sexp and sexp != '-':
                if sexp.startswith(SUGG_IMPL_AGR):  # mark option to run as implicit agreement
                    sexp = sexp[2:]
                if SUGG_MSG in sexp:  # message to user
                    sexp = sexp.split(SUGG_MSG)[0]
                # the command from the suggestions did not pass through trans_simple - do it here (if dialog_simp)
                g, e = self.call_construct_eval(sexp, self.context, do_trans_simp=True)
                self.set_result(g)
                if e:
                    re_raise_exc(e)  # pass on exception
        else:
            raise WrongSuggestionSelectionException(self)


class Yield(Node):
    """
    Let the input node explain itself to user - calculation and/or result.
    """

    # normally, the communication to user is through exceptions - only if something bad happened
    # TODO: think about chaining explanations - best practices / needed control parameters...
    def __init__(self):
        super().__init__(type(self))
        self.signature.add_sig(posname(1), Node, True, alias='output')

    def exec(self, all_nodes=None, goals=None):
        n = self.inputs[posname(1)]  # the input node - NOT its result. Allow it to explain itself
        y = n.yield_msg()  # call object's method to generate answer + objects
        y.text = MSG_YIELD + y.text
        self.context.add_message(self, y)
        self.set_result(n)
        # TODO - use the returned objects to set common ground more correctly!
        # s, objs = n.yield_msg()
        #                                             (some objects may further chain it to their inputs...)
        # s, objs = y if isinstance(y, tuple) and len(y)==2 else (y,[])
        # if s:
        #     if isinstance(s, tuple):
        #         s = s[0]
        #     self.context.add_message(self, MSG_YIELD + s)
        # self.set_result(n)

    def yield_msg(self, params=None):
        if self.result != self:
            return self.result.yield_msg(params)
        return super().yield_msg(params)


class size(Node):
    """
    Returns the number of elements in the RESULT of an expression. 0 if trivial result.
    """

    def __init__(self):
        super().__init__(Int)
        self.signature.add_sig(posname(1), Node, True)
        self.signature.add_sig('unroll', Bool)  # if `True` - unroll set objects

    def exec(self, all_nodes=None, goals=None):
        inp = self.inputs[posname(1)]
        if inp == inp.result and inp.typename() != 'SET' and inp.outypename() != inp.typename():
            i = 0
        else:
            if inp == inp.result and inp.outypename() != inp.typename():
                i = 0
            else:
                inp = inp.res
                unroll = self.inp_equals('unroll', True)
                if inp.typename() == 'SET':
                    # we could either give just the number of direct descendants, or recursively unroll the set
                    if unroll:
                        i = len(inp.unroll_set_objects())
                    else:
                        i = inp.num_pos_inputs()
                else:
                    i = 1
        s = 'Int(%d)' % i
        d, e = self.call_construct_eval(s, self.context)
        self.set_result(d)

    def allows_exception(self, ee):
        e = to_list(ee)[0]
        if isinstance(e, DFException):
            e = e.chain_end()
        if not isinstance(e, ElementNotFoundException):
            return False, ee
        return True, ee


class Exists(Node):
    """
    Checks if the input expression has a non-empty result. - this must allow possible exceptions in input graph
    """

    def __init__(self):
        super().__init__(Bool)
        self.signature.add_sig(posname(1), Node, True)

    def exec(self, all_nodes=None, goals=None):
        inp = self.inputs[posname(1)]
        o = True
        if inp.result == inp:
            o = False
        else:
            inp = inp.res
            if inp.typename() == 'SET':
                if inp.num_pos_inputs() < 1:
                    o = False

        s = 'Bool(%s)' % o
        d, e = self.call_construct_eval(s, self.context)
        self.set_result(d)

    def yield_msg(self, params=None):
        objs = []
        r = self.res.dat
        inp = self.input_view(posname(1))
        if r:
            msg = inp.describe(params)
            s, objs = msg.text, msg.objects
            if s:
                msg += ' NL ' + s
            objs += ['VAL#Yes']
        else:
            s, objs = inp.yield_failed_msg(params)
            objs += ['VAL#No']
            if s:
                msg = 'No. ' + s
            elif inp.out_type is not None:
                msg = 'No. I could not find any %s' % node_fact.sample_nodes[inp.out_type.__name__].obj_name_singular
            else:
                msg = 'No. I could not find anything.'
        return Message(msg, objects=objs)

    # allow possible exceptions in input graph
    def allows_exception(self, ee):
        e = to_list(ee)[0]
        if isinstance(e, DFException):
            e = e.chain_end()
        if not isinstance(e, ElementNotFoundException):
            return False, ee
        return True, ee


class replace_agg(Node):
    """
    Takes one aggregator as input, returns a new aggregator node, wrapping the same objects.
    """

    # in case of a non aggregator input - no conversion is done. This makes it safe to apply this function to non-aggs
    def __init__(self):
        super().__init__()
        self.signature.add_sig(posname(1), Node, True)  # aggregator to be replaced
        self.signature.add_sig(posname(2), Str, True)  # name of new operator

    def valid_input(self):
        inp = self.input_view(posname(1))
        if inp.is_aggregator():
            op = self.get_dat(posname(2))
            if op not in node_fact.aggregators:
                raise InvalidTypeException("unknown aggregator type: %s" % op, self)

    def exec(self, all_nodes=None, goals=None):
        inp = self.input_view(posname(1))
        if inp.is_aggregator():
            op = self.get_dat(posname(2))
            sexp = op + '(' + ','.join([id_sexp(inp.input_view(i)) for i in inp.inputs]) + ')'
            r, e = self.call_construct_eval(sexp, self.context)
            self.set_result(r)
        else:
            self.set_result(inp)


# switch between alternative paths - the first one is "active", the rest are inactive
# this is a soft switch - the basic idea was to just affect the score calculation of refer -
#     when a path goes through a non active path of SWITCH, there is a penalty, so nodes in the active path
#     are preferred (but the inactive paths are still visible).
# todo - make it a "harder" switch - i.e. make the nodes in inactive paths invivible (for match / collect_nodes...)?
class SWITCH(Operator):
    def __init__(self):
        super().__init__()  # Dynamic output type
        self.signature.add_sig('excl', Bool)  # if True, match only the active path
                                              # this does not quite fit with the "soft" switch - verify
        self.copy_in_type = posname(1)

    # will match only first input if 'excl' is True, else - behaves like OR
    # TODO - what is the desired behaviour in case of nested SWITCHES?
    # todo - check the view!
    # todo - is this correct?? the switch is the ref or obj??
    def match(self, obj, iview=VIEW.INT, oview=None, check_level=False, match_miss=False):
        if self.inp_equals('excl', True):
            inp = self.input_view(posname(1))
            return inp.match(obj, check_level=check_level, match_miss=match_miss)
        else:
            for nm in self.inputs:
                inp = self.input_view(nm)
                if inp.match(obj, check_level=check_level, match_miss=match_miss):
                    return True
        return False

    # switch the active input
    # Specifying the new active input can be by:
    #   inp_nm - the name of the input which should be set to active
    #   cond   - a condition to match all nodes under each input, until a match is found
    #            if cond, then will try to match also result nodes if with_res is True
    #            todo - if needed, maybe add more params to control get_refer_match
    # do nothing if no match is specified/found
    # todo - maybe this should be the create_new_beg func? (careful to call on right node...)
    # def dup_switch_active(self, inp_nm=None, cond=None, with_res=True):
    #     if (not inp_nm or inp_nm not in self.inputs) and not cond:
    #         return self
    #     # if both inp_nm and cond - take inp_nm
    #     if not inp_nm:
    #         for i in self.inputs:
    #             n = self.input_view(i)
    #             nds = n.topological_order(follow_res=with_res)
    #             matches = get_refer_match(self.context, nds, [n], pos1=cond)
    #             if matches:
    #                 inp_nm = i
    #                 break
    #     if inp_nm and inp_nm!=posname(1):  # change needed - make a new SWITCH node
    #         inps = [id_sexp(self.input_view(inp_nm))] + [id_sexp(self.input_view(i)) for i in self.inputs if i!=inp_nm]
    #         s = 'SWITCH(' + ','.join(inps) + ')'
    #         d, _ = self.call_construct(s)
    #         return d
    #     return self

    def create_new_beg(self, new_beg, mode, rev, root, mid, below):
        # For now, assuming the current SWITCH is the only one on the ppath from root to 'below'
        #    there may be several, and then we may want to activate all - todo
        if below and mode == ';activate':
            path = below.get_a_path(self)  # assuming current node is the only SWITCH
            if path and len(path)>1:
                inp_nm = [i for i in self.inputs if self.inputs[i]==path[-2]][0]
                if inp_nm and inp_nm!=posname(1):  # path found, and not active already
                    inps = [id_sexp(self.input_view(inp_nm))] + \
                           [id_sexp(self.input_view(i)) for i in self.inputs if i != inp_nm]
                    s = 'SWITCH(' + ','.join(inps) + ')'
                    d, _ = self.call_construct(s, self.context)
                    d.just_dup = True
                    return d, False, False, [], 'overwrite'
        return None, None, True, None, None

    def order_score_offset(self, path):
        ps = [i for i, p in enumerate(path) if p == self]
        if ps and ps[0] > 0 and posname(1) in self.inputs:
            i = ps[0]
            inp = path[i - 1]
            return 0 if inp == self.inputs[posname(1)] else 100
        return 0


# consider auto_switch node - where the "active" input is automatically switched during a revise (eg. in on_dup) - todo?


class allows(Node):
    def __init__(self):
        super().__init__(Bool)  # dynamic out type
        self.signature.add_sig(posname(1), Node, True, alias='filter')
        self.signature.add_sig(posname(2), Node, True, alias='object')

    def exec(self, all_nodes=None, goals=None):
        filt = self.input_view(posname(1))
        obj = self.input_view(posname(2))
        match = filt.match(obj)
        d, e = self.call_construct_eval('Bool(%s)' % ('True' if match else 'False'), self.context)
        self.set_result(d)

    def yield_msg(self, params=None):
        match = self.res.dat
        if match is None:
            return ''
        filt = self.input_view(posname(1))
        obj = self.input_view(posname(2))
        if obj.typename() == 'SET':
            raise DFException('Error - should be applied to single object', self, objects=['ERR#multi'])
        pp = {i: 0 for i in params} if params else {}  # hack, convert params to dict, so we can add filt
        pp['yn_filter'] = filt
        return obj.yield_msg(pp)


####################################################################################################################
# experimental -
# some nodes related to "context switching"
#    to avoid confusion: this is NOT about switching between multiple instances of DialogContexts
# for example:
#    - entering a side dialog, and then returning to the main task.
#    - exploring a hypothesis, with the possibility to return to the start state if it fails
# shifting context is done both by rearranging the order of goals in context.goals, and by using nodes to connect
#   multiple goals.
# There can be many ways in which context switching is possible:
# - just for one turn, or for many
# - just one alternative context or several
# - nested contexts or flat
# - what is kept from a context once it is switched out
#   - forget that it happened
#   - keep it as "first class" graph
#   - keep it as "second class" graph
# The actual switching (reordering of goals) is easy (and we don't really need a node for this - we can have a function
#  in Node or DialogContext to do this).
# The more tricky part is to decide WHEN to do the switching, and, in case there are multiple contexts,
# to WHICH context to switch.
#

# note - if previous goals are omitted (e.g. due to unique_goal_types in context.pack), restoring old context would fail


# side_task : this is used when the "main" task has not finished yet, but we go temporarily go into a side dialog,
#    and then return to the main task.
# there may be different types of side tasks... first implementation
# for example:
#   1. User:  I want to create a meeting tomorrow
#   2. Agent: you are free at 10. Is that good?
#   3. User:  Is Dan free at 10:00?
#   4. Agent: Yes, Dan is free
#   5. User:  then Yes
# without side task, after turn 4, the last (current) goal (is Dan free?) is satisfied - the system will not go back
#  to the main goal (since the suggestion from turn 2 no longer exists, so can not be accepted).
# side task allows to keep the main goal active.
# (this is relevant only if the main goal has not been satisfied yet. otherwise, we don't attach the side task to it)
# the current implementation is quite similar to do() - grouping the two tasks together, and trying to satisfy both.
# there are some differences, though:
#  - we typically don't want to keep the side task around (it may interfere with refer/revise)
#    - although there are cases we may want to do that - use the flag 'persist'
#  - We need to deal with the (common) case where the side task succeeds, and the main task fails
#    (normally an evaluation either completely fails or completely succeeds) - i.e. generate BOTH success and failure
#     messages.
# todo -
#   - after side task is done, do we completely remove it from the graph? (destructive), or keep it "somewhere"?
#     - should we be able to revise / refer to it during (or even after) it's lifespan?
class side_task(Node):
    def __init__(self):
        super().__init__(Node)  # dynamic out type
        self.signature.add_sig('task', Node)  # this will be moved to pos1
        self.signature.add_sig('persist', Bool)  # Unless persist=True, the side task will be removed from the graph
        self.signature.add_sig('silent', Bool)   # don't create a message for task (but copy if one already exists) (temp)
        self.signature.add_sig(POS, Node)

    def yield_msg(self, params=None):
        p = self.input_view(posname(1))
        return p.yield_msg(params) if p else Message('')  # chain messaging

    def trans_simple(self, top):
        if 'task' in self.inputs:  # mode input 'task' to pos1 - this shows that we have not yet transformed this node
            task = self.inputs['task']
            self.disconnect_input('task')
            task.connect_in_out(posname(1), self)

            goals = self.context.goals
            prev_done = goals[-1].evaluated if goals else True
            if not prev_done:  # add the last goal
                self.add_pos_input(goals[-1])
        return self, None

    # on duplication (revise) - remove side_task if it has only one pos input
    def on_duplicate(self, dup_tree=False):
        if self.num_pos_inputs() == 1:
            nm = [i for i in self.inputs if is_pos(i)][0]
            task = self.inputs[nm]
            self.disconnect_input(nm)
            pnm, parent = self.get_parent()
            if parent:
                parent.replace_input(pnm, task)
            return None  # remove this node
        return self

    # todo - this is not quite right when we have messages we want to output only once (do we need separate counters??)
    def collect_messages(self, ee):
        msg = []
        objs = []
        for i in self.inputs:
            if is_pos(i):
                n = self.inputs[i]
                es = n.get_top_exceptions(ee)
                for e in es:
                    if e.message:
                        msg.append(e.message)
                    if e.objects:
                        objs.extend(to_list(e.objects))
                if not es:
                    m = n.yield_msg()
                    if m.text:
                        msg.append(m.text)
                    if m.objects:
                        objs.extend(to_list(m.objects))
        return msg, objs

    # this would be called during the evaluation, after the subtasks have been evaluated -
    #    typically, the "main" task would fail, since it failed in the last turn.
    # at this point, allows_exception is called, so we use this chance to:
    #   1. output the message from the side task AND from the main task
    #   2. remove the side task (unless persist=true)
    def allows_exception(self, e):
        task = self.inputs[posname(1)] if posname(1) in self.inputs else None
        # if task and task.evaluated:
        #     if self.inp_equals('silent', True):  # if silent, move message from task to side_task- if msg already exists
        #         self.context.move_messages(task, self)
        #     else:  # by default, we get the yield message for the task and attach it to side_task
        #         y= task.yield_msg()
        #         s, objs = y if isinstance(y, tuple) and len(y) == 2 else (y, [])
        #         self.context.add_message(self, MSG_YIELD + s)
        # we know that there WAS an exception. create a new one, with all the exception/success messages
        msg, objs = self.collect_messages(e)
        ex = DFException('  NL  '.join(msg), self, objects=objs)
        self.context.add_exception(ex)
        e = [ex] + e
        if not self.inp_equals('persist', True):
            self.disconnect_input(posname(1))
        return False, e  # do not actually change the exception status


# another version of handling side dialogs -
# creating restore points (dialog.restore_points), to which we can return.
# (basically reordering context.goals)
# for example - cases where the system makes a (single) suggestion, and then tentatively accepts it
#    we "mark" the state before accepting the suggestion, so that we can get back to that point if the user eventually
#    decides to reject the suggestion.


# save a restore_point
# - not expecting to actually use this - typically this would be performed by directly calling a function to do this
class save_state(Node):
    def __init__(self):
        super().__init__(type(self))
        self.signature.add_sig(posname(1), Int)  # which goal to take - by default the one just before this one

    def exec(self, all_nodes=None, goals=None):
        i = self.get_dat(posname(1))
        i = i if i is not None else 2
        if len(self.context.goals) >= i:
            # self.context.goals[-1], self.context.goals[-2] = self.context.goals[-2], self.context.goals[-1]
            self.context.restore_points.append(self.context.goals[-i])  # should be a function in context


# restore a previous restore_point
# restored goal is added as last goal and evaluated again
class restore_state(Node):
    def __init__(self):
        super().__init__(Node)  # dynamic out type
        # self.signature.add_sig(posname(1), Int)  # in case there are several return points (for now only one expected)

    # we could do this with trans_simple, or with exec
    # def trans_simple(self, top):
    #     n = self
    #     if self.context.restore_points:
    #         pnm, parent = self.get_parent()
    #         if parent:
    #             g = self.context.restore_prev_state()  # with index value from input
    #             if g:
    #                 parent.replace_input(pnm, g)
    #                 n = parent
    #     return n, None

    def exec(self, all_nodes=None, goals=None):
        if self.context.restore_points:
            r = self.context.restore_points[-1]   # with index value from input
            self.context.restore_points = self.context.restore_points[:-1]  # remove this restore point (any case we would like to return to it again??)
            self.set_result(r)
            r.call_eval(add_goal=True)


# possible place off of which to hang objects mentioned by the system.
# objects are connected to the result - so this can not be revised!
# it has no input, and does nothing.
class sys_mentioned(Node):
    def __init__(self):
        super().__init__()
