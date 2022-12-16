"""
Singleton class to hold goals and exceptions, and to assign unique node ids.
"""

# note - this is a general class - does not really know what types it holds, so no dependencies on anything
from opendf.defs import *
from opendf.exceptions.df_exception import DFException
from opendf.exceptions import parse_node_exception
from copy import copy

# Intentionally does not formally depend on Node
from opendf.exceptions.python_exception import SemanticException


logger = logging.getLogger(__name__)

class DialogContext:
    """
    Holds the context relevant to a single conversation - graph, exceptions, messages, ...
    """

    def __init__(self):
        self.idx_to_node = {}  # { node_id : node }
        self.goals = []
        self.other_goals = []  # goals which are excluded from the normal search of refer/revise
                               # todo - we may want to have several sets of "other goals" (e.g a dict of lists...?)
        self.exceptions = []
        self.messages = []
        # TODO: keep track of exceptions' age (which could help is selecting e.g. an oldLoc node candidate in revise)
        # currently, we keep just the last exception, and copied_exceptions don't survive the next duplication
        #   - so no need
        self.exception_nodes = []  # only the nodes (without msg and hints).
        self.copied_exceptions = []  # duplicated nodes, whose original nodes had an exception.
        # they are used to prioritize nodes in searches (refer/revise)
        self.assign = {}  # bound variables: name -> node
        self.res_assign = {}  # bound variables: name -> node.result. Temporary storage until result is evaluated
        self.turn_num = 0
        self.continued_turn = False  # if `True`: agent should "wait" (in some actions) until user is done
        self.prev_agent_hints = None  # hints (from prev turn) used for translating NLU output to sexp
        self.prev_sugg_act = None  # suggestions from agent (in prev turn) which can be recalled by user's sexp
        # list of sexps. by default, the first one is the action to take on rejection
        # SUGG_IMPL_AGR marks a suggested sexp as implicit accept - to be executed if no explicit
        # accept/reject is given
        self.register_offset = 0  # hack - allow to "hide" a bunch of nodes - e.g. external DB
        self.supress_exceptions = True  # <<<  hack, useful when running batch conversion - should this be HERE?
        self.prev_nodes = None  # used for simplify - NOT automatically cleared
        self.res = None  # temp field used for packing/unpacking
        self.res_pnt = None  # temp field used for packing/unpacking
        self.restore_points = []  # restore previous state

        self.init_stub_file = "opendf/applications/smcalflow/data_stub.json"
        # self.link_res = []

    def clear(self):
        self.idx_to_node = {}
        self.goals = []
        self.exceptions = []
        self.messages = []
        self.exception_nodes = []
        self.copied_exceptions = []
        self.assign = {}
        self.res_assign = {}
        self.turn_num = 0
        self.continued_turn = False
        self.prev_agent_hints = None
        self.prev_sugg_act = None
        self.register_offset = 0
        self.restore_points = []


    # register a node - give it an id and add it to dict of nodes.
    # if renumber is given, force the given id. if that id already exists (should not happen!) - warn and get a new id
    # note - renumber is LOCAL only - it will not change any references to the old id
    def register_node(self, node, renumber=None):
        if node.id is None or (renumber is not None and renumber!=node.id):
            if renumber is not None:
                if renumber in self.idx_to_node:
                    print('WARN - renumber id already exists! - ignoring (%s)' % renumber)
                    raise Exception("bad renumber %s" % renumber)
                if node.id is not None:
                    del self.idx_to_node[node.id]
            i = renumber if renumber is not None else len(self.idx_to_node) + self.register_offset
            while i in self.idx_to_node:  # avoid overwriting existing node id
                i += 1
            self.idx_to_node[i] = node
            node.id = i
            node.context = self

    def num_registered(self):
        return len(self.idx_to_node)

    def replace_node(self, node, id):
        if id not in self.idx_to_node:
            logger.warning('Error - trying to replace non existing node - %d', id)
            exit(1)
        self.idx_to_node[id] = node

    # def get_node(self, idx):
    #     if idx in self.idx_to_node:
    #         return self.idx_to_node[idx]
    #     return None

    def add_goal(self, g, allow_dup=False, move_up=True):
        if g not in self.goals or allow_dup:
            self.goals.append(g)
        elif move_up:
            self.goals = [i for i in self.goals if i != g]
            self.goals.append(g)
        if g.typename() in unique_goal_types:
            self.goals = [i for i in self.goals if i!=g and i.typename()!=g.typename()] + [g]

    def switch_goal_order(self, i1, i2):
        n = len(self.goals)
        if i1!=i2 and -n < i1 < n and -n < i2 < n:
            self.goals[i1], self.goals[i2] = self.goals[i2], self.goals[i1]

    def remove_goal(self, g):
        self.goals = [i for i in self.goals if i != g]

    # if only_one_exception - keep only one exception (to display / report to user)
    #   - generally, this means we keep only the LAST exception of the evaluation.
    #   - we can disable overwriting the exception by using keep_old - if True/not None, it will not be overwritten
    #     - note that keep_old has to be external - it depends on the computation being done.
    def add_exception(self, ex, keep_old=False):
        # TODO: update old exceptions' "age"?
        if only_one_exception:
            if not self.exceptions or not keep_old:
                self.exceptions = [ex]
        else:
            if ex not in self.exceptions or not unique_exception:
                self.exceptions.append(ex)
        self.exception_nodes = [parse_node_exception(e)[1] for e in self.exceptions]
        return self.exceptions[-1]  # returns last exception

    def clear_exceptions(self):
        self.exceptions = []

    def get_node_exceptions(self, nd):
        return [e for e in self.exceptions if e.node==nd]

    def set_prev_agent_turn(self, ex):
        if not self.continued_turn:
            if ex is None or not ex:
                self.prev_agent_hints = None
                self.prev_sugg_act = None
            else:
                if isinstance(ex, list):
                    ex = ex[0]
                if isinstance(ex, DFException):
                    ex = ex.chain_end()
                m, n, h, sg = parse_node_exception(ex)  # CHECK
                self.prev_agent_hints = h
                self.prev_sugg_act = sg

    def add_assign(self, nm, n):
        if nm[-1] == '~':  # a '~' at the end of the assign name means the assignment is to the RESULT of the node
            self.res_assign[nm[:-1]] = n
            self.assign[nm[:-1]] = n  # will be set to the result node after successful evaluation
        else:
            self.assign[nm] = n

    def get_assign(self, nm):
        if nm in self.assign:
            return self.assign[nm]
        return None

    def has_assign(self, nm):
        return nm in self.assign

    # nm can be one of:
    # $name / name - will look for name in assigned names
    # $#num / #num / num - will look for node with this id number
    def get_node(self, nm, raise_ex=True):
        if isinstance(nm, str) and nm.isnumeric():
            nm = int(nm)
        if isinstance(nm, int):
            if nm in self.idx_to_node:
                return self.idx_to_node[nm]
            elif raise_ex:
                raise SemanticException('Error - unknown node #%d' % nm)
            else:
                return None
        if nm[0] == '$':
            nm = nm[1:]
        if nm[0] == '#':
            if nm[1:].isnumeric():
                return self.get_node(int(nm[1:]))
            elif raise_ex:
                raise SemanticException('Error - bad node name format %s' % nm)
            else:
                return None
        if nm in self.assign:
            return self.assign[nm]
        if raise_ex:
            raise SemanticException('Error - unknown node name %s' % nm)
        else:
            return None

    def get_turn_num(self):
        return self.turn_num

    def reset_turn_num(self):
        self.turn_num = 0

    def inc_turn_num(self):
        self.turn_num += 1

    def reset_messages(self):
        self.messages = []

    # old signature was add_message(node, msg)  (where msg was originally just text, but sometimes tuple (txt, objs)
    # new one is add_message(msg), where msg is a Message
    # in the old case, we create a Message
    # in any case, we fill the Message.turn (unless already filled)
    def add_message(self, p1, p2=None):
        if p2 is not None:  # old style
            if isinstance(p2, Message):
                msg = p2
                msg.node = p1
            else:
                if isinstance(p2, tuple):
                    t, o = p2
                elif isinstance(p2, str):
                    t, o = p2, None
                else:
                    raise Exception('Bad usage of add_message : %s' % p2)
                msg = Message(t, p1, o)
        else:
            msg = p1
        if not msg.node:
            raise Exception('Bad message - no node!')
        msg.turn = self.turn_num if msg.turn is None else msg.turn
        # self.messages.append((nd, msg))
        self.messages.append(msg)

    # def get_node_messages(self, nd):
    #     return [m for (n, m) in self.messages if n.id == nd.id]

    def get_node_messages(self, nd):
        return [m for m in self.messages if m.node and m.node.id == nd.id]

    # move messages from source node to destination node
    # def move_messages(self, src, dst):
    #     msgs = []
    #     for nd, ms in self.messages:
    #         if nd==src:
    #             nd = dst
    #         msgs.append((nd, ms))
    #     self.messages = msgs

    def move_messages(self, src, dst):
        msgs = []
        for m in self.messages:
            m.node = dst if m.node==src else m.node
            msgs.append(m)
        self.messages = msgs

    def most_recent_goal(self, nds):
        gls = [i for i, g in enumerate(self.goals) if g in nds]
        if gls:
            return self.goals[gls[-1]]
        return None

    # def set_print(self, v):
    #     self.show_print = v

    # these functions are needed for controlling node id's (does not affect any behavior, exclusively cosmetic value)
    def get_next_node_id(self):
        return len(self.idx_to_node) + self.register_offset

    def set_next_node_id(self, v=0):
        self.register_offset = v - len(self.idx_to_node)

    def get_highest_node_id(self):
        if len(self.idx_to_node) == 0:
            return 0
        return sorted(list(self.idx_to_node.keys()))[-1]

    def is_assigned(self, n):
        return n in self.assign.values()

    def replace_assign(self, n1, n2):
        nm = [i for i in self.assign if self.assign[i] == n1]
        for m in nm:
            self.assign[m] = n2

    # pack / unpack context
    # TODO -
    #   - handle additional node attributes (which are not in the base Node class)  (as tags?)
    #   - add counters  (as tags?, special_feat syntax?)
    #   - possibly add base function which takes a string and fills note attr's
    #     - and inverse func which dumps attrs to a string (and then added to the node string in compr_tree)
    def pack_context(self, pack):
        goals = []
        goal_types = [i.typename() for i in self.goals]
        for i, g in enumerate(goal_types):
            if g not in unique_goal_types or g not in goal_types[i + 1:]:
                goals.append(self.goals[i])

        # all the nodes we want to save - reachable from the goals (possibly through .result link)
        nodes = []
        for g in goals + self.other_goals:
            nds = g.topological_order()
            nodes += nds

        # if no suggestions (especially - no suggestions referring to specific node numbers!) -
        #    then we could renumber the nodes, to keep the index low
        #    (but that would mean different node id's between turns, which could be confusing for debugging)

        # get the graphs for the goals - excluding result
        seen = []
        pack.goals = []
        for ig, g in enumerate(goals):
            st, seen = g.compr_tree(seen)
            # if True:
            #     from opendf.parser.pexp_parser import parse_p_expressions
            #     try:
            #         x = parse_p_expressions(st)
            #     except Exception as ex:
            #         ss = g.show()
            #         print('Bad expression for goal #%d: %s' % (ig,st))
            pack.goals.append(st)

        for g in self.other_goals:
            st, seen = g.compr_tree(seen)
            pack.other_goals.append(st)

        # missing nodes are results - build separate graphs for them
        pack.res = []
        done = False
        while not done:
            done = True
            for n in nodes:
                if n.id not in seen and n.res_out:
                    done = False
                    st, seen = n.compr_tree(seen)
                    pack.res.append(st)

        # store .result links separately (avoid need to directly set result in construct)
        pack.res_pnt = {}
        for n in nodes:
            if n.result != n:
                pack.res_pnt[n.id] = n.result.id

        for e in self.exceptions:
            if e.node in nodes:
                # ee = type(e)(e.message, e.node.id, hints=e.hints, suggestions=e.suggestions, orig=e.orig, chain=e.chain)
                # ee = e.dup()
                ee = copy(e)
                ee.node = e.node.id
                pack.exceptions.append(ee)

        for e in self.exception_nodes:
            if e in nodes:
                pack.exception_nodes.append(e.id)

        for e in self.copied_exceptions:
            if e in nodes:
                pack.copied_exceptions.append(e.id)

        pack.prev_agent_hints = self.prev_agent_hints
        pack.prev_sugg_act = self.prev_sugg_act
        pack.turn_num = self.turn_num
        # pack.messages = [(nd.id, msg) for nd, msg in self.messages]
        pack.messages = [Message(m.text, m.node.id, m.objects, m.turn) for m in self.messages]

        return pack

    def unpack_context(self, node, unpack):
        # we pass a node because we cannot import Node here due to
        # cycles in references

        unpack.prev_agent_hints = self.prev_agent_hints
        unpack.prev_sugg_act = self.prev_sugg_act
        unpack.turn_num = self.turn_num

        for s in self.goals:
            g, _ = node.call_construct(s, unpack, constr_tag=None)
            unpack.goals.append(g)

        for s in self.other_goals:
            g, _ = node.call_construct(s, unpack, constr_tag=None)
            unpack.other_goals.append(g)

        if self.res:
            for s in self.res:
                g, _ = node.call_construct(s, unpack, constr_tag=None)

        for n in self.res_pnt:
            r = unpack.idx_to_node[self.res_pnt[n]]
            m = unpack.idx_to_node[n]
            m.set_result(r)

        for e in self.exceptions:
            # ee = type(e)(e.message, unpack.idx_to_node[e.node], hints=e.hints,
            #              suggestions=e.suggestions, orig=e.orig, chain=e.chain)
            # ee = e.dup()
            ee = copy(e)
            ee.node = unpack.idx_to_node[e.node]
            unpack.exceptions.append(ee)

        for e in self.exception_nodes:
            unpack.exception_nodes.append(unpack.idx_to_node[e])

        for e in self.copied_exceptions:
            unpack.copied_exceptions.append(unpack.idx_to_node[e])

        # unpack.messages = \
        #     [(unpack.idx_to_node[nd_id], msg) for nd_id, msg in self.messages if nd_id in unpack.idx_to_node]
        unpack.messages = \
            [Message(m.text, unpack.idx_to_node[m.node], m.objects, m.turn) for m in self.messages
             if m.node in unpack.idx_to_node]

        return unpack

    # make a copy of this context, through packing and unpacking (some info is not preserved!)
    def make_copy_with_pack(self):
        nd = self.get_node(0)  # needs a dummy node as input, to access Node functions
        return self.pack_context(DialogContext()).unpack_context(nd, DialogContext())

    def get_exec_status(self):
        if not self.goals:
            return None, None, None
        gl = self.goals[-1]
        i_turn = gl.created_turn
        msg = [i for i in self.messages if i.node.created_turn==i_turn]  # todo - change condition to use message.turn
        exc = [i for i in self.exceptions if i.node.created_turn==i_turn]  # todo - change condition to use exception.turn
        return i_turn, exc, msg
