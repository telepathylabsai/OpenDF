"""
Nodes from MultiWOZ 2.2 application.
"""
import random
import re

from sqlalchemy import select, or_

from opendf.applications.core.nodes.time_nodes import Time
from opendf.applications.multiwoz_2_2.domain import MultiWOZDB, MultiWOZContext
from opendf.exceptions.df_exception import AskMoreInputException, MissingValueException
from opendf.exceptions import re_raise_exc
from opendf.applications.multiwoz_2_2.multiwoz_db import MultiWozSqlDB
from opendf.applications.multiwoz_2_2.utils import edit_distance, select_value
from opendf.defs import posname, POS, is_pos, EnvironmentDefinition, SUGG_IMPL_AGR, \
    use_database, DB_NODE_TAG, NODE_COLOR_DB, Message, VIEW
from opendf.exceptions.df_exception import InvalidInputException, \
    ElementNotFoundException, OracleException, MultipleEntriesSingletonException
from opendf.graph.node_factory import NodeFactory
from opendf.graph.nodes.framework_operators import LIKE, EQ, LE, GE
from opendf.graph.nodes.framework_objects import Str, Float, Bool
from opendf.graph.nodes.node import Node, get_diff_fields, collect_values
from collections import defaultdict
from opendf.graph.nodes.framework_functions import get_refer_match, auto_reorder_inputs
from opendf.utils.database_utils import get_database_handler
from opendf.utils.utils import id_sexp, and_values_str, to_list, get_type_and_clevel
from datetime import date, datetime, time
from opendf.parser.pexp_parser import escape_string
from opendf.graph.nodes.framework_functions import get_refer_match

if use_database:
    multiwoz_db = MultiWozSqlDB.get_instance()
else:
    multiwoz_db = MultiWOZDB.get_instance()
node_fact = NodeFactory.get_instance()
environment_definitions = EnvironmentDefinition.get_instance()


class Address(Node):  # type
    def __init__(self):
        super().__init__(Address)
        self.signature.add_sig(posname(1), Str)

    def generate_sql_where(self, selection, parent_id, **kwargs):
        if posname(1) in self.inputs:
            selection = self.input_view(posname(1)).generate_sql_where(selection, parent_id, **kwargs)

        return selection


class Area(Node):  # type
    def __init__(self):
        super().__init__(Area)
        self.signature.add_sig(posname(1), Str)

    def generate_sql_where(self, selection, parent_id, **kwargs):
        if posname(1) in self.inputs:
            selection = self.input_view(posname(1)).generate_sql_where(selection, parent_id, **kwargs)

        return selection


class Internet(Node):  # type
    def __init__(self):
        super().__init__(Internet)
        self.signature.add_sig(posname(1), Str)

    def generate_sql_where(self, selection, parent_id, **kwargs):
        if posname(1) in self.inputs:
            selection = self.input_view(posname(1)).generate_sql_where(selection, parent_id, **kwargs)

        return selection


class Parking(Node):  # type
    def __init__(self):
        super().__init__(Parking)
        self.signature.add_sig(posname(1), Str)

    def generate_sql_where(self, selection, parent_id, **kwargs):
        if posname(1) in self.inputs:
            selection = self.input_view(posname(1)).generate_sql_where(selection, parent_id, **kwargs)

        return selection


