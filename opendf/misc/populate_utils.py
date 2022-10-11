import re
from opendf.applications.smcalflow.domain import fill_graph_db
#from opendf.applications.smcalflow.populating_stub_data import init_db_person, init_db_events, init_weather_places\
from opendf.applications.smcalflow.domain import add_db_person, add_db_event, \
    add_db_place, mod_db_event, get_stub_data_from_json
from opendf.applications.core.nodes.time_nodes import date_sexp, time_sexp, datetime_to_domain_str
from opendf.misc.templates_utils import norm_text, norm2
from opendf.defs import *
from opendf.utils.utils import id_sexp, to_list
from opendf.applications.smcalflow.exceptions.df_exception import MultipleEventSuggestionsException
from opendf.applications.smcalflow.nodes.objects import Event
from opendf.applications.core.nodes.time_nodes import name_to_month
from opendf.graph.nodes.framework_functions import get_refer_match

from nltk import CFG
from nltk.parse import RecursiveDescentParser, ShiftReduceParser, ChartParser, EarleyChartParser
from nltk.tree.tree import Tree

def get_agent_person_ents(ctx):
    templates = ctx.templates
    pos, neg = [], []
    awords, atempls, avals = ctx.agent_words, ctx.agent_templs, ctx.agent_vals
    if 'PersonName' in awords:
        for i,w in enumerate(awords):
            if w=='PersonName':
                pos.append(avals[i])  # just pos for now
    else:
        return pos, neg


def init_db(d_context, people=None, events=None, places=None, data_file=None, additional_objs=None):
    db_persons, db_events, weather_places = [], [], []
    if data_file and (people is None or events is None or places is None):
        db_events, db_persons, weather_places, _, _, _, _, _ = get_stub_data_from_json(data_file)
    people = people if people else db_persons
    events = events if events else db_events
    places = places if places else weather_places
    if additional_objs:
        people += additional_objs[0]
        events += additional_objs[1]
        places += additional_objs[2]
    d_context.db_people = people
    d_context.db_events = events
    d_context.db_places = places
    if use_database:
        from opendf.applications.smcalflow.database import Database, populate_stub_database
        from opendf.applications.smcalflow.storage_factory import StorageFactory
        database = Database.get_instance()
        if database:
            database.clear_database()
        populate_stub_database(data_file, people, events, places)
        storage = StorageFactory.get_instance()
        storage.clear_cache()
    else:
        fill_graph_db(d_context, people, events)


def get_all_db_events():
    # DBevent :  ['id', 'subject', 'start', 'end', 'location', 'attendees', 'accepted', 'showas']
    dbevs = []
    if use_database:
        from opendf.applications.smcalflow.database import Database
        from opendf.applications.smcalflow.storage_factory import StorageFactory
        from opendf.applications.smcalflow.domain import DBevent
        database = Database.get_instance()
        if database:
            for e in database._get_event_entries('all'):
                id = e.identifier
                subj = e.subject
                start = datetime_to_domain_str(e.starts_at)
                end = datetime_to_domain_str(e.ends_at)
                loc = e.location.identifier
                atts = [i.recipient.identifier for i in e.attendees]
                acc =  [i.response_status for i in e.attendees]
                shw =  [i.show_as_status for i in e.attendees]
                dbevs.append(DBevent(id, subj, start, end, loc, atts, acc, shw))
    return dbevs


def add_person(d_context, fullName=None, firstName=None, lastName=None, id=None, phone=None, email=None, manager=None, friends=None):
    p = add_db_person(d_context.db_people, fullName, firstName, lastName, id, phone, email, manager, friends)
    d_context.db_people = p
    init_db(d_context, d_context.db_people, d_context.db_events, data_file=d_context.init_stub_file)


def add_event(d_context, subject=None, start=None, end=None, location=None, attendees=None, accepted=None, showas=None):
    id = 1 if not d_context.db_events else max([e.id for e in d_context.db_events]) + 1
    p = add_db_event(d_context.db_events, id, subject, start, end, location, attendees, accepted, showas)
    d_context.db_events = p
    d_context.populated_events.append(id)
    init_db(d_context, d_context.db_people, d_context.db_events, d_context.db_places, data_file=d_context.init_stub_file)


