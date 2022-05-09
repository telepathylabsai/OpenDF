"""
Miscellaneous of useful functions which are used in several places and do not have dependencies.
"""
import datetime

import re
from math import sin, cos, sqrt, atan2, radians


# gets base type and constraint level - assuming no special chars
def get_type_and_clevel(s):
    if not s:
        return s, 0
    if not isinstance(s, str):
        s = str(s)
    clevel = 0
    done = False
    while not done:
        if s[-1] == '?':
            clevel += 1
            s = s[:-1]
        elif len(s) > 8 and s.startswith('Constraint[') and s[-1] == ']':
            clevel += 1
            s = s[len('Constraint['):-1]
        else:
            done = True
    return s, clevel


# todo - define new syntax for special features
# def get_val_parse(t):
#     s, v = sep_feats(t)
#     nfeats = {}
#     if '!' in v:
#         nfeats['evalres'] = not '-!' in v
#     if '&' in v:
#         nfeats['mut'] = not '-&' in v
#     if '`' in v:
#         nfeats['hide'] = not '-`' in v
#     if '/' in v:
#         nfeats['detach'] = not '-/' in v
#     if '|' in v:
#         nfeats['block'] = not '-' in v
#     if '+' in v:
#         nfeats['goal'] = VIEW_EXT if '-+' in v else VIEW_INT
#     if '*' in v:
#         nfeats['goal'] = VIEW_INT if '-*' in v else VIEW_EXT
#
#     # 'iview' - This specifies the view mode for consuming an input - the node itself or its result
#     #           (this value gets stored in the parent's view_mode)
#     #           for match, it's the view mode used for match REF
#     if '~' in v:
#         nfeats['iview'] = VIEW_INT if '-~' in v else VIEW_EXT
#     if '@' in v:
#         nfeats['iview'] = VIEW_EXT if '-@' in v else VIEW_INT
#     # 'oview' controls the view mode used for match OBJ - match the obj node or its result
#     if '>' in v:
#         nfeats['oview'] = VIEW_INT if '->' in v else VIEW_EXT
#     if '<' in v:
#         nfeats['oview'] = VIEW_EXT if '-<' in v else VIEW_INT
#
#     return s, nfeats


def to_number(val):
    if (len(val)) < 1:
        return None
    sgn = 1
    if val[0] == '-':
        val = val[1:]
        sgn = -1
    if val.isnumeric():  # if val is int
        return sgn * int(val)
    ps = [i for i in val if i == '.']
    if len(ps) > 1:
        return None
    a = [i for i in val if i not in '0123456789.']
    if a:
        return None
    return sgn * float(val)


# for a given node, and a STRING value, return the value cast according to the node type
def cast_str_val(nd, val):
    val = val[1:] if val[0] == '#' else val
    tp = nd.typename()
    num = to_number(val) if tp in ['Int', 'Float', 'Number'] else None

    if num is not None and (tp == 'Int' or tp == 'Number' and isinstance(num, int)):
        return int(num)
    elif tp in ['Float', 'Number'] and num is not None:
        return float(num)
    elif tp == 'Bool' and val.lower() in ['true', 'false', 'yes', 'no']:
        return False if val.lower() in ['false', 'no'] else True
    elif tp in ['Str', 'CasedStr', 'String'] and val[0] == '"' and val[-1] == '"':
        return val[1:-1]
        # return re.sub('_', ' ', val[1:-1])  # remove quotes
    elif tp in ['Str', 'CasedStr', 'String']:
        return val  # no quotes
        # return re.sub('_', ' ', val)  # no quotes
    else:
        return None


