# Part of OpenSPP. See LICENSE file for full copyright and licensing details.

# OpenSPP release information - used by packaging scripts
#
# This file follows the same pattern as Odoo's release.py for compatibility
# with the build/package.py script.

RELEASE_LEVELS = [ALPHA, BETA, CANDIDATE, FINAL] = ["alpha", "beta", "candidate", "final"]
RELEASE_LEVELS_DISPLAY = {ALPHA: ALPHA, BETA: BETA, CANDIDATE: "rc", FINAL: ""}

# OpenSPP version info (major, minor, micro, release_level, serial)
# Based on Odoo 19.0 with OpenSPP modules version 1.3.0
version_info = (19, 0, 1, FINAL, 0, "")
version = (
    ".".join(str(s) for s in version_info[:2])
    + RELEASE_LEVELS_DISPLAY[version_info[3]]
    + str(version_info[4] or "")
    + version_info[5]
)
series = serie = "19.0"

# Product information
product_name = "OpenSPP"
description = "OpenSPP - Social Protection Platform"
long_desc = """OpenSPP is a comprehensive open-source platform designed for social protection
program management. Built on Odoo 19, it provides tools for beneficiary registry,
program management, entitlement processing, and more.
"""

# Classifiers for PyPI
classifiers = [
    "Development Status :: 4 - Beta",
    "License :: OSI Approved :: GNU Lesser General Public License v3 (LGPLv3)",
    "Programming Language :: Python",
]

# URLs
url = "https://openspp.org"
author = "OpenSPP.org"
author_email = "info@openspp.org"
license_name = "LGPL-3"

# Windows service name
nt_service_name = "openspp-server-" + series
