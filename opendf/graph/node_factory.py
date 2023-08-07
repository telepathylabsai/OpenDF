"""
Factory to create the nodes. It does not depend on Node.
"""
from collections import defaultdict
from opendf.exceptions.python_exception import UnknownNodeTypeException
import re
from opendf.defs import *
from opendf.utils.utils import get_type_and_clevel, to_list, get_subclasses
from opendf.defs import posname
from opendf.exceptions.python_exception import SemanticException

# Intentionally does not formally depend on Node

logger = logging.getLogger(__name__)


# This class is more than just a factory
# it also holds general information about all node types, and some useful functions related to node types and names
# However, by design, it's formally NOT dependent on the node classes - to avoid circular dependencies
# Thus, it can be included from Node and vice versa
# It's a singleton, which AFTER initialization needs to be filled (by an EXTERNAL function which does depend on all
#   node types)

# factory method: return an instance of a subclass of Node, from the type matching the input name
# currently set up as a singleton, but not really necessary (except maybe to save some initialization computation)
class NodeFactory:
    """
    The node factory.
    """

    __instance = None

    @staticmethod
    def get_instance():
        if NodeFactory.__instance is None:
            NodeFactory.__instance = NodeFactory()
        return NodeFactory.__instance

    def __init__(self):
        """
        Virtually private constructor.
        """
        if NodeFactory.__instance is None:
            NodeFactory.__instance = self
        else:
            raise SingletonClassException()

        self.node_types = None  # { node name : node type }
        self.sample_nodes = None  # { node name : instantiated node of this type }
        self.leaf_types = None  # list of node type names which are leaf type; can accept only one real input,
        #  and that input is a base type

        self.leaf_in_type = None
        # { leaf typename : [param name, param type name }  e.g. { 'Year' : (posname(10, 'Int')}

        self.operators = []
        self.modifiers = []
        self.aggregators = []
        self.qualifiers = []
        # for generator
        self.gen_out = defaultdict(set)  # for each type - which nodes can generate this type (have this out type)
                                         # X is in gen_out[Y] --> X can output Y
        self.has_type_prm = defaultdict(set)  # for each node - find nodes which have this type as input
                                              # save as (node, inp_name)
                                              # (X, nm) is in has_type_prm[Y] --> X.inputs[nm] can be Y

    def create_node_from_type_name(self, d_context, name, register, tags=None):
        name, clevel = get_type_and_clevel(name)
        # name = re.sub('\?', '', name)
        t = self.node_types[name]
        nd = t()
        nd.created_turn = d_context.get_turn_num() if d_context else 0
        nd.constraint_level = clevel
        nd.inputs.aliases = nd.signature.aliases  # for using AliasedODict for inputs[]
        if register and d_context:
            d_context.register_node(nd)
        if tags:
            nd.add_tags(tags)
        nd.context = d_context
        return nd

    def gen_node(self, d_context, name, register=True, constr_tag=None):
        if name[0] == '$':  # link to existing node
            if not d_context:
                raise SemanticException('Context error - trying to use assign without context')
            nd = d_context.get_node(name)
            return nd

        # create new node
        # handle constraint types - including aggregators and qualifiers - these are marked with '[]'
        clevel = 0

        # for functions with dynamic output
        out_typ = None

        s = re.sub('[\]\[]', ' ', name).split()  # MS style - e.g Constraint[Event]

        if len(s) > 1:
            clevel = name.count('Constraint')
            outn = re.sub('\?', '', s[-1])
            if outn not in self.node_types:
                raise UnknownNodeTypeException(outn)
            out_typ = self.node_types[outn]
            name = outn
        elif name[-1] == '?':  # sugared constraint syntax - allow "Event?" instead of "Constraint[Event]"
            name, clevel = get_type_and_clevel(name)
            # name = re.sub('\?', '', name)
            logger.debug(name)
            if name not in self.node_types:
                raise UnknownNodeTypeException(name)

        if name in self.node_types:
            nd = self.create_node_from_type_name(d_context, name, register, constr_tag)
            # Note: now the node has already been initialized - be very careful overwriting any node values!!!
            #       (if forgetting this - node values would seem to magically change!)
            nd.constraint_level = clevel

            # for given out_type
            if out_typ is not None:
                nd.out_type = out_typ
            # for given constraint out level (for object types only)
            return nd
        else:
            raise UnknownNodeTypeException(name)

    def is_dynamic_out_type(self, tp):
        if tp in self.sample_nodes and self.sample_nodes[tp].out_type == self.node_types['Node']:
            return True
        return False

    # get type names which have just one base input - they will be summarized (not drawn)
    def set_leaf_types(self):
        lt = []
        it = {}
        for nm in self.sample_nodes:
            n = self.sample_nodes[nm]
            t = [i for i in n.signature if not n.signature[i].prop]
            if len(t) == 1 and n.signature[t[0]].match_tnames(base_types):
                lt.append(nm)
                it[nm] = (t[0], n.signature[t[0]].type_name())
        self.leaf_types = lt
        self.leaf_in_type = it

    # wrap a list of nodes into a n aggregator.
    # if given only one node - behavior depend on flag wrap_one
    def make_agg(self, ns, register=True, wrap_one=False, agg=None):
        agg = agg if agg else 'SET'
        if not ns:
            return None
        if len(ns) == 1 and not wrap_one:
            return ns[0]
        if not isinstance(ns, list):
            if not wrap_one:
                return ns
            ns = [ns]
        r = self.create_node_from_type_name(ns[0].context, agg, register)
        for i, n in enumerate(ns):
            r.add_linked_input(posname(i + 1), n)
        return r

    # initializations after filled with types
    def init_lists(self):
        self.operators = [i.__name__ for i in list(get_subclasses(self.node_types['Operator']))]
        self.modifiers = [i.__name__ for i in list(get_subclasses(self.node_types['Modifier']))]
        self.aggregators = [i.__name__ for i in list(get_subclasses(self.node_types['Aggregator']))]
        self.qualifiers = [i.__name__ for i in list(get_subclasses(self.node_types['Qualifier']))]

    def init_gen(self):
        # for generator - collect nodes which have outputs/inputs for each one of the node types
        #
        # gen_out[x] = [a,...] means that a is a nodes whose return type is x
        #              (or one of the output types is x, in case of multiple out types)
        #  e.g. gen_out[Date] includes Today()
        #
        # has_type_prm[x] = [(y,a), ...] means that y is a node whose input a has x as one of its allowed types
        #  e.g. has_type_prm[Date] includes (DateTime, 'date')
        for nm in self.sample_nodes:
            n = self.sample_nodes[nm]
            ts = n.out_type  # we may allow multiple out types (?)
            for t in to_list(ts):
                self.gen_out[t].add(type(n))
            if n.is_object():
                sg = n.signature
                for i in sg:
                    ts = to_list(sg[i].type)
                    for t in ts:
                        self.has_type_prm[t].add((type(n), i))
        x=1

    # dump all nodes' signatures to a file
    def dump_node_types(self, pname, bname):
        params, bases = {}, {}
        for i in self.sample_nodes:
            if i != 'Node':  # not in NODE:
                s = self.sample_nodes[i]
                params[i] = {j: [k.__name__ for k in to_list(s.signature[j].type)] for j in s.signature}
                bases[i] = type(s).__bases__[0].__name__  # base class of each node
        import json
        open(pname, 'w').write(json.dumps(params))
        open(bname, 'w').write(json.dumps(bases))

    # dump all nodes' signatures to a file # TODO: make another fct and keep old as it was
    def dump_node_types_and_params(self, pname, bname, no_equal=False):
        params, bases = {}, {}
        save_f_nodes = True
        logger.info("Saving node types into ../analyze/conv/%s_signatures.txt", bname)
        f_nodes = open("../analyze/conv/" + bname + "_signatures.txt", 'w')
        set_signatures = set()

        for i in self.sample_nodes:
            if i != 'Node':  # not in NODE:
                s = self.sample_nodes[i]
                params[i] = {j: [k.__name__ for k in to_list(s.signature[j].type)] for j in s.signature}
                bases[i] = type(s).__bases__[0].__name__  # base class of each node
                if save_f_nodes:
                    suffix = {'\n', '?\n', '??\n', '(\n', '?(\n', '??(\n'}
                    for item in suffix:
                        f_nodes.write(i + item)
                    set_signatures.update([j for j in s.signature])

        import json
        open(pname, 'w').write(json.dumps(params))
        open(bname, 'w').write(json.dumps(bases))
        suffix = {'\n', '(\n'}
        if not no_equal:
            suffix.add('=\n')
        if save_f_nodes:
            for sign in set_signatures:

                for suff in suffix:
                    f_nodes.write(sign + suff)
                f_nodes.write(':' + sign + '\n')
                f_nodes.write(':' + sign + '(\n')
            if no_equal:
                f_nodes.write("=\n")
            f_nodes.close()
