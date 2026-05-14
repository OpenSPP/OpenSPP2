# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    registry_search_mode = fields.Selection(
        selection=[
            ("unified", "Unified Search (search across all fields)"),
            ("targeted", "Targeted Search (search a specific field)"),
        ],
        string="Registry Search Mode",
        default="unified",
        config_parameter="spp_registry_search.search_mode",
        help="'Unified Search' searches name, ID number, phone, and email simultaneously. "
        "Convenient but slower on very large datasets. "
        "'Targeted Search' requires users to select which field to search — faster on large datasets.",
    )

    registry_search_target_field = fields.Selection(
        selection=[
            ("name", "Name"),
            ("id_number", "ID Number"),
            ("phone", "Phone Number"),
            ("email", "Email"),
        ],
        string="Default Search Field",
        default="name",
        config_parameter="spp_registry_search.target_field",
        help="When search mode is 'Targeted Search', this is the default field "
        "users will search against. Users can change this in the search portal.",
    )

    registry_search_result_limit = fields.Integer(
        string="Maximum Search Results",
        default=50,
        config_parameter="spp_registry_search.result_limit",
        help="Maximum number of results returned per search. Lower values improve performance. Range: 10-200.",
    )

    registry_search_min_chars = fields.Integer(
        string="Minimum Search Characters",
        default=3,
        config_parameter="spp_registry_search.min_chars",
        help="Minimum number of characters required before a search is triggered. "
        "Higher values reduce unnecessary queries. Range: 1-10.",
    )
