# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Shared services for aggregation engine."""

from .scope_builder import build_area_scope, build_cel_scope, build_explicit_scope

__all__ = [
    "build_area_scope",
    "build_cel_scope",
    "build_explicit_scope",
]
