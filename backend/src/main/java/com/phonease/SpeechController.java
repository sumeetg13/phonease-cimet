package com.phonease;

import com.fasterxml.jackson.databind.node.ObjectNode;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@RestController
public class SpeechController {
    private final SessionService sessions;
    private final AgentClient agent;
    public SpeechController(SessionService sessions, AgentClient agent) {
        this.sessions=sessions; this.agent=agent;
    }
    @PostMapping("/api/speech")
    public ResponseEntity<byte[]> speech(@RequestBody ObjectNode payload) {
        String id=SessionService.required(payload,"session_id");
        if (!payload.has("revision") || !payload.get("revision").isIntegralNumber())
            throw new IllegalArgumentException("revision required");
        ObjectNode session=sessions.get(id);
        if (!payload.get("revision").equals(session.get("revision")))
            throw new IllegalArgumentException("Stale speech request. Refresh the session.");
        if (session.path("state").asText().equals("human"))
            throw new IllegalArgumentException("AI speech is disabled after human acceptance");
        // Never trust a browser-provided prompt: only read the persisted assistant reply.
        String text=session.path("message").asText();
        if (text.isBlank() || text.length()>4096) throw new IllegalArgumentException("Invalid speech length");
        byte[] audio=agent.speech(text);
        if (audio==null || audio.length==0) throw new IllegalStateException("Missing audio");
        return ResponseEntity.ok().contentType(MediaType.parseMediaType("audio/mpeg"))
            .header("Cache-Control","no-store").body(audio);
    }
}
