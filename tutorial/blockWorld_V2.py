from opendf.applications.smcalflow.nodes.functions import *
from opendf.graph.nodes.node import Node
from opendf.graph.nodes.framework_functions import get_refer_match
from opendf.applications.smcalflow.nodes.functions import (
    Int, Bool, Str)
from opendf.utils.utils import Message
from opendf.exceptions.df_exception import (
    DFException, InvalidValueException)
from opendf.exceptions.__init__ import re_raise_exc
from opendf.defs import posname


# to run:
# PYTHONPATH=$(pwd) python opendf/main.py -n tutorial.blockWorld_V2 -ef tutorial/block_examples.py


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



class Position(Node):
    def __init__(self):
        super().__init__(type(self))
        self.signature.add_sig('x', Int)
        self.signature.add_sig('y', Int)

    def describe(self, params=None):
        prms = []
        for i in ['x', 'y']:
            if i in self.inputs:
                d = self.get_dat(i)
                if d is not None:
                    prms.append('%s=%s' % (i, d))
        s = ''
        if prms:
            s = '(' + ','.join(prms) + ')'
        return Message(s)

    # convenience
    def get_pos(self):
        return self.get_dat('x'), self.get_dat('y')


class PBlock(Node):
    def __init__(self):
        super().__init__(type(self))
        self.signature.add_sig('block', Block)
        self.signature.add_sig('position', Position)

    def describe(self, params=None):
        msg = ''
        if 'block' in self.inputs:
            # has text: "big red wood cube, id=1"
            m = self.input_view('block').describe(params=params)
            msg += m.text
        if 'position' in self.inputs:
            m = self.input_view('position').describe()
            if m.text:
                msg += ' at ' + m.text
        return Message(msg)

    def get_pos(self):
        pos = self.input_view('position')
        return pos.get_pos() if pos else None

    def func_FN(self, obj, fname=None, farg=None, op=None, mode=None):
        if fname == 'left_of':
            return pos_is_left_of(obj, farg)
        return False


