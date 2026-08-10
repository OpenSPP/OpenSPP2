### 19.0.2.0.1

- fix: re-raise database errors (`psycopg2.Error`, `ConcurrencyError`) from the
  create/write scan-queue hooks instead of swallowing them, so transient
  serialization failures reach Odoo's transaction retry machinery instead of
  poisoning the transaction for unrelated downstream code

### 19.0.2.0.0

- Initial migration to OpenSPP2
