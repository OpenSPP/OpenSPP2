# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Value normalisation shared by the post-submit freeze guards.

Once a change request leaves draft, two guards compare an incoming write
payload against the stored value: one on ``spp.change.request`` for the fields
that bind it to what was routed and approved, and one on every
``spp.cr.detail.*`` model for its proposed-change fields. Both must normalise
identically -- if they disagree about what counts as a change, the same payload
is accepted by one and rejected by the other. Defining it once keeps them in
step, and means a gap has to be closed only once.

Deliberately model-free so importing it registers nothing: ``change_request`` is
imported before ``change_request_detail_base``, so having either import the
other would tie the freeze to model registration order.
"""


def normalize_frozen_value(value):
    """Normalize a value for comparison against a stored field value.

    - A recordset becomes its id, so a Many2one written as a recordset compares
      equal to the stored id rather than looking like a change.
    - ``None`` and ``""`` both become ``False``, which is what Odoo actually
      stores for an unset field. A JSON-RPC client or integration re-saving a
      record sends ``""`` for an empty Char; without collapsing it, that payload
      would not match the stored ``False`` and an idempotent re-save would be
      rejected as though it altered the approved content.
    """
    if hasattr(value, "id"):
        value = value.id
    if value is None or value == "":
        return False
    return value
