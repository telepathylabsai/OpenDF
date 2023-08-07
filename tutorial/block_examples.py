# to run:
# PYTHONPATH=$(pwd) python opendf/main.py -n tutorial.blockWorld -ef tutorial/block_examples.py [-d ...]

dialogs = [
    # #0: scratch pad - use for testing expressions
    [
        # EX 1.
        # 'Int(1)',
        # 'Float(1.1)',
        # 'Bool(True)',
        # 'Str(cat)',
        # 'Str("two cats")',   # use quotes if there are spaces, otherwise not needed
        # 'material(plastic)',
        # 'Cube(color=red)',
        # 'Cube(size=small, color=blue, material=metal)',

        # Ex 2.
        #'Cylinder(color=yellow, material=plastic)'


        # Ex 3.
        # 'Cube(color=red, material=wood, size=big)',
        # 'Cube(color=yellow, material=plastic, size=big)',
        # 'Pyramid(color=blue, material=metal, size=small)',
        # 'Ball(color=yellow, material=plastic, size=big)',

        # 'refer(Ball?())',
        # 'refer(Pyramid?(material=metal))',
        # ':color(refer(Block?(material=wood)))',
        # 'Yield(:color(refer(Block?(material=wood))))',
        # 'Yield(size(refer(Block?(material=plastic), multi=True)))',
        # 'Yield(Exists(refer(Cube?(color=yellow))))',


        # Ex 4.
        # 'refer(NOT(Cube?(material=plastic)), multi=True)',
        # 'refer(AND(Block?(), NOT(Cube?(material=plastic))), multi=True)',
        # 'refer(Cube?(material=NOT(Material(plastic))), multi=True)',  # note we have to explicitly use Material(plastic)
        # 'refer(AND(OR(Block?(size=small), Block?(material=wood)), OR(Cube?(), Ball?())),multi=true)',
        # 'refer(Block?(color=OR(Color(red), Color(blue))), multi=True)',

        #'Mult(Add(1,2), Add(3,4))',
        #'Power(2,3.0)',

        'Board()',
        # 'InitGrid()',
        # 'ShowBoard()',

        #'Yield(Ball(color=red))',
        #'Material(plastic)',
        #'Color(red)',
        #'Cube3(color=red)',

        # 'Yield(size(refer(Block?(material=plastic), multi=True)))',
        # 'revise(old=Material?(), new=Material(wood))'

        # 'Yield(EQf(size(refer(Block?(), multi=True)),3))',
        # 'revise(old=Int?(), new=4)',

        #'refer(Block?(color=red))',
        #'refer(NOT(Cube?(material=plastic)), multi=True)',
        #'refer(AND(Block?(), NOT(Cube?(material=plastic))), multi=True)',
        #'Yield(Exists(refer(Block?(material=plastic), multi=True)))',
        #
        #

        #'Yield(size(refer(Block?(material=plastic), multi=True)))',
        #'revise(old=Material?(), new=Material(wood))'

        # 'Yield(GTf(size(refer(Block?(material=plastic), multi=True)), 3))',
        # 'revise(old=Int?(), new=1)',
     ],

    ############################## examples for blockWorld_V1 ###############################################

    # #1 :
    ['Cube1(color=red, material=wood)',],
    # #2 :
    ['Cube2(color=red, material=wood)',],
    # #3 :
    ['Cube3(color=red, material=wood)',],
    # #4 :
    ['Cube4(color=red, material=wood)',],
    # #5 :
    ['Yield(Cube(color=red, material=wood, size=big))',],
    # #6 :
    [
        'Cube(color=red, material=wood, size=big)',
        'Cube(color=yellow, material=plastic, size=big)',
        'Pyramid(color=blue, material=metal, size=small)',
        'Ball(color=yellow, material=plastic, size=big)',
    ],
    # #7 :
    [
        'SET(Cube(color=red, material=wood, size=big), \
        Cube(color=yellow, material=plastic, size=big))',
    ],
    # #8 :
    [
        'Cube(color=red, material=wood, size=big)',
        'Cube(color=yellow, material=plastic, size=big)',
        'Pyramid(color=blue, material=metal, size=small)',
        'Ball(color=yellow, material=plastic, size=big)',
        'refer(Cube?(color=red))',
    ],
    # #9 :
    [
        'Cube(color=red, material=wood, size=big)',
        'Cube(color=yellow, material=plastic, size=big)',
        'Pyramid(color=blue, material=metal, size=small)',
        'Ball(color=yellow, material=plastic, size=big)',
        'refer(Pyramid?())',
    ],
    # #10 :
    [
        'Cube(color=red, material=wood, size=big)',
        'Cube(color=yellow, material=plastic, size=big)',
        'Pyramid(color=blue, material=metal, size=small)',
        'Ball(color=yellow, material=plastic, size=big)',
        'refer(Cube?())',
    ],
    # #11 :
    [
        'Cube(color=red, material=wood, size=big)',
        'Cube(color=yellow, material=plastic, size=big)',
        'Pyramid(color=blue, material=metal, size=small)',
        'Ball(color=yellow, material=plastic, size=big)',
        'refer(Cube?(), multi=True)',
    ],
    # #12 :
    [
        #'getattr(size, Ball(size=big, material=plastic, color=yellow))',
        ':size(Ball(size=big, material=plastic, color=yellow))'  # equivalent - shorthand notation
    ],
    # #13 :
    [
        'Cube(color=red, material=wood, size=big)',
        'Cube(color=yellow, material=plastic, size=big)',
        'Pyramid(color=blue, material=metal, size=small)',
        'Ball(color=yellow, material=plastic, size=big)',
        'Yield(:size(refer(Ball?())))'
    ],
    # #14 :
    [
        'Cube(color=red, material=wood, size=big)',
        'Cube(color=yellow, material=plastic, size=big)',
        'Pyramid(color=blue, material=metal, size=small)',
        'Ball(color=yellow, material=plastic, size=big)',
        'Yield(refer(Cube?(color=:color(refer(Ball?())))))',
    ],
    # #15 :
    [
        'Cube(color=red, material=wood, size=big)',
        'Cube(color=yellow, material=plastic, size=big)',
        'Pyramid(color=blue, material=metal, size=small)',
        'Ball(color=yellow, material=plastic, size=big)',
        'Yield(:size(refer(Cube?(color=:color(refer(Ball?()))))))',
    ],
    # #16 :
    [
        'Cube(color=red, material=wood, size=big)',
        'Cube(color=yellow, material=plastic, size=big)',
        'Pyramid(color=blue, material=metal, size=small)',
        'Ball(color=yellow, material=plastic, size=big)',
        'Yield(EQf(:material(refer(Cube?(color=:color(refer(Ball?()))))), \
             :material(refer(Block?(color=blue)))))',
    ],
    # #17 :
    [
        'Cube(color=red, material=wood, size=big)',
        'Cube(color=yellow, material=plastic, size=big)',
        'Pyramid(color=blue, material=metal, size=small)',
        'Ball(color=yellow, material=plastic, size=big)',
        'refer(OR(Block?(material=plastic),Block?(color=blue)), multi=True)',
    ],
    # #18 :
    [
        'Cube(color=red, material=wood, size=big)',
        'Cube(color=yellow, material=plastic, size=big)',
        'Pyramid(color=blue, material=metal, size=small)',
        'Ball(color=yellow, material=plastic, size=big)',
        ':size(refer(Cube?(color=red)))',
    ],
    # #19 :
    [
        'Cube(color=red, material=wood, size=big)',
        'Cube(color=yellow, material=plastic, size=big)',
        'Pyramid(color=blue, material=metal, size=small)',
        'Ball(color=yellow, material=plastic, size=big)',
        ':size(refer(Cube?(color=red)))',
        'revise(old=Color?(), new=Color(yellow))',
    ],

    # #20 :
    [
        'Cube(color=red, material=wood, size=big)',
        'Cube(color=yellow, material=plastic, size=big)',
        'Pyramid(color=blue, material=metal, size=small)',
        'Ball(color=yellow, material=plastic, size=big)',
        ':material(refer(Cube?(size=big)))',
        'revise(hasParam=color, new=Color(red), newMode=extend)',
    ],

    ############################## examples for blockWorld_V2 ###############################################

    #  #21 :
    [
        'Board()',
        'InitGrid(size=7,rand=False)',
        'ShowBoard()',
    ],
    #  #22 :
    [
        'Board()',
        'InitGrid(size=7,rand=False)',
        'AddBlock(block=Cube(id=1, color=red, material=wood, size=small), x=1, y=1)',
        'ShowBoard()',
    ],
    #  #23 :
    [
        'Board()',
        'InitGrid(size=7,rand=False)',
        'AddBlock(block=Cube(id=1, color=red, material=wood, size=small), x=8, y=1)',
    ],
    #  #24 :
    [
        'Board()',
        'InitGrid(size=7,rand=False)',
        'AddBlock(block=Cube(id=1, color=red, material=wood, size=small), x=1, y=1)',
        'MoveBlock(id=1, position=Position(x=4, y=4))',
        'ShowBoard()',
    ],
    #  #25 :
    [
        'Board()',
        'InitGrid(size=7,rand=False)',
        'AddBlock(block=Cube(id=1, color=red, material=wood, size=small), x=1, y=1)',
        'revise(old=Position?(), mid=PBlock(block=Block(id=1)), new=Position(x=4,y=4))',
        'ShowBoard()',
    ],
    #  #26 :
    [
        '<&>Board()',
        'InitGrid(size=7,rand=False)',
        'AddBlock(block=Cube(id=1, color=red, material=wood, size=small), x=1, y=1)',
        'revise(old=Position?(), mid=PBlock(block=Block(id=1)), new=Position(x=4,y=4))',
        'ShowBoard()',
    ],
    #  #27 :
    [
        'Board()',
        'InitGrid(size=7,rand=False)',
        'AddBlock(block=Cube(id=1, color=red, material=wood, size=big),x=1, y=1)',
        'AddBlock(block=Cube(id=2, color=yellow, material=plastic, size=big),x=4, y=4)',
        'AddBlock(block=Pyramid(id=3, color=blue, material=metal, size=small),x=3, y=1)',
        'AddBlock(block=Ball(id=4, color=yellow, material=plastic, size=big),x=1, y=3)',
        ':size(refer(Cube?(color=yellow)))',
    ],
    #  #28 :
    [
        'Board()',
        'InitGrid(size=7,rand=False)',
        'AddBlock(block=Cube(id=1, color=red, material=wood, size=big),x=1, y=1)',
        'AddBlock(block=Cube(id=2, color=yellow, material=plastic, size=big),x=4, y=4)',
        'AddBlock(block=Pyramid(id=3, color=blue, material=metal, size=small),x=3, y=1)',
        'AddBlock(block=Ball(id=4, color=yellow, material=plastic, size=big),x=1, y=3)',
        'refer(PBlock?(position=Position(x=4)))',

    ],
    #  #29 :
    [
        'Board()',
        'InitGrid(size=7,rand=False)',
        'AddBlock(block=Cube(id=1, color=red, material=wood, size=big),x=1, y=1)',
        'AddBlock(block=Cube(id=2, color=yellow, material=plastic, size=big),x=4, y=4)',
        'AddBlock(block=Pyramid(id=3, color=blue, material=metal, size=small),x=3, y=1)',
        'AddBlock(block=Ball(id=4, color=yellow, material=plastic, size=big),x=1, y=3)',
        'refer(PBlock?(position=Position(x=GT(3))))',
    ],
    #  #30 :
    [
        'Board()',
        'InitGrid(size=7,rand=False)',
        'AddBlock(block=Cube(id=1, color=red, material=wood, size=big),x=1, y=1)',
        'AddBlock(block=Cube(id=2, color=yellow, material=plastic, size=big),x=4, y=4)',
        'AddBlock(block=Pyramid(id=3, color=blue, material=metal, size=small),x=3, y=1)',
        'AddBlock(block=Ball(id=4, color=yellow, material=plastic, size=big),x=1, y=3)',
        'Yield(IsLeftOf1(refer(PBlock?(block=Block?(id=1))), \
                         refer(PBlock?(block=Block?(id=2)))))',
    ],
    #  #31 :
    [
        'Board()',
        'InitGrid(size=7,rand=False)',
        'AddBlock(block=Cube(id=1, color=red, material=wood, size=big),x=1, y=1)',
        'AddBlock(block=Cube(id=2, color=yellow, material=plastic, size=big),x=4, y=4)',
        'AddBlock(block=Pyramid(id=3, color=blue, material=metal, size=small),x=3, y=1)',
        'AddBlock(block=Ball(id=4, color=yellow, material=plastic, size=big),x=1, y=3)',
        'Yield(IsLeftOf2(refer(PBlock?(block=Block?(id=1))), \
                         refer(PBlock?(block=Block?(id=2)))))',
    ],
    #  #32 :
    [
        'Board()',
        'InitGrid(size=7,rand=False)',
        'AddBlock(block=Cube(id=1, color=red, material=wood, size=big),x=1, y=1)',
        'AddBlock(block=Cube(id=2, color=yellow, material=plastic, size=big),x=4, y=4)',
        'AddBlock(block=Pyramid(id=3, color=blue, material=metal, size=small),x=3, y=1)',
        'AddBlock(block=Ball(id=4, color=yellow, material=plastic, size=big),x=1, y=3)',
        'Yield(IsLeftOf3(refer(PBlock?(block=Ball?()), multi=True), \
                   refer(PBlock?(block=Cube?()), multi=True)))',
    ],
    #  #33 :
    [
        'Board()',
        'InitGrid(size=7,rand=False)',
        'AddBlock(block=Cube(id=1, color=red, material=wood, size=big),x=1, y=1)',
        'AddBlock(block=Cube(id=2, color=yellow, material=plastic, size=big),x=4, y=4)',
        'AddBlock(block=Pyramid(id=3, color=blue, material=metal, size=small),x=3, y=1)',
        'AddBlock(block=Ball(id=4, color=yellow, material=plastic, size=big),x=1, y=3)',
        'Yield(IsLeftOf(refer(PBlock?(block=Ball?()), multi=True), \
                   refer(PBlock?(block=Cube?()), multi=True)))',
    ],
    #  #34 :
    [
        'Board()',
        'InitGrid(size=7,rand=False)',
        'AddBlock(block=Cube(id=1, color=red, material=wood, size=big),x=1, y=1)',
        'AddBlock(block=Cube(id=2, color=yellow, material=plastic, size=big),x=4, y=4)',
        'AddBlock(block=Pyramid(id=3, color=blue, material=metal, size=small),x=3, y=1)',
        'AddBlock(block=Ball(id=4, color=yellow, material=plastic, size=big),x=1, y=3)',
        'refer(FN(fname=left_of, \
                  farg=refer(PBlock?(block=Block(material=metal)))), \
               multi=True)',
    ],

    ############################## examples for blockWorld_V3 ###############################################

    #  #35 :
    ['Griddy(game=LoopMove(init=InitBoard()))',],
    #  #36 :
    [
        'Griddy(game=LoopMove(init=InitBoard()))',
        'revise(hasParam=size, new=7, newMode=extend)',
    ],
    #  #37 :
    [
        'Griddy(game=LoopMove(init=InitBoard()))',
        'revise(hasParam=size, new=7, newMode=extend)',
        'revise(hasParam=move, new=move_spec(id=1, x=2,y=2),newMode=extend)',
    ],
    #  #38 :
    [
        'Griddy(game=LoopMove(init=InitBoard()))',
        'revise(hasParam=size, new=7, newMode=extend)',
        'revise(hasParam=move, new=move_spec(id=1, x=2,y=2),newMode=extend)',
        'revise(hasParam=end, new=True, newMode=extend)',
    ],
    #  #39 :
    [
        'Griddy(game=LoopMove(init=InitBoard()))',
        'revise(hasParam=size, new=7, newMode=extend)',
        'revise(hasParam=move, new=move_spec(id=1, x=2,y=2),newMode=extend)',
        'revise(hasParam=end, new=True, newMode=extend)',
        'revise(hasParam=confirm, new=True, newMode=extend)',
    ],
    #  #40 :
    ['refer(Griddy?())',],
    #  #41 :
    ['<!>refer(Griddy?())',],
    #  #42 :
    [
        '<!>refer(Griddy?())',
        '<!>refer(Griddy?())',
    ],


    ############################## examples for blockWorld_V4 ###############################################

    #  #43 :
    [
        'Griddy(game=LoopMove(init=InitBoard()))',
        'revise(hasParam=size, new=7, newMode=extend)',
    ],
    #  #44 :
    [
        'Griddy(game=LoopMove(init=InitBoard()))',
        'revise(hasParam=size, new=7, newMode=extend)',
        'RejectSuggestion()',
    ],
    #  #45 :
    [
        'Griddy(game=LoopMove(init=InitBoard()))',
        'revise(hasParam=size, new=7, newMode=extend)',
        'AcceptSuggestion(2)',
    ],
    #  #46 :
    [
        'Griddy(game=LoopMove(init=InitBoard()))',
        'revise(hasParam=size, new=7, newMode=extend)',
        'Yield(:position(refer(PBlock?(block=Block?(id=3)))))',
    ],
    #  #47 :
    [
        'Griddy(game=LoopMove(init=InitBoard()))',
        'revise(hasParam=size, new=7, newMode=extend)',
        'side_task(task=:position(refer(PBlock?(block=Block?(id=3)))), persist=True)',
    ],
    #  #48 :
    [
        'Griddy(game=LoopMove(init=InitBoard()))',
        'revise(hasParam=size, new=7, newMode=extend)',
        'side_task(task=:position(refer(PBlock?(block=Block?(id=3)))))',

    ],
    #  # :
    [],



]
