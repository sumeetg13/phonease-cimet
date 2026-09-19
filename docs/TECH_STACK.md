# Phonease technology stack

| Layer | Implementation |
|---|---|
| Public backend | Java 21, Spring Boot 3.5.6, Spring Web MVC, JDBC, RestClient |
| Database | PostgreSQL 17; JSONB session/receipt bodies; Flyway schema migration |
| Agent service | Python 3.12, FastAPI, Uvicorn, LangGraph StateGraph |
| Model connector | LangChain `langchain-openai` / ChatOpenAI, strict JSON Schema output |
| Default model | `gpt-4.1-mini-2025-04-14`; configured only in the Python service |
| User interface | React 19, JavaScript, CSS, Lucide icons, Vite 7 |
| Browser voice | OpenAI neural TTS (`gpt-4o-mini-tts`, `marin`), Web Speech recognition; optional device speech synthesis |
| Reverse proxy | Nginx, same-origin UI/API routing |
| Telephony | Twilio Voice REST API, TwiML with Polly Neural, HMAC-SHA1 webhooks |
| Packaging | Docker multi-stage builds, Docker Compose |
| Tests | Python unittest/FastAPI TestClient, JUnit 5, Node built-in tests, HTTP smoke checks |
| Local scripts | Bash and Python 3.9+ |

The Java backend owns durable state and public integrations. Python runs the conversation graph and connectors. React is a complete replacement for the reference's imperative browser UI. PostgreSQL replaces SQLite; no runtime dependency on CIMET remains.

The tested Python dependency set is pinned in `agent-service/requirements.lock`; npm dependencies are locked in `frontend/package-lock.json`. Maven versions are managed by the Spring Boot parent in `backend/pom.xml`.

Sources consulted for implementation: [Spring Boot requirements](https://docs.spring.io/spring-boot/3.5/system-requirements.html), [LangGraph graph API](https://docs.langchain.com/oss/python/langgraph/graph-api), [LangChain ChatOpenAI](https://docs.langchain.com/oss/python/integrations/chat/openai).
