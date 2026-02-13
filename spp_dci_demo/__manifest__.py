# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
{
    "name": "OpenSPP DCI Demo",
    "version": "19.0.1.0.0",
    "category": "OpenSPP",
    "license": "LGPL-3",
    "website": "https://openspp.org",
    "author": "OpenSPP.org",
    "depends": [
        "spp_mis_demo_v2",
        "spp_dci_client",
        "spp_change_request_v2",
        "spp_programs",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/vocabulary_data.xml",
        "data/dci_data_source.xml",
        "data/system_parameters.xml",
        "data/demo_household.xml",
        "views/cr_detail_add_member_view.xml",
        "views/change_request_view.xml",
    ],
    "demo": [],
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": False,
    "auto_install": False,
    "summary": "DCI Demo: Birth Verification for Child Benefit Enrollment",
    "description": """
DCI Demo Module
===============

This module demonstrates DCI (Data Convergence Initiative) integration
for birth verification in the context of adding a child to a household.

Demo Story:
-----------
A parent comes to a service point to add their newborn to their household.
They have the Birth Registration Number (BRN) from OpenCRVS. The social worker:

1. Creates an "Add Child" change request on the household
2. Enters child details (name, DOB, gender) + BRN on the detail form
3. Clicks "Verify Birth" -> DCI query to OpenCRVS -> birth verified
4. Clicks "Submit" -> CR auto-approved if verification matched
5. Child added to household with verified BRN identity document
""",
}
