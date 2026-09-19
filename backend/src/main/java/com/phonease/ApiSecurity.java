package com.phonease;

import jakarta.servlet.*;
import jakarta.servlet.http.*;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.filter.OncePerRequestFilter;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;

@Component
public class ApiSecurity extends OncePerRequestFilter {
    private final byte[] expected;
    public ApiSecurity(@Value("${phonease.api-token}") String token,
        @Value("${phonease.telephony-enabled}") boolean telephony) {
        if (token.isBlank() || (telephony && token.length()<24)) throw new IllegalArgumentException("Configure PHONEASE_API_TOKEN; telephone mode requires at least 24 characters");
        expected=("Bearer "+token).getBytes(StandardCharsets.UTF_8);
    }
    @Override protected void doFilterInternal(HttpServletRequest req, HttpServletResponse res, FilterChain chain) throws ServletException,IOException {
        res.setHeader("Cache-Control","no-store"); res.setHeader("X-Content-Type-Options","nosniff");
        if (req.getRequestURI().startsWith("/api/")) {
            String token=req.getHeader("Authorization");
            if (token==null || !MessageDigest.isEqual(expected,token.getBytes(StandardCharsets.UTF_8))) {
                res.setStatus(401); res.setContentType("application/json"); res.getWriter().write("{\"error\":\"Enter the configured Phonease API token.\"}"); return;
            }
        }
        if (req.getContentLengthLong()>16384) { res.sendError(413); return; }
        chain.doFilter(req,res);
    }
}
