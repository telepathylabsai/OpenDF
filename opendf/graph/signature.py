"""
Defines the signature of the nodes.
"""

from collections import OrderedDict
from opendf.defs import *

from itertools import chain

from opendf.defs import is_pos

str_base = str, bytes, bytearray
items = 'items'

_RaiseKeyError = object()  # singleton for no-default behavior


class AliasODict(OrderedDict):
    """
    Ordered dictionary with alias.

    An entry in the dict has a "formal" name, but may be referred to using an alias
    e.g. if we define that 'y' is an alias for 'x', then dict['x'] and dict['y'] refer to the same cell.
    """
    __slots__ = ()

    @staticmethod
    def _process_args(mapping=(), **kwargs):
        if hasattr(mapping, items):
            mapping = getattr(mapping, items)()
        return ((k, v) for k, v in chain(mapping, getattr(kwargs, items)()))

    def _process_args_alias(self, mapping=(), **kwargs):
        if hasattr(mapping, items):
            mapping = getattr(mapping, items)()
        return ((self.real_name(k), v) for k, v in chain(mapping, getattr(kwargs, items)()))

    def real_name(self, nm):
        return self.aliases[nm] if nm in self.aliases else nm

    def __init__(self, mapping=(), **kwargs):
        super(AliasODict, self).__init__(self._process_args(mapping, **kwargs))
        self.aliases = {}

    def __getitem__(self, k):
        return super(AliasODict, self).__getitem__(self.real_name(k))

    def __setitem__(self, k, v):
        return super(AliasODict, self).__setitem__(self.real_name(k), v)

    def __delitem__(self, k):
        return super(AliasODict, self).__delitem__(self.real_name(k))

    def get(self, k, default=None):
        return super(AliasODict, self).get(self.real_name(k), default)

    def setdefault(self, k, default=None):
        return super(AliasODict, self).setdefault(self.real_name(k), default)

    def pop(self, k, v=_RaiseKeyError):
        if v is _RaiseKeyError:
            return super(AliasODict, self).pop(self.real_name(k))
        return super(AliasODict, self).pop(self.real_name(k), v)

    def update(self, mapping=(), **kwargs):
        super(AliasODict, self).update(self._process_args_alias(mapping, **kwargs))

    def __contains__(self, k):
        return super(AliasODict, self).__contains__(self.real_name(k))

    def copy(self):
        return type(self)(self)

    @classmethod
    def fromkeys(cls, keys, v=None):
        return super(AliasODict, cls).fromkeys((k for k in keys), v)

    def __repr__(self):
        return '{0}({1})'.format(type(self).__name__, super(AliasODict, self).__repr__())

    def really_has(self, k):
        """
        Checks if dict has `k` as a real name, NOT as an alias name.

        :param k: the name
        :type k: Any
        :return: `True` if `k` is in the dictionary but is not an alias; otherwise, `False`
        :rtype: bool
        """
        return k in self and k not in self.aliases

    def duplicate(self):
        """
        Creates a copy of this dictionary.

        :return: the copy of this dictionary.
        :rtype: "AliasODict"
        """
        d = AliasODict()
        for i in self:
            d[i] = self[i]
        for i in self.aliases:
            d.aliases[i] = self.aliases[i]
        return d


class InputParam:
    """
    Represents entries in the signature of a node. We allow parameter types to be either a single type, or a list of
    types. Auxiliary functions handle extra work caused by this.
    """

    def __init__(self, type, required, ml, e, view, ptags, mm, prop, alias, custom):
        self.type = type  # one type or a list of allowed types
        self.oblig = required
        self.multi = ml  # flag to indicate that a "real" object could have aggregation as input for this param
        #  e.g. an event can have several attendees (multi=True) but only one id (multi=False)
        #   (constraints can always have aggregation)  (not used yet)
        self.excl_match = e or prop  # exclude this input from matching
        self.view = view  # default int/ext usage of this input
        self.prmtags = ptags  # various tags we may want to attach to the parameters - a set of strings - e.g. omit_dup
        # TODO: merge these into the node tags?
        self.match_miss = mm  # flag this param to accept match when value is missing
        # - only when calling match with match_miss=True!
        self.prop = prop  # property - for now just for 'get', not 'set'
        self.alias = alias  # alias for positional argument
        self.custom = custom  # if this parameter should be matched with a special function

    def multi_type(self):
        return isinstance(self.type, list)

    def match_type(self, t):
        return True if t == self.type or isinstance(self.type, list) and t in self.type else False

    # True if ANY of the types in the list match
    def match_types(self, ts):
        if not isinstance(ts, list):
            ts = [ts]
        return any([self.match_type(t) for t in ts])

    def match_tname(self, n):
        if isinstance(self.type, list):
            return n in [t.__name__ for t in self.type]
        else:
            return n == self.type.__name__

    # return a list (possibly empty) of input typenames, which match a given list of typenames
    # works also if self has a single type (not a list)
    # notice - not returning True/False !
    def match_tnames(self, ns):
        """
        Returns a LIST of matching names (not a boolean).
        """
        if not isinstance(ns, list):
            ns = [ns]
        tn = [self.type.__name__] if not isinstance(self.type, list) else [i.__name__ for i in self.type]
        return [i for i in tn if i in ns]

    def type_name(self):
        if isinstance(self.type, list):
            s = ','.join(t.__name__ for t in self.type)
            return s
        else:
            return self.type.__name__

    def get_first_type_name(self):
        return self.type[0].__name__ if isinstance(self.type, list) else self.type.__name__


