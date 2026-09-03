# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Family resolution shared by the portal controllers.

A portal user may act for themselves or for any live member of the family
groups they belong to. Membership liveness is tested against the clock, not
the stored ``is_ended`` flag, which only refreshes on write.
"""

from odoo import fields

GROUP_TYPE_NS = "urn:openspp:vocab:group-type"


def live_membership_domain():
    now = fields.Datetime.now()
    return ["|", ("ended_date", "=", False), ("ended_date", ">", now)]


def portal_family_members(env, partner):
    """Live members of the family groups ``partner`` belongs to, as
    {individual: family}, ``partner`` first. The partner is always included,
    even without a family."""
    Membership = env["spp.group.membership"].sudo()
    live = live_membership_domain()
    mine = Membership.search([("individual", "=", partner.id)] + live)
    families = mine.filtered(
        lambda m: m.group.group_type_id.namespace_uri == GROUP_TYPE_NS and m.group.group_type_id.code == "family"
    ).mapped("group")
    members = {partner: families[:1]}
    if families:
        for membership in Membership.search([("group", "in", families.ids)] + live, order="group, id"):
            members.setdefault(membership.individual, membership.group)
    return members


def resolve_family_member(raw, members, partner):
    """The posted member id resolved against ``members``; ``partner`` when
    nothing was posted. Returns None for anything else."""
    if raw in (None, ""):
        return partner
    try:
        member_id = int(raw)
    except (TypeError, ValueError):
        return None
    for member in members:
        if member.id == member_id:
            return member
    return None
