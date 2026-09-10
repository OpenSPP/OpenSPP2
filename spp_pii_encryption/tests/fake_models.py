# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Throwaway models for the migration-wizard tests.

Imported ONLY from inside a test's setUpClass (after
FakeModelLoader.backup_registry) — importing this module registers the
classes in MetaModel's module-to-models map, so a module-level import
would leak them into real registry reloads.
"""

from odoo import fields, models


class EncryptionTestRecord(models.Model):
    """Concrete consumer of the encrypted-field mixin (none exists in the
    real stack yet — the encryption core is a provider layer)."""

    _name = "spp.encryption.test.record"
    _description = "Encryption Migration Test Record"
    _inherit = ["spp.encrypted.field.mixin"]

    name = fields.Char()
    secret = fields.Char()
    secret_index = fields.Char(index=True)

    def _get_encrypted_fields(self):
        return ["secret"]