class Board(Node):
    def __init__(self):
        super().__init__(type(self))
        # blocks is a SET of valid PBlocks - correct positions and correct blocks
        self.signature.add_sig('blocks', PBlock, multi=True)
        self.costs = None  # dictionary: {(x,y): cost}
        self.size = None

    def get_pblocks(self):
        if 'blocks' in self.inputs:
            return self.input_view('blocks').get_op_objects()
        return []

    def init_grid(self, size, rand=False):
        self.size = size
        self.costs = {}
        for x in range(size):
            for y in range(size):
                self.costs[(x, y)] = random.randint(1, 4) if rand else 1 + (x + y) % 4

    def get_position(self, id):
        # returns a tuple with pos_y and pos_x
        pblocks = self.get_pblocks()
        for i in pblocks:
            if i.get_ext_dat('block.id') == id:
                return i.get_pos()

    def describe(self, params=None):
        pos = {}
        pblocks = self.get_pblocks()
        for pb in pblocks:
            p = pb.input_view('position')
            x, y = pb.get_pos()
            bid = pb.get_ext_dat('block.id')
            pos[(x, y)] = bid

        ss = []
        for y in range(self.size - 1, -1, -1):
            s = []
            for x in range(self.size):
                if (x, y) in pos:
                    s.append('%s*%s' % (self.costs[(x, y)], pos[(x, y)]))
                else:
                    s.append('_%s_' % self.costs[(x, y)])
            ss.append(s)
        s = '  NL  '.join([' '.join(i) for i in ss])

        # calculate and append total board costs
        s = s + '  NL  ' + 'total cost: ' + str(self.calculate_total_cost())
        return Message(s)

    def calculate_total_cost(self):
        block_costs = []
        pblocks = self.input_view('blocks')  # this would be a SET
        if pblocks:
            for i in pblocks.inputs:
                pb = pblocks.input_view(i)  # by construction - these are CORRECT PBlocks
                pos = pb.input_view('position')
                x, y = pos.get_dats(['x', 'y'])
                block_costs.append(self.costs[(x, y)])
        return sum(block_costs)

    def add_block(self, new_block, position_x, position_y):
        if position_x < 0 or position_x > self.size - 1:
            raise DFException("This position_x is invalid!", self)

        if position_y < 0 or position_y > self.size - 1:
            raise DFException("This position_y is invalid!", self)

        new_id = new_block.get_dat('id')

        pblocks = self.get_pblocks()
        for pb in pblocks:
            x, y = pb.get_pos()
            if (position_x, position_y) == (x, y):
                # rearrange context.goals?
                raise DFException("This position is already taken!", self)

            bid = pb.get_ext_dat('block.id')
            if bid == new_id:
                raise DFException("This ID already exists!", self)

        new_pblock, _ = self.call_construct_eval(
            'PBlock(block=%s, position=Position(x=%d, y=%d))' %
            (id_sexp(new_block), position_x, position_y), self.context)

        if not pblocks:  # no blocks so far - create SET to hold blocks
            pblocks, _ = self.call_construct_eval('SET(%s)' % id_sexp(new_pblock), self.context)
            pblocks.connect_in_out('blocks', self)
        else:
            self.input_view('blocks').add_pos_input(new_pblock)
        return new_pblock

    def move_block(self, id, position_x, position_y):
        pblocks = self.get_pblocks()
        if id not in [i.get_ext_dat('block.id') for i in pblocks]:
            raise DFException("No block with ID %s" % id, self)

        for i in pblocks:
            x, y = i.get_ext_dat('position.x'), i.get_ext_dat('position.y')
            if (x, y) == (position_x, position_y):
                raise DFException("Position (%s,%s) is already taken!" % (position_x, position_y), self)

        if position_x < 0 or position_x > self.size - 1:
            raise DFException("This position_x is invalid!", self)

        if position_y < 0 or position_y > self.size - 1:
            raise DFException("This position_y is invalid!", self)

        # move block - this is destructive!
        for i in pblocks:
            bid = i.get_ext_dat('block.id')
            if bid == id:
                posx, posy = i.get_ext_view('position.x'), i.get_ext_view('position.y')
                if posx:  # should always be true
                    posx.data = position_x  # this is destructive!
                if posy:  # should always be true
                    posy.data = position_y  # this is destructive!



class InitGrid(Node):
    def __init__(self):
        super().__init__(type(self))
        self.signature.add_sig('rand', Bool)
        self.signature.add_sig('size', Int)

    def exec(self, all_nodes=None, goals=None):
        size = self.get_dat('size')
        if not size:
            size = 7
        rand = self.inp_equals('rand', True)
        # boards = [g for g in self.context.goals if g.typename()=='Board']
        boards = get_refer_match(self.context, all_nodes, goals, pos1='Board?()')
        if not boards:
            raise DFException('Please create a Board first!', self)

        board = boards[0]
        board.init_grid(size, rand)
        s = board.describe().text


class ShowBoard(Node):
    def __init__(self):
        super().__init__(type(self))

    def exec(self, all_nodes=None, goals=None):
        txt = ''
        boards = get_refer_match(self.context, all_nodes, goals, pos1='Board?()')
        if not boards:
            txt = 'No Board exists'
        else:
            board = boards[0]
            if board.size is None:
                txt = 'The board is uninitialized'
            else:
                txt = board.describe().text
        self.context.add_message(Message(txt, node=self))


