import re
import signal
from contextlib import contextmanager
from datetime import date, datetime, timedelta

# Security: Maximum time allowed for regex execution (seconds)
REGEX_TIMEOUT_SECONDS = 1

# Security: Maximum pattern length to prevent ReDoS
MAX_REGEX_PATTERN_LENGTH = 1000

# Security: Blocked attribute names (same as in cel_parser.py)
BLOCKED_ATTRIBUTES = frozenset(
    {
        "__class__",
        "__bases__",
        "__subclasses__",
        "__mro__",
        "__code__",
        "__globals__",
        "__builtins__",
        "__import__",
        "__dict__",
        "__module__",
        "_cr",
        "_uid",
        "_context",
        "_ids",
        "env",
        "sudo",
        "with_user",
        "with_context",
        "with_company",
        "cr",
        "cursor",
        "execute",
        "query",
    }
)


class RegexTimeoutError(Exception):
    """Raised when regex execution times out."""

    pass


@contextmanager
def _regex_timeout(seconds: int):
    """Context manager to limit regex execution time.

    Note: This uses SIGALRM which only works on Unix systems.
    On Windows, the timeout is not enforced.
    """

    def timeout_handler(signum, frame):
        raise RegexTimeoutError(f"Regex execution exceeded {seconds}s timeout")

    # Only set alarm on Unix systems
    if hasattr(signal, "SIGALRM"):
        old_handler = signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(seconds)
        try:
            yield
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)
    else:
        # Windows: no timeout enforcement
        yield


def _safe_hasattr(obj: any, name: str) -> bool:
    """Safely check if object has attribute, blocking dangerous attributes."""
    if name.startswith("_") or name in BLOCKED_ATTRIBUTES:
        return False
    return hasattr(obj, name)


def _safe_getattr(obj: any, name: str, default: any = None) -> any:
    """Safely get attribute, blocking dangerous attribute access."""
    if name.startswith("_") or name in BLOCKED_ATTRIBUTES:
        return default
    return getattr(obj, name, default)


def today():
    return date.today()


def now():
    return datetime.now()


def days_ago(n: int):
    return date.today() - timedelta(days=int(n))


def years_ago(n: int):
    try:
        n = int(n)
    except Exception:
        n = 0
    today_d = date.today()
    # naive year delta
    try:
        return today_d.replace(year=today_d.year - n)
    except ValueError:
        # Feb 29th case
        return today_d.replace(month=2, day=28, year=today_d.year - n)


def months_ago(n: int):
    n = int(n)
    today_d = date.today()
    y = today_d.year
    m = today_d.month - n
    while m <= 0:
        m += 12
        y -= 1
    d = min(today_d.day, 28)
    return date(y, m, d)


def age_years(d):
    if not d:
        return None
    if isinstance(d, datetime):
        d = d.date()
    if not isinstance(d, date):
        return None
    t = date.today()
    return t.year - d.year - ((t.month, t.day) < (d.month, d.day))


def between(x, a, b):
    return a <= x <= b


def size(collection):
    """Get size of a collection (list, dict, string, or Odoo recordset).

    Args:
        collection: Any object with __len__ or a falsy value

    Returns:
        int: Length of the collection, or 0 if None/empty

    Examples:
        >>> size([1, 2, 3])
        3
        >>> size("hello")
        5
        >>> size(None)
        0
    """
    if collection is None:
        return 0
    # Handle dict-like objects with 'ids' or 'count' (Odoo recordset representation)
    # Check this BEFORE __len__ since dicts also have __len__
    if isinstance(collection, dict):
        if "count" in collection:
            return collection["count"]
        if "ids" in collection:
            return len(collection["ids"])
        # Fall through to regular len() for normal dicts
    if hasattr(collection, "__len__"):
        return len(collection)
    return 0


def has(obj, field=None):
    """Check if an object has a non-empty field value.

    Can be called as:
    - has(obj, "field_name") - check if obj.field_name is non-empty
    - has(value) - check if value is non-empty (truthy)

    Args:
        obj: Object to check, or value if field is None
        field: Optional field name to check

    Returns:
        bool: True if the field/value exists and is non-empty

    Examples:
        >>> has({"name": "John"}, "name")
        True
        >>> has({"name": ""}, "name")
        False
        >>> has("non-empty")
        True
        >>> has(None)
        False

    Security:
        Access to private attributes (starting with _) and dangerous
        attributes like __class__, env, sudo, etc. is blocked.
    """
    if field is None:
        # Single argument: check if value is truthy
        return bool(obj)

    # Two arguments: check if obj.field is truthy
    if obj is None:
        return False

    # Security: Block access to private/dangerous attributes
    if isinstance(field, str) and (field.startswith("_") or field in BLOCKED_ATTRIBUTES):
        return False

    if isinstance(obj, dict):
        val = obj.get(field)
    elif _safe_hasattr(obj, field):
        val = _safe_getattr(obj, field)
    else:
        return False
    return bool(val)


def matches(string, pattern):
    """Check if string matches a regex pattern.

    Args:
        string: String to match against
        pattern: Regular expression pattern

    Returns:
        bool: True if the pattern matches anywhere in the string

    Examples:
        >>> matches("hello world", r"world")
        True
        >>> matches("hello", r"^hel")
        True
        >>> matches("hello", r"^world")
        False

    Security:
        - Pattern length is limited to MAX_REGEX_PATTERN_LENGTH (1000 chars)
        - Regex execution has a timeout of REGEX_TIMEOUT_SECONDS (1 second)
        - These limits prevent ReDoS (Regular Expression Denial of Service) attacks
    """
    if string is None:
        return False
    if not isinstance(string, str):
        string = str(string)
    if not isinstance(pattern, str):
        return False

    # Security: Limit pattern length to prevent ReDoS
    if len(pattern) > MAX_REGEX_PATTERN_LENGTH:
        return False

    try:
        # Security: Apply timeout to regex execution
        with _regex_timeout(REGEX_TIMEOUT_SECONDS):
            return bool(re.search(pattern, string))
    except (re.error, RegexTimeoutError):
        return False