class Name(Node):  # type
    def __init__(self, typ=None):
        typ = typ if typ else type(self)
        super().__init__(typ)
        self.signature.add_sig(posname(1), Str)

    def func_LIKE(self, ref):
        sl, rf = self.res.inputs[posname(1)].res.dat, ref.res.dat
        if sl is None and rf is None:
            return True
        if sl is None or rf is None:
            return False
        if sl == rf:
            return True
        w1, w2 = 1, 4
        stops = ['the', 'of', 'at', 'and', 'hotel', 'house']
        stoks = re.sub('[-_,&:\.]', ' ', sl).lower().split()  # tokens in query
        rtoks = re.sub('[-_,&:\.]', ' ', rf.lower()).split()  # tokens in candidate object
        ls = sum([w1 if i in stops else w2 for i in stoks])
        lr = sum([w1 if i in stops else w2 for i in rtoks])
        m = 0
        for r in rtoks:
            if r in stoks:
                m += w1 if r in stops else w2
        if m >= lr / 2.0 and m >= ls / 2.0:
            return True
        return False

    @staticmethod
    def extract_names(sl):
        names = re.sub('[-_]', ' ', sl).lower().split()  # all names must be there
        names = [n for n in names if n not in ['the', 'of', 'at', 'hotel', 'house']]
        return names

    def generate_sql_where(self, selection, parent_id, **kwargs):
        qualifier = kwargs.get("qualifier")
        if isinstance(qualifier, LIKE):
            sl = self.res.inputs[posname(1)].res.dat
            if sl is None:
                return selection
            names = self.extract_names(sl)
            if len(names) == 1:
                selection = selection.where(qualifier(parent_id, names[0]))
            elif len(names) > 1:
                exclude = kwargs.get('exclude_words')  # if this is set, do not include these words in the query
                if exclude:
                    names = [i for i in names if i.lower() not in exclude]
                names = list(map(lambda x: qualifier(parent_id, x), names))
                selection = selection.where(or_(*names).self_group())
        elif posname(1) in self.inputs:
            selection = self.input_view(posname(1)).generate_sql_where(selection, parent_id, **kwargs)

        return selection


class Phone(Node):  # type
    def __init__(self):
        super().__init__(Phone)
        self.signature.add_sig(posname(1), Str)

    def generate_sql_where(self, selection, parent_id, **kwargs):
        if posname(1) in self.inputs:
            selection = self.input_view(posname(1)).generate_sql_where(selection, parent_id, **kwargs)

        return selection


class Postcode(Node):  # type
    def __init__(self):
        super().__init__(Postcode)
        self.signature.add_sig(posname(1), Str)

    def generate_sql_where(self, selection, parent_id, **kwargs):
        if posname(1) in self.inputs:
            selection = self.input_view(posname(1)).generate_sql_where(selection, parent_id, **kwargs)

        return selection


class Price(Node):  # type
    def __init__(self):
        super().__init__(Float)
        self.signature.add_sig(posname(1), Float)

    def generate_sql_where(self, selection, parent_id, **kwargs):
        if posname(1) in self.inputs:
            selection = self.input_view(posname(1)).generate_sql_where(selection, parent_id, **kwargs)

        return selection


class Pricerange(Node):  # type
    def __init__(self):
        super().__init__(Pricerange)
        self.signature.add_sig(posname(1), Str)

    def generate_sql_where(self, selection, parent_id, **kwargs):
        if posname(1) in self.inputs:
            selection = self.input_view(posname(1)).generate_sql_where(selection, parent_id, **kwargs)

        return selection


class Stars(Node):  # type
    def __init__(self):
        super().__init__(Stars)
        self.signature.add_sig(posname(1), Str)

    def generate_sql_where(self, selection, parent_id, **kwargs):
        if posname(1) in self.inputs:
            selection = self.input_view(posname(1)).generate_sql_where(selection, parent_id, **kwargs)

        return selection

    def describe(self, params=None):
        return '%s stars' % self.get_dat(posname(1)), []

    def yield_msg(self, params=None):
        return '%s stars' % self.get_dat(posname(1)), []


class Takesbookings(Node):  # type
    def __init__(self):
        super().__init__(Takesbookings)
        self.signature.add_sig(posname(1), Str)

    def generate_sql_where(self, selection, parent_id, **kwargs):
        if posname(1) in self.inputs:
            selection = self.input_view(posname(1)).generate_sql_where(selection, parent_id, **kwargs)

        return selection


class Type(Node):  # type
    def __init__(self):
        super().__init__(Type)
        self.signature.add_sig(posname(1), Str)

    def generate_sql_where(self, selection, parent_id, **kwargs):
        if posname(1) in self.inputs:
            selection = self.input_view(posname(1)).generate_sql_where(selection, parent_id, **kwargs)

        return selection