# dummy string similarity:
#   if at least half the chars of one string appear in the second string - then consider them similar
def strings_similar(a, b):
    a, b = (a, b) if len(a) < len(b) else (b, a)
    n_sim = len([i for i in a if i in b])
    if n_sim >= max(1, len(a) // 2):
        return True
    return False


def to_list(a):
    return a if isinstance(a, list) else [] if not a else [a]


def flatten_list(a):
    l = []
    for i in a:
        if isinstance(i, list):
            l.extend(flatten_list(i))
        else:
            l.append(i)
    return l


# ################################################################################################

# in general, when performing match, we require ref constraint level to be obj constraint level + 1
# e.g. ref is Event? and obj is Event; or ref is Event?? and obj is Event?
# if ref clevel is 0 - this is not a "typical" case (since ref is not really a constraint!), but we may want to allow
# it. In this case, ref is a simple object, which should match an "equal" object
def compatible_clevel(ref_clevel, obj_clevel):
    return True if ref_clevel == obj_clevel + 1 or (ref_clevel == 0 and obj_clevel == 0) else False


# hint is a string, with the following 2 possible formats:
# 1. prog=...  - this is a program (Sexp string)
# 2. tp[?+][:opt]*[:#nd]
# :conv - allows to specify mapping for NLU entity VALUES. e.g. ":conv=accept/True,reject/False"
#         '*/*' means copy NLU entity name.  '*/xxx' means use xxx for 'other values'
# opts:
#   :tname - input name to map entity name into
#   :nmode - new/extend/;xxx/...
#   :omode - hasParam/role/...
#   :otype - specify type of node to revise (avoid revising wrong type)
def parse_hint(h):
    if h.startswith('prog='):
        return None, 0, [], h[5:]
    s = h.split(':')
    opts = {i.split('=')[0]: i.split('=')[1] if len(i.split('=')) > 1 else '' for i in to_list(s[1:])}
    if 'conv' in opts:
        opts['conv'] = {c.split('/')[0]: c.split('/')[1] for c in opts['conv'].split(',')}
    tp = re.sub('\?', '', s[0])
    cl = len(s[0]) - len(tp)
    return tp, cl, opts, None


# make sexp reference to the given node, possibly add suffix and prefix. Return '' if n not a registered node
# convenience function (is this the right place?)
# TODO: move this to Node!
def id_sexp(n, pref=None, suf=None):
    if not n or n.id is None:
        return ''
    s = '$#%d' % n.id
    s = pref + s if pref else s
    s = s + suf if suf else s
    return s


def comma_id_sexp(ns):
    return ','.join([id_sexp(i) for i in to_list(ns)])


def get_subclasses(cls):
    for subclass in cls.__subclasses__():
        yield from get_subclasses(subclass)
        yield subclass


def add_element(lst, e):
    if not e:
        return lst
    if not lst:
        return [e]
    return list(set(lst + [e]))


def remove_element(lst, e):
    if not lst or not e:
        return lst
    l = to_list(lst)
    return list(set([i for i in l if i != e]))


def is_assign_name(s):
    if not s or s[0] != 'x' or len(s) < 2 or not s[1:].isnumeric():
        return False
    return True


# Earth radius in meters
R = 6371000.0


def geo_distance(lat1, long1, lat2, long2):
    """
    Computes the distance between to pairs of coordinates (in decimal degrees), on earth.

    It assumes the earth is a perfect sphere with radius of 6371000.0 meters.

    :param lat1: the latitude of the first coordinates
    :type lat1: float
    :param long1: the longitude of the first coordinates
    :type long1: float
    :param lat2: the latitude of the second coordinates
    :type lat2: float
    :param long2: the longitude of the second coordinates
    :type long2: float
    :return: the distance between the two coordinate pairs, in meters
    :rtype: int
    """

    lat1 = radians(lat1)
    long1 = radians(long1)
    lat2 = radians(lat2)
    long2 = radians(long2)

    lat_distance = lat2 - lat1
    long_distance = long2 - long1

    a = sin(lat_distance / 2) ** 2 + cos(lat1) * cos(lat2) * sin(long_distance / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))

    return R * c


def str_to_datetime(st):
    s = [int(i) for i in st.split('/')]
    return datetime.datetime(s[0], s[1], s[2], s[3], s[4])
