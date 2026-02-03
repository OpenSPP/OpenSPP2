import hmac
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

# Security: Maximum recursion depth to prevent stack overflow DoS
MAX_RECURSION_DEPTH = 100

# Security: Blocked attribute names to prevent object traversal attacks
BLOCKED_ATTRIBUTES = frozenset(
    {
        # Python internals that enable code execution
        "__class__",
        "__bases__",
        "__subclasses__",
        "__mro__",
        "__code__",
        "__globals__",
        "__builtins__",
        "__import__",
        "__loader__",
        "__spec__",
        "__dict__",
        "__module__",
        "__qualname__",
        "__func__",
        "__self__",
        "__call__",
        "__getattr__",
        "__setattr__",
        "__delattr__",
        "__getattribute__",
        "__reduce__",
        "__reduce_ex__",
        # Odoo internals
        "_cr",
        "_uid",
        "_context",
        "_ids",
        "env",
        "sudo",
        "with_user",
        "with_context",
        "with_company",
        # Database access
        "cr",
        "cursor",
        "execute",
        "query",
    }
)

# Security: Forbidden keyword argument names to prevent injection attacks
FORBIDDEN_KWARG_NAMES = frozenset({"__class__", "__init__", "__dict__", "__globals__", "__builtins__"})


def _safe_getattr(obj: Any, name: str, default: Any = None) -> Any:
    """Safely get attribute, blocking dangerous attribute access.

    Args:
        obj: Object to get attribute from
        name: Attribute name
        default: Default value if attribute not found

    Returns:
        Attribute value or default

    Raises:
        AttributeError: If attribute is blocked for security
    """
    # Block private/magic attributes
    if name.startswith("_"):
        raise AttributeError(f"Access to private attribute '{name}' is not allowed")

    # Block known dangerous attributes
    if name in BLOCKED_ATTRIBUTES:
        raise AttributeError(f"Access to attribute '{name}' is not allowed")

    if hasattr(obj, name):
        return getattr(obj, name)
    if isinstance(obj, dict):
        return obj.get(name, default)
    return default


# AST Nodes
@dataclass
class Literal:
    value: Any


@dataclass
class Ident:
    name: str


@dataclass
class Attr:
    obj: Any
    name: str


@dataclass
class Call:
    func: Any  # Ident or Attr
    args: list[Any]
    kwargs: dict[str, Any] = field(default_factory=dict)  # Named arguments


@dataclass
class And:
    left: Any
    right: Any


@dataclass
class Or:
    left: Any
    right: Any


@dataclass
class Not:
    expr: Any


@dataclass
class Neg:
    """Unary negation (e.g., -5, -record.amount)."""

    expr: Any


@dataclass
class BinOp:
    """Binary arithmetic operation (e.g., a + b, a * b)."""

    op: str  # "ADD", "SUB", "MUL", "DIV", "MOD"
    left: Any
    right: Any


@dataclass
class Ternary:
    """Ternary conditional operator (e.g., condition ? true_expr : false_expr)."""

    condition: Any
    true_expr: Any
    false_expr: Any


@dataclass
class Compare:
    op: str
    left: Any
    right: Any


@dataclass
class InOp:
    left: Any
    items: list[Any]


class Token:
    def __init__(self, kind: str, value: Any, pos: int):
        self.kind = kind
        self.value = value
        self.pos = pos


# Parser keywords - mapped to token types
KEYWORDS = {
    "and": "AND",
    "or": "OR",
    "not": "NOT",
    "true": True,
    "false": False,
}

# Complete set of CEL reserved words that should not be treated as user variables
# This is the authoritative list for the CEL domain
CEL_RESERVED_WORDS = {
    # Boolean literals
    "true",
    "false",
    "null",
    # Logical operators
    "and",
    "or",
    "not",
    "in",
    # CEL standard macros
    "has",
    "all",
    "exists",
    "exists_one",
    "map",
    "filter",
    # CEL standard library functions and type constructors
    "size",
    "type",
    "int",
    "uint",
    "double",
    "string",
    "bytes",
    "duration",
    "timestamp",
    "list",
}

