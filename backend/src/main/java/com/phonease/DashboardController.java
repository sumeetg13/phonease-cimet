package com.phonease;

import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;
import java.util.List;

@RestController
public class DashboardController {
    record Lead(String id, String name, String phone, long callsStarted, long callsDone,
                long handoffsRequested, long handoffsDone, boolean aiCalled, boolean aiCallDone,
                boolean humanHandoffDone, String latestCallState, String latestHandoffStatus, boolean suppressed) {}
    record Dashboard(int totalLeads, long aiCallsDone, long remainingToCall, long humanHandoffs, List<Lead> leads) {}
    private final JdbcTemplate db;

    public DashboardController(JdbcTemplate db) { this.db = db; }

    @GetMapping("/api/dashboard")
    public Dashboard get() {
        // One snapshot supplies both the queue and its totals. PostgreSQL owns all statuses.
        return summarize(db.query("SELECT * FROM lead_activity WHERE queued ORDER BY name, id", (rs, row) -> new Lead(
            rs.getString("id"), rs.getString("name"), rs.getString("phone"),
            rs.getLong("calls_started"), rs.getLong("calls_done"), rs.getLong("handoffs_requested"), rs.getLong("handoffs_done"),
            rs.getBoolean("ai_called"), rs.getBoolean("ai_call_done"), rs.getBoolean("human_handoff_done"),
            rs.getString("latest_call_state"), rs.getString("latest_handoff_status"), rs.getBoolean("suppressed"))));
    }

    static Dashboard summarize(List<Lead> leads) {
        return new Dashboard(leads.size(), leads.stream().mapToLong(Lead::callsDone).sum(),
            leads.stream().filter(lead -> !lead.aiCalled() && !lead.suppressed()).count(),
            leads.stream().mapToLong(Lead::handoffsDone).sum(), leads);
    }
}
