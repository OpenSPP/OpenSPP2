from . import models
from . import services


def post_init_hook(env):
    """Initialize disability CEL functions after module installation.

    This hook registers disability-specific CEL functions with the
    function registry for use in program eligibility expressions.
    """
    env["spp.cel.disability.functions"].register_disability_functions()
