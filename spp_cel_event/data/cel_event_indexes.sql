-- Scalability indexes for spp_cel_event module
-- These indexes optimize CEL expression evaluation against event data

-- ══════════════════════════════════════════════════════════════
-- EVENT DATA CEL QUERY INDEXES
-- ══════════════════════════════════════════════════════════════

-- Composite index for fast event lookup in CEL expressions
-- Supports: event('survey_code', 'field_name') queries
-- This index enables the most common CEL pattern: checking specific fields
-- for a registrant's most recent event of a given type
CREATE INDEX IF NOT EXISTS idx_cel_event_lookup
ON spp_event_data (partner_id, event_type_code, state, collection_date DESC)
WHERE state = 'active';

-- JSONB GIN index for field data queries
-- Supports: Fast field extraction from data_json JSONB column
-- Enables efficient queries like: event('survey', 'field')['value']
CREATE INDEX IF NOT EXISTS idx_cel_event_data_jsonb
ON spp_event_data USING GIN (data_json)
WHERE state = 'active';

-- Partial index for date-range queries in CEL
-- Supports: event_between('survey', date1, date2) queries
-- Optimizes temporal eligibility rules (e.g., events in last 6 months)
CREATE INDEX IF NOT EXISTS idx_cel_event_date_range
ON spp_event_data (event_type_code, collection_date DESC, partner_id)
WHERE state = 'active' AND collection_date IS NOT NULL;

-- Composite index for event counting in CEL
-- Supports: event_count('survey_code') queries
-- Enables efficient counting of events per registrant per type
CREATE INDEX IF NOT EXISTS idx_cel_event_count
ON spp_event_data (partner_id, event_type_code, state)
WHERE state = 'active';
