"""
Operator node types.

We can think of operators as decorators of nodes. These types represent logical operations and aggregations, and are
not "real" objects or functions. Unlike objects, they don't have a fixed out type. Unlike functions, they do NOT
create a result.

Their main usages are:
    1. hold aggregations (SET);
    2. describing "complex" constraint operations, and checking the match of these operations.
"""

from sqlalchemy import or_, select, not_, and_
from sqlalchemy.sql import Join
from opendf.defs import VIEW, POS, is_pos, posname, Message
from opendf.exceptions.df_exception import InvalidNumberOfInputsException, NotImplementedYetDFException, \
    InvalidResultException
from opendf.utils.utils import flatten_list
from opendf.graph.nodes.framework_objects import Bool, Str
from opendf.graph.nodes.node import Node


# ################################################################################################
# ################################################################################################

# TODO: add operators corresponding to AlwaysTrueConstraint / AlwaysFalseConstraint
#  - e.g EMPTY, CLEAR, TRUE, FALSE
#     - different meaning for clear (erase in modifier) vs. empty (insist object does not have field)


class Operator(Node):
    def __init__(self, outtyp=None):
        super().__init__(outtyp)
        self.copy_in_type = posname(1)


# Aggregators: AND, OR, SET, ...
class Aggregator(Operator):
    def __init__(self, outtyp=None):
        super().__init__(outtyp)


# Qualifiers: EQ, NEQ, GT, LT, ...
class Qualifier(Operator):

    def __init__(self, outtyp=None):
        super().__init__(outtyp)

    def __call__(self, *args):
        """
        Apply the qualifier to the arguments.

        :param args: the list of arguments
        :type args: List
        :return: the result of the qualifier
        :rtype: Any
        """
        return None

    def generate_sql_where(self, selection, parent_id, **kwargs):
        kwargs["qualifier"] = self
        return self.input_view(posname(1)).generate_sql_where(selection, parent_id, **kwargs)


# Modifier - base type (derived from Operator)
# TODO: maybe a modifier should not be an operator after all << clarify
class Modifier(Node):
    """
    Modifier nodes specify/apply a modification to be applied to an object. Modifiers typically operate on specific
    types, and are defined in the same module. A modifier has its own (optional) parameters (non-positional),
    as well a positional input, which is of the type this modifier operated on.
    """

    def __init__(self, outtyp=None):
        super().__init__(outtyp)

    # Actually - just use the base match - until we clear the difference between modifier and operator...
    # match for Modifiers 0 - base function
    # Two simple cases:
    #   - stop match and return True - e.g. postpone_start(15_minutes) - no point trying to match
    #   - simple pass through - e.g. add_person(John)  - maybe there is a point matching (need use case...)
    # setting the second as default
    def match(self, obj, iview=VIEW.INT, oview=None, check_level=False, match_miss=False):
        # inp = self.input_view(posname(1))
        inp = self.res
        # if inp:
        return inp.match(obj, check_level=check_level, match_miss=match_miss)
        # return super(Node, self).match(obj, iview, oview, check_level, match_miss)


# ################################################################################################


def selection_has_table(selection, table):
    """
    Checks if the table is already in the selection.

    :param selection: the selection
    :type selection: Any
    :param table: the table
    :type table: Any
    :return: `True`, if the table is already in the selection; otherwise, `False`
    :rtype: bool
    """
    for _table in selection.froms:
        if isinstance(_table, Join):
            if _table.left == table:
                return True
            if _table.right == table:
                return True
        if _table == table:
            return True

    return False


def join_if_needed(table, selection):
    """
    Joins `table` into `selection` if it is not already there.

    :param table: the table
    :type table: Any
    :param selection: the selection
    :type selection: Any
    :return: the joined selection
    :rtype: Any
    """
    if len(selection.froms) == 0:
        return selection.select_from(table)
    if not selection_has_table(selection, table):
        return selection.join(table)
    return selection


