# How to contribute to OpenDF

## License

Work in progress...

## Where to add your new nodes

Each application in OpenDF should have a corresponding package
under `opendf/applications`.
Inside this package, should be a place for the node, usually a package
called `nodes`.

### Creating new nodes for existing application

If one want to create new nodes for an existing application, he/she should find
a suitable place,
under `application` package, in order to place the new nodes, accordingly with
the node function.

### Experimenting with new nodes

If one wants to experiment with new nodes/applications, he/she can create new
nodes in
`applications/sandbox/sandbox.py`. These nodes will be automatically imported
by the node factory.

Please, do not include nodes under the `sandbox` space on your pull request.

### Creating a new application

If one wants to create a new application, he/she should create a new package
for this application,
under the `application/external` package. In this package, one can include all
the logic for the application.

We suggest a separation of the application `Node` from the non-graph part, for
instance,
by concentrating the `Nodes` into a dedicated package.

## How to load the nodes

In order to use the nodes of your application, one should call
the `fill_type_info` function.
This function will load all the subclasses of `Node` into the `NodeFactory`
singleton class.

Make sure to import the desired nodes, before calling the `fill_type_info`
function;
otherwise, your nodes will not be imported.

Nodes from `smcalflow` and `sandbox` applications are imported by default.
Remember that nodes are instantiated by name, from the OpenDF expression.

If there is a conflict of names, one node will be select (arbitrarily).
In case of problems selecting the correct nodes, one can implement his/her
own `fill_type_info` function,
importing only the desired nodes.

## How to implement new nodes

In order to implement new nodes, one should follow the steps below:

### Create a subclass of Node

The first step of implementing a new node is to create a subclass of the base
`Node` class.

### Add the signature in `__init__`

Inside the `__init__` method of the subclass, one must call the construction
of the parent node, passing to it the type of the result of the node.
By default, it is the same type of the node.

Then, one should add the inputs of the node to its signature, by calling the
method `self.signature.add_sig(.)`.

### Implement `valid_input` (optional)

Optionally, one would want to implement the `valid_input` method.
This method is called before the main logic of the node, represented by the
`exec` method, and can be used to validate the input of the given node.

By this point, all the inputs of the node were already successfully executed.

### Implement `exec` (optional)

Then, one should implement the `exec` node. This is the place where the logic
of the node should be. In case of a node that only holds data, this method
might not be necessary.

### Data inside node

In Dataflow, nodes are often copied around (when revised). The data of a node
that is not in its inputs (a local variable, for example) is not copied.

If coping this data is necessary, one should explicitly do so by implementing
the `on_duplicate(.)` method of the node.

One can find the data by accessing the local variable `self.dup_of`, which
points to the node used to create the copy.

### Other Functions

The function above are the main ones when implementing a new node.
However, there are other functions that could be needed, depending on the
logic of the node.

We refer the reader to the code, in order to see which functions might be
useful for him/her.

### Examples

In order to have an overview of how to implement new nodes, we suggest to look
at other implemented nodes.

The file `opendf/applications/smcalflow/nodes/time_nodes.py` contains several
simple nodes related to date and time, for the SMCalFlow application,
and can be a good starting point to get familiar with the node implementation.
