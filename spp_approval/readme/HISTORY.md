### 19.0.2.0.2

- fix(spp_approval): stop offering **New** on the approval review lists. A review is created by the approval flow when a record is submitted, so a hand-made one would need a model name, a record id and a definition typed into a blank form and would point at nothing. Both **My Pending Approvals** and **Approval Reviews** are affected, along with the New in a review's own breadcrumb (#1167)

### 19.0.2.0.1

- Fix CEL Expressions tab crash: the ace editor fields used the invalid
  CodeEditor mode ``text``; changed to ``javascript`` (Odoo 19 only accepts
  ``javascript``/``xml``/``qweb``/``scss``/``python``). ``javascript`` is
  used because the CEL dialect uses ``&&``/``||``/``!``, ``true``/``false``/
  ``null`` and ``? :`` ternaries, which it highlights correctly.

### 19.0.2.0.0

- Initial migration to OpenSPP2
