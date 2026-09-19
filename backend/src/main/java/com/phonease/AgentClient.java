package com.phonease;

import com.fasterxml.jackson.databind.JsonNode;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.client.JdkClientHttpRequestFactory;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClient;
import java.net.http.HttpClient;
import java.time.Duration;

@Component
public class AgentClient {
    private final RestClient client;
    public AgentClient(@Value("${phonease.agent-url}") String url, @Value("${phonease.agent-token}") String token) {
        var factory = new JdkClientHttpRequestFactory(HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(3)).build());
        factory.setReadTimeout(Duration.ofSeconds(15));
        client = RestClient.builder().baseUrl(url).requestFactory(factory).defaultHeader("Authorization", "Bearer " + token).build();
    }
    public JsonNode scripts() { return client.get().uri("/scripts").retrieve().body(JsonNode.class); }
    public JsonNode post(String path, Object body) {
        return client.post().uri(path).body(body).retrieve().body(JsonNode.class);
    }
}
