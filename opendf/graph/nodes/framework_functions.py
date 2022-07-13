"""
Framework functions which are part of the graph execution engine framework.
"""
import logging
import re

from opendf.defs import VIEW_INT, POS, MSG_YIELD, SUGG_LABEL, SUGG_MSG, SUGG_IMPL_AGR, is_pos, posname, \
    posname_idx  # , NODE
from opendf.exceptions.df_exception import DFException, MissingValueException, \
    WrongSuggestionSelectionException, EmptyEntrySingletonException, IncompatibleInputException, \
    InvalidTypeException, MultipleEntriesSingletonException, NoReviseMatchException, ElementNotFoundException, \
    InvalidResultException
from opendf.graph.node_factory import NodeFactory
from opendf.graph.nodes.framework_objects import Str, Bool, Int
from opendf.graph.nodes.node import Node
from opendf.utils.utils import get_type_and_clevel, comma_id_sexp, id_sexp, to_list
from opendf.exceptions import re_raise_exc

logger = logging.getLogger(__name__)

node_fact = NodeFactory.get_instance()


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
                    search_last_goal=True, merge_equiv=True, merge_equiv_res=True):
    all_nodes = [n for n in all_nodes0] if all_nodes0 else []
    all_nodes = [n for n in all_nodes if not n.hide]
    goals = [g for g in goals0] if goals0 else []
    if goals and search_last_goal:  # search also on last (current) goal
        last_nodes = Node.collect_nodes([d_context.goals[-1]])  # it is dynamically built, so we need to collect nodes
        all_nodes.extend([n for n in last_nodes if n not in all_nodes])

    matches = []
    nodes = all_nodes
    if not force_fallback:
        if pos1:  # type constraint - could be an aggregated constraint (AND/OR/...)
            candidates = [n for n in nodes if
                          pos1.match(n, iview=pos1view, oview=VIEW_INT, check_level=True, match_miss=match_miss)]
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
                          cond.match(n, iview=condview, oview=VIEW_INT, check_level=True, match_miss=match_miss)]
            nodes = candidates  # allow further filtering
            matches = candidates
        if midtype:
            tp = midtype  # type is a string - always get res.dat
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
            nodes = matches  # allow type + role
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

    if not matches and not no_fallback and pos1:  # and not matches1
        # use the constraint given in posname(1) to search external data
        # evaluate externally created result, unless explicitly given no_eval=True in inputs
        do_eval = not (no_eval or is_ref_goal)
        if pos1.not_operator():
            matches = pos1.fallback_search(parent, all_nodes, goals, do_eval=do_eval, params=params)
        else:
            # for operators - find type they operate on (assuming unique), do fallback search on that
            # (NO consraints - use an "empty" node of that type), open result set, then filter with operator tree
            o = pos1.get_op_type()
            if o:
                # object found. That type's fallback search should explicitly deal with this case. Pass pos1 as parent
                #   e.g. Recipient: is_sub= self==node_fact.sample_nodes[self.typename()] and parent.is_operator()
                matches = node_fact.sample_nodes[o.__name__].fallback_search(pos1, all_nodes, goals, do_eval=do_eval,
                                                                             params=params)
        if cond and matches:
            objs = list(set(sum([n.get_op_objects(typs=[pos1.typename()]) for n in matches], [])))
            matches = [n for n in objs if
                       cond.match(n, iview=condview, oview=VIEW_INT, check_level=True, match_miss=match_miss)]
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

        self.signature.add_sig(posname(1), Node, view=VIEW_INT)
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
        all_nodes = all_nodes if all_nodes else []
        all_nodes = [n for n in all_nodes if not n.hide]
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
                                  match_miss)
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
        s = self.inputs[posname(1)].describe()
        if s:
            return 'I could not find any ' + s
        return ''


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
    root = node_fact.create_node_from_type_name(d_context, op, )  # create temp node (don't register yet)
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