def aggregate_selections(inputs, selection, parent_id, kwargs):
    conditions = []
    for _, value in inputs.items():
        child_selection = value.generate_sql_where(select(), parent_id, **kwargs)
        for column in child_selection.selected_columns:
            selection = join_if_needed(column.table, selection)
            selection = selection.add_columns(column)
        where_clause = child_selection.whereclause
        if where_clause is not None:
            conditions.append(where_clause)
    return conditions, selection


class AND(Aggregator):
    def __init__(self):
        super().__init__()  # Dynamic output type

    def valid_input(self):
        inputs = self.num_pos_inputs()
        if inputs == 0:
            raise InvalidNumberOfInputsException.make_exc(self, 'at least one', inputs)

    def match(self, obj, iview=VIEW.INT, oview=None, check_level=False, match_miss=False):
        if self.constr_obj_view == VIEW.EXT:  # TODO: verify, and then copy for all other operators!
            obj = obj.res
        for nm in self.inputs:
            inp = self.input_view(nm)
            if not inp.match(obj, check_level=check_level, match_miss=match_miss):
                return False
        return True

    def generate_sql_where(self, selection, parent_id, **kwargs):
        conditions, selection = aggregate_selections(self.inputs, selection, parent_id, kwargs)
        if len(conditions) == 1:
            return selection.where(conditions[0])
        return selection.where(and_(*conditions).self_group())


class OR(Aggregator):
    def __init__(self):
        super().__init__()  # Dynamic output type

    def valid_input(self):
        inputs = self.num_pos_inputs()
        if inputs == 0:
            raise InvalidNumberOfInputsException.make_exc(self, "at least one", inputs)

    def match(self, obj, iview=VIEW.INT, oview=None, check_level=False, match_miss=False):
        for nm in self.inputs:
            inp = self.input_view(nm)
            if inp.match(obj, check_level=check_level, match_miss=match_miss):
                return True
        return False

    def generate_sql_where(self, selection, parent_id, **kwargs):
        conditions, selection = aggregate_selections(self.inputs, selection, parent_id, kwargs)
        if len(conditions) == 1:
            return selection.where(conditions[0])
        return selection.where(or_(*conditions).self_group())


# do we want an XOR?  e.g.   X AND (A OR B)  (allows {X,A}, {X,B}, {X,A,B}) vs. X AND (A XOR B) (allows {X,A}, {X,B})
#  e.g. in the case of looking for an event with attendees


class NOT(Aggregator):
    def __init__(self):
        super().__init__()  # Dynamic output type

    def valid_input(self):
        inputs = self.num_pos_inputs()
        if inputs != 1:
            raise InvalidNumberOfInputsException.make_exc(self, 1, inputs)

    def match(self, obj, iview=VIEW.INT, oview=None, check_level=False, match_miss=False):
        nm = list(self.inputs.keys())[0]
        inp = self.input_view(nm)
        return not inp.match(obj, check_level=check_level, match_miss=match_miss)

    def generate_sql_where(self, selection, parent_id, **kwargs):
        subquery = self.input_view(posname(1)).generate_sql_where(select(), parent_id, **kwargs)
        for column in subquery.selected_columns:
            selection = join_if_needed(column.table, selection)
            selection = selection.add_columns(column)
        condition = subquery.whereclause
        return selection.where(not_(condition))


class ANY(Aggregator):
    """
    `ANY` is a wrapper which handles `SET` as input (but works also on real objects). It is `True` if at least one ref
    (collected from `SET` tree rooted at self) matches at least one object.
    """

    def __init__(self):
        super().__init__()  # Dynamic output type

    def valid_input(self):
        inputs = self.num_pos_inputs()
        if inputs != 1:
            raise InvalidNumberOfInputsException.make_exc(self, 'at least one', inputs)

    def match(self, obj, iview=VIEW.INT, oview=None, check_level=False, match_miss=False):
        nm = posname(1)
        inp = self.input_view(nm)
        refs = inp.unroll_set_objects([])
        objs = obj.unroll_set_objects([])
        for r in refs:
            for o in objs:
                if r.match(o, match_miss=match_miss):
                    return True
        return False

    def generate_sql_where(self, selection, parent_id, **kwargs):
        conditions, selection = aggregate_selections(self.inputs, selection, parent_id, kwargs)
        if len(conditions) == 1:
            return selection.where(conditions[0])
        return selection.where(or_(*conditions).self_group())


