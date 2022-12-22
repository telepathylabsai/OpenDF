from opendf.applications.multiwoz_2_2.nodes.multiwoz import *
from opendf.applications.multiwoz_2_2.utils import *
from opendf.graph.nodes.framework_functions import revise, duplicate_subgraph

if use_database:
    multiwoz_db = MultiWozSqlDB.get_instance()
else:
    multiwoz_db = MultiWOZDB.get_instance()
node_fact = NodeFactory.get_instance()
environment_definitions = EnvironmentDefinition.get_instance()


class Hospital(MultiWOZDomain):

    def __init__(self):
        super().__init__(Hospital)
        self.signature.add_sig('department', Department)
        self.signature.add_sig('phone', Phone)

    def get_context_values(self, inform_values=None, req_fields=None):
        slot_values = {}
        for name in self.inputs:
            element = next(filter(lambda x: x.typename() == "Str", self.input_view(name).topological_order()), None)
            slot_values[f'hospital-{name.lower()}'] = [element.dat] if element else []

        return slot_values

    def generate_sql_select(self):
        return select(MultiWozSqlDB.HOSPITAL_TABLE)

    def generate_sql_where(self, selection, parent_id, **kwargs):
        if 'department' in self.inputs:
            selection = self.input_view("department").generate_sql_where(
                selection, MultiWozSqlDB.HOSPITAL_TABLE.columns.department, **kwargs)

        if 'phone' in self.inputs:
            selection = self.input_view("phone").generate_sql_where(
                selection, MultiWozSqlDB.HOSPITAL_TABLE.columns.phone, **kwargs)

        return selection

    def graph_from_row(self, row, context):
        params = []
        for field in self.signature.keys():
            value = row[field]
            if value:
                if isinstance(value, str):
                    value = escape_string(value)
                params.append(f"{field}={value}")

        node_str = f"Hospital({', '.join(params)})"
        g, _ = Node.call_construct_eval(node_str, context, constr_tag=NODE_COLOR_DB)
        g.tags[DB_NODE_TAG] = 0
        return g

    def describe(self, params=None):
        prms = []
        dpt, name, phone= self.get_dats(['department', 'name', 'phone'])
        if not dpt:
            prms.append(name if name else 'the hospital')
        if dpt:
            s = 'has a ' if name else 'the '
            t = '' if any ([i in dpt.lower() for i in ['department', 'hospital']]) else ' department'
            prms.append('%s %s%s' % (s, dpt, t))
        if phone:
            prms.append('the phone number is %s' % phone)
        return Message(', '.join(prms), objects=[self])

    def collect_state(self):
        do_collect_state(self, 'hospital')


