### 19.0.2.1.0

- feat(registrant_gis): show Latitude and Longitude as editable fields on the registrant and group forms, kept in sync with the map coordinates in both directions. Values outside ±90 / ±180 are refused — including on import — so an impossible coordinate can no longer be stored and then break the map widget every time the record is opened, with no way to correct it (#1143)

### 19.0.2.0.0

- Initial migration to OpenSPP2