class NONE(Aggregator):
    """
    `NONE` is a wrapper which handles `SET` as input (but works also on real objects). It is `True` if none of the ref
    (collected from `SET` tree rooted at self) matches any object (negative of `ANY`).
    """

    def __init__(self):
        super().__init__()  # Dynamic output type

    def valid_input(self):
        inputs = self.num_pos_inputs()
        if inputs != 1:
            raise InvalidNumberOfInputsException.make_exc(self, 1, inputs)

    def generate_sql_where(self, selection, parent_id, **kwargs):
        conditions, selection = aggregate_selections(self.input_view(posname(1)).inputs, selection, parent_id, kwargs)

        return selection.where(not_(or_(*conditions).self_group()))

    def match(self, obj, iview=VIEW.INT, oview=None, check_level=False, match_miss=False):
        nm = posname(1)
        inp = self.input_view(nm)
        refs = inp.unroll_set_objects([])
        objs = obj.unroll_set_objects([])
        for r in refs:
            for o in objs:
                if r.match(o, match_miss=match_miss):
                    return False
        return True


class ALL(Aggregator):
    """
    `ALL` is a wrapper which handles `SET` as input (but works also on real objects). `True` if all ref
    (collected from `SET` tree rooted at self) matches at least one object.
    """

    def __init__(self):
        super().__init__()  # Dynamic output type

    def valid_input(self):
        inputs = self.num_pos_inputs()
        if inputs != 1:
            raise InvalidNumberOfInputsException.make_exc(self, 1, inputs)

    def match(self, obj, iview=VIEW.INT, oview=None, check_level=False, match_miss=False):
        nm = posname(1)
        inp = self.input_view(nm)
        refs = inp.unroll_set_objects([])
        objs = obj.unroll_set_objects([])
        for r in refs:
            found = False
            for o in objs:
                if not found and r.match(o, match_miss=match_miss):
                    found = True
            if not found:
                return False
        return True

    def generate_sql_where(self, selection, parent_id, **kwargs):
        conditions, selection = aggregate_selections(self.inputs, selection, parent_id, kwargs)
        if len(conditions) == 1:
            return selection.where(conditions[0])
        return selection.where(and_(*conditions).self_group())


# EXACT - a little different from other operators - currently it operates on subfields of a constraint
#  e.g. find event with attendees being exactly  X, Y
# (should this be a separate operator - EXACTSUB, and have a separete EXACT which matches SETs ?
class EXACT(Aggregator):
    """
    `EXACT` is an operator EXACT() which checks if sets match exactly
    """

    def __init__(self):
        super().__init__()  # Dynamic output type
        # self.signature.add_sig('subField', Bool)  # set to true if inputs are separate constraints about subfields

    def valid_input(self):
        inputs = self.num_pos_inputs()
        if inputs == 0:
            raise InvalidNumberOfInputsException.make_exc(self, 'at least one', inputs)

    def match(self, obj, iview=VIEW.INT, oview=None, check_level=False, match_miss=False):
        # if self.inp_equals('subField', True):
        inps = [self.input_view(i) for i in self.inputs if is_pos(i)]
        if len(list(set([(i.typename(), i.constraint_level) for i in inps]))) != 1:
            raise InvalidResultException('EXACT expects inputs of one kind only %s' % self, self)
        if len(list(set(flatten_list([i.get_subfields_with_level(1) for i in inps])))) != 1:
            raise InvalidResultException('EXACT expects all inputs to have the same subfields %s' % self, self)
        tp, fld = inps[0].typename(), inps[0].get_subfields_with_level(1)[0]
        # assuming that the inputs really correspond to different objects! (not trivial)
        if obj.typename() != tp:
            return False  # todo - may need following view ...
            # raise Exception('EXACT expects ref object to be of same type %s/%s' % (self, obj), self)
        for i in inps:
            if not i.match(obj, match_miss=match_miss):
                return False
        if len(inps) != inps[0].get_plurality(fld, obj.input_view(fld)):
            return False
        return True

    def generate_sql_where(self, selection, parent_id, **kwargs):
        conditions, selection = aggregate_selections(self.inputs, selection, parent_id, kwargs)
        kwargs['aggregator'] = 'EXACT'
        count_selection = self.input_view(posname(1)).generate_sql_where(select(), parent_id, **kwargs)
        conditions.append(count_selection == len(self.inputs))
        if len(conditions) == 1:
            return selection.where(conditions[0])
        return selection.where(and_(*conditions).self_group())