class Book_stay(Node):  # type
    def __init__(self):
        super().__init__(Book_stay)
        self.signature.add_sig(posname(1), Str)

    def generate_sql_where(self, selection, parent_id, **kwargs):
        if posname(1) in self.inputs:
            selection = self.input_view(posname(1)).generate_sql_where(selection, parent_id, **kwargs)

        return selection


class Book_people(Node):  # type
    def __init__(self):
        super().__init__(Book_people)
        self.signature.add_sig(posname(1), Str)

    def generate_sql_where(self, selection, parent_id, **kwargs):
        if posname(1) in self.inputs:
            selection = self.input_view(posname(1)).generate_sql_where(selection, parent_id, **kwargs)

        return selection


class Book_day(Node):  # type
    def __init__(self):
        super().__init__(Book_day)
        self.signature.add_sig(posname(1), Str)

    def generate_sql_where(self, selection, parent_id, **kwargs):
        if posname(1) in self.inputs:
            selection = self.input_view(posname(1)).generate_sql_where(selection, parent_id, **kwargs)

        return selection


class Book_time(Node):  # type
    def __init__(self):
        super().__init__(Book_time)
        self.signature.add_sig('pos1', Str)

    def generate_sql_where(self, selection, parent_id, **kwargs):
        if posname(1) in self.inputs:
            selection = self.input_view(posname(1)).generate_sql_where(selection, parent_id, **kwargs)

        return selection


database_handler = get_database_handler()
TIME_REGEX = re.compile(r"([0-9]+):([0-9]+)")


class MWOZTime(Node):  # type

    def __init__(self, typ=None):
        typ = typ if typ else type(self)
        super().__init__(typ)
        self.signature.add_sig(posname(1), Str)
        self.qualifier = EQ()

    def exec(self, all_nodes=None, goals=None):
        tm = self.get_dat(posname(1))
        if isinstance(tm, str):
            tm = tm.lower()
            tm = re.sub('after ', '', tm)
            tm = re.sub('at ', '', tm)
            tm = re.sub('[? ]', '', tm)
            if tm in ['lunch', 'noon', 'noontime']:
                tm = '12:00'
        match = TIME_REGEX.fullmatch(tm)
        if not match:
            raise InvalidInputException(f"Expected time in HH:MM format, got: {tm}", self)

    def generate_sql_where(self, selection, parent_id, **kwargs):
        str_time = self.get_dat(posname(1))
        match = TIME_REGEX.fullmatch(str_time)
        if match is None:
            hour, minute = 0, 0  # problem
        else:
            hour, minute = match.groups()
        ptime = time(int(hour) % 24, int(minute) % 60)
        qualifier = kwargs.get("qualifier", self.qualifier)
        return selection.where(qualifier(database_handler.to_database_time(parent_id),
                                         database_handler.to_database_time(ptime)))


class ArriveBy(MWOZTime):
    def __init__(self):
        super().__init__(MWOZTime)
        self.signature.add_sig(posname(1), Str)
        self.qualifier = LE()


class LeaveAt(MWOZTime):
    def __init__(self):
        super().__init__(MWOZTime)
        self.signature.add_sig(posname(1), Str)
        self.qualifier = GE()


class Location(Node):  # type
    def __init__(self):
        super().__init__(Location)
        self.signature.add_sig(posname(1), Str)

    # for equality, use Str's LIKE function - ignoring case. todo - maybe something more fuzzy?
    def func_EQ(self, ref):
        return self.input_view(posname(1)).func_LIKE(ref)

    def generate_sql_where(self, selection, parent_id, **kwargs):
        if posname(1) in self.inputs:
            selection = self.input_view(posname(1)).generate_sql_where(selection, parent_id, **kwargs)

        return selection


class Duration(Node):  # type
    def __init__(self):
        super().__init__(Duration)
        self.signature.add_sig(posname(1), Str)

    def generate_sql_where(self, selection, parent_id, **kwargs):
        if posname(1) in self.inputs:
            selection = self.input_view(posname(1)).generate_sql_where(selection, parent_id, **kwargs)

        return selection