# TODO: changing this to be AliasODict may make it a bit cleaner
# TODO: do we need to duplicate the signature in copy_info?
class Signature(OrderedDict):
    def __init__(self):
        super().__init__()
        self.aliases = {}  # { alias : real_name }
        self.key_index = {}
        self.multi_res = False  # can the result of this node be multiple objects?
        # True: yes (but not necessarily always), False: never, None: not applicable, or not clear

    def add_sig(self, name, typ,
                oblig=False,  # obligatory parameter - complain if not given
                multi=False,  # (unused) - mark this input as conceptually able to represent multiple objects
                #   e.g. a person has one unique ID, but may have many cars
                excl_match=False,  # exclude this input from matching
                view=VIEW_EXT,
                ptags=None,
                match_miss=False,  # during match, if missing and match got the match_miss flag, then will match
                prop=False,  # is property (not a "real" input) - similar to python's property
                # for now - only for property 'get' - not for property 'set'. (may need additional flag for 'set')
                alias=None,  # alias for positional argument
                custom=None):  # parameter needs custom match function
        ptags = ptags if ptags else []
        if alias:
            if not is_pos(name):  # allow alias only for positional parameters
                alias = None
            else:
                self.aliases[alias] = name
        self.key_index[name] = len(self)
        self[name] = InputParam(typ, oblig, multi, excl_match, view, ptags, match_miss, prop, alias, custom)

    def get_first_type_name(self, name):
        if name == '_aka':
            return 'Str'
        if name == '_out_type':
            return 'Str'
        name = self.real_name(name)
        if name not in self and is_pos(name) and POS in self:
            name = POS
        return self[name].get_first_type_name()

    def allows_prm(self, nm):
        if nm in self or nm in ['_aka', '_out_type']:
            return True
        if is_pos(nm) and POS in self:  # TODO: check if it still used
            return True
        if nm in self.aliases:
            return True
        return False

    # check if a name is an alias
    def is_alias(self, nm):
        return nm in self.aliases

    # check if a name has an alias
    def has_alias(self, nm):
        return nm in list(self.aliases.values())

    # if a name is an alias, return the real name; otherwise, return the input.
    #   does not check that input name is valid
    def real_name(self, nm):
        return self.aliases[nm] if nm in self.aliases else nm

    # special case - when we want to allow unspecified number of positional parameters (all of the same type)
    # we do it by adding just one parameter to the signature, and call it POS (defined with posname())
    def sig_name(self, nm):
        nm = self.real_name(nm)
        if nm not in self and is_pos(nm) and POS in self:
            nm = POS
        return nm

    # return alias if input name has one, else return input name
    def pretty_name(self, nm):
        if nm not in self:
            return nm
        return self[nm].alias if self[nm].alias else nm

    # the following functions are just wrappers for the InputParameter functions, taking care of alias
    def multi_type(self, nm):
        nm = self.sig_name(nm)
        return self[nm].multi_type()

    def match_type(self, nm, t):
        nm = self.sig_name(nm)
        return self[nm].match_type(t)

    def match_types(self, nm, ts):
        nm = self.sig_name(nm)
        return self[nm].match_types(ts)

    def match_tname(self, nm, n):
        nm = self.sig_name(nm)
        return self[nm].match_tname(n)

    def match_tnames(self, nm, ns):
        nm = self.sig_name(nm)
        return self[nm].match_tnames(ns)

    def type_name(self, nm):
        nm = self.sig_name(nm)
        return self[nm].type_name()

    def get_key_index(self, k):
        if k in self.key_index:
            return self.key_index[k]
        return -1

    def set_multi_res(self, val):
        self.multi_res = val

