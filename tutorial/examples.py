# to run:
# PYTHONPATH=$(pwd) python opendf/main.py -n tutorial.blockWorld -ef tutorial/examples.py


dialogs = [
    [
        'Cube(color=red, material=wood, size=big)',
        # 'Cube(color=yellow, material=plastic, size=big)',

        # 'Board()',
        # 'InitGrid()',
        # 'AddBlock(block=Cube(id=1, color=red, material=wood, size=big),x=1, y=1)',
        # 'AddBlock(block=Cube(id=2, color=yellow, material=plastic, size=big),x=4, y=4)',
        # 'AddBlock(block=Pyramid(id=3, color=blue, material=metal, size=small),x=3, y=1)',
        # 'AddBlock(block=Ball(id=4, color=yellow, material=plastic, size=big),x=1, y=3)',
        # 'refer(Cube?(size=big))',
        # 'revise(hasParam=color, new=Color(red), newMode=extend)',
        # 'refer(FN(fname=left_of, farg=refer(PBlock?(block=Block(material=metal)))), multi=True)'
        #

        # 'Cube(color=red, material=wood, size=big)',
        # 'Cube(color=yellow, material=plastic, size=big)',
        # 'Pyramid(color=blue, material=metal, size=small)',
        # 'Ball(color=yellow, material=plastic, size=big)',
        # #'Griddy(game=LoopMove(init=InitBoard(size=7)))',
        # #'move_spec(id=1, position=Position(x=2,y=2))',
        # 'revise(hasParam=move, new=move_spec(id=1, x=2,y=2), newMode=extend)',
        # 'revise(hasParam=end, new=True, newMode=extend)',
        # 'revise(hasParam=confirm, new=True, newMode=extend)',
        # '<!>refer(Griddy?())',
        # '<!>refer(Griddy?())',
        # 'Griddy(game=LoopMove(init=InitBoard()))',
        # 'revise(hasParam=size, new=7, newMode=extend)',
        # 'revise(hasParam=move, new=move_spec(id=1, x=2,y=2), newMode=extend)',
        # 'AcceptSuggestion(2)',
        # 'Yield(:position(refer(PBlock?(block=Block?(id=3)))))',
        # 'side_task(task=:position(refer(PBlock?(block=Block?(id=3)))), persist=True)',
        # 'side_task(task=:position(refer(PBlock?(block=Block?(id=3)))))',
        # 'RejectSuggestion()',

        # 'SET(SET(1, 2), 3, 4)',
        # '<&>Board()',
        # 'ShowBoard()',
        # 'AddBlock(block=Cube(id=1, color=red, material=wood, size=small), x=1, y=1)',
        # 'ShowBoard()',
        # 'MoveBlock(id=1, position=Position(x=4, y=4))',
        # 'revise(old=Position?(), mid=PBlock?(block=Block(id=1)), new=Position(x=4,y=4))',

        # 'ShowBoard()',
        # ':size(refer(Cube?(color=yellow)))',
        # 'Yield(IsLeftOf(refer(PBlock?(block=Block?(id=1))), refer(PBlock?(block=Block?(id=2)))))',
        # 'refer(PBlock?(position=Position(x=4)))',
        # 'refer(PBlock?(position=Position(x=GT(3))))',

        # 'IsLeftOf(refer(PBlock?(block=Ball?()), multi=True), refer(PBlock?(block=Cube?()), multi=True))',
        # 'ShowBoard()',
        # 'ShowBoard()'
        # 'Add(1,Add(2,3))',
        # 'SET(Cube(color=red, material=wood, size=big), Cube(color=yellow, material=plastic, size=big))',
        # 'Cube(color=red, material=wood)',
        # 'Yield(Cube(color=red, material=wood, size=big))'
        # 'refer(Cube?(color=red))',
        # 'refer(Pyramid?())',
        # 'refer(Cube?())',
        # 'refer(OR(Block?(material=plastic), Block?(color=blue)), multi=True)',
        # 'refer(Cube?(), multi=True)',
        # 'getattr(size, refer(Ball?()))',
        # 'getattr(size, Ball(size=big, material=plastic, color=yellow))',
        # ':size(Ball(size=big, material=plastic, color=yellow))',
        # ':size(refer(Cube?(color=red)))',
        # 'revise(old=Color?(), new=Color(yellow))',
        # ':size(refer(Ball?()))',
        # 'revise(old=Block??(), new=Pyramid?())',
        # 'Yield(refer(Cube?(color=:color(refer(Ball?())))))',
        # 'Yield(:size(refer(Cube?(color=:color(refer(Ball?()))))))',
        # 'EQf(:material(refer(Cube?(color=:color(refer(Ball?()))))), :material(refer(Block?(color=blue))))',
        # 'refer(Block?(material=wood))',
        # 'init_game()',
        # 'game()',
        # 'revise(hasParam=task, new=MoveBlock(id=2, position=Position(x=6, y=0)), newMode=extend)',
        # 'revise(hasParam=task, new=MoveBlock(id=2, position=Position(x=5, y=0)), newMode=extend)',
        # 'revise(hasParam=done, new=True, newMode=extend)',
     ]
]
