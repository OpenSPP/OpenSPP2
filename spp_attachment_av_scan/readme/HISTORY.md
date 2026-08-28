### 19.0.2.0.2

- fix: never enqueue a malware scan while the registry is still loading. The
  scan-queue hooks re-raise database errors, and registry construction has no
  transaction-retry wrapper, so a transient serialization conflict raised while
  enqueueing aborted the whole load. Attachments written during load (module
  data, menu `web_icon_data`) stay `pending` instead; a `datas` write during load
  still resets the scan status, so changed bytes never keep a stale `clean`
  verdict

### 19.0.2.0.1

- fix: re-raise database errors (`psycopg2.Error`, `ConcurrencyError`) from the
  create/write scan-queue hooks instead of swallowing them, so transient
  serialization failures reach Odoo's transaction retry machinery instead of
  poisoning the transaction for unrelated downstream code

### 19.0.2.0.0

- Initial migration to OpenSPP2
