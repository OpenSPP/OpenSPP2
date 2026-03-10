### Developer Guide: Creating Custom CR Types

This guide walks through creating a new change request type, from a minimal
single-field example to advanced dynamic approval with multi-tier workflows.

**Architecture overview**

A CR type consists of four parts:

| Part | What it does |
| --- | --- |
| **Detail model** | Python model holding the proposed changes (inherits `spp.cr.detail.base`) |
| **Detail form view** | XML view rendered inside the CR form |
| **CR type record** | XML data linking the detail model, view, approval workflow, and field mappings |
| **Field mappings** | XML records defining how detail fields map to registrant fields at apply time |

When a user creates a change request, the system:

1. Creates a `spp.change.request` record
2. Auto-creates the linked detail record via `_ensure_detail()`
3. Pre-fills detail fields from the registrant via `prefill_from_registrant()`
4. On submission, selects the approval workflow (static or dynamic)
5. After approval, applies changes to the registrant via field mappings or custom logic

### Example 1: Basic CR Type (Static Approval)

A CR type that lets users update a single field with one-tier approval.

**Detail model**

```python
# models/cr_detail_update_widget.py
from odoo import fields, models


class SPPCRDetailUpdateWidget(models.Model):
    _name = "spp.cr.detail.update_widget"
    _description = "CR Detail: Update Widget"
    _inherit = ["spp.cr.detail.base", "mail.thread"]

    widget_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Widget",
        domain="[('namespace_uri', '=', 'urn:example:widget')]",
        tracking=True,
    )

    def _get_prefill_mapping(self):
        return {"widget_id": "widget_id"}
```

Key points:

- Always inherit `spp.cr.detail.base` (required) and `mail.thread` (for tracking)
- Never use `required=True` on detail fields — the detail record is created empty
  by `_ensure_detail()` and populated later
- `_get_prefill_mapping()` returns `{detail_field: registrant_field}` — the base class
  copies current registrant values into the detail on creation

**Detail form view**

```xml
<!-- views/detail_update_widget_views.xml -->
<record id="spp_cr_detail_update_widget_form" model="ir.ui.view">
    <field name="name">spp.cr.detail.update_widget.form</field>
    <field name="model">spp.cr.detail.update_widget</field>
    <field name="arch" type="xml">
        <form string="Update Widget">
            <header>
                <button name="action_proceed_to_cr" string="Proceed"
                    type="object" class="btn-primary"
                    invisible="approval_state != 'draft'" />
                <button name="action_proceed_to_cr" string="Proceed"
                    type="object" class="btn-primary"
                    invisible="approval_state != 'revision'" />
                <field name="approval_state" widget="statusbar"
                    statusbar_visible="draft,pending,approved,applied" />
            </header>
            <sheet>
                <group>
                    <group>
                        <field name="widget_id" />
                    </group>
                </group>
            </sheet>
        </form>
    </field>
</record>
```

The `action_proceed_to_cr` button navigates back to the parent CR form.
`approval_state` is a related field from `spp.cr.detail.base`.

**Approval definition and CR type data**

```xml
<!-- data/cr_type_update_widget.xml -->
<odoo noupdate="1">
    <!-- Approval definition: single-tier group approval -->
    <record id="approval_def_update_widget" model="spp.approval.definition">
        <field name="name">Update Widget Approval</field>
        <field name="model_id" ref="spp_change_request_v2.model_spp_change_request" />
        <field name="approval_type">group</field>
        <field name="approval_group_id" ref="my_module.group_validator" />
        <field name="is_require_comment">True</field>
        <field name="sla_days">5</field>
    </record>

    <!-- CR type -->
    <record id="cr_type_update_widget" model="spp.change.request.type">
        <field name="name">Update Widget</field>
        <field name="code">update_widget</field>
        <field name="description">Update widget assignment</field>
        <field name="target_type">individual</field>
        <field name="detail_model">spp.cr.detail.update_widget</field>
        <field name="detail_form_view_id" ref="spp_cr_detail_update_widget_form" />
        <field name="apply_strategy">field_mapping</field>
        <field name="auto_apply_on_approve">True</field>
        <field name="approval_definition_id" ref="approval_def_update_widget" />
        <field name="icon">fa-cog</field>
        <field name="sequence">50</field>
        <field name="is_system_type">True</field>
        <field name="source_module">my_module</field>
    </record>

    <!-- Field mapping: detail.widget_id → registrant.widget_id -->
    <record id="cr_type_update_widget_mapping" model="spp.change.request.type.mapping">
        <field name="type_id" ref="cr_type_update_widget" />
        <field name="source_field">widget_id</field>
        <field name="target_field">widget_id</field>
        <field name="sequence">10</field>
    </record>
</odoo>
```

