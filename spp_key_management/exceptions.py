# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""
Key Management Exceptions.

Custom exceptions for key management operations to enable
robust error handling without relying on string matching.
"""

from odoo.exceptions import UserError


class MasterKeyNotConfiguredError(UserError):
    """Raised when the master encryption key is not configured.

    This exception indicates that spp_master_key is missing from
    odoo.conf, which is required for database-stored key encryption.
    """

    pass
