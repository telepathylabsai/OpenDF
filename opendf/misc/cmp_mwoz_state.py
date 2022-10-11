import json
import sys
from opendf.main_multiwoz_2_2 import compare_dialogue_state
import logging

logger = logging.getLogger(__name__)
# compare df_state generated at two separate runs of main_multiwoz_2_2
#  - use the option -w to main_multiwoz_2_2 to write the state

f1 = json.loads(open(sys.argv[1], 'r').read())
f2 = json.loads(open(sys.argv[2], 'r').read())

n_dia = 0
n_dia2 = 0
n_turns = 0
n_turns2 = 0
n_match = 0
n_match_dia = 0
n_strict = 0  # slots match, but active intent mismatch?

for d in f1:
    logger.warning(d)
    miss = False
    n_dia += 1
    d1= f1[d]
    if d in f2:
        n_dia2 += 1
        d2 = f2[d]
        for t in range(len(d1)):
            n_turns += 1
            if t<len(d2):
                n_turns2 += 1
                t1, t2 = d1[t], d2[t]
                errs1 = compare_dialogue_state(t1, t2, '')
                errs2 = compare_dialogue_state(t2, t1, '')
                if not errs1 + errs2:
                    n_match += 1
                    if t1!=t2:
                        n_strict += 1
                else:
                    miss = True
            else:
                miss = True
    else:
        miss = True
    if not miss:
        n_match_dia += 1

print('%d dialogs, %d matched, %d turns, %d match (%.1f)' %(n_dia, n_match_dia, n_turns, n_match, 100.0*n_match/n_turns))
print('n_dia2=%d  n_turn2=%d' %(n_dia2, n_turns2))

print(n_strict)