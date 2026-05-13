"""Bridge-specific exceptions.

Distinguish *configuration* errors (broken setup, unsupported handler)
from *runtime* errors (transient registry failures). Configuration errors
must surface immediately to operators; runtime errors are subject to the
variable's external_failure_policy (null / last_known / fail).
"""

from odoo.exceptions import UserError


class DCIConfigurationError(UserError):
    """Setup-time problem with the DCI integration.

    Examples:
      - The DCI client module required by a variable's registry_type is
        not installed (handler hits the ImportError branch).
      - A variable's registry_type has no concrete handler (e.g., SR/FR
        in v1).
      - Required configuration on a data source or provider is missing
        and cannot be silently substituted.

    Always propagates through _compute_dci_values regardless of policy.
    Operators must see broken integration immediately — silently treating
    these as "no one is eligible" is a compliance hazard.
    """
