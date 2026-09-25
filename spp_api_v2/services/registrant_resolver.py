# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Resolve an external identifier to exactly one registrant."""

from odoo.exceptions import ValidationError


class AmbiguousIdentifierError(Exception):
    """The identifier is live on more than one registrant."""

    def __init__(self, partners):
        super().__init__("Identifier matches more than one registrant")
        self.partners = partners


class IdentifierInUseError(ValidationError):
    """The identifier is already live on another registrant."""


def resolve_registrant(env, system_uri, value, is_group=None):
    raise NotImplementedError
