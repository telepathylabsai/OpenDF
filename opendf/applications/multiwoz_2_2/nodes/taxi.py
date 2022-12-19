from opendf.applications.multiwoz_2_2.nodes.multiwoz import *
from opendf.applications.multiwoz_2_2.utils import *
from opendf.graph.nodes.framework_functions import revise, duplicate_subgraph

node_fact = NodeFactory.get_instance()
environment_definitions = EnvironmentDefinition.get_instance()


# The Taxi domain is different from the other domains in that there are no real taxis the agent is searching over,
# instead, they are just invented as a combination of type, color, and phone number.


class Taxi(MultiWOZDomain):

    def __init__(self):
        super().__init__(Taxi)
        self.signature.add_sig('color', Color)
        self.signature.add_sig('type', TaxiType)
        self.signature.add_sig('phone', Phone)

        self.signature.add_sig('arriveby', Str)
        self.signature.add_sig('departure', Location)
        self.signature.add_sig('destination', Location)
        self.signature.add_sig('leaveat', [Str, Time])
        self.signature.add_sig('price', Float)
        self.signature.add_sig('bookday', Book_day)

    def get_context_values(self, inform_values=None, req_fields=None):
        slot_values = {}
        for name in self.inputs:
            element = []
            if name in {'arriveby', 'leaveat'}:
                node = next(filter(lambda x: x.typename() == "Time", self.input_view(name).topological_order()), None)
                if isinstance(node, Time):
                    p_time = node.to_Ptime()
                    element.append(f"{p_time.hour:02d}:{p_time.minute:02d}")
            else:
                node = next(filter(lambda x: x.typename() == "Str", self.input_view(name).topological_order()), None)
                if node:
                    element.append(node.dat)
            slot_values[f'taxi-{name.lower()}'] = element

        return slot_values

    def fallback_search(self, parent, all_nodes=None, goals=None, do_eval=True, params=None):
        nodes = self.collect_nodes(self.context.other_goals)
        matches = get_refer_match(self.context, nodes, self.context.other_goals, pos1=self, no_fallback=True)
        return matches

    def describe(self, params=None):
        prms = ['%s : %s' %(i, self.get_dat(i)) for i in self.inputs]
        return Message('Taxi reservation:  NL  ' + '  NL  '.join(prms))

    def collect_state(self):
        do_collect_state(self, 'taxi')


