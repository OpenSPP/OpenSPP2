# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""
OpenSPP Access Management Compliance Framework.

This package provides tools for:
- Declaring expected access control configurations (compliance.yaml)
- Validating actual configurations against specifications
- Generating automated tests from compliance specs
- Producing compliance reports

Usage:
    # Check compliance for all modules
    python -m scripts.compliance.checker --all

    # Generate tests from compliance spec
    python -m scripts.compliance.test_generator spp_registry_base

    # Generate compliance report
    python -m scripts.compliance.checker --report --format markdown
"""

from .schema import (
    ComplianceSpec,
    ModelAccess,
    RecordRule,
    MenuAccess,
    FieldRestriction,
    ActionRestriction,
    GroupDefinition,
)

__all__ = [
    "ComplianceSpec",
    "ModelAccess",
    "RecordRule",
    "MenuAccess",
    "FieldRestriction",
    "ActionRestriction",
    "GroupDefinition",
]
