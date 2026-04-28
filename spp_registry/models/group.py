# Part of OpenSPP Registry. See LICENSE file for full copyright and licensing details.
import logging

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

# expression.expression() is needed for complex query building with joins;
# Domain.AND/OR only handles simple domain operations
from odoo.osv import expression  # noqa: PLC0415 - no alternative for expression.expression()
from odoo.tools import Query

_logger = logging.getLogger(__name__)


class SPPGroup(models.Model):
    """Group registrant model.

    This model consolidates:
    - Base group functionality (spp_registry_group)
    - Membership functionality (spp_registry_membership)
    """

    _inherit = "res.partner"

    # Canary field for triggering recomputation of dependent fields
    # Used by _recompute_parent_groups in individual.py to trigger group updates
    force_recompute_canary = fields.Boolean(
        compute="_compute_force_recompute_canary",
        store=True,
        help="Technical field to trigger group recomputation when members change",
    )

    @api.depends("group_membership_ids", "group_membership_ids.individual")
    def _compute_force_recompute_canary(self):
        """Dummy compute to trigger dependent field recomputation."""
        for record in self:
            record.force_recompute_canary = False

    # Group fields
    group_type_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Group Type",
        domain="[('namespace_uri', '=', 'urn:openspp:vocab:group-type')]",
    )
    is_partial_group = fields.Boolean("Partial Group")
    group_type_name = fields.Char(related="group_type_id.display", string="Group Type Name")

    # Membership fields
    group_membership_ids = fields.One2many(
        "spp.group.membership",
        "group",
        "Group Members",
    )

    # True when the group-membership-type vocabulary has at least one code.
    # Used by views to hide the "Group Role" column entirely when the
    # vocabulary is empty (otherwise the column shows blank tag cells with
    # nothing pickable).
    has_group_membership_type_codes = fields.Boolean(
        compute="_compute_has_group_membership_type_codes",
    )

    # True when the group-type vocabulary has at least one code. Used to
    # hide the Group Type form field when there's nothing to pick.
    has_group_type_codes = fields.Boolean(
        compute="_compute_has_group_type_codes",
    )

    def _compute_has_group_membership_type_codes(self):
        # sudo() so non-admin readers can still resolve the column-visibility
        # flag; we only return a boolean, no vocabulary content leaks.
        has_codes = bool(
            self.env["spp.vocabulary.code"]  # nosemgrep: odoo-sudo-without-context
            .sudo()
            .search_count(
                [("vocabulary_id.namespace_uri", "=", "urn:openspp:vocab:group-membership-type")],
                limit=1,
            )
        )
        for rec in self:
            rec.has_group_membership_type_codes = has_codes

    def _compute_has_group_type_codes(self):
        # sudo(): same rationale as above — we only expose a boolean.
        has_codes = bool(
            self.env["spp.vocabulary.code"]  # nosemgrep: odoo-sudo-without-context
            .sudo()
            .search_count(
                [("vocabulary_id.namespace_uri", "=", "urn:openspp:vocab:group-type")],
                limit=1,
            )
        )
        for rec in self:
            rec.has_group_type_codes = has_codes

    def write(self, values):
        res = super().write(values)
        self._validate_unique_membership_types()
        return res

    @api.model
    def create(self, values):
        new_record = super().create(values)
        new_record._validate_unique_membership_types()
        return new_record

    def _validate_unique_membership_types(self):
        """Validate that unique membership types (e.g., 'head') appear only once per group."""
        # Get the 'head' vocabulary code - this is a unique membership type
        # Use sudo() because this validation is internal and should work regardless of user permissions
        # nosemgrep: odoo-sudo-without-context
        head_code = self.env["spp.vocabulary.code"].sudo().get_code("urn:openspp:vocab:group-membership-type", "head")
        if not head_code:
            return

        for group in self:
            if not group.group_membership_ids:
                continue
            head_count = sum(
                1 for membership in group.group_membership_ids if head_code.id in membership.membership_type_ids.ids
            )
            if head_count > 1:
                raise ValidationError(_("Only one %s is allowed per group") % head_code.display)

    def invalidate_group_metrics(self):
        """Invalidate cached metrics for these groups.

        Called when group composition changes (members added/removed)
        to ensure metric() calls in CEL return fresh values.
        """
        if not self:
            return

        # Check if spp_indicators is installed
        if "spp.indicator.invalidation.buffer" not in self.env:
            return

        buffer = self.env["spp.indicator.invalidation.buffer"]

        # Invalidate all household metrics for affected groups
        # Using wildcard pattern - safer default, can optimize later
        buffer.add(pattern="household.*", subject_model="res.partner", subject_ids=self.ids)

        # Also invalidate scoring metrics
        buffer.add(pattern="scoring.*", subject_model="res.partner", subject_ids=self.ids)

        _logger.debug("[spp.registry] Scheduled metric invalidation for %d groups", len(self))

    def count_individuals(self, relationship_kinds=None, domain=None):
        """
        Count the number of individuals in the group that match the kinds and domain.
        """
        # _logger.info("SQL DEBUG: count_individuals: records:%s" % self.ids)
        membership_kind_domain = None
        individual_domain = None
        if self.group_membership_ids:
            if relationship_kinds:
                membership_kind_domain = [("name", "in", relationship_kinds)]
        else:
            return dict()

        if domain is not None:
            individual_domain = domain

        query_result = self._query_members_aggregate(membership_kind_domain, individual_domain)

        return query_result

    def _query_members_aggregate(self, membership_kind_domain=None, individual_domain=None):
        # Short‑circuit when there are no memberships; avoids unnecessary query
        # building (and compatibility issues with deprecated _where_calc API).
        if not self.group_membership_ids:
            return []

        ids = self.ids
        partner_model = "res.partner"
        domain = [
            ("is_registrant", "=", True),
            ("is_group", "=", True),
            ("disabled", "=", None),
        ]
        # Use expression.expression() instead of deprecated _where_calc in Odoo 19
        query_obj = expression.expression(
            model=self.env[partner_model],
            domain=domain,
        ).query

        membership_alias = query_obj.left_join("res_partner", "id", "spp_group_membership", "group", "id")
        individual_alias = query_obj.left_join(membership_alias, "individual", "res_partner", "id", "individual")
        membership_kind_rel_alias = query_obj.left_join(
            membership_alias,
            "id",
            "spp_group_membership_spp_vocabulary_code_rel",
            "spp_group_membership_id",
            "id",
        )
        rel_kind_alias = query_obj.left_join(
            membership_kind_rel_alias,
            "spp_vocabulary_code_id",
            "spp_vocabulary_code",
            "id",
            "id",
        )

        # Add INNER JOIN with VALUES (ids)
        # TODO: In the absence of managing "INNER JOIN" by Odoo Query object,
        # We will create the inner join manually
        inner_join_vals = "(" + "), (".join(map(str, ids)) + ")"
        inner_join_query = f"INNER JOIN ( VALUES {inner_join_vals} ) vals(v)"
        inner_join_query += f' ON ("{membership_alias}"."group" = v and not "{membership_alias}"."is_ended") '

        # Build where clause for the membership_alias
        # In Odoo 19, create a separate query to extract the where clause
        membership_query = Query(self.env, membership_alias, self.env["spp.group.membership"]._table_sql)
        expression.expression(
            model=self.env["spp.group.membership"],
            domain=[("is_ended", "=", False)],
            alias=membership_alias,
            query=membership_query,
        )
        # Extract the where clause SQL and add it to the main query
        membership_where_sql = membership_query.where_clause
        if membership_where_sql:
            query_obj.add_where(membership_where_sql)

        # Build where clause for the individual_alias
        individual_query = Query(self.env, individual_alias, self.env["res.partner"]._table_sql)
        expression.expression(
            model=self.env["res.partner"],
            domain=[("disabled", "=", None)],
            alias=individual_alias,
            query=individual_query,
        )
        # Extract the where clause SQL and add it to the main query
        individual_where_sql = individual_query.where_clause
        if individual_where_sql:
            query_obj.add_where(individual_where_sql)

        if membership_kind_domain:
            # Convert domain from old 'name' field to vocabulary code 'display' field
            vocab_domain = []
            for leaf in membership_kind_domain:
                if isinstance(leaf, list | tuple) and leaf[0] == "name":
                    vocab_domain.append(("display", leaf[1], leaf[2]))
                else:
                    vocab_domain.append(leaf)
            membership_kind_query = Query(self.env, rel_kind_alias, self.env["spp.vocabulary.code"]._table_sql)
            expression.expression(
                model=self.env["spp.vocabulary.code"],
                domain=vocab_domain,
                alias=rel_kind_alias,
                query=membership_kind_query,
            )
            # Extract the where clause SQL and add it to the main query
            membership_kind_where_sql = membership_kind_query.where_clause
            if membership_kind_where_sql:
                query_obj.add_where(membership_kind_where_sql)

        if individual_domain:
            individual_query = Query(self.env, individual_alias, self.env[partner_model]._table_sql)
            expression.expression(
                model=self.env[partner_model],
                domain=individual_domain,
                alias=individual_alias,
                query=individual_query,
            )
            # Extract the where clause SQL and add it to the main query
            individual_where_sql = individual_query.where_clause
            if individual_where_sql:
                query_obj.add_where(individual_where_sql)

        select_query, select_params = query_obj.select("res_partner.id AS id", "count(*) AS members_cnt")

        # TODO: In the absence of managing "GROUP BY" by Odoo Query object,
        # we will add the GROUP BY clause manually
        select_query += " GROUP BY " + partner_model.replace(".", "_") + ".id"

        # TODO: In the absence of managing "INNER JOIN" by Odoo Query object,
        # Inject the prepared INNER JOIN manually
        index = select_query.find("WHERE")
        select_query = select_query[:index] + inner_join_query + select_query[index:]
        # _logger.info(
        #   "SQL DEBUG: SQL query: %s, params: %s" % (select_query, select_params)
        # )
        self.env.cr.execute(select_query, select_params)
        # Generate result as tuple
        results = self.env.cr.fetchall()
        # _logger.info("SQL DEBUG: SQL Query Result: %s" % results)
        return results

    def compute_count_and_set_indicator(self, field_name, kinds, domain, presence_only=False):
        """
        This method computes the count matching a domain, then sets the indicator on the field name.

        :param field_name: The name of the field.
        :type field_name: str
        :param kinds: The kinds of roles in the group
        :type kinds: list
        :param domain: The domain to filter group members.
        :type domain: list
        :param presence_only: A boolean value to define if we return a boolean instead of the count
        :type presence_only: bool
        :return: The count of the specified field, then sets the indicator on the field name.
        :rtype: int, bool
        """

        # _logger.info(
        #     "SQL DEBUG: compute_count_and_set_indicator: total records:%s" % len(self)
        # )
        # Get groups only
        records = self.filtered(lambda a: a.is_group)
        query_result = None
        if records:
            # Generate the SQL query
            query_result = records.count_individuals(relationship_kinds=kinds, domain=domain)
            # _logger.info(
            #     "SQL DEBUG: compute_count_and_set_indicator: field:%s, results:%s"
            #     % (field_name, query_result)
            # )

            result_map = dict(query_result)
            for record in records:
                if presence_only:
                    record[field_name] = result_map.get(record.id, 0) > 0
                else:
                    record[field_name] = result_map.get(record.id, 0)

    def _update_compute_fields(self, records, field_name, kinds, domain, presence_only=False):
        # Get groups only
        records = records.filtered(lambda a: a.is_group)

        query_result = None
        if records:
            # Generate the SQL query using Job Queue
            query_result = records.count_individuals(relationship_kinds=kinds, domain=domain)
            # _logger.info(
            #     "SQL DEBUG: job_queue->_update_compute_fields: field:%s, results:%s"
            #     % (field_name, query_result)
            # )
            # if query_result:
            #     # Update the compute fields and affected records

            result_map = dict(query_result)
            for record in records:
                # _logger.info(
                #     "SQL DEBUG: XXX job_queue->_update_compute_fields: record.id:%s, results:%s"
                #     % (record.id, result_map.get(record.id, 0))
                # )
                if presence_only:
                    record[field_name] = result_map.get(record.id, 0) > 0
                else:
                    record[field_name] = result_map.get(record.id, 0)
