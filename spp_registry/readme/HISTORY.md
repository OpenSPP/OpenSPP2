### 19.0.2.1.5

- fix(registry): reject future dates of birth on every write path. `_birthdate_onchange` only guards the form UI, so ORM `create`/`write`, CSV/Excel import, and API writes (XML-RPC, API v2, DCI) could persist a future `birthdate` — which the non-stored `age` compute then rendered as a negative string. A stored-field `@api.constrains("birthdate")` (`_check_birthdate_not_future`) now enforces this server-side; the onchange is kept as the friendlier silent-reset UX in the form (#362)

### 19.0.2.1.4

- fix(registry): remove the dead `@api.constrains("age")` `_check_age_is_integer` guard. `age` is a non-stored compute derived from `birthdate`, so the constraint never fired and only emitted the registry-load warning `@constrains parameter 'age' is not writeable`. Computed `age` values are unchanged; stale i18n entries for the removed message are dropped

### 19.0.2.1.3

- fix(registry): show an ID **Status** column on the group form (Valid/Invalid badge) so a soft-removed ID is distinguishable from a valid one. IDs added directly via the registry UI keep an **empty** status (Valid/Invalid is set only by the ID-document change request flow) — per the #1110 decision to stay consistent across the system (#1110)

### 19.0.2.1.1

- fix(views): add reusable `x2many_no_padding` JS widget that suppresses the four empty placeholder rows Odoo 19 hardcodes on inline list-in-form views. Apply it to the Phone, IDs, Relationships, Group Membership, and Group Members lists on registrant forms so blank cells don't bloat the layout (#943).

### 19.0.2.0.0

- Initial migration to OpenSPP2
