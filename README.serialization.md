# OpenDF Serialization

OpenDF dialogues hold data in several forms. In this document, we list the different ways of holding data in OpenDF, how
this data can be (de)serialized, and the advantages and disadvantages of each method.

During the execution of a dialogue, we may want to serialize its state from one turn to the other, or at the end of the
dialogue. Either because we need to store and retrieve dialogues, or because we need to send the dialogue state through
an HTTP API.

The easiest approach to this is to simply pickle the `DialogContext` class and unpickle it when necessary. If one
follows this approach, he/she does not need to worry about any of details described in this file.
However, depending on the dialogue, the pickled object can be too big. In order to address this issues, OpenDF provides
different ways to store the dialogue data, so it can be serialized in a more optimized way.

In the sections below, we list all the places where the user/developer of OpenDF can use to store data, how each of them
are (de)serialized and how to signal OpenDF that this data must be handled by the serialization mechanism. This tutorial
is intended to developers of OpenDF applications, throughout this tutorial, we refer to them as "user".

## Graph Structure

The most straightforward way of holding data is the graph itself. The graph holds data in the form of data nodes.
Currently, there are four types of data nodes (Str, Int, Float and Bool). This data nodes can be combined into more
complex structures, in order to store other forms of data, such as time, dates, and others.

**The user does not need to care about how to (de)serialize this data. It is automatically handled by OpenDF.**

These nodes can be directly generated from P-Expressions and can be also converted back into P-Expressions. Furthermore,
one can use the native Dataflow mechanism of refer and revise.

On the other hand, this make the graph more complex and harder to understand. In addition, sometimes we do not want to
expose part of the data to the `refer` and `revise` mechanisms.

## Node Tags

Tags are data that is stored inside the node, but do not make part of the graph (it is not a node on its own).
The user can define tags in the P-Expression as a normal parameter, by putting the special `^` in front of it, like:

```
Date(year=Int(2022), month=12, 31, ^is_holiday, ^holiday=New Year's Eve)
```

The expression above defines a data with two tags: the first one `^is_holiday` is a flag that indicates that the date is
a holiday; the second `^holiday=New Year's Eve` is a tag with a value, that indicates that the holiday is
the `New Year's Eve`.

These values do not appear in the graph (they are not nodes), but can be useful in some cases.

**Tags are also natively handled by OpenDF, the user does not need to care about it during (de)serialization.**

## Node Counters

A common patter in dialogues is to ask for questions, but if the user refuses to answer it, we might want to stop
asking, it is an optional question. In order to implement this, OpenDF uses counters, to count how many times a give
step was performed

In order to use the counters, the user must first declare the names of the counters to use, these are usually done in
the `__init__` method of the node. To do this call `self.inc_count("max_<COUNTER_NAME>", <MAX_VALUE>)`.
Where `<COUNTER_NAME>` is the name of the counter and `<MAX_VALUE>` is the maximum value it should accept. Notice that
the convention is call `self.inc_count` with a name prefixed with `max_`, to be the maximum of the counter.

There are two methods to use the counters, `self.count_ok(<COUNTER_NAME>)`, which will return `True` iff the counter
value is below the maximum allowed value; and `self.inc_count(<COUNTER_NAME>)`, which will increment the counter value
by one. Optionally, the user can call `self.inc_count(<COUNTER_NAME>, <N>)`, which will increment the counter value
by `<N>`.

**All the counters are automatically handled by OpenDF's (de)serialization mechanism.**

## Node Variables

A natural way of storing data is to put it into fields on the node object. However, this data must be explicitly handled
by the user, since OpenDF does not keep track of internal node fields.

There are two moments when the user should worry about keeping this data.

### Node Duplication

The first one is when a node is duplicated, for instance, during a revise operation. During the duplication of the node,
the internal fields are not copied.
However, the user has the chance to copy this data, by implementing the `on_duplicate(self, dup_tree=False)` method.
This method is called on the node, after the duplication.

In this method, the user has access to the original node (that was duplicated) and can copy the internal variables from
it. To access it, use `self.dup_of`. Finally, this method should return a node, which is typically `self` (the
duplicated node). The snipped below shows an example of how to use it:

