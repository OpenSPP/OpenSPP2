# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Demo environment setup.

Runs from the module's post_init_hook so that a single install produces a
fully working demo database: the Child Benefit Programme configured with the
scheduled entitlement and bank-file payment managers, a CEL eligibility rule,
a current-month cycle, funds, and demo families covering every eligibility
branch of the birth-order rules.
"""

import logging
from datetime import date

from dateutil.relativedelta import relativedelta

from odoo import Command, _, fields

_logger = logging.getLogger(__name__)

PROGRAM_NAME = "Child Benefit Programme"
ELIGIBILITY_EXPRESSION = "r.birth_order >= 3 && age_years(r.birthdate) < 3"


# Family blueprints: (family, mother, father, [(child, birthdate offset kwargs, extra vals)])
# Every eligibility branch of the birth-order rules is represented.
def _family_blueprints(today):
    def bd(**kwargs):
        return today - relativedelta(**kwargs)

    return [
        {
            "name": "Demo Family One",
            "story": "Third child born recently: eligible, ranks 1/2/3.",
            "mother": "Mother One",
            "father": "Father One",
            "children": [
                ("Child One-A", bd(years=6, months=2), {}),
                ("Child One-B", bd(years=3, months=6), {}),
                ("Child One-C", bd(months=2, day=3), {}),
            ],
        },
        {
            "name": "Demo Family Two",
            "story": "Third child close to the age limit: schedule nearly exhausted.",
            "mother": "Mother Two",
            "father": "Father Two",
            "children": [
                ("Child Two-A", bd(years=8), {}),
                ("Child Two-B", bd(years=5), {}),
                ("Child Two-C", bd(months=34, day=10), {}),
            ],
        },
        {
            "name": "Demo Family Three",
            "story": "Only two children: not eligible.",
            "mother": "Mother Three",
            "father": "Father Three",
            "children": [
                ("Child Three-A", bd(years=4), {}),
                ("Child Three-B", bd(months=3, day=20), {}),
            ],
        },
        {
            "name": "Demo Family Four",
            "story": "Twins as 2nd and 3rd (sequence recorded): only the 3rd-ranked twin is eligible.",
            "mother": "Mother Four",
            "father": "Father Four",
            "children": [
                ("Child Four-A", bd(years=5), {}),
                ("Child Four-Twin1", bd(months=4, day=8), {"birth_sequence": 1}),
                ("Child Four-Twin2", bd(months=4, day=8), {"birth_sequence": 2}),
            ],
        },
        {
            "name": "Demo Family Five",
            "story": "Adopted middle child is excluded: natural 3rd child still ranks 3rd.",
            "mother": "Mother Five",
            "father": "Father Five",
            "children": [
                ("Child Five-A", bd(years=7), {}),
                ("Child Five-B", bd(years=4), {"citizen_by": "adopted"}),
                ("Child Five-C", bd(years=2, months=6), {}),
                ("Child Five-D", bd(months=1, day=18), {}),
            ],
        },
        {
            "name": "Demo Family Six",
            "story": "Twins without a recorded birth sequence: officer determination queue.",
            "mother": "Mother Six",
            "father": "Father Six",
            "children": [
                ("Child Six-A", bd(years=3, months=2), {}),
                ("Child Six-Twin1", bd(months=2, day=12), {}),
                ("Child Six-Twin2", bd(months=2, day=12), {}),
            ],
        },
        {
            "name": "Demo Family Seven",
            "story": "Newborn not yet registered (no date of birth): held, no rank.",
            "mother": "Mother Seven",
            "father": "Father Seven",
            "children": [
                ("Child Seven-A", bd(years=6), {}),
                ("Child Seven-B", bd(years=3), {}),
                ("Child Seven-C", None, {}),
            ],
        },
        {
            "name": "Demo Family Eight",
            "story": "Fourth child born last month: eligible at rank 4.",
            "mother": "Mother Eight",
            "father": "Father Eight",
            "children": [
                ("Child Eight-A", bd(years=9), {}),
                ("Child Eight-B", bd(years=7), {}),
                ("Child Eight-C", bd(years=4), {}),
                ("Child Eight-D", bd(months=1, day=22), {}),
            ],
        },
    ]


def create_demo_environment(env):
    """Build the whole demo environment. Idempotent: returns False when the
    demo programme already exists, so it is safe to call from a button.

    If the programme exists but is missing its journal (e.g. a partially
    completed earlier run), the journal is repaired before returning using the
    wizard's standard journal helper."""
    existing = env["spp.program"].search([("name", "=", PROGRAM_NAME)], limit=1)
    if existing:
        if not existing.journal_id:
            _ensure_chart_of_accounts(env)
            wizard = env["spp.program.create.wizard"].new({"currency_id": env.company.currency_id.id})
            existing.journal_id = wizard.create_journal(f"{PROGRAM_NAME} Journal", env.company.currency_id.id)
            _logger.info("Repaired missing journal on existing demo programme %s", existing.id)
        return False
    env = env(context=dict(env.context, tracking_disable=True))
    program = _create_program(env)
    families = _create_families(env)
    _enroll_and_open_cycle(env, program)
    _create_grievances(env, families)
    _create_portal_users(env)
    _logger.info("Child benefit demo setup complete")
    return True


