-- Scalability indexes for spp_event_data module
-- These indexes support queries for 40M+ registrants and 300M+ events

-- ══════════════════════════════════════════════════════════════
-- EVENT DATA INDEXES
-- ══════════════════════════════════════════════════════════════

-- Primary lookup: active events per registrant by type
-- Supports: "Get active survey for registrant X"
CREATE INDEX IF NOT EXISTS idx_spp_event_data_active_by_type
ON spp_event_data (partner_id, event_type_code)
WHERE state = 'active';

-- Collection date range queries
-- Supports: "Events collected in date range"
CREATE INDEX IF NOT EXISTS idx_spp_event_data_collection_date
ON spp_event_data (collection_date DESC, partner_id);

-- Expiry tracking for cron jobs
-- Supports: "_cron_expire_events"
CREATE INDEX IF NOT EXISTS idx_spp_event_data_expiry
ON spp_event_data (expiry_date)
WHERE state = 'active' AND expiry_date IS NOT NULL;

-- External source deduplication
-- Supports: "Find event by ODK submission ID"
CREATE INDEX IF NOT EXISTS idx_spp_event_data_source_ref
ON spp_event_data (source_reference)
WHERE source_reference IS NOT NULL;

-- State-based filtering
-- Supports: "All pending events" dashboard queries
CREATE INDEX IF NOT EXISTS idx_spp_event_data_state
ON spp_event_data (state)
WHERE state IN ('draft', 'pending');

-- ══════════════════════════════════════════════════════════════
-- EVENT TYPE INDEXES
-- ══════════════════════════════════════════════════════════════

-- Code lookup (unique constraint provides index)
-- Type filtering by source
CREATE INDEX IF NOT EXISTS idx_spp_event_type_source
ON spp_event_type (source_type)
WHERE active = true;

-- ══════════════════════════════════════════════════════════════
-- REGISTRANT (res_partner) INDEXES
-- ══════════════════════════════════════════════════════════════

-- Note: These should be added by spp_registry_base module
-- Listed here for reference only

-- Active registrant lookup
-- CREATE INDEX IF NOT EXISTS idx_res_partner_is_registrant
-- ON res_partner (is_registrant)
-- WHERE is_registrant = true AND active = true;
