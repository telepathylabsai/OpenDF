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
                # t = ['%s:%s' % (j, k) for [j, k] in s if k]
                t = '%s:%s' % (s[0], s[1])
        return '' if not t else ', '.join(t) if isinstance(t, list) else t




for dia in data:
    print('\n' + dia + '='*40)
    d = data[dia]
    goal = d['goal']
    for g in goal:
        gg = goal[g]
        if g=='message':
            pass
        elif g=='topic':
            t = [i for i in gg if gg[i]]
            if t:
                print('topic: ' + ','.join(t))
        else:
            if len(gg)>0:
                for s in gg:
                    if len(gg[s])>0:
                        t = ''
                        if isinstance(gg[s], dict):
                            t = ['%s:%s' % (i, gg[s][i]) for i in gg[s]]
                        elif isinstance(gg[s], list):
                            t = gg[s]
                        else:
                            t = [gg[s]]
                        if t:
                            print(' goal  %s:%s   %s' %(g, s, ', '.join(t)))

    log = d['log']
    for it, turn in enumerate(log):
        spkr = 'Agnt' if it%2 else 'User'
        print('%2d %s: %s' %(it, spkr, turn['text']))
        if spkr =='User':
            for i in turn:
                if len(turn[i]) > 0:
                    f = turn[i]
                    if i == 'dialog_act':
                        for j in f:  # hotel-inform
                            t = ',  '.join(['%s:%s' % (k, l) for [k, l] in f[j]])
                            if t:
                                print('         %s %s    %s' % (i, j, t))
        else:  # agent
            for i in turn:
                if len(turn[i])>0:
                    f = turn[i]
                    if i=='dialog_act':
                        for j in f:
                            t = ',  '.join(['%s:%s' % (k,l) for [k,l] in f[j]])
                            if t:
                                print('         %s %s    %s' %(i,j,t))
                    if i=='metadata':
                        for j in f:  # taxi
                            tt = []
                            for m in f[j]:  # book, semi
                                t = get_non_empty(f[j][m])
                                if t:
                                    tt.append(t)
                            t = ',  '.join(tt) if tt and isinstance(tt, list) else tt if tt else ''
                            if t:
                                print('         %s %s    %s' %(i,j,t))
