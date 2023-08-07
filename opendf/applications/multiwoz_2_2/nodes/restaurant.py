import random

from opendf.applications.multiwoz_2_2.nodes.multiwoz import *
from opendf.applications.multiwoz_2_2.utils import *
from opendf.graph.nodes.framework_functions import revise, duplicate_subgraph
from opendf.utils.utils import Message

if use_database:
    multiwoz_db = MultiWozSqlDB.get_instance()
else:
    multiwoz_db = MultiWOZDB.get_instance()
node_fact = NodeFactory.get_instance()
environment_definitions = EnvironmentDefinition.get_instance()

map_restaurant_slots = {
    "restaurant-food": "food=%s",
    "restaurant-type": "type=%s",
    "restaurant-area": "area=%s",
    "restaurant-pricerange": "pricerange=%s",
    "restaurant-address": "address=%s",
    "restaurant-phone": "phone=%s",
    "restaurant-postcode": "postcode=%s",
    "restaurant-booktime": "booktime=%s",
    "restaurant-bookpeople": "bookpeople=%s",
    "restaurant-bookday": "bookday=%s",
    "restaurant-name": "name=%s" if EXTRACT_SIMP else "name=LIKE(Name(%s))",
    "restaurant-parking": "parking=%s",
}

map_restaurant_inputs = {
    "food": 'serving %s food',
    "type": 'of type %s',
    "area": 'in the %s',
    "pricerange": 'in the %s range',
    "address": 'at %s',
    "phone": 'phone number %s',
    "postcode": 'post code %s',
    "booktime": 'at %s',
    "bookpeople": 'for %s people',
    "bookday": 'on %s',
    "name": 'called %s',
    "parking": 'parking: %s',
}