def post_init_hook(env):
    _logger.info("Child benefit demo setup starting")
    create_demo_environment(env)


# Portal logins to demonstrate the monitoring portal from a family head's
# view: a family with one qualified child, one with two, one with three, and
# one with none (to show the empty state). Portal access is granted to the
# individual head/mother, never to the family group.
PORTAL_LOGINS = [
    ("parent", "Demo Family One"),  # 1 qualified child
    ("gurung", "Gurung Family"),  # 2 qualified children
    ("dahal", "Dahal Family"),  # 3 qualified children
    ("no-benefit", "Demo Family Three"),  # 0 qualified children (empty state)
]
PORTAL_PASSWORD = "Cbp-Parent-Demo-2026!"


def _family_head(env, family_name):
    """The head/mother individual of a family, who receives portal access."""
    family = env["res.partner"].search([("name", "=", family_name), ("is_group", "=", True)], limit=1)
    if not family:
        return env["res.partner"]
    Vocab = env["spp.vocabulary.code"]
    for role_ns in (
        ("mother", env.ref("spp_child_benefit.code_membership_type_mother")),
        ("head", Vocab.get_code("urn:openspp:vocab:group-membership-type", "head")),
    ):
        _code, role = role_ns
        ms = family.group_membership_ids.filtered(
            lambda m, r=role: not m.is_ended and r and r.id in m.membership_type_ids.ids
        )
        if ms:
            return ms[0].individual
    return env["res.partner"]


def _create_portal_users(env):
    """Grant portal access to the head of each demonstration family in
    PORTAL_LOGINS. Idempotent."""
    Users = env["res.users"]
    portal_group = env.ref("base.group_portal")
    for login, family_name in PORTAL_LOGINS:
        if Users.search_count([("login", "=", login)]):
            continue
        head = _family_head(env, family_name)
        if not head:
            _logger.info("Portal login '%s' skipped: no head for %s", login, family_name)
            continue
        Users.create(
            {
                "name": head.name,
                "login": login,
                "password": PORTAL_PASSWORD,
                "partner_id": head.id,
                "group_ids": [Command.set([portal_group.id])],
            }
        )
        _logger.info("Created portal user '%s' for %s (%s)", login, head.name, family_name)


def _ensure_chart_of_accounts(env):
    """A bank journal created before the company has a chart of accounts spawns
    transient accounting records that Odoo garbage-collects at end of install,
    taking the journal with it. Ensure a chart of accounts exists first."""
    company = env.company
    if not company.chart_template:
        try:
            env["account.chart.template"].try_loading("generic_coa", company=company, install_demo=False)
        except Exception as err:  # noqa: BLE001 - best effort; the wizard guards journal creation
            _logger.warning("Could not load a chart of accounts for the demo: %s", err)


