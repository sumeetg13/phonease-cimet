# Verification

Verified locally on 19 September 2026 using Docker Desktop on macOS.

| Check | Result |
|---|---|
| Java 21 / Spring Boot Maven package and JUnit signature test | Passed |
| Python policy, script, telephony renderer and LangGraph tests | 64 passed |
| React production build and browser voice unit tests | Build passed; 5 tests passed |
| Public API authentication | Missing bearer token rejected |
| Full five-field journey | Consent, read-back, corrections, final review and mock receipt passed |
| Turn safety | Duplicate events are idempotent; stale revisions rejected |
| Durable policy effects | Suppression prevents another session; receipts are retrieved and reused |
| Sensitive-data boundary | Tested payment digits absent from retrieved state |
| Human handover | Context packet, unavailability, acceptance and AI freeze passed |
| Disabled telephony | Outbound request rejected; no real calls placed |
| Service recreation | Accepted handover and confirmed fields restored from PostgreSQL after backend/agent recreation |
| Live model | One paid OpenAI analysis successfully routed a human request through LangChain, LangGraph, Spring Boot and PostgreSQL |
| Browser workflow | Start, consent, human request, acceptance and terminal input disablement passed |
| Browser layout | Desktop 1440×1000 and mobile 390×844 inspected; no horizontal overflow; no browser errors observed |
| Transcript scroll | Starting a conversation retains page position while scrolling only the transcript |

Python dependencies are frozen in `agent-service/requirements.lock`; JavaScript dependencies are recorded in `frontend/package-lock.json`. Docker builds use these files. See the README for repeatable unit and HTTP smoke commands. The HTTP smoke creates synthetic sessions retained in the local database; it does not alter CIMET data.

Not verified: real microphone recognition or audible speech quality, actual Twilio calls/two-party bridging, real journey submission, external DNC systems, production load/security, and multi-user identity. The inherited prototype limitations are listed in [FEATURE_PARITY.md](FEATURE_PARITY.md). A successful model test confirms the configured key worked at test time, not a guarantee of future quota or availability.
