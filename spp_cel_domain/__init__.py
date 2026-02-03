from . import controllers
from . import exceptions
from . import models
from . import services
from . import wizard


def post_init_hook(env):
    """Register core CEL functions after module installation."""
    _register_core_functions(env)


def _register_core_functions(env):
    """Register core CEL functions with the function registry."""
    from .services.cel_functions import age_years, years_ago, between

    registry = env["spp.cel.function.registry"]

    # Register core functions
    registry.register("age_years", age_years)
    registry.register("years_ago", years_ago)
    registry.register("between", between)