# Python builtins that are added to the CEL eval namespace
PYTHON_BUILTINS = {
    "len",
    "str",
    "int",
    "float",
    "bool",
    "abs",
    "min",
    "max",
    "sum",
}

# Common context variable names used in CEL expressions
# ADR-008: Added 'r' as the standard prefix for current record access
CEL_CONTEXT_IDENTIFIERS = {
    "m",
    "e",
    "r",
    "members",
    "enrollments",
    "entitlements",
}


class Lexer:
    def __init__(self, text: str):
        self.t = text
        self.i = 0

    def peek(self) -> str:
        return self.t[self.i : self.i + 1]

    def _ws(self):
        while self.peek() and self.peek().isspace():
            self.i += 1

    def number(self) -> Token:
        start = self.i
        while self.peek() and (self.peek().isdigit() or self.peek() == "."):
            self.i += 1
        num_str = self.t[start : self.i]
        try:
            value = float(num_str) if "." in num_str else int(num_str)
        except ValueError as e:
            raise SyntaxError(f"Invalid number '{num_str}' at position {start}") from e
        return Token("NUMBER", value, start)

    def ident(self) -> Token:
        start = self.i
        while self.peek() and (self.peek().isalnum() or self.peek() == "_"):
            self.i += 1
        val = self.t[start : self.i]
        if val in KEYWORDS:
            kw = KEYWORDS[val]
            if kw in (True, False):
                return Token("BOOL", kw, start)
            return Token(kw, val, start)
        return Token("IDENT", val, start)

    def string(self) -> Token:
        quote = self.peek()
        self.i += 1
        start = self.i
        parts: list[str] = []
        while self.peek():
            ch = self.peek()
            if ch == quote:
                break
            if ch == "\\":
                parts.append(self.t[start : self.i])
                self.i += 1  # consume backslash
                esc = self.peek()
                if not esc:
                    raise SyntaxError(f"Unterminated escape at position {self.i}")
                parts.append(esc)
                self.i += 1
                start = self.i
            else:
                self.i += 1
        if not self.peek():
            raise SyntaxError(f"Unterminated string starting at position {start - 1}")
        parts.append(self.t[start : self.i])
        s = "".join(parts)
        self.i += 1  # closing quote
        return Token("STRING", s, start - 1)

    def tokens(self) -> list[Token]:
        out: list[Token] = []
        self._ws()
        while self.peek():
            ch = self.peek()
            if ch.isdigit():
                out.append(self.number())
            elif ch.isalpha() or ch == "_":
                out.append(self.ident())
            elif ch in ('"', "'"):
                out.append(self.string())
            elif ch == "(" or ch == ")" or ch == "," or ch == "." or ch == "[" or ch == "]":
                out.append(Token(ch, ch, self.i))
                self.i += 1
            elif ch == "=" and self.t[self.i : self.i + 2] == "==":
                out.append(Token("EQ", "==", self.i))
                self.i += 2
            elif ch == "=":
                # Single '=' for named arguments in function calls
                out.append(Token("=", "=", self.i))
                self.i += 1
            elif ch == "!" and self.t[self.i : self.i + 2] == "!=":
                out.append(Token("NE", "!=", self.i))
                self.i += 2
            elif ch == "!":
                # Support '!' as a logical NOT operator, in addition to the
                # textual 'not' keyword. This is primarily for compatibility
                # with existing studio logic pack expressions.
                out.append(Token("NOT", "!", self.i))
                self.i += 1
            elif ch == "&" and self.t[self.i : self.i + 2] == "&&":
                out.append(Token("AND", "&&", self.i))
                self.i += 2
            elif ch == "|" and self.t[self.i : self.i + 2] == "||":
                out.append(Token("OR", "||", self.i))
                self.i += 2
            elif ch == ">" and self.t[self.i : self.i + 2] == ">=":
                out.append(Token("GE", ">=", self.i))
                self.i += 2
            elif ch == "<" and self.t[self.i : self.i + 2] == "<=":
                out.append(Token("LE", "<=", self.i))
                self.i += 2
            elif ch == ">":
                out.append(Token("GT", ">", self.i))
                self.i += 1
            elif ch == "<":
                out.append(Token("LT", "<", self.i))
                self.i += 1
            elif ch == "-":
                out.append(Token("MINUS", "-", self.i))
                self.i += 1
            elif ch == "+":
                out.append(Token("PLUS", "+", self.i))
                self.i += 1
            elif ch == "*":
                out.append(Token("STAR", "*", self.i))
                self.i += 1
            elif ch == "/":
                out.append(Token("SLASH", "/", self.i))
                self.i += 1
            elif ch == "%":
                out.append(Token("PERCENT", "%", self.i))
                self.i += 1
            elif ch == "?":
                out.append(Token("QUESTION", "?", self.i))
                self.i += 1
            elif ch == ":":
                out.append(Token("COLON", ":", self.i))
                self.i += 1
            else:
                raise SyntaxError(f"Unknown character '{ch}' at position {self.i}")
            self._ws()
        out.append(Token("EOF", None, self.i))
        return out