def duplicate_subgraph(root, old_beg, new_beg, mode, inp_nm=None, omit_dup='omit_dup'):
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
        new_beg, dup_old_beg, done, ignore = old_beg.create_new_beg(new_beg, mode)
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
        new_beg.connect_in_out(inp_nm, nwsb, force=True)
        if o_in:
            o_in.remove_out_link(inp_nm, nwsb)

    # `new_beg` is a node whose inputs are similar to `old_beg`.
    # overwrite multiple inputs of (copy of) `old_beg`. Other inputs of `old_beg` are copied unchanged
    if mode == 'overwrite':  # TODO: check mutable
        n = new_subgraph[old_idx[old_beg]]  # copy of `old_beg`
        for i in new_beg.inputs:
            if i in n.inputs:
                # we already connected output links of old inputs to new node - remove those for overwritten inputs
                n.inputs[i].remove_out_link(i, n)
            n.add_linked_input(i, new_beg.inputs[i], new_beg.view_mode[i])

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
                n.add_linked_input(i, nd, new_beg.view_mode[i])

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
            new_beg.connect_in_out(pnm, n)

    for n in new_subgraph:  # hook for action after newly duplicated
        if n.just_dup:
            n.on_duplicate()
            n.just_dup = False

    # TODO: go over new subgraph, and for each node call `node.on_dup()`
    return new_subgraph


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
        self.signature.add_sig('mid', Node, view=VIEW_INT)  # middle constraint
        # TODO: similar to mid - add 'parent'? Means constraint to direct parent on THIS path
        self.signature.add_sig('midGoal', Node)  # like mid, but if no match found, then fall back to 'try-harder' -
        # create new graph - the new graph will be used as the match result
        # - i.e. ignoring 'root' and 'mid' related constraints. (oldLoc/new still apply)
        self.signature.add_sig('old', Node, view=VIEW_INT)  # oldLoc constraint -
        self.signature.add_sig('oclevel', Str)  # old clevel match mode - strict / prefer / any
        self.signature.add_sig('oldType', Str)  # oldLoc constraint - type of old (as Str, including ?'s)
        self.signature.add_sig('oldTypes', Node)  # like oldType, but expects a SET of strings instead of one string
        self.signature.add_sig(
            'oldNodeId', Str)  # oldLoc - specify existing node NAME - do NOT put '$'/'$#' before name!
        self.signature.add_sig('oldNode', Node)  # oldLoc - specify existing node - needs '$'/'$#' before name!
        self.signature.add_sig('role', Str)  # role constraint for oldLoc - find a node which is USED as input param
        self.signature.add_sig('hasParam', Str)  # means - find a node which HAS this input param
        self.signature.add_sig('hasTag', Str)  # means - find a node which has this tag
        self.signature.add_sig('new', Node, view=VIEW_INT)  # specification of new
        # TODO: check. Should we really use view=VIEW_INT?
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
        if 'new' not in self.inputs:
            raise MissingValueException('new', self)
        n_o = sum([1 for i in ['old', 'oldType', 'role', 'hasParam', 'oldNode', 'oldNodeId'] if i in self.inputs])
        if n_o < 1:
            raise IncompatibleInputException("refer node needs at least one of old/role/hasParam constraint", self)
        if ('oldNode' in self.inputs or 'oldNode' in self.inputs) and \
                ('inp_nm' not in self.inputs or self.get_dat('newMode') != 'extend'):
            raise IncompatibleInputException("revise: oldNode needs inp_nm and extend", self)
        if self.get_dat('no_eval_res'):
            self.eval_res = False
        # TODO: should we check that oldLoc mode is compatible with new mode (e.g. old=hasParam with new=extend?)

    def add_scored_matches(self, g, ig, m, matches):
        """
        Given goal (root) and mid, find and score matches for oldLoc, and add them to `matches`.
        """
        nodes = m.topological_order([], follow_res=False)  # nodes under m
        nodes = [n for n in nodes if not n.hide]
        candidates = nodes.copy()
        candidates0 = []
        ml = self.get_dat('oclevel')
        d_context = self.context
        match_level = 'strict' if not ml or ml not in ['strict', 'prefer', 'any'] else ml
        if 'old' in self.inputs:
            old, iview = self.get_inp_view_and_mode('old')
            if match_level != 'strict':
                candidates0 = [n for n in candidates if old.match(n, iview=iview, oview=VIEW_INT, check_level=False)]
                if match_level == 'any':
                    candidates = candidates0
                else:
                    candidates = [n for n in candidates if old.match(n, iview=iview, oview=VIEW_INT, check_level=True)]
            else:
                candidates = [n for n in candidates if old.match(n, iview=iview, oview=VIEW_INT, check_level=True)]
        if 'oldType' in self.inputs or 'oldTypes' in self.inputs:
            if 'oldType' in self.inputs:
                tp = [self.get_dat('oldType')]
            else:
                o = self.input_view('oldTypes')
                tp = [o.get_dat(i) for i in o.inputs]
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

        if 'oldNodeId' in self.inputs:  # oldNode is a string
            nd = d_context.get_node(self.get_dat('oldNodeId'))  # oldNode is a string
            candidates = [nd] if nd in candidates else []
        if 'oldNode' in self.inputs:  # oldNode is a Node
            nd = self.input_view('oldNode')  # most likely it's the result
            candidates = [nd] if nd in candidates else []
            # TODO: if oldNode is result ... (not in candidates)
        if 'role' in self.inputs:
            # TODO: allow period separated role string to specify multi-step path to candidate nodes
            # role = re.sub(' ', '_', self.get_dat('role'))
            role = self.get_dat('role')
            candidates = [n for n in candidates for m, o in n.outputs if
                          m == role or m == o.signature.real_name(role)]  # nodes which serve as role
            if not candidates:
                candidates = [n for n in candidates0 for m, o in n.outputs if
                              m == role or m == o.signature.real_name(role)]
        if 'hasParam' in self.inputs:
            param = self.get_dat('hasParam')
            candidates = [n for n in candidates if n.signature.allows_prm(param)]  # nodes which allow param
            if not candidates:
                candidates = [n for n in candidates0 if n.signature.allows_prm(param)]  # nodes which allow param
        if 'hasTag' in self.inputs:
            tg = self.get_dat('hasTag')
            candidates = [n for n in candidates if tg in n.tags]  # nodes which have this tag
            if not candidates:
                candidates = [n for n in candidates0 if tg in n.tags]

        # score matches and add to match list    TODO: more elaborate score function - take 'mid' into account?
        for o in candidates:
            score = ig * 100 + len(nodes) - nodes.index(o)  # nodes.index(o) - topological order of candidate
            if o in d_context.exception_nodes + d_context.copied_exceptions:
                # increase priority of node corresponding to exception. Higher priority if immediate exception
                score = score - 50 if o in d_context.exception_nodes else score - 25
            elif o.res in d_context.exception_nodes + d_context.copied_exceptions:
                # same if exception happened for its result
                score = score - 50 if o.res in d_context.exception_nodes else score - 25
            matches[(g, m, o)] = score
        return matches

    def get_goals(self, g):
        """
        Gets registered goals 'above' (and including) `g`. If none found, then return `g` itself.

        :param g: the goal
        :type g: Node
        :return: the goals above (including) `g`
        :rtype: List[Node]
        """
        goals = []
        d_context = self.context
        # TODO: `g.input_view()` instead of `g.inputs[]`?
        r = [g] if g.not_operator() else [g.inputs[i] for i in g.inputs]  # already sorted - most recent first
        for i in r:
            p = list(i.parent_nodes(res=True)[0].keys())
            for j in p:
                if j != self and j not in goals and j in d_context.goals:
                    goals.append(j)
        goals = [g for g in d_context.goals if g in goals]  # sort goals by order in `d_nodes.goals`
        if not goals:  # fallback to base behavior
            goals = r
        return goals

    def get_revise_matches(self, all_nodes, goals):
        """
        Finds matching (goal, mid, old) positions in graph:
            - for root: goal nodes of the specified type;
            - for old: nodes of the matching type under the found goals.
        """
        matches = {}
        rgoals = list(reversed(goals))
        new_mid = False
        if 'goal' in self.inputs or 'midGoal' in self.inputs:  # can't be both
            r = self.input_view('goal') if 'goal' in self.inputs else self.input_view('midGoal')
            rr = self.get_goals(r)  # registered goals (if existing)
            if 'midGoal' in self.inputs and r.not_operator() and \
                    rr[0] not in all_nodes:
                # midGoal node is not under old goals (incl result)
                new_mid = True  # it's a new node - no need to look at the old goals
            if 'goal' in self.inputs or new_mid:
                rgoals = rr
                # else - if not a midGoal matched existing node - then stay with the original goals
        for ig, g in enumerate(rgoals):  # search for root
            ok = g != self and (g.typename() not in ['revise'] or not g.evaluated)
            # TODO: careful with giving a non-empty constraint on out_type!
            # TODO: robustness in combination with fetch - which can return object/constraint/program!
            if ok and 'root' in self.inputs:
                r, iview = self.get_inp_view_and_mode('root')
                ok = ok and r.match(g, iview=iview, oview=VIEW_INT, check_level=True)
            if ok:
                if 'mid' in self.inputs or 'midGoal' in self.inputs:
                    mids = g.topological_order([], follow_res=False)  # nodes under g
                    if 'mid' in self.inputs:  # select nodes which match constraint
                        mm, miview = self.get_inp_view_and_mode('mid')
                        mids = [n for n in mids if mm.match(n, iview=miview, oview=VIEW_INT, check_level=True)]
                    if 'midGoal' in self.inputs:  # select nodes which are in midGoal (one or set)
                        mg = self.input_view('midGoal').unroll_set_objects([])
                        mids = [n for n in mids if n in mg]
                else:  # if no 'mid' specified - set it to the root
                    mids = [g]
                for m in mids:
                    # skip if (g, m) were already checked
                    if not [1 for (og, om, oo) in matches if og == g and om == m]:
                        matches = self.add_scored_matches(g, ig, m, matches)

        matches = sorted(matches, key=matches.get)
        # TODO: fallback search?
        return matches

    def exec(self, all_nodes=None, goals=None):
        """
        If found matches:
            - rank and choose best (root, mid, old);
            - construct (and evaluate) graph for new;
            - copy necessary nodes between old and root - reuse nodes (point to existing nodes) as much as possible;
            - insert the new graph in the copy (instead of old).
        """
        matches = self.get_revise_matches(all_nodes, goals)
        if len(matches) == 0:
            raise NoReviseMatchException(self)

        root, mid, old = matches[0]  # use only best match
        mode = self.get_dat('newMode') if 'newMode' in self.inputs else 'new'
        inp_nm = self.get_dat('hasParam') if 'hasParam' in self.inputs else \
            self.get_dat(
                'role') if 'role' in self.inputs else ''  # TODO: additional input to specify name of extension?
        inp_nm = self.get_dat('inp_nm') if 'inp_nm' in self.inputs else inp_nm
        omit_dup = self.get_dat('omit_dup') if 'omit_dup' in self.inputs else ['omit_dup']
        new_subgraph = duplicate_subgraph(root, old, self.input_view('new'), mode, inp_nm, omit_dup=omit_dup)

        if len(new_subgraph) == 0:
            return None
        goal = new_subgraph[-1]  # root of duplicated graph
        self.set_result(goal)  # set result to point to duplicated graph before evaluating it (it might fail)

        ng = self.get_dat('no_add_goal')
        if not ng:
            self.context.add_goal(goal)

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
        if not sig.allows_prm(nm):
            raise InvalidResultException(
                "getattr- %s : signature does not have a field %s" % (self.input_view(posname(2)).typename(), nm), self)
        if nm not in res.inputs:
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
        val = r.describe()
        nd = self.input_view(posname(2))
        attr = self.get_dat(posname(1))
        msg = nd.getattr_yield_msg(attr, val)
        return msg

    def trans_simple(self, top):
        nd = self.input_view(posname(2))
        # add a 'singleton' wrapper around input nodes which may return multiple results
        if nd and nd.signature.multi_res == True:  # or maybe even just != False
            self.wrap_input(posname(2), 'singleton(')
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
            raise MissingValueException("filter/index", self)

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

    # no need to do anything! the evaluation process already takes care of evaluating the inputs before we get here.
    # result points to result of last input
    def exec(self, all_nodes=None, goals=None):
        n_exp = max([posname_idx(i) for i in self.inputs])
        self.set_result(self.inputs[posname(n_exp)].res)


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
                    raise e


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
            else:
                idx = 1  # if no idx given, choose the first (positive) option
            sexp = prev_sugg[idx]
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
                    g, e = Node.call_construct_eval(sexp, self.context, do_trans_simp=True)
                    self.set_result(g)
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
        s = n.yield_msg()  # call object's method to generate answer.
        # (some objects may further chain it to their inputs...)
        if s:
            self.context.add_message(self, MSG_YIELD + s)
        self.set_result(n)


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
    Checks if the input expression has a non-empty result.
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
        r = self.res.dat
        inp = self.input_view(posname(1))
        if r:
            msg = 'Looks like it.'
            s = inp.describe()
            if s:
                msg += ' NL ' + s
        else:
            s = inp.yield_failed_msg(params)
            if s:
                msg = 'No. ' + s
            elif inp.out_type is not None:
                msg = 'No. I could not find any %s' % node_fact.sample_nodes[inp.out_type.__name__].obj_name_singular
            else:
                msg = 'No. I could not find anything.'
        return msg

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