class FindHospital(Node):
    def __init__(self):
        super().__init__(Hospital)
        self.signature.add_sig(posname(1), Hospital, alias='hospital')
        self.inc_count('max_inform', 1)

    def exec(self, all_nodes=None, goals=None):
        context = self.context
        if posname(1) in self.inputs:
            hospital = self.inputs[posname(1)]
        else:
            hospital, _ = self.call_construct('Hospital?()', context)
            hospital.connect_in_out(posname(1), self)

        has_constr = [i for i in hospital.inputs if hospital.input_view(i)]
        if has_constr:
            results = results0 = multiwoz_db.find_elements_that_match(hospital, hospital.context)
            # in the dataset, it seems that the agent arbitrarily picks a match when several are available (?)
            if len(results)>1:
                results = results0 = [results[0]]
        else:
            # the dataset only contains department names, without any hospital name/info, but in some dialogues
            # hospital names are mentioned (as well as address and postcode) ...??
            # in the dataset, if users just ask for a hospital (with no further detail), they get Addenbrokes
            # (actually, this is the only hospital name mentioned in dialogs)
            # we had to add this to the MWOZ file hospital_db.json:
            # {
            #         "department": "Addenbrookes Hospital",
            #         "id": 999,
            #         "phone": "01223245151"
            #     },
            h, _ = self.call_construct('Hospital?(department=LIKE(Department(Addenbrokes Hospital)))', context)
            results = results0 = multiwoz_db.find_elements_that_match(h, hospital.context)
        # todo - for hospital just take any match if any found (?)
        nresults = nresults0 = len(results)

        self.filter_and_set_result(results)  # initially set result to single result, if single, or don't

        inform_fields = defaultdict(list)
        req_fields = {}
        sugg = None
        objs = None
        if environment_definitions.agent_oracle:
            dact = context.agent_turn['dialog_act']['dialog_act']
            atext = context.agent_turn['utterance']
            # 1. try to understand what the agent did -
            for d in dact:
                dom, typ = d.split('-')
                if dom=='Hospital':
                    if typ in ['Inform']:
                        for [k, v] in dact[d]:
                            inform_fields[k].append(v)
                    if typ == 'Request':
                        for [k, v] in dact[d]:
                            req_fields[k] = v

            if environment_definitions.oracle_only:
                # return the original message of the agent,
                #    but may need to change the result according to the agent's action
                #update_mwoz_state(Hospital, context, inform_fields, req_fields)
                raise OracleException(atext, self, suggestions=sugg, objects=objs)

        if not environment_definitions.agent_oracle:
            # add here logic to recommend ...?
            if nresults > 1:  #  and 'rec_name' not in inform_fields:
                dfields = get_diff_fields(results0, ['name'])
                if len(dfields)>0:
                    for f in list(dfields.keys())[:2]:
                        req_fields[f] = '?'

        if len(inform_fields)>0 or len(req_fields)>0:

            for f in ['department', 'phone']:  # todo add more
                if f in inform_fields:
                    inform_fields[f] = collect_values(results0, f)

            if 'rec_name' not in inform_fields or req_fields:  #  and nresults>2:
                if len(req_fields)==0 and not environment_definitions.agent_oracle and nresults>2:  # don't suggest if following oracle
                    dfields = get_diff_fields(results, ['phone', 'department'])
                    if dfields:
                        req_fields = {i:'?' for i in list(dfields.keys())[:2]}

            msg = self.describe_inform_request(nresults0, inform_fields, req_fields)

            #update_mwoz_state(hospital, context, inform_fields, req_fields)  # use inform_fields to update state
            if nresults!=1:
                raise OracleException(msg, self, suggestions=sugg, objects=objs)
            else:
                self.context.add_message(self, msg)

        # no inform fields and no recommendation
        #update_mwoz_state(hospital, context)  # update without inform fields
        if nresults == 0:
            raise ElementNotFoundException(
                "I can not find a matching hospital in the database. Maybe another area or type?", self)
        if nresults > 1:
            diffs = ' or '.join(list(inform_fields.keys())[:2])
            if diffs:
                msg = 'Multiple (%d) matches found. Maybe select  %s?' % (nresults, diffs)
            else:
                msg = 'Multiple (%d) matches found. Can you be more specific?' % nresults
            raise MultipleEntriesSingletonException(msg, self, suggestions=sugg, objects=objs)

        # there is no 'book' above Hospital (which would tell the user about the result), so do it here
        if self.count_ok('inform'):
            self.inc_count('inform')
            # msg = 'I found several matches. How about %s?' % self.res.get_dat('name') \
            #     if nresults0>1 and 'rec_name' in inform_fields else self.result.describe()[0]
            msg = 'I found:  NL  ' + self.result.describe().text
            raise OracleException(msg, self, suggestions=sugg, objects=objs)

    def fallback_search(self, parent, all_nodes=None, goals=None, do_eval=True, params=None):
        top = [g for g in self.context.goals if g.typename()=='MwozConversation']
        if not top:
            top, _ = self.call_construct('MwozConversation()', self.context)
            self.context.add_goal(top)
        else:
            top = top[-1]
        s = '' if posname(1) in self.inputs else 'Hospital?()'
        d, e = self.call_construct('FindHospital(%s)' % s, self.context)
        if posname(1) in self.inputs:
            self.inputs[posname(1)].connect_in_out(posname(1), d)
        top.add_task(d)
        parent.set_result(d)
        if do_eval:
            e = top.call_eval(add_goal=False)
            if e:
                raise e[0]
        return [d]

    # suggest an Hospital by name - if user rejects, then clear Hospital name
    # def mod_name_and_suggest_neg(self, constr, nm):
    #     d, e = constr.call_construct('LIKE(Name(%s))' % nm, constr.context)
    #     constr.replace_input('name', d)
    #     return ['revise(old=Hospital??(), newMode=overwrite, new=Hospital?(name=Clear()))',
    #             'side_task(task=no_op())']

    def filter_and_set_result(self, results, filter_name=None):
        if filter_name:
            f, _ = self.call_construct('Hospital?(department=LIKE(Department(%s)))' % filter_name, self.context)
            results = [r for r in results if f.match(r)]
        if len(results)==1:
            self.set_result(results[0])
            results[0].call_eval(add_goal=False)  # not necessary, but adds color
        return results

    def describe_inform_request(self, nresults0, inform_fields, req_fields):
        prms = []
        nm = inform_fields.get('name')
        if nm:
            prms.append('I have found ' + and_values_str(nm))

        dpt = inform_fields.get('department')
        if dpt:
            prms.append('department name ' + and_values_str(dpt))

        if 'choice' in inform_fields:
            inform_fields['choice'] = [nresults0]
        choice = inform_fields.get('choice')
        if choice:
            prms.append('There are %d matching results' % nresults0)
        elif nresults0 > 1:
            prms.append('I see several (%d) matches' % nresults0)
        plural=nresults0>1

        phone = inform_fields.get('phone')
        if phone:
            prms.append('The phone number is ' + phone[0])

        # if 'rec_name' in inform_fields:
        #     prms.append('I recommend %s' % inform_fields['rec_name'][0])
        if len(req_fields) > 0:
            if nresults0 > 0:
                prms.append('maybe select %s' % ' or '.join([i for i in req_fields]))
            else:
                prms.append('Sorry, I can\'t find a match. Try a different %s' % ' or '.join([i for i in req_fields]))
        msg = ', '.join(prms)
        return msg

    def collect_state(self):
        if self.result!=self:
            self.res.collect_state()
        elif 'hospital' in self.inputs:
            self.inputs['hospital'].collect_state()