class Parser:
    def __init__(self, text: str):
        self.tokens = Lexer(text).tokens()
        self.i = 0

    def cur(self) -> Token:
        return self.tokens[self.i]

    def eat(self, kind: str) -> Token:
        if self.cur().kind != kind:
            raise SyntaxError(f"Expected {kind} at {self.cur().pos}")
        t = self.cur()
        self.i += 1
        return t

    def parse(self) -> Any:
        result = self.expr(0)
        # Ensure we consumed all tokens
        if self.cur().kind != "EOF":
            raise SyntaxError(f"Unexpected token {self.cur().kind} at {self.cur().pos}")
        return result

    PRECEDENCE = {
        "QUESTION": 1,  # Ternary has lowest precedence
        "OR": 2,
        "AND": 3,
        "IN": 4,
        "EQ": 5,
        "NE": 5,
        "GT": 6,
        "GE": 6,
        "LT": 6,
        "LE": 6,
        "PLUS": 7,
        "MINUS": 7,  # Binary minus (subtraction)
        "STAR": 8,
        "SLASH": 8,
        "PERCENT": 8,
    }

    def lbp(self, tok: Token) -> int:
        if tok.kind in self.PRECEDENCE:
            return self.PRECEDENCE[tok.kind]
        if tok.kind == "IDENT" and tok.value == "in":
            return self.PRECEDENCE["IN"]
        return 0

    def nud(self, tok: Token) -> Any:
        if tok.kind in ("NUMBER", "STRING", "BOOL"):
            return Literal(tok.value)
        if tok.kind == "IDENT":
            left: Any = Ident(tok.value)
            # Handle attribute access and function calls in a loop
            # to support: obj.attr, func(), func().attr, func().attr.method(), etc.
            while True:
                if self.cur().kind == ".":
                    self.eat(".")
                    name = self.eat("IDENT").value
                    left = Attr(left, name)
                elif self.cur().kind == "(":
                    self.eat("(")
                    args: list[Any] = []
                    kwargs: dict[str, Any] = {}
                    if self.cur().kind != ")":
                        while True:
                            # Check for keyword argument: IDENT = expr
                            if (
                                self.cur().kind == "IDENT"
                                and self.i + 1 < len(self.tokens)
                                and self.tokens[self.i + 1].kind
                                == "="  # nosemgrep: odoo-timing-attack-password - Token kind comparison in parser, not a secret value.
                            ):
                                # Parse as keyword argument
                                param_name = self.eat("IDENT").value
                                # Security: Block dangerous kwarg names
                                if param_name in FORBIDDEN_KWARG_NAMES or param_name.startswith("_"):
                                    pos = self.cur().pos
                                    raise SyntaxError(f"Forbidden keyword argument '{param_name}' at position {pos}")
                                self.eat("=")
                                param_value = self.expr(0)
                                kwargs[param_name] = param_value
                            else:
                                # Regular positional argument
                                args.append(self.expr(0))
                            if self.cur().kind == ",":
                                self.eat(",")
                                # Allow trailing comma
                                if self.cur().kind == ")":
                                    break
                                continue
                            break
                    self.eat(")")
                    left = Call(left, args, kwargs)
                else:
                    break
            return left
        if tok.kind == "(":
            expr = self.expr(0)
            self.eat(")")
            return expr
        if tok.kind == "[":
            items: list[Any] = []
            if self.cur().kind != "]":
                while True:
                    items.append(self.expr(0))
                    if self.cur().kind == ",":
                        self.eat(",")
                        # Allow trailing comma
                        if self.cur().kind == "]":
                            break
                        continue
                    break
            self.eat("]")
            return Literal([i.value if isinstance(i, Literal) else i for i in items])
        if tok.kind == "NOT":
            # NOT has low precedence - it applies to the whole expression that follows
            # e.g., "not me.age > 18" parses as "not (me.age > 18)"
            return Not(self.expr(0))
        if tok.kind == "MINUS":
            # Unary minus with high precedence (7)
            return Neg(self.expr(7))
        raise SyntaxError(f"Unexpected token {tok.kind} at {tok.pos}")

    def led(self, left: Any, tok: Token) -> Any:
        if tok.kind == "AND":
            return And(left, self.expr(self.PRECEDENCE["AND"]))
        if tok.kind == "OR":
            return Or(left, self.expr(self.PRECEDENCE["OR"]))
        if tok.kind in ("EQ", "NE", "GT", "GE", "LT", "LE"):
            return Compare(tok.kind, left, self.expr(self.PRECEDENCE[tok.kind]))
        if tok.kind == "IDENT" and tok.value == "in":
            # left IN [list]
            right = self.expr(self.PRECEDENCE["IN"])
            if isinstance(right, Literal) and isinstance(right.value, list):
                return InOp(left, right.value)
            raise SyntaxError("Right operand of 'in' must be a list literal")
        # Arithmetic operators
        if tok.kind == "PLUS":
            return BinOp("ADD", left, self.expr(self.PRECEDENCE["PLUS"]))
        if tok.kind == "MINUS":
            return BinOp("SUB", left, self.expr(self.PRECEDENCE["MINUS"]))
        if tok.kind == "STAR":
            return BinOp("MUL", left, self.expr(self.PRECEDENCE["STAR"]))
        if tok.kind == "SLASH":
            return BinOp("DIV", left, self.expr(self.PRECEDENCE["SLASH"]))
        if tok.kind == "PERCENT":
            return BinOp("MOD", left, self.expr(self.PRECEDENCE["PERCENT"]))
        # Ternary operator: condition ? true_expr : false_expr
        if tok.kind == "QUESTION":
            true_expr = self.expr(0)  # Parse until we hit COLON
            self.eat("COLON")
            false_expr = self.expr(self.PRECEDENCE["QUESTION"])  # Right-associative
            return Ternary(left, true_expr, false_expr)
        raise SyntaxError(f"Unexpected infix token {tok.kind}")

    def expr(self, rbp: int) -> Any:
        t = self.cur()
        self.i += 1
        left = self.nud(t)
        while self.lbp(self.cur()) > rbp:
            t = self.cur()
            self.i += 1
            left = self.led(left, t)
        return left


