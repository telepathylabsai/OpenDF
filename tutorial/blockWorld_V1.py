from opendf.graph.nodes.node import Node
from opendf.applications.smcalflow.nodes.functions import (
    Message, Int, Bool, Str)
from opendf.exceptions.df_exception import (
    DFException, InvalidValueException)
from opendf.defs import posname


# to run:
# PYTHONPATH=$(pwd) python opendf/main.py -n tutorial.blockWorld_V1 -ef tutorial/block_examples.py

class Cube1(Node):
    def __init__(self):
        super().__init__(type(self))
        self.signature.add_sig('color', Str)
        self.signature.add_sig('material', Str)
        self.signature.add_sig('size', Str)


####################################################################


class Cube2(Node):
    def __init__(self):
        super().__init__(type(self))
        self.signature.add_sig('color', Str)
        self.signature.add_sig('material', Str)
        self.signature.add_sig('size', Str, oblig=True)


####################################################################


class Cube3(Node):
    def __init__(self):
        super().__init__(type(self))
        self.signature.add_sig('color', Str)
        self.signature.add_sig('material', Str)
        self.signature.add_sig('size', Str)

    def valid_input(self):
        if 'size' not in self.inputs:
            raise DFException('What size is the cube?', self)


####################################################################


class Color(Node):
    def __init__(self):
        super().__init__(type(self))
        self.signature.add_sig(posname(1), Str)

    def valid_input(self):
        valid_colors = ['red', 'yellow', 'blue']
        dt = self.dat
        if dt is not None:
            if dt.lower() not in valid_colors:
                raise InvalidValueException(
                    message="{} is not a valid color!".format(dt),
                    node=self)
        else:
            raise DFException(message="Please specify a color", node=self)


class BlockSize(Node):
    def __init__(self):
        super().__init__(type(self))
        self.signature.add_sig(posname(1), Str)

    def valid_input(self):
        valid_sizes = ['small', 'big']
        dt = self.dat
        if dt is not None:
            if dt.lower() not in valid_sizes:
                raise InvalidValueException(
                    message="{} is not a valid size!".format(dt),
                    node=self)
        else:
            raise DFException(
                message="Please specify the block size", node=self)


class Material(Node):
    def __init__(self):
        super().__init__(type(self))
        self.signature.add_sig(posname(1), Str)

    def valid_input(self):
        valid_materials = ['metal', 'plastic', 'wood']
        dt = self.dat
        if dt is not None:
            if dt.lower() not in valid_materials:
                raise InvalidValueException(
                    message="{} is not a valid material!".format(dt),
                    node=self)
        else:
            raise DFException(message="Please specify a material", node=self)


class Cube4(Node):
    def __init__(self):
        super().__init__(type(self))
        self.signature.add_sig('color', Color)
        self.signature.add_sig('material', Material)
        self.signature.add_sig('size', BlockSize)

    def valid_input(self):
        if 'size' not in self.inputs:
            raise DFException('What size is the cube?', self)


####################################################################


class Block(Node):
    def __init__(self, out_type=None):
        out_type = out_type if out_type else type(self)
        super().__init__(out_type)
        self.signature.add_sig('id', Int)
        self.signature.add_sig('color', Color)
        self.signature.add_sig('material', Material)
        self.signature.add_sig('size', BlockSize)

    def describe(self, params=None):
        dats_dict = self.get_dats_dict([
            'id', 'size', 'color', 'material'])
        dats_dict.update({'shape': self.typename().lower()})
        key_value_strings = []
        text = ''
        for i in ['size', 'color', 'material', 'shape']:
            if dats_dict[i] is not None:
                key_value_strings.append(dats_dict[i])
        text = ('' if params and 'no_art' in params else ' A ') + (
            ' '.join(key_value_strings))
        if dats_dict['id']:
            text += ', id=%s' % dats_dict['id']

        return Message(text=text)

    def getattr_yield_msg(self, attr, val=None, plural=None, params=None):
        shape = self.typename().lower()
        txt = ''
        if attr in self.inputs:
            val = self.get_dat(attr)
            if attr == 'color':
                txt = 'The color of the %s is %s' % (shape, val)
            elif attr == 'size':
                txt = 'The %s is quite %s' % (shape, val)
            elif attr == 'material':
                txt = 'The %s is made of %s' % (shape, val)
            elif attr == 'id':
                txt = "The %s's id is %s" % (shape, val)
            else:
                txt = 'The %s of the %s is %s' % (attr, shape, val)
        return Message(txt)


class Cube(Block):
    def __init__(self):
        super().__init__(type(self))


class Pyramid(Block):
    def __init__(self):
        super().__init__(type(self))


class Ball(Block):
    def __init__(self):
        super().__init__(type(self))

