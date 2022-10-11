import json
import sys

fname = sys.argv[1]

ll = open(fname, 'r').read()
data = json.loads(ll)


def get_non_empty(s):
    if not s:
        return ''
    if isinstance(s, str):
        return s if s not in ['not mentioned'] else ''
    if isinstance(s, dict):
        t = ['%s:%s' % (i, get_non_empty(s[i])) for i in s if get_non_empty(s[i])]
        return '' if not t else ', '.join(t) if isinstance(t, list) else t

    if isinstance(s, list):
        t = ''
        if len(s)>0 and isinstance(s[0], dict):
            t = [get_non_empty(i) for i in s if get_non_empty(i)]
        else:
            if len(s)==2:
                t = ['%s:%s' % (j, k) for [j,k] in s if k]
        return '' if not t else ', '.join(t) if isinstance(t, list) else t


def get_slot(s):
    return '%s:%s' % (s['slot'], s['value'])

def get_action(s):
    return ''  # always empty?

def get_state(s):
    intnt = s['active_intent']
    slts = s['slot_values']
    slots = ['%s:%s' % (i, '/'.join(slts[i])) for i in slts]
    rqslots = s['requested_slots']
    t = []
    if intnt!='NONE':
        t.append('active_intent:' + intnt)
    if slots:
        t.append('slots:: ' + ', '.join(slots))
    if rqslots:
        t.append('req_slots:: ' + ', '.join(rqslots))
    return ', '.join(t)

for d in data:
    print('\n' + d['dialogue_id'] + '='*40)
    serv = d['services']
    print('  services: %s' % ', '.join(serv))

    for it, turn in enumerate(d['turns']):
        spkr = turn['speaker']
        print('%2d %s: %s' %(it, spkr, turn['utterance']))
        if spkr =='USER':
            tt = []
            frames = turn['frames']
            for fr in frames:
                dom = fr['service']
                slots = [get_slot(s) for s in fr['slots']]
                # actions = [get_action(s) for s in fr['actions']]
                state = get_state(fr['state'])
                if slots:
                    print('         %s slots: %s' %(dom, ', '.join(slots)))
                if state:
                    print('         %s state: %s' %(dom, state))
        else:  # system
            pass  # nothing interesting (??)