def _create_program(env):
    """Create the demo programme exactly the way a user would: through the
    standard program-creation wizard, then add the Bank File payment method
    through the standard Manager Setup dialog. No bespoke program-building.

    The wizard's create_journal runs here; a chart of accounts must exist
    first or the journal's transient accounting records are garbage-collected
    at end of install (see _ensure_chart_of_accounts)."""
    _ensure_chart_of_accounts(env)

    wizard = env["spp.program.create.wizard"].create(
        {
            "name": PROGRAM_NAME,
            "currency_id": env.company.currency_id.id,
            "target_type": "individual",
            "rrule_type": "monthly",
            # Auto-approve entitlements so the demo flows straight to payment
            # without approving each entitlement one by one.
            "auto_approve_entitlements": True,
            "entitlement_type": "schedule",
            "schedule_monthly_amount": 10000.0,
            "schedule_age_limit_months": 36,
            "schedule_cutoff_day": 15,
            "eligibility_cel_expression": ELIGIBILITY_EXPRESSION,
        }
    )
    wizard.create_program()
    program = env["spp.program"].search([("name", "=", PROGRAM_NAME)], limit=1)

    # Add the Bank File (CSV) payment method the standard way.
    _add_payment_manager(env, program, "spp.program.payment.manager.csv")

    # Fund so entitlement approval passes the balance check.
    env["spp.program.fund"].create({"program_id": program.id, "amount": 10_000_000.0, "state": "posted"})
    return program


def _add_payment_manager(env, program, method_model):
    """Attach a payment method through the standard Manager Setup dialog."""
    if program.payment_manager_ids:
        return
    setup = env["spp.manager.setup.wizard"].create(
        {
            "program_id": program.id,
            "category": "payment",
            "method": method_model,
            "name": _("Bank File (CSV)"),
        }
    )
    setup.action_create_manager()


def _split_person_name(full_name):
    """Given/family name parts from a display name: first token is the given
    name, the remainder the family name. The explicit display name is always
    passed alongside, so composition never overrides it."""
    parts = full_name.split(None, 1)
    return {
        "name": full_name,
        "given_name": parts[0],
        "family_name": parts[1] if len(parts) > 1 else "",
    }


# Extra, non-curated families to give the demo a fuller population. Each entry
# is the number of *qualified* children that family should have (3rd-or-higher
# birth order and under the age limit); the family also gets two older,
# non-qualified siblings so the ranking is realistic. The counts are fixed so
# the totals stay deterministic and testable; names are drawn from the pools
# below. Sum = qualified children added on top of the curated 5.
EXTRA_FAMILY_PROFILES = [1, 2, 1, 3, 2, 1, 2, 3, 1, 2, 1, 2, 3, 1, 2, 1, 2]
_EXTRA_GIVEN_NAMES = [
    "Aria",
    "Beni",
    "Cara",
    "Deva",
    "Elan",
    "Fira",
    "Gani",
    "Hira",
    "Ivo",
    "Jaya",
    "Kiran",
    "Lira",
    "Mira",
    "Nima",
    "Oni",
    "Pema",
    "Rina",
    "Sami",
    "Tara",
    "Uma",
    "Vira",
    "Wina",
    "Yara",
    "Zani",
    "Anil",
    "Bina",
    "Chandra",
    "Dipa",
    "Esha",
    "Gita",
]
_EXTRA_FAMILY_NAMES = [
    "Adhikari",
    "Baniya",
    "Chettri",
    "Dahal",
    "Gurung",
    "Humagai",
    "Iyer",
    "Joshi",
    "Karki",
    "Lama",
    "Magar",
    "Neupane",
    "Oli",
    "Pradhan",
    "Rai",
    "Sharma",
    "Thapa",
    "Uprety",
    "Verma",
    "Wagle",
]


