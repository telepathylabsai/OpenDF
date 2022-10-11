from opendf.applications.multiwoz_2_2.nodes.multiwoz import *
from opendf.applications.multiwoz_2_2.utils import *
from opendf.graph.nodes.framework_functions import revise, duplicate_subgraph


if use_database:
    multiwoz_db = MultiWozSqlDB.get_instance()
else:
    multiwoz_db = MultiWOZDB.get_instance()
node_fact = NodeFactory.get_instance()
environment_definitions = EnvironmentDefinition.get_instance()


class Attraction(MultiWOZDomain):

    def __init__(self):
        super().__init__(Attraction)
        self.signature.add_sig('name', Name)
        self.signature.add_sig('type', Type)
        self.signature.add_sig('area', Area)
        self.signature.add_sig('pricerange', Pricerange)
        self.signature.add_sig('openhours', OpenHours)
        self.signature.add_sig('phone', Phone)
        self.signature.add_sig('postcode', Postcode)
        self.signature.add_sig('address', Address)
        self.signature.add_sig('entrancefee', EntranceFee)

    def get_context_values(self, inform_values=None, req_fields=None):
        slot_values = {}
        for name in self.inputs:
            element = next(filter(lambda x: x.typename() == "Str", self.input_view(name).topological_order()), None)
            slot_values[f'attraction-{name.lower()}'] = [element.dat] if element else []

        return slot_values

    def generate_sql_select(self):
        return select(MultiWozSqlDB.ATTRACTION_TABLE)

    def generate_sql_where(self, selection, parent_id, **kwargs):
        if 'address' in self.inputs:
            selection = self.input_view("address").generate_sql_where(
                selection, MultiWozSqlDB.ATTRACTION_TABLE.columns.address, **kwargs)

        if 'area' in self.inputs:
            selection = self.input_view("area").generate_sql_where(
                selection, MultiWozSqlDB.ATTRACTION_TABLE.columns.area, **kwargs)

        if 'entrancefee' in self.inputs:
            selection = self.input_view("entrancefee").generate_sql_where(
                selection, MultiWozSqlDB.ATTRACTION_TABLE.columns.entrancefee, **kwargs)

        if 'name' in self.inputs:
            selection = self.input_view("name").generate_sql_where(
                selection, MultiWozSqlDB.ATTRACTION_TABLE.columns.name, **kwargs)

        if 'openhours' in self.inputs:
            selection = self.input_view("openhours").generate_sql_where(
                selection, MultiWozSqlDB.ATTRACTION_TABLE.columns.openhours, **kwargs)

        if 'phone' in self.inputs:
            selection = self.input_view("phone").generate_sql_where(
                selection, MultiWozSqlDB.ATTRACTION_TABLE.columns.phone, **kwargs)

        if 'postcode' in self.inputs:
            selection = self.input_view("postcode").generate_sql_where(
                selection, MultiWozSqlDB.ATTRACTION_TABLE.columns.postcode, **kwargs)

        if 'pricerange' in self.inputs:
            selection = self.input_view("pricerange").generate_sql_where(
                selection, MultiWozSqlDB.ATTRACTION_TABLE.columns.pricerange, **kwargs)

        if 'type' in self.inputs:
            selection = self.input_view("type").generate_sql_where(
                selection, MultiWozSqlDB.ATTRACTION_TABLE.columns.type, **kwargs)

        return selection

    def graph_from_row(self, row, context):
        params = []
        for field in self.signature.keys():
            value = row[field]
            if value:
                if isinstance(value, str):
                    value = escape_string(value)
                params.append(f"{field}={value}")

        node_str = f"Attraction({', '.join(params)})"
        g, _ = Node.call_construct_eval(node_str, context, constr_tag=NODE_COLOR_DB)
        g.tags[DB_NODE_TAG] = 0
        return g

    def describe(self, params=None):
        prms = []
        address, area, name, pricerange, type = \
            self.get_dats(['address', 'area',  'name', 'pricerange', 'type'])
        prms.append(name if name else 'the ' + type if type else 'the attraction')
        if type:
            prms.append('is a %s' % type)
        if area:
            prms.append('in the %s' % area)
        if pricerange:
            prms.append('%s price range' % pricerange)

        return Message(', '.join(prms), objects=[self])

    def collect_state(self):
        do_collect_state(self, 'attraction')


