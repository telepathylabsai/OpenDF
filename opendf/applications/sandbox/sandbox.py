import random
from opendf.applications.smcalflow.nodes.functions import *
from opendf.graph.nodes.node import Node
from opendf.graph.nodes.framework_functions import get_refer_match
from opendf.applications.smcalflow.nodes.functions import (
    Message, Int, Bool, Str)
from opendf.exceptions.df_exception import (
    DFException, InvalidValueException)
from opendf.exceptions.__init__ import re_raise_exc
from opendf.defs import posname


class Mult(Node):
    def __init__(self):
        super().__init__(Int)
        self.signature.add_sig(posname(1), Int, True)
        self.signature.add_sig(posname(2), Int, True)

    def exec(self, all_nodes=None, goals=None):
        p1 = self.get_dat(posname(1))
        p2 = self.get_dat(posname(2))
        r = p1 * p2
        d, e = self.call_construct_eval('Int(%d)' % r, self.context)
        self.set_result(d)


# ===================== BlockWorld NODES ==========
# to be used with the application developer tutorial.
# This should be refactored into separate files reflecting progressive versions of the application in the tutorial.
# Until then, you'll have to comment/uncomment different parts of the code.
# (also - need to clean this file - some parts are unused / duplications).

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
                    prms.append('%s=%s' %(i,d))
        s = ''
        if prms:
            s = '(' + ','.join(prms) + ')'
        return Message(s)

    # convenience
    def get_pos(self):
        return self.get_dat('x'), self.get_dat('y')


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



class Cube2(Node):
    def __init__(self):
        super().__init__(type(self))
        self.signature.add_sig('color', Str)
        self.signature.add_sig('material', Str)
        self.signature.add_sig('size', Str, oblig=True)

    def valid_input(self):
        if 'size' not in self.inputs:
            raise DFException('What size is the cube?', self)


class Cube1(Node):
    def __init__(self):
        super().__init__(type(self))
        self.signature.add_sig('color', Color)
        self.signature.add_sig('material', Material)
        self.signature.add_sig('size', BlockSize)

    def valid_input(self):
        if 'size' not in self.inputs:
            raise DFException('What size is the cube?', self)


class Cube(Block):
    def __init__(self):
        # initialize itself not with type Block, but with out_type=Cube
        super().__init__(type(self))


class Pyramid(Block):
    def __init__(self):
        super().__init__(type(self))


class Ball(Block):
    def __init__(self):
        super().__init__(type(self))


# demo - for efficiency :
# get last board - faster than calling refer
def get_last_board(context):
    boards = [i for i in context.goals if i.typename() == 'Board']
    return boards[-1] if boards else None


class PlaceBlock(Node):
    def __init__(self):
        super().__init__(type(self))
        self.signature.add_sig('block', Block)
        self.signature.add_sig('position', Position)

    # get block, verify ID
    # look at the board, check if position is given and valid
    # add block to the board
    def exec(self, all_nodes=None, goals=None):
        boards = get_refer_match(self.context, all_nodes, goals, type='Board')

        if not boards:  # or - use get_last_board <<<
            raise DFException('No board found! Please initialize the game.', self)  # <<< detailed exception messages
        else:
            board = boards[0]

            # get block from input
            block = self.input_view('block')
            if not block:
                raise DFException('Which block are you trying to place?', self)  # may add hint <<<
            else:
                id = block.get_dat('id')
                if id is None:
                    raise DFException('Block does not have an id', self)  # may add hint <<<
                else:
                    pos = self.input_view('position')
                    if not pos:
                        raise DFException('Please specify the position to place the block', self)  # may add hint <<<
                    else:
                        block_position_x = pos.get_dat('x')
                        if block_position_x is None or not 0<=block_position_x<board.size:
                            raise DFException('Invalid / missing x possition', self)  # may add hint <<<
                        block_position_y = pos.get_dat('y')
                        if block_position_x is None or not 0<=block_position_x<board.size:
                            raise DFException('Invalid / missing y possition', self)  # may add hint <<<

                        # call function from Board to check
                        # add_block may raise exceptions, catch them
                        # with 'try', see in init
                        try:
                            board.add_block(
                                block, block_position_x,
                                block_position_y)
                        except Exception as ex:
                            re_raise_exc(ex, self)
                        
                        # could be useful for compositional expressions: place block and get its color
                        self.set_result(block)
                        self.context.add_message(Message(board.describe().text, node=self))  # <<< show new board
                        return


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
                    if block_position_x is None or not 0<=block_position_x<board.size:
                        raise DFException('Invalid / missing x possition', self)
                    block_position_y = pos.get_dat('y')
                    if block_position_x is None or not 0<=block_position_x<board.size:
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