class Restaurant(MultiWOZDomain):
    def __init__(self, typ=None):
        typ = typ if typ else type(self)
        super().__init__(typ)
        self.signature.add_sig('name', Name)
        self.signature.add_sig('food', Food)
        self.signature.add_sig('type', Type)
        self.signature.add_sig('area', Area)
        self.signature.add_sig('pricerange', Pricerange)

        self.signature.add_sig('address', Address)
        self.signature.add_sig('phone', Phone)
        self.signature.add_sig('postcode', Postcode)

    @staticmethod
    def gen_get_field_str_format(name, prms=None):
        return gen_get_field_str_format(name, map_restaurant_inputs)

    def gen_show_options(self):
        return ['name', 'food', 'type', 'area', 'pricerange', 'address', 'phone', 'postcode']

    @staticmethod
    def gen_get_alternative_values(name, prms=None):
        if name=='name':
            return ['city stop', 'la cucina', 'el sombrero']
        if name=='food':
            return ['mexican', 'japanese', 'italian', 'french']
        if name=='type':
            return ['restaurant', 'bar', 'pub']
        if name=='area':
            return ['north', 'south', 'west', 'east', 'center']
        if name=='pricerange':
            return ['cheap', 'moderate', 'expensive']
        return []

    def get_context_values(self, inform_values=None, req_fields=None):
        slot_values = {}
        for name in self.inputs:
            element = next(filter(lambda x: x.typename() == "Str", self.input_view(name).topological_order()), None)
            slot_values[f'restaurant-{name.lower()}'] = [element.dat] if element else []

        return slot_values

    # def describe(self, params=None):
    #     prms = []
    #     address, area, food, post, name, pricerange, phone, typ = \
    #         self.get_dats(['address', 'area', 'food', 'postcode', 'name', 'pricerange', 'phone', 'type'])
    #     prms.append(name if name else 'the ' + type if type else 'the restaurant')
    #     if food:
    #         prms.append('serves %s food' % food)
    #     if area:
    #         prms.append('in the %s' % area)
    #     if pricerange:
    #         prms.append('%s price range' % pricerange)
    #     if typ:
    #         prms.append('is a %s' % typ)
    #     if address:
    #         prms.append('and is located at %s' % address)
    #     return Message(', '.join(prms), objects=[self])

    def describe(self, params=None):
        prms = []
        name, typ = self.get_dats(['name', 'type'])
        prms.append(name if name else 'the ' + type if type else 'the restaurant')
        for i in ['food', 'area', 'pricerange', 'type', 'address']:
            dt = self.get_dat(i)
            if dt:
                prms.append(map_restaurant_inputs[i] % dt)
        return Message(', '.join(prms), objects=[self])

    # def getattr_yield_msg(self, attr, val=None, plural=None, params=None):
    #     nm = self.get_dat('name')
    #     msg = nm if nm else 'The restaurant'
    #     if attr == 'food':
    #         return Message(msg + ' serves %s.' % self.get_dat('food'))
    #     if attr == 'type':
    #         return Message(msg + ' as a %s.' % self.get_dat('type'))
    #     if attr == 'phone':
    #         return Message(msg + "'s phone number is  %s ." % self.get_dat('phone'))
    #     if attr == 'pricerange':
    #         return Message(msg + ' is %s .' % self.get_dat('pricerange'))
    #     if attr == 'area':
    #         return Message(msg + ' is in the %s .' % self.get_dat('area'))
    #     if attr == 'postcode':
    #         return Message(msg + "'s post code is  %s ." % self.get_dat('postcode'))
    #     return Message('')

    def getattr_yield_msg(self, attr, val=None, plural=None, params=None):
        nm = self.get_dat('name')
        msg = nm if nm else 'The restaurant'
        if attr in ['food', 'type', 'phone', 'pricerange', 'area', 'postcode']:
            return Message(msg + map_restaurant_inputs[attr] % self.get_dat(attr))
        return Message('')

    @staticmethod
    def do_fallback_search(node, parent, all_nodes=None, goals=None, do_eval=True, params=None):
        return multiwoz_db.find_elements_that_match(node, node.context)

    # disabled fallback_search  - do we need it??

    def generate_sql_select(self):
        return select(MultiWozSqlDB.RESTAURANT_TABLE)

    def generate_sql_where(self, selection, parent_id, **kwargs):
        if 'name' in self.inputs:
            kwargs['exclude_words'] = ['restaurant']  # do not include these words in the query (reduce db hits)
            selection = self.input_view("name").generate_sql_where(
                selection, MultiWozSqlDB.RESTAURANT_TABLE.columns.name, **kwargs)
            del kwargs['exclude_words']

        if 'area' in self.inputs:
            selection = self.input_view("area").generate_sql_where(
                selection, MultiWozSqlDB.RESTAURANT_TABLE.columns.area, **kwargs)

        if 'address' in self.inputs:
            selection = self.input_view("address").generate_sql_where(
                selection, MultiWozSqlDB.RESTAURANT_TABLE.columns.address, **kwargs)

        if 'food' in self.inputs:
            selection = self.input_view("food").generate_sql_where(
                selection, MultiWozSqlDB.RESTAURANT_TABLE.columns.food, **kwargs)

        if 'phone' in self.inputs:
            selection = self.input_view("phone").generate_sql_where(
                selection, MultiWozSqlDB.RESTAURANT_TABLE.columns.phone, **kwargs)

        if 'postcode' in self.inputs:
            selection = self.input_view("postcode").generate_sql_where(
                selection, MultiWozSqlDB.RESTAURANT_TABLE.columns.postcode, **kwargs)

        if 'pricerange' in self.inputs:
            selection = self.input_view("pricerange").generate_sql_where(
                selection, MultiWozSqlDB.RESTAURANT_TABLE.columns.pricerange, **kwargs)

        if 'type' in self.inputs:
            selection = self.input_view("type").generate_sql_where(
                selection, MultiWozSqlDB.RESTAURANT_TABLE.columns.type, **kwargs)

        return selection

    def graph_from_row(self, row, context):
        params = []
        for field in self.signature.keys():
            if self.signature[field].custom:
                continue
            value = row[field]
            if value:
                if isinstance(value, str):
                    value = escape_string(value)
                params.append(f"{field}={value}")

        node_str = f"Restaurant({', '.join(params)})"
        g, _ = Node.call_construct_eval(node_str, context, constr_tag=NODE_COLOR_DB)
        g.tags[DB_NODE_TAG] = 0
        return g

    def collect_state(self):
        do_collect_state(self, 'restaurant')

    # returns tuples: ('param_name=value', describing text, weight offset)
    # (low weight -> lower prob to select)
    def gen_field_opts(self, node_name, prms=None):
        opts = []
        add_field_opt(opts, self, 'name', -0.5)
        add_field_opt(opts, self, 'area', 0)
        add_field_opt(opts, self, 'food', 0)
        add_field_opt(opts, self, 'type', -0.2)
        add_field_opt(opts, self, 'pricerange', 0)
        if prms and 'full' in prms:
            add_field_opt(opts, self, 'phone', 0)
            add_field_opt(opts, self, 'postcode', -0.2)
            add_field_opt(opts, self, 'address', 0)
        return opts

    # replace slot value with a random (but valid) value for the given opt
    @staticmethod
    def get_alternative_opt_value(opt):
        slot, txt = opt
        if '=' in slot:
            slot = slot.split('=')[0]
        vals = Restaurant.gen_get_alternative_values(slot)
        if vals:
            val = random.choice(vals)
            # return '%s=%s' % (slot, val), Restaurant.gen_get_field_str_format(slot) % val
            return '%s=%s' % (slot, val), gen_get_field_str_format(slot, map_restaurant_inputs) % val
        return opt


