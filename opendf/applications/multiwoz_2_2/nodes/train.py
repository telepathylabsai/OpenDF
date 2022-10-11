from opendf.applications.multiwoz_2_2.nodes.multiwoz import *
from opendf.applications.multiwoz_2_2.utils import *
from opendf.graph.nodes.framework_functions import revise, duplicate_subgraph

if use_database:
    multiwoz_db = MultiWozSqlDB.get_instance()
else:
    multiwoz_db = MultiWOZDB.get_instance()
node_fact = NodeFactory.get_instance()
environment_definitions = EnvironmentDefinition.get_instance()


class Train(MultiWOZDomain):

    def __init__(self, typ=None):
        typ = typ if typ else type(self)
        super().__init__(typ)
        self.signature.add_sig('departure', Location)
        self.signature.add_sig('destination', Location)
        self.signature.add_sig('leaveat', MWOZTime)
        self.signature.add_sig('arriveby', MWOZTime)
        self.signature.add_sig('day', Str)
        # the fields below come from the system
        self.signature.add_sig('duration', Duration)
        self.signature.add_sig('price', Float)
        self.signature.add_sig('trainid', TrainID)

    def get_context_values(self, inform_values=None, req_fields=None):
        slot_values = {}
        for name in self.inputs:
            element = []
            if name in {'arriveby', 'leaveat'}:
                node = next(filter(lambda x: x.typename() in {"Time", "MWOZTime"}, self.input_view(name).topological_order()), None)
                if isinstance(node, Time):
                    p_time = node.to_Ptime()
                    element.append(f"{p_time.hour:02d}:{p_time.minute:02d}")
                elif isinstance(node, MWOZTime):
                    time_str = node.get_dat(posname(1)).split()[-1]
                    match = TIME_REGEX.match(time_str)
                    if match is None:
                        hour, minute = 0, 0  # problem
                    else:
                        hour, minute = match.groups()
                    element.append(f"{int(hour) % 24:02d}:{int(minute) % 60:02d}")
            else:
                node = next(filter(lambda x: x.typename() == "Str", self.input_view(name).topological_order()), None)
                if node:
                    element.append(node.dat)
            slot_values[f'train-{name.lower()}'] = element

        return slot_values

    def generate_sql_select(self):
        return select(MultiWozSqlDB.TRAIN_TABLE)

    def generate_sql_where(self, selection, parent_id, **kwargs):
        if 'arriveby' in self.inputs:
            selection = self.input_view("arriveby").generate_sql_where(
                selection, MultiWozSqlDB.TRAIN_TABLE.columns.arriveby, **kwargs)

        if 'day' in self.inputs:
            selection = self.input_view("day").generate_sql_where(
                selection, MultiWozSqlDB.TRAIN_TABLE.columns.day, **kwargs)

        if 'departure' in self.inputs:
            selection = self.input_view("departure").generate_sql_where(
                selection, MultiWozSqlDB.TRAIN_TABLE.columns.departure, **kwargs)

        if 'destination' in self.inputs:
            selection = self.input_view("destination").generate_sql_where(
                selection, MultiWozSqlDB.TRAIN_TABLE.columns.destination, **kwargs)

        if 'duration' in self.inputs:
            selection = self.input_view("duration").generate_sql_where(
                selection, MultiWozSqlDB.TRAIN_TABLE.columns.duration, **kwargs)

        if 'leaveat' in self.inputs:
            selection = self.input_view("leaveat").generate_sql_where(
                selection, MultiWozSqlDB.TRAIN_TABLE.columns.leaveat, **kwargs)

        if 'price' in self.inputs:
            selection = self.input_view("price").generate_sql_where(
                selection, MultiWozSqlDB.TRAIN_TABLE.columns.price, **kwargs)

        if 'trainid' in self.inputs:
            selection = self.input_view("trainid").generate_sql_where(
                selection, MultiWozSqlDB.TRAIN_TABLE.columns.trainid, **kwargs)

        return selection

    def graph_from_row(self, row, context):
        params = []
        for field in self.signature.keys():
            value = row[field]
            if value and field in ['leaveat', 'arriveby']:
                s = str(value).split()[1].split(':')
                value = ':'.join(s[:2])
            if value:
                if isinstance(value, str):
                    value = escape_string(value)
                params.append(f"{field}={value}")

        node_str = f"Train({', '.join(params)})"
        g, _ = Node.call_construct_eval(node_str, context, constr_tag=NODE_COLOR_DB)
        g.tags[DB_NODE_TAG] = 0
        return g

    def describe(self, params=None):
        prms = []
        dep, dest, leave, arr, day, dur, price, tid = \
            self.get_dats(['departure', 'destination', 'leaveat', 'arriveby', 'day', 'duration', 'price', 'trainid'])
        prms.append(tid if tid else 'the train')
        if dep:
            prms.append('from %s' % dep)
        if dest:
            prms.append('to %s' % dest)
        if day:
            prms.append('on %s' % day)
        if leave:
            prms.append('leaves at %s' % leave)
        if arr:
            prms.append('arrives at %s' % arr)
        if price:
            prms.append('costs %s' % price)
        return Message(', '.join(prms), objects=[self])

    def getattr_yield_msg(self, attr, val=None, plural=None, params=None):
        return self.describe(params=params)

    def collect_state(self):
        do_collect_state(self, 'train')


