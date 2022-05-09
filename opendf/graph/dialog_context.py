"""
Singleton class to hold goals and exceptions, and to assign unique node ids.
"""

# note - this is a general class - does not really know what types it holds, so no dependencies on anything
from opendf.defs import *
from opendf.exceptions.df_exception import DFException
from opendf.exceptions import parse_node_exception


# Intentionally does not formally depend on Node
from opendf.exceptions.python_exception import SemanticException


logger = logging.getLogger(__name__)

class DialogContext:
    """
    Holds the context relevant to a single conversation - graph, exceptions, messages, ...
    """

    # __instance = None
    #
    # @staticmethod
    # def get_instance():
    #     """
    #     Static access method.
    #     """
    #     if DialogContext.__instance is None:
    #         DialogContext.__instance = DialogContext()
    #     return DialogContext.__instance

    def __init__(self):
        # """
        # Virtually private constructor.
        # """
        # if DialogContext.__instance is None:
        #     DialogContext.__instance = self
        # else:
        #     raise SingletonClassException()

        self.idx_to_node = {}  # { node_id : node }
        self.goals = []
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
        # self.show_print = True
        self.register_offset = 0  # hack - allow to "hide" a bunch of nodes - e.g. external DB
        self.supress_exceptions = False  # hack, useful when running batch conversion - should this be HERE?
        self.prev_nodes = None  # used for simplify - NOT automatically cleared

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

    def register_node(self, node):
        if node.id is None:
            i = len(self.idx_to_node) + self.register_offset
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

    def add_message(self, nd, msg):
        self.messages.append((nd, msg))

    def most_recent_goal(self, nds):
        gls = [i for i, g in enumerate(self.goals) if g in nds]
        if gls:
            return self.goals[gls[-1]]
        return None

    def set_print(self, v):
        self.show_print = v

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
