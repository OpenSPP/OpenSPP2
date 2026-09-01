### 19.0.2.2.3

- fix(registry): repair the stored `status`/`is_ended` computes on `spp.group.membership` once the clock crosses `ended_date`. Both fields depend only on `ended_date` compared against *now*, so a future-dated departure never took effect once the clock crossed it — rosters, metrics, API search and downstream gates kept treating the member as active indefinitely. Writing a future `ended_date` now schedules the repair cron at exactly that moment (staleness window ~1 minute), and a daily sweep self-heals everything else: rows already stale in existing databases (drained in committed batches on the first run, however large the backlog) and rows written behind the ORM, including `is_ended = NULL` rows that raw-SQL consumers treated as ended (#417)

### 19.0.2.2.2

- fix(registry): let an ID type be used again after its ID was removed. Removing an ID through a change request keeps the row and marks it Invalid, and the old uniqueness rule counted those dead rows — so the registrant was left with an Invalid ID and no way to add a valid one of the same type. Uniqueness now applies to live IDs only, and is refused before the write so the message names the ID type rather than surfacing a database error (#1136)

### 19.0.2.2.1

- feat(registry): registry configuration is consolidated into one **Registry Settings** section in the Settings app, with the Restrict Registry Edits toggle and the relocated superuser configuration menus (API V2, Import Match). Changing the toggle needs a Settings administrator; the section's menu is gated to match, since the framework refuses a settings save from anyone else (#1009)

### 19.0.2.1.4

- fix(registry): remove the dead `@api.constrains("age")` `_check_age_is_integer` guard. `age` is a non-stored compute derived from `birthdate`, so the constraint never fired and only emitted the registry-load warning `@constrains parameter 'age' is not writeable`. Computed `age` values are unchanged; stale i18n entries for the removed message are dropped

### 19.0.2.1.3

- fix(registry): show an ID **Status** column on the group form (Valid/Invalid badge) so a soft-removed ID is distinguishable from a valid one. IDs added directly via the registry UI keep an **empty** status (Valid/Invalid is set only by the ID-document change request flow) — per the #1110 decision to stay consistent across the system (#1110)

### 19.0.2.1.1

- fix(views): add reusable `x2many_no_padding` JS widget that suppresses the four empty placeholder rows Odoo 19 hardcodes on inline list-in-form views. Apply it to the Phone, IDs, Relationships, Group Membership, and Group Members lists on registrant forms so blank cells don't bloat the layout (#943).

### 19.0.2.0.0

- Initial migration to OpenSPP2