###################################################################


class TrainBookInfo(Node):
    def __init__(self):
        super().__init__(type(self))
        #self.signature.add_sig('bookstay', Book_stay)
        self.signature.add_sig('bookpeople', Book_people)
        #self.signature.add_sig('bookday', Book_day)

    def get_context_values(self, inform_values=None, req_fields=None):
        slot_values = {}
        for name in self.inputs:
            element = next(filter(lambda x: x.typename() == "Str", self.input_view(name).topological_order()), None)
            #name = 'book' + name[5:] if name.startswith('book_') else name
            slot_values[f'train-{name}'] = [element.dat] if element else []
        if inform_values:
            for k in inform_values:
                slot_values['train-'+k] = inform_values[k]
        return slot_values

    def collect_state(self):
        do_collect_state(self, 'train', 'book')


class BookTrainConfirmation(Node):
    def __init__(self):
        super().__init__(type(self))
        self.signature.add_sig('train', Train)
        self.signature.add_sig('book_info', TrainBookInfo)
        self.signature.add_sig('conf_code', Str)

    def describe(self, params=None):
        s = ['Train resevation: ']
        m1 = self.input_view('train').describe(params=['compact'])
        m2 = self.input_view('book_info').describe()
        s.append(m1.text)
        s.append(m2.text)
        s.append('Confirmation code: ' + self.get_dat('conf_code'))
        return Message('  NL  '.join(s), objects=m1.objects+m2.objects)

    def collect_state(self):
        self.inputs['train'].collect_state()
        self.inputs['book_info'].collect_state()
        do_collect_state(self, 'train', 'book')  # add conf code directly


def check_train_availability(train, binf, book_fields):
    if environment_definitions.agent_oracle:
        if 'ref' in book_fields:
            return True, book_fields['ref']
        if 'nobook' in book_fields:
            return False, None
    return True, 'XYZ%12345'  #  % random.randint(1000000, 9000000)