@lru_cache(maxsize=256)
def parse(text: str) -> Any:
    """Parse a CEL expression with caching.

    Args:
        text: CEL expression string to parse

    Returns:
        Parsed AST node

    Note:
        Results are cached using LRU cache with maxsize=256.
        This significantly improves performance for frequently used expressions.
    """
    return Parser(text).parse()


def evaluate(ast: Any, context: dict[str, Any], _depth: int = 0) -> Any:  # noqa: C901
    """Evaluate a CEL AST node against a context dictionary.

    Args:
        ast: Parsed CEL AST node (from parse())
        context: Dictionary of variable bindings
        _depth: Internal recursion depth counter (do not pass manually)

    Returns:
        The result of evaluating the expression

    Raises:
        RecursionError: If expression exceeds maximum recursion depth

    Example:
        >>> ast = parse("severity == 'critical' and priority == '3'")
        >>> evaluate(ast, {"severity": "critical", "priority": "3"})
        True
    """
    # Security: Check recursion depth to prevent stack overflow DoS
    if _depth > MAX_RECURSION_DEPTH:
        raise RecursionError(f"Expression exceeds maximum recursion depth of {MAX_RECURSION_DEPTH}")

    if isinstance(ast, Literal):
        return ast.value

    if isinstance(ast, Ident):
        return context.get(ast.name)

    if isinstance(ast, Attr):
        obj = evaluate(ast.obj, context, _depth + 1)
        if obj is None:
            return None
        # Security: Use safe getattr to block dangerous attribute access
        try:
            return _safe_getattr(obj, ast.name)
        except AttributeError:
            return None

    if isinstance(ast, And):
        left = evaluate(ast.left, context, _depth + 1)
        if not left:
            return False
        return bool(evaluate(ast.right, context, _depth + 1))

    if isinstance(ast, Or):
        left = evaluate(ast.left, context, _depth + 1)
        if left:
            return True
        return bool(evaluate(ast.right, context, _depth + 1))

    if isinstance(ast, Not):
        return not evaluate(ast.expr, context, _depth + 1)

    if isinstance(ast, Neg):
        val = evaluate(ast.expr, context, _depth + 1)
        if val is None:
            return None
        return -val

    if isinstance(ast, BinOp):
        left = evaluate(ast.left, context, _depth + 1)
        right = evaluate(ast.right, context, _depth + 1)
        if left is None or right is None:
            return None
        if ast.op == "ADD":
            return left + right
        if ast.op == "SUB":
            return left - right
        if ast.op == "MUL":
            return left * right
        if ast.op == "DIV":
            if right == 0:
                return None  # Division by zero returns None
            return left / right
        if ast.op == "MOD":
            if right == 0:
                return None  # Modulo by zero returns None
            return left % right
        return None

    if isinstance(ast, Ternary):
        condition = evaluate(ast.condition, context, _depth + 1)
        if condition:
            return evaluate(ast.true_expr, context, _depth + 1)
        return evaluate(ast.false_expr, context, _depth + 1)

    if isinstance(ast, Compare):
        left = evaluate(ast.left, context, _depth + 1)
        right = evaluate(ast.right, context, _depth + 1)
        return _compare(left, ast.op, right)

    if isinstance(ast, InOp):
        left = evaluate(ast.left, context, _depth + 1)
        return left in ast.items

    if isinstance(ast, Call):
        func = evaluate(ast.func, context, _depth + 1)
        # Security: Only allow functions explicitly registered in context
        # Functions must be in context (not from object traversal) to be callable
        if callable(func) and _is_allowed_callable(func, context):
            args = [evaluate(arg, context, _depth + 1) for arg in ast.args]
            kwargs = {k: evaluate(v, context, _depth + 1) for k, v in ast.kwargs.items()}
            return func(*args, **kwargs)
        return func

    return None


