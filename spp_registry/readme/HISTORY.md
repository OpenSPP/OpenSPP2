### 19.0.2.1.3

- fix(registry): show an ID **Status** column on the group form (Valid/Invalid badge) and default a newly added ID to Valid so IDs added via the registry form are no longer left with an empty status (#1110)

### 19.0.2.1.1

- fix(views): add reusable `x2many_no_padding` JS widget that suppresses the four empty placeholder rows Odoo 19 hardcodes on inline list-in-form views. Apply it to the Phone, IDs, Relationships, Group Membership, and Group Members lists on registrant forms so blank cells don't bloat the layout (#943).

### 19.0.2.0.0

- Initial migration to OpenSPP2