**Access control**

Add rows to `security/ir.model.access.csv`:

```
access_spp_cr_detail_update_widget_user,...,group_cr_user,1,1,1,0
access_spp_cr_detail_update_widget_validator,...,group_cr_validator,1,1,1,0
access_spp_cr_detail_update_widget_validator_hq,...,group_cr_validator_hq,1,1,1,0
access_spp_cr_detail_update_widget_manager,...,group_cr_manager,1,1,1,1
```

**Manifest**

```python
{
    "depends": ["spp_change_request_v2"],
    "data": [
        "security/ir.model.access.csv",
        "views/detail_update_widget_views.xml",   # views BEFORE data
        "data/cr_type_update_widget.xml",
    ],
}
```

Views must load before data that references them via `detail_form_view_id`.

### Example 2: Multi-Field CR Type with Multi-Tier Approval

A CR type with several fields and a two-tier approval chain (Tier 1 then Tier 2).

**Detail model with boolean prefill override**

```python
from odoo import fields, models


class SPPCRDetailUpdateProfile(models.Model):
    _name = "spp.cr.detail.update_profile"
    _description = "CR Detail: Update Profile"
    _inherit = ["spp.cr.detail.base", "mail.thread"]

    status_id = fields.Many2one(
        "spp.vocabulary.code",
        string="Status",
        domain="[('namespace_uri', '=', 'urn:example:status')]",
        tracking=True,
    )
    is_active = fields.Boolean(string="Active", tracking=True)
    notes = fields.Text(string="Notes")

    def _get_prefill_mapping(self):
        return {
            "status_id": "status_id",
            "is_active": "is_active",
        }

    def prefill_from_registrant(self):
        """Override: base class skips False booleans; use 'is not None' instead."""
        self.ensure_one()
        if not self.registrant_id:
            return

        mapping = self._get_prefill_mapping()
        values = {}
        for detail_field, registrant_field in mapping.items():
            value = getattr(self.registrant_id, registrant_field, None)
            if value is not None:
                values[detail_field] = value

        if values:
            self.write(values)
```

**Multi-tier approval definition (XML)**

Multi-tier definitions require a three-step pattern — Odoo enforces a constraint
that tiers must exist before `use_multitier` can be enabled:

```xml
<odoo noupdate="1">
    <!-- Step 1: Create definition WITHOUT use_multitier -->
    <record id="approval_def_update_profile" model="spp.approval.definition">
        <field name="name">Update Profile - Two-Tier Approval</field>
        <field name="model_id" ref="spp_change_request_v2.model_spp_change_request" />
        <field name="approval_type">group</field>
        <field name="approval_group_id" ref="my_module.group_tier1" />
        <field name="is_require_comment">True</field>
    </record>

    <!-- Step 2: Create tier records -->
    <record id="tier_update_profile_1" model="spp.approval.tier">
        <field name="definition_id" ref="approval_def_update_profile" />
        <field name="name">Tier 1 - Field Review</field>
        <field name="sequence">10</field>
        <field name="approval_type">group</field>
        <field name="approval_group_id" ref="my_module.group_tier1" />
    </record>

    <record id="tier_update_profile_2" model="spp.approval.tier">
        <field name="definition_id" ref="approval_def_update_profile" />
        <field name="name">Tier 2 - HQ Review</field>
        <field name="sequence">20</field>
        <field name="approval_type">group</field>
        <field name="approval_group_id" ref="my_module.group_tier2" />
    </record>

    <!-- Step 3: Enable multi-tier AFTER tiers exist -->
    <record id="approval_def_update_profile" model="spp.approval.definition">
        <field name="use_multitier">True</field>
    </record>
</odoo>
```

