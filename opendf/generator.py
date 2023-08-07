"""
Dialog generator.
"""

# may want to merge this with main.py ?
#     or get the common parts out of main.py, so we can reuse them? (also, e.g., for custom_mains...)


# "Agenda driven" dialog generator.
# The agenda is an actual completed dialog ("target dialog")
#    (later, we could think of perturbations/augmentation)
# step 1: execute the target dialog, to get the final "target graph" - this is our agenda
#         this could be stored in a separate context
#
# step 2: start a new dialog:
#         - initialize new context,
#         - initialize a new graph - "current graph"
#            - (the usual init done by the system as first step, together with greeting)
#
# step 3 (repeat until done):
#         - map current graph nodes to target graph nodes
#         - look for a node in the current graph to generate the user request
#           - in general - we look at the target graph to get the slots/values the request should contain
#           - use its custom logic to generate the request - both pexp and text
#         - add randomness, to select different nodes/behaviors/slots
#           - possibly - also select values different from the target values,
#             and later correct them (users changed their mind)
#           - we may specify some preferences about the selection - encourage specific values / behaviors
#         - respond to agent messages:
#           - either to suggestions (OpenDF's suggestion mechanism),
#           - or to a structured representation of the message (e.g. objects)
#


import argparse
import json
import time
import uuid

import yaml
import random
import re
from dataclasses import dataclass

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
# to run this from the command line (assuming running from the repository's root directory) , use:
# PYTHONPATH=$(pwd) python opendf/main.py

# the main function gets S-exps as input, and executes them one by one.
# input is taken from dialogs in the examples file, by default `opendf.examples.main_examples`

logger = logging.getLogger(__name__)
environment_definitions = EnvironmentDefinition.get_instance()


def create_arguments_parser():
    """
    Creates the argument parser for the file.

    :return: the argument parser
    :rtype: argparse.ArgumentParser
    """
    parser = argparse.ArgumentParser(
        description="The main entry point to run the dataflow graphs. It runs examples from the "
                    "examples file.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument(
        "--config", "-c", metavar="config", type=str, required=False, default="resources/smcalflow_config.yaml",
        help="the configuration file for the application"
    )

    parser.add_argument(
        "--dialog_id", "-d", metavar="dialog_id", type=str, required=True, default=0, nargs="+",
        help="the dialog id to use. "
             "This should be the index of a dialog defined in the examples file"
    )

    parser.add_argument(
        "--rand_seed", "-s", metavar="rand_seed", type=int, required=False, default=0,
        help="the random seed to use. 0 to ignore"
    )

    parser.add_argument(
        "--additional_nodes", "-n", metavar="additional_nodes", type=str, required=False,
        default=None, nargs="+",
        help="path for python modules containing additional nodes to be imported. "
             "The path should be in python dot notation "
             "(e.g. `opendf.applications.sandbox.sandbox`) "
             "This argument only works when using `SMCalFlowEnvironment` as environment class"
    )

    parser.add_argument(
        "--output", "-o", metavar="output", type=str, required=False, default=None,
        help="Serializes the context of the graph to the given filepath. "
             "If the extension of the file is .bz2, it will be compressed"
    )

    parser.add_argument(
        "--persona", "-p", metavar="persona type", type=str, required=False,
        default="",
        help="persona used to select user actions. will use default if not given. will ignore unknown"
    )

    parser.add_argument(
        "--log", "-l", metavar="log", type=str, required=False, default="INFO",
        choices=LOG_LEVELS.keys(),
        help=f"The level of the logging, possible values are: {list(LOG_LEVELS.keys())}"
    )

    parser = add_environment_option(parser)

    return parser


# class Persona():
#     def __init__(self,
#                  ask_incomplete=0.1,
#                  ask_complete=0.2,
#                  select_suggested=0.5,
#                  slot_noise=0.1,
#                  add_refer=0.7,
#                  prefer_continue_exception=0.5,
#                  base_select_task=0.7,
#                  base_option_noise=0.7,
#                  personality=None):
#         self.ask_incomplete = ask_incomplete
#         self.ask_complete = ask_complete
#         self.select_suggested = select_suggested
#         self.slot_noise = slot_noise
#         self.add_refer = add_refer
#         self.prefer_continue_exception = prefer_continue_exception
#         self.base_select_task = base_select_task
#         self.base_option_noise = base_option_noise
#         if personality:
#             if personality in ['simple1']:
#                 print('\nUsing personality type: %s\n' % personality)
#             else:
#                 print('\nUnknown personality type, using default values!\n')
#         if personality == 'simple1':
#             self.ask_incomplete = 0
#             self.ask_complete = 0
#             self.select_suggested = 1
#             self.slot_noise = 0
#             self.add_refer = 0
#             self.prefer_continue_exception = 1
#             self.base_select_task = 0
#             self.base_option_noise = 0