def modify_event(d_context, id, subject=None, start=None, end=None, location=None,
                 attendees=None, accepted=None, showas=None):
    p = mod_db_event(d_context.db_events, id, subject, start, end, location, attendees, accepted, showas)
    d_context.db_events = p
    init_db(d_context, d_context.db_people, d_context.db_events, d_context.db_places, data_file=d_context.init_stub_file)


gram = CFG.fromstring('\n'.join(open('opendf/misc/agent_answer.cfg', 'r').readlines()))
# parser = ShiftReduceParser(gram)  # do NOT use shift-reduce parser !
                                    # (requires that no rhs is a prefix of another rhs - which we need)
# parser = RecursiveDescentParser(gram) # don't use - can fail in a very slow way
parser = EarleyChartParser(gram)

productions = gram.productions()

# check for shift reduce
# # Any production whose RHS is an extension of another production's RHS
# # will never be used.
# for i in range(len(productions)):
#     for j in range(i + 1, len(productions)):
#         rhs1 = productions[i].rhs()
#         rhs2 = productions[j].rhs()
#         if rhs1[: len(rhs2)] == rhs2:
#             print("Warning: %r will never be used" % productions[i])
#             print('    %s : %s\n    %s : %s' % (productions[i], rhs1, productions[j], rhs2))


class ParseNode():
    def __init__(self, name, parent=None, children=None):
        self.name = name
        self.parent = parent
        self.children = children if children else []

    def show(self):
        s = self.name
        n = self
        while n.parent:
            n = n.parent
            s += '/' + n.name
        return s

    def __repr__(self):
        return self.show()

    @staticmethod
    def from_tree(t, parent=None):
        nm = t.label() if isinstance(t, Tree) else t
        nd = ParseNode(nm, parent)
        if isinstance(t, Tree):
            for i in t:
                nd.children.append(ParseNode.from_tree(i, nd))
        return nd

    def get_leaves(self):
        leaves = []
        stack = [self]
        while stack:
            nd = stack.pop()
            if nd.children:
                stack += reversed(nd.children)
            else:
                leaves.append(nd)
        return leaves

    def get_subnodes(self, typ=None):
        typ = to_list(typ) if typ else typ
        nodes = []
        stack = [self]
        while stack:
            nd = stack.pop()
            if not typ or nd.name in typ:
                nodes.append(nd)
            stack += nd.children
        return nodes

    def has_subnode(self, name):
        stack = [self]
        while stack:
            nd = stack.pop()
            if nd.name==name:
                return True
            stack += nd.children
        return False

    # get ALL nodes which pass through the specified node types (keep order)
    def get_sub_ext(self, ext):
        if not ext:
            return [self]
        if not isinstance(ext, list):
            ext = ext.split('.')
        nds = self.get_subnodes(ext[0])
        subs = [i.get_sub_ext(ext[1:]) for i in nds]
        return sum(subs,[])



# def get_leaves_paths(tree):
#     pp = ParseNode.from_tree(tree)
#     ll = pp.get_leaves()
#     leaves = []
#     stack = [(tree, ('S',))]
#     while stack:
#         value, treepos = stack.pop()
#         if not isinstance(value, Tree):
#             leaves.append((value, treepos))
#         else:
#             for i in range(len(value) - 1, -1, -1):
#                 try:
#                     v = treepos if not isinstance(value[i], Tree) else treepos + (value[i]._label,)
#                     stack.append((value[i], v))
#                 except Exception as ex:
#                     pass
#     return leaves


def align_parse(prs, alg):
    pn = ParseNode.from_tree(prs)
    # leaves = get_leaves_paths(prs[0])
    leaves = pn.get_leaves()
    if len(leaves) != len(alg):
        raise Exception("bad parse %s / %s" % (prs, alg))
    # return [(w,a,l,'/'.join(p)) for (w,a),(l,p) in zip(alg,leaves)]
    # return [(w,a,l,'/'.join(p), '/'.join([i for i in p if i[-1]=='_'])) for (w,a),(l,p) in zip(alg,leaves)]
    return pn, [(w, a, n) for (w,a),n in zip(alg,leaves)]


# now - loads and builds gram/parser each call - fix
def parse_agent_txt(txt):
    prs, alg = [], []
    try:
        nrm = norm2(txt)
        tt = nrm[0].split()
        prs = list(parser.parse(tt))[0]  # assuming only one tree - i.e. only one sentence at a time!
        if prs:
            prs, alg = align_parse(prs, nrm[1])
    except Exception as ex:
        return [], []
    return prs, alg


