from opendf.defs import posname
from opendf.graph.nodes.framework_objects import Str
from opendf.graph.nodes.node import Node


class UpperCase(Node):

    def __init__(self):
        super(UpperCase, self).__init__(Str)
        self.signature.add_sig(posname(1), Str, True)

    def exec(self, all_nodes=None, goals=None):
        string: str = self.get_dat(posname(1))
        g, _ = self.call_construct(f"Str({string.upper()})", self.context)
        self.set_result(g)