class TrainID(Node):  # type
    def __init__(self):
        super().__init__(TrainID)
        self.signature.add_sig(posname(1), Str)

    def generate_sql_where(self, selection, parent_id, **kwargs):
        if posname(1) in self.inputs:
            selection = self.input_view(posname(1)).generate_sql_where(selection, parent_id, **kwargs)

        return selection


class EntranceFee(Node):  # type
    def __init__(self):
        super().__init__(EntranceFee)
        self.signature.add_sig(posname(1), Str)

    def generate_sql_where(self, selection, parent_id, **kwargs):
        if posname(1) in self.inputs:
            selection = self.input_view(posname(1)).generate_sql_where(selection, parent_id, **kwargs)

        return selection


class OpenHours(Node):  # type
    def __init__(self):
        super().__init__(OpenHours)
        self.signature.add_sig(posname(1), Str)

    def generate_sql_where(self, selection, parent_id, **kwargs):
        if posname(1) in self.inputs:
            selection = self.input_view(posname(1)).generate_sql_where(selection, parent_id, **kwargs)

        return selection


class Department(Name):  # type
    def __init__(self):
        super().__init__(Department)
        self.signature.add_sig(posname(1), Str)

    def func_LIKE(self, ref):
        sl, rf = self.res.inputs[posname(1)].res.dat, ref.res.dat
        if sl is None and rf is None:
            return True
        if sl is None or rf is None:
            return False
        if sl == rf:
            return True
        w1, w2 = 0, 2
        wtypo = 1
        stops = ['the', 'of', 'at', 'and', 'department']
        stoks = re.sub('[-_,&:\.]', ' ', sl).lower().split()  # tokens in query
        rtoks = re.sub('[-_,&:\.]', ' ', rf.lower()).split()  # tokens in candidate object
        ls = sum([w1 if i in stops else w2 for i in stoks])
        lr = sum([w1 if i in stops else w2 for i in rtoks])
        m = 0
        for r in rtoks:
            if r in stoks:
                m += w1 if r in stops else w2
            elif self.typo(r, stoks):
                m += wtypo
        if m >= lr / 2.0 and m >= ls / 2.0:
            return True
        return False

    def typo(self, o, qs):
        for q in qs:
            e = edit_distance(o, q)
            if e <= 2 and min(len(o), len(q)) > e:
                return True
        return False


class Color(Node):  # type
    def __init__(self):
        super().__init__(Color)
        self.signature.add_sig(posname(1), Str)

    def generate_sql_where(self, selection, parent_id, **kwargs):
        if posname(1) in self.inputs:
            selection = self.input_view(posname(1)).generate_sql_where(selection, parent_id, **kwargs)

        return selection


class TaxiType(Node):  # type
    def __init__(self):
        super().__init__(TaxiType)
        self.signature.add_sig(posname(1), Str)

    def generate_sql_where(self, selection, parent_id, **kwargs):
        if posname(1) in self.inputs:
            selection = self.input_view(posname(1)).generate_sql_where(selection, parent_id, **kwargs)

        return selection


class Food(Node):  # type
    def __init__(self):
        super().__init__(Food)
        self.signature.add_sig(posname(1), Str)

    def generate_sql_where(self, selection, parent_id, **kwargs):
        if posname(1) in self.inputs:
            selection = self.input_view(posname(1)).generate_sql_where(selection, parent_id, **kwargs)

        return selection


################################################################################
################################### DOMAINS ####################################
################################################################################

class MultiWOZDomain(Node):

    def __init__(self, out_type=None):
        if out_type is None:
            out_type = MultiWOZDomain
        super(MultiWOZDomain, self).__init__(out_type)

    def get_context_values(self, inform_values=None, req_fields=None):
        return {}


################################################################################################################
############################################## Aux funcs #######################################################


# try to avoid using this!
# there may be several different ones
# this runs without input, and is always the one and only node in its graph
class mwoz_no_op(Node):
    def __init__(self):
        super().__init__()

    def exec(self, all_nodes=None, goals=None):
        ctx = self.context
        if len(ctx.goals) > 1:
            prev = ctx.goals[-2]
            # do we really need to duplicate? or just re-run the same graph?
            # one reason to duplicate so that we re-calc the updated state (for comparison with mwoz annotation)
            # can we do it somewhere else?
            dp = prev.duplicate_tree(prev)[-1]
            dp.call_eval(add_goal=False)