def filter_restaurant_name_and_set_result(nd, results, filter_name=None):
    if filter_name:
        f, _ = nd.call_construct('Restaurant?(name=LIKE(Name(%s)))' % filter_name, nd.context)
        results = [r for r in results if f.match(r)]
    if len(results)==1:
        nd.set_result(results[0])
        results[0].call_eval(add_goal=False)  # not necessary, but adds color
    return results


class RestaurantBookInfo(Node):
    def __init__(self):
        super().__init__(type(self))
        self.signature.add_sig('bookday', Book_day)  # , custom=True)
        self.signature.add_sig('booktime', Book_time)  # , custom=True)
        self.signature.add_sig('bookpeople', Book_people)  # , custom=True)

    def gen_show_options(self):
        return ['bookday', 'booktime', 'bookpeople']

    @staticmethod
    def gen_get_field_str_format(name, prms=None):
        return gen_get_field_str_format(name, map_restaurant_inputs, prms)
        # if name=='bookday':
        #     return 'on %s'
        # if name=='booktime':
        #     return 'at %s'
        # if name=='bookpeople':
        #     return 'for %s people'
        # return ''

    @staticmethod
    def gen_get_alternative_values(name, prms=None):
        if name=='bookday':
            return ['sunday', 'monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday']
        if name=='booktime':
            return ['17:00', '18:00', '12:30', '13:00', '20:30']
        if name=='bookpeople':
            return ['1', '2', '3', '4']
        return []

    def get_context_values(self, inform_values=None, req_fields=None):
        slot_values = {}
        for name in self.inputs:
            element = next(filter(lambda x: x.typename() == "Str", self.input_view(name).topological_order()), None)
            #name = 'book' + name[5:] if name.startswith('book_') else name
            slot_values[f'restaurant-{name}'] = [element.dat] if element else []
        if inform_values:
            for k in inform_values:
                slot_values['restaurant-'+k] = inform_values[k]

        return slot_values

    def collect_state(self):
        do_collect_state(self, 'restaurant', 'book')

    def gen_field_opts(self, node_name, prms=None):
        opts = []
        add_field_opt(opts, self, 'bookday', 0)
        add_field_opt(opts, self, 'booktime', 0)
        add_field_opt(opts, self, 'bookpeople', 0)
        return opts

    # replace slot value with a random (but valid) value for the given opt
    @staticmethod
    def get_alternative_opt_value(opt):
        slot, txt = opt
        if '=' in slot:
            slot = slot.split('=')[0]
        vals = RestaurantBookInfo.gen_get_alternative_values(slot)
        if vals:
            val = random.choice(vals)
            # return '%s=%s' % (slot, val), RestaurantBookInfo.gen_get_field_str_format(slot) % val
            return '%s=%s' % (slot, val), gen_get_field_str_format(slot, map_restaurant_inputs) % val
        return opt


class BookRestaurantConfirmation(Node):
    def __init__(self):
        super().__init__(type(self))
        self.signature.add_sig('restaurant', Restaurant)
        self.signature.add_sig('book_info', RestaurantBookInfo)
        self.signature.add_sig('conf_code', Str)

    def describe(self, params=None):
        s = ['Restaurant resevation: ']
        m1 = self.input_view('restaurant').describe(params=['compact'])
        m2 = self.input_view('book_info').describe()
        s.append(m1.text)
        s.append(m2.text)
        s.append('Confirmation code: ' + self.get_dat('conf_code'))
        return Message('  NL  '.join(s), objects=m1.objects+m2.objects)

    def collect_state(self):
        self.inputs['restaurant'].collect_state()
        self.inputs['book_info'].collect_state()
        do_collect_state(self, 'restaurant', 'book')  # add conf code directly


def check_restaurant_availability(restaurant, binf, book_fields):
    if environment_definitions.agent_oracle:
        if 'ref' in book_fields:
            return True, book_fields['ref']
        if 'nobook' in book_fields:
            return False, None
    return True, 'XYZ%12345'  #  % random.randint(1000000, 9000000)


