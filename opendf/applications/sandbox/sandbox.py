import random
from opendf.applications.smcalflow.nodes.functions import *
from opendf.graph.nodes.node import Node
from opendf.graph.nodes.framework_functions import get_refer_match
from opendf.applications.smcalflow.nodes.functions import (
    Message, Int, Bool, Str)
from opendf.exceptions.df_exception import (
    DFException, InvalidValueException)
from opendf.exceptions.__init__ import re_raise_exc
from opendf.defs import posname


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


class UpperCase(Node):

    def __init__(self):
        super(UpperCase, self).__init__(Str)
        self.signature.add_sig(posname(1), Str, True)

    def exec(self, all_nodes=None, goals=None):
        string: str = self.get_dat(posname(1))
        g, _ = self.call_construct(f"Str({string.upper()})", self.context)
        self.set_result(g)