### Example 3: Dynamic Approval

Dynamic approval lets the user select a single field to modify per change request.
The selected field determines which approval workflow applies, using CEL-based
conditions to route sensitive changes to stricter workflows.

Three things are needed:

1. Override `_get_field_to_modify_selection()` on the detail model
2. Create candidate approval definitions with CEL conditions
3. Set `use_dynamic_approval=True` on the CR type and link the candidates

**Detail model with field selector**

```python
from odoo import api, fields, models


class SPPCRDetailUpdateInfo(models.Model):
    _name = "spp.cr.detail.update_info"
    _description = "CR Detail: Update Info"
    _inherit = ["spp.cr.detail.base", "mail.thread"]

    status_id = fields.Many2one("spp.vocabulary.code", string="Status")
    category_id = fields.Many2one("spp.vocabulary.code", string="Category")
    is_priority = fields.Boolean(string="Priority")

    @api.model
    def _get_field_to_modify_selection(self):
        """Define which fields appear in the 'Field to Modify' dropdown."""
        return [
            ("status_id", "Status"),
            ("category_id", "Category"),
            ("is_priority", "Priority Flag"),
        ]

    def _get_prefill_mapping(self):
        return {
            "status_id": "status_id",
            "category_id": "category_id",
            "is_priority": "is_priority",
        }
```

**Detail form view with field visibility**

When dynamic approval is on, only the selected field is shown. Use the
`use_dynamic_approval` related field (available on `spp.cr.detail.base`)
instead of traversing `change_request_id.request_type_id.use_dynamic_approval`:

```xml
<form string="Update Info">
    <header>
        <button name="action_proceed_to_cr" string="Proceed"
            type="object" class="btn-primary"
            invisible="approval_state != 'draft'" />
        <field name="approval_state" widget="statusbar"
            statusbar_visible="draft,pending,approved,applied" />
    </header>
    <sheet>
        <!-- Field selector: visible only when dynamic approval is on -->
        <group invisible="not use_dynamic_approval">
            <group>
                <field name="field_to_modify"
                    required="use_dynamic_approval" />
            </group>
        </group>

        <!-- Each field hidden when dynamic approval is on and not selected -->
        <group>
            <group>
                <field name="status_id"
                    invisible="use_dynamic_approval
                               and field_to_modify != 'status_id'" />
                <field name="category_id"
                    invisible="use_dynamic_approval
                               and field_to_modify != 'category_id'" />
                <field name="is_priority"
                    invisible="use_dynamic_approval
                               and field_to_modify != 'is_priority'" />
            </group>
        </group>
    </sheet>
</form>
```

**Candidate approval definitions with CEL conditions**

Candidates are evaluated in `sequence` order. The first matching CEL condition
wins. A definition without a CEL condition acts as a catch-all fallback.