class BookRestaurant(Node):
    def __init__(self):
        super().__init__(BookRestaurantConfirmation)
        self.signature.add_sig('restaurant', Restaurant)
        self.signature.add_sig('book_info', RestaurantBookInfo)
        # maybe wrap the book info inputs into a node?
        self.inc_count('max_mention_name', 1)

    # todo - add agent_oracle mode!
    def exec(self, all_nodes=None, goals=None):
        #self.update_mwoz_state()

        if 'restaurant' not in self.inputs:
            raise MissingValueException('restaurant', self, 'Please specify what restaurant you are looking for')
        restaurant = self.input_view('restaurant')
        context = self.context

        # unlike find restaurant, there are no recommendations for book restaurant (?), so not much to do for oracle
        # maybe: in case of failed booking, then inform what needs to change? todo
        inform_fields = {}
        req_fields = {}
        book_fields = {}
        bfields = ['bookday', 'bookstay', 'booktime', 'ref']
        if environment_definitions.agent_oracle:
            dact = context.agent_turn['dialog_act']['dialog_act']
            atext = context.agent_turn['utterance']
            # 1. try to understand what the agent did -
            for d in dact:
                dom, typ = d.split('-')
                if dom=='xxBooking':
                    pass  # todo
                elif dom=='Restaurant' or dom=='Booking':
                    if typ == 'Inform':
                        for [k, v] in dact[d]:
                            if k in bfields:
                                inform_fields[k] = v
                    if typ == 'Book':
                        for [k, v] in dact[d]:
                            if k in bfields:
                                book_fields[k] = v
                    if typ == 'NoBook':
                        book_fields['nobook'] = 'True'
                    if typ == 'Request':
                        for [k, v] in dact[d]:
                            if k in bfields:
                                req_fields[k] = v

            if environment_definitions.oracle_only:
                # return the original message of the agent,
                #self.update_mwoz_state(inform_fields, req_fields)
                raise OracleException(atext, self)

        msg = ''
        mention_name = self.count_ok('mention_name')
        curr_name = self.get_ext_dat('restaurant.name')
        # print(curr_name)
        if self.dup_of:
            prev_name = self.dup_of.get_ext_dat('restaurant.name')
            if prev_name and curr_name!=prev_name:
                mention_name=True
        if mention_name:
            self.inc_count('mention_name')
            msg = 'OK, ' + restaurant.describe().text + '.  NL  '
        if restaurant.inp_equals('takesbookings', 'no'):
            raise InvalidInputException(msg + 'Unfortunately the restaurant does not take bookings.   NL  Maybe try another restaurant?', self)
        if 'book_info' not in self.inputs:  # should not be the case when using the "normal" initialization (fallback search)
            d, e = self.call_construct('RestaurantBookInfo()', self.context)
            d.connect_in_out('book_info', self)
        binf = self.inputs['book_info']
        if 'bookday' not in binf.inputs:
            raise MissingValueException('bookday', self, msg+'On which day would you like to book the restaurant?')
        if 'booktime' not in binf.inputs:
            raise MissingValueException('booktime', self, msg+'At what time would you like to book the restaurant?')  # todo - add hint - to avoid confusing with num people?
        if 'bookpeople' not in binf.inputs:
            raise MissingValueException('bookpeople', self, msg+'For how many people would you like to book the restaurant?')
        ok, conf_code = check_restaurant_availability(restaurant, binf, book_fields)
        if ok:
            d, e = self.call_construct_eval('BookRestaurantConfirmation(restaurant=%s, book_info=%s, conf_code=%s)' %
                                            (id_sexp(restaurant), id_sexp(binf), conf_code), self.context)
            self.set_result(d)
            self.context.add_message(self, 'I have made the reservation as requested  NL  The confirmation code is %s' % conf_code)
        else:
            # todo - if oracle - say what failed / what is needed
            raise InvalidInputException('Unfortunately the restaurant can not confirm this booking.    NL  Maybe try another day or length of stay?', self)

    def collect_state(self):
        if self.result != self:
            self.res.collect_state()
        else:
            self.inputs['restaurant'].collect_state()
            self.inputs['book_info'].collect_state()

    def get_opts(self):
        opts = []
        for i in ['restaurant', 'book_info']:
            if i in self.inputs:
                opts += self.input_view(i).gen_field_opts('BookRestaurant')
        return opts

    def add_slot_noise(self, opts, noise=0):
        if noise>0:
            opts = [o if random.random() > noise else
                    RestaurantBookInfo.get_alternative_opt_value(Restaurant.get_alternative_opt_value(o)) for o in opts]
        return opts

    def gen_user(self, target, context, node_map, persona, tried=None):
        # using the convention:
        #    if calling for the first time (before the current BookRestaurant even exists), then
        #    self is actually target, and target is given as None
        tried = tried if tried else []
        curr_exists = target is not None
        targ = target if curr_exists else self
        ctx = self.context
        if EXTRACT_SIMP:
            rest = self.input_view('restaurant')
            # 1. we may ask a question about the restaurant
            if curr_exists and (random.random()<persona.ask_incomplete or
                                (random.random()<persona.ask_complete and rest and rest.typename()=='Restaurant')):
                if rest and rest.typename()!='Restaurant':
                    rest = None
                slot = random.choice(['food', 'area', 'address', 'phone', 'postcode'])
                txt = 'what is the %s of the restaurant?' % slot  # todo - make nicer
                pexp = 'get_restaurant_info('
                if rest:
                    references = get_refer_match(ctx, Node.collect_nodes(ctx.goals), ctx.goals, pos1='Restaurant?()')
                    rr = 'refer(Restaurant?())' if references and references[0]==rest else id_sexp(rest)
                    pexp += 'restaurant=%s, ' % rr
                pexp += slot + ')'
                return pexp, txt, None, False
            else:  # 2. otherwise - continue revising
                objs = []
                if curr_exists:  # self is in the current graph. try to find exception from prev turn
                    es = self.context.get_prev_exceptions(ndtyps=['FindRestaurant', 'BookRestaurant'])
                    objs = sum([e.objects for e in es], [])
                opts = targ.get_opts()
                copts = self.get_opts() if curr_exists else []
                opts = [o for o in opts if o not in copts]   # do not repeat existing options
                if opts:
                    max_opts = min(3, len(opts))  # todo - if all opts already given...
                    min_opts = 0 if not curr_exists else 1
                    n = select_n_opts(min_opts, max_opts)
                    sel_opts = []
                    if objs:
                        pref_opts = [(i,j, w) for k in objs for (i,j, w) in opts if i.startswith(k)]
                        if pref_opts:
                            if random.random()<persona.select_suggested:  # frequently - select only one of the suggested slots
                                sel_opts = select_weighted_opt_choices(pref_opts, 1)  # [random.choice(pref_opts)]
                    if not sel_opts:
                        # random.shuffle(opts)
                        # sel_opts = opts[:n]
                        sel_opts = select_weighted_opt_choices(opts, n)
                    sel_opts = self.add_slot_noise(sel_opts, noise=persona.slot_noise)
                    if curr_exists:  # if we want to add refer even before task created, then we have to pass
                                     # as input the current context (and give it as input to add_refer)
                        sel_opts = add_refer(self, sel_opts, ['Restaurant', 'RestaurantBooking', 'revise_restaurant'], persona.add_refer)
                    pexp = 'revise_restaurant(' + ','.join([i for (i,j) in sel_opts]) + ')'
                    txt = "I'm looking for a restaurant "
                    if len(sel_opts)>3:
                        x=1
                    if len(sel_opts)>0:
                        txt += ', '.join([j for (i,j) in sel_opts])
                    return pexp, txt, None, False
        return '', '', None, False

    # base function - generate text of user request for input inp given target node
    def gen_user_text(self, target, inp):
        # should always be customized!
        v = target.input_view(inp)
        if v:
            return 'I want %s to be %s' % (inp, v.describe().text)
        return 'grrr...'

    def compare_task(self, other):
        crest, cbook = self.get_input_views(['restaurant', 'book_info'])
        orest, obook = other.get_input_views(['restaurant', 'book_info'])
        if crest.typename() == 'Restaurant' and cbook.typename() == 'RestaurantBookInfo':
            if orest.typename() == 'Restaurant' and obook.typename() == 'RestaurantBookInfo':
                if crest.compare_graphs(orest) and cbook.compare_graphs(obook):
                    return True
        return False


