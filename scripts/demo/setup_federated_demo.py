# ============================================================================
# SPDCI FEDERATED DEMO — ONE-SHOT SEED SCRIPT.  DO NOT SHIP IN PRODUCTION.
# ============================================================================
#
# Creates 4 demo registrants for the SPDCI dry-run on both sides of the
# federated topology (SP and OpenSPP-DR). Each partner's UIN reg_id matches
# a real OpenG2P SR seed identifier so the SP-side `is_poor` lookup returns
# a real `income_level` from OpenG2P during Enroll-Eligible.
#
# RUN ON SP:
#   docker compose exec openspp-dev odoo shell -d openspp --no-http \
#     < scripts/demo/setup_federated_demo.py
#
# RUN ON DR:
#   docker compose -f docker-compose.dr.yml exec openspp-dr \
#     odoo shell -d openspp_dr --no-http \
#     < scripts/demo/setup_federated_demo.py
#
# WHAT THIS IS NOT:
#   - Not a module. Production installs of any spp_* module create zero
#     registrants. This is an out-of-band seed script run ONLY before a
#     demo. Delete the partners after the demo.
#   - Not idempotent in a "fix any prior wrong state" sense. It's
#     idempotent in the "skip if UIN already exists" sense. To re-run
#     cleanly, first delete the partners (see CLEANUP at the bottom).
#
# WHAT IT CREATES:
#   - SP side: 4 res.partner records with UIN reg_ids matching OpenG2P
#     SR seeds (IND-NSR-0001, 0002, 0003, 0007).
#   - DR side: same 4 partners (same UINs) PLUS approved disability
#     assessments for two of them so their res.partner.has_disability
#     computes to True.
#
# DEMO MATRIX (after running on both sides):
#
#   | Persona            | UIN          | SR income_level | DR assessment | Expected verdict |
#   |--------------------|--------------|-----------------|---------------|------------------|
#   | Maria Widow        | IND-NSR-0001 | low             | approved      | ENROLLED         |
#   | Kim Lee            | IND-NSR-0007 | medium          | approved      | not eligible     |
#   | Priya Rivera       | IND-NSR-0002 | low             | none          | not eligible     |
#   | Noah Rivera        | IND-NSR-0003 | (empty)         | none          | not eligible     |
#
#   With CEL rule `has_disability == true && is_poor == "low"`:
#   - Only Maria passes (both registries return the right value)
#   - Kim fails is_poor (medium != low)
#   - Priya fails has_disability (no approved DR assessment)
#   - Noah fails both
# ============================================================================

import logging
from odoo import fields

_logger = logging.getLogger("setup_federated_demo")

# (UIN, given_name, surname, has_dr_assessment)
DEMO_PERSONAS = [
    ("IND-NSR-0001", "Maria",  "Widow",   True),   # eligible
    ("IND-NSR-0007", "Kim",    "Lee",     True),   # not poor (medium)
    ("IND-NSR-0002", "Priya",  "Rivera",  False),  # poor but not disabled
    ("IND-NSR-0003", "Noah",   "Rivera",  False),  # neither
]

# Detect side: DR-side has spp.disability.assessment installed
on_dr_side = "spp.disability.assessment" in env
side_label = "DR" if on_dr_side else "SP"
_logger.warning(
    "=== DEMO SEED: setting up %d federated-demo partners on the %s side. "
    "DO NOT use this in production. ===",
    len(DEMO_PERSONAS),
    side_label,
)
print(f"\n=== Setting up demo partners on the {side_label} side ===\n")

# Find UIN vocabulary code; use get_or_create_local to bypass system-vocab protection
vocab_id_type = env.ref("spp_vocabulary.vocab_id_type", raise_if_not_found=False)
if not vocab_id_type:
    raise RuntimeError("spp_vocabulary.vocab_id_type not found — install spp_vocabulary first")

Code = env["spp.vocabulary.code"]
uin_code = Code.with_context(active_test=False).search(
    [("vocabulary_id", "=", vocab_id_type.id), ("code", "=", "UIN")], limit=1,
)
if not uin_code:
    uin_code = Code.get_or_create_local(
        namespace_uri="urn:openspp:vocab:id-type",
        code="UIN",
        display="UIN (Universal Identification Number)",
    )
    print(f"  Seeded UIN vocab code (id={uin_code.id})")

Partner = env["res.partner"]
RegId = env["spp.registry.id"]

for uin, given, surname, has_dr_assessment in DEMO_PERSONAS:
    # Idempotent: skip if a partner already has this UIN
    existing = RegId.search([("value", "=", uin), ("id_type_id", "=", uin_code.id)], limit=1)
    if existing:
        partner = existing.partner_id
        print(f"  ↻  {uin} already exists on this side as partner.id={partner.id} ({partner.name})")
    else:
        partner = Partner.create({
            "name": f"{given} {surname}",
            "given_name": given,
            "family_name": surname,
            "is_registrant": True,
            "is_group": False,
            "birthdate": "1990-01-01",
        })
        RegId.create({
            "partner_id": partner.id,
            "id_type_id": uin_code.id,
            "value": uin,
        })
        print(f"  ✓  Created {given} {surname} (UIN={uin}, partner.id={partner.id})")

    # DR-side only: ensure an approved disability assessment exists
    # for the personas flagged has_dr_assessment.
    if on_dr_side and has_dr_assessment:
        Assessment = env["spp.disability.assessment"]
        existing_asmt = Assessment.search(
            [("registrant_id", "=", partner.id), ("approval_state", "=", "approved")], limit=1,
        )
        if existing_asmt:
            print(f"     - approved assessment already exists (id={existing_asmt.id})")
        else:
            asmt = Assessment.create({
                "registrant_id": partner.id,
                "assessment_date": fields.Date.today(),
                # Force has_disability=True by setting one WG domain to severe.
                # _compute_disability_indicator sets has_disability when any
                # WG_* field is 'a_lot' or 'cannot'.
                "wg_walking": "a_lot",
                "review_category": "mip",  # 3-year review cadence
            })
            # Bypass the approval workflow — direct write for demo seed only.
            asmt.write({"approval_state": "approved"})
            # Touch the related partner so has_disability propagates immediately.
            partner.invalidate_recordset(["current_disability_assessment_id", "has_disability"])
            print(f"     ✓ Created approved assessment (id={asmt.id}, "
                  f"partner.has_disability now {partner.has_disability})")

env.cr.commit()

# Summary
print("\n=== Summary ===")
for uin, given, surname, has_dr_assessment in DEMO_PERSONAS:
    reg = RegId.search([("value", "=", uin), ("id_type_id", "=", uin_code.id)], limit=1)
    p = reg.partner_id
    if on_dr_side:
        hd = "has_disability=True" if p.has_disability else "has_disability=False"
    else:
        hd = "(DR side controls disability)"
    print(f"  {uin}  partner.id={p.id:<5}  {p.name:<22}  {hd}")

print("\n=== Done. ===")
print("Next: run this same script against the OTHER side." if on_dr_side else
      "Next: run this same script against the DR (openspp_dr database).")
print("\nCLEANUP after the demo:")
print("  Delete the 4 partners via UI, or:")
print("  >>> uin_code = env.ref('spp_vocabulary.vocab_id_type')")
print("  >>> RegId = env['spp.registry.id']")
print("  >>> uins = ['IND-NSR-0001', 'IND-NSR-0007', 'IND-NSR-0002', 'IND-NSR-0003']")
print("  >>> partners = RegId.search([('value', 'in', uins)]).mapped('partner_id')")
print("  >>> partners.unlink()")
print("  >>> env.cr.commit()")
