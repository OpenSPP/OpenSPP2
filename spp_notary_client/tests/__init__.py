# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

try:
    import odoo  # noqa: F401
except ImportError:
    pass
else:
    from . import test_odoo_client