# ALT (bad name) is not a "normal" operator - it's NOT used in constraints
# it is used as an OR on execution - overrides exceptions if the execution of any of its inputs suceeded
# use with care, until this becomes clearer!
# do we really want to discard all exceptions if one branch is ok? (what about warnings...?)
class ALT(Aggregator):
    def __init__(self):
        super().__init__()  # Dynamic output type
        self.ex = None  # temp store exceptions of children

    def valid_input(self):
        inputs = self.num_pos_inputs()
        if inputs == 0:
            raise InvalidNumberOfInputsException.make_exc(self, "at least one", inputs)

    def allows_exception(self, e):
        for i in self.inputs:
            if self.inputs[i].evaluated:
                self.set_result(self.inputs[i])
                self.evaluated = True
                return True, None
        return False, e


class LT(Qualifier):
    def __init__(self):
        super().__init__()  # Dynamic output type

    def valid_input(self):
        inputs = self.num_pos_inputs()
        if inputs != 1:
            raise InvalidNumberOfInputsException.make_exc(self, 1, inputs)

    def match(self, obj, iview=VIEW.INT, oview=None, check_level=False, match_miss=False):
        inp = self.input_view(posname(1))
        return inp.func_LT(obj)  # compare obj to arg of (LT)

    def __call__(self, *args, **kwargs):
        return args[0] < args[1]


class GT(Qualifier):
    def __init__(self):
        super().__init__()  # Dynamic output type
        self.copy_in_type = posname(1)

    def __call__(self, *args, **kwargs):
        return args[0] > args[1]

    def valid_input(self):
        inputs = self.num_pos_inputs()
        if inputs != 1:
            raise InvalidNumberOfInputsException.make_exc(self, 1, inputs)

    def match(self, obj, iview=VIEW.INT, oview=None, check_level=False, match_miss=False):
        inp = self.input_view(posname(1))
        return inp.func_GT(obj)  # compare obj to arg of (GT)


class GE(Qualifier):
    def __init__(self):
        super().__init__()  # Dynamic output type

    def __call__(self, *args, **kwargs):
        return args[0] >= args[1]

    def valid_input(self):
        inputs = self.num_pos_inputs()
        if inputs != 1:
            raise InvalidNumberOfInputsException.make_exc(self, 1, inputs)

    def match(self, obj, iview=VIEW.INT, oview=None, check_level=False, match_miss=False):
        inp = self.input_view(posname(1))
        return inp.func_GE(obj)  # compare obj to arg of (GE)


class LE(Qualifier):
    def __init__(self):
        super().__init__()  # Dynamic output type

    def __call__(self, *args, **kwargs):
        return args[0] <= args[1]

    def valid_input(self):
        inputs = self.num_pos_inputs()
        if inputs != 1:
            raise InvalidNumberOfInputsException.make_exc(self, 1, inputs)

    def match(self, obj, iview=VIEW.INT, oview=None, check_level=False, match_miss=False):
        inp = self.input_view(posname(1))
        return inp.func_LE(obj)  # compare obj to arg of (LE)