def _is_allowed_callable(func: Any, context: dict[str, Any]) -> bool:
    """Check if a callable is explicitly allowed (registered in context).

    This prevents arbitrary function execution from object traversal.

    Args:
        func: The callable to check
        context: The evaluation context

    Returns:
        bool: True if the callable is allowed
    """
    # Check direct identity first
    for value in context.values():
        if value is func:
            return True

    # Check if it's a wrapper with matching __name__
    func_name = getattr(func, "__name__", None)
    if func_name:
        for value in context.values():
            if callable(value) and getattr(value, "__name__", None) == func_name:
                return True

    return False


def _compare(left: Any, op: str, right: Any) -> bool:
    """Perform comparison based on operator."""
    try:
        if op == "EQ":
            if isinstance(left, (str, bytes)) and isinstance(right, (str, bytes)):
                return hmac.compare_digest(left, right)
            return left == right
        if op == "NE":
            if isinstance(left, (str, bytes)) and isinstance(right, (str, bytes)):
                return not hmac.compare_digest(left, right)
            return left != right
        if op == "GT":
            return left > right
        if op == "GE":
            return left >= right
        if op == "LT":
            return left < right
        if op == "LE":
            return left <= right
    except (TypeError, ValueError):
        return False
    return False


# GRM Tickets Profile Helper Functions
def days_since(date_value):
    """Calculate days since a given date.

    Args:
        date_value: A date or datetime object

    Returns:
        int: Number of days since the date (0 if date_value is None/invalid)

    Example:
        >>> from datetime import date, timedelta
        >>> yesterday = date.today() - timedelta(days=1)
        >>> days_since(yesterday)
        1
    """
    if not date_value:
        return 0
    from datetime import date, datetime

    if isinstance(date_value, datetime):
        date_value = date_value.date()
    if isinstance(date_value, date):
        return (date.today() - date_value).days
    return 0


