CREATE TABLE leads (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    phone TEXT,
    queued BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Seed identities only. Call and handoff outcomes always come from saved sessions.
INSERT INTO leads (id, name, phone, queued) VALUES
    ('synthetic-lead-amelia-chen', 'Amelia Chen', '0491 570 006', true),
    ('synthetic-lead-daniel-osei', 'Daniel Osei', '0491 570 118', true),
    ('synthetic-lead-priya-nair', 'Priya Nair', '0491 570 226', true),
    ('synthetic-lead-jack-thompson', 'Jack Thompson', '0491 570 334', true),
    ('synthetic-lead-sofia-ricci', 'Sofia Ricci', '0491 570 442', true)
ON CONFLICT (id) DO NOTHING;

-- Preserve existing ad-hoc/test history without adding it to the operator's queue.
INSERT INTO leads (id, name)
SELECT DISTINCT ON (lead_id) lead_id, COALESCE(NULLIF(body #>> '{fields,name,value}', ''), 'Unnamed lead')
FROM sessions ORDER BY lead_id, updated_at DESC, id
ON CONFLICT (id) DO NOTHING;

ALTER TABLE sessions ADD CONSTRAINT sessions_lead_fk FOREIGN KEY (lead_id) REFERENCES leads(id);
ALTER TABLE sessions
    ADD COLUMN call_state TEXT GENERATED ALWAYS AS (body->>'state') STORED,
    ADD COLUMN ai_call_done BOOLEAN GENERATED ALWAYS AS
        (COALESCE(body->>'state' IN ('completed', 'declined', 'suppressed', 'human', 'callback', 'ended'), false)) STORED,
    ADD COLUMN handoff_status TEXT GENERATED ALWAYS AS
        (COALESCE(body #>> '{handoff,status}', 'not_requested')) STORED;

-- Keep the FK and lead identity valid for every session writer, including webhooks.
CREATE FUNCTION ensure_session_lead() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    INSERT INTO leads (id, name)
    VALUES (NEW.lead_id, COALESCE(NULLIF(NEW.body #>> '{fields,name,value}', ''), 'Unnamed lead'))
    ON CONFLICT (id) DO UPDATE SET name = CASE
        WHEN leads.name = 'Unnamed lead' THEN EXCLUDED.name ELSE leads.name END;
    RETURN NEW;
END;
$$;
CREATE TRIGGER sessions_ensure_lead BEFORE INSERT OR UPDATE ON sessions
    FOR EACH ROW EXECUTE FUNCTION ensure_session_lead();

CREATE VIEW lead_activity AS
SELECT l.id, l.name, l.phone, l.queued,
       COALESCE(activity.calls_started, 0) AS calls_started,
       COALESCE(activity.calls_done, 0) AS calls_done,
       COALESCE(activity.handoffs_requested, 0) AS handoffs_requested,
       COALESCE(activity.handoffs_done, 0) AS handoffs_done,
       COALESCE(activity.calls_started, 0) > 0 AS ai_called,
       COALESCE(activity.calls_done, 0) > 0 AS ai_call_done,
       COALESCE(activity.handoffs_done, 0) > 0 AS human_handoff_done,
       latest.call_state AS latest_call_state,
       COALESCE(latest.handoff_status, 'not_requested') AS latest_handoff_status,
       EXISTS (SELECT 1 FROM suppression WHERE lead_id = l.id) AS suppressed
FROM leads l
LEFT JOIN (
    SELECT lead_id, COUNT(*) AS calls_started,
           COUNT(*) FILTER (WHERE ai_call_done) AS calls_done,
           COUNT(*) FILTER (WHERE handoff_status <> 'not_requested') AS handoffs_requested,
           COUNT(*) FILTER (WHERE handoff_status = 'accepted') AS handoffs_done
    FROM sessions GROUP BY lead_id
) activity ON activity.lead_id = l.id
LEFT JOIN LATERAL (
    SELECT call_state, handoff_status FROM sessions WHERE lead_id = l.id
    ORDER BY (body->>'created_at')::numeric DESC NULLS LAST, id DESC LIMIT 1
) latest ON true;
