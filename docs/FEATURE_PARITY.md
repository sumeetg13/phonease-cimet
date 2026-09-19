# Reference feature parity

| CIMET feature | Phonease implementation |
|---|---|
| Synthetic journey start and saved snapshots | Spring API + React snapshot selector |
| Consent gate and pre-consent local rules | Copied and adapted supervisor policy |
| Five Energy fields and shared scripts | Versioned JSON registry |
| Validation, aliases and spoken digits | Reference parsers and tests |
| Pending values, read-back, confirmation and corrections | Reference state machine through LangGraph |
| Final review and local mock receipt | Policy plus PostgreSQL receipt deduplication by lead |
| Resume confirmed fields and script version guard | Session state persisted as JSONB |
| 15-category signals and contextual sentiment | Reference rules + LangChain structured model analysis |
| Model failure triggers handover | Preserved fail-closed behavior |
| Payment text withholding | Preserved before persistence and known-rule model calls |
| DNC, refusal, busy, repair budgets and frustration window | Preserved policy with PostgreSQL suppression |
| Human packet, acceptance, unavailable and AI freeze | API + React handover panel |
| Duplicate event/stale revision protection | Supervisor within serialized database transaction |
| Browser speech, interruption and relaxed pacing | React controls + preserved voice engine |
| Operator script guidance, trace and scenarios | React console |
| Twilio dial allowlist and reservation | Spring outbound integration with committed reservation |
| Signed Twilio callbacks and call identity checks | Spring controller |
| TwiML Gather/Say, whisper, DTMF acceptance and bridging | Python renderer + Spring callbacks |
| Environment configuration and one-command launcher | Private Phonease .env + Compose scripts |
| Automated tests and generated script book | Preserved/adapted tests and exporter |

The same scope limitations apply: official Energy schema and recording were not supplied; external DNC is a stub, journey submission is local mock, browser acceptance is a simulation, and follow-up is not a booked callback. ViciDial, real CIMET submission, acoustic emotion analysis and continuous full-duplex streaming remain unimplemented. Telephone adapter behavior is covered by tests; live two-party audio needs approved Twilio credentials and numbers.

Phonease adds session restore, a telephone test confirmation panel, database migrations, service authentication and container packaging. The complete original application and its data remain in the separate CIMET folder.
