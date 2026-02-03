# External Dependencies

OpenSPP requires the following external Odoo module repositories.
The Docker setup fetches these automatically. For manual installation,
clone each repo and add it to your Odoo addons path.

| Repository | Branch | Modules |
|------------|--------|---------|
| [OCA/queue](https://github.com/OCA/queue) | 19.0 | `queue_job` |
| [OCA/rest-framework](https://github.com/OCA/rest-framework) | 19.0 | `extendable`, `extendable_fastapi` |
| [OCA/server-backend](https://github.com/OCA/server-backend) | 19.0 | `base_user_role` |
| [OCA/server-tools](https://github.com/OCA/server-tools) | 19.0 | `base_sparse_field` |
| [OCA/server-ux](https://github.com/OCA/server-ux) | 19.0 | `base_technical_user` |
| [muk-it/odoo-modules](https://github.com/muk-it/odoo-modules) | 19.0 | `muk_web_theme`, `muk_web_chatter` |
