"""
Base node types.
"""

from opendf.defs import posname
from opendf.graph.nodes.node import Node


# ################################################################################################
# ###################################### special Node types ######################################

# Base types - leaf (no inputs) holding a basic type - int, string, float, bool
# originally only these types were allowed to hold data (later relaxed, but still under consideration)

def default_qualifier(op1, op2):
    return op1 == op2


class Int(Node):
    def __init__(self):
        super().__init__(type(self))

    def generate_sql_where(self, selection, parent_id, **kwargs):
        qualifier = kwargs.get("qualifier", default_qualifier)
        return selection.where(qualifier(parent_id, self.dat))


class Float(Node):
    def __init__(self):
        super().__init__(type(self))

    def generate_sql_where(self, selection, parent_id, **kwargs):
        qualifier = kwargs.get("qualifier", default_qualifier)
        return selection.where(qualifier(parent_id, self.dat))


class Bool(Node):
    def __init__(self):
        super().__init__(type(self))

    def generate_sql_where(self, selection, parent_id, **kwargs):
        qualifier = kwargs.get("qualifier", default_qualifier)
        return selection.where(qualifier(parent_id, self.dat))


class Str(Node):
    def __init__(self):
        super().__init__(type(self))

    def func_EQ(self, ref, op=None):
        sl, rf = self.dat, ref.dat
        if sl is not None and rf is not None:
            if rf.lower() == sl.lower():
                return True
        return False

    def func_LIKE(self, ref):
        sl, rf = self.res.dat, ref.res.dat  # note - sl different from base definition
        if sl is not None and rf is not None:
            if rf == sl:
                return True
            if isinstance(rf, str) and isinstance(sl, str):
                if sl.lower() in rf.lower():
                    return True
        return False

    def generate_sql_where(self, selection, parent_id, **kwargs):
        qualifier = kwargs.get("qualifier", default_qualifier)
        return selection.where(qualifier(parent_id, self.dat))


class CasedStr(Node):
    def __init__(self):
        super().__init__(type(self))

    def generate_sql_where(self, selection, parent_id, **kwargs):
        qualifier = kwargs.get("qualifier", default_qualifier)
        return selection.where(qualifier(parent_id, self.dat))


# ################################################################################################

class Index(Node):
    """
    Used as index, e.g. in filtering.
    """

    def __init__(self):
        super().__init__(type(self))
        self.signature.add_sig(posname(1), Int)
        # not checking if it has a value - allow it to be "empty"


class Dummy(Node):
    """
    A dummy type with no inputs. e.g. use: for debugging - "hang" some intermediate nodes on this node's result -
    so they will be drawn. Putting it on the result is safer - they are hidden from revise.
    """

    def __init__(self):
        super().__init__()


class Debug(Node):
    """
    same as Dummy. more dignified name :)
    """

    def __init__(self):
        super().__init__()


class DummyRoot(Node):
    """
    aux type used for trans_simple
    """

    def __init__(self):
        super().__init__()
        self.signature.add_sig(posname(1), Node)


# ################################################################################################

EMPTY_CLEAR_FIELDS = {'Empty', 'Clear'}


class Empty(Node):
    """
    A node to sign to the match and pruning mechanism that the field should be empty.
    """

    def __init__(self):
        super().__init__(Node)

    def generate_sql_where(self, selection, parent_id, **kwargs):
        if parent_id is not None:
            return selection.where(parent_id == None)

        return None


class Clear(Node):
    """
    A node to sign to the match and pruning mechanism that all constraints for an input field have been cleared
    """

    def __init__(self):
        super().__init__(Node)

    def generate_sql_where(self, selection, parent_id, **kwargs):
        return selection


def has_emtpy(nodes):
    """
    Checks if there is an `Empty` node in `nodes`.

    :param nodes: a iterable of Nodes
    :type nodes: Iterable[Node]
    :return: `True`, if there is an `Empty` node in `nodes`; otherwise, `False`
    :rtype: bool
    """
    for node in nodes:
        if isinstance(node, Node) and node.typename() in {'Empty', 'Clear'}:
            return True

    return False


# ################################################################################################
# ######################################## just for demo  ########################################

class Add(Node):
    def __init__(self):
        super().__init__(Int)  # Dynamic output type
        self.signature.add_sig(posname(1), Int, True)
        self.signature.add_sig(posname(2), Int, True)

    def exec(self, all_nodes=None, goals=None):
        p1 = self.get_dat(posname(1))
        p2 = self.get_dat(posname(2))
        r = p1 + p2
        d, e = self.call_construct_eval('Int(%d)' % r, self.context)
        self.set_result(d)