@dataclass
class Persona():
    ask_incomplete: float = 0.1
    ask_complete: float = 0.2
    select_suggested: float = 0.5
    slot_noise: float = 0.1
    add_refer: float = 0.7
    prefer_continue_exception: float = 0.5
    base_select_task: float = 0.7
    base_option_noise: float = 0.7

    @staticmethod
    def with_personality(personality):
        if personality == 'simple1':
            return Persona(0.0, 0.0, 1.0, 0.0, 0.0, 1.0, 0.0, 0.0)
        logger.info(f"Unknown personality {personality}, using default values.")
        return Persona()


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


class OpenDFDialogueGenerator(OpenDFDialogue):

    def __init__(self, init_pexp, top_type, compare_func=None):
        self.init_pexp = init_pexp
        self.top_type = top_type
        self.compare_func = compare_func

    @staticmethod
    def collect_messages(d_context, ex, turn):
        msgs = []
        for m in d_context.messages:
            if isinstance(m, Message) and m.node:
                if m.node.created_turn == turn:
                    msgs.append(m.text)
        if ex:
            msgs.append(ex[0].message)
        # remove repeated messages
        remove = []
        for ii, i in enumerate(msgs):
            for ij, j in enumerate(msgs):
                if ij > ii:
                    if len(i) >= len(j) and j in i:
                        remove.append(ij)
                    if len(i) < len(j) and i in j:
                        remove.append(ii)
        msgs = [m for i, m in enumerate(msgs) if i not in remove]

        return '  NL  '.join(msgs)

    def gen_next_turn(self, target_context, d_context, persona):
        pexp = None
        txt = None
        curr = None
        post = None
        finished = None
        # 1. align graphs - for now only look at last goal of the specified top type
        curr_tops = [g for g in d_context.goals if g.typename() in list(self.top_type)]
        targ_tops = [g for g in target_context.goals if g.typename() in list(self.top_type)]
        targ_top = targ_tops[-1] if targ_tops else None
        curr_top = curr_tops[-1] if curr_tops else None
        if not targ_top:
            raise Exception('No target found for generation')
        if not curr_top:
            curr_top = targ_top.gen_curr_top(d_context)
        # if curr_tops and targ_tops:
        #     curr_top, targ_top = curr_tops[-1], targ_tops[-1]
        # else ...?
        if not curr_top:
            raise Exception('No curr top - can\'t generate')
        if environment_definitions.do_comp_gen:
            d_context.gen_curr_top = curr_top  # hack! fix

        # get nodes (in current graph) which can be used for generating a user request, and their matching nodes in
        # target
        node_map = curr_top.match_gen_nodes(targ_top, {})

        # choose one node to generate user request - prioritize based on: evaluated; with exception
        nscores = {}
        for n in node_map:
            score = random.random()
            if not n.evaluated:
                score += 0.5
                if d_context.get_node_exceptions(n, -1):
                    score += 0.5
                elif d_context.get_exceptions_under_node(n, -1):
                    score += 0.25
            nscores[n] = score
        nodes = sorted(nscores, key=nscores.get)
        # curr, targ = random.choice(list(node_map.items()))  # random selection
        tried = []
        for curr in reversed(nodes):
            # curr, targ = nodes[-1], node_map[nodes[-1]]
            targ = node_map[curr]
            pexp, txt, post, finished = curr.gen_user(targ, d_context, node_map, persona=persona, tried=tried)
            if pexp:
                return pexp, txt, curr, post, finished
                # return None, False, '', curr, post, finished
            tried.append(curr)
        return pexp, txt, curr, post, finished

    def run_dialogue(self, target_context, d_context, draw_graph=True, persona=None, do_trans=True):
        end_of_dialog = False
        d_context.reset_turn_num()
        ex = None
        psexp = None  # prev sexp
        i_utter = 0
        persona = persona if persona else Persona()
        notrans = d_context.no_trans

        print('\n\nGenerated conversation:')
        gl = None

        # hack - to generate training data for augmentation- repeatedly generate first turn (only)
        repeat_first_turn = 10
        gen_rand_start = True  # randomly generate target tree each iteration
        too_long_pexp = 999
        too_long_txt = 999

        if environment_definitions.do_comp_gen and repeat_first_turn > 0:
            n_diff = 0
            max_pexp, max_txt = 0,0
            n_long = 0
            long_gen = set()
            generated_examples = set()
            fp2 = open('tmp/aug_2.txt', 'w')
            fp3 = open('tmp/aug_2.txt2', 'w')
            fpl = open('tmp/aug_2_long.jsonl', 'w')
            with open('tmp/aug_2.jsonl', 'w') as fp:
                for ii in tqdm(range(repeat_first_turn), dynamic_ncols=True, unit=" examples"):
                    d_context.clear()
                    d_context.no_trans = notrans

                    if gen_rand_start:
                        constr = gen_rand_event_constraints(environment_definitions.max_n_ev_constrs)
                        pex = 'CreateEvent(' + constr + ')'
                        target_context.clear()
                        target_context.no_trans = notrans
                        d, _ = Node.call_construct(pex, target_context, add_goal=True)

                    isexp, txt, gen_node, post, end_of_dialog = \
                        self.gen_next_turn(target_context, d_context, persona)
                    user_text = re.sub(' NL ', '\n', txt).strip()
                    tokenized_exp = tokenize_pexp(isexp, sep_equal=False)
                    fp2.write(tokenized_exp + '\n')
                    fp3.write(txt + '  //  ' + tokenized_exp + '\n')
                    if len(tokenized_exp.split()) >= too_long_pexp or len(user_text.split())>=too_long_txt:
                        if (user_text, tokenized_exp) not in long_gen:
                            n_long += 1
                            long_gen.add((user_text, tokenized_exp))
                            json.dump(generate_dialogue(user_text, tokenized_exp), fpl)
                            fpl.write("\n")
                        continue
                    if (user_text, tokenized_exp) in generated_examples:
                        continue
                    max_pexp = max(max_pexp, len(tokenized_exp.split()))
                    max_txt = max(max_txt, len(user_text.split()))
                    n_diff += 1
                    if n_diff%10000==0:
                        tqdm.write('  %d diff  : p %d  : t %d : long: %d' % (n_diff, max_pexp, max_txt, n_long))
                    generated_examples.add((user_text, tokenized_exp))
                    json.dump(generate_dialogue(user_text, tokenized_exp), fp)
                    fp.write("\n")
                    # fp2.write(user_text + '  //  ' + tokenized_exp + '\n')
            print(f"Unique examples:\t{len(generated_examples)}")
            print('\n')
            fp2.close()
            fp3.close()
            fpl.close()
            print('txt token num histogram:')
            print(np.histogram([len(e[0].split()) for e in generated_examples]))
            print('pexp token num histogram:')
            print(np.histogram([len(e[1].split()) for e in generated_examples]))
            import pickle
            pickle.dump(list(generated_examples), open('tmp/xxx.set', 'wb'))
            exit(0)
        else:

            if gen_rand_start:
                d_context.clear()
                d_context.no_trans = notrans
                constr = gen_rand_event_constraints(environment_definitions.max_n_ev_constrs)
                pex = 'CreateEvent(' + constr + ')'
                target_context.clear()
                target_context.no_trans = notrans
                d, _ = Node.call_construct(pex, target_context, add_goal=True)
                d, _ = Node.call_construct(pex, d_context, add_goal=True)
                d, _ = Node.call_construct(pex, d_context, add_goal=True)

            while not end_of_dialog:
                gen_node, post = None, None
                if i_utter == 0:
                    isexp, txt = self.init_pexp, 'hello'
                else:
                    isexp = None
                    if i_utter < 20:  # temp - do just one step
                        isexp, txt, gen_node, post, end_of_dialog = \
                            self.gen_next_turn(target_context, d_context, persona)
                if isexp is None or not isexp:
                    # temp (for mwoz only) - this should be generated (app specific)
                    isexp, cont, txt = 'General_bye()', False, 'Goodbye!'
                    end_of_dialog = True

                print('%d. User: %s' % (i_utter, re.sub(' NL ', '\n', txt)))
                print('         ' + isexp)
                d_context.no_trans = False
                gl, ex, d_context, turn_answers = \
                    self.run_single_turn(isexp, d_context, draw_graph, gl, do_trans=True)  # do_trans)

                if post:
                    gen_node.post_gen(post)

                msgs = self.collect_messages(d_context, ex, i_utter)
                if msgs:
                    print('%d. Agent: %s' % (i_utter, re.sub(' NL ', '\n          ', msgs)))
                i_utter += 1

        comparison = None
        if self.compare_func:
            comparison = self.compare_func(d_context, target_context)
            print('\nGenerated dialog %s reach same result as target\n' %
                  ('DID' if comparison else "DIDN'T"))

        if draw_graph:
            # temporary - for visuzlization (but will not draw correctly - mix of two contexts...)
            if False and not target_context.other_goals and not d_context.other_goals:
                d_context.other_goals = target_context.goals  # [-2:-1]
            draw_all_graphs(d_context, 0, not ex, sexp=indent_sexp(psexp))

        if d_context.exceptions:
            msg, nd, _, _ = parse_node_exception(d_context.exceptions[-1])
            nd.explain(msg=msg)

        return gl, ex, d_context, comparison


