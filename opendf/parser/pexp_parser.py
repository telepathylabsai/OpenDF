"""
Parser for P-expressions.
"""
import re

# noinspection PyUnresolvedReferences
from typing import List, Optional, Any, Tuple

# TODO: add ply to requirements, when it is ready
# noinspection PyPackageRequirements
import ply.lex as lex
# noinspection PyPackageRequirements
import ply.yacc as yacc

# IDENTIFIER_EXPRESSION = r"[:a-zA-Z0-9_-][^\=,\(\)\<\>\{\}\#\$]*"
from opendf.exceptions.python_exception import LexerException, ParserException

IDENTIFIER_EXPRESSION = r"[:a-zA-Z0-9_\-\+\#][^\=,\(\)]*"
# IDENTIFIER_EXPRESSION = r"[:a-zA-Z0-9_-][^\=,\(\)]*"
IDENTIFIER_REGEX = re.compile(IDENTIFIER_EXPRESSION)

QUOTED_STRING_EXPRESSION = r"(\"(\\.|[^\"])*\"|\'(\\.|[^\'])*\')"
QUOTED_STRING_REGEX = re.compile(QUOTED_STRING_EXPRESSION)

TAG_CHAR = "^"


def sort_key_name(key):
    name, _ = key
    if name is None:
        name = ""
    return name


def sort_key_name_and_value(key):
    name, value = key
    if name is None:
        name = ""
    return name, value


def escape_string(string, quote_mark="\""):
    """
    Returns an escaped version of the `string`, that either conforms with `IDENTIFIER_REGEX` or are proper surround
    by quotes.

    :param string: the string
    :type string: str
    :param quote_mark: the quote mark to use, either single or double quotes
    :type quote_mark: str
    :return: the escaped string
    :rtype: str
    """
    match = IDENTIFIER_REGEX.match(string)
    if match is not None and match.group() == string:
        return string

    match = QUOTED_STRING_REGEX.match(string)
    if match is not None and match.group() == string:
        return string

    result = [quote_mark]
    escape_symbol = False
    for char in string:
        if escape_symbol:
            # the previous char entered escape mode, whatever comes now is escaped and it exits escape mode
            escape_symbol = False
        else:
            # it is not in escape mode
            if char == "\\":
                # it entered escape mode
                escape_symbol = True
            elif char == quote_mark:
                # it is an unescaped ", it needs to be escaped
                result.append("\\")
            # it is something else that does not need escaping
        result.append(char)
    if escape_symbol:
        # string ended at escape mode, it needs to exit escape mode; otherwise, the final quote will be escaped
        result.append("\\")
    result.append(quote_mark)

    return "".join(result)


class ASTNode:
    """
    Represents a P-expression node of the Abstract Syntax Tree (AST)
    """

    def __init__(self, name, inputs=(), tags=(), parent=None, role=None, set_assign=None, special_features=None,
                 is_terminal=False, is_assign=False):
        f"""
        Creates a ASTNode.

        :param name: the name of the node
        :type name: Any
        :param inputs: the inputs of the node as pairs of names and values, where the name might be empty
        :type inputs: List[Tuple[str, Node]]  # TODO: A dict might be better
        :param tags: the tags of the node as pairs of names and values
        :type tags: List[Tuple[str, str]]  # TODO: a dict might be better, we may support other values
        :param parent: the parent of the node
        :type parent: ASTNode or None
        :param role: the name of this node on the list of inputs of the parent
        :type role: str or None
        :param set_assign: a reference name for the node, defined as `{{set_assign}}` before the node
        :type set_assign: str or None
        :param special_features: the set of special features
        :type special_features: str or None
        :param is_terminal: whether or not the node is a terminal value
        :type is_terminal: bool
        :param is_assign: whether or not the node is a reference to another node
        :type is_assign: bool
        """
        self.name = name
        self.inputs = list(inputs)
        for i_name, i_value in self.inputs:
            i_value.parent = self
            i_value.role = i_name
        self.tags = list(tags)
        self.parent = parent
        self.role = role
        self.set_assign = set_assign
        self.special_features = special_features
        self.is_terminal = is_terminal
        self.is_assign = is_assign

    def __repr__(self):
        if self.is_assign:
            try:
                int_name = int(self.name)
                return f"$#{int_name}"
            except:
                return f"${self.name}"

        message = ""

        if self.set_assign:
            message += f"{{{self.set_assign}}}"

        if self.special_features:
            message += f"<{self.special_features}>"

        message += escape_string(self.name)

        if not self.is_terminal:
            message += "("
            input_str = []
            for name, value in self.inputs:
                if name:
                    input_str.append(f"{name}={value}")
                else:
                    input_str.append(f"{value}")
            for name, value in self.tags:
                value = escape_string(value)
                if name:
                    input_str.append(f"{TAG_CHAR}{name}={value}")
                else:
                    input_str.append(f"^{value}")
            if input_str:
                message += ", ".join(input_str)
            message += ")"

        return message

    def __eq__(self, other):
        if not isinstance(other, ASTNode):
            return False

        if self.name != other.name:
            return False

        if self.inputs:
            if not other.inputs:
                return False
            if sorted(self.inputs, key=sort_key_name) != sorted(other.inputs, key=sort_key_name):
                return False
        else:
            if other.inputs:
                return False

        if self.tags:
            if not other.tags:
                return False
            if sorted(self.tags, key=sort_key_name_and_value) != sorted(other.tags, key=sort_key_name_and_value):
                return False
        else:
            if other.tags:
                return False

        # checking for equality between the parents would create an infinite loop, we break the loop by checking only
        # for the name of the parents
        if self.parent is None:
            if other.parent is not None:
                return False
        else:
            if other.parent is None:
                return False
            else:
                if self.parent.name != other.parent.name:
                    return False

        if self.role != other.role:
            return False

        if self.set_assign != other.set_assign:
            return False

        if self.special_features:
            if not other.special_features:
                return False
            if sorted(self.special_features) != sorted(other.special_features):
                return False
        else:
            if other.special_features:
                return False

        if self.is_terminal != other.is_terminal:
            return False

        if self.is_assign != other.is_assign:
            return False

        return True


