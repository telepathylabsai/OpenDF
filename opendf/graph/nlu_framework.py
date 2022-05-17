"""
Stores NLU classes and functions.
"""

# file to store NLU classes and functions, still experimental (UNUSED!)

NLU_INTENT = 1
NLU_SLOT = 2
NLU_TREE = 3


class nlu_out:
    def __init__(self, typ, name=None, val=None, consumed=False):
        self.typ = typ  # intent, slot (flat/single entity), tree (hierarchical entity tree)
        self.name = name
        self.val = val
        self.consumed = consumed

    def __repr__(self):
        t = 'INTENT' if self.typ == NLU_INTENT else 'SLOT' if self.typ == NLU_SLOT else 'TREE'
        return '%s: %s / %s / %s' % (t, self.name, self.val, self.consumed)


class NLU(list):
    def __init__(self):
        super().__init__()

    def has_type(self, typ):
        return True if [i for i in self if i.typ == typ] else False

    def count_consumed(self, typ=None):
        return sum([i.consumed for i in self if not typ or i.typ == typ])

    def has_unconsumed(self, typ=None):
        return any([not i.consumed for i in self if not typ or i.typ == typ])

    def get_first_idx(self, typ=None):
        idx = [i for (i, j) in enumerate(self) if not typ or j.typ == typ]
        return idx[0] if idx else -1

    def has_entry(self, typ=None, name=None, val=None, consumed=None):
        return [n for (n,i) in enumerate(self) if (typ is None or i.typ==typ) and (name is None or i.name==name) and
                (val is None or i.val==val) and (consumed is None or i.consumed==consumed)]

    def mark_consumed(self, idx, cons=True):
        if idx<len(self):
            self[idx].consumed=cons