class FindTaxi(Node):
    def __init__(self):
        super().__init__(Taxi)
        self.signature.add_sig(posname(1), Taxi, alias='taxi')

    def exec(self, all_nodes=None, goals=None):
        context = self.context
        if posname(1) in self.inputs:
            taxi = self.inputs[posname(1)]
        else:
            taxi, _ = self.call_construct('Taxi?()', context)
            taxi.connect_in_out(posname(1), self)

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
                if dom=='Taxi':
                    if typ in ['Inform']:
                        for [k, v] in dact[d]:
                            inform_fields[k].append(v)
                    if typ == 'Request':
                        for [k, v] in dact[d]:
                            req_fields[k] = v

            if environment_definitions.oracle_only:
                # return the original message of the agent,
                #    but may need to change the result according to the agent's action
                #update_mwoz_state(taxi, context, inform_fields, req_fields)
                raise OracleException(atext, self, suggestions=sugg, objects=objs)

        dfields = [i for i in ['departure', 'destination'] if i not in taxi.inputs]
        if not any([i in taxi.inputs for i in ['leaveat', 'arriveby']]):
            dfields.append('leaveat')
        if not environment_definitions.agent_oracle or (len(req_fields)==0 and dfields):
            req_fields = {i: '?' for i in dfields[:2]}

        if len(inform_fields)>0 or len(req_fields)>0:
            msg = self.describe_inform_request(inform_fields, req_fields)
            #update_mwoz_state(taxi, context, inform_fields, req_fields)  # use inform_fields to update state
            if len(req_fields)>0:
                raise MultipleEntriesSingletonException(msg, self, suggestions=sugg, objects=objs)

            d, inform_fields = self.make_taxi_booking(inform_fields)
            self.set_result(d)
            self.context.add_message(self, msg)
            return

        # no inform fields, despite all info being provided ???
        #update_mwoz_state(taxi, context)  # update without inform fields
        raise ElementNotFoundException("I can not find a taxi right now. Maybe try later?", self)

    def make_taxi_booking(self, inform_fields):
        # all required inputs given by user, so we expect the agent has now provided booked taxi info
        for i in ['departure', 'destination', 'leaveat', 'arriveby']:
            if i not in inform_fields:
                inform_fields[i] = self.input_view('taxi').get_dat(i)

        if 'type' not in inform_fields:
            inform_fields['type'] = 'Pink Rolls Royce'
        if 'phone' not in inform_fields:
            inform_fields['phone'] = '12345678'
        prms = ['%s=%s' % (i, escape_string(to_list(inform_fields[i])[0])) for i in inform_fields if inform_fields[i] and i!='none']
        # if taxi description is missing - invent values
        d, e = self.call_construct('Taxi(' + ','.join(prms) + ')', self.context)
        return d, inform_fields

    def fallback_search(self, parent, all_nodes=None, goals=None, do_eval=True, params=None):
        top = [g for g in self.context.goals if g.typename()=='MwozConversation']
        if not top:
            top, _ = self.call_construct('MwozConversation()', self.context)
            self.context.add_goal(top)
        else:
            top = top[-1]
        s = id_sexp(self.inputs[posname(1)]) if posname(1) in self.inputs else 'taxi=Taxi?()'
        d, e = self.call_construct('FindTaxi(%s)' % s, self.context)
        top.add_task(d)
        parent.set_result(d)
        if do_eval:
            e = top.call_eval(add_goal=False)
            if e:
                raise e[0]
        return [d]

    def describe_inform_request(self, inform_fields, req_fields):
        prms = []

        infs = ['type', 'phone', 'color', 'price']
        found = any ([i in inform_fields for i in infs])
        if found:
            prms.append('I have booked a car for you.')
        for i in infs:
            if i in inform_fields and len(inform_fields[i])>0:
                prms.append('%s is %s' %(i, inform_fields[i][0]))

        dep = inform_fields.get('departure')
        if dep:
            prms.append('departure from  ' + and_values_str(dep))
        dest = inform_fields.get('destination')
        if dest:
            prms.append('Destination %s' % to_list(dest)[0])
        leave = inform_fields.get('leaveat')
        if leave:
            prms.append('Leaving at ' + to_list(leave)[0])
        arrive = inform_fields.get('arriveby')
        if arrive:
            prms.append('Arrive by ' + to_list(arrive)[0])

        if len(req_fields) > 0:
            prms.append('Can you tell me your desired ' + ' or '.join([i for i in req_fields]))

        msg = ', '.join(prms)
        return msg

    def collect_state(self):
        if self.result!=self:
            self.res.collect_state()
        elif 'taxi' in self.inputs:
            self.inputs['taxi'].collect_state()


class revise_taxi(revise):
    # make it a subtype of revise, so we don't revise this call
    def __init__(self):
        super().__init__()
        self.signature.add_sig('color', Color)
        self.signature.add_sig('type', TaxiType)
        self.signature.add_sig('phone', Phone)

        self.signature.add_sig('arriveby', Str)
        self.signature.add_sig('departure', Location)
        self.signature.add_sig('destination', Location)
        self.signature.add_sig('leaveat', [Str, Time])
        self.signature.add_sig('price', Float)
        self.signature.add_sig('bookday', Book_day)


    def valid_input(self):  # override the revise valid_input
        pass

    def exec(self, all_nodes=None, goals=None):
        # 1. raise or create task
        root = do_raise_task(self, 'FindTaxi') #  the top conversation

        # 2. do revise if requested fields given
        taxi_fields = ['color', 'type', 'phone', 'arriveby', 'departure', 'destination', 'leaveat', 'price', 'bookday']

        fields = [i for i in self.inputs if i in taxi_fields]
        if fields:
            nodes = root.topological_order(follow_res=False)
            find = [i for i in nodes if i.typename()=='FindTaxi']
            if find:  # should always be the case
                find = find[0]
                prms = ['%s=%s' % (i, id_sexp(self.inputs[i])) for i in fields]
                old = find.inputs['taxi']
                s = 'Taxi?(' + ','.join(prms) + ')'
                new, _ = self.call_construct(s, self.context)
                new_subgraph = duplicate_subgraph(root, old, new, 'overwrite', self)
                root = new_subgraph[-1]

        self.set_result(root)
        self.context.add_goal(root)  # will not add if already added before
        # root.call_eval()  # no need to call eval, since eval_res is True. is this what we want?