# class SuggestMove(Node):
#     def __init__(self):
#         super().__init__(type(self))
#
#     def exec(self, all_nodes=None, goals=None):
#         board = get_last_board(self.context)
#         print(board)
#         moves = board.get_suggestions()
#         # what will be printed in suggestion
#         txt = []
#         for (pb, pos, cost) in moves:
#             s = ('moving the ' + pb.describe(params=['no_art']).text +
#                  ' to (%d,%d)'%(pos[0], pos[1]) + ' --> ' + str(cost))
#             txt.append(s)
#         text = 'Here are the suggested moves:  NL ' + '  NL '.join(txt)
#         sugg = []
#         # suggestion #0 - reject (user doesn't like any of the moves)
#         #   --> we will suggest new moves (rerun this node)
#         sugg.append('rerun(id=%d)' % self.id)  # --> $#40
#         # now accepting the "real" moves
#         for (pb, pos, cost) in moves:
#             id = pb.get_ext_dat('block.id')
#             x, y = pos
#             s = 'MoveBlock(id=%s, position=Position(x=%d, y=%d))' % (id, x, y)
#             sugg.append(s)
#         raise DFException(text, self, suggestions=sugg)


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


class IsLeftOf0(Node):
    def __init__(self):
        # super (Node) expects that the init param is output type
        # super().__init__(type(self))
        super().__init__(out_type=Bool)

        # can be a set of PBlocks
        self.signature.add_sig('pblock_1', PBlock)
        self.signature.add_sig('pblock_2', PBlock)

    def exec(self, all_nodes=None, goals=None):
        pblocks_1 = self.input_view('pblock_1').get_op_objects()
        # pblocks_2 = self.input_view('pblock_2').get_op_objects()
        pblock_2 = self.input_view('pblock_2')  # may be SET or PBlock

        # any of the 1st list must be left of any in the 2nd list
        answer = 'False'

        for item_1 in pblocks_1:
            if True:
                if pos_is_left_of(item_1, pblock_2):
                    answer = 'True'
            else:
                for item_2 in pblocks_2:
                    print(item_1.show())
                    x1 = item_1.get_ext_dat('position.x')
                    x2 = item_2.get_ext_dat('position.x')

                    if x1 is not None and x2 is not None:
                        if x1 < x2:
                            answer = 'True'

        # step 2: construct a Bool node
        return_node, _ = self.call_construct_eval(
            'Bool(%s)' % answer, self.context, add_goal=False)
        # if answer:
        #     return_node, _ = self.call_construct_eval(
        #         'Bool(True)', self.context, add_goal=False)
        # else:
        #     return_node, _ = self.call_construct_eval(
        #         'Bool(False)', self.context, add_goal=False)

        # don't forget to set_result otherwise no output from Node!
        self.set_result(return_node)

        # ignore exceptions for now


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

        return_node, _ = self.call_construct_eval(
            'Bool(%s)' % answer, self.context, add_goal=False)
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