def main(target_context, dialogue_generator, environment_class: EnvironmentClass,
         draw_graph=True, output_path=None, persona=None):
    try:
        d_context = environment_class.get_new_context()
        d_context.no_trans = target_context.no_trans  # always?
        environment_class.d_context = d_context
        if environment_definitions.in_place_replacement:
            g = target_context.goals[-1]
            # first copy (will stay as is)
            dup = g.duplicate_tree(g, n_context=d_context, do_on_dup=False)[-1]
            d_context.add_goal(dup)
            # second copy - will be modified in place
            dup = g.duplicate_tree(g, n_context=d_context, do_on_dup=False)[-1]
            d_context.add_goal(dup)
        with environment_class:
            do_trans = not target_context.no_trans
            gl, ex, ctx, comparison = dialogue_generator.run_dialogue(
                target_context, d_context, draw_graph=draw_graph, persona=persona, do_trans=do_trans)
            # gl, ex, ctx = dialog(target_context, d_context, init_pexp, top_type, compare,
            #                      draw_graph=draw_graph, persona=persona)
            if output_path:
                from os.path import splitext
                import pickle
                _, ext = splitext(output_path)
                if ext == '.bz2':
                    import bz2
                    with bz2.BZ2File(output_path, 'wb') as output_file:
                        pickle.dump(d_context, output_file)
                else:
                    with open(output_path, 'wb') as output_file:
                        pickle.dump(d_context, output_file)
            return gl, ex, ctx, comparison
    except Exception as e:
        raise e