```xml
<odoo noupdate="1">
    <!-- Catch-all fallback (sequence=100, no CEL) — evaluated LAST -->
    <record id="approval_def_update_info_default" model="spp.approval.definition">
        <field name="name">Update Info - Default Approval</field>
        <field name="model_id" ref="spp_change_request_v2.model_spp_change_request" />
        <field name="approval_type">group</field>
        <field name="approval_group_id" ref="my_module.group_basic_approver" />
        <field name="sequence">100</field>
    </record>

    <!-- Status changes require stricter approval (sequence=10) -->
    <record id="approval_def_update_info_status" model="spp.approval.definition">
        <field name="name">Update Info - Status Change (Escalated)</field>
        <field name="model_id" ref="spp_change_request_v2.model_spp_change_request" />
        <field name="approval_type">group</field>
        <field name="approval_group_id" ref="my_module.group_senior_approver" />
        <field name="sequence">10</field>
        <field name="use_cel_condition">True</field>
        <field name="cel_condition">record.selected_field_name == "status_id"</field>
        <field name="is_require_comment">True</field>
        <field name="sla_days">10</field>
    </record>

    <!-- CR type with dynamic approval enabled -->
    <record id="cr_type_update_info" model="spp.change.request.type">
        <field name="name">Update Info</field>
        <field name="code">update_info</field>
        <field name="target_type">individual</field>
        <field name="detail_model">spp.cr.detail.update_info</field>
        <field name="detail_form_view_id" ref="spp_cr_detail_update_info_form" />
        <field name="apply_strategy">field_mapping</field>
        <field name="auto_apply_on_approve">True</field>
        <!-- Static fallback -->
        <field name="approval_definition_id" ref="approval_def_update_info_default" />
        <!-- Dynamic approval -->
        <field name="use_dynamic_approval">True</field>
        <field name="candidate_definition_ids" eval="[
            Command.link(ref('approval_def_update_info_status')),
            Command.link(ref('approval_def_update_info_default')),
        ]" />
    </record>
</odoo>
```

**CEL condition reference**

CEL conditions have access to these variables:

| Variable | Type | Description |
| --- | --- | --- |
| `record.selected_field_name` | string | Technical field name the user selected |
| `old_value` | typed | Current value on the registrant |
| `new_value` | typed | Proposed value from the detail record |
| `record` | dict | All fields on the `spp.change.request` record |
| `user` | dict | Current user |
| `company` | dict | Current company |

Many2one values are dicts with `id` and `name` (display_name) keys. Vocabulary
models (`spp.vocabulary.code`) additionally include `code` (string) and, if
hierarchical, a `parent` dict with `id`, `name`, and `code` keys.

Example CEL conditions:

```python
# Match by field name
record.selected_field_name == "status_id"

# Match multiple fields
record.selected_field_name in ["status_id", "category_id"]

# Match by new value (vocabulary code)
record.selected_field_name == "status_id" and new_value.code == "3"

# Match by value transition
old_value.code == "1" and new_value.code in ["32", "33"]

# Match by parent category (hierarchical vocabulary)
new_value.parent.code == "active"

# Combine field and value conditions
record.selected_field_name == "status_id" and (
    new_value.parent.code == "active" or
    old_value.parent.code == "graduated"
)
```

**Combining dynamic approval with multi-tier**

A candidate definition can itself be multi-tier. For example, status changes
that require three-tier approval:

```xml
<!-- Definition with CEL condition -->
<record id="approval_def_update_info_escalated" model="spp.approval.definition">
    <field name="name">Update Info - Escalated (3-Tier)</field>
    <field name="model_id" ref="spp_change_request_v2.model_spp_change_request" />
    <field name="approval_type">group</field>
    <field name="approval_group_id" ref="my_module.group_tier1" />
    <field name="sequence">5</field>
    <field name="use_cel_condition">True</field>
    <field name="cel_condition">record.selected_field_name == "status_id"
        and old_value.code == "1" and new_value.code in ["32", "33"]</field>
</record>

<!-- Three tiers -->
<record id="tier_escalated_1" model="spp.approval.tier">
    <field name="definition_id" ref="approval_def_update_info_escalated" />
    <field name="name">Tier 1 - Field Office</field>
    <field name="sequence">10</field>
    <field name="approval_type">group</field>
    <field name="approval_group_id" ref="my_module.group_tier1" />
</record>

<record id="tier_escalated_2" model="spp.approval.tier">
    <field name="definition_id" ref="approval_def_update_info_escalated" />
    <field name="name">Tier 2 - Regional</field>
    <field name="sequence">20</field>
    <field name="approval_type">group</field>
    <field name="approval_group_id" ref="my_module.group_tier2" />
</record>

<record id="tier_escalated_3" model="spp.approval.tier">
    <field name="definition_id" ref="approval_def_update_info_escalated" />
    <field name="name">Tier 3 - National</field>
    <field name="sequence">30</field>
    <field name="approval_type">group</field>
    <field name="approval_group_id" ref="my_module.group_tier3" />
</record>

<!-- Enable multi-tier AFTER tiers exist -->
<record id="approval_def_update_info_escalated" model="spp.approval.definition">
    <field name="use_multitier">True</field>
</record>
```