class FindAttraction(Node):
    def __init__(self):
        super().__init__(Attraction)
        self.signature.add_sig(posname(1), Attraction, alias='attraction')
        self.inc_count('max_inform_name', 1)

    def exec(self, all_nodes=None, goals=None):
        context = self.context
        if posname(1) in self.inputs:
            att = self.inputs[posname(1)]
        else:
            att, _ = self.call_construct('Attraction?()', context)
            att.connect_in_out(posname(1), self)

        results = results0 = multiwoz_db.find_elements_that_match(att, att.context)
        nresults = nresults0 = len(results)

        self.filter_and_set_result(results)  # initially set result to single result, if single, or don't

        inform_fields = defaultdict(list)
        rec_field = 'rec_name'
        req_fields = {}
        sugg = None
        objs = None
        if environment_definitions.agent_oracle:
            dact = context.agent_turn['dialog_act']['dialog_act']
            atext = context.agent_turn['utterance']
            # 1. try to understand what the agent did -
            for d in dact:
                dom, typ = d.split('-')
                if dom=='Attraction':
                    if typ in ['Inform', 'Recommend']:
                        for [k, v] in dact[d]:
                            kk = 'rec_' + k if typ == 'Recommend' else k
                            inform_fields[kk].append(v)
                    if typ == 'Request':
                        for [k, v] in dact[d]:
                            req_fields[k] = v

            # for attractions - there are examples where the agent mentions just one name,
            #   but no attraction-recommend is present. convert this to a recommendation
            if 'rec_name' not in inform_fields and 'name' in inform_fields and len(to_list(inform_fields['name'])) == 1:
                rec_field = 'name'
            # for now - if the agent recommends an attraction (by name), then we create a suggestion with implicit accept
            if rec_field in inform_fields:
                if len(inform_fields[rec_field])==1:
                    nm = inform_fields[rec_field][0]
                    r = self.filter_and_set_result(results, nm)
                    if r:
                        results = r
                        nresults = len(results)
                    # results should not be empty - unless the agent made a mistake
                    sugg = self.mod_name_and_suggest_neg(att, nm)
                else:   # ignore multiple recommendations
                    del inform_fields[rec_field]

            if environment_definitions.oracle_only:
                # return the original message of the agent,
                #    but may need to change the result according to the agent's action
                #update_mwoz_state(att, context, inform_fields, req_fields)
                raise OracleException(atext, self, suggestions=sugg, objects=objs)

        if not environment_definitions.agent_oracle:
            # add here logic to recommend ...?
            if nresults > 1 and rec_field not in inform_fields:
                dfields = get_diff_fields(results0, ['type', 'area', 'pricerange'])
                if len(dfields)>0:
                    for f in list(dfields.keys())[:2]:
                        req_fields[f] = '?'

        if len(inform_fields)>0 or len(req_fields)>0:
            rname = inform_fields.get(rec_field)
            rname = rname[0] if rname else None
            if rname and not sugg:   # the recommendation was added by the logic (didn't come from the agent)
                r = self.filter_and_set_result(results, rname)
                results = r if r else results
                nresults = len(results)
                sugg = self.mod_name_and_suggest_neg(att, rname)

            # for the selected fields, we now get the ACTUAL values we see in the results
            # in a case like: "all three have free parking. I recommend X" - where there are values as well as
            # a recommendation, we add to the state the values before the recommendation.
            # arbitrary decision. (affects only comparison of states)
            for f in ['name', 'type', 'area', 'pricerange', 'entrancefee', 'address', 'phone', 'postcode']:  # todo add more
                if f in inform_fields:
                    inform_fields[f] = collect_values(results0, f)

            if rec_field not in inform_fields or req_fields:  #  and nresults>2:
                if len(req_fields)==0 and not environment_definitions.agent_oracle and nresults>2:  # don't suggest if following oracle
                    dfields = get_diff_fields(results, ['address', 'phone', 'postcode', 'name'])
                    if dfields:
                        req_fields = {i:'?' for i in list(dfields.keys())[:2]}

            msg = self.describe_inform_request(nresults0, inform_fields, req_fields)

            #update_mwoz_state(att, context, inform_fields, req_fields)  # use inform_fields to update state
            if nresults!=1:
                raise OracleException(msg, self, suggestions=sugg, objects=objs)
            else:
                self.context.add_message(self, msg)

        # no inform fields and no recommendation
        #update_mwoz_state(att, context)  # update without inform fields
        if nresults == 0:
            raise ElementNotFoundException(
                "I can not find a matching attraction in the database. Maybe another area or type?", self)
        if nresults > 1:
            diffs = ' or '.join(list(inform_fields.keys())[:2])
            if diffs:
                msg = 'Multiple (%d) matches found. Maybe select  %s?' % (nresults, diffs)
            else:
                msg = 'Multiple (%d) matches found. Can you be more specific?' % nresults
            raise MultipleEntriesSingletonException(msg, self, suggestions=sugg, objects=objs)

        # there is no 'book' above attraction (which would tell the user about the result), so do it here
        if self.count_ok('inform_name'):
            self.inc_count('inform_name')
            msg = ('How about %s?' % self.res.get_dat('name')) \
                if nresults0>1 and 'rec_name' in inform_fields else self.result.describe().text
            raise OracleException(msg, self, suggestions=sugg, objects=objs)

    def fallback_search(self, parent, all_nodes=None, goals=None, do_eval=True, params=None):
        top = [g for g in self.context.goals if g.typename()=='MwozConversation']
        if not top:
            top, _ = self.call_construct('MwozConversation()', self.context)
            self.context.add_goal(top)
        else:
            top = top[-1]
        s = '' if posname(1) in self.inputs else 'Attraction?()'
        d, e = self.call_construct('FindAttraction(%s)' % s, self.context)
        if posname(1) in self.inputs:
            self.inputs[posname(1)].connect_in_out(posname(1), d)
        top.add_task(d)
        parent.set_result(d)
        if do_eval:
            e = top.call_eval(add_goal=False)
            if e:
                raise e[0]
        return [d]

    # suggest an attraction by name - if user rejects, then clear attraction name
    def mod_name_and_suggest_neg(self, constr, nm):
        d, e = constr.call_construct('LIKE(Name(%s))' % escape_string(nm), constr.context)
        constr.replace_input('name', d)
        return ['revise(old=Attraction??(), newMode=overwrite, new=Attraction?(name=Clear()))',
                'side_task(task=no_op())']

    def filter_and_set_result(self, results, filter_name=None):
        if filter_name:
            f, _ = self.call_construct('Attraction?(name=LIKE(Name(%s)))' % escape_string(filter_name), self.context)
            results = [r for r in results if f.match(r)]
        if len(results)==1:
            self.set_result(results[0])
            results[0].call_eval(add_goal=False)  # not necessary, but adds color
        return results

    def describe_inform_request(self, nresults0, inform_fields, req_fields):
        prms = []
        nm = inform_fields.get('name')
        if nm and 'rec_name' not in inform_fields :
            prms.append('I have found ' + and_values_str(nm))

        if 'choice' in inform_fields:
            inform_fields['choice'] = [nresults0]
        choice = inform_fields.get('choice')
        if choice:
            prms.append('There are %d matching results' % nresults0)
        elif nresults0 > 1 and 'name' not in inform_fields:
            prms.append('I see several (%d) matches' % nresults0)

        typ = inform_fields.get('type')
        if typ:
            prms.append('of type ' + and_values_str(typ))

        area = inform_fields.get('area')
        if area:
            prms.append('In the ' + and_values_str(area))
        adr = inform_fields.get('address')
        if adr:
            adr = adr[0]
            prms.append('It\'s located at ' + adr)
        phone = inform_fields.get('phone')
        if phone:
            prms.append('The phone number is ' + phone[0])
        postcode = inform_fields.get('postcode')
        if postcode:
            prms.append('The post code number is ' + postcode[0])
        price = inform_fields.get('pricerange')
        if price:
            prms.append('The price is ' + price[0])

        if 'rec_name' in inform_fields:
            prms.append('I recommend %s' % inform_fields['rec_name'][0])
        if len(req_fields) > 0:
            if nresults0 > 0:
                prms.append('maybe select %s' % ' or '.join([i for i in req_fields]))
            else:
                prms.append('Sorry, I can\'t find a match. Try a different %s' % ' or '.join([i for i in req_fields]))
        msg = ', '.join(prms)
        return msg

    def on_duplicate(self, dup_tree=False):
        old = self.dup_of.res if self.dup_of.res != self.dup_of else self.dup_of.input_view('attraction')
        curr = self.input_view('attraction')
        if 'name' in old.inputs and 'name' in curr.inputs:
            changed = any([old.get_dat(i)!=curr.get_dat(i) and curr.get_dat(i) is not None
                           for i in ['area', 'type', 'pricerange']])
            if changed:
                curr.disconnect_input('name')
                self.reset_count('inform_name')
        return self

    def collect_state(self):
        if self.result!=self:
            self.res.collect_state()
        elif 'attraction' in self.inputs:
            self.inputs['attraction'].collect_state()


