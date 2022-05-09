#  Copyright (c) Microsoft Corporation.
#  Licensed under the MIT license.

import jsons
from tqdm import tqdm


def load_jsonl_file(data_jsonl, cls=None, unit=" items", verbose=False):
    """
    Loads a jsonl file and yield the deserialized dataclass objects.
    """
    if verbose:
        desc = f"Reading {cls} from {data_jsonl}"
    else:
        desc = None
    with open(data_jsonl) as fp:
        for line in tqdm(fp, desc=desc, unit=unit, dynamic_ncols=True, disable=not verbose):
            yield jsons.loads(line.strip(), cls=cls)
