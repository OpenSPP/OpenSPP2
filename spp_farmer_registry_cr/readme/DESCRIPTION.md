Defines change request types specific to farmer registry operations. Enables structured, approval-controlled updates to farm details, agricultural activities, land parcels, and farm assets through the OpenSPP change request workflow.

### Key Features

- Four pre-defined CR types: Update Farm Details, Add Farm Activity, Update Land Parcel, Add/Update/Remove Farm Assets
- Granular operation controls per CR type (add/update/remove toggles for activities, parcels, assets)
- Field mappings for automatic value application on approval
- Custom apply strategy handlers for each CR type
- Role-based approval routing with Local-to-HQ validator workflow