def hours_since(datetime_value):
    """Calculate hours since a given datetime.

    Args:
        datetime_value: A datetime object

    Returns:
        float: Number of hours since the datetime (0 if datetime_value is None/invalid)

    Example:
        >>> from datetime import datetime, timedelta
        >>> two_hours_ago = datetime.now() - timedelta(hours=2)
        >>> hours_since(two_hours_ago)
        2.0...
    """
    if not datetime_value:
        return 0
    from datetime import datetime

    if isinstance(datetime_value, datetime):
        delta = datetime.now() - datetime_value
        return delta.total_seconds() / 3600
    return 0


def is_business_day(date_value):
    """Check if a date is a business day (Mon-Fri).

    Args:
        date_value: A date or datetime object

    Returns:
        bool: True if the date is Monday-Friday, False otherwise

    Example:
        >>> from datetime import date
        >>> is_business_day(date(2025, 11, 26))  # Wednesday
        True
        >>> is_business_day(date(2025, 11, 29))  # Saturday
        False
    """
    if not date_value:
        return False
    from datetime import date, datetime

    if isinstance(date_value, datetime):
        date_value = date_value.date()
    if isinstance(date_value, date):
        return date_value.weekday() < 5  # 0-4 are Mon-Fri
    return False


def cel_min(*args):
    """Return the minimum of the arguments.

    Args:
        *args: Numbers to compare

    Returns:
        The minimum value, or None if no valid numbers
    """
    valid_args = [a for a in args if a is not None and isinstance(a, int | float)]
    if not valid_args:
        return None
    return min(valid_args)


def cel_max(*args):
    """Return the maximum of the arguments.

    Args:
        *args: Numbers to compare

    Returns:
        The maximum value, or None if no valid numbers
    """
    valid_args = [a for a in args if a is not None and isinstance(a, int | float)]
    if not valid_args:
        return None
    return max(valid_args)


def cel_size(collection):
    """Return the size/length of a collection.

    Args:
        collection: A list, dict, string, or other collection

    Returns:
        The length of the collection, or 0 if None/empty
    """
    if collection is None:
        return 0
    try:
        return len(collection)
    except TypeError:
        return 0


def get_default_functions():
    """Get the default CEL functions for GRM tickets profile.

    Returns:
        dict: Dictionary of function name to function object
    """
    return {
        "days_since": days_since,
        "hours_since": hours_since,
        "is_business_day": is_business_day,
        "min": cel_min,
        "max": cel_max,
        "size": cel_size,
    }
