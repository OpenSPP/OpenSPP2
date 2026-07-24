### 19.0.2.0.1

- fix(security): archive the 14 default-credential DRIMS-SL demo users (shared password `demo`, including `admin.dmc@drims.gov.lk` which holds `base.group_system`) on a production install via a self-contained `post_init_hook`; they stay active only when demo data is enabled.

### 19.0.2.0.0

- Initial migration to OpenSPP2