class revise_attraction(revise):
    # make it a subtype of revise, so we don't revise this call
    def __init__(self):
        super().__init__()
        self.signature.add_sig('name', Name)
        self.signature.add_sig('type', Type)
        self.signature.add_sig('area', Area)
        self.signature.add_sig('pricerange', Pricerange)
        self.signature.add_sig('openhours', OpenHours)
        self.signature.add_sig('phone', Phone)
        self.signature.add_sig('postcode', Postcode)
        self.signature.add_sig('address', Address)
        self.signature.add_sig('entrancefee', EntranceFee)

    def valid_input(self):  # override the revise valid_input
        pass

    def trans_simple(self, top):
        if 'name' in self.inputs:
            n = self.input_view('name')
            if n.typename()=='Name':
                self.wrap_input('name', 'LIKE(')
        return self, None

    def exec(self, all_nodes=None, goals=None):
        # 1. raise or create task
        root = do_raise_task(self, 'FindAttraction') #  the top conversation

        # 2. do revise if requested fields given
        attraction_fields = ['name', 'type', 'area', 'pricerange', 'openhours', 'phone', 'postcode', 'address', 'entrancefee']
        fields = [i for i in self.inputs if i in attraction_fields]
        if fields:
            nodes = root.topological_order(follow_res=False)
            find = [i for i in nodes if i.typename()=='FindAttraction']
            if find:  # should always be the case
                find = find[0]
                prms = ['%s=%s' % (i, id_sexp(self.inputs[i])) for i in fields]
                old = find.inputs['attraction']
                s = 'Attraction?(' + ','.join(prms) + ')'
                new, _ = self.call_construct(s, self.context)
                new_subgraph = duplicate_subgraph(root, old, new, 'overwrite', self)
                root = new_subgraph[-1]

        self.set_result(root)
        self.context.add_goal(root)  # will not add if already added before
        # root.call_eval()  # no need to call eval, since eval_res is True. is this what we want?


