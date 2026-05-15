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
#     < scripts/demo/setup_spdci_demo.py
#
# RUN ON DR:
#   docker compose -f docker-compose.dr.yml exec openspp-dr \
#     odoo shell -d openspp_dr --no-http \
#     < scripts/demo/setup_spdci_demo.py
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
#   - SP side: 15 res.partner records with UIN reg_ids matching every
#     OpenG2P SR seed in the IND-NSR-0001..IND-NSR-0015 range. Names
#     mirror OpenG2P's actual seed names so the federation story stays
#     honest (an SP-side audit row tagged "Alex Rivera" matches what
#     OpenG2P would return on probe). If a partner with a given UIN
#     already exists, it is RENAMED to match the persona rather than
#     skipped — this keeps the script reusable when prior partners are
#     already attached to programs and can't be deleted.
#   - SP side, additionally: every demo partner is added as a draft
#     membership of program record id=DEMO_PROGRAM_ID (default 1) so
#     Enroll Eligible can be demonstrated directly. Override the constant
#     at the top of the script before running if your program record's
#     id differs.
#   - DR side: same 15 partners PLUS approved disability assessments
#     for 8 of them, distributed so the eligibility matrix exercises
#     all four poor×disabled quadrants.
#
# DEMO MATRIX (with CEL rule `has_disability == true && is_poor == "low"`):
#
#   | UIN          | Persona       | OpenG2P income | DR assessment | Verdict        |
#   |--------------|---------------|----------------|---------------|----------------|
#   | IND-NSR-0001 | Alex Rivera   | low            | approved      | ENROLLED       |
#   | IND-NSR-0002 | Priya Rivera  | low            | none          | not eligible*  |
#   | IND-NSR-0003 | Noah Rivera   | (empty)        | none          | not eligible   |
#   | IND-NSR-0004 | Morgan Cole   | low            | approved      | ENROLLED       |
#   | IND-NSR-0005 | Leah Cole     | low            | none          | not eligible*  |
#   | IND-NSR-0006 | Nia Cole      | (empty)        | approved      | not eligible** |
#   | IND-NSR-0007 | Kim Lee       | medium         | approved      | not eligible** |
#   | IND-NSR-0008 | Jun Lee       | medium         | none          | not eligible   |
#   | IND-NSR-0009 | Rin Lee       | (empty)        | approved      | not eligible** |
#   | IND-NSR-0010 | Taylor Brooks | low            | approved      | ENROLLED       |
#   | IND-NSR-0011 | Iris Brooks   | (empty)        | none          | not eligible   |
#   | IND-NSR-0012 | Reyn Brooks   | (empty)        | none          | not eligible   |
#   | IND-NSR-0013 | Sam Hayes     | low            | approved      | ENROLLED       |
#   | IND-NSR-0014 | Dev Hayes     | low            | none          | not eligible*  |
#   | IND-NSR-0015 | Asha Hayes    | (empty)        | approved      | not eligible** |
#
#   *  = poor but not disabled (DR says no) — exercises has_disability filter
#   ** = disabled but not poor (SR says no/medium) — exercises is_poor filter
#
#   Enrolled count: 4 / 15. Every quadrant of the (poor × disabled) matrix
#   is represented, so the demo can visibly show that BOTH registries must
#   agree before a registrant qualifies.
# ============================================================================

import logging

from odoo import fields

_logger = logging.getLogger("setup_spdci_demo")

# On the SP side, the script also adds every demo partner as a draft
# membership of this program so Edwin can demo Enroll Eligible directly
# without walking through the change-request flow. Override before
# running if your program record's id differs.
DEMO_PROGRAM_ID = 1

# Each tuple: (UIN, given_name, surname, has_dr_assessment)
# Names match OpenG2P SR seed records (probed 2026-05-15 against
# partner-nsr.play.openg2p.org). has_dr_assessment toggles whether we
# create an approved disability assessment on the DR side — this is
# what makes res.partner.has_disability compute to True.
DEMO_PERSONAS = [
    ("IND-NSR-0001", "Alex", "Rivera", True),  # poor + disabled  -> ENROLLED
    ("IND-NSR-0002", "Priya", "Rivera", False),  # poor only
    ("IND-NSR-0003", "Noah", "Rivera", False),  # neither
    ("IND-NSR-0004", "Morgan", "Cole", True),  # poor + disabled  -> ENROLLED
    ("IND-NSR-0005", "Leah", "Cole", False),  # poor only
    ("IND-NSR-0006", "Nia", "Cole", True),  # disabled only (no income)
    ("IND-NSR-0007", "Kim", "Lee", True),  # disabled only (medium income)
    ("IND-NSR-0008", "Jun", "Lee", False),  # neither (medium income, no disability)
    ("IND-NSR-0009", "Rin", "Lee", True),  # disabled only (no income)
    ("IND-NSR-0010", "Taylor", "Brooks", True),  # poor + disabled  -> ENROLLED
    ("IND-NSR-0011", "Iris", "Brooks", False),  # neither
    ("IND-NSR-0012", "Reyn", "Brooks", False),  # neither
    ("IND-NSR-0013", "Sam", "Hayes", True),  # poor + disabled  -> ENROLLED
    ("IND-NSR-0014", "Dev", "Hayes", False),  # poor only
    ("IND-NSR-0015", "Asha", "Hayes", True),  # disabled only (no income)
]