class FindRestaurant(Node):
    def __init__(self):
        super().__init__(Restaurant)
        self.signature.add_sig(posname(1), Restaurant, alias='restaurant')

    def exec(self, all_nodes=None, goals=None):
        context = self.context
        if posname(1) in self.inputs:
            restaurant = self.inputs[posname(1)]
        else:
            restaurant, _ = self.call_construct('Restaurant?()', context)
            restaurant.connect_in_out(posname(1), self)

        results = results0 = multiwoz_db.find_elements_that_match(restaurant, restaurant.context)
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
                if dom=='Booking':
                    if typ in ['Book', 'Inform']:
                        for [k, v] in dact[d]:
                            if k=='name':
                                inform_fields['book_name'].append(v)
                elif dom=='Restaurant':
                    if typ in ['Inform', 'Recommend']:
                        for [k, v] in dact[d]:
                            kk = 'rec_' + k if typ == 'Recommend' else k
                            inform_fields[kk].append(v)
                    if typ == 'Request':
                        for [k, v] in dact[d]:
                            req_fields[k] = v

            # for now - if the agent recommends a restaurant (by name), then we create a suggestion with implicit accept
            if 'book_name' in inform_fields:
                rec_field = 'book_name'

            if 'name' in inform_fields and len(inform_fields['name'])==1 and nresults0>1 and rec_field not in inform_fields:
                #rec_field = 'name'
                inform_fields['rec_name'] = inform_fields['name']
            if rec_field in inform_fields:
                if len(inform_fields[rec_field])==1:
                    nm = inform_fields[rec_field][0]
                    r = self.filter_and_set_result(results, nm)
                    if r:
                        results = r
                        nresults = len(results)
                    # results should not be empty - unless the agent made a mistake
                    sugg = self.mod_restaurant_name_and_suggest_neg(restaurant, nm)
                    # objs = add_mention_if_name_match(find, results, nm)  # no need - already added as result
                else:   # ignore multiple recommendations
                    del inform_fields[rec_field]

            if environment_definitions.oracle_only:
                # return the original message of the agent,
                #    but may need to change the result according to the agent's action
                #update_mwoz_state(restaurant, context, inform_fields, req_fields)
                raise OracleException(atext, self, suggestions=sugg, objects=objs)

        if not environment_definitions.agent_oracle:  # len(inform_fields)==0:  # no oracle, or oracle didn't say anything - use node logic to select what to report
            # add here logic to recommend a restaurant?
            if nresults > 1 and rec_field not in inform_fields:
                dfields = get_diff_fields(results0, ['type', 'food', 'area', 'pricerange'])
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
                sugg = self.mod_restaurant_name_and_suggest_neg(restaurant, rname)

            for f in ['type', 'food', 'area', 'pricerange', 'name', 'address', 'phone', 'postcode']:  # todo add more
                if f in inform_fields:
                    inform_fields[f] = collect_values(results0, f)

            if rec_field not in inform_fields or req_fields:  #  and nresults>2:
                if len(req_fields)==0 and not environment_definitions.agent_oracle and nresults>2:  # don't suggest if following oracle
                    dfields = get_diff_fields(results, ['type', 'food', 'area', 'pricerange'])
                    if dfields:
                        req_fields = {i:'?' for i in list(dfields.keys())[:2]}

            msg, objs = self.describe_inform_request(nresults0, inform_fields, req_fields)

            #update_mwoz_state(restaurant, context, inform_fields, req_fields)  # use inform_fields to update state
            if nresults!=1 or rec_field in inform_fields:
                raise OracleException(msg, self, suggestions=sugg, objects=objs)
            else:
                self.context.add_message(self, msg)

        # no inform fields and no recommendation
        #update_mwoz_state(restaurant, context)  # update without inform fields
        if nresults == 0:
            raise ElementNotFoundException(
                "I can not find a matching restaurant in the database. Maybe another area or price range?", self)
        if nresults > 1:
            objs = list(inform_fields.keys())[:2]
            diffs = ' or '.join(objs)
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
        s = '' if posname(1) in self.inputs else 'Restaurant?()'
        d, e = self.call_construct('BookRestaurant(restaurant=FindRestaurant(%s), book_info=RestaurantBookInfo())' % s , self.context)
        if posname(1) in self.inputs:
            find = d.inputs['restaurant']
            self.inputs[posname(1)].connect_in_out(posname(1), find)
        top.add_task(d)
        h = d.inputs['restaurant']
        parent.set_result(h)
        if do_eval:
            e = top.call_eval(add_goal=False)
            if e:
                raise e[0]
        return [h]

    # suggest a restaurant by name - if user rejects, then clear restaurant name
    def mod_restaurant_name_and_suggest_neg(self, constr, nm):
        d, e = constr.call_construct('LIKE(Name(%s))' % escape_string(nm), constr.context)
        constr.replace_input('name', d)
        return ['revise(old=Restaurant??(), newMode=overwrite, new=Restaurant?(name=Clear()))',
                'side_task(task=no_op())']

    def filter_and_set_result(self, results, filter_name=None):
        if filter_name:
            f, _ = self.call_construct('Restaurant?(name=LIKE(Name(%s)))' % escape_string(filter_name), self.context)
            results = [r for r in results if f.match(r)]
        if len(results)==1:
            self.set_result(results[0])
            results[0].call_eval(add_goal=False)  # not necessary, but adds color
        return results

    def describe_inform_request(self, nresults0, inform_fields, req_fields):
        prms = []
        objs = []
        nm = inform_fields.get('name')
        if nm and 'rec_name' not in inform_fields and 'book_name' not in inform_fields:
            prms.append('I have found ' + and_values_str(nm))

        if 'choice' in inform_fields:
            inform_fields['choice'] = [nresults0]
        choice = inform_fields.get('choice')
        if choice:
            prms.append('There are %d matching results' % nresults0)
        elif nresults0 > 1 and 'book_name' not in inform_fields and 'name' not in inform_fields:
            prms.append('I see several (%d) matches' % nresults0)

        for i in ['type', 'area', 'food', 'address', 'phone', 'postcode', 'pricerange']:
            dt = inform_fields.get(i)
            if dt:
                val = and_values_str(dt) if i in ['type', 'area', 'food'] else dt[0]
                prms.append(map_restaurant_inputs[i] % val)
        # typ = inform_fields.get('type')
        # if typ:
        #     prms.append('of type ' + and_values_str(typ))
        #
        # area = inform_fields.get('area')
        # if area:
        #     prms.append('In the ' + and_values_str(area))
        #
        # food = inform_fields.get('food')
        # if food:
        #     prms.append('They serve ' + and_values_str(food))
        # adr = inform_fields.get('address')
        # if adr:
        #     adr = adr[0]
        #     prms.append('It\'s located at ' + adr)
        # phone = inform_fields.get('phone')
        # if phone:
        #     prms.append('The phone number is ' + phone[0])
        # postcode = inform_fields.get('postcode')
        # if postcode:
        #     prms.append('The post code number is ' + postcode[0])
        # price = inform_fields.get('pricerange')
        # if price:
        #     prms.append('The price is ' + price[0])

        if 'rec_name' in inform_fields:
            prms.append('I recommend %s' % inform_fields['rec_name'][0])
        if 'book_name' in inform_fields:
            prms.append('I Have booked %s' % inform_fields['book_name'][0])
        if len(req_fields) > 0:
            objs = [i for i in req_fields]
            if nresults0 > 0:
                prms.append('maybe select %s' % ' or '.join(objs))
            else:
                prms.append('Sorry, I can\'t find a match. Try a different %s' % ' or '.join(objs))
        msg = ', '.join(prms)
        return msg, objs

    def on_duplicate(self, dup_tree=False):
        super().on_duplicate(dup_tree=dup_tree)
        # old = self.dup_of.input_view('restaurant')
        old = self.dup_of.res if self.dup_of.res != self.dup_of else self.dup_of.input_view('restaurant')
        curr = self.input_view('restaurant')
        if 'name' in old.inputs and 'name' in curr.inputs:
            changed = any([old.get_dat(i)!=curr.get_dat(i)  and curr.get_dat(i) is not None
                           for i in ['area', 'type', 'pricerange', 'food']])
            if changed:
                curr.disconnect_input('name')
        return self

    def collect_state(self):
        if self.result!=self:
            self.res.collect_state()
        elif 'restaurant' in self.inputs:
            self.inputs['restaurant'].collect_state()


