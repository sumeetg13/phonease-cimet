package com.phonease;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.*;
import java.util.Map;

@RestController
public class ApiController {
    private final SessionService sessions;
    private final AgentClient agent;
    private final JdbcTemplate db;
    public ApiController(SessionService sessions, AgentClient agent, JdbcTemplate db) { this.sessions=sessions; this.agent=agent; this.db=db; }
    @GetMapping("/health") public Map<String,String> health() { db.queryForObject("SELECT 1",Integer.class); agent.scripts(); return Map.of("status","ok","scope","synthetic-prototype"); }
    @GetMapping("/api/scripts") public JsonNode scripts() { return agent.scripts(); }
    @PostMapping("/api/sessions") @ResponseStatus(org.springframework.http.HttpStatus.CREATED)
    public ObjectNode start(@RequestBody ObjectNode payload) { return sessions.start(payload); }
    @GetMapping("/api/sessions/{id}") public ObjectNode get(@PathVariable String id) { return sessions.get(id); }
    @PostMapping("/api/turn") public ObjectNode turn(@RequestBody ObjectNode payload) { return sessions.action("turn",payload); }
    @PostMapping("/api/accept") public ObjectNode accept(@RequestBody ObjectNode payload) { return sessions.action("accept",payload); }
    @PostMapping("/api/unavailable") public ObjectNode unavailable(@RequestBody ObjectNode payload) { return sessions.action("unavailable",payload); }
    @PostMapping("/api/end") public ObjectNode end(@RequestBody ObjectNode payload) { return sessions.action("end",payload); }
}