class get_taxi_info(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('taxi', Taxi)
        # self.signature.add_sig('feats', Node)
        self.signature.add_sig(POS, Str)


    def trans_simple(self, top):
        pnm, parent = self.get_parent()
        if parent.typename()!='side_task':
            if PERSIST_SIDE:
                parent.wrap_input(pnm, 'side_task(persist=True,task=', do_eval=False)
            else:
                parent.wrap_input(pnm, 'side_task(task=', do_eval=False)
            return parent, None
        return self, None

    def exec(self, all_nodes=None, goals=None):
        taxi = self.input_view('taxi')
        if not taxi:
            m = get_refer_match(self.context, all_nodes, goals, pos1='Taxi?()')
            if m:
                taxi = m[0]
            else:
                raise MissingValueException('taxi', self, 'I can give information only after we have selected one taxi')

        if taxi:
            fts = []
            fts += [self.input_view(i).dat for i in self.inputs if is_pos(i)]
            if fts:
                vals = ['the %s is %s' %(i, taxi.get_dat(i)) for i in fts]
                msg = 'The taxi:  NL  ' + ',  NL  '.join(vals)
                self.context.add_message(self, msg)

    def yield_msg(self, params=None):
        msg = self.context.get_node_messages(self)
        return msg[0] if msg else Message('')


def extract_find_taxi(utterance, slots, context=None, general=None):
    extracted = []
    problems = set()
    has_req = any([i for i in slots if 'request' in i])
    for name, value in slots.items():
        if 'request-' in name:
            continue
        value = select_value(value)
        if not name.startswith(TAXI_PREFIX):
            problems.add(f"Slot {name} not mapped for find_taxi!")
            continue

        role = name[TAXI_PREFIX_LENGTH:]
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
        if name == "taxi-departure":
            if EXTRACT_SIMP:
                extracted.append(f"departure={escape_string(value)}")
            else:
                extracted.append(f"departure=Location({escape_string(value)})")
        elif name == "taxi-destination":
            if EXTRACT_SIMP:
                extracted.append(f"destination={escape_string(value)}")
            else:
                extracted.append(f"destination=Location({escape_string(value)})")
        elif name == "taxi-bookday":
            extracted.append(f"bookday={escape_string(value)}")
        elif name == "taxi-arriveby":
            extracted.append(f"arriveby={escape_string(value)}")
        elif name == "taxi-leaveat":
            extracted.append(f"leaveat={escape_string(value)}")
        elif name == "taxi-price":
            value = value.replace("pounds", "").replace("pound", "").strip()
            extracted.append(f"price={value}")
        else:
            problems.add(f"Slot {name} not mapped for find_taxi!")

    extracted_req = []
    if has_req:
        for name, value in slots.items():
            if 'request' in name:
                value = select_value(value)
                if not name.startswith(TAXI_PREFIX + 'request-'):
                    problems.add(f"Slot {name} not mapped for find_hotel request!")
                    continue

                role = name[TAXI_PREFIX_LENGTH+len('request-'):]
                if value in SPECIAL_VALUES:
                    extracted_req.append(f"{role}={SPECIAL_VALUES[value]}")
                    continue

                if role in ['departure', 'destination', 'leaveat', 'arriveby', 'type', 'color', 'price', 'phone']:
                    extracted_req.append(role)
                # todo - add other fields and check not a bad field name

    exps = get_extract_exps('Taxi', context, general, extracted, [], extracted_req)

    return exps, problems