# deprecated
# class revise_restaurant(Restaurant):
#     def __init__(self):
#         super().__init__()
#
#     def transform_graph(self, top):
#         pnm, parent = self.get_parent()
#         prms = ['%s=%s' % (i, id_sexp(self.input_view(i))) for i in self.inputs if i in self.inputs]
#         s = 'revise(old=Restaurant??(), new=Restaurant?(%s), newMode=overwrite)' % ','.join(prms)
#         d, e = self.call_construct(s, self.context)
#         self.replace_self(d)
#         return parent, None


class revise_restaurant(revise):
    # make it a subtype of revise, so we don't revise this call
    def __init__(self):
        super().__init__()
        self.signature.add_sig('name', Name)
        self.signature.add_sig('food', Food)
        self.signature.add_sig('type', Type)
        self.signature.add_sig('area', Area)
        self.signature.add_sig('pricerange', Pricerange)

        self.signature.add_sig('address', Address)
        self.signature.add_sig('phone', Phone)
        self.signature.add_sig('postcode', Postcode)
        # for booking
        self.signature.add_sig('bookday', Book_day)  # , custom=True)
        self.signature.add_sig('booktime', Book_time)  # , custom=True)
        self.signature.add_sig('bookpeople', Book_people)  # , custom=True)

    def valid_input(self):  # override the revise valid_input
        pass

    def transform_graph(self, top):
        if 'name' in self.inputs:
            n = self.input_view('name')
            if n.typename()=='Name':
                self.wrap_input('name', 'LIKE(')
        return self, None

    def exec(self, all_nodes=None, goals=None):
        # 1. raise or create task
        root = do_raise_task(self, 'FindRestaurant') #  the top conversation

        # 2. do revise if requested fields given
        rest_fields = ['area', 'food', 'name', 'pricerange',  'type',
                        'address', 'phone', 'postcode']
        book_fields = ['booktime', 'bookpeople', 'bookday']
        fields = {'rest': [i for i in self.inputs if i in rest_fields],
                  'book': [i for i in self.inputs if i in book_fields]}
        for f in fields:
            if fields[f]:
                nodes = root.topological_order(follow_res=False)
                book = [i for i in nodes if i.typename()=='BookRestaurant']
                if book:  # should always be the case
                    book = book[0]
                    prms = ['%s=%s' % (i, id_sexp(self.inputs[i])) for i in fields[f]]
                    # we know exactly what root/old/new should be, so no need to use the search mechanism of the
                    #   'revise' node - instead we can directly call duplicate_subgraph to create the revised graph
                    if f=='rest':
                        old = book.inputs['restaurant'].inputs['restaurant']
                        s = 'Restaurant?(' + ','.join(prms) + ')'
                    else:  # book info
                        old = book.inputs['book_info']
                        s = 'RestaurantBookInfo(' + ','.join(prms) + ')'
                    new, _ = self.call_construct(s, self.context)
                    new_subgraph = duplicate_subgraph(root, old, new, 'overwrite', self)
                    root = new_subgraph[-1]

        self.set_result(root)
        self.context.add_goal(root)  # will not add if already added before
        # root.call_eval()  # no need to call eval, since eval_res is True. is this what we want?