class AddBlock(Node):
    def __init__(self):
        super().__init__(PBlock)
        self.signature.add_sig('block', Block)
        self.signature.add_sig('x', Int)
        self.signature.add_sig('y', Int)

    def exec(self, all_nodes=None, goals=None):
        block = self.input_view('block')
        if not block:
            raise DFException('Please specify the block to add', self)
        x, y = self.get_dats(['x', 'y'])
        if x is None:
            raise DFException('Please specify the x position', self)
        if y is None:
            raise DFException('Please specify the y position', self)
        boards = get_refer_match(self.context, all_nodes, goals, pos1='Board?()')
        if not boards:
            raise DFException('Please create a Board first!', self)
        board = boards[0]
        if board.size is None:
            raise DFException('Please init the grid first!', self)
        try:
            new_pblock = board.add_block(block, x, y)
        except Exception as ex:
            re_raise_exc(ex, self)
        # s = board.describe().text
        # self.context.add_message(Message(s, node=self))
        self.set_result(new_pblock)


class MoveBlock(Node):
    def __init__(self):
        super().__init__(type(self))
        self.signature.add_sig('id', Int)
        self.signature.add_sig('position', Position)

    # get block, verify ID
    # look at the board, check if position is given and valid
    # add block to the board
    def exec(self, all_nodes=None, goals=None):
        boards = get_refer_match(self.context, all_nodes, goals, type='Board')

        if not boards:
            raise DFException('No board found! Please initialize the game.', self)
        else:
            board = boards[0]

            # get block from input
            id = self.get_dat('id')
            if id is None:
                raise DFException('Which block ID are you trying to move?', self)
            else:
                pos = self.input_view('position')
                if not pos:
                    raise DFException('Please specify the position to place the block', self)
                else:
                    block_position_x = pos.get_dat('x')
                    if block_position_x is None or not 0 <= block_position_x < board.size:
                        raise DFException('Invalid / missing x possition', self)
                    block_position_y = pos.get_dat('y')
                    if block_position_x is None or not 0 <= block_position_x < board.size:
                        raise DFException('Invalid / missing y possition', self)

                    # call function from Board to check
                    # add_block may raise exceptions, catch them
                    # with 'try', see in init
                    try:
                        board.move_block(
                            id, block_position_x,
                            block_position_y)
                    except Exception as ex:
                        re_raise_exc(ex, self)
                    # self.context.add_message(Message(board.describe().text, node=self))
                    return


############################################################################################################


class IsLeftOf1(Node):
    def __init__(self):
        super().__init__(out_type=Bool)
        self.signature.add_sig(posname(1), PBlock, alias='pblock1')
        self.signature.add_sig(posname(2), PBlock, alias='pblock2')

    def exec(self, all_nodes=None, goals=None):
        pblock1 = self.input_view('pblock1')
        pblock2 = self.input_view('pblock2')
        answer = 'False'
        if pblock1 and pblock2:
            x1 = pblock1.get_ext_dat('position.x')
            x2 = pblock2.get_ext_dat('position.x')
            answer = x1 < x2
        return_node, _ = self.call_construct_eval('Bool(%s)' % answer, self.context, add_goal=False)
        self.set_result(return_node)


############################################################################################################


# same as IsLeftOf1, except we added a definition for yield_msg
class IsLeftOf2(Node):
    def __init__(self):
        super().__init__(out_type=Bool)
        self.signature.add_sig(posname(1), PBlock, alias='pblock1')
        self.signature.add_sig(posname(2), PBlock, alias='pblock2')

    def exec(self, all_nodes=None, goals=None):
        pblock1 = self.input_view('pblock1')
        pblock2 = self.input_view('pblock2')
        answer = 'False'
        if pblock1 and pblock2:
            x1 = pblock1.get_ext_dat('position.x')
            x2 = pblock2.get_ext_dat('position.x')
            answer = x1 < x2
        return_node, _ = self.call_construct_eval('Bool(%s)' % answer, self.context, add_goal=False)
        self.set_result(return_node)

    def yield_msg(self, params=None):
        block1 = self.get_ext_view('pblock1.block')
        block2 = self.get_ext_view('pblock2.block')
        if block1 and block2:
            txt1 = block1.describe(params=['no_art']).text
            txt2 = block2.describe(params=['no_art']).text
            if self.res.dat == True:
                txt = 'Yes,  NL  %s NL is left of  NL  %s' % (txt1, txt2)
            else:
                txt = 'No,  NL  %s NL is NOT left of  NL  %s' % (txt1, txt2)
        else:
            txt = "No"
        return Message(txt)


