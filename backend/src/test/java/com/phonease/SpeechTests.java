package com.phonease;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import java.util.NoSuchElementException;
import static org.mockito.Mockito.*;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.*;

class SpeechTests {
    SessionService sessions;
    AgentClient agent;
    MockMvc mvc;
    ObjectNode session;
    @BeforeEach void setup() {
        sessions=mock(SessionService.class); agent=mock(AgentClient.class);
        session=new ObjectMapper().createObjectNode().put("id","test").put("revision",2)
            .put("state","collecting").put("message","Persisted assistant reply");
        when(sessions.get("test")).thenReturn(session);
        mvc=MockMvcBuilders.standaloneSetup(new SpeechController(sessions,agent))
            .setControllerAdvice(new ApiErrors()).addFilters(new ApiSecurity("test-token",false)).build();
    }
    @Test void requiresAuthentication() throws Exception {
        mvc.perform(post("/api/speech").contentType("application/json").content("{}"))
            .andExpect(status().isUnauthorized());
        verifyNoInteractions(sessions,agent);
    }
    @Test void usesPersistedReplyNotUserTextAndReturnsBinary() throws Exception {
        byte[] bytes={73,68,51}; when(agent.speech("Persisted assistant reply")).thenReturn(bytes);
        mvc.perform(post("/api/speech").header("Authorization","Bearer test-token")
            .contentType("application/json").content("{\"session_id\":\"test\",\"revision\":2,\"text\":\"Untrusted prompt\"}"))
            .andExpect(status().isOk()).andExpect(content().contentType("audio/mpeg"))
            .andExpect(content().bytes(bytes)).andExpect(header().string("Cache-Control","no-store"));
        verify(agent).speech("Persisted assistant reply"); verifyNoMoreInteractions(agent);
    }
    @Test void rejectsStaleRevision() throws Exception { reject("{\"session_id\":\"test\",\"revision\":1}",400); }
    @Test void requiresIntegerRevision() throws Exception {
        reject("{\"session_id\":\"test\"}",400);
        reject("{\"session_id\":\"test\",\"revision\":2.5}",400);
    }
    @Test void rejectsAfterHumanAcceptance() throws Exception {
        session.put("state","human"); reject("{\"session_id\":\"test\",\"revision\":2}",400);
    }
    @Test void requiresExistingSession() throws Exception {
        when(sessions.get("test")).thenThrow(new NoSuchElementException());
        reject("{\"session_id\":\"test\",\"revision\":2}",404);
    }
    @Test void rejectsOverlongReplyBeforePaidCall() throws Exception {
        session.put("message","x".repeat(4097)); reject("{\"session_id\":\"test\",\"revision\":2}",400);
    }
    private void reject(String body,int status) throws Exception {
        mvc.perform(post("/api/speech").header("Authorization","Bearer test-token")
            .contentType("application/json").content(body)).andExpect(status().is(status));
        verifyNoInteractions(agent);
    }
}
