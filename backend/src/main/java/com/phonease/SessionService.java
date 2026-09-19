package com.phonease;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.support.TransactionTemplate;
import java.util.*;
import java.util.function.Function;

@Service
public class SessionService {
    private final JdbcTemplate db;
    private final ObjectMapper mapper;
    private final AgentClient agent;
    private final TransactionTemplate tx;
    public SessionService(JdbcTemplate db, ObjectMapper mapper, AgentClient agent, TransactionTemplate tx) {
        this.db=db; this.mapper=mapper; this.agent=agent; this.tx=tx;
    }
    private JsonNode parse(String body) {
        try { return mapper.readTree(body); } catch (Exception e) { throw new IllegalStateException("Invalid persisted session"); }
    }
    public ObjectNode get(String id) {
        var rows=db.query("SELECT body::text FROM sessions WHERE id=?", (rs,n)->parse(rs.getString(1)), id);
        if (rows.isEmpty()) throw new NoSuchElementException("Unknown session");
        return (ObjectNode) rows.getFirst();
    }
    public boolean suppressed(String lead) {
        return Boolean.TRUE.equals(db.queryForObject("SELECT EXISTS(SELECT 1 FROM suppression WHERE lead_id=?)", Boolean.class, lead));
    }
    private JsonNode receipt(String lead) {
        var rows=db.query("SELECT body::text FROM receipts WHERE lead_id=?", (rs,n)->parse(rs.getString(1)), lead);
        return rows.isEmpty() ? null : rows.getFirst();
    }
    public void save(ObjectNode session) {
        String lead=session.path("lead_id").asText();
        if (session.path("state").asText().equals("suppressed"))
            db.update("INSERT INTO suppression(lead_id,reason) VALUES (?, 'customer opt-out') ON CONFLICT DO NOTHING",lead);
        JsonNode receipt=session.get("receipt");
        if (receipt!=null && !receipt.isNull()) {
            db.update("INSERT INTO receipts(lead_id,body) VALUES (?,?::jsonb) ON CONFLICT DO NOTHING",lead,receipt.toString());
            session.set("receipt",receipt(lead));
        }
        db.update("INSERT INTO sessions(id,lead_id,body) VALUES (?,?,?::jsonb) ON CONFLICT(id) DO UPDATE SET body=EXCLUDED.body, updated_at=now()",
            session.path("id").asText(),lead,session.toString());
    }
    private <T> T locked(java.util.function.Supplier<T> work) {
        return tx.execute(status -> {
            // Match the reference's single writer, including multiple backend instances.
            db.query("SELECT pg_advisory_xact_lock(70686)", rs -> { }, new Object[0]);
            return work.get();
        });
    }
    public ObjectNode start(ObjectNode payload) {
        return locked(()-> {
            if (!payload.has("lead_id")) payload.put("lead_id","synthetic-"+UUID.randomUUID());
            String lead=required(payload,"lead_id");
            if (suppressed(lead)) throw new IllegalArgumentException("Lead suppressed");
            ObjectNode session=decide("start",null,payload);
            save(session); return session;
        });
    }
    public ObjectNode decide(String operation, ObjectNode session, ObjectNode payload) {
        ObjectNode body=mapper.createObjectNode().put("operation",operation);
        body.set("payload",payload);
        if (session!=null) {
            body.set("session",session);
            body.put("suppressed",suppressed(session.path("lead_id").asText()));
            body.set("receipt",receipt(session.path("lead_id").asText()));
        }
        return (ObjectNode) agent.post("/decide",body);
    }
    public ObjectNode mutate(String id, Function<ObjectNode,ObjectNode> action) {
        return locked(()-> { ObjectNode result=action.apply(get(id)); save(result); return result; });
    }
    public ObjectNode action(String operation, ObjectNode payload) {
        String id=required(payload,"session_id");
        return mutate(id, s-> {
            if (operation.equals("accept") && s.hasNonNull("call_sid")) throw new IllegalArgumentException("Telephone human must accept with DTMF");
            if (operation.equals("turn")) {
                required(payload,"text",true); required(payload,"event_id");
                if (!payload.has("revision") || !payload.get("revision").isIntegralNumber()) throw new IllegalArgumentException("revision required");
            }
            return decide(operation,s,payload);
        });
    }
    public static String required(JsonNode node, String key) { return required(node,key,false); }
    private static String required(JsonNode node,String key,boolean empty) {
        JsonNode value=node.get(key);
        if (value==null || !value.isTextual() || (!empty && value.asText().isBlank())) throw new IllegalArgumentException(key+" required");
        return value.asText();
    }
}
