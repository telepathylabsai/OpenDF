# MultoWOZ-DF - a dataflow implementation of MultiWOZ

This page describes the dataflow implementation of MultiWOZ, and how to run the experiments described in our upcoming paper "MultiWOZ-DF".

## Data

We are using MultiWOZ version 2.2. 

Please follow the instructions in the MultiWOZ github page (not that some scripts need to be run).

Make a directory "opendf/resources/multiwoz", and copy the 7 domain databases (attraction_db.json, ...train_db.json) into that directory.

Manually add the following line to the hospital_db.json:

 {"department": "Addenbrookes Hospital", "id": 999, "phone": "01223245151"},

(this appears as answer in multiple dialogues, but not in the hospital database)

Make a directory opendf/tmp/multiwoz_2_2, and under that create directories train, dev, test,
and copy the corresponding dialogue json files (dialogues_001.json, ...) there.

Copy the file dialog_acts.json to tmp/multiwoz_2_2


## Running

Use main_multiwoz_2_2.py to run the multiwoz experiments. 

This program: 
1. converts each dialogue turn to our DF format, 
2. writes out the converted DF expressions - for use by the seq2seq model training 
3. executes the expression, and 
4. compares the execution results with the manual dialogue state annotation


For example, running:

main_multiwoz_2_2.py -o tmp/multiwoz_2_2/dev_ -a -A -g  -x -d MUL1271

will run one dialogue (MUL1271), and draw the resulting graphs for the whole conversation.
It will also save the file tmp/multiwos_2_2/dev_dialog_good.txt (or .../dev_dialog_bad.txt, 
depending on the success of the comparison to the manual annotation) with the log of the conversation.

Please see the program for explanation about the required/optional inputs.

To run main.py with multiwoz nodes, use:

main.py -c resources/multiwoz_2_2_config.yaml

## Code

The multiwoz implementation is under opendf/applications/multiwoz_2_2, with the domains each implemented as a separate file under nodes/.

The code for the different domain nodes is to a large degree a copy-paste of each other, but each domain has some unique peculiarities.

The code for the domains' nodes is longer than the "typical" SMCalFlow node, due to the fact that in addition to "normal" execution, 
we also have to take care of conversion from the original annotation, handling the oracle input (see paper), and comparing the execution 
result to the manual DST annotation.


## Implementation style

In the Multiwoz experiment in the original Semantic Machines paper, the focus was on a minimal DF implementation to 
demonstrate possible benefits of the DF paradigm even for flat intents/entities type of datasets.

In the current implementation, we decided to give a fuller implementation, which is closer to
an actually functional dialogue system - connect this with the seq2seq translation model,
and you could run interactive dialogues.

In particular - the user can ask questions (and have them answered) about the domains, as well 
as having a top-level (interaction-level) active node, which keeps prompting the user for input, keeping
the conversation "alive".
