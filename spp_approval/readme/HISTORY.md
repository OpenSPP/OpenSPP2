### 19.0.2.0.1

- Fix CEL Expressions tab crash: the ace editor fields used the invalid
  CodeEditor mode ``text``; changed to ``javascript`` (Odoo 19 only accepts
  ``javascript``/``xml``/``qweb``/``scss``/``python``). ``javascript`` is
  used because the CEL dialect uses ``&&``/``||``/``!``, ``true``/``false``/
  ``null`` and ``? :`` ternaries, which it highlights correctly.

### 19.0.2.0.0

- Initial migration to OpenSPP2
