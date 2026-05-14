import logging

from . import models
from . import services

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    """Re-assert the DCI binding on spp_studio.var_has_disability.

    The preset overrides spp_studio.var_has_disability so the semantic
    `has_disability` CEL accessor sources from OpenG2P over DCI instead
    of the local res.partner field. The override is declared in
    data/openg2p_cel_variables.xml with `noupdate="1"`, but that only
    protects against re-applying THIS module's data file. It does NOT
    protect against a future `-u spp_studio`, which would reset the
    variable back to source_type='field' from spp_studio's original
    standard_variables.xml.

    This hook re-asserts the DCI binding after every install/upgrade so
    the demo deployment stays correctly wired. The Odoo upgrade ordering
    guarantees this module's post_init_hook fires AFTER spp_studio's
    data files have been loaded, so any silent reset is undone here.
    """
    variable = env.ref("spp_studio.var_has_disability", raise_if_not_found=False)
    if not variable:
        _logger.warning(
            "spp_studio.var_has_disability not found during post_init_hook; skipping DCI binding re-assert."
        )
        return

    provider = env.ref("spp_dci_openg2p.openg2p_dr_provider", raise_if_not_found=False)
    if not provider:
        _logger.error(
            "spp_dci_openg2p.openg2p_dr_provider not found; cannot re-assert DCI binding on has_disability variable."
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
    }

    drift = {
        field: value
        for field, value in expected.items()
        if (variable[field].id if hasattr(variable[field], "id") else variable[field]) != value
    }
    if drift:
        variable.write(expected)
        _logger.info(
            "Re-asserted DCI binding on spp_studio.var_has_disability: %d field(s) restored (%s)",
            len(drift),
            ", ".join(drift.keys()),
        )
    else:
        _logger.debug("spp_studio.var_has_disability DCI binding already correct; no changes.")