# get differentiating fields in a list of objects
def get_diff_fields(objs, ignore_fields=None):
    fields = defaultdict(set)
    for o in objs:
        for i in o.inputs:
            v = o.get_dat(i)
            if v is not None:
                fields[i].add(v)
    dfields = {}
    ignore_fields = ignore_fields if ignore_fields else []
    for f in fields:
        if f not in ignore_fields:
            if len(fields[f]) > 1:
                dfields[f] = fields[f]
    return dfields


def and_values_str(vals):
    if len(vals) > 1:
        return ', '.join(['%s' % i for i in vals[:-1]]) + ' and ' + '%s' % vals[-1]
    return '%s' % vals[0]


def collect_values(objs, field):
    return list(set([o.get_dat(field) for o in objs if o.get_dat(field)]))


def do_collect_state(node, domain, intent='find'):
    slots = {}
    for name in node.inputs:
        element = next(filter(lambda x: x.typename() == "Str", node.input_view(name).topological_order()), None)
        if element:
            slots[domain + '-' + name] = element.dat

    frame = {
        "service": domain,
        "state": {
            "active_intent": intent + '_' + domain,
            "slot_values": slots,
        }
    }
    node.context.update_last_turn_frame(frame)


# fix annotation errors where we have Domain-Inform::'?'  instead of Domain-Request::'?'
# also tacked on to this - optionally remove the 'choice' slot - don't convert this.
def fix_inform_request(slots, rem_choice=True):
    for name, value in slots.items():
        if rem_choice and 'choice' in name:
            del slots[name]
            continue
        value = select_value(value)
        if value == '?' and '-Inform' in name:
            nm = re.sub('Inform', 'Request', name)
            slots[nm] = value
            del slots[name]

    return slots


EXTRACT_SIMP = True
OMIT_GET_INFO = False



def get_extract_exp_simp(domain, context, general, extracted, extracted_book, extracted_req):
    exps = []
    domain = domain.lower()
    ext = extracted + extracted_book
    if ext or (not OMIT_GET_INFO and not extracted_req):
        exps.append('revise_%s(%s)' % (domain, ', '.join(ext)))

    if extracted_req and not OMIT_GET_INFO:
        exps.append('get_%s_info(%s)' % (domain, ','.join(extracted_req)))

    return exps


# given the extracted fields (for inform, book, request), generate the Pexps
#  relies on uniform naming for all the domains!
#  e.g. for hotels: Hotel, FindHotel, get_hotel_info, HotelBookInfo  (book - only for hotel, restaurant, train)
def get_extract_exps(domain, context, general, extracted, extracted_book, extracted_req):
    if EXTRACT_SIMP:
        return get_extract_exp_simp(domain, context, general, extracted, extracted_book, extracted_req)
    exps = []
    has_req = len(extracted_req) > 0
    domain = domain.lower()
    Domain = domain.capitalize()
    exists = get_refer_match(context, Node.collect_nodes(context.goals), context.goals,
                             type='Find%s' % Domain, no_fallback=True)  # do NOT create a new one!
    if extracted or (not extracted_book and not has_req and not OMIT_GET_INFO):
        inner_node_str = f"{Domain}?({', '.join(extracted)})"

        if not extracted and general:
            exps.append(general)
        else:
            if not exists or not extracted:
                exps.append('raise_task(Find%s)' % Domain)
                exists = True
            if extracted:
                exps.append(f"revise(old={Domain}??(), newMode=overwrite, new={inner_node_str})")

    if extracted_book:
        inner_node_str = f"{Domain}BookInfo({', '.join(extracted_book)})"
        if not exists:
            exps.append('raise_task(Find%s)' % Domain)
        exps.append(f"revise(old={Domain}BookInfo?(), newMode=overwrite, new={inner_node_str})")

    if has_req and not OMIT_GET_INFO:
        exps.append('get_%s_info(%s)' % (domain, ','.join(extracted_req)))

    return exps