### Methods Reference

Methods available for override on detail models (all inherited from
`spp.cr.detail.base`):

| Method | Decorator | Returns | When to override |
| --- | --- | --- | --- |
| `_get_field_to_modify_selection()` | `@api.model` | `[(field, label), ...]` | Dynamic approval: define selectable fields |
| `_get_prefill_mapping()` | instance | `{detail_field: registrant_field}` | Pre-fill detail from registrant on creation |
| `prefill_from_registrant()` | instance | None | Detail has boolean fields that need `False` pre-filled |

Related fields available on all detail models (from `spp.cr.detail.base`):

| Field | Type | Source |
| --- | --- | --- |
| `change_request_id` | Many2one | Direct link to parent CR |
| `registrant_id` | Many2one | `change_request_id.registrant_id` |
| `approval_state` | Selection | `change_request_id.approval_state` |
| `is_applied` | Boolean | `change_request_id.is_applied` |
| `use_dynamic_approval` | Boolean | `change_request_id.request_type_id.use_dynamic_approval` |
| `field_to_modify` | Selection | Dynamic field selector (populated by `_get_field_to_modify_selection`) |

### CR Type Fields Reference

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `name` | Char | required | Display name |
| `code` | Char | required | Unique identifier (lowercase, underscores) |
| `target_type` | Selection | `"both"` | `"individual"`, `"group"`, or `"both"` |
| `detail_model` | Char | required | Technical name of the detail model |
| `detail_form_view_id` | Many2one | required | Reference to the detail form view |
| `apply_strategy` | Selection | `"field_mapping"` | `"field_mapping"`, `"custom"`, or `"manual"` |
| `auto_apply_on_approve` | Boolean | `True` | Apply changes automatically after final approval |
| `approval_definition_id` | Many2one | required | Static/fallback approval workflow |
| `use_dynamic_approval` | Boolean | `False` | Enable field-level approval routing |
| `candidate_definition_ids` | Many2many | empty | Candidate definitions for dynamic routing |
| `icon` | Char | optional | FontAwesome icon class (e.g., `"fa-cog"`) |
| `sequence` | Integer | `10` | Display order in type lists |
| `is_system_type` | Boolean | `False` | Installed by a module (not user-created) |
| `source_module` | Char | optional | Module that installed this type |

### Checklist

Before declaring a new CR type complete:

- Detail model inherits `spp.cr.detail.base` and `mail.thread`
- No `required=True` on detail fields (validate at submission, not creation)
- `_get_prefill_mapping()` defined if fields should pre-fill from registrant
- `prefill_from_registrant()` overridden if detail has boolean fields
- Form view uses `approval_state` (not raw state field) for visibility
- Form view uses `use_dynamic_approval` (not the 3-level chain) for dynamic visibility
- Views listed before data in `__manifest__.py` (data references `detail_form_view_id`)
- `ir.model.access.csv` has 4 rows (user, validator, validator\_hq, manager)
- Field mappings exist for every field that should be applied to the registrant
- Approval definition has `model_id` pointing to `spp_change_request_v2.model_spp_change_request`
- If multi-tier: tiers created before `use_multitier=True` is set
- If dynamic: fallback definition has `sequence=100` (evaluated last)
- Tests cover CR creation, approval routing, and field application