def call_main(arguments, env, id_arg, persona, draw_graph=True):
    if isinstance(env, GenericEnvironmentClass):
        from opendf.main import OpenDFDialogue, run_dialogue_from_arguments

        target_context = run_dialogue_from_arguments(arguments, draw_graph=False)
        _init_pexp, _top_type, _compare = env.init_gen(target_context, environment_definitions)
        if _init_pexp is None:
            raise Exception("Application not supported!")
    elif isinstance(env, SMCalFlowEnvironment):
        from opendf.main import OpenDFDialogue, run_dialogue_from_arguments

        target_context = run_dialogue_from_arguments(arguments, id_arg, draw_graph=False, do_trans=False)
        target_context.no_trans = True
        # for now - we'll just generate variations of one turn, and not execute it
        #         - so no need for init, compare, top_type
        _init_pexp, _top_type, _compare = 'no_op()', ['CreateEvent', 'DeleteEvent',
                                                      'UpdateEvent'], None  # None, None,
        # None  # environment_class.init_gen(target_context, environment_definitions)
        # if _init_pexp is None:
        #     raise Exception("Application not supported!")

    else:  # multiwoz.  (generator not implemented for any other application yet)
        # config = "resources/multiwoz_2_2_config.yaml"
        from opendf.main_multiwoz_2_2 import run_dialog_with_id
        from opendf.applications.multiwoz_2_2.nodes.multiwoz import init_gen

        target_context = run_dialog_with_id(id_arg)  # (uses oracle)
        _init_pexp, _top_type, _compare = init_gen(target_context, environment_definitions)

    node_fact = NodeFactory.get_instance()
    node_fact.init_gen()

    dialogue_generator = OpenDFDialogueGenerator(_init_pexp, _top_type, _compare)
    if arguments.environment:
        environment_definitions.update_values(**arguments.environment)

    random.seed(sd)

    main(target_context, dialogue_generator, environment_class,
         output_path=arguments.output, persona=persona, draw_graph=draw_graph)


if __name__ == "__main__":
    start = time.time()
    try:
        parser = create_arguments_parser()
        arguments = parser.parse_args()
        config_log(level=arguments.log)

        sd = arguments.rand_seed if arguments.rand_seed else random.randint(0,1000)
        print('seed=%d' % sd)
        random.seed(sd)

        _persona = Persona.with_personality(arguments.persona)

        application_config = yaml.load(open(arguments.config, 'r'), Loader=yaml.UnsafeLoader)
        environment_class = application_config["environment_class"]

        if isinstance(environment_class, SMCalFlowEnvironment) and arguments.additional_nodes:
            environment_class.additional_paths = arguments.additional_nodes

        id_args = arguments.dialog_id
        draw_graph = len(id_args) == 1
        results = []
        for id_arg in id_args:
            _, _, _, comparison = call_main(arguments, environment_class, id_arg, _persona, draw_graph)
            results.append(comparison)

        print("Dialogue Results:")
        for id_arg, result in zip(id_args, results):
            print(f"{id_arg}:\t{result}")

        print()
        all_good = all(results)
        print(f"All OK: {all_good}")

    except Exception as e:
        raise e
    finally:
        end = time.time()
        logger.info(f"Running time: {end - start:.3f}s")
        logging.shutdown()
