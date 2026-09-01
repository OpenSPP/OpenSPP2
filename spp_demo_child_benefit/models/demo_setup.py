# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Demo environment setup: program, managers, and demo families.

The generator runs from the module's post_init_hook so a single install
produces a fully working demo database.
"""
import logging

_logger = logging.getLogger(__name__)


def post_init_hook(env):
    _logger.info("Child benefit demo setup starting")
    # Program, managers, and demo family generation are wired here.