# update state using last top conversation node
def collect_last_state(context):
    tops = [n for n in context.goals if n.typename() == 'MwozConversation']
    if tops:
        context.clear_state()
        tops[-1].collect_state()


################################################################################################################
################################################################################################################

# MwozConversation is the top node - it represents the whole interaction with the user, and is responsible for:
#  - holding the active tasks
#  - storing completed tasks
#  - prompting the user for more requests
#  - finalizing interaction
# It is satisfied when it gets a goodbye input
class MwozConversation(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('tasks', Node)
        self.signature.add_sig('goodbye', Bool)
        self.inc_count('max_first_time_msg', 1)

    def add_task(self, t):
        self.inc_count('first_time_msg')  # skip initial message if adding task
        self.add_objects('tasks', t)  # may need a switch?

    # todo - still need to think about how to handle completed tasks
    # - the reason to move completed tasks away is to avoid confusing refer/revise
    #   (especially if two domains share inputs). but on the other hand, the saliency model may be enough to solve this.
    #   also, in case in the same dialog the user tries to book/find two instances of same type
    # - may need to also remove all the dup_of's? (to avoid going back to an unfinished version of the task??)
    def store_complete_tasks(self):
        msg = []
        if 'tasks' in self.inputs:
            tt = self.inputs['tasks']
            tasks = tt.get_op_objects(view=VIEW.INT)
            n_tasks = len(tasks)
            for t in tasks:
                if t.evaluated and n_tasks > 1:  # keep task around until there is another task (of same/any kind?)
                    m = t.yield_msg()
                    msg.append(m.text)
                    self.context.other_goals.append(t)
                    pnm, parent = t.get_parent()
                    parent.disconnect_input(pnm)
                    n_tasks -= 1
        if not msg:
            return ''
        return 'I made:  NL  ' + '  NL  '.join(msg)

    def finalize_conversation(self):
        pass

    def exec(self, all_nodes=None, goals=None):
        # 1. store completed tasks
        cmsg = self.store_complete_tasks()
        # 2. if goodbye - finalize
        if self.inp_equals('goodbye', True):
            self.context.add_message(self, 'Goodbye!')
            self.finalize_conversation()
        else:
            if self.count_ok('first_time_msg'):
                msg = 'Hello, I\'m your MWOZ agent. How can I help you?'
                self.inc_count('first_time_msg')
            else:
                msg = cmsg + 'Is there anything else I can do for you?'
            raise AskMoreInputException(msg, self)

    def allows_exception(self, e):
        self.store_complete_tasks()
        if self.inp_equals('goodbye', True):  # if goodbye - then ignore exceptions and proceed to evaluate self
            return True, e
        return False, e

    def collect_state(self):
        # 1. collect non-complete tasks
        tasks = []
        if 'tasks' in self.inputs:
            tt = self.inputs['tasks']
            tasks = tt.get_op_objects(view=VIEW.INT)

        # 2. completed tasks (unless newer task of same type)
        for t in self.context.other_goals:
            if t.typename() not in [i.typename() for i in tasks]:
                t.collect_state()

        # 3. current tasks
        for t in tasks:
            t.collect_state()


# this is a dummy task, whose sole use is to perform fallback search on completed tasks
# to use this - add params['fallback_type']='SearchCompleted' to the call to get_refer_match
class SearchCompleted(Node):
    def __init__(self):
        super().__init__()

    def fallback_search(self, parent, all_nodes=None, goals=None, do_eval=True, params=None):
        ctx = params['context']
        if not ctx.other_goals:
            return []
        nodes = self.collect_nodes(ctx.other_goals)
        role, typ, pos1 = None, None, None
        if params:
            role = params.get('role')
            pos1 = params.get('pos1')
            type = params.get('type')
        matches = get_refer_match(ctx, nodes, ctx.other_goals,
                                  pos1=pos1, role=role, type=type, no_fallback=True)
        return matches


# try to avoid using this!
# there may be several different ones
# this runs without input, and is always the one and only node in its graph
class mwoz_no_op(Node):
    def __init__(self):
        super().__init__()

    def exec(self, all_nodes=None, goals=None):
        ctx = self.context
        if len(ctx.goals) > 1:
            prev = ctx.goals[-2]
            # do we really need to duplicate? or just re-run the same graph?
            # one reason to duplicate so that we re-calc the updated state (for comparison with mwoz annotation)
            # can we do it somewhere else?
            dp = prev.duplicate_tree(prev)[-1]
            dp.call_eval(add_goal=False)


# find the task type, or create it if it does not exist
# returns the top goal with the requested task and adds it to the context goals
# does NOT call evaluation, or set result
# 'node' is needed just for context and in case we call construct (so could be any node in the same context)
def do_raise_task(node, typ):
    context = node.context
    typ0 = typ + '/0'
    seen_top_types = []  # don't go back to an older version of the same top goal
    for g in reversed(context.goals):
        if g.typename() not in seen_top_types:
            nds = g.topological_order(follow_res=False)
            tps = [n.typename_cl() for n in nds]
            ntp = [n for n, t in zip(nds, tps) if t == typ0]
            if ntp and 'MwozConversation/0' in tps:
                t = ntp[-1]
                pnm, parent = t.get_parent()
                while parent:  # assuming simple path to root
                    auto_reorder_inputs(parent, [t])
                    t = parent
                    pnm, parent = t.get_parent()
                if g != context.goals[-1]:
                    context.goals.append(g)
                return g
        seen_top_types.append(g.typename())

    # not found in graph - create a new task, but do not evaluate the created task
    d, e = node.call_construct_eval('refer(%s?(), no_eval=True)' % typ, context)
    d = d.res
    while d.typename() != 'MwozConversation' and d.outputs:
        pnm, d = d.get_parent()
    return d


# find the most recent graph in context.goals which has a subnode of a given type,
# raise that goal to the front, and re-evaluate it
# we may want to do something like in SWITCH - "activating" the sub task which has the target node
# todo - unnecessary logic inside - fix this once it's clearer how we deal with completed tasks!
# TODO - make this also create the task (using fallback search) if it does not exist yet.
class raise_task(Node):
    def __init__(self):
        super().__init__()  # dynamic out type
        self.signature.add_sig(posname(1), Str, True)

    def exec(self, all_nodes=None, goals=None):
        typ = self.get_dat(posname(1))
        d = do_raise_task(self, typ)
        self.set_result(d)
        e = d.call_eval(add_goal=True)
        if e:
            re_raise_exc(e)


class GenericPleasantry(Node):
    def __init__(self):
        super().__init__()

    def exec(self, all_nodes=None, goals=None):
        msg = self.yield_msg()
        if environment_definitions.agent_oracle:
            if environment_definitions.oracle_only:
                msg = self.context.agent_turn['utterance']
        self.context.add_message(self, msg)

    def yield_msg(self, params=None):
        return Message("Thank you! Goodbye!")


class General_thank(GenericPleasantry):
    def __init__(self):
        super().__init__()

    # for "thanks", which can come in the middle of an interaction, stay with the main task
    def trans_simple(self, top):
        pnm, parent = self.get_parent()
        if parent.typename() != 'side_task':
            parent.wrap_input(pnm, 'side_task(task=', do_eval=False)
            # parent.wrap_input(pnm, 'side_task(persist=True,task=', do_eval=False)
            return parent, None
        return self, None

    def yield_msg(self, params=None):
        return Message("I'm glad to help")


class General_bye(GenericPleasantry):
    def __init__(self):
        super().__init__()

    def yield_msg(self, params=None):
        return Message("Thank you! Goodbye!")


class General_welcome(GenericPleasantry):
    def __init__(self):
        super().__init__()

    def yield_msg(self, params=None):
        return Message("How can I help?")


class General_greet(GenericPleasantry):
    def __init__(self):
        super().__init__()

    def yield_msg(self, params=None):
        return Message("Hello! How can I help you?")