class IsLeftOf(Node):
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
        return_node, _ = self.call_construct_eval(
            'Bool(%s)' % answer, self.context, add_goal=False)
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

    def get_positions(self):
        blocks = self.get_pblocks()
        pos = {i.get_pos(): i for i in blocks}
        return pos

    # get suggestions for moves to improve total cost
    # (but don't try to hard - some suggestions may not actually improve)
    # does not consider stacking yet
    # returns tuples: (pblock, new position, new score)
    # def get_suggestions(self):
    #     curr_cost = self.calculate_total_cost()
    #     # returns dict with (x, y): PBlock() k-v structure
    #     pos = self.get_positions()
    #     suggs = []
    #     for p in pos:
    #         pblock = pos[p]
    #         best_cost = 999
    #         best_pos = None
    #         for i in range(10):  # randomly sample 10 positions
    #             x, y = (random.randint(0, self.size-1),
    #                     random.randint(0, self.size - 1))
    #             if (x, y) not in pos:  # position not occupied
    #                 cost = self.costs[(x, y)]
    #                 if cost < best_cost:
    #                     best_cost, best_pos = cost, (x, y)
    #         if best_pos is not None:  # true unless all sampled points were occupied
    #             suggs.append((pblock, best_pos, curr_cost + best_cost - self.costs[p]))
    #     return suggs

    # def init_board(self, size=7, rand=False, show=False):
    #     # if rand - do random init
    #     # if size - use the size
    #     self.size = size
    #
    #     self.costs = {}
    #     if rand:
    #         pass  # todo - random cost initialization
    #     else:
    #         for x in range(size):
    #             for y in range(size):
    #                 self.costs[(x, y)] = max(abs(x - size // 2), abs(y - size // 2))
    #
    #     if show:
    #         s = self.describe().text  # <<<
    #
    #         # draw_graph() will look at context and print message
    #         self.context.add_message(Message(s, node=self))

    def init_grid(self, size, rand=False):
        self.size = size
        self.costs = {}
        for x in range(size):
            for y in range(size):
                self.costs[(x, y)] = random.randint(1, 4) if rand else 1 + (x + y) % 4

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
        if position_x < 0 or position_x > self.size-1:
            raise DFException("This position_x is invalid!", self)

        if position_y < 0 or position_y > self.size-1:
            raise DFException("This position_y is invalid!", self)

        new_id = new_block.get_dat('id')

        pblocks = self.get_pblocks()
        for pb in pblocks:
            x, y = pb.get_pos()
            if (position_x, position_y) == (x,y):
                # rearrange context.goals?
                raise DFException("This position is already taken!", self)

            bid = pb.get_ext_dat('block.id')
            if bid==new_id:
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
            x,y = i.get_ext_dat('position.x'), i.get_ext_dat('position.y')
            if (x, y) == (position_x, position_y):
                raise DFException("Position (%s,%s) is already taken!" % (position_x, position_y), self)

        if position_x < 0 or position_x > self.size-1:
            raise DFException("This position_x is invalid!", self)

        if position_y < 0 or position_y > self.size-1:
            raise DFException("This position_y is invalid!", self)

        # move block - this is destructive!
        for i in pblocks:
            bid = i.get_ext_dat('block.id')
            if bid==id:
                posx, posy = i.get_ext_view('position.x'), i.get_ext_view('position.y')
                if posx:  # should always be true
                    posx.data = position_x  # this is destructive!
                if posy:  # should always be true
                    posy.data = position_y  # this is destructive!

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
        for y in range(self.size-1, -1, -1):
            s = []
            for x in range(self.size):
                if (x, y) in pos:
                    s.append('%s*%s' % (self.costs[(x,y)], pos[(x,y)]))
                else:
                    s.append('_%s_' % self.costs[(x,y)])
            ss.append(s)
        s = '  NL  '.join([' '.join(i) for i in ss])

        # calculate and append total board costs
        s = s + '  NL  ' + 'total cost: ' + str(self.calculate_total_cost())
        return Message(s)


class InitBoard(Node):
    def __init__(self):
        super().__init__(type(self))
        self.signature.add_sig('rand', Bool)
        self.signature.add_sig('size', Int)

    def exec(self, all_nodes=None, goals=None):
        # if rand - do random init
        rand = self.inp_equals('rand', True)
        if 'size' not in self.inputs:
            # size = 7  # set default size
            raise DFException('Please specify the size of the board', self)
        else:
            size = self.get_dat('size')

        board, _ = self.call_construct_eval('Board()', self.context, add_goal=True)
        self.context.switch_goal_order(-1, -2)  # for side task, we want Griddy to be the last goal

        board.init_grid(size=size, rand=rand)
        d, _ = self.call_construct_eval(
                'Cube(id=1,color=red,material=wood,size=big)',
                self.context)
        board.add_block(d, 1, 1)

        d, _ = self.call_construct_eval(
                'Cube(id=2,color=yellow,material=plastic,size=big)',
                self.context)
        board.add_block(d, 4, 4)

        d, _ = self.call_construct_eval(
                'Pyramid(id=3,color=blue,material=metal,size=small)',
                self.context)
        board.add_block(d, 3, 1)

        d, _ = self.call_construct_eval(
                'Ball(id=4,color=yellow,material=plastic,size=big)',
                self.context)
        board.add_block(d, 1, 3)

        self.context.add_message(Message(board.describe().text, node=self))


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
        #self.context.add_message(Message(s, node=self))


