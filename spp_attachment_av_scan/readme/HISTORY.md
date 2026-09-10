### 19.0.2.2.0

- fix: stop module upgrades from resetting the quarantine crons and config
  parameters. `data/quarantine_cron.xml` shipped in a plain `<odoo>` block, so
  every upgrade rewrote all four records to the shipped defaults: a tuned
  `quarantine_retention_days`, a changed cron interval, or a deliberately
  disabled cron was silently reverted. The file is now `noupdate="1"`. A
  post-migration reconciles the `noupdate` column on the `ir_model_data` rows of
  databases that installed the module earlier, leaving the stored values
  untouched, so tuned values survive and untouched defaults stay as shipped

### 19.0.2.1.0

- feat: sweep attachments stranded at `scan_status = pending`. Queueing a scan is
  best-effort, so a non-database enqueue failure leaves the attachment written and
  unscanned with nothing to bring it back; registry-load writes land in the same
  state. An hourly `ir.cron` re-queues them. Bounded on both axes so it is safe to
  leave enabled on an existing database: `pending_sweep_batch_size` (default 100)
  caps one run, `pending_sweep_max_attempts` (default 3) caps the attempts per
  record, and `pending_sweep_min_age_minutes` (default 60) keeps a fresh upload that
  is merely waiting in a deep queue from being double-queued. Quarantined files,
  forensic download copies, attachments with no `res_model`, and the system models
  that store their own source-controlled binaries (menu `web_icon_data`) are out of
  scope

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
