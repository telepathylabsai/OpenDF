import json
import sys

fname = sys.argv[1]

ll = open(fname, 'r').read()
data = json.loads(ll)

for dia in data:
    d = data[dia]
    print('\n' + dia + '='*40)

    for n in d:
        spkr = 'Agnt' if int(n)%2 else 'User'
        print('%s. %s:' % (n, spkr))
        turn = d[n]
        for k in turn:
            t = turn[k]
            if k=='dialog_act':
                for i in t:
                    print('    %s  %s' %(i, ', '.join(['%s:%s' % (u,v) for [u,v] in t[i]])))



