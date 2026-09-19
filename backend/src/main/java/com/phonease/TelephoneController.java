package com.phonease;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import jakarta.servlet.http.HttpServletRequest;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.*;
import org.springframework.stereotype.Component;
import org.springframework.util.*;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.client.RestClient;
import org.springframework.http.client.JdkClientHttpRequestFactory;
import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.time.Duration;
import java.net.http.HttpClient;
import java.net.URLEncoder;
import java.util.*;

@RestController
public class TelephoneController {
    private final SessionService sessions;
    private final AgentClient agent;
    private final ObjectMapper mapper;
    private final boolean enabled;
    private final String base,account,auth,from;
    private final Set<String> allowed;
    private final RestClient provider;
    public TelephoneController(SessionService sessions, AgentClient agent, ObjectMapper mapper,
        @Value("${phonease.telephony-enabled}") boolean enabled,
        @Value("${phonease.public-base-url}") String base,
        @Value("${phonease.twilio-account-sid}") String account,
        @Value("${phonease.twilio-auth-token}") String auth,
        @Value("${phonease.twilio-from-number}") String from,
        @Value("${phonease.test-numbers}") String numbers) {
        this.sessions=sessions; this.agent=agent; this.mapper=mapper; this.enabled=enabled;
        this.base=base.replaceAll("/+$",""); this.account=account; this.auth=auth; this.from=from;
        this.allowed=new HashSet<>(); for (String number:numbers.split(",")) if (!number.isBlank()) allowed.add(number.trim());
        var factory=new JdkClientHttpRequestFactory(HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(3)).build());
        factory.setReadTimeout(Duration.ofSeconds(8));
        provider=RestClient.builder().requestFactory(factory).baseUrl("https://api.twilio.com").build();
    }
    @PostMapping("/api/dial") public JsonNode dial(@RequestBody ObjectNode body) {
        String id=SessionService.required(body,"session_id"), number=SessionService.required(body,"number");
        if (!enabled) throw new IllegalArgumentException("Telephone calling is disabled");
        if (!base.startsWith("https://") || !account.matches("AC[a-fA-F0-9]{32}") || auth.isBlank() || from.isBlank())
            throw new IllegalArgumentException("Configure HTTPS URL and Twilio credentials");
        if (!allowed.contains(number)) throw new IllegalArgumentException("Destination must be an approved test number");
        // Commit reservation BEFORE provider I/O. Ambiguous failures cannot be redialled automatically.
        sessions.mutate(id, s->{
            if (sessions.suppressed(s.path("lead_id").asText())) throw new IllegalArgumentException("Lead suppressed");
            if (s.path("dial_attempted").asBoolean() || !s.path("state").asText().equals("consent")) throw new IllegalArgumentException("Session is not eligible for dialing");
            s.put("dial_attempted",true); return s;
        });
        MultiValueMap<String,String> fields=new LinkedMultiValueMap<>();
        fields.add("To",number); fields.add("From",from); fields.add("Record","false"); fields.add("Method","POST");
        fields.add("Url",base+"/twilio/start?sid="+URLEncoder.encode(id,StandardCharsets.UTF_8));
        JsonNode result=provider.post().uri("/2010-04-01/Accounts/"+account+"/Calls.json")
            .headers(h->h.setBasicAuth(account,auth)).contentType(MediaType.APPLICATION_FORM_URLENCODED).body(fields).retrieve().body(JsonNode.class);
        if (result==null || !result.hasNonNull("sid")) throw new IllegalStateException("Missing provider call ID");
        sessions.mutate(id,s->{s.put("call_sid",result.path("sid").asText()); return s;});
        return mapper.createObjectNode().put("call_sid",result.path("sid").asText()).put("status",result.path("status").asText());
    }
    public static boolean signatureValid(String url, MultiValueMap<String,String> params, String signature, String token) {
        if (signature==null || signature.isBlank() || token.isBlank()) return false;
        try {
            StringBuilder material=new StringBuilder(url);
            new TreeMap<>(params).forEach((key,values)->new TreeSet<>(values).forEach(value->material.append(key).append(value)));
            Mac mac=Mac.getInstance("HmacSHA1"); mac.init(new SecretKeySpec(token.getBytes(StandardCharsets.UTF_8),"HmacSHA1"));
            byte[] expected=Base64.getEncoder().encode(mac.doFinal(material.toString().getBytes(StandardCharsets.UTF_8)));
            return MessageDigest.isEqual(expected,signature.getBytes(StandardCharsets.UTF_8));
        } catch (Exception e) { return false; }
    }
    @PostMapping(value="/twilio/{route}", consumes=MediaType.APPLICATION_FORM_URLENCODED_VALUE, produces=MediaType.TEXT_XML_VALUE)
    public ResponseEntity<String> webhook(@PathVariable String route, @RequestParam String sid,
        @RequestParam(required=false) Integer revision, @RequestBody MultiValueMap<String,String> params,
        @RequestHeader(value="X-Twilio-Signature",required=false) String signature, HttpServletRequest request) {
        String canonical=base+request.getRequestURI()+(request.getQueryString()==null ? "" : "?"+request.getQueryString());
        if (!enabled || !signatureValid(canonical,params,signature,auth)) return ResponseEntity.status(403).body("<Response><Hangup/></Response>");
        if (!Set.of("start","turn","whisper","accept","unavailable","dial-result").contains(route)) return ResponseEntity.notFound().build();
        ObjectNode result=sessions.mutate(sid,s->{
            String call=params.getFirst("CallSid");
            boolean child=route.equals("whisper") || route.equals("accept");
            if (call==null || (!child && !call.equals(s.path("call_sid").asText()))) throw new IllegalArgumentException("Call SID mismatch");
            if (route.equals("whisper")) {
                String parent=params.getFirst("ParentCallSid");
                if (parent!=null && !parent.equals(s.path("call_sid").asText())) throw new IllegalArgumentException("Parent call mismatch");
                if (s.path("state").asText().equals("handoff_pending")) s.put("human_leg_sid",call);
            }
            if (route.equals("accept") && !call.equals(s.path("human_leg_sid").asText())) throw new IllegalArgumentException("Human leg mismatch");
            ObjectNode payload=mapper.createObjectNode();
            switch(route) {
                case "start":
                    if (sessions.suppressed(s.path("lead_id").asText())) return sessions.decide("close",s,payload);
                    break;
                case "turn":
                    if (revision!=null && revision==s.path("revision").asInt()) {
                        payload.put("text",Objects.requireNonNullElse(params.getFirst("SpeechResult"),""));
                        payload.put("event_id","twilio-turn-"+revision).put("revision",revision);
                        String confidence=params.getFirst("Confidence");
                        if (confidence!=null && !confidence.isBlank()) payload.put("confidence",Double.parseDouble(confidence));
                        return sessions.decide("turn",s,payload);
                    }
                    break;
                case "accept":
                    if ("1".equals(params.getFirst("Digits")) && s.path("state").asText().equals("handoff_pending"))
                        return sessions.decide("accept",s,payload.put("agent","telephone-specialist"));
                    break;
                case "unavailable": case "dial-result":
                    if (s.path("state").asText().equals("handoff_pending")) return sessions.decide("unavailable",s,payload);
                    break;
                default: break;
            }
            return s;
        });
        if (route.equals("accept")) return ResponseEntity.ok(result.path("state").asText().equals("human") ? "<Response/>" : "<Response><Hangup/></Response>");
        if (route.equals("dial-result") && result.path("state").asText().equals("human")) return ResponseEntity.ok("<Response><Hangup/></Response>");
        if (route.equals("whisper") && !result.path("state").asText().equals("handoff_pending")) return ResponseEntity.ok("<Response><Hangup/></Response>");
        ObjectNode render=mapper.createObjectNode().put("whisper",route.equals("whisper")); render.set("session",result);
        return ResponseEntity.ok(agent.post("/twiml",render).path("xml").asText());
    }
}
