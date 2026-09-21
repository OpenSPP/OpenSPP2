### 19.0.2.0.2

- test(dci_client): make the outgoing-log integration tests hold on a database that has `spp_api_v2` installed, the only place they run at all (they skip without `spp.api.outgoing.log`, so they had never executed before the full-stack CI). The client writes the audit row through a separate, committed cursor so it survives the request's rollback; a test transaction at REPEATABLE READ cannot see that row and instead found an earlier class's committed row, so every status assertion compared against a stale success entry. The tests now assert at the log-service seam, one test reads a real row back through a fresh cursor and removes it, and the 401-retry test builds a valid OAuth2 source and asserts the two log calls in the order the code guarantees. No behaviour change (#443)

### 19.0.2.0.0

- Initial migration to OpenSPP2