def expected_qualified_count():
    """Qualified beneficiaries the generator produces: curated 5 + extras."""
    return 5 + sum(EXTRA_FAMILY_PROFILES)


def _family_refs(env):
    Vocab = env["spp.vocabulary.code"]
    return {
        "fam_type": Vocab.get_code("urn:openspp:vocab:group-type", "family"),
        "role_head": Vocab.get_code("urn:openspp:vocab:group-membership-type", "head"),
        "role_child": env.ref("spp_child_benefit.code_membership_type_child"),
        "role_mother": env.ref("spp_child_benefit.code_membership_type_mother"),
        "role_father": env.ref("spp_child_benefit.code_membership_type_father"),
        "banks": [
            env.ref("spp_demo_child_benefit.bank_national"),
            env.ref("spp_demo_child_benefit.bank_rural"),
            env.ref("spp_demo_child_benefit.bank_community"),
        ],
        "villages": env["spp.area"].search([("code", "like", "%-%-%")]),
    }


def _create_one_family(env, refs, index, name, mother_name, father_name, children):
    """Create a single family: mother (head + payee, with a bank account),
    father, and the given children. `children` is a list of
    (full_name, birthdate, extra_vals)."""
    Partner = env["res.partner"]
    Membership = env["spp.group.membership"]
    villages = refs["villages"]
    banks = refs["banks"]
    area = villages[index % len(villages)] if villages else env["spp.area"]

    mother = Partner.create(
        {
            **_split_person_name(mother_name),
            "is_registrant": True,
            "is_group": False,
            "birthdate": date(1990 + index % 6, 3 + index % 9, 5 + index % 23),
            "area_id": area.id if area else False,
        }
    )
    env["res.partner.bank"].create(
        {
            "partner_id": mother.id,
            "acc_number": f"10{index:03d}{100000 + index * 7919}",
            "bank_id": banks[index % len(banks)].id,
        }
    )
    father = Partner.create(
        {
            **_split_person_name(father_name),
            "is_registrant": True,
            "is_group": False,
            "birthdate": date(1988 + index % 6, 1 + index % 11, 3 + index % 25),
            "area_id": area.id if area else False,
        }
    )
    family = Partner.create(
        {
            "name": name,
            "is_registrant": True,
            "is_group": True,
            "group_type_id": refs["fam_type"].id,
            "area_id": area.id if area else False,
        }
    )
    Membership.create(
        {
            "group": family.id,
            "individual": mother.id,
            "membership_type_ids": [Command.set([refs["role_head"].id, refs["role_mother"].id])],
        }
    )
    Membership.create(
        {
            "group": family.id,
            "individual": father.id,
            "membership_type_ids": [Command.set([refs["role_father"].id])],
        }
    )
    for child_name, birthdate, extra in children:
        vals = {
            **_split_person_name(child_name),
            "is_registrant": True,
            "is_group": False,
            "birthdate": birthdate,
            "area_id": area.id if area else False,
        }
        vals.update(extra)
        child = Partner.create(vals)
        Membership.create(
            {
                "group": family.id,
                "individual": child.id,
                "membership_type_ids": [Command.set([refs["role_child"].id])],
            }
        )
    return family


def _extra_family_children(today, family_index, qualified_count):
    """Two older, non-qualified siblings plus `qualified_count` recent children
    (3rd birth order and up, each under 36 months) so the family has exactly
    `qualified_count` qualified beneficiaries."""
    fam_name = _EXTRA_FAMILY_NAMES[family_index % len(_EXTRA_FAMILY_NAMES)]

    def given(offset):
        return _EXTRA_GIVEN_NAMES[(family_index * 3 + offset) % len(_EXTRA_GIVEN_NAMES)]

    children = [
        (f"{given(0)} {fam_name}", today - relativedelta(years=6, months=family_index % 5), {}),
        (f"{given(1)} {fam_name}", today - relativedelta(years=4, months=family_index % 7), {}),
    ]
    # Recent children spread under 36 months, with varied days for proration.
    recent_offsets = [30, 20, 8][:qualified_count]
    for i, months_ago in enumerate(recent_offsets):
        day = 3 + (family_index + i * 9) % 24  # vary day for entry/exit proration
        birthdate = (today - relativedelta(months=months_ago)).replace(day=day)
        children.append((f"{given(2 + i)} {fam_name}", birthdate, {}))
    return children


