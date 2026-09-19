package com.phonease;

import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import java.util.List;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.Mockito.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

class DashboardTests {
    @Test void emptyDatabaseDoesNotInventDemoLeads() {
        var result = DashboardController.summarize(List.of());
        assertEquals(0, result.totalLeads());
        assertEquals(0, result.remainingToCall());
        assertEquals(0, result.aiCallsDone());
        assertEquals(0, result.humanHandoffs());
    }

    @Test void countsPeopleOnceAndOnlyAcceptedHandoffsAsDone() {
        var result = DashboardController.summarize(List.of(
            lead("repeat", 3, 2, 2, 1, false),
            lead("pending", 1, 0, 1, 0, false),
            lead("uncalled", 0, 0, 0, 0, false),
            lead("suppressed", 0, 0, 0, 0, true)
        ));
        assertEquals(4, result.totalLeads());
        assertEquals(1, result.remainingToCall());
        assertEquals(2, result.aiCallsDone());
        assertEquals(1, result.humanHandoffs());
    }

    private DashboardController.Lead lead(String id, long started, long done, long requested, long accepted, boolean suppressed) {
        return new DashboardController.Lead(id, id, null, started, done, requested, accepted,
            started > 0, done > 0, accepted > 0, null, "not_requested", suppressed);
    }

    @Test void endpointRequiresAuthenticationAndReturnsDatabaseMetrics() throws Exception {
        var db = mock(JdbcTemplate.class);
        var mvc = MockMvcBuilders.standaloneSetup(new DashboardController(db))
            .addFilters(new ApiSecurity("test-token", false)).build();
        mvc.perform(get("/api/dashboard")).andExpect(status().isUnauthorized());
        verifyNoInteractions(db);
        mvc.perform(get("/api/dashboard").header("Authorization", "Bearer test-token"))
            .andExpect(status().isOk()).andExpect(jsonPath("$.totalLeads").value(0))
            .andExpect(jsonPath("$.remainingToCall").value(0))
            .andExpect(jsonPath("$.leads.length()").value(0));
    }
}