class BookTrain(Node):
    def __init__(self):
        super().__init__(BookTrainConfirmation)
        self.signature.add_sig('train', Train)
        self.signature.add_sig('book_info', TrainBookInfo)
        # maybe wrap the book info inputs into a node?
        self.inc_count('max_inform_tid', 1)

    # todo - add agent_oracle mode!
    def exec(self, all_nodes=None, goals=None):
        #self.update_mwoz_state()

        if 'train' not in self.inputs:
            raise MissingValueException('Please specify which train you are looking for', self)
        train = self.input_view('train')
        context = self.context

        # maybe: in case of failed booking, then inform what needs to change? todo
        fields = ['bookpeople', 'ref']
        inform_fields = {}
        req_fields = {}
        book_fields = {}
        if environment_definitions.agent_oracle:
            dact = context.agent_turn['dialog_act']['dialog_act']
            atext = context.agent_turn['utterance']
            # 1. try to understand what the agent did -
            for d in dact:
                dom, typ = d.split('-')
                if dom=='xxBooking':
                    pass  # todo
                elif dom=='Train' or dom=='Booking':
                    if typ == 'Inform':
                        for [k, v] in dact[d]:
                            if k in fields:
                                inform_fields[k] = v
                    if typ in ['Book', 'OfferBooked']:
                        for [k, v] in dact[d]:
                            if k in fields:
                                book_fields[k] = v
                    if typ == 'NoBook':
                        book_fields['nobook'] = 'True'
                    if typ == 'Request':
                        for [k, v] in dact[d]:
                            if k in fields:
                                req_fields[k] = v

            if environment_definitions.oracle_only:
                # return the original message of the agent,
                #self.update_mwoz_state(inform_fields, req_fields)
                raise OracleException(atext, self)

        msg = ''
        if self.count_ok('inform_tid'):
            self.inc_count('inform_tid')
            msg = 'OK, ' + train.describe().text + '.  NL  '
        if 'book_info' not in self.inputs:  # should not be the case when using the "normal" initialization (fallback search)
            d, e = self.call_construct('TrainBookInfo()', self.context)
            d.connect_in_out('book_info', self)
        binf = self.inputs['book_info']
        if 'bookpeople' not in binf.inputs:
            raise MissingValueException(msg+'For how many people?', self)
        # if 'bookday' not in binf.inputs:
        #     raise MissingValueException(msg+'On which day?', self)
        ok, conf_code = check_train_availability(train, binf, book_fields)
        #self.update_mwoz_state(inform_fields, req_fields)
        if ok:
            d, e = self.call_construct_eval('BookTrainConfirmation(train=%s, book_info=%s, conf_code=%s)' %
                                            (id_sexp(train), id_sexp(binf), conf_code), self.context)
            self.set_result(d)
            self.context.add_message(self, 'I have made the reservation as requested. confirmation ref %s' % conf_code)
        else:
            # todo - if oracle - say what failed / what is needed
            raise InvalidInputException('Unfortunately the train can not confirm this booking.    NL  Maybe try another day or length of stay?', self)

    def collect_state(self):
        if self.result != self:
            self.res.collect_state()
        else:
            self.inputs['train'].collect_state()
            self.inputs['book_info'].collect_state()


