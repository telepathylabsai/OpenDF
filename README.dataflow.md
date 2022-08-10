# Dataflow Dialogue Framework

This implementation of the dataflow dialogue framework follows the ideas of the original 
[Semantic Machines paper](https://arxiv.org/abs/2009.11423), i.e.:

1. Dataflow expressions correspond to computational graphs made of object/function nodes.
2. The dialogue history is kept as a set of computational graphs.
3. The system uses object-oriented design, where nodes are strongly typed.
4. The graphs are constructed in a top-down construction phase.
5. The graphs are then evaluated (executed) in a bottom-up evaluation phase.
6. In case the evaluation encounters an error (e.g. wrong or missing input), as exception is raised.
7. The exceptions are explicitly used for error recovery (e.g. generating a request for the missing information).
8. The framework has a refer() operation, which allows to re-use previously mentioned nodes.
9. The refer() operation may have a fall back method in case it could not find a node in the graph (e.g. search an external DB).
10. The system has a revise() function, which allows to modify and re-use previous computations.

The description of the system is general enough, so that different implementations are possible. 
The current implementation is an initial basic suggestion, which should serve as a base for experimentation
and further improvements.


Below is a high level description of the implementation, intended to give the reader a general 
understanding of how the different parts work together.

For more details, please see the code.

## Dataflow Expressions

In the original paper, dataflow expressions are in a LISPRESS format - a LISP-like format 
, also referred to as S-expressions  (or S_exp). 

The current implementation uses a Python-like format for dataflow expressions (also referred to
as P-exp). This is for convenience only, in all respects, they have equivalent semantics, and
we often interchange the use of the terms S-exp / P-exp.

## Nodes

Nodes are the building blocks of the graphs. The base *Node* class:

1. Defines the data fields which each node uses
2. Implements the basic utilities allow combining nodes into graphs: handling inputs, result
3. Implements multiple utilities for accessing data, traversing graphs, and more.

Each graph object/function is implemented as a separate class, which is derived from the base *Node* class.

Each (derived) node is defined by: 

1. A signature, which describes inputs as well as result type. For each input, a name and a type 
(or types) is given, as well as defining some optional extra parameters.
2. (optional) logic to test if inputs are valid (possibly raise exceptions if not)
3. (optional) logic to execute during the evaluation phase (possibly raise exceptions if errors encountered)

In the current implementation, there are a few node types which correspond to "base data types": 
Int, Float, Str, Bool. These nodes actually hold data (actual values). (this set is extensible)
All other nodes types do not hold values - typically they have inputs (but not always).

The set of node types is extensible. You can define new node types, and then use them in expressions by 
mentioning their names.

Evaluation of a node sets the node's result pointer. It can point to a previously existing node, 
a newly created node (which was created by the execution logic). 
By default (e.g. when no execution logic is defined), the result pointer of a node 
points to itself.

Nodes with no evaluation logic are sometimes referred to as *object* nodes (as opposed to *function* nodes),
but the difference is not always meaningful (when drawing the graphs, objects are drawn as rectangles, 
and functions are drawn as ellipses).

As an example for an *object* node, we may have *Employee*, which has the fields (inputs): 
first_name (Str), last_name (Str), employee_id (Int). It may have logic to test the validity of the inputs
(e.g. that they are all given, and of the correct type, and if not request the missing field)
but no logic to execute during evaluation. 

As an example for a *function* node we may have a node FindManager, which has an input Employee, 
execution logic which finds the manager of the employee, and sets that a result to point to the Employee 
node corresponding to the manager.

### Constraints / Queries

While not absolutely necessary, constraints are very useful, so a constraint handling mechanism has been
built into the base *Node*. Constraints are typically used in partial specification of objects (i.e. 
specifying only part of the necessary inputs), which are then typically used as search queries (we sometimes
interchange the terms *constraints* and *queries*). We use the character "?" to indicate a query.

For example, *Employee?(first_name=John)* is a partial specification of an Employee, which can then be used
to search for matching objects, e.g. by executing: *refer(Employee?(first_name=John))*.

Queries can have different "levels" - we could search for an object, or we could search for a query, 
(this can go on).  For example - we could search for places which had a query about Employees:
*refer(Employee??())* -  "*Employee??*" indicates we're looking for an "*Employee?*" node, and would match the
"*Employee?(first_name=John)*" node in the example above.

In practice, this is implemented as having a flag in each node indicating the constraint_level.

Given a constraint node *nodeA* (i.e. a constraint node, which is the root of a constraint subtree), 
we can text if another node  *nodeB* (at the top of another subtree) matches the constraint, we can
call: *nodeA.match(nodeB)*. This will traverse the constraint tree and determine if the candidate object
matches the constraint.


### operators

Operators are a special subclass of nodes, which is used mostly to construct mode complex constraints. 
Two types of operators are:
1. Aggregators: AND, OR, ANY, NONE, ...
2. Qualifiers: LT, GT, LE, EQ, ...

The *match()* function accepts operators.

The special aggregator SET is used for indicating a collection of nodes (not necessarily constraints).

### Input View

In the SMCalFlow dataset, the (linguistically motivated) terms Intension / Extension 
are prominently used in the SMCalFlow dataset, and correspond to the modes of reference.

In this implementation, these terms are not used. Instead, we differentiate between two cases of using an input:
- use the input node itself
- use the result of the input node

A simple example: say we have the expression *Add(Add(1,2), Add(3,4))* , where *Add* is a function which
adds two integers. If the next request is "replace Add(1,2) with Add(5,6)", there are several ways to
interpret this:
1. Replace the expression Add(1,2) with the expression Add(5,6)  --> *Add(Add(5,6), Add(3,4))*
2. Replace the expression Add(1,2) with the result of Add(5,6)   --> *Add(11, Add(3,4))*
3. Replace the result of  Add(1,2) with the expression Add(5,6)  --> *Add(Add(1,2), Add(Add(5,6),4))*
4. Replace the result Add(1,2) with the result of Add(5,6)       --> *Add(Add(1,2), Add(11,4))*

In this implementation, we use a non-standard name for this aspect, hoping to avoid confusion with 
linguistic jargon. The term used is "*view*", and two modes are supported:
- VIEW_INT (use the node itself)
- VIEW_EXT (use the (transitive) result of the node)

In practice, in the overwhelming majority of cases, we use the result of the input node.
In fact, there could be applications which would need additional view modes.

The view mode can be specified in the signature of a node, or overridden in a specific expression by 
special syntax.  Use *Node.inputs[name]* to get the input node, *Node.inputs[name].res* to get the 
transitive result of the input, and *Node.input_view(name)* to get the pre-selected view of the input.

### Extending Nodes

It is expected that in addition to the implementation of additional node types (objects/functions), the 
functionality of the base *Node* type will be extended.

In the current implementation, each node has a dictionary (*Node.tags*), which can be used as
general purpose storage, which can be accessed and used by its execution logic. Tags can be set either 
from within the execution logic of nodes, or from the P-exp using the syntax *^tagname=tagvalue*,
e.g. *FindManager(John, ^xx=5)* corresponds to the same graph as *FindManager(John)*, except that the
*FindManager* node will have *xx=5* in its tags dictionary.

Tags are a convenient (hacky) way to add functionalities without adding new fields to the base Node. Once
some functionalities prove to be widely useful, they can be added to the base Node, and may deserve their
own syntax to allow setting them directly from dataset expressions. 

## Node Factory

The *NodeFactory* class is responsible for creating new nodes. 

In order to use it, it first needs to be initialized, by calling a function (e.g. fill_type_info), 
which automatically scans the classes in the imported files and collects all the node types defined there.

Once *NodeFactory* is initialized, it can generate a new node, given the *name* of the node 
class (e.g. "*Employee*" / "*Employee??*").

## Dialogue Context

The class *DialogContext* holds the context (history) of the conversation. 
Typically, each user turn is represented by one computational graph (but it's possible to have more 
than one). 

The term *goal* refers to the top node of the computation. *DialogContext* collects these goals, so that 
*refer* and *revise* operations can look over previous computations.

In addition to goals, *DialogContext* also holds:
- An index to all the nodes created so far - each node gets a unique id number, which can later be reused. 
   To directly reuse a node (e.g. node #17) use the syntax: *$#17*
- Assignment list: we allow assigning a name to a node, which can later be re-used. 
   The syntax for assignment is e.g.  
   *{x1}Employee?(first_name=John)*, and for reuse: *refer($x1)*
- Additional information which needs to be carried from one turn to the next - 
  e.g. hints and suggestions (see explanations below)



## Processing steps

Given a P-exp as input, the following steps take place 
(after initializing *NodeFactory* and *DialogContext*):

### Construction

The expression is parsed, and constructed in a top-down manner. 

For example, constructing the graph for the expression "*refer(Employee?(first_name=John))*", 
will start by creating a node of type
*refer* (in this example we'll call it nodeR). *Refer* nodes accept positional arguments 
(as well as named arguments). positional arguments are 
automatically named 'pos1', 'pos2', ...  

Input 'pos1' of *refer* can get any type of input node (this is indicated in the signature as type *Node*).

In this case, we create a node of type *Employee* (call it nodeE), mark it as a 
constraint (level 1: *Employee?*), and connect it to nodeR: we set nodeR.inputs['pos1'] = nodeE.

In addition, for each node, we store a list of nodes for which it is used as input (and the name used for 
that input). This allows us to traverse the graph upwards. 
In this case we add ('pos1', nodeR) to nodeE.outputs.

Next, the input *first_name* of *Employee* is followed. 
Note that the full notation would be "*Employee?(first_name=Str(John))*", but type inference allows to omit
the explicit mention of *Str*. The signature of *Employee* for *first_name* 
indicates an input type of *Str* (which is one of the base data types). Since "John" is not a known node type, 
but can be interpreted as a string value, an *Str* node is created (call it nodeS), and its date (value) is set to the string "John".
A special syntax ("#") can be used to force a token to be interpreted as a node of a type which accepts 
the value: e.g. "#John" (Str), "#10" (Int), "#2.5" (Float), "#True" (Bool).

Finally, we set nodeE.inputs['first_name']=nodeS, and nodeS.outputs.append(('first_name', nodeE)).

Construction also handles the special cases of assignments ("*refer($x1)*") and node reuse by index number ("*$#17*").

If an error is detected during construction (e.g. use of an unknown node type, wrong syntax), 
an exception will be thrown (as an exception indicates a bad expression, it typically indicates a problem
with the expression generation, not with the user request itself). 

Note that graph construction (as well as evaluation) can also be called dynamically from the node 
execution logic, which is much more convenient than programmatically constructing graphs.

### Pos-Construction Check

A Post construction step traverses the generated graph in a top-to-bottom way, 
checking for type correctness, and raising an exception if a problem is detected.


### Evaluation

The evaluation phases traverses the graph in a bottom-up way.
For each node the steps are:
1. Execute the logic for testing input validity (if such logic exists). For convenience,
input validity is checked separately for "normal" nodes and for constraint nodes -
 *Node.valid_input()*  and *Node.valid_constraint()*
2. Execute the logic for node evaluation  - *Node.exec()*. This logic may create new nodes, 
as well as new goals.
3. Set the result pointer for the node (if not set already).

An exception may be thrown either of *valid_input, valid_constraint, exec*. 
There are two types of exceptions:
1. Exceptions which were intentionally raised, in order to communicate an error to the user;
2. Exceptions which were not raised unintentionally, or that are not intended for the user.

In the current implementation this is indicated by the arguments given to the exception. 
Intentional, communicative exceptions should include 2 (or more) arguments: a message (string), and a node 
(typically the node which raised the exception).
Unintentional exceptions (raised by python), or intentional but uncommunicative exceptions include only 
the message argument. When encountering a communicative exception, the message is conveyed to the user, 
and execution continues (typically stopping the evaluation process of the current graph, and moving to
the next turn). For unintentional or uncommunicative exceptions, execution is stopped, and the call stack
is dumped to help debugging.

### Drawing

Dataflow graphs are drawn by functions in graph.draw_graph.py. The drawing can be controlled by variables
in *defs.py* (some of them can be set from the command line).

With the help of these variables, it is possible to either show or hide various pieces of information, and
to reduce clutter in the drawing (which can get overwhelming for larger graphs).

For example, the drawing can be controlled to:
- Draw only the last N turns
- Draw separate turns in separate boxes
- Collapse (summarize) sub-graphs into single nodes
- Draw the P-exp/S-exp and/OR the dataflow graph
- Etc.


## Entry points

There are several versions of the main program: 

### dialog.py

This is the initial version of the system, as described above.

### main.py

The original paper describes an application with strict type constraints on node inputs. This has advantages, 
e.g. when translating the user's natural language to P-exp, but on the other hand, it tends
to lead to more complicated expressions, where various type casts have to be annotated explicitly.

A different way, which is taken in main.py, is to omit these explicit type casts from the expressions 
(making it easier to create and understand the expressions), and then at run time automatically add these
missing steps (such as type casts and format conversions).

In order to achieve this, one more processing step is added after the post-construction test, in which 
the constructed tree is transformed in a top-to-bottom way. Note that at that point, the nodes have not yet
been evaluated. If the transformation needs to have knowledge of the results of its inputs, additional
transformation logic can be added e.g. at the valid_input() function of that node (at that point, all input
nodes are guaranteed to have been evaluated).

This is the default (and most up-to-date) entry point. Use this one. 

### dialog_txt.py

The Semantic Machines paper also explored using the dataflow system for a non-dataflow
dataset. In their example, dialogues from the MultiWOZ dataset (whose annotation is based on intents and 
entities) are executed as dataflow dialogues.

dialog_txt.py was implemented to follow this idea - instead of getting a P-exp as input,
it gets the results of an intent/entity NLU. 

An additional translation step is added before construction, where the input intents and entities
are converted to one or more P-exps. Custom translation logic is optionally implemented 
for each node type. 

Currently it does not work (as the application it was
used for is not part of this release). We hope to add a simple example soon.

### dialog_simplify.py

This program simplifies dialogues rather than execute them. It has two work modes:
- Simplifying a single S-exp (from the file examples.simplify_examples.py), in which case 
the expression is simplified, and then the original and simplified versions are drawn.
- Simplifying a whole file, in which case all the dialogues in a .jsonl file (the SMCalFlow train 
or validation files) are simplified, and a new .jsonl file is created. 

an additional program (*show_simplification.py*) can be used to search and display original
and simplified expressions, together with the dialogue context.


