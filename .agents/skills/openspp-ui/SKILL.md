---
name: openspp-ui
description:
  OpenSPP UI design patterns for Odoo 19 views. Use when creating or modifying forms,
  lists, kanban, dashboards, or search views in spp_* modules.
---

# OpenSPP UI Design

Enforce consistent UI for OpenSPP's social protection platform on Odoo 19.

## Design Personality

OpenSPP serves **government agencies and NGOs**. The UI must convey:

- **Trust** - Government-grade reliability, no flashy effects
- **Clarity** - Dense but organized, scannable information
- **Accessibility** - Works for field officers on varying devices
- **Efficiency** - Power users need speed, not hand-holding

## Before Creating a View

**Ask: What's the user's task?**

| Task Type       | Layout                 | Key Features                        |
| --------------- | ---------------------- | ----------------------------------- |
| Data Entry      | Multi-column, editable | Inline lists, minimal readonly      |
| Review/Approval | Status prominent       | Ribbons, history tab, readonly feel |
| Dashboard       | KPI cards              | Clickable stats, visual counts      |
| Configuration   | Grouped settings       | Heavy help text, toggles            |

## State & Color Vocabulary

Use consistently across all modules:

| State     | List Decoration      | Badge Class         | Icon         |
| --------- | -------------------- | ------------------- | ------------ |
| Draft     | `decoration-muted`   | `text-bg-secondary` | `fa-pencil`  |
| Pending   | `decoration-warning` | `text-bg-warning`   | `fa-clock-o` |
| Approved  | `decoration-success` | `text-bg-success`   | `fa-check`   |
| Rejected  | `decoration-danger`  | `text-bg-danger`    | `fa-times`   |
| Cancelled | `decoration-muted`   | `text-bg-secondary` | `fa-ban`     |

## Standard Form Structure

```xml
<form>
  <header>
    <button
      name="action_submit"
      string="Submit"
      type="object"
      class="btn-primary"
      invisible="state != 'draft'"
    />
    <field name="state" widget="statusbar" statusbar_visible="draft,pending,approved" />
  </header>
  <sheet>
    <widget
      name="web_ribbon"
      title="Approved"
      invisible="state != 'approved'"
      bg_color="text-bg-success"
    />
    <div class="oe_button_box" name="button_box" />
    <div class="oe_title">
      <h1>
        <field name="name" placeholder="Name" />
      </h1>
    </div>
    <group col="2">
      <group name="left_section">...</group>
      <group name="right_section">...</group>
    </group>
    <notebook>
      <page name="details" string="Details">...</page>
    </notebook>
  </sheet>
  <chatter />
</form>
```

**Key rules:**

- Header: only buttons + statusbar
- Sheet: ribbon → button_box → title → groups → notebook
- Always name your groups for extensibility

## Anti-Patterns

### Odoo 19 Gotchas

```xml
<!-- WRONG --> <xpath expr="//div[@class='oe_title']" ...>
<!-- RIGHT --> <xpath expr="//div[hasclass('oe_title')]" ...>

<!-- WRONG --> <group string="Group By">  <!-- in search view -->
<!-- RIGHT --> <group>
```

```python
# WRONG: Tuple syntax
partner.write({'child_ids': [(0, 0, {'name': 'New'})]})

# RIGHT: Command API
from odoo import Command
partner.write({'child_ids': [Command.create({'name': 'New'})]})
```

### OpenSPP Mistakes

- Editable fields in `<header>` → use tabs
- Positional XPath `//page[1]` → use named elements
- Forms without named groups → breaks inheritance

## Detailed Patterns

For comprehensive guidelines, see [UI Design Principles](docs/principles/ui-design.md):

- Multi-column layouts
- Extension points and XPath targets
- Widget selection guide
- Dashboard KPI patterns
- Search and list view patterns