class FN(Qualifier):

    def __init__(self):
        super().__init__()  # Dynamic output type
        self.signature.add_sig('farg', Node, True)  # empty object or any extra arguments to the function
        self.signature.add_sig('fname', Str)  # name of function to call (to be handled by the specific type)

    def __call__(self, *args, **kwargs):
        return None

    def match(self, obj, iview=VIEW.INT, oview=None, check_level=False, match_miss=False):
        fname = self.get_dat('fname')
        farg = self.input_view('farg')
        return farg.func_FN(obj, fname=fname, farg=farg)


class EQ(Qualifier):
    def __init__(self):
        super().__init__()  # Dynamic output type

    def __call__(self, *args, **kwargs):
        return args[0] == args[1]

    def valid_input(self):
        inputs = self.num_pos_inputs()
        if inputs == 0:
            raise InvalidNumberOfInputsException.make_exc(self, 1, inputs)

    def match(self, obj, iview=VIEW.INT, oview=None, check_level=False, match_miss=False):
        inp = self.input_view(posname(1))
        return inp.func_EQ(obj)  # compare obj to arg of (EQ)


class NEQ(Qualifier):
    def __init__(self):
        super().__init__()  # Dynamic output type

    def __call__(self, *args, **kwargs):
        return args[0] != args[1]

    def valid_input(self):
        inputs = self.num_pos_inputs()
        if inputs != 1:
            raise InvalidNumberOfInputsException.make_exc(self, 1, inputs)

    def match(self, obj, iview=VIEW.INT, oview=None, check_level=False, match_miss=False):
        inp = self.input_view(posname(1))
        return inp.func_NEQ(obj)  # compare obj to arg of (NEQ)


class LIKE(Qualifier):

    def __init__(self):
        super().__init__()  # Dynamic output type

    def __call__(self, *args, **kwargs):
        return args[0].like(f"%{args[1]}%")

    def valid_input(self):
        inputs = self.num_pos_inputs()
        if inputs != 1:
            raise InvalidNumberOfInputsException.make_exc(self, 1, inputs)

    def match(self, obj, iview=VIEW.INT, oview=None, check_level=False, match_miss=False):
        inp = self.input_view(posname(1))
        return inp.func_LIKE(obj)  # compare obj to arg of (LIKE)
        # e.g. ...name=LIKE(PersonName(john))  -> at match time we'll use PersonName(john).func_LIKE(ref)


class TRUE(Qualifier):

    def __init__(self):
        super().__init__()  # Dynamic output type

    def __call__(self, *args, **kwargs):
        return True

    def valid_input(self):
        inputs = self.num_pos_inputs()
        if inputs != 1:
            raise InvalidNumberOfInputsException.make_exc(self, 1, inputs)

    def match(self, obj, iview=VIEW.INT, oview=None, check_level=False, match_miss=False):
        return True


# corresponds to AlwaysFalseConstraint - but only for the case of clearing a field
class FALSE(Qualifier):

    def __init__(self):
        super().__init__()  # Dynamic output type

    def __call__(self, *args, **kwargs):
        return False

    def valid_input(self):
        inputs = self.num_pos_inputs()
        if inputs != 1:
            raise InvalidNumberOfInputsException.make_exc(self, 1, inputs)

    def match(self, obj, iview=VIEW.INT, oview=None, check_level=False, match_miss=False):
        return False


class MIN(Aggregator):
    def __init__(self):
        super().__init__()  # Dynamic output type

    def valid_input(self):
        inputs = self.num_pos_inputs()
        if inputs == 0:
            raise InvalidNumberOfInputsException.make_exc(self, 'at least one', inputs)
        raise NotImplementedYetDFException('MIN not implemented yet', self)  # TODO: need to think if/how to use this


class MAX(Aggregator):
    def __init__(self):
        super().__init__()  # Dynamic output type

    def valid_input(self):
        inputs = self.num_pos_inputs()
        if inputs == 0:
            raise InvalidNumberOfInputsException.make_exc(self, 'at least one', inputs)
        raise NotImplementedYetDFException('MAX not implemented yet', self)  # TODO: need to think if/how to use this


