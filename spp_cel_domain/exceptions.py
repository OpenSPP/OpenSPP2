"""CEL Domain Exception Hierarchy.

Provides specific exception types for better error handling and user feedback.
"""


class CELError(Exception):
    """Base exception for all CEL-related errors."""

    def __init__(self, message, details=None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class CELSyntaxError(CELError):
    """Raised when the CEL expression has syntax errors.

    This is a user-fixable error - the expression text is malformed.
    """

    def __init__(self, message, line=None, column=None, expression=None):
        super().__init__(message, {"line": line, "column": column, "expression": expression})
        self.line = line
        self.column = column
        self.expression = expression


class CELSymbolError(CELError):
    """Raised when an unknown field or symbol is referenced.

    This is a user-fixable error - the field name doesn't exist in the profile.
    """

    def __init__(self, symbol, available_symbols=None, profile=None):
        message = f"Unknown symbol: '{symbol}'"
        if available_symbols:
            message += f". Available: {', '.join(sorted(available_symbols)[:10])}"
        super().__init__(
            message,
            {"symbol": symbol, "available": available_symbols, "profile": profile},
        )
        self.symbol = symbol
        self.available_symbols = available_symbols
        self.profile = profile


class CELTypeError(CELError):
    """Raised when there's a type mismatch in the expression.

    Examples: comparing string to number, using exists() on non-relation field.
    """

    def __init__(self, message, expected_type=None, actual_type=None, field=None):
        super().__init__(message, {"expected": expected_type, "actual": actual_type, "field": field})
        self.expected_type = expected_type
        self.actual_type = actual_type
        self.field = field


class CELFunctionError(CELError):
    """Raised when a function call is invalid.

    Examples: wrong number of arguments, unknown function name.
    """

    def __init__(self, function_name, message, available_functions=None):
        full_message = f"Function '{function_name}': {message}"
        super().__init__(full_message, {"function": function_name, "available": available_functions})
        self.function_name = function_name
        self.available_functions = available_functions


class CELExecutionError(CELError):
    """Raised when expression execution fails at runtime.

    This may indicate a system error rather than a user error.
    """

    def __init__(self, message, plan=None, partial_results=None):
        super().__init__(message, {"plan": str(plan), "partial_results": partial_results})
        self.plan = plan
        self.partial_results = partial_results


class CELMetricsUnavailableError(CELError):
    """Raised when metrics are referenced but spp_indicators is not installed."""

    def __init__(self, metric_name=None):
        message = "Metrics functionality requires the spp_indicators module to be installed"
        if metric_name:
            message = f"Cannot evaluate metric '{metric_name}': {message}"
        super().__init__(message, {"metric": metric_name})
        self.metric_name = metric_name


class CELProfileError(CELError):
    """Raised when a profile configuration is invalid or missing."""

    def __init__(self, profile_name, message):
        full_message = f"Profile '{profile_name}': {message}"
        super().__init__(full_message, {"profile": profile_name})
        self.profile_name = profile_name


class CELValidationError(CELError):
    """Raised when an expression violates scalability or security constraints.

    Examples: IN clause with too many items, expressions that would generate
    inefficient queries at scale.
    """

    def __init__(self, message, constraint=None, limit=None, actual=None):
        super().__init__(message, {"constraint": constraint, "limit": limit, "actual": actual})
        self.constraint = constraint
        self.limit = limit
        self.actual = actual
