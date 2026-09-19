CREATE TABLE sessions (
    id TEXT PRIMARY KEY,
    lead_id TEXT NOT NULL,
    body JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX sessions_lead_idx ON sessions(lead_id);
CREATE TABLE suppression (lead_id TEXT PRIMARY KEY, reason TEXT NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now());
CREATE TABLE receipts (lead_id TEXT PRIMARY KEY, body JSONB NOT NULL, created_at TIMESTAMPTZ NOT NULL DEFAULT now());
