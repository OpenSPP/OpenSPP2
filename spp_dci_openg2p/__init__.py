import logging

from . import models
from . import services

_logger = logging.getLogger(__name__)


# Fields the preset insists on every install/upgrade. Anything else on the
# variable (labels, descriptions, category) is left to whoever last edited it.
_EXPECTED_BINDING_FIELDS = (
    "source_type",
    "source_field",
    "external_provider_id",
    "dci_attribute_path",
    "cache_strategy",
    "cache_ttl_seconds",
    "external_failure_policy",
    "state",
    "active",
)


def post_init_hook(env):
    """Re-assert the DCI binding on spp_studio.var_has_disability.

    Runs on every install AND upgrade of this module (Odoo invokes
    post_init_hook on -i and -u). Detects drift on the canonical
    has_disability variable and rewrites the necessary fields so the
    bridge dispatcher can route it to OpenG2P.

    Why this exists vs. just trusting the data XML override:

      1. The data XML uses noupdate="1", which Odoo honours by setting
         noupdate=True on the ir.model.data entry. On subsequent upgrades
         of THIS module, the XML is skipped — but operators may have
         clobbered the binding manually, or another module's data load
         may have reset it. The hook is the one place that always runs
         on -u and can restore drift.

      2. spp_studio's standard_variables.xml creates the record in DRAFT
         state by default. The preset must explicitly activate it so it
         participates in the cache pre-warm (`active=True`) and in the
         CEL resolver's symbol lookup (`state='active'`). The XML data
         load doesn't reliably push it through the state machine.

      3. If the data XML failed to apply for any reason (load-order
         issue, transient validation error during -i), the hook is the
         safety net that catches it.
    """
    variable = env.ref("spp_studio.var_has_disability", raise_if_not_found=False)
    if not variable:
        _logger.warning(
            "spp_studio.var_has_disability not found during post_init_hook; "
            "skipping DCI binding re-assert. Install spp_studio first."
        )
        return

    provider = env.ref("spp_dci_openg2p.openg2p_dr_provider", raise_if_not_found=False)
    if not provider:
        _logger.error(
            "spp_dci_openg2p.openg2p_dr_provider not found; cannot re-assert "
            "DCI binding on has_disability variable. Verify "
            "data/openg2p_data_provider.xml loaded successfully."
        )
        return

    expected = {
        "source_type": "external",
        "source_field": False,
        "external_provider_id": provider.id,
        "dci_attribute_path": "has_disability",
        "cache_strategy": "ttl",
        "cache_ttl_seconds": 300,
        "external_failure_policy": "null",
        # State + active control whether the variable participates in the
        # resolver / precompute pipeline:
        #   - state='active' is the workflow status (Draft / Active /
        #     Inactive) used by spp_studio's lifecycle and CEL symbol
        #     visibility
        #   - active=True is the standard Odoo archived/unarchived flag
        #     used by precompute_cached_variables' search domain
        "state": "active",
        "active": True,
    }

    drift = {}
    for field in _EXPECTED_BINDING_FIELDS:
        current = variable[field]
        # Many2one comparison: compare ids, not recordsets
        if hasattr(current, "id"):
            current_value = current.id if current else False
        else:
            current_value = current
        if current_value != expected[field]:
            drift[field] = expected[field]

    if drift:
        # Bypass workflow validation by writing state directly. _pre_activate
        # would reject draft -> active if source_type is 'field' and the
        # field is missing; we're flipping source_type and state in the same
        # write so that path doesn't apply.
        variable.write(expected)
        _logger.info(
            "Re-asserted DCI binding on spp_studio.var_has_disability: "
            "%d field(s) restored (%s)",
            len(drift),
            ", ".join(drift.keys()),
        )
    else:
        _logger.info(
            "spp_studio.var_has_disability DCI binding already correct; "
            "no changes."
        )
