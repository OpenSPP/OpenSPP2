# ============================================================================
# SPDCI DEMO — MEMBERSHIP + CACHE RESET.  DO NOT SHIP IN PRODUCTION.
# ============================================================================
#
# Resets the 15 demo registrants seeded by `setup_spdci_demo.py` back to a
# clean pre-evaluation state so the operator can demo Enroll Eligible
# multiple times during a presentation:
#
#   1. All memberships on program id=DEMO_PROGRAM_ID for the demo
#      partners get flipped from {enrolled, not_eligible, paused, exited}
#      back to state='draft'. The next Enroll Eligible click will
#      re-evaluate the CEL rule for each.
#
#   2. The DCI value cache for the demo partners is wiped. This forces
#      the next eligibility check to re-fetch live from OpenG2P SR and
#      OpenSPP-DR (instead of serving the 5-minute TTL'd cached values).
#      Useful when the demo audience should see the DCI round-trip in
#      the SP log.
#
# RUN ON SP ONLY:
#   docker compose exec openspp-dev odoo shell -d openspp --no-http \
#     < scripts/demo/reset_spdci_demo.py
#
# (DR side has no memberships and no DCI cache — nothing to reset there.)
# ============================================================================

import logging

_logger = logging.getLogger("reset_spdci_demo")

DEMO_PROGRAM_ID = 1
DEMO_UINS = [f"IND-NSR-{n:04d}" for n in range(1, 16)]
WIPE_DCI_CACHE = True  # Set False if you want to keep the cache warm

print("\n=== Resetting SPDCI demo memberships ===\n")

# Resolve the demo partner ids via their UIN reg_ids
RegId = env["spp.registry.id"]
reg_ids = RegId.search([("value", "in", DEMO_UINS)])
partner_ids = sorted(set(reg_ids.mapped("partner_id.id")))
if not partner_ids:
    raise RuntimeError("No demo partners found. Run scripts/demo/setup_spdci_demo.py first.")

print(f"  Demo partners: {len(partner_ids)} (ids={partner_ids})")

# ---- 1. Reset memberships on the demo program ------------------------------
Membership = env["spp.program.membership"]
program = env["spp.program"].browse(DEMO_PROGRAM_ID).exists()
if not program:
    raise RuntimeError(f"spp.program id={DEMO_PROGRAM_ID} not found")

mems = Membership.search([("program_id", "=", program.id), ("partner_id", "in", partner_ids)])
before_states = {m.id: m.state for m in mems}
mems.write({"state": "draft", "exit_date": False})

print(f"\n  Program: {program.name!r} (id={program.id})")
print(f"  Memberships reset: {len(mems)}")
for m in mems.sorted("partner_id"):
    print(f"    partner.id={m.partner_id.id:<4}  {m.partner_id.name:<32}  {before_states[m.id]!r} -> 'draft'")

# ---- 2. Wipe the DCI value cache for the demo partners ---------------------
if WIPE_DCI_CACHE:
    DataValue = env["spp.data.value"]
    cache_rows = DataValue.search(
        [
            ("subject_model", "=", "res.partner"),
            ("subject_id", "in", partner_ids),
            ("variable_name", "in", ["has_disability", "is_poor", "has_dependent_under_school_age"]),
        ]
    )
    n_cache = len(cache_rows)
    cache_rows.unlink()
    print(f"\n  DCI cache rows wiped: {n_cache}")
    print("  Next Enroll Eligible will fire live DCI queries against OpenG2P + OpenSPP-DR.")
else:
    print("\n  DCI cache untouched (set WIPE_DCI_CACHE=True at the top to also wipe).")

env.cr.commit()

print("\n=== Done. Click Enroll Eligible on the program to re-evaluate. ===")
print('Expected outcome with rule `has_disability == true && is_poor == "low"`:')
print("  4 ENROLLED  : Alex Rivera (0001), Morgan Cole (0004), Taylor Brooks (0010), Sam Hayes (0013)")
print("  11 not eligible")