def leaf_to_alg(l, alg):
    for w,a,n in alg:
        if n==l:
            return (w,a,n)
    return None


def get_aligned_val(n, alg):
    a = leaf_to_alg(n, alg)
    if a:
        return a[1]
    return None


def get_parse_date(n, alg):  # TODO - distinguish start / end
    yr, mn, dy, wd = None, None, None, None
    if n.has_subnode('EV_DATE_P2'):
        m = n.get_subnodes('MONTH')[0]
        mn = get_aligned_val(m, alg)
        if isinstance(mn, str):
            mn = name_to_month(mn)
    return yr, mn, dy, wd


def get_parse_time(n, alg):  # TODO - distinguish start / end
    hr, mt, mr = None, None, None
    if n.has_subnode('EV_TIME_P1'):
        m = n.get_sub_ext('TIME1.TM_HM.num:num')
        if m:
            hm = get_aligned_val(m[0], alg)
            if hm:
                [hr, mt] = [int(i) for i in hm.split(':')]

        m = n.get_sub_ext('TIME1.TM_MD.merid')
        if m:
            mr = get_aligned_val(m[0], alg)
    return hr, mt, mr


def get_parse_subject(n, alg):  # TODO - distinguish start / end
    subj = None
    if n.has_subnode('EV_SUBJ_P1'):
        m = n.get_sub_ext('EV_SUBJ_P1.TITLE.quote')
        if m:
            subj = get_aligned_val(m[0], alg)
            if subj:
                subj = re.sub('"', '', subj)
                if subj[-1]==':':
                    subj = subj[:-1]
    return subj


def get_person_name(p, alg):
    first, last = None, None
    n = p.get_subnodes(typ='NAME')
    if n:
        nsub = n[0].get_subnodes(['tok', 'PersonName'])
        if nsub:
            first = get_aligned_val(nsub[0], alg)
    n2 = p.get_subnodes(typ='NAME2')
    if n2:
        n2sub = n2[0].get_subnodes(['tok', 'PersonName'])
        if n2sub:
            last = re.sub('[.]', '', get_aligned_val(n2sub[0], alg))
    return first, last


def get_parse_attendees(n, alg):
    pers = n.get_subnodes(typ='PERSON')
    return [get_person_name(p, alg) for p in pers]


def get_event_fields(prs, alg):
    fields = {}
    pos = [i for i in prs.get_subnodes() if i.name=='POS_EV']
    if pos:
        pos = pos[0]  # take first POS_EV  (we don't expect multiple events (?))
        pnds = pos.get_subnodes()
        for n in pnds:
            if n.name=='EVENT_DATEx':  # TODO - distinguish start / end
                fields['date'] = get_parse_date(n, alg)
            if n.name=='EVENT_TIMEx':
                fields['time'] = get_parse_time(n, alg)
            if n.name=='EVENT_SUBJECTx':
                fields['subject'] = get_parse_subject(n, alg)
            if n.name=='EVENT_ATTENDEESx':
                fields['attendees'] = get_parse_attendees(n, alg)

    return fields


def create_pop_event(flt, fields):
    cp, _ = flt.duplicate_res_tree(keep_turn=True)
    if cp.typename()!='AND':
        d, e = cp.call_construct('AND(%s)' % id_sexp(cp), cp.context)
        d.created_turn = cp.created_turn  # needed??
        cp = d
    conds = []
    for i in fields:
        if i=='subject':
            conds.append('subject="%s"' % fields[i])
        elif i=='date':    # TODO - distinguish start / end
            yr, mn, dy, wd = fields[i]
            conds.append('slot=TimeSlot?(start=DateTime?(date=%s))' % date_sexp(yr, mn, dy, wd, allow_constr=True))
        elif i=='time':    # TODO - distinguish start / end
            hr, mt, mr = fields[i]
            conds.append('slot=TimeSlot?(start=DateTime?(time=%s))' % time_sexp(hr, mt, allow_constr=True, mr=mr))
    for c in conds:
        d, e = cp.call_construct('Event?(%s)' % c, cp.context)
        cp.add_pos_input(d)

    cp.prune_modifiers()

    try:
        d = Event.create_suggestion(cp, cp, prm=['first_only'])
        # TODO - event suggestion puts 'online' if no value is given - should put this to UNK?
        #   if 'LocationKeyPhrase' in d.subnodes...?
        #d.event_possible(avoid_id=ev.get_dat('id'), allow_clash=True)  # verify that the event is possible  - no clashes ...
    except Exception as ex:
        if isinstance(ex, MultipleEventSuggestionsException):
            if ex.suggestions and len(ex.suggestions)>1:
                sug = ex.suggestions[1]  # first positive
        print('problem creating event - no suggestion - skip\n%s' % cp.show())
        return False

    id, subject, start, end, loc, atts, accepted, showas = d.get_fields()
    if not loc:
        location = 0
    else:
        location = get_location_id(str(loc), flt.context, add_missing=True)
        # l = [p.id for p in flt.context.db_places if p.name and loc in p.name]
        # if l:
        #     location = l[0]
        # else:
        #     flt.context.db_places = add_db_place(flt.context.db_places, name=loc)
        #     location = [p.id for p in flt.context.db_places if p.name and loc in p.name][0]
    add_event(flt.context, subject, start, end, location, atts, accepted, showas)
    return True


