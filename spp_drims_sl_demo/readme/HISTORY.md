### 19.0.2.0.1

- fix(security): archive the six default-credential DRIMS-SL demo users (`kumari`, `rajitha`, `silva`, `perera`, `fernando`, `secretary`, shared password `demo`) on a production install via a `post_init_hook` reusing spp_drims_sl's helper; they stay active only when demo data is enabled. A migration archives them the same way on upgrade from a released version (the install hook does not run on `-u`).

### 19.0.2.0.0

- Initial migration to OpenSPP2