class LAST(Aggregator):
    def __init__(self):
        super().__init__()  # Dynamic output type

    def valid_input(self):
        inputs = self.num_pos_inputs()
        if inputs == 0:
            raise InvalidNumberOfInputsException.make_exc(self, "at least one", inputs)
        raise NotImplementedYetDFException('LAST not implemented yet', self)  # TODO: need to think if/how to use this


class SET(Aggregator):
    """
    Basic way to hold multiple objects. For logical match operations applied to `SET`s - add ANY/ALL, to explicitly
    specify how to match on sets.
    """

    def __init__(self):
        super().__init__()  # Dynamic output type

    def valid_input(self):
        inputs = self.num_pos_inputs()
        if inputs == 0:
            raise InvalidNumberOfInputsException.make_exc(self, "at least one", inputs)

    # for now - treat SET in reference constraint like an AND
    def match(self, obj, iview=VIEW.INT, oview=None, check_level=False, match_miss=False):
        for nm in self.inputs:
            inp = self.input_view(nm)
            if not inp.match(obj, check_level=check_level, match_miss=match_miss):
                return False
        return True

    def describe(self, params=None):
        values, objs = [], []
        for i in range(1, self.num_pos_inputs() + 1):
            m = self.input_view(posname(i)).describe(params=params)
            values.append(m.text)
            objs += m.objects
        return Message(f"{{{' NL '.join(values)}}}", objects=objs)


# #################################################################################################################
# special operators - wrapper nodes, which are mostly transparent to the calculation, but have special uses

# TEE is used when we do graph transformations (e.g. wrapping)
#   currently it has a 'name' parameter (which is added to assignments),
#     but that could be taken care of also with let() / {assign}
# we could equally use '{x1}TEE(#Jane)' /  'TEE(name=x1, #Jane)',
# we could rename it to LET (like MS), but conceptually emphasizes the assignment, not the "place holding" function
# computation-wise it's a pass-through - its result just points to its input
# it is used when we expect the input to be:
#   1. used in multiple calculation paths
#   2. transformed (e.g. wrapped)
# it insures that the TRANSFORMED input will be shared between the calculations
# transformation without TEE:
# a--->b--->c--->d                           a--->b--->A--->B--->c--->d
#      |                      transform b         |
#      ---->e--->f                                ---->e--->f
# transformation with TEE:
# a--->b--->TEE--->c--->d                    a--->b--->A--->B--->TEE--->c--->d
#            |                transform b                         |
#            ----->e--->f                                         ----->e--->f
# Note - if 'name' is given as input, we DELETE it after evaluation (in exec) -
# we don't want to re-assign this name to a new node on duplicate. In any case, we use the name only in the initial
# construct using the name later, after revise - not clear what we want/mean - the original / new...
#  hack - if name starts with '.' then don't remove - so we can refer to the LATEST version of TEE in later sexps
class TEE(Aggregator):
    """
    Keeps a place in the graph, which is resilient against graph transformations.
    """

    def __init__(self):
        super().__init__()  # Dynamic output type
        self.signature.add_sig('name', Str, True)
        self.signature.add_sig(posname(1), Node, True)
        self.copy_in_type = posname(1)

    def valid_input(self):
        inputs = self.num_pos_inputs()
        if inputs != 1:
            raise InvalidNumberOfInputsException.make_exc(self, 1, inputs)

    def match(self, obj, iview=VIEW.INT, oview=None, check_level=False, match_miss=False):
        inp = self.input_view(posname(1))
        return inp.match(obj, check_level=check_level, match_miss=match_miss)

    def exec(self, all_nodes=None, goals=None):
        inp = self.inputs[posname(1)]
        self.result = inp

        name = self.get_dat('name')
        if name:
            self.context.add_assign(name, self)
            if name[0] != '.':
                self.del_input('name')


