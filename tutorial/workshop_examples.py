"""
The P-Expression examples for the workshop.
to run:
PYTHONPATH=$(pwd) python opendf/main.py -n tutorial.workshop_nodes -ef tutorial/workshop_examples.py [-d ...]
"""

dialogs = [
    # 0: scratch pad - use for testing expressions
    [
        "Cube1()",
    ],
    # 1
    [
        "Cube1(color=red, material=wood)",
    ],
    # 2
    [
        "Cube2(color=red, material=wood)",
    ],
    # 3
    [
        "Yield(Cube(color=red, material=wood, size=big))",
    ],
    # 4
    [
        "Pyramid(color=blue, material=plastic, size=big)",
    ],
    # 5
    [
        "Cube(color=red, material=wood, size=big)",
        "Cube(color=yellow, material=plastic, size=big)",
        "Pyramid(color=blue, material=metal, size=small)",
        "Ball(color=yellow, material=plastic, size=big)",
    ],
    # 6
    [
        "Cube(color=red, material=wood, size=big)",
        "Cube(color=yellow, material=plastic, size=big)",
        "Pyramid(color=blue, material=metal, size=small)",
        "Ball(color=yellow, material=plastic, size=big)",
        "Ball(color=yellow, material=plastic, size=big)",
        "refer(Cube?(color=red))",
    ],
    # 7
    [
        "Cube(color=red, material=wood, size=big)",
        "Cube(color=yellow, material=plastic, size=big)",
        "Pyramid(color=blue, material=metal, size=small)",
        "Ball(color=yellow, material=plastic, size=big)",
        "Ball(color=yellow, material=plastic, size=big)",
        "refer(Cube?())",
    ],
    # 8
    [
        "Cube(color=red, material=wood, size=big)",
        "Cube(color=yellow, material=plastic, size=big)",
        "Pyramid(color=blue, material=metal, size=small)",
        "Ball(color=yellow, material=plastic, size=big)",
        "Ball(color=yellow, material=plastic, size=big)",
        "refer(Cube?(), multi=True)",
    ],
    # 9
    [
        "Cube(color=red, material=wood, size=big)",
        "Cube(color=yellow, material=plastic, size=big)",
        "Pyramid(color=blue, material=metal, size=small)",
        "Ball(color=yellow, material=plastic, size=big)",
        "Ball(color=yellow, material=plastic, size=big)",
        "getattr(size, refer(Ball?()))",
    ],
    # 10
    [
        "Cube(color=red, material=wood, size=big)",
        "Cube(color=yellow, material=plastic, size=big)",
        "Pyramid(color=blue, material=metal, size=small)",
        "Ball(color=yellow, material=plastic, size=big)",
        "Ball(color=yellow, material=plastic, size=big)",
        ":size(refer(Ball?()))",
    ],
    # 11
    [
        "Cube(color=red, material=wood, size=big)",
        "Cube(color=yellow, material=plastic, size=big)",
        "Pyramid(color=blue, material=metal, size=small)",
        "Ball(color=yellow, material=plastic, size=big)",
        "Ball(color=yellow, material=plastic, size=big)",
        "Yield(:size(refer(Cube?(color=:color(refer(Ball?()))))))",
    ],
    # 12
    [
        "Cube(color=red, material=wood, size=big)",
        "Cube(color=yellow, material=plastic, size=big)",
        "Pyramid(color=blue, material=metal, size=small)",
        "Ball(color=yellow, material=plastic, size=big)",
        "Ball(color=yellow, material=plastic, size=big)",
        "Yield(EQf(:material(refer(Cube?(color=:color(refer(Ball?()))))), :material(refer(Block?(color=blue)))))",
    ],
    # 13
    [
        "Cube(color=red, material=wood, size=big)",
        "Cube(color=yellow, material=plastic, size=big)",
        "Pyramid(color=blue, material=metal, size=small)",
        "Ball(color=yellow, material=plastic, size=big)",
        "Ball(color=yellow, material=plastic, size=big)",
        "refer(OR(Block?(material=wood), Block?(color=blue)), multi=True)",
    ],
    # 14
    [
        "Cube(color=red, material=wood, size=big)",
        "Cube(color=yellow, material=plastic, size=big)",
        "Pyramid(color=blue, material=metal, size=small)",
        "Ball(color=yellow, material=plastic, size=big)",
        "Ball(color=yellow, material=plastic, size=big)",
        ":size(refer(Cube?(color=red)))",
    ],
    # 15
    [
        "Cube(color=red, material=wood, size=big)",
        "Cube(color=yellow, material=plastic, size=big)",
        "Pyramid(color=blue, material=metal, size=small)",
        "Ball(color=yellow, material=plastic, size=big)",
        "Ball(color=yellow, material=plastic, size=big)",
        ":size(refer(Cube?(color=red)))",
        "revise(old=Color?(), new=Color(yellow))",
    ],
    # 16
    [
        "Cube(color=red, material=wood, size=big)",
        "Cube(color=yellow, material=plastic, size=big)",
        "Pyramid(color=blue, material=metal, size=small)",
        "Ball(color=yellow, material=plastic, size=big)",
        "Ball(color=yellow, material=plastic, size=big)",
        "size(refer(Block?(material=plastic), multi=True))",
    ],
    # 17
    [
        "Cube(color=red, material=wood, size=big)",
        "Cube(color=yellow, material=plastic, size=big)",
        "Pyramid(color=blue, material=metal, size=small)",
        "Ball(color=yellow, material=plastic, size=big)",
        "Ball(color=yellow, material=plastic, size=big)",
        "EQf(size(refer(Cube?(), multi=True)), Int(3))",
    ],
]