class AddBlock(Node):
    def __init__(self):
        super().__init__(type(self))
        self.signature.add_sig('block', Block)
        self.signature.add_sig('x', Int)
        self.signature.add_sig('y', Int)

    def exec(self, all_nodes=None, goals=None):
        block = self.input_view('block')
        if not block:
            raise DFException('Please specify the block to add', self)
        x, y = self.get_dats(['x','y'])
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
            new_block = board.add_block(block, x, y)
        except Exception as ex:
            re_raise_exc(ex, self)
        # s = board.describe().text
        # self.context.add_message(Message(s, node=self))
        self.set_result(new_block)


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


# class show_board(Node):
#     def __init__(self):
#         super().__init__(type(self))
#
#     def exec(self, all_nodes=None, goals=None):
#         # manually execute 'refer' with type=Board
#         b = get_refer_match(self.context, all_nodes, goals, type='Board')
#         # try pos1='Board?()'
#         # pos1 will be less efficient, understand why, during construction
#
#         if b:
#             board = b[0]
#             s = board.describe().text
#             self.context.add_message(Message(s, node=self))
#
#             # calculate and append total board costs
#             # Q: can we do this without repeating the same in Board.exec?
#             # total_board_cost = sum(sum(list) for list in board.costs)
#             board.calculate_total_cost()
#
#             self.context.add_message(Message(s, node=self))


class LoopMove(Node):
    def __init__(self):
        super().__init__(type(self))
        self.signature.add_sig('init', InitBoard)
        self.signature.add_sig('move', move_spec)
        self.signature.add_sig('end', Bool)


class move_spec(Node):
    def __init__(self):
        super().__init__(type(self))
        self.signature.add_sig('id', Int)
        self.signature.add_sig('x', Int)
        self.signature.add_sig('y', Int)


class LoopMove(Node):
    def __init__(self):
        super().__init__(type(self))
        self.signature.add_sig('init', InitBoard)
        self.signature.add_sig('move', move_spec)
        self.signature.add_sig('end', Bool)

    def exec(self, all_nodes=None, goals=None):
        done = self.get_dat('end')
        if not done:
            msg = ''
            mspec = self.input_view('move')
            board = get_last_board(self.context)
            if mspec:
                id, x, y = mspec.get_dats(['id', 'x', 'y'])
                if id is not None:
                    try:
                        board.move_block(id, x, y)
                        cost = board.calculate_total_cost()
                        msg = 'Moved block #%d to {%d,%d}  NL  The cost is now %d  NL  ' % (id, x, y, cost)
                    except Exception as ex:
                        msg = to_list(ex)[0].message.text + '  NL  '
            # Add suggestions
            txt, sugg = [],  ['revise(hasParam=move, new=move_spec(), newMode=extend)']
            for i in range(3):
                id = random.randint(1, 5)
                x, y = random.randint(0, board.size), random.randint(0, board.size)
                txt.append('%d) move block#%d to {%d,%d}' % (i+1, id, x, y))
                sugg.append('revise(hasParam=move, new=move_spec(id=%d,x=%d,y=%d), newMode=extend)' % (id, x, y))
            msg += 'What is your next move?  NL  You can specify your own move  NL  '
            msg += 'or select one of the following moves:  NL  '
            msg += '  NL  '.join(txt)
            raise DFException(msg, self, suggestions=sugg)


class Griddy(Node):
    def __init__(self):
        super().__init__(type(self))
        self.signature.add_sig('game', LoopMove)
        self.signature.add_sig('confirm', Bool)

    def exec(self, all_nodes=None, goals=None):
        done = self.get_dat('confirm')
        if done is None:
            raise DFException('Are you sure you want to quit?', self)
        elif done:
            self.context.add_message(Message('Goodbye', node=self))
        else:
            raise DFException('todo - resume game', self)

    def fallback_search(self, parent, all_nodes=None, goals=None, do_eval=True, params=None):
        g, _ = self.call_construct('Griddy(game=LoopMove(init=InitBoard()))', self.context, add_goal=True)
        return [g]