```
def on_duplicate(self, dup_tree=False):
    self.internal_value = self.dup_of.internal_value
    return self
```

### Context Packing

The other moment when the user should care about the internal fields of a node is when the `DialogContext` is being
packed. This is a procedure to reduce the size of the `DialogContext`, before serializing it.
This will summarize the nodes as strings, in order to reduce their memory size. Here, the user should take care of
serializing the internal fields as well.

In order to do so, the user must implement two methods: (1) the method `get_internal_data(self)`, that should return a
dictionary containing the internal fields; and (2) the method `set_internal_data(self, internal_data)`, that will
receive the dictionary generated by `get_internal_data(self)` and should put the data back in the fields.

#### get_internal_data

As mentioned above, the method `def get_internal_data(self)` should return a dictionary containing the internal fields.
When implementing this method, the user must be aware that parent classes might also put data into the dictionary. Aside
from calling the super method, a good pratice is to prefix the keys of the dictionary with a class related string, so
they will not conflict with keys from other classes. The snippet below shows an example of how to use it.

```
def get_internal_data(self):
    internal_data = super().get_internal_data()
    internal_data["MyClass.my_internal_data"] = self.my_internal_data

    return internal_data
```

Where `self.my_internal_data` is the internal data of `MyClass`.

#### set_internal_data

In order to deserialize the data, the user must also implement the method `def set_internal_data(self, internal_data)`.
This method receives as parameter the dictionary generated by `get_internal_data(self)`. Again, being aware that parant
classes data might also be presented here. The snippet below shows an example of how to use it.

```
def set_internal_data(self, internal_data):
    super().set_internal_data(internal_data)
    self.my_internal_data = internal_data["MyClass.my_internal_data"]
```

## Context Data

Aside from data stored in nodes, one can also store data in the dialogue context itself. There are two ways of doing
it. (1) Implementing a new dialogue context class; (2) using the `mem` attribute from the original `DialogContext`
class.

### Implementing Own Dialogue Context

The first one is to implement another dialogue context class, inhering from the original `DialogContext`.

The user can add the additional properties to the class, inside the `__init__` method, then he/she has to implement
three methods:

#### get_empty_context

A method to get an empty instance of the dialogue context, the signature is `def get_empty_context(self):`.

#### Pack Context

A method to pack (compress) the current context, the signature is `def pack_context(self):`.
In this method, the user must call the parent method to pack the generic part. Then, it can add the specific data to the
return packed context.

The example below shows how to get the packed part from the parent and then adds the `specific_data` to it.

```
def pack_context(self):
    pack = super().pack_context()
    pack.specific_data = self.specific_data

    return pack
```

In this example, the specific_data is added "as is" to the packed context, then the packed context is serialized using
pickle. One can implement a smarter way to reduce the size of such data, for instance, throwing way things that can be
easily recomputed later.

#### Unpack Context

A method to unpack (decompress) the packed context, the signature is `def unpack_context(self):`.
In this method, the user must call the parent method to unpack the generic part. Then, it can unpack the specific data
and add it to the unpacked context.

The example below shows how to get the unpacked part from the parent and then adds the `specific_data` to it.

```
def unpack_context(self):
    unpack = super().unpack_context()
    unpack.specific_data = self.specific_data

    return unpack
```

In this case, since the data was stored "as is", we just need to assign it to the unpacked context. If we had compressed
it in any way, we would need to decompress it here.

### Storing Generic Data on Dialogue Context

The second one is to use the `mem` dictionary in `DialogContext`. It is a dictionary that has strings as keys and any
arbitrary object as value.

**Data in this dictionary are automatically handled by OpenDF's (de)serialization mechanism.**

There are three methods to access this dictionary:

#### set_mem

`def set_mem(self, nm, val=0):` is used to set a memory data with a name and a value.

#### get_mem

`def get_mem(self, nm):` is used to retrieve a memory data by name.

#### has_mem

`def has_mem(self, nm):` is used to check if a memory data with a given name exists.