class FindTrain(Node):
    def __init__(self):
        super().__init__(Train)
        self.signature.add_sig(posname(1), Train, alias='train')

    def exec(self, all_nodes=None, goals=None):
        context = self.context
        if posname(1) in self.inputs:
            train = self.inputs[posname(1)]
        else:
            train, _ = self.call_construct('Train?()', context)
            train.connect_in_out(posname(1), self)

        results = results0 = multiwoz_db.find_elements_that_match(train, train.context)
        nresults = nresults0 = len(results)

        # update_mwoz_state(train, context)   # initial state from last turn / prev pexp in this turn
        self.filter_and_set_result(results)  # initially set result to single result, if single, or don't

        inform_fields = defaultdict(list)
        req_fields = {}
        rec_field = None
        sugg = None
        objs = None
        if environment_definitions.agent_oracle:
            dact = context.agent_turn['dialog_act']['dialog_act']
            atext = context.agent_turn['utterance']
            # 1. try to understand what the agent did -
            for d in dact:
                dom, typ = d.split('-')
                if dom=='Booking':
                    if typ=='Book':
                        for [k, v] in dact[d]:
                            if k=='name':
                                inform_fields['book_name'].append(v)
                elif dom=='Train':
                    if typ in ['Inform']:
                        for [k, v] in dact[d]:
                            inform_fields[k].append(v)
                    if typ == 'Request':
                        for [k, v] in dact[d]:
                            req_fields[k] = v

            # for train - recommending by time  - either leave or arrive
            if nresults>1:
                for i in ['trainid', 'leaveat', 'arriveby']:
                    if not rec_field and i in inform_fields and len(to_list(inform_fields[i]))==1:
                        rec_field = i

            # TODO - if accepting recommendation from agent for leave/arrive time, the it means that EXACT time,
            #        not like the input from user, which is interpreted as LE / GE !
            if rec_field:
                v = inform_fields[rec_field][0]
                r = self.filter_and_set_result(results, rec_field, v, inform_fields)
                if r:
                    results = r
                    nresults = len(results)
                # results should not be empty - unless the agent made a mistake
                sugg = self.mod_train_field_and_suggest_neg(train, rec_field, v, inform_fields)
                #update_mwoz_state(train, context, inform_fields, req_fields)

            if environment_definitions.oracle_only:
                # return the original message of the agent,
                #    but may need to change the result according to the agent's action
                #update_mwoz_state(train, context, inform_fields, req_fields)
                raise OracleException(atext, self, suggestions=sugg, objects=objs)

        if not environment_definitions.agent_oracle:
            # todo - add logic to recommend first/last train (depending on user request specifying leave or arrive)
            if nresults > 1 and not rec_field:
                dfields = get_diff_fields(results0, ['departure', 'destination', 'leaveat', 'arriveby', 'day'])
                if len(dfields)>0:
                    for f in list(dfields.keys())[:2]:
                        req_fields[f] = '?'

        org_inform_fields = {i:inform_fields[i] for i in inform_fields}
        if len(inform_fields)>0 or len(req_fields)>0:
            if rec_field and not sugg:
                v = inform_fields[rec_field][0]
                r = self.filter_and_set_result(results, rec_field, v, org_inform_fields)
                results = r if r else results
                nresults = len(results)
                sugg = self.mod_train_field_and_suggest_neg(train, rec_field, v, org_inform_fields)

            for f in ['departure', 'destination', 'leaveat', 'arriveby', 'day', 'duration', 'price', 'trainid']:
                if f in inform_fields:
                    inform_fields[f] = collect_values(results0, f)

            if not rec_field or req_fields:
                if len(req_fields)==0 and not environment_definitions.agent_oracle and nresults>2:
                    dfields = get_diff_fields(results, ['departure', 'destination', 'leaveat', 'arriveby', 'day'])
                    if dfields:
                        req_fields = {i:'?' for i in list(dfields.keys())[:2]}

            msg = self.describe_inform_request(nresults0, inform_fields, req_fields, rec_field, org_inform_fields)

            #update_mwoz_state(train, context, inform_fields, req_fields)  # use inform_fields to update state
            if nresults!=1 or rec_field:
                raise OracleException(msg, self, suggestions=sugg, objects=objs)
            else:
                self.context.add_message(self, msg)

        # no inform fields
        #update_mwoz_state(train, context)  # update without inform fields
        if nresults == 0:
            raise ElementNotFoundException(
                "I can not find a matching train in the database. Maybe another area or price range?", self)
        if nresults > 1:
            diffs = ' or '.join(list(inform_fields.keys())[:2])
            if diffs:
                msg = 'Multiple (%d) matches found. Maybe select  %s?' % (nresults, diffs)
            else:
                msg = 'Multiple (%d) matches found. Can you be more specific?' % nresults
            raise MultipleEntriesSingletonException(msg, self, suggestions=sugg, objects=objs)

        # if nresults==1 : success, do nothing

    def fallback_search(self, parent, all_nodes=None, goals=None, do_eval=True, params=None):
        top = [g for g in self.context.goals if g.typename()=='MwozConversation']
        if not top:
            top, _ = self.call_construct('MwozConversation()', self.context)
            self.context.add_goal(top)
        else:
            top = top[-1]
        s = '' if posname(1) in self.inputs else 'Train?()'
        d, e = self.call_construct('BookTrain(train=FindTrain(%s), book_info=TrainBookInfo())' % s, self.context)
        if posname(1) in self.inputs:
            find = d.inputs['train']
            self.inputs[posname(1)].connect_in_out(posname(1), find)
        top.add_task(d)
        h = d.inputs['train']
        parent.set_result(h)
        if do_eval:
            e = top.call_eval(add_goal=False)
            if e:
                raise e[0]
        return [h]

    # suggest a train with the newly suggested  trainid / leaveat / arriveby
    # if reject - restore ALL original values
    def mod_train_field_and_suggest_neg(self, constr, field, v, inform_fields):
        prms = []
        for i in ['trainid', 'leaveat', 'arriveby']:
            if i in inform_fields and len(inform_fields[i]) == 1:
                t = 'TrainID' if i == 'trainid' else 'MWOZTime'
                v = escape_string(inform_fields[i][0])
                old_v = constr.get_dat(i)
                p = '%s=%s(%s)' %(i, t, old_v) if old_v else '%s=Clear()' % t
                prms.append(p)
                d, e = constr.call_construct('%s(%s)' %(t, v), constr.context)
                constr.replace_input(i, d)
        return ['revise(old=Train??(), newMode=overwrite, new=Train?(%s))' % ','.join(prms),
                'side_task(task=no_op())']

    def filter_and_set_result(self, results, field=None, val=None, inform_fields=None):
        if field:
            pp = {}
            rerun_db_search = True
            if rerun_db_search:  # we limit the number of results returned from the DB. need to run a search again
                train = self.input_view(posname(1))
                if train:
                    pp = {i: id_sexp(train.input_view(i)) for i in train.inputs}
            for i in ['trainid', 'leaveat', 'arriveby']:
                if i in inform_fields and len(inform_fields[i]) == 1:
                    t = 'TrainID' if i == 'trainid' else 'MWOZTime'
                    v = inform_fields[i][0]
                    s = '%s(%s)' % (t, escape_string(v))
                    pp[i] = s

            prms = ['%s=%s' %(i, pp[i]) for i in pp]
            s = 'Train?(%s)' % ','.join(prms)
            print(s)
            f, _ = self.call_construct(s, self.context)
            if rerun_db_search:
                results = multiwoz_db.find_elements_that_match(f, self.context)
            else:
                results = [r for r in results if f.match(r)]
            # for now, we do a hack for time - this is necessary due to the different meanings of time
            #  depending on user/agent   (solution - return to explicitly using EQ / LE / GE as before)
            for i in ['leaveat', 'arriveby']:
                if i in inform_fields and len(inform_fields[i]) == 1:
                    v = inform_fields[i][0]
                    results = [r for r in results if r.get_dat(i)==v]
        if len(results)==1:
            self.set_result(results[0])
            results[0].call_eval(add_goal=False)  # not necessary, but adds color
        return results

    def describe_inform_request(self, nresults0, inform_fields, req_fields, rec_field, org_inform_fields):
        dep = inform_fields.get('departure')
        dest = inform_fields.get('destination')
        leave = inform_fields.get('leaveat')
        arr = inform_fields.get('arriveby')
        day = inform_fields.get('day')
        dur = inform_fields.get('duration')
        price = inform_fields.get('price')
        tid = inform_fields.get('trainid')

        prms = []
        if tid and len(to_list(tid))<3:
            prms.append('I have found ' + and_values_str(tid))

        if 'choice' in inform_fields:
            inform_fields['choice'] = [nresults0]
        choice = inform_fields.get('choice')
        if choice:
            prms.append('There are %d matching results' % nresults0)
        elif nresults0 > 1:
            prms.append('I see several (%d) matches' % nresults0)

        if dep and len(to_list(dep))<4:
            prms.append('leaving from  ' + and_values_str(dep))
        if dest  and len(to_list(dest))<4:
            prms.append('going to  ' + and_values_str(dest))
        if leave and len(to_list(leave))<3:
            prms.append('leaving at  ' + and_values_str(leave))
        if day and len(to_list(day))<3:
            prms.append('on  ' + and_values_str(day))
        if arr and len(to_list(arr))<3:
            prms.append('arriving at  ' + and_values_str(arr))
        if price and len(to_list(price))<3:
            prms.append('costs  ' + and_values_str(price))

        if rec_field:
            s = 'I recommend:' + ('' if 'trainid' in org_inform_fields else 'the train ')
            prms.append(s)
            for i in ['trainid', 'leaveat', 'arriveby']:
                if i in org_inform_fields:
                    v = org_inform_fields[i][0]
                    t = 'leaving at ' if i=='leaveat' else 'arriving at ' if i=='arriveby' else ''
                    prms.append('%s%s' % (t,v))

        # if 'book_name' in inform_fields:
        #     prms.append('I Have booked %s' % inform_fields['book_name'][0])
        if len(req_fields) > 0:
            if nresults0 > 0:
                prms.append('maybe select %s' % ' or '.join([i for i in req_fields]))
            else:
                prms.append('Sorry, I can\'t find a match. Try a different %s' % ' or '.join([i for i in req_fields]))
        msg = ', '.join(prms)
        return msg

    # if we revise a train constraint which already has a train name with a non-name constraint, then drop the name.
    #    e.g. user: "I want to book train X", Agent: "train X is ... and has no parking". User: "I want parking"
    #    also if agent made a suggestion (which was implicitly accepted) - since we don't have explicit RejectSuggestion
    #    we need this implicit reject
    def on_duplicate(self, dup_tree=False):
        # old = self.dup_of.input_view('train')
        old = self.dup_of.res if self.dup_of.res != self.dup_of else self.dup_of.input_view('train')
        curr = self.input_view('train')
        if 'trainid' in old.inputs and 'trainid' in curr.inputs:
            changed = any([old.get_dat(i)!=curr.get_dat(i) and curr.get_dat(i) is not None
                           for i in ['departure', 'destination', 'leaveat', 'arriveby', 'day', 'duration']])
            if changed:
                curr.disconnect_input('trainid')
        return self

    def collect_state(self):
        if self.result!=self:
            self.res.collect_state()
        elif 'train' in self.inputs:
            self.inputs['train'].collect_state()