# use this node is for debugging - replace the "proactive" restaurant recommendation by the agent
# implement recommendation as a suggestion with implicit accept
class suggest_restaurant(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig(posname(1), Str)

    def exec(self, all_nodes=None, goals=None):
        if posname(1) in self.inputs:
            nm = self.get_dat(posname(1))
            suggs = ['no_op()',
                     SUGG_IMPL_AGR + 'revise(old=Restaurant??(), newMode=overwrite, new=Restaurant?(name=LIKE(Name(%s))))' % nm]
            raise OracleException('How about %s?' % nm, self, suggestions=suggs)
        # optionally - if no name given, try to get one from the available possible restaurants


class get_restaurant_info(Node):
    def __init__(self):
        super().__init__()
        self.signature.add_sig('restaurant', Restaurant)
        # self.signature.add_sig('feats', Node)
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
        restaurant = self.input_view('restaurant')
        if not restaurant:
            m = get_refer_match(self.context, all_nodes, goals, type='Restaurant')
            if m:
                restaurant = m[0]
            else:
                raise MissingValueException('restaurant', self, 'I can give information only after we have selected one restaurant')

        if restaurant:
            fts = []
            fts += [self.input_view(i).dat for i in self.inputs if is_pos(i)]
            if fts:
                vals = ['the %s is %s' %(i, restaurant.get_dat(i)) for i in fts]
                msg = 'For %s: ' % restaurant.get_dat('name') + ',  NL  '.join(vals)
                self.context.add_message(self, msg)

    def yield_msg(self, params=None):
        # msg = [m for (n,m) in self.context.messages if n==self]
        msg = self.context.get_node_messages(self)
        return msg[0] if msg else Message('')


################################################################################################################


def extract_find_restaurant(utterance, slots, context, general=None):
    return extract_find_domain(utterance, slots, context, 'Restaurant', map_restaurant_slots,
                               RESTAURANT_PREFIX, ['booktime', 'bookpeople', 'bookday'],
                               ['name', 'food', 'pricerange', 'type', 'area', 'address', 'phone', 'postcode'],
                               general)

