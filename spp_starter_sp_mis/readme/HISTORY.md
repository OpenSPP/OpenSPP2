### 19.0.2.1.1

- chore(starter_sp_mis): the duplicate SP-MIS Settings section is removed — the toggle it carried now lives in Registry Settings, and this module's storage key is written in step with it, so enforcement is unchanged (#1009)

### 19.0.2.1.0

- fix(starter_sp_mis): make the registry restriction hold and stop it re-locking itself. Enforcement moves from a JavaScript patch Odoo 19 no longer reads to the access check every create, write and delete passes through, so it applies over RPC and data import too; promoting a plain contact into the registry is refused as well. The setting is marked `noupdate`, with a migration for databases where an upgrade would otherwise keep switching it back on (#1142)

### 19.0.2.0.0

- Initial migration to OpenSPP2
