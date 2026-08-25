### 19.0.2.1.1

- fix(security): the Tier-3 `group_registry_read` group can read `spp.irrigation.asset`. The registrant form renders `irrigation_asset_ids`, and the model was granted only to the Tier-2 `group_registry_viewer` group. Note the pre-existing `access_spp_irrigation_asset_registry_read` entry is misnamed — it grants the Tier-2 viewer group — so the new entry uses a distinct identifier rather than renaming it and orphaning the old one.

### 19.0.2.1.0

- feat(views): add an "Irrigation" tab on the farm (group) form so per-farm irrigation assets are reachable without leaving the farm record; backed by a new `irrigation_asset_ids` One2many on `res.partner` (inverse of the existing `farm_id`)

### 19.0.2.0.0

- Initial migration to OpenSPP2
