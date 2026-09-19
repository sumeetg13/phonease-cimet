## What's already there as part of START FROM WHERE WE LEFT:
- After every single turn, SessionService.save() writes the full session (collected fields, current stage, revision counter, event log, signals) to Postgres — not just at hangup (backend/src/main/java/com/phonease/SessionService.java:36-47).
- The script logic explicitly supports resuming mid-flow: if a new call starts and some fields are already confirmed, it skips straight to what's missing and says a dedicated resume line — "We'll keep the details you already confirmed and ask only what's missing." (agent-service/phonease/core.py:139, scripts.json:226).
- A new Twilio call can be pointed at the same sid (/twilio/start?sid=...), and it will rehydrate that exact session from the DB and continue — the turn-by-turn revision check even guards against stale/duplicate submissions.


## Database used : Postgres

Postgres is running in Docker (phonease-postgres-1, image postgres:17-alpine) and is currently healthy with real data in it. Here's what's stored:

Schema — one Flyway migration (backend/src/main/resources/db/migration/V1__initial.sql), no ORM (raw JdbcTemplate + Jackson JsonNode), three tables:

┌─────────────┬──────────────────────────────────────────────────────────────────┬─────────────────────────────────────────────┐
│    Table    │                             Columns                              │                   Purpose                   │
├─────────────┼──────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────┤
│ sessions    │ id (PK, text), lead_id (text, indexed), body (jsonb), updated_at │ Full conversation/call state as a JSON blob │
├─────────────┼──────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────┤
│ suppression │ lead_id (PK), reason, created_at                                 │ Do-not-contact list (opt-outs)              │
├─────────────┼──────────────────────────────────────────────────────────────────┼─────────────────────────────────────────────┤
│ receipts    │ lead_id (PK), body (jsonb), created_at                           │ Final submitted lead payload per adapter    │
└─────────────┴──────────────────────────────────────────────────────────────────┴─────────────────────────────────────────────┘

Current row counts: 22 sessions, 2 suppressions, 2 receipts.

sessions.body format — a JSON document with top-level keys: id, mode, seen, turn, state, events, fields, consent, handoff, lead_id, message, pending, receipt, signals, analysis, failures, revision, created_at, anger_count, active_script, script_version, sections_introduced. This is the entire agent conversation state (script progress, collected fields, event log, embedded receipt) serialized straight into jsonb — sizes run up to ~3.6KB per session.

receipts.body format — e.g.:
{
  "id": "mock-f36fcd58cef0",
  "adapter": "local-mock",
  "payload": {
    "fields": {"fuel": "electricity", "solar": false, "moving": false, "postcode": "3000", "occupancy": "rent"},
    "consent": true,
    "lead_id": "synthetic-...",
    "vertical": "energy",
    "schema_version": "energy-demo-v2"
  }
}

Read/write pattern (SessionService.java): sessions/receipts are read back as raw JSON text and re-parsed, not mapped to Java classes. Writes use INSERT ... ON CONFLICT upserts, and every mutation is wrapped in a Postgres advisory lock (pg_advisory_xact_lock(70686)) to serialize writes across backend instances — there's no per-row locking, just one global lock. Suppression rows are inserted automatically whenever a session's state becomes "suppressed", and receipts are inserted once and then treated as immutable (ON CONFLICT DO NOTHING).
