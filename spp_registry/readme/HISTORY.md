### 19.0.2.1.3

- fix(registry): show an ID **Status** column on the group form (Valid/Invalid badge) so a soft-removed ID is distinguishable from a valid one. IDs added directly via the registry UI keep an **empty** status (Valid/Invalid is set only by the ID-document change request flow) — per the #1110 decision to stay consistent across the system (#1110)

### 19.0.2.1.1

- fix(views): add reusable `x2many_no_padding` JS widget that suppresses the four empty placeholder rows Odoo 19 hardcodes on inline list-in-form views. Apply it to the Phone, IDs, Relationships, Group Membership, and Group Members lists on registrant forms so blank cells don't bloat the layout (#943).

### 19.0.2.0.0

- Initial migration to OpenSPP2
