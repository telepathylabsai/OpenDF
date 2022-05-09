"""
Test cases for the P-expression parser.
"""
import json
import unittest

from opendf.parser.pexp_parser import parse_p_expressions, ASTNode


class TestPExpParser(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        pass

    @classmethod
    def tearDownClass(cls) -> None:
        pass

    def test_expression_1(self):
        expression = "Int()"
        expected = [
            ASTNode("Int")
        ]
        trees = parse_p_expressions(expression)
        self.assertEqual(expected, trees)

    def test_expression_2(self):
        expression = "Int(10) Int(2) -10 3.14 .54 -.54 -0.54 2.45e2 abc Abc ABC"
        expected = [
            ASTNode("Int", [(None, ASTNode("10", is_terminal=True))]),
            ASTNode("Int", [(None, ASTNode("2", is_terminal=True))]),
            ASTNode("-10 3.14 .54 -.54 -0.54 2.45e2 abc Abc ABC", is_terminal=True),
        ]
        trees = parse_p_expressions(expression)
        self.assertEqual(expected, trees)

    def test_expression_3(self):
        expression = "HourAM(Int(10)) "
        expression += "Recipient(name=John Doe,firstName=John,lastName=Doe,id=1001, " \
                      "phoneNum=+41 76 123 10 01, email=john.doe@opendf.com)"
        expected = [
            ASTNode("HourAM", [(None, ASTNode("Int", [(None, ASTNode("10", is_terminal=True))]))]),
            ASTNode("Recipient", [("name", ASTNode("John Doe", is_terminal=True)),
                                  ("firstName", ASTNode("John", is_terminal=True)),
                                  ("lastName", ASTNode("Doe", is_terminal=True)),
                                  ("id", ASTNode("1001", is_terminal=True)),
                                  ("phoneNum", ASTNode("+41 76 123 10 01", is_terminal=True)),
                                  ("email", ASTNode("john.doe@opendf.com", is_terminal=True))]),
        ]
        trees = parse_p_expressions(expression)
        self.assertEqual(expected, trees)

    def test_expression_4(self):
        expression = "Name(Str(\"John Doe\")) "
        expression += "Name(\"John Doe\") "
        expression += "Str(\"Str(This is a string, note the definition of a Str node)\") "
        json_encode = json.dumps({"name": "John Doe", "age": 30, "email": "john.doe@opendf.com"})
        expression += f"JSON('{json_encode}') "
        expected = [
            ASTNode("Name", [(None, ASTNode("Str", [(None, ASTNode("John Doe", is_terminal=True))]))]),
            ASTNode("Name", [(None, ASTNode("John Doe", is_terminal=True))]),
            ASTNode("Str", [(None, ASTNode("Str(This is a string, note the definition of a Str node)",
                                           is_terminal=True))]),
            ASTNode("JSON", [(None, ASTNode(json_encode, is_terminal=True))]),
        ]
        trees = parse_p_expressions(expression)
        self.assertEqual(expected, trees)

    def test_expression_5(self):
        expression = "Time(hour=Int(10), minute=50) // this is a comment\n"
        expression += "Time?(hour=Int(10), /* this is also a comment */ minute=50) " \
                      "Time??(hour=Int(10), minute=50) " \
                      "Constraint[Time](hour=Int(10), minute=50) " \
                      "Constraint[Constraint[Time]](hour=Int(10), minute=50) " \
                      "Constraint[Constraint[Time?]](hour=Int(10), minute=50) "
        expected = [
            ASTNode("Time", [("hour", ASTNode("Int", [(None, ASTNode("10", is_terminal=True))])),
                             ("minute", ASTNode("50", is_terminal=True))]),
            ASTNode("Time?", [("hour", ASTNode("Int", [(None, ASTNode("10", is_terminal=True))])),
                              ("minute", ASTNode("50", is_terminal=True))]),
            ASTNode("Time??", [("hour", ASTNode("Int", [(None, ASTNode("10", is_terminal=True))])),
                               ("minute", ASTNode("50", is_terminal=True))]),
            ASTNode("Constraint[Time]", [("hour", ASTNode("Int", [(None, ASTNode("10", is_terminal=True))])),
                                         ("minute", ASTNode("50", is_terminal=True))]),
            ASTNode("Constraint[Constraint[Time]]",
                    [("hour", ASTNode("Int", [(None, ASTNode("10", is_terminal=True))])),
                     ("minute", ASTNode("50", is_terminal=True))]),
            ASTNode("Constraint[Constraint[Time?]]",
                    [("hour", ASTNode("Int", [(None, ASTNode("10", is_terminal=True))])),
                     ("minute", ASTNode("50", is_terminal=True))]),
        ]
        trees = parse_p_expressions(expression)
        self.assertEqual(expected, trees)

    def test_expression_6(self):
        expression = "Date(str 25, ^holiday=Christmas, ^is_holiday) "
        expression += "Date(year=Int(2022), month=12, 31, ^holiday=New Year's Eve, ^is_holiday)"
        expected = [
            ASTNode("Date",
                    inputs=[
                        (None, ASTNode("str 25", is_terminal=True)),
                    ],
                    tags=[("holiday", "Christmas"), (None, "is_holiday")]
                    ),
            ASTNode("Date",
                    inputs=[
                        ("year", ASTNode("Int", [(None, ASTNode("2022", is_terminal=True))])),
                        ("month", ASTNode("12", is_terminal=True)),
                        (None, ASTNode("31", is_terminal=True)),
                    ],
                    tags=[("holiday", "New Year's Eve"), (None, "is_holiday")]
                    ),
        ]
        trees = parse_p_expressions(expression)
        self.assertEqual(expected, trees)

    def test_expression_7(self):
        expression = "<-?'>Date(year=Int(2022), month=12, 25, ^holiday=Christmas, ^is_holiday) "
        expression += "{my_date}<-?'>Date(year=Int(2022), month=12, 25, ^holiday=Christmas, ^is_holiday) "
        expression += "<-?'>{other_date}Date(year=Int(2022), month=12, 25, ^holiday=\"* Christmas *\", ^is_holiday) "
        expression += "{another_date}Date(year=Int(2022), month=12, 25, \" test \", ^holiday=Christmas, ^is_holiday) "
        expected = [
            ASTNode("Date",
                    inputs=[
                        ("year", ASTNode("Int", [(None, ASTNode("2022", is_terminal=True))])),
                        ("month", ASTNode("12", is_terminal=True)),
                        (None, ASTNode("25", is_terminal=True)),
                    ],
                    tags=[("holiday", "Christmas"), (None, "is_holiday")],
                    special_features="-?'"
                    ),
            ASTNode("Date",
                    inputs=[
                        ("year", ASTNode("Int", [(None, ASTNode("2022", is_terminal=True))])),
                        ("month", ASTNode("12", is_terminal=True)),
                        (None, ASTNode("25", is_terminal=True)),
                    ],
                    tags=[("holiday", "Christmas"), (None, "is_holiday")],
                    set_assign="my_date",
                    special_features="-?'"
                    ),
            ASTNode("Date",
                    inputs=[
                        ("year", ASTNode("Int", [(None, ASTNode("2022", is_terminal=True))])),
                        ("month", ASTNode("12", is_terminal=True)),
                        (None, ASTNode("25", is_terminal=True)),
                    ],
                    tags=[("holiday", "* Christmas *"), (None, "is_holiday")],
                    set_assign="other_date",
                    special_features="-?'"
                    ),
            ASTNode("Date",
                    inputs=[
                        ("year", ASTNode("Int", [(None, ASTNode("2022", is_terminal=True))])),
                        ("month", ASTNode("12", is_terminal=True)),
                        (None, ASTNode("25", is_terminal=True)),
                        (None, ASTNode(" test ", is_terminal=True)),
                    ],
                    tags=[("holiday", "Christmas"), (None, "is_holiday")],
                    set_assign="another_date",
                    ),
        ]
        trees = parse_p_expressions(expression)
        self.assertEqual(expected, trees)

    def test_expression_8(self):
        expression = "$#123 $my_ref $#-456 Str(#this{is}a node with a complex string  )"
        expected = [
            ASTNode("123", is_assign=True),
            ASTNode("my_ref", is_assign=True),
            ASTNode("-456", is_assign=True),
            ASTNode("Str", [(None, ASTNode("#this{is}a node with a complex string", is_terminal=True))]),
        ]
        trees = parse_p_expressions(expression)
        self.assertEqual(expected, trees)

    def test_expression_9(self):
        expression = ":dayOfWeek(Tomorrow())"
        expected = [
            ASTNode(":dayOfWeek", inputs=[(None, ASTNode("Tomorrow"))]),
        ]
        trees = parse_p_expressions(expression)
        self.assertEqual(expected, trees)

    def test_expression_10(self):
        expression = "{other_date}<-?'>Date(year=Int(2022), month=12, 25, ^holiday=\"* Christmas *\", ^is_holiday)"
        trees = parse_p_expressions(expression)
        self.assertEqual(expression.strip(), str(trees[0]))