def get_location_id(nm, context, add_missing=False):
    location = None
    l = [p.id for p in context.db_places if p.name and nm in p.name]
    if l:
        location = l[0]
    else:
        context.db_places = add_db_place(context.db_places, name=nm)
        location = [p.id for p in context.db_places if p.name and nm in p.name][0]
    return location


def make_new_attendee(rcp, evid):
    prms = []
    prms.append('recipient=%s' % id_sexp(rcp))
    if evid is not None:
        prms.append('eventid=%d' % evid)
    prms.append('response=NotResponded')
    prms.append('show=Busy')
    d, e = rcp.call_construct('Attendee(' + ','.join(prms) + ')', rcp.context)
    return d


# assuming the create event has all the fields (although some may be UNK)
def modify_pop_event(ev, fields):
    context = ev.context
    ats, acpts, shows = [], [], []
    f_loc = None
    for i in fields:
        if i=='subject':
            n = ev.input_view(i)
            n.data = fields[i]
        elif i=='date':    # TODO - distinguish start / end
            yr, mn, dy, wd = fields[i]
            n = ev.get_ext_view('slot.start.date')
            if yr is not None:
                n.input_view('year').data = yr
            if mn is not None:
                n.input_view('month').data = mn
            if dy is not None:
                n.input_view('day').data = dy
            if wd is not None:
                n.input_view('dow').data = wd
        elif i=='time':    # TODO - distinguish start / end
            hr, mt, mr = fields[i]
            n = ev.get_ext_view('slot.start.time')
            if n:
                hr = None if hr is None else hr if mr is None else 12+hr%12 if 'p' in mr.lower() else hr%12
                if hr is not None:
                    n.input_view('hour').data = hr
                if mt is not None:
                    n.input_view('minute').data = mt
        elif i=='attendees':
            for f,l in fields[i]:
                try:
                    nm = '%s %s' % (f, l) if l else f
                    if nm != 'you':   # do we also need to add current user?
                        d, e = ev.call_construct('Recipient?(name=LIKE(PersonName(%s)))' % nm, ev.context)
                        m = get_refer_match(ev.context, None, None, pos1=d, force_fallback=True, params=['verified'])
                        if m and m[0].get_dat('id') and m[0].get_dat('id') not in ev.get_attendee_ids():
                            ats.append(make_new_attendee(m[0], ev.get_dat('id')))
                except Exception as ex:
                    print('Error adding %s' % nm)
            ev.add_objects('attendees', ats)

        elif i=='location':
            n = ev.get_ext_view('location.LocationKeyPhrase.Str')
            if n:
                location = get_location_id(fields[i], context, add_missing=True)

    id, subject, start, end, loc, atts, accepted, showas = ev.get_fields()
    location = get_location_id(loc, context, add_missing=True)

    modify_event(context, id, subject, start, end, location, atts, accepted, showas)
    return True


# check if the object is one which was created by populate
def is_populate_object(nd):
    nm = nd.typename()
    if nm=='Event':
        d_context = nd.context
        db_events, db_persons, weather_places, _, _, _, _, _ = get_stub_data_from_json(d_context.init_stub_file)
        id = nd.get_dat('id')
        return id is not None and not [e for e in db_events if e.id==id]
    # TODO - add more types
    return False