# noinspection PyMissingOrEmptyDocstring,PyPep8Naming,PySingleQuotedDocstring,PyMethodMayBeStatic
class PExpLexer:
    """
    Lexer for P-expressions.
    """

    tokens = [
        "IDENTIFIER",
        "OPEN_ARGUMENTS",
        "CLOSE_ARGUMENTS",
        "ITEM_SEPARATOR",
        "NAME_VALUE_SEPARATOR",
        "TAG_CHAR",
        "SPECIAL_FEATURE",
        "DECLARE_ASSIGN_NAME",
        "ASSIGN_NAME",
        "ASSIGN_NODE_NUMBER",
        "ASSIGN_NODE",
        "QUOTED_STRING",
    ]
    """List of tokens names."""

    t_IDENTIFIER = IDENTIFIER_EXPRESSION
    # t_IDENTIFIER = r"[:a-zA-Z_-][a-zA-Z0-9_\-\?\[\]]*"  # original, simpler one
    t_OPEN_ARGUMENTS = r"\("
    t_CLOSE_ARGUMENTS = r"\)"
    t_ITEM_SEPARATOR = r","
    t_NAME_VALUE_SEPARATOR = r"="
    t_TAG_CHAR = r"\^"
    t_SPECIAL_FEATURE = r"\<[^\<\>]+\>"
    t_ASSIGN_NODE = r"\$"
    t_QUOTED_STRING = r"(\"(\\.|[^\"])*\"|\'(\\.|[^\'])*\')"

    ignore_COMMENT = r'//[^\r\n]*'
    ignore_BLOCK_COMMENT = r"/\*([^\*]|\*[^/])*\*/"

    t_ignore = " \t\n"

    def __init__(self, **kwargs):
        """
        Creates a P-expression lexer.
        """
        self.lexer = lex.lex(module=self, **kwargs)

    def input(self, data):
        return self.lexer.input(data)

    def token(self):
        return self.lexer.token()

    # the substring that matches the ASSIGN NAME MUST be a subset of the set matched by identifier
    # the ASSIGN NAME below (inside curly brackets) must be equal the sub-regex below, after $ sign
    def t_DECLARE_ASSIGN_NAME(self, t):
        r"\{[a-zA-Z_-][a-zA-Z0-9\~_-]+\}"
        t.value = t.value[1:-1].strip()
        return t

    # the ASSIGN NAME above (inside curly brackets) must be equal the sub-regex below, after $ sign
    def t_ASSIGN_NAME(self, t):
        r"\$[ \t\n]*[a-zA-Z_-][a-zA-Z0-9_-]+"
        t.value = t.value[1:].strip()
        return t

    def t_ASSIGN_NODE_NUMBER(self, t):
        r"\$\#-?[0-9]+"
        t.value = t.value[2:].strip()
        return t

    def t_COMMENT(self, t):
        r'//[^\r\n]*'
        pass

    def t_BLOCK_COMMENT(self, t):
        r"/\*([^\*]|\*[^/])*\*/"
        pass

    def t_error(self, t):
        raise LexerException(t)