class revise_train(revise):
    # make it a subtype of revise, so we don't revise this call
    def __init__(self):
        super().__init__()
        # for the hotel
        self.signature.add_sig('departure', Location)
        self.signature.add_sig('destination', Location)
        self.signature.add_sig('leaveat', MWOZTime)
        self.signature.add_sig('arriveby', MWOZTime)
        self.signature.add_sig('day', Str)
        # the fields below come from the system
        self.signature.add_sig('duration', Duration)
        self.signature.add_sig('price', Float)
        self.signature.add_sig('trainid', TrainID)
        # book field
        self.signature.add_sig('bookpeople', Book_people)

    def valid_input(self):  # override the revise valid_input
        pass

    def trans_simple(self, top):
        leave, arrive, dur = self.get_input_views(['leaveat', 'arriveby', 'duration'])
        if leave and leave.typename()=='MWOZTime':
            self.wrap_input('leaveat', 'GE(')
        if arrive and arrive.typename()=='MWOZTime':
            self.wrap_input('arriveby', 'LE(')
        if dur and dur.typename()=='Duration':
            self.wrap_input('duration', 'LIKE(')
        return self, None

    def exec(self, all_nodes=None, goals=None):
        # 1. raise or create task
        root = do_raise_task(self, 'FindTrain') #  the top conversation

        # 2. do revise if requested fields given
        train_fields = ['departure', 'destination', 'leaveat', 'arriveby', 'day', 'duration', 'price', 'trainid']
        book_fields = ['bookpeople']
        fields = {'train': [i for i in self.inputs if i in train_fields],
                  'book': [i for i in self.inputs if i in book_fields]}
        for f in fields:
            if fields[f]:
                nodes = root.topological_order(follow_res=False)
                book = [i for i in nodes if i.typename()=='BookTrain']
                if book:  # should always be the case
                    book = book[0]
                    prms = ['%s=%s' % (i, id_sexp(self.inputs[i])) for i in fields[f]]
                    # we know exactly what root/old/new should be, so no need to use the search mechanism of the
                    #   'revise' node - instead we can directly call duplicate_subgraph to create the revised graph
                    if f=='train':
                        old = book.inputs['train'].inputs['train']
                        s = 'Train?(' + ','.join(prms) + ')'
                    else:  # book info
                        old = book.inputs['book_info']
                        s = 'TrainBookInfo(' + ','.join(prms) + ')'
                    new, _ = self.call_construct(s, self.context)
                    new_subgraph = duplicate_subgraph(root, old, new, 'overwrite', self)
                    root = new_subgraph[-1]

        self.set_result(root)
        self.context.add_goal(root)  # will not add if already added before
        # root.call_eval()  # no need to call eval, since eval_res is True. is this what we want?


