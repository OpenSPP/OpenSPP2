### 19.0.2.1.0

- Enforce ``UNIQUE(menu_id)`` on ``spp.hide.menu``: a second configuration row
  for the same menu made ``hide_menus()`` raise ``Expected singleton`` from
  ``_register_hook`` and abort the registry load — a total outage (#408).
  ``hide_menus()`` now also reads its state off a single governing row, so a
  database on which the constraint could not be applied keeps working.
- Ship a pre-migration that de-duplicates existing rows before the constraint
  lands, preferring a row that can still restore its menu. The surplus rows'
  external ids are repointed onto the surviving row and marked ``noupdate``,
  so the seeding module's next upgrade adopts the survivor instead of
  recreating a duplicate, and dropping the seed later cannot garbage-collect
  it.
- Behaviour note for module authors: installing a module that seeds an
  ``spp.hide.menu`` record for a menu that already has a configuration row now
  fails loudly with an ``IntegrityError`` instead of silently inserting the
  duplicate that used to brick the next registry load. Target the existing
  record or drop the seed.

### 19.0.2.0.1

- Keep hidden menus hidden after a module upgrade resets their
  ``group_ids`` via XML. Re-applying now runs from ``_register_hook`` so
  it covers every upgrade path (immediate, ``base.module.upgrade`` wizard,
  and CLI ``-u``), not just the immediate path handled by ``next()``.

### 19.0.2.0.0

- Initial migration to OpenSPP2