# Detect side: DR-side has spp.disability.assessment installed
on_dr_side = "spp.disability.assessment" in env
side_label = "DR" if on_dr_side else "SP"
_logger.warning(
    "=== DEMO SEED: setting up %d federated-demo partners on the %s side. DO NOT use this in production. ===",
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
    [("vocabulary_id", "=", vocab_id_type.id), ("code", "=", "UIN")],
    limit=1,
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

demo_partners = env["res.partner"].browse()

for uin, given, surname, has_dr_assessment in DEMO_PERSONAS:
    # If a partner already has this UIN, RENAME to match the persona
    # rather than skip. This makes the script reusable when a DB already
    # has IND-NSR-XXXX partners enrolled in programs (we can't delete
    # them without orphaning memberships, but we can rebrand them).
    existing = RegId.search([("value", "=", uin), ("id_type_id", "=", uin_code.id)], limit=1)
    persona_values = {
        "name": f"{given} {surname}",
        "given_name": given,
        "family_name": surname,
        "is_registrant": True,
        "is_group": False,
        "birthdate": "1990-01-01",
    }
    if existing:
        partner = existing.partner_id
        before = partner.name
        partner.write(persona_values)
        if before != partner.name:
            print(f"  ↻  {uin} partner.id={partner.id}  renamed: {before!r} -> {partner.name!r}")
        else:
            print(f"  ↻  {uin} partner.id={partner.id}  already named {partner.name!r}")
    else:
        partner = Partner.create(persona_values)
        RegId.create(
            {
                "partner_id": partner.id,
                "id_type_id": uin_code.id,
                "value": uin,
            }
        )
        print(f"  ✓  Created {given} {surname} (UIN={uin}, partner.id={partner.id})")
    demo_partners |= partner

    # DR-side only: ensure an approved disability assessment exists
    # for the personas flagged has_dr_assessment.
    if on_dr_side and has_dr_assessment:
        Assessment = env["spp.disability.assessment"]
        existing_asmt = Assessment.search(
            [("registrant_id", "=", partner.id), ("approval_state", "=", "approved")],
            limit=1,
        )
        if existing_asmt:
            print(f"     - approved assessment already exists (id={existing_asmt.id})")
        else:
            asmt = Assessment.create(
                {
                    "registrant_id": partner.id,
                    "assessment_date": fields.Date.today(),
                    # Force has_disability=True by setting one WG domain to severe.
                    # _compute_disability_indicator sets has_disability when any
                    # WG_* field is 'a_lot' or 'cannot'.
                    "wg_walking": "a_lot",
                    "review_category": "mip",  # 3-year review cadence
                }
            )
            # Bypass the approval workflow — direct write for demo seed only.
            asmt.write({"approval_state": "approved"})
            # Touch the related partner so has_disability propagates immediately.
            partner.invalidate_recordset(["current_disability_assessment_id", "has_disability"])
            print(
                f"     ✓ Created approved assessment (id={asmt.id}, "
                f"partner.has_disability now {partner.has_disability})"
            )

# SP-side only: add every demo partner as a draft membership of the
# program with record ID = 1, so Edwin can demo Enroll Eligible directly
# without first walking through the change-request flow to add members
# (his colleague demos that part on a separate instance).
# Memberships start in state='draft'; eligibility evaluation flips them
# to 'enrolled' or 'not_eligible' based on the CEL rule.
if not on_dr_side:
    program = env["spp.program"].browse(DEMO_PROGRAM_ID).exists()
    if not program:
        print("\n  ⚠  spp.program id=1 not found on SP — skipping bulk-enroll step.")
        print("     Create the program first (or change DEMO_PROGRAM_ID at the top of the script).")
    else:
        Membership = env["spp.program.membership"]
        added = 0
        already = 0
        for partner in demo_partners:
            existing_mem = Membership.search(
                [("partner_id", "=", partner.id), ("program_id", "=", program.id)],
                limit=1,
            )
            if existing_mem:
                already += 1
                continue
            Membership.create(
                {
                    "partner_id": partner.id,
                    "program_id": program.id,
                    "state": "draft",
                }
            )
            added += 1
        print(
            f"\n  ✓  Program '{program.name}' (id={program.id}): "
            f"{added} new memberships added, {already} already members "
            f"({len(demo_partners)} demo partners total)."
        )

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
print(
    "Next: run this same script against the OTHER side."
    if on_dr_side
    else "Next: run this same script against the DR (openspp_dr database)."
)
print("\nCLEANUP after the demo:")
print("  Delete the 4 partners via UI, or:")
print("  >>> uin_code = env.ref('spp_vocabulary.vocab_id_type')")
print("  >>> RegId = env['spp.registry.id']")
print("  >>> uins = [f'IND-NSR-{n:04d}' for n in range(1, 16)]")
print("  >>> partners = RegId.search([('value', 'in', uins)]).mapped('partner_id')")
print("  >>> partners.unlink()")
print("  >>> env.cr.commit()")
