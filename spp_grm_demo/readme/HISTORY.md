### 19.0.2.0.1

- fix(security): archive the default-credential GRM demo users (`demo_grm_manager`, `demo_grm_officer`, shared password `demo`) on a production install via a `post_init_hook`; they stay active only when demo data is enabled. Also drop `Production/Stable` (this is a demo-only bundle).

### 19.0.2.0.0

- Initial migration to OpenSPP2
