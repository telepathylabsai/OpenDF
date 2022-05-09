# Implementation of SMCalFlow dialogues

The SMCalFlow dataset was released together with the original 
[Semantic Machines paper](https://arxiv.org/abs/2009.11423) (see description there). 

Later, a second version was released (V2), which uses a slightly different format,
but in this work we use V1.

Each turn in the dialogues is annotated with using a LISPRESS (S-Exp) LISP-like format. See their 
[github page](https://github.com/microsoft/task_oriented_dialogue_as_dataflow_synthesis) for a description 
of the syntax/semantics of the S-exp's (see the documents for V1).

## Syntax

For convenience, this work converts the S-exp into python-like expressions (P-exp). 


This is mostly straightforward, where we convert:
- S-exp: *(func arg1 arg2 arg3)*  -->  P-exp: *func(arg1, arg2, arg3)*
- S-exp: *(func :name1 arg1 :name2 arg2)*  -->  Pexp: *func(name1=arg1, name2=arg2)* 

In S-exps, a function can get either named or positional arguments (indicated by
the first letter of the function name being upper or lower case). In the P-exps, 
it's allowed to mix named and positional arguments (as defined in each node's signature).

There are a few special constructs in the S-exps which need special treatment:

#### Sugared get

Shorthand notation to get an input field of a node:

S-exp: *:id (X)*  --> get the id field of X

This is accepted as a P-exp, but internally converted to the P-exp:  *getattr(id, X)*

#### do

This combines several expressions into one expression, where each is executed in turn.

S-exp: *(do exp1 exp2 exp3)*  --> P-exp: do(exp1, exp2, exp3)

#### let

In order to be able to re-use nodes (and computations), the *let* construct can be used to assign a name
to a node, and then re-use it.  In the original dataset, the names used are ONLY x0, x1, ... x6.

The S-exp syntax is: *(let (x0 exp0 x1 exp1 x2 exp2) main_exp)* 

The P-exp syntax is: *do(let(x0, exp0), let(x1, exp1), let(x2, exp2), main_exp)*

Additionally, when using the assigned name, the P-exp uses '$' to indicate the assignment:

S-exp: *(let (x0 Today) (FindEvent :start x0))* --> P-exp: *do(let(x0, Today()), FindEvent(start=$x0))*

P-exps also allow assigning names to nodes "on the fly" by prepending *{name}* before a node, as well
as allowing these names to persist from turn to turn.


#### Constraints

The syntax for constraints has been changed:
- S-exp: *Constraint[X]*  -->  P-exp *X?*
- S-exp: *Constraint[Constraint[X]]*  -->  P-exp *X??*


## Semantics

The dialogues in the dataset are from the domains of:
- Calendar (search, create, modify, delete calendar events)
- People (find people and their information)
- Weather
- Places (location and properties)

The dialogues were collected in a way which encourages natural/unbiased conversations, and then annotated
manually by programs (S-exps) whose execution result answers the user's request.

Unfortunately, the documentation of how the different function and object types, and how they work 
together, were not released, so in this work some design decisions were taken which differ from the 
original implementation.

Style-wise, this package uses a "simplified" annotation scheme, where "deterministic" parts of the annotation
(e.g. type casts, or obligatory steps) are omitted from the annotation (and performed, if necessary, during
the evaluation phase).

Content-wise, a significant difference is the way constraints are represented, handled and combined. 
In the original system, a compositional pattern (nesting/chaining) is used, while in this implementation
the combination is done in a flat way (but each constraint can still be compositional). For example:

S-exp:
```
        (EventOnDate
            :date (NextDOW :dow #(DayOfWeek "TUESDAY"))
            :event (Constraint[Event] :subject (?~= #(String "sales meeting"))))
```
P-exp:
```
       AND(
            starts_at(NextDOW(TUESDAY)),
            has_subject("sales meeting") )
           
```

## Implementation

In addition to the implementation of a base Dataflow Dialogue framework system, this package includes
a partial implementation of a system designed to execute SMCalFlow dialogues.

It still needs (a lot of) work as it's still incomplete:
1. Not all original functions are implemented (hence, some turns can not be executed)
2. Even for implemented functions, some expressions/dialogues may execute incorrectly

Nevertheless, it covers most of the functionality. More importantly, it should give some ideas how to
use a dataflow approach to dialogue implementation.

### Constraint Handling:

Constraints are central in SMCalFlow. For example, when a user wants to search for an event, they 
can specify time/location/attendees they want the event to have. This is represented as event 
constraints. P-exp: *Event?()*

The user may modify (revise) their request by adding more constraints, and this can be repeated 
multiple times. 

Handling these constraints is one of the main difficulties in implementing the SMCalFlow functions, 
since:
- The same constraint may be represented in different ways
- There are multiple ways to (semantically) combine constraints
- The result of the combination needs to be usable by various functions

#### Combining Constraints

Superficially, there are two ways of adding constraints: 
- Discard (clobber) previous constraint(s), and replace with a new constraint. This is typically
explicitly indicated in the user's request ("No, actually I meant X").
- Keep the old constraints and combine it with the new one.

The latter case, can be quite complicated, as both the previous
and the new constraint may themselves actually be complex constraint trees - logical 
combinations of constraints (i.e. basic constraints combined with operators such as *AND, OR, NOT, ...*).

Formally, The constraints (or constraint trees) could be combined either as an OR of the constraints, 
as AND of the  constraints, or possibly some custom logic per object type.

However, natural dialogues implicitly include a lot of heuristic processing, which needs to be accounted 
for in order to achieve the desired behavior. For example:
- The current constraint completely contradicts a previous one.
- The current constraint partially contradicts a previous one.
- The current constraint contradicts a combination of previous constraints

#### Using constraints

Once constraints have been combined, the combined constraint tree can be used. The most common uses are:
- Search over the graph for matching nodes (or search an external DB - see below). This is 
straight-forward and practical, as the search space is typically not very large. 
- Make suggestions which conform with the constraints. Unlike the first case, the target objects/nodes
may not exist yet, and the search space may be very big, so instead of doing a full space search, some 
heuristic reduction of the search space may be used.

#### Modifiers

In this implementation, a design pattern we call "modifier" was used for handling *Event* constraints.

Several such modifiers are defined (e.g. *starts_at, avoid_start, end_at, with_attendee, avoid_attendee, ...*),
which correspond to basic requests from users. Each modifier knows what kind of inputs it can expect,
and how to convert the input into an *Event?()*, where the constraint is formulated in a standardized way.

A user turn is translated into a modifier tree (modifiers combined with operators). Each new modifier tree
(corresponding to the latest turn) is combined with an AND to the existing modifier tree (such that
all the turns are combined under one AND). This may not be general enough for all cases, but it seems to 
be enough for most cases. (The user can explicitly request an OR within one turn).

Finally, a pruning process is performed, where contradiction (partial or whole) are detected, and 
some constraints are discarded.

Practically, the construction of the modifier trees is performed during *revise()* operations, and 
pruning occurs at the function that uses the constraints (e.g. *FindEvents, CreateEvent,...*) just 
before their use. See the code for full details (implementation is still ongoing!).

Other patterns may prove to be better/simpler/more powerful...





## External API - Database

The current implementation uses a relational database system to store data. For now, only Recipient (which represents a
person) and Event nodes are stored in the database. The use of a relational database brings two main advantages:

1. it represents, in a realist way, a possible interface between dataflow and the calendar and contacts of the user;
2. it allows us to transform constraints into SQL query and process them in the database system directly.

For now, the database is constructed at the beginning of the execution of the system and is populated with stub data. At
the end of the execution, the database is destroyed. This is a proof-of-concept, in a real environment, the system
should connect to an existing database and use the data from there.

#### Fallback Search

If a *refer* node is not able to find a node in the graph, that conforms with the searching constraints, it can call a
fallback search that will try to find the corresponding node elsewhere.

In the case of Recipient and Event nodes, which are represented in the relational database, the fallback search will try
to find corresponding entries directly in the database, by transforming the constraints into a SQL query.

### Event Suggestion

When the user asks to create a new event, the dataflow system must answer with a list of event suggestions that conforms
with the constraints from the user's requested. There are several ways to generate the suggestions based on the set of
constraints. Thus, we implemented an EventFactory, that is responsible for generate the event suggestions.

Currently, there are 4 implementations of the `EventFactory`. Two of them (`SimpleEventFactory` and
`IteratorEventFactory`), are naive (but fast) implementations that only cover simple constraint tree; while the other
two (`DatabaseEventFactory` and `DatabaseStartDurationEventFactory`) cover much more general constraint trees, at the
cost of a longer run time.

The `DatabaseEventFactory` and `DatabaseStartDurationEventFactory` uses a relational database system in order to
generate all the possible combinations of start and end timepoints for the event, then it selects only the ones that
conforms with the constraints.

Several optimizations can be applied to these factories, but most of them are heavily dependent on the constraint tree.
Thus, there is a tradeoff between generality and performance.

`DatabaseStartDurationEventFactory` is the default factory, but it can be changed by changing the value of
the `EnvironmentDefinition.event_factory_name` variable in the `opendf/defs.py` file.

`DatabaseStartDurationEventFactory` generates a list of possible event start and end timeslot pairs by combining the
values from the possible starting times and the possible event durations. These values are generated according to the
variables `event_suggestion_period`, `minimum_slot_interval`, `minimum_duration` and `maximum_duration_days`, defined in
the `opendf/defs.py` file; and are stored in the database.