class get_attraction_info(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('attraction', Attraction)
        self.signature.add_sig(POS, Str)

    def trans_simple(self, top):
        pnm, parent = self.get_parent()
        if parent and parent.typename()!='side_task':
            if PERSIST_SIDE:
                parent.wrap_input(pnm, 'side_task(persist=True,task=', do_eval=False)
            else:
                parent.wrap_input(pnm, 'side_task(task=', do_eval=False)
            return parent, None
        return self, None

    def exec(self, all_nodes=None, goals=None):
        att = self.input_view('attraction')
        if not att:
            m = get_refer_match(self.context, all_nodes, goals, type='Attraction')
            if m:
                att = m[0]
            else:
                raise MissingValueException('I can give information only after we have selected one attraction', self)

        if att:
            fts = []
            fts += [self.input_view(i).dat for i in self.inputs if is_pos(i)]
            if fts:
                vals = ['the %s is %s' %(i, att.get_dat(i)) for i in fts]
                msg = 'For %s: ' % att.get_dat('name') + ',  NL  '.join(vals)
                self.context.add_message(self, msg)

    def yield_msg(self, params=None):
        msg = self.context.get_node_messages(self)
        return msg[0] if msg else Message('')


def extract_find_attraction(utterance, slots, context=None, general=None):
    extracted = []
    problems = set()
    has_req = any([i for i in slots if 'request' in i])
    for name, value in slots.items():
        if 'choice' in name:
            continue
        if 'request-' in name:
            continue
        value = select_value(value)
        if not name.startswith(ATTRACTION_PREFIX):
            problems.add(f"Slot {name} not mapped for find_attraction!")
            continue

        role = name[ATTRACTION_PREFIX_LENGTH:]
        if value in SPECIAL_VALUES:
            extracted.append(f"{role}={SPECIAL_VALUES[value]}")
            continue

        if context and value not in utterance:
            references = get_refer_match(context, Node.collect_nodes(context.goals), context.goals,
                                         role=role, params={'fallback_type':'SearchCompleted', 'role': role})
            if references and references[0].dat == value:
                extracted.append(f"{role}=refer(role={role})")
                continue
            # else:
            # TODO: maybe log that the reference could not be found in the graph

        if name == "attraction-name":
            if EXTRACT_SIMP:
                extracted.append(f"name={escape_string(value)}")
            else:
                extracted.append(f"name=LIKE(Name({escape_string(value)}))")
        elif name == "attraction-type":
            extracted.append(f"type={escape_string(value)}")
        elif name == "attraction-pricerange":
            extracted.append(f"pricerange={escape_string(value)}")
        elif name == "attraction-area":
            extracted.append(f"area={escape_string(value)}")
        else:
            problems.add(f"Slot {name} not mapped for find_attraction!")

    extracted_req = []
    if has_req:
        for name, value in slots.items():
            if 'request' in name:
                value = select_value(value)
                if not name.startswith(ATTRACTION_PREFIX + 'request-'):
                    problems.add(f"Slot {name} not mapped for find_attraction request!")
                    continue

                role = name[ATTRACTION_PREFIX_LENGTH+len('request-'):]

                if role in ['name', 'area', 'type', 'entrancefee', 'openhours', 'phone', 'address',
                            'postcode', 'pricerange']:
                    extracted_req.append(role)
                # todo - add other fields and check not a bad field name

    exps = get_extract_exps('Attraction', context, general, extracted, [], extracted_req)

    return exps, problems