# noinspection PyMethodMayBeStatic,PyMissingOrEmptyDocstring
def _split_input_and_tags(values):
    inputs = []
    tags = []
    for name, value in values:
        if name is None or name[0] != TAG_CHAR:
            inputs.append((name, value))
        else:
            tag_name = name[1:]
            if not tag_name:
                tag_name = None
            tags.append((tag_name, value.name))

    return inputs, tags


class PExpParser:
    """
    Parser for P-expressions.
    """

    def __init__(self, lexer, **kwargs):
        """
        Creates a P-expression parser.

        :param lexer: the P-expression lexer
        :type lexer: PExpLexer
        """
        self.lexer = lexer
        self.tokens = lexer.tokens
        self.parser = yacc.yacc(module=self, **kwargs)

        self.parsed_trees: List[ASTNode] = []

    def parse(self, expressions):
        """
        Parses the `expressions`.

        :param expressions: the P-expressions
        :type expressions: str
        :return: the parsed expressions
        :rtype: List[ASTNode]
        """
        self.parsed_trees = []
        self.parser.parse(input=expressions, lexer=self.lexer)
        value = self.parsed_trees
        self.parsed_trees = []

        return value

    def p_program_single(self, p):
        """program : value"""
        self.parsed_trees.append(p[1])

    def p_program_multiple(self, p):
        """program : program value"""
        self.parsed_trees.append(p[2])

    def p_parameters_single(self, p):
        """parameters : parameter"""
        p[0] = []
        if p[1] is not None:
            p[0].append(p[1])

    def p_parameters_many(self, p):
        """parameters : parameters ITEM_SEPARATOR parameter"""
        p[0] = p[1]
        p[0].append(p[3])

    def p_parameter_empty(self, p):
        """parameter :"""
        pass

    def p_parameter_simple(self, p):
        """parameter : tag_parameter
                     | simple_parameter"""
        p[0] = p[1]

    def p_parameter_value(self, p):
        """simple_parameter : value"""
        p[0] = (None, p[1])

    def p_parameter_name_value(self, p):
        """simple_parameter : name NAME_VALUE_SEPARATOR value"""
        p[0] = (p[1], p[3])

    def p_tag_parameter(self, p):
        """tag_parameter : TAG_CHAR simple_parameter"""
        name = p[2][0]
        if name is None:
            name = ""
        p[0] = (TAG_CHAR + name, p[2][1])

    def p_name(self, p):
        """name : IDENTIFIER"""
        p[0] = p[1].strip()

    def p_value_by_name_reference(self, p):
        """value : ASSIGN_NAME"""
        p[0] = ASTNode(p[1], is_assign=True)

    def p_value_by_number_reference(self, p):
        """value : ASSIGN_NODE_NUMBER"""
        p[0] = ASTNode(p[1], is_assign=True)

    def p_value_with_name(self, p):
        """value : DECLARE_ASSIGN_NAME value"""
        value: ASTNode = p[2]
        value.set_assign = p[1]
        p[0] = value

    def p_value_with_feature(self, p):
        """value : SPECIAL_FEATURE value"""
        value: ASTNode = p[2]
        value.special_features = p[1][1:-1]
        p[0] = value

    def p_value_non_terminal(self, p):
        """value : expression"""
        p[0] = p[1]

    def p_expression(self, p):
        """expression : IDENTIFIER OPEN_ARGUMENTS parameters CLOSE_ARGUMENTS"""
        inputs, tags = _split_input_and_tags(p[3])
        p[0] = ASTNode(p[1].strip(), inputs=inputs, tags=tags)

    def p_value_terminal_identifier(self, p):
        """value : IDENTIFIER"""
        p[0] = ASTNode(p[1].strip(), is_terminal=True)

    def p_value_terminal_quote(self, p):
        """value : QUOTED_STRING"""
        unquoted = p[1][1:-1]
        p[0] = ASTNode(unquoted, is_terminal=True)

    def p_error(self, p):
        raise ParserException(p)


lexer = PExpLexer()
parser = PExpParser(lexer)


def parse_p_expressions(expressions):
    """
    Parses the P-expression in `expressions`.

    :param expressions: the P-expressions
    :type expressions: str
    :return: the parsed expressions
    :rtype: List[ASTNode]
    """

    return parser.parse(expressions)