class revise_hospital(revise):
    # make it a subtype of revise, so we don't revise this call
    def __init__(self):
        super().__init__()
        self.signature.add_sig('department', Department)
        self.signature.add_sig('phone', Phone)

    def valid_input(self):  # override the revise valid_input
        pass

    def transform_graph(self, top):
        if 'department' in self.inputs:
            n = self.input_view('department')
            if n.typename()=='Department':
                self.wrap_input('department', 'LIKE(')
        return self, None

    def exec(self, all_nodes=None, goals=None):
        # 1. raise or create task
        root = do_raise_task(self, 'FindHospital') #  the top conversation

        # 2. do revise if requested fields given
        hospital_fields = ['department', 'phone']
        fields = [i for i in self.inputs if i in hospital_fields]
        if fields:
            nodes = root.topological_order(follow_res=False)
            find = [i for i in nodes if i.typename()=='FindHospital']
            if find:  # should always be the case
                find = find[0]
                prms = ['%s=%s' % (i, id_sexp(self.inputs[i])) for i in fields]
                old = find.inputs['hospital']
                s = 'Hospital?(' + ','.join(prms) + ')'
                new, _ = self.call_construct(s, self.context)
                new_subgraph = duplicate_subgraph(root, old, new, 'overwrite', self)
                root = new_subgraph[-1]

        self.set_result(root)
        self.context.add_goal(root)  # will not add if already added before
        # root.call_eval()  # no need to call eval, since eval_res is True. is this what we want?


class get_hospital_info(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('Hospital', Hospital)
        #self.signature.add_sig('feats', Node)
        self.signature.add_sig(POS, Str)

    def transform_graph(self, top):
        pnm, parent = self.get_parent()
        if parent.typename()!='side_task':
            if PERSIST_SIDE:
                parent.wrap_input(pnm, 'side_task(persist=True,task=', do_eval=False)
            else:
                parent.wrap_input(pnm, 'side_task(task=', do_eval=False)
            return parent, None
        return self, None

    def exec(self, all_nodes=None, goals=None):
        hospital = self.input_view('hospital')
        if not hospital:
            m = get_refer_match(self.context, all_nodes, goals, type='Hospital')
            if m:
                hospital = m[0]
            else:
                raise MissingValueException('hospital', self, 'I can give information only after we have selected one hospital')

        if hospital:
            fts = []
            fts += [self.input_view(i).dat for i in self.inputs if is_pos(i)]
            if fts:
                vals = ['the %s is %s' %(i, hospital.get_dat(i)) for i in fts]
                msg = 'For %s: ' % hospital.get_dat('name') + ',  NL  '.join(vals)
                self.context.add_message(self, msg)

    def yield_msg(self, params=None):
        msg = self.context.get_node_messages(self)
        return msg[0] if msg else Message('')


def extract_find_hospital(utterance, slots, context, general=None):
    extracted = []
    has_req = any([i for i in slots if 'request' in i])
    problems = set()
    for name, value in slots.items():
        if 'request-' in name:
            continue
        value = select_value(value)
        if not name.startswith(HOSPITAL_PREFIX):
            problems.add(f"Slot {name} not mapped for find_hospital!")
            continue

        role = name[HOSPITAL_PREFIX_LENGTH:]
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
        if name == "hospital-department":
            if EXTRACT_SIMP:
                extracted.append(f"department={escape_string(value)}")
            else:
                extracted.append(f"department=LIKE(Department({escape_string(value)}))")
        else:
            problems.add(f"Slot {name} not mapped for find_hospital!")

    extracted_req = []
    if has_req:
        for name, value in slots.items():
            if 'request' in name:
                value = select_value(value)
                if not name.startswith(HOSPITAL_PREFIX + 'request-'):
                    problems.add(f"Slot {name} not mapped for find_hotel request!")
                    continue

                role = name[HOSPITAL_PREFIX_LENGTH+len('request-'):]
                if value in SPECIAL_VALUES:
                    extracted_req.append(f"{role}={SPECIAL_VALUES[value]}")
                    continue

                if role in ['department', 'phone']:
                    extracted_req.append(role)
                # todo - add other fields and check not a bad field name

    exps = get_extract_exps('Hospital', context, general, extracted, [], extracted_req)

    return exps, problems