# MODE is currently unused, but could be used to insert as a flag/tag/marker into the graph
# in node.py, the function get_pos_neg_mode_objs collects these flags
# during 'match' - it's simply a pass through
class MODE(Modifier):
    def __init__(self):
        super().__init__()  # Dynamic output type
        self.signature.add_sig('mode', Str, True)
        self.signature.add_sig(posname(1), Node, True)

    def valid_input(self):
        inputs = self.num_pos_inputs()
        if inputs != 1:
            raise InvalidNumberOfInputsException.make_exc(self, 1, inputs)


class BLOCK(Operator):
    """
    Used to block tree traversal when looking for objects.
    """

    def __init__(self):
        super().__init__()  # Dynamic output type
        self.signature.add_sig(posname(1), Node, True)

    def valid_input(self):
        inputs = self.num_pos_inputs()
        if inputs != 1:
            raise InvalidNumberOfInputsException.make_exc(self, 1, inputs)


# #################################################################################################################
# To avoid confusion, we have a separate set of functions for boolean inputs (as opposed to constraint conditions)
# GTf, LEf,... - these are considered "normal" function nodes, and not operators
# The functions below (ANDf, ORf, LTf,....) are "normal" functions (not operators), which perform logical operations


class ANDf(Node):
    def __init__(self):
        super().__init__(Bool)  # Dynamic output type
        self.signature.add_sig(POS, Bool)

    def valid_input(self):
        inputs = self.num_pos_inputs()
        if inputs < 1:
            raise InvalidNumberOfInputsException.make_exc(self, 'at least one', inputs)

    def exec(self, all_nodes=None, goals=None):
        r = True
        for i in self.inputs:
            if is_pos(i):
                if not self.inp_equals(i, True):
                    r = False
                    break
        d, e = self.call_construct_eval(f"Bool({r})", self.context)
        self.set_result(d)


class ORf(Node):
    def __init__(self):
        super().__init__(Bool)  # Dynamic output type
        self.signature.add_sig(POS, Bool)

    def valid_input(self):
        inputs = self.num_pos_inputs()
        if inputs < 1:
            raise InvalidNumberOfInputsException.make_exc(self, 'at least one', inputs)

    def exec(self, all_nodes=None, goals=None):
        r = 'False'
        for i in self.inputs:
            if is_pos(i):
                if self.inp_equals(i, True):
                    r = 'True'
                    break
        d, e = self.call_construct_eval('Bool(%s)' % r, self.context)
        self.set_result(d)


class NOTf(Node):
    def __init__(self):
        super().__init__(Bool)  # Dynamic output type
        self.signature.add_sig(posname(1), Bool, True)

    def valid_input(self):
        inputs = self.num_pos_inputs()
        if inputs != 1:
            raise InvalidNumberOfInputsException.make_exc(self, 1, inputs)

    def exec(self, all_nodes=None, goals=None):
        r = not self.get_dat(posname(1))
        d, e = self.call_construct_eval('Bool(%s)' % str(r), self.context)
        self.set_result(d)


class Qualifierf(Node):

    def yield_msg(self, params=None):
        message = 'Yes.' if self.res.dat else 'No.'
        obj = []
        for value in self.inputs.values():
            if value.data is None:
                message += ' '
                m = value.yield_msg(params)
                message += m.text
                obj += m.objects
        return Message(message, objects=obj)


class LTf(Qualifierf):
    def __init__(self):
        super().__init__(Bool)  # Dynamic output type
        self.signature.add_sig(posname(1), Node, True)
        self.signature.add_sig(posname(2), Node, True)

    def valid_input(self):
        inputs = self.num_pos_inputs()
        if inputs != 2:
            raise InvalidNumberOfInputsException.make_exc(self, 2, inputs)

    def exec(self, all_nodes=None, goals=None):
        n1, n2 = self.input_view(posname(1)), self.input_view(posname(2))
        r = n2.func_LT(n1)
        d, e = self.call_construct_eval('Bool(%s)' % str(r), self.context)
        self.set_result(d)