# use this node is for debugging - replace the "proactive" train recommendation by the agent
# implement recommendation as a suggestion with implicit accept
class suggest_train(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig(posname(1), Str)

    def exec(self, all_nodes=None, goals=None):
        if posname(1) in self.inputs:
            nm = self.get_dat(posname(1))
            suggs = ['no_op()',
                     SUGG_IMPL_AGR + 'revise(old=Train??(), newMode=overwrite, new=Train?(trainid=%s))' % nm]
            raise OracleException('How about %s?' % nm, self, suggestions=suggs)


class get_train_info(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('train', Train)
        #self.signature.add_sig('feats', Node)
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
        train = self.input_view('train')
        if not train:
            m = get_refer_match(self.context, all_nodes, goals, pos1='Train?()')
            if m:
                train = m[0]
            else:
                raise MissingValueException('I can give information only after we have selected one train', self)

        if train:
            fts = []
            fts += [self.input_view(i).dat for i in self.inputs if is_pos(i)]
            if fts:
                vals = ['the %s is %s' %(i, train.get_dat(i)) for i in fts]
                msg = 'For %s: ' % train.get_dat('trainid') + ',  NL  '.join(vals)
                self.context.add_message(self, msg)

    def yield_msg(self, params=None):
        msg = self.context.get_node_messages(self)
        return msg[0] if msg else Message('')


################################################################################################################


# TODO: how do we treat multiple possible values? Check if any is in the input?
#  Check if we can find any by refer?
def extract_find_train(utterance, slots, context, general=None):
    extracted = []
    extracted_book = []
    problems = set()
    slots = fix_inform_request(slots)
    has_req = any([i for i in slots if 'request' in i])
    for name, value in slots.items():
        value = select_value(value)

        if not name.startswith(TRAIN_PREFIX) or 'request' in name:
            if 'request' not in name:
                problems.add(f"Slot {name} not mapped for find_train!")
            continue

        role = name[TRAIN_PREFIX_LENGTH:]
        if value in SPECIAL_VALUES:
            if role in {'bookpeople', 'booktime'}:
                extracted_book.append(f"{role}={SPECIAL_VALUES[value]}")
            else:
                extracted.append(f"{role}={SPECIAL_VALUES[value]}")
            continue

        if context and value not in utterance:
            references = get_refer_match(context, Node.collect_nodes(context.goals), context.goals,
                                         role=role, params={'fallback_type':'SearchCompleted', 'role': role})
            if references and references[0].dat == value:
                if role in {'bookpeople', 'booktime'}:
                    extracted_book.append(f"{role}=refer(role={role})")
                else:
                    extracted.append(f"{role}=refer(role={role})")
                continue
            # else:
            # TODO: maybe log that the reference could not be found in the graph

        if name == "train-departure":
            if EXTRACT_SIMP:
                extracted.append(f"departure={escape_string(value)}")
            else:
                extracted.append(f"departure=LIKE(Location({escape_string(value)}))")
        elif name == "train-destination":
            if EXTRACT_SIMP:
                extracted.append(f"destination={escape_string(value)}")
            else:
                extracted.append(f"destination=LIKE(Location({escape_string(value)}))")
        elif name == "train-duration":
            if EXTRACT_SIMP:
                extracted.append(f"duration={escape_string(value)}")
            else:
                extracted.append(f"duration=LIKE(Duration({escape_string(value)}))")
        elif name == "train-day":
            extracted.append(f"day={escape_string(value)}")
        elif name == "train-arriveby":
            if EXTRACT_SIMP:
                extracted.append(f"arriveby={escape_string(value)}")
            else:
                extracted.append(f"arriveby=ArriveBy({escape_string(value)})")
        elif name == "train-leaveat":
            if EXTRACT_SIMP:
                extracted.append(f"leaveat={escape_string(value)}")
            else:
                extracted.append(f"leaveat=LeaveAt({escape_string(value)})")
        elif name == "train-price":
            value = value.replace("pounds", "").replace("pound", "").strip()
            extracted.append(f"price={value}")
        elif name == "train-bookpeople":
            extracted_book.append(f"bookpeople={escape_string(value)}")
        elif name == "train-booktime":
            extracted_book.append(f"booktime={escape_string(value)}")
        else:
            problems.add(f"Slot {name} not mapped for book_train!")

    extracted_req = []
    if has_req:
        for name, value in slots.items():
            if 'request' in name:
                if not name.startswith(TRAIN_PREFIX + 'request-'):
                    problems.add(f"Slot {name} not mapped for find_train request!")
                    continue

                role = name[TRAIN_PREFIX_LENGTH+len('request-'):]
                if role in ['departure', 'destination', 'leaveat', 'arriveby', 'day', 'duration', 'price', 'trainid']:
                    extracted_req.append(role)
                # todo - add other fields and check not a bad field name

    exps = get_extract_exps('Train', context, general, extracted, extracted_book, extracted_req)

    return exps, problems







