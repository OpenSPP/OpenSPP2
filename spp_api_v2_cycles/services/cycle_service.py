# Part of OpenSPP. See LICENSE file for full copyright and licensing details.
"""Service for Cycle resource operations"""

import logging
from typing import Any

from odoo.api import Environment

_logger = logging.getLogger(__name__)


class CycleService:
    """Service for Cycle resource CRUD and mapping"""

    def __init__(self, env: Environment):
        self.env = env

    def find_by_identifier(self, identifier: str):
        """
        Lookup cycle by identifier (name).

        Args:
            identifier: Cycle name

        Returns:
            spp.cycle record or empty recordset
        """
        return (
            self.env["spp.cycle"]  # nosemgrep: odoo-sudo-without-context
            .sudo()
            .search(
                [("name", "=", identifier)],
                limit=1,
            )
        )

    def search(self, params: dict) -> tuple[Any, int]:
        """
        Search cycles with parameters.

        Args:
            params: Search parameters dict

        Returns:
            Tuple of (recordset, total_count)
        """
        domain = []

        # Program filter
        if params.get("program"):
            domain.append(("program_id.name", "ilike", params["program"]))

        # State filter
        if params.get("state"):
            domain.append(("state", "=", params["state"]))

        # Start date filter
        if params.get("startDate"):
            start_date = params["startDate"]
            if start_date.startswith("ge"):
                domain.append(("start_date", ">=", start_date[2:]))
            elif start_date.startswith("le"):
                domain.append(("start_date", "<=", start_date[2:]))
            else:
                domain.append(("start_date", ">=", start_date))

        # End date filter
        if params.get("endDate"):
            end_date = params["endDate"]
            if end_date.startswith("ge"):
                domain.append(("end_date", ">=", end_date[2:]))
            elif end_date.startswith("le"):
                domain.append(("end_date", "<=", end_date[2:]))
            else:
                domain.append(("end_date", "<=", end_date))

        # Last updated filter
        if params.get("_lastUpdated"):
            last_updated = params["_lastUpdated"]
            if last_updated.startswith("ge"):
                domain.append(("write_date", ">=", last_updated[2:]))
            elif last_updated.startswith("le"):
                domain.append(("write_date", "<=", last_updated[2:]))
            elif last_updated.startswith("gt"):
                domain.append(("write_date", ">", last_updated[2:]))
            elif last_updated.startswith("lt"):
                domain.append(("write_date", "<", last_updated[2:]))
            else:
                domain.append(("write_date", ">=", last_updated))

        total = self.env["spp.cycle"].sudo().search_count(domain)  # nosemgrep: odoo-sudo-without-context

        count = params.get("_count", 20)
        offset = params.get("_offset", 0)

        records = (
            self.env["spp.cycle"]  # nosemgrep: odoo-sudo-without-context
            .sudo()
            .search(
                domain,
                limit=count,
                offset=offset,
                order="sequence asc",
            )
        )

        return records, total

    def to_api_schema(self, cycle) -> dict[str, Any]:
        """
        Convert Odoo cycle to API schema.

        CRITICAL: NO database IDs exposed

        Args:
            cycle: spp.cycle record

        Returns:
            Dictionary matching Cycle schema
        """
        if not cycle:
            return {}

        result = {
            "type": "Cycle",
            "identifier": cycle.name,
            "name": cycle.name,
            "state": cycle.state,
        }

        # Sequence
        if cycle.sequence:
            result["sequence"] = cycle.sequence

        # Program reference
        if cycle.program_id:
            result["program"] = {
                "reference": f"Program/{cycle.program_id.name}",
                "display": cycle.program_id.name,
            }

        # Period
        if cycle.start_date or cycle.end_date:
            result["period"] = {}
            if cycle.start_date:
                result["period"]["start"] = cycle.start_date.isoformat()
            if cycle.end_date:
                result["period"]["end"] = cycle.end_date.isoformat()

        # Approval info
        if cycle.approved_date:
            result["approvedDate"] = cycle.approved_date.isoformat()
        if cycle.approved_by:
            result["approvedBy"] = cycle.approved_by.name

        # Statistics
        statistics = {}
        if hasattr(cycle, "members_count"):
            statistics["membersCount"] = cycle.members_count
        if hasattr(cycle, "entitlements_count"):
            statistics["entitlementsCount"] = cycle.entitlements_count
        if hasattr(cycle, "payments_count"):
            statistics["paymentsCount"] = cycle.payments_count
        if hasattr(cycle, "total_amount") and cycle.total_amount:
            statistics["totalAmount"] = cycle.total_amount
            if cycle.currency_id:
                statistics["currency"] = cycle.currency_id.name

        if statistics:
            result["statistics"] = statistics

        # Navigation
        if cycle.previous_cycle_id:
            result["previousCycle"] = {
                "reference": f"Cycle/{cycle.previous_cycle_id.name}",
                "display": cycle.previous_cycle_id.name,
            }
        if cycle.next_cycle_id:
            result["nextCycle"] = {
                "reference": f"Cycle/{cycle.next_cycle_id.name}",
                "display": cycle.next_cycle_id.name,
            }

        # Metadata
        if cycle.write_date:
            version_id = str(int(cycle.write_date.timestamp() * 1000000))
            result["meta"] = {
                "versionId": version_id,
                "lastUpdated": cycle.write_date.isoformat(),
            }

        return result
