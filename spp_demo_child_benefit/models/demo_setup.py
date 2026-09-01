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

from odoo import Command, fields

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


def post_init_hook(env):
    _logger.info("Child benefit demo setup starting")
    if env["spp.program"].search_count([("name", "=", PROGRAM_NAME)]):
        _logger.info("Demo program already present; skipping setup")
        return
    env = env(context=dict(env.context, tracking_disable=True))
    program = _create_program(env)
    families = _create_families(env)
    _enroll_and_open_cycle(env, program)
    _create_grievances(env, families)
    _logger.info("Child benefit demo setup complete")


def _create_program(env):
    journal = env["account.journal"].create({"name": f"{PROGRAM_NAME} Journal", "type": "bank", "code": "CBP"})
    program = env["spp.program"].create({"name": PROGRAM_NAME, "target_type": "individual", "journal_id": journal.id})

    # Default managers for the kinds we keep stock (eligibility, cycle, program, ...)
    from odoo.addons.spp_programs.models import constants  # noqa: PLC0415

    for field, mapping in constants.MANAGER_MODELS.items():
        if field in ("entitlement_manager_ids", "payment_manager_ids") or program[field]:
            continue
        for mgr_obj, def_mgr_obj in mapping.items():
            concrete = env[def_mgr_obj].create({"program_id": program.id})
            container = env[mgr_obj].create(
                {"program_id": program.id, "manager_ref_id": f"{def_mgr_obj},{concrete.id}"}
            )
            program.write({field: [Command.link(container.id)]})

    # Eligibility: readable CEL policy with the birth-order threshold
    for container in program.eligibility_manager_ids:
        concrete = container.manager_ref_id
        if concrete and "cel_expression" in concrete._fields:
            concrete.write({"eligibility_mode": "cel", "cel_expression": ELIGIBILITY_EXPRESSION})

    # Cycle manager: monthly recurrence
    for container in program.cycle_manager_ids:
        concrete = container.manager_ref_id
        if concrete and "rrule_type" in concrete._fields:
            concrete.write({"rrule_type": "monthly"})

    # Scheduled entitlement manager
    ent_mgr = env["spp.program.entitlement.manager.schedule"].create(
        {"name": "Scheduled Cash Entitlement", "program_id": program.id}
    )
    ent_container = env["spp.program.entitlement.manager"].create(
        {"program_id": program.id, "manager_ref_id": f"spp.program.entitlement.manager.schedule,{ent_mgr.id}"}
    )
    program.entitlement_manager_ids = [Command.link(ent_container.id)]

    # Bank-file payment manager
    pay_mgr = env["spp.program.payment.manager.csv"].create(
        {"name": "Bank File (CSV)", "program_id": program.id, "create_batch": True}
    )
    pay_container = env["spp.program.payment.manager"].create(
        {"program_id": program.id, "manager_ref_id": f"spp.program.payment.manager.csv,{pay_mgr.id}"}
    )
    program.payment_manager_ids = [Command.link(pay_container.id)]

    # Fund so entitlement approval passes the balance check
    env["spp.program.fund"].create({"program_id": program.id, "amount": 10_000_000.0, "state": "posted"})
    return program


def _create_families(env):
    Vocab = env["spp.vocabulary.code"]
    fam_type = Vocab.get_code("urn:openspp:vocab:group-type", "family")
    role_head = Vocab.get_code("urn:openspp:vocab:group-membership-type", "head")
    role_child = env.ref("spp_child_benefit.code_membership_type_child")
    role_mother = env.ref("spp_child_benefit.code_membership_type_mother")
    role_father = env.ref("spp_child_benefit.code_membership_type_father")
    banks = [
        env.ref("spp_demo_child_benefit.bank_national"),
        env.ref("spp_demo_child_benefit.bank_rural"),
        env.ref("spp_demo_child_benefit.bank_community"),
    ]
    villages = env["spp.area"].search([("code", "like", "%-%-%")])

    Partner = env["res.partner"]
    Membership = env["spp.group.membership"]
    today = fields.Date.today()
    families = []
    for index, blueprint in enumerate(_family_blueprints(today)):
        area = villages[index % len(villages)] if villages else env["spp.area"]
        mother = Partner.create(
            {
                "name": blueprint["mother"],
                "is_registrant": True,
                "is_group": False,
                "birthdate": date(1990 + index % 6, 3 + index % 9, 5 + index),
                "area_id": area.id if area else False,
            }
        )
        env["res.partner.bank"].create(
            {
                "partner_id": mother.id,
                "acc_number": f"10{index:02d}00{100000 + index * 7919}",
                "bank_id": banks[index % len(banks)].id,
            }
        )
        father = Partner.create(
            {
                "name": blueprint["father"],
                "is_registrant": True,
                "is_group": False,
                "birthdate": date(1988 + index % 6, 1 + index % 11, 3 + index),
                "area_id": area.id if area else False,
            }
        )
        family = Partner.create(
            {
                "name": blueprint["name"],
                "is_registrant": True,
                "is_group": True,
                "group_type_id": fam_type.id,
                "area_id": area.id if area else False,
            }
        )
        Membership.create(
            {
                "group": family.id,
                "individual": mother.id,
                "membership_type_ids": [Command.set([role_head.id, role_mother.id])],
            }
        )
        Membership.create(
            {
                "group": family.id,
                "individual": father.id,
                "membership_type_ids": [Command.set([role_father.id])],
            }
        )
        for child_name, birthdate, extra in blueprint["children"]:
            vals = {
                "name": child_name,
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
                    "membership_type_ids": [Command.set([role_child.id])],
                }
            )
        families.append(family)
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
    cycle = env["spp.cycle"].create(
        {
            "name": f"{today.strftime('%B %Y')} Cycle",
            "program_id": program.id,
            "start_date": month_start,
            "end_date": month_start + relativedelta(months=1, days=-1),
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
