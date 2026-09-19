package com.phonease;

import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.client.RestClientResponseException;
import org.springframework.http.converter.HttpMessageNotReadableException;
import java.util.*;

@RestControllerAdvice
public class ApiErrors {
    @ExceptionHandler(NoSuchElementException.class)
    ResponseEntity<?> missing() { return ResponseEntity.status(404).body(Map.of("error","Unknown session")); }
    @ExceptionHandler({IllegalArgumentException.class,HttpMessageNotReadableException.class})
    ResponseEntity<?> invalid(Exception e) { return ResponseEntity.badRequest().body(Map.of("error",e instanceof IllegalArgumentException ? e.getMessage() : "Invalid JSON request")); }
    @ExceptionHandler(RestClientResponseException.class)
    ResponseEntity<?> upstream(RestClientResponseException e) {
        return ResponseEntity.status(e.getStatusCode().value()==400 ? 400 : 502).body(Map.of("error", e.getStatusCode().value()==400 ? "Invalid operation or stale revision. Refresh the session." : "Agent or telephone adapter unavailable; no automatic retry attempted."));
    }
    @ExceptionHandler(Exception.class)
    ResponseEntity<?> failure(Exception e) { return ResponseEntity.status(502).body(Map.of("error","Service unavailable. No automatic retry was attempted.")); }
}
