### 19.0.2.0.1

- Keep hidden menus hidden after a module upgrade resets their
  ``group_ids`` via XML. Re-applying now runs from ``_register_hook`` so
  it covers every upgrade path (immediate, ``base.module.upgrade`` wizard,
  and CLI ``-u``), not just the immediate path handled by ``next()``.

### 19.0.2.0.0

- Initial migration to OpenSPP2
