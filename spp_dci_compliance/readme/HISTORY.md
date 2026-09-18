### 19.0.1.0.1

- fix(dci_compliance): the security-warning systray item requested the `rpc` web service, which Odoo 19 no longer provides. `useService("rpc")` throws at component setup, and because the item is registered for every backend user the whole webclient failed to mount on any database with this module installed: a blank page after login, for everyone. The component now calls `rpc()` from `@web/core/network/rpc` directly, the same way the rest of OpenSPP does. The `/dci/security/warnings` route the item depends on gains its first tests (#450)
