
from opendf.applications.smcalflow.nodes.functions import *


class Mult(Node):
    def __init__(self):
        super().__init__(Int)
        self.signature.add_sig(posname(1), Int, True)
        self.signature.add_sig(posname(2), Int, True)

    def exec(self, all_nodes=None, goals=None):
        p1 = self.get_dat(posname(1))
        p2 = self.get_dat(posname(2))
        r = p1 * p2
        d, e = self.call_construct_eval('Int(%d)' % r, self.context)
        self.set_result(d)
