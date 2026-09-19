#!/usr/bin/env python3
"""Verify lead migrations and call status tracking in an isolated, rolled-back PostgreSQL schema."""
from pathlib import Path
import subprocess
import uuid

root = Path(__file__).resolve().parents[1]
schema = 'dashboard_test_' + uuid.uuid4().hex
migration = root / 'backend/src/main/resources/db/migration'
sql = f'BEGIN; CREATE SCHEMA {schema}; SET LOCAL search_path TO {schema};\n'
sql += (migration / 'V1__initial.sql').read_text()
# Verify that pre-migration history is attached to the seeded identity, not replaced.
sql += """
INSERT INTO sessions(id,lead_id,body) VALUES
('old-call','synthetic-lead-amelia-chen','{"state":"completed","created_at":1}'),
('old-test','synthetic-old-test','{"state":"human","created_at":1,"handoff":{"status":"accepted"}}');
"""
sql += (migration / 'V2__persist_lead_queue.sql').read_text()
sql += """
DO $$ BEGIN
    ASSERT (SELECT count(*) FROM leads WHERE queued) = 5, 'seeded queue';
    ASSERT (SELECT count(*) FROM leads) = 6, 'backfilled ad-hoc history';
    ASSERT (SELECT calls_done FROM lead_activity WHERE id='synthetic-lead-amelia-chen') = 1, 'historical call';
    ASSERT (SELECT count(*) FROM lead_activity WHERE queued AND NOT ai_called) = 4, 'uncalled leads';
    ASSERT (SELECT sum(handoffs_done) FROM lead_activity WHERE queued) = 0, 'exclude ad-hoc calls';
END $$;
INSERT INTO sessions(id,lead_id,body) VALUES
('new-call','synthetic-lead-amelia-chen','{"state":"handoff_pending","created_at":2,"handoff":{"status":"awaiting_acceptance"}}');
DO $$ BEGIN
    ASSERT (SELECT calls_started FROM lead_activity WHERE id='synthetic-lead-amelia-chen') = 2, 'repeat calls';
    ASSERT (SELECT handoffs_done FROM lead_activity WHERE id='synthetic-lead-amelia-chen') = 0, 'pending is not done';
    ASSERT (SELECT handoffs_requested FROM lead_activity WHERE id='synthetic-lead-amelia-chen') = 1, 'pending is requested';
    ASSERT (SELECT latest_call_state FROM lead_activity WHERE id='synthetic-lead-amelia-chen') = 'handoff_pending', 'latest state';
END $$;
UPDATE sessions SET body = jsonb_set(jsonb_set(body,'{state}','"human"'),'{handoff,status}','"accepted"') WHERE id='new-call';
DO $$ BEGIN
    ASSERT (SELECT ai_call_done FROM sessions WHERE id='new-call'), 'stored completion';
    ASSERT (SELECT handoff_status FROM sessions WHERE id='new-call') = 'accepted', 'stored acceptance';
    ASSERT (SELECT human_handoff_done FROM lead_activity WHERE id='synthetic-lead-amelia-chen'), 'lead handoff flag';
    ASSERT (SELECT calls_done FROM lead_activity WHERE id='synthetic-lead-amelia-chen') = 2, 'two completed calls';
END $$;
-- Replayed updates must not duplicate counts.
UPDATE sessions SET body=body WHERE id='new-call';
INSERT INTO sessions(id,lead_id,body) VALUES
('unavailable-call','synthetic-lead-daniel-osei','{"state":"callback","created_at":3,"handoff":{"status":"unavailable"}}'),
('ended-call','synthetic-lead-priya-nair','{"state":"ended","created_at":4,"handoff":{"status":"cancelled"}}'),
('new-test','synthetic-new-test','{"state":"consent","created_at":5,"fields":{"name":{"value":"Test Person"}}}');
INSERT INTO suppression(lead_id,reason) VALUES ('synthetic-lead-sofia-ricci','test suppression');
DO $$ BEGIN
    ASSERT (SELECT sum(handoffs_done) FROM lead_activity WHERE queued) = 1, 'accepted only, no duplicates';
    ASSERT (SELECT sum(calls_done) FROM lead_activity WHERE queued) = 4, 'completed, accepted, callback, ended';
    ASSERT (SELECT count(*) FROM lead_activity WHERE queued AND NOT ai_called AND NOT suppressed) = 1, 'callable remaining';
    ASSERT (SELECT name FROM leads WHERE id='synthetic-new-test') = 'Test Person', 'new leads persisted';
    ASSERT (SELECT name FROM leads WHERE id='synthetic-lead-amelia-chen') = 'Amelia Chen', 'seed identity retained';
END $$;
"""
seed = (migration / 'V3__seed_fifty_demo_leads.sql').read_text()
sql += seed
sql += """
DO $$ BEGIN
    ASSERT (SELECT count(*) FROM leads WHERE queued) = 50, 'upgrade to 50 queued leads';
    ASSERT (SELECT sum(calls_done) FROM lead_activity WHERE queued) = 4, 'upgrade preserves call history';
    ASSERT (SELECT sum(handoffs_done) FROM lead_activity WHERE queued) = 1, 'upgrade preserves accepted handoffs';
    ASSERT (SELECT count(*) FROM lead_activity WHERE queued AND NOT ai_called AND NOT suppressed) = 46, '45 additional uncalled leads';
END $$;
UPDATE leads SET name='Edited Demo Name', phone='Edited phone', queued=false WHERE id='synthetic-lead-oliver-smith';
"""
sql += seed
sql += """
DO $$ BEGIN
    ASSERT (SELECT count(*) FROM leads) = 52, 'reapplying seed cannot duplicate leads';
    ASSERT (SELECT count(*) FROM leads WHERE queued) = 49, 'edited queue choice preserved';
    ASSERT (SELECT name FROM leads WHERE id='synthetic-lead-oliver-smith') = 'Edited Demo Name', 'edited name preserved';
    ASSERT (SELECT phone FROM leads WHERE id='synthetic-lead-oliver-smith') = 'Edited phone', 'edited phone preserved';
END $$;
"""
# Also apply the complete chain to an empty schema, as on a new checkout.
sql += f'CREATE SCHEMA {schema}_fresh; SET LOCAL search_path TO {schema}_fresh;\n'
for filename in ['V1__initial.sql', 'V2__persist_lead_queue.sql', 'V3__seed_fifty_demo_leads.sql']:
    sql += (migration / filename).read_text()
sql += """
DO $$ BEGIN
    ASSERT (SELECT count(*) FROM leads WHERE queued) = 50, 'fresh seed has 50 leads';
    ASSERT (SELECT count(DISTINCT phone) FROM leads) = 50, 'distinct sample phone numbers';
    ASSERT (SELECT count(*) FROM lead_activity WHERE queued AND NOT ai_called AND NOT suppressed) = 50, 'all fresh leads uncalled';
    ASSERT (SELECT sum(calls_done) FROM lead_activity WHERE queued) = 0, 'no fabricated calls';
    ASSERT (SELECT sum(handoffs_done) FROM lead_activity WHERE queued) = 0, 'no fabricated handoffs';
END $$;
ROLLBACK;
"""
subprocess.run(['docker', 'compose', 'exec', '-T', 'postgres', 'sh', '-c',
                'exec psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -v ON_ERROR_STOP=1 -q'],
               input=sql, text=True, cwd=root, check=True)
print('PASS: fresh 50-lead seed, upgrade/backfill, duplicate prevention, edited data/history preservation and call/handoff totals; fixtures rolled back.')