def _create_families(env):
    refs = _family_refs(env)
    today = fields.Date.today()
    families = []
    for index, blueprint in enumerate(_family_blueprints(today)):
        families.append(
            _create_one_family(
                env, refs, index, blueprint["name"], blueprint["mother"], blueprint["father"], blueprint["children"]
            )
        )

    # Extra families for a fuller demo population, several with more than one
    # qualified child.
    for offset, qualified_count in enumerate(EXTRA_FAMILY_PROFILES):
        index = len(families)
        fam_name = _EXTRA_FAMILY_NAMES[offset % len(_EXTRA_FAMILY_NAMES)]
        mother_name = f"{_EXTRA_GIVEN_NAMES[offset % len(_EXTRA_GIVEN_NAMES)]} {fam_name}"
        father_name = f"{_EXTRA_GIVEN_NAMES[(offset + 11) % len(_EXTRA_GIVEN_NAMES)]} {fam_name}"
        children = _extra_family_children(today, offset, qualified_count)
        families.append(_create_one_family(env, refs, index, f"{fam_name} Family", mother_name, father_name, children))
    _logger.info("Created %s demo families", len(families))
    return families


def _enroll_and_open_cycle(env, program):
    """Enroll eligible children via the program's CEL rule and open the
    current-month cycle with them."""
    eligible_ids = env["spp.cel.service"].get_matching_ids(ELIGIBILITY_EXPRESSION, "registry_individuals")
    children = env["res.partner"].browse(eligible_ids)
    for child in children:
        env["spp.program.membership"].create({"partner_id": child.id, "program_id": program.id, "state": "enrolled"})
    today = fields.Date.today()
    month_start = date(today.year, today.month, 1)
    # The cycle start date cannot precede today, so start no earlier than today
    # (the current benefit month is still matched: materialization floors the
    # lower bound to the first of the cycle's start month).
    cycle = env["spp.cycle"].create(
        {
            "name": f"{today.strftime('%B %Y')} Cycle",
            "program_id": program.id,
            "start_date": max(month_start, today),
            "end_date": month_start + relativedelta(months=1, days=-1),
            # The cycle carries its own auto-approve flag (the manager's flag
            # only seeds cycles created through its New Cycle flow); set it here
            # so the demo flows straight to payment without manual approval.
            "auto_approve_entitlements": True,
        }
    )
    for child in children:
        env["spp.cycle.membership"].create({"partner_id": child.id, "cycle_id": cycle.id, "state": "enrolled"})
    _logger.info("Enrolled %s eligible children; cycle %s ready", len(children), cycle.name)


def _create_grievances(env, families):
    category = env.ref("spp_demo_child_benefit.grm_category_payment")
    channel = env.ref("spp_grm.grm_ticket_channel_web", raise_if_not_found=False)
    Ticket = env["spp.grm.ticket"]
    mothers = families[0].group_membership_ids.mapped("individual").filtered(lambda p: p.name.startswith("Mother"))
    if not mothers:
        return
    vals = {
        "name": "Payment not received for last month",
        "description": "The benefit payment for the previous month has not arrived in my account.",
        "category_id": category.id,
        "partner_id": mothers[0].id,
    }
    if channel:
        vals["channel_id"] = channel.id
    Ticket.create(vals)
    _logger.info("Created demo grievance ticket")
