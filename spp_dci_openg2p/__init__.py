import logging

from . import models
from . import services
from . import wizards

_logger = logging.getLogger(__name__)


# Fields the preset insists on every install/upgrade. Anything else on the
# variable (labels, descriptions, category) is left to whoever last edited it.
_EXPECTED_BINDING_FIELDS = (
    "source_type",
    "source_field",
    "external_provider_id",
    "dci_attribute_path",
    "value_type",
    "cache_strategy",
    "cache_ttl_seconds",
    "external_failure_policy",
    "state",
    "active",
)


# Per-variable bindings re-asserted on every install/upgrade. Each entry
# carries everything that varies between variables:
#
#   xml_id          - ir.model.data reference identifying the record
#   attribute_path  - dotted path applied to OpenG2P's reg_records[0]
#   value_type      - CEL value type; controls cache JSON typing and CEL
#                     SQL fast-path projection
#   state           - 'active' (live) or 'inactive' (skipped by precompute
#                     and resolver — used as a deferred-feature placeholder)
#
# ADD a row when introducing a new SR-sourced variable; the rest of the
# hook handles drift correction uniformly.
_PRESET_VARIABLES = (
    {
        "xml_id": "spp_dci_openg2p.var_is_poor",
        "attribute_path": "income_level",
        "value_type": "string",
        "state": "active",
    },
    # has_dependent_under_school_age is parked inactive — OpenG2P's
    # per-individual record does not embed household composition or
    # dependent birth dates, so the variable cannot be resolved without
    # a second OpenG2P endpoint call or schema extension. Kept here so
    # the data XML and the hook stay in sync; revive when OpenG2P
    # exposes the data. See CONFIGURE.md "Deferred features".
    {
        "xml_id": "spp_dci_openg2p.var_has_dependent_under_school_age",
        "attribute_path": "has_dependent_under_school_age",
        "value_type": "boolean",
        "state": "inactive",
    },
)


def post_init_hook(env):
    """Re-assert DCI bindings on every preset-owned CEL variable.

    Runs on every install AND upgrade of this module (Odoo invokes
    post_init_hook on -i and -u). Detects drift on each SR variable
    declared by this preset and rewrites the necessary fields so the
    bridge dispatcher can route them to OpenG2P.

    Why this exists vs. just trusting the data XML:

      1. The data XML uses noupdate="1", which Odoo honours by setting
         noupdate=True on the ir.model.data entries. On subsequent
         upgrades of THIS module, the XML is skipped — but operators
         may have clobbered the bindings manually, or another module's
         data load may have reset them. The hook is the one place that
         always runs on -u and can restore drift.

      2. spp.cel.variable records ship in DRAFT state by default. The
         preset must explicitly activate them so they participate in
         the cache pre-warm (active=True) and in the CEL resolver's
         symbol lookup (state='active'). The XML data load doesn't
         reliably push them through the state machine.

      3. If the data XML failed to apply for any reason (load-order
         issue, transient validation error during -i), the hook is the
         safety net that catches it.

    The hook does NOT touch ``spp_studio.var_has_disability`` — that
    binding is the responsibility of the DR-side preset
    (``spp_dci_openspp_dr``, ADR-024). If an earlier version of this
    preset bound ``has_disability`` to OpenG2P (FR-as-DR pretense), the
    binding is left in place on upgrade for backwards compatibility;
    operators can clear it manually or install the DR preset to override.
    """
    provider = env.ref(
        "spp_dci_openg2p.openg2p_dr_provider",
        raise_if_not_found=False,
    )
    if not provider:
        _logger.error(
            "spp_dci_openg2p.openg2p_dr_provider not found; cannot "
            "re-assert SR variable bindings. Verify "
            "data/openg2p_data_provider.xml loaded successfully."
        )
        return

    for binding in _PRESET_VARIABLES:
        xml_id = binding["xml_id"]
        variable = env.ref(xml_id, raise_if_not_found=False)
        if not variable:
            _logger.warning(
                "%s not found during post_init_hook; skipping DCI "
                "binding re-assert. Verify data/openg2p_cel_variables.xml "
                "loaded successfully.",
                xml_id,
            )
            continue

        is_active = binding["state"] == "active"
        expected = {
            "source_type": "external",
            "source_field": False,
            "external_provider_id": provider.id,
            "dci_attribute_path": binding["attribute_path"],
            "value_type": binding["value_type"],
            "cache_strategy": "ttl",
            "cache_ttl_seconds": 300,
            "external_failure_policy": "null",
            # state + active control whether the variable participates
            # in the resolver / precompute pipeline:
            #   - state='active' is the workflow status used by spp_studio's
            #     lifecycle and CEL symbol visibility
            #   - active=True is the Odoo archived/unarchived flag used by
            #     precompute_cached_variables' search domain
            # An "inactive" preset variable (e.g., a deferred-feature
            # placeholder) is kept registered but excluded from both
            # paths so the dispatcher never tries to fetch it.
            "state": binding["state"],
            "active": is_active,
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
            # Bypass workflow validation by writing state directly.
            # _pre_activate would reject draft -> active if source_type
            # is 'field' and the field is missing; we're flipping
            # source_type and state in the same write so that path
            # doesn't apply.
            variable.write(expected)
            _logger.info(
                "Re-asserted DCI binding on %s: %d field(s) restored (%s)",
                xml_id,
                len(drift),
                ", ".join(drift.keys()),
            )
        else:
            _logger.info(
                "%s DCI binding already correct; no changes.",
                xml_id,
            )