############################################################################################################


# allow multiple blocks as input
class IsLeftOf3(Node):
    def __init__(self):
        super().__init__(out_type=Bool)
        self.signature.add_sig(posname(1), PBlock, alias='pblock1')
        self.signature.add_sig(posname(2), PBlock, alias='pblock2')

    def exec(self, all_nodes=None, goals=None):
        pblocks1 = self.input_view('pblock1').get_op_objects()
        pblocks2 = self.input_view('pblock2').get_op_objects()
        answer = 'False'
        for item1 in pblocks1:
            for item2 in pblocks2:
                x1 = item1.get_ext_dat('position.x')
                x2 = item2.get_ext_dat('position.x')
                if x1 < x2:
                    answer = 'True'
        return_node, _ = self.call_construct_eval('Bool(%s)' % answer, self.context, add_goal=False)
        self.set_result(return_node)

    def yield_msg(self, params=None):
        blocks1 = self.input_view('pblock1').get_op_objects()
        blocks2 = self.input_view('pblock2').get_op_objects()
        if blocks1 and blocks2:
            if len(blocks1)==1 and len(blocks2)==1:
                txt1 = blocks1[0].describe(params=['no_art']).text
                txt2 = blocks2[0].describe(params=['no_art']).text
                if self.res.dat == True:
                    txt = 'Yes,  NL  %s NL is left of  NL  %s' % (txt1, txt2)
                else:
                    txt = 'No,  NL  %s NL is NOT left of  NL  %s' % (txt1, txt2)
            else:
                txt = 'Yes' if self.res.dat == True else 'No'
        else:
            txt = "No"
        return Message(txt)


############################################################################################################

# make the core logic of IsLeftOf into a function (not node)
#   - can be used from other places as well
# - block1 is ONE Node (typically a PBlock), block2 may be a SET
def pos_is_left_of(block1, block2):
    x1 = block1.get_ext_dat('position.x')
    if x1 is not None:
        blocks2 = block2.get_op_objects()
        for b2 in blocks2:
            x2 = b2.get_ext_dat('position.x')
            if x2 is not None:
                if x1 < x2:
                    return True
    return False


class IsLeftOf(Node):
    def __init__(self):
        super().__init__(out_type=Bool)
        self.signature.add_sig(posname(1), PBlock, alias='pblock1')  # may be SET or PBlock
        self.signature.add_sig(posname(2), PBlock, alias='pblock2')  # may be SET or PBlock

    def exec(self, all_nodes=None, goals=None):
        pblocks1 = self.input_view('pblock1').get_op_objects()
        pblock2 = self.input_view('pblock2')  # may be SET or PBlock
        answer = 'False'

        for item1 in pblocks1:
            if pos_is_left_of(item1, pblock2):
                answer = 'True'
        return_node, _ = self.call_construct_eval('Bool(%s)' % answer, self.context, add_goal=False)
        self.set_result(return_node)

    def yield_msg(self, params=None):
        blocks1 = self.input_view('pblock1').get_op_objects()
        blocks2 = self.input_view('pblock2').get_op_objects()
        if blocks1 and blocks2:
            if len(blocks1)==1 and len(blocks2)==1:
                txt1 = blocks1[0].describe(params=['no_art']).text
                txt2 = blocks2[0].describe(params=['no_art']).text
                if self.res.dat == True:
                    txt = 'Yes,  NL  %s NL is left of  NL  %s' % (txt1, txt2)
                else:
                    txt = 'No,  NL  %s NL is NOT left of  NL  %s' % (txt1, txt2)
            else:
                txt = 'Yes' if self.res.dat == True else 'No'
        else:
            txt = "No"
        return Message(txt)