class GTf(Qualifierf):
    def __init__(self):
        super().__init__(Bool)  # Dynamic output type
        self.signature.add_sig(posname(1), Node, True)
        self.signature.add_sig(posname(2), Node, True)

    def valid_input(self):
        inputs = self.num_pos_inputs()
        if inputs != 2:
            raise InvalidNumberOfInputsException.make_exc(self, 2, inputs)

    def exec(self, all_nodes=None, goals=None):
        n1, n2 = self.input_view(posname(1)), self.input_view(posname(2))
        r = n2.func_GT(n1)
        d, e = self.call_construct_eval('Bool(%s)' % str(r), self.context)
        self.set_result(d)


class GEf(Qualifierf):
    def __init__(self):
        super().__init__(Bool)  # Dynamic output type
        self.signature.add_sig(posname(1), Node, True)
        self.signature.add_sig(posname(2), Node, True)

    def valid_input(self):
        inputs = self.num_pos_inputs()
        if inputs != 2:
            raise InvalidNumberOfInputsException.make_exc(self, 2, inputs)

    def exec(self, all_nodes=None, goals=None):
        n1, n2 = self.input_view(posname(1)), self.input_view(posname(2))
        r = n2.func_GE(n1)
        d, e = self.call_construct_eval('Bool(%s)' % str(r), self.context)
        self.set_result(d)


class LEf(Qualifierf):
    def __init__(self):
        super().__init__(Bool)  # Dynamic output type
        self.signature.add_sig(posname(1), Node, True)
        self.signature.add_sig(posname(2), Node, True)

    def valid_input(self):
        inputs = self.num_pos_inputs()
        if inputs != 2:
            raise InvalidNumberOfInputsException.make_exc(self, 2, inputs)

    def exec(self, all_nodes=None, goals=None):
        n1, n2 = self.input_view(posname(1)), self.input_view(posname(2))
        r = n2.func_LE(n1)
        d, e = self.call_construct_eval('Bool(%s)' % str(r), self.context)
        self.set_result(d)


class EQf(Qualifierf):
    def __init__(self):
        super().__init__(Bool)  # Dynamic output type
        self.signature.add_sig(posname(1), Node, True)
        self.signature.add_sig(posname(2), Node, True)

    def valid_input(self):
        inputs = self.num_pos_inputs()
        if inputs != 2:
            raise InvalidNumberOfInputsException.make_exc(self, 2, inputs)

    def exec(self, all_nodes=None, goals=None):
        n1, n2 = self.input_view(posname(1)), self.input_view(posname(2))
        r = n2.func_EQ(n1)
        d, e = self.call_construct_eval('Bool(%s)' % str(r), self.context)
        self.set_result(d)


class NEQf(Qualifierf):
    def __init__(self):
        super().__init__(Bool)  # Dynamic output type
        self.signature.add_sig(posname(1), Node, True)
        self.signature.add_sig(posname(2), Node, True)

    def valid_input(self):
        inputs = self.num_pos_inputs()
        if inputs != 2:
            raise InvalidNumberOfInputsException.make_exc(self, 2, inputs)

    def exec(self, all_nodes=None, goals=None):
        n1, n2 = self.input_view(posname(1)), self.input_view(posname(2))
        r = n2.func_NEQ(n1)
        d, e = self.call_construct_eval('Bool(%s)' % str(r), self.context)
        self.set_result(d)


class LIKEf(Node):
    def __init__(self):
        super().__init__(Bool)  # Dynamic output type
        self.signature.add_sig(posname(1), Node, True)
        self.signature.add_sig(posname(2), Node, True)

    def valid_input(self):
        inputs = self.num_pos_inputs()
        if inputs != 2:
            raise InvalidNumberOfInputsException.make_exc(self, 2, inputs)

    def exec(self, all_nodes=None, goals=None):
        n1, n2 = self.input_view(posname(1)), self.input_view(posname(2))
        r = n2.func_LIKE(n1)
        d, e = self.call_construct_eval('Bool(%s)' % str(r), self.context)
        self.set_result(d)
