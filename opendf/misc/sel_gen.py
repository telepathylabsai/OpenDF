
import argparse
import json
import time
import uuid

import yaml
import random
import re

from tqdm import tqdm
import numpy as np

from opendf.applications import EnvironmentClass, GenericEnvironmentClass, SMCalFlowEnvironment
from opendf.graph.draw_graph import draw_all_graphs
from opendf.defs import *
from opendf.main import OpenDFDialogue
from opendf.utils.arg_utils import add_environment_option
from opendf.exceptions import parse_node_exception
from opendf.utils.simplify_exp import indent_sexp
from opendf.utils.utils import Message
from opendf.graph.node_factory import NodeFactory

from opendf.utils.simplify_exp import tokenize_pexp
from opendf.utils.utterance_tokenizer import UtteranceTokenizer

from opendf.applications.smcalflow.nodes.modifiers import gen_rand_event_constraints
from opendf.graph.nodes.node import Node

import pickle
from collections import defaultdict



tokenizer = UtteranceTokenizer()

def generate_dialogue(user_text, tokenized_exp):
    dialogue_id = str(uuid.uuid4())
    tokens = tokenizer.tokenize(user_text)
    return {"dialogue_id": dialogue_id,
            "turns": [
                {
                    "agent_utterance": {
                        "described_entities": [],
                        "original_text": "",
                        "tokens": []
                    },
                    "lispress": tokenized_exp,
                    "program_execution_oracle": {
                        "has_exception": False,
                        "refer_are_correct": True
                    },
                    "skip": False,
                    "turn_index": 0,
                    "user_utterance": {
                        "original_text": user_text,
                        "tokens": tokens
                    }
                }]
            }


def del_terminal(s):
    rm = []
    i = 0
    j = -1
    l = len(s)
    t = ''
    while i<l:
        c = s[i]
        if c=='(':
            j=i
        if c=='=' and j>=0:
            j=i
        if c==',':
            j=-1
        if c==')':
            if j>=0:
                rm += list(range(j+1,i))
            j = -1
        i += 1
    t = ''.join([s[i] for i in range(l) if i not in rm])
    return t

x=1

gen = pickle.load(open('tmp/xxx.set', 'rb'))

maxt = 30
maxp = 50

d = defaultdict(list)
n_long = 0
i=0
for g in tqdm(gen, dynamic_ncols=True, unit=" examples"):
    i+=1
    if len(g[0].split()) < maxt and len(g[1].split()) < maxp:
        s = del_terminal(g[1])
        d[s].append(g)
        if len(d)%50000==0:
            tqdm.write('d=%d, long=%.4f'%(len(d), n_long/i))
    else:
        n_long+=1
    # if i>5000:
    #     break

ll = [0] * 50
for i in d:
    n = min(40,len(d[i]))
    ll[n] += 1
print(ll)


ll = np.array([len(d[i]) for i in d])
print(np.histogram(ll))

sel = []
for i in d:
    sel += [random.choice(d[i])]

print(len(sel))

print('writing')
with open('tmp/yyy.set', 'w') as fp:
    for g in tqdm(sel):
        json.dump(generate_dialogue(g[0], g[1]), fp)
        fp.write("\n")

x=1