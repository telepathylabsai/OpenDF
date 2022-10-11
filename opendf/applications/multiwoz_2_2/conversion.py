"""
Converts a MultiWOZ 2.2 dialogue into P-Expressions.
"""
import logging
from typing import Dict

from opendf.applications.multiwoz_2_2.nodes.taxi import extract_find_taxi
from opendf.applications.multiwoz_2_2.nodes.hotel import extract_find_hotel
from opendf.applications.multiwoz_2_2.nodes.train import extract_find_train
from opendf.applications.multiwoz_2_2.nodes.restaurant import extract_find_restaurant
from opendf.applications.multiwoz_2_2.nodes.attraction import extract_find_attraction
from opendf.applications.multiwoz_2_2.nodes.hospital import extract_find_hospital
from opendf.applications.multiwoz_2_2.nodes.police import extract_find_police

from opendf.applications.multiwoz_2_2.utils import *

INTENT_MAP = {
    "find_hotel": extract_find_hotel,
    "find_hospital": extract_find_hospital,
    "find_police": extract_find_police,
    "find_restaurant": extract_find_restaurant,
    "find_train": extract_find_train,
    "find_attraction": extract_find_attraction,
    "find_taxi": extract_find_taxi,
    "book_restaurant": extract_find_restaurant,
    "book_train": extract_find_train,
    "book_hotel": extract_find_hotel,
}


class ConversionErrorMultiWOZ_2_2(Exception):

    def __init__(self, *args):
        super(ConversionErrorMultiWOZ_2_2, self).__init__(*args)


def get_related_dict(service, items):
    """
    Gets the dict which has a field named 'service' with value equal to `service` (parameter),
    from the list of dicts `item`.

    If there is no dict that matches, it returns an empty dict.

    :param service: the value of the service
    :type service: str
    :param items: the list of dicts
    :type items: List[Dict]
    :return: the dict with the given service, if exists; otherwise, returns an empty dict
    :rtype: Dict
    """
    for item in items:
        if item.get("service") == service:
            return item
    return {}


def compute_diff(previous_turn, current_turn):
    """
    Computes the difference between the previous turn and the current turn.
    It considers that the turns are additive, i.e. the current turn (possibly)
    has more items, on top of the previous turn.

    The result if a dictionary containing only the new items.

    :param previous_turn: the previous turn
    :type previous_turn: Dict
    :param current_turn: the current turn
    :type current_turn: Dict
    :return: the items from current turn that were not presented in previous turn
    :rtype: Dict
    """
    if not previous_turn:
        return current_turn

    result = {}
    for key, value in current_turn.items():
        if key not in previous_turn:
            result[key] = value
        elif isinstance(value, dict):
            inner_result = compute_diff(previous_turn[key], value)
            if inner_result:
                result[key] = inner_result
        elif isinstance(value, list):
            result_list = []
            for item in value:
                if isinstance(item, dict) and "service" in item:
                    previous_item = get_related_dict(item["service"], previous_turn[key])
                    dict_diff = compute_diff(previous_item, item)
                    if dict_diff:
                        result_list.append(dict_diff)
                elif item not in previous_turn[key]:
                    result_list.append(item)
            if result_list:
                result[key] = result_list
        elif value != previous_turn[key]:
            result[key] = value

    return result


def clean_frame(frame):
    """
    Cleans the frame dict by removing unused fields.

    :param frame: the frame dict
    :type frame: Dict
    :return: the cleaned frame
    :rtype: Dict
    """
    if "actions" in frame and not frame["actions"]:
        del frame["actions"]

    if "slots" in frame:
        del frame["slots"]

    state = frame.get("state")
    if state:
        if "requested_slots" in state and not state["requested_slots"]:
            del state["requested_slots"]

        if "slot_values" in state and not state["slot_values"]:
            del state["slot_values"]

    return frame


ADD_LAST_GOODBYE = True  # add a goodbye from the user at the last turn


def convert_dialogue(dialogue, turn_id, context, use_dialog_act=False):
    # the dataflow counts one turn as a pair of user and agent interaction,
    # while multiwoz counts a turn for the user and another for the agent.
    # Here, we only care for the user turns, which are the even turns
    turn_id = turn_id * 2

    if dialogue is None:
        return [], []

    all_problems = set()

    previous_turn = dialogue["turns"][turn_id - 2] if turn_id else {}
    current_turn = dialogue["turns"][turn_id]
    utterance = current_turn["utterance"].lower()
    expressions = []
    p_exp = get_init_generic(current_turn)
    general = p_exp if p_exp != "GenericPleasantry()" else None

    # do we have multiple active intents?
    frames = current_turn.get("frames", [])
    active_intents = {}
    for frame in frames:
        frame_intent = frame["state"].get("active_intent", "NONE")
        if frame_intent != "NONE":
            service = frame["service"]
            active_intents[service] = False
            if 'dialog_act' in current_turn and 'dialog_act' in current_turn['dialog_act']:
                dacts = current_turn['dialog_act']['dialog_act']
                active_intents[service] = any([service in i.lower() for i in dacts])
    has_intent_with_dacts = any([active_intents[i] for i in active_intents])

    for frame in frames:
        frame_intent = frame["state"].get("active_intent", "NONE")
        if frame_intent == "NONE":
            continue
        frame_service = frame["service"]
        previous_frame = \
            get_related_dict(frame_service, previous_turn.get("frames", []))  # prev turn frame for same service
        frame_difference = compute_diff(previous_frame, frame)

        # remove spurious active intents with no dialog acts (heuristic cleaning of annotations)
        if len(active_intents) > 0 and not active_intents[frame_service] and has_intent_with_dacts:
            continue
        # if current_intent is `None`, it is the same intent as the last turn.
        # Change it to revise.  - not used anymore
        # is_revise = None  # "state" not in frame_difference or "active_intent" not in frame_difference["state"] #

        if frame_intent not in INTENT_MAP:
            if frame_intent not in SKIPPED_INTENTS:
                problem = f"Intent {frame_intent} not mapped!"
                all_problems.add(problem)
            continue

        if use_dialog_act:
            slot_dict = convert_dialog_act(current_turn, frame_service)
        else:
            slot_dict = frame_difference.get("state", {}).get("slot_values", {})

        turn_expressions, conversion_problems = INTENT_MAP[frame_intent](utterance, slot_dict, context, general)
        all_problems.update(conversion_problems)

        if turn_expressions:
            expressions.extend(turn_expressions)

    if ADD_LAST_GOODBYE and turn_id == len(dialogue["turns"]) - 2 and not any(
            ['General_bye' in e for e in expressions]):
        expressions.append('General_bye()')
    if len(expressions) == 1:
        p_exp = expressions[0]
    elif len(expressions) > 1:
        p_exp = f"cont_turn({', '.join(expressions)})"

    if all_problems:
        logger = logging.getLogger()
        logger.warning(all_problems)
    return p_exp, all_problems


allow_request = True


def convert_dialog_act(current_turn, frame_service):
    dialog_act_key = frame_service[0].upper() + frame_service[1:] + "-Inform"
    act_slot = current_turn['dialog_act']['dialog_act'].get(dialog_act_key, [])
    slot_dict = {}
    for name, value in act_slot:
        if name.lower() == "none" or value.lower() == "none":
            continue
        slot_dict.setdefault(f"{frame_service}-{name}", []).append(value)
    if allow_request:
        dialog_act_key = frame_service[0].upper() + frame_service[1:] + "-Request"
        act_slot = current_turn['dialog_act']['dialog_act'].get(dialog_act_key, [])
        for name, value in act_slot:
            if name.lower() == "none" or value.lower() == "none":
                continue
            slot_dict.setdefault(f"{frame_service}-request-{name}", []).append(value)

    return slot_dict


def get_init_generic(current_turn):
    pexp = ["GenericPleasantry()"]
    dacts = current_turn['dialog_act']['dialog_act']
    for i in dacts:
        if i.startswith('general-'):
            pexp.append('General_%s()' % i[len('general-'):])
    if 'General_bye()' in pexp:
        return 'General_bye()'
    return pexp[-1]
