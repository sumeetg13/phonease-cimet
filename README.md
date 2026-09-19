# Phonease

Energy recovery conversation workspace, rebuilt from the CIMET reference using **Java Spring Boot, PostgreSQL, Python LangChain/LangGraph and React**. This is a separate project; it does not import or run files from CIMET.

## Run

Install and start Docker Desktop. Python 3.9+ is used by the local configuration helper; all application runtimes and dependencies run inside containers.

```sh
python3 scripts/setup.py
# Set OPENAI_API_KEY in the new .env to enable model analysis.
./scripts/run.sh
```

Open http://127.0.0.1:5173. The local operator token defaults to `local-demo`; enter the value of `PHONEASE_API_TOKEN` if you change it. Set `UI_PORT` in `.env` to use a different port. `./scripts/run.sh --no-open` starts without opening the browser. It rebuilds changed services and leaves them running in the background.

```sh
./scripts/stop.sh                 # Stops services; retains PostgreSQL data
docker compose logs -f backend agent
```

The setup helper never overwrites an existing `.env`. For an explicitly chosen existing key, `python3 scripts/setup.py --reference-env /path/to/existing/.env` copies only `OPENAI_API_KEY` into a new private configuration. All other secrets are generated independently. `.env` is ignored by Git and excluded from image build contexts. OpenAI credentials are given only to the Python service.

After changing configuration, rerun the launcher. No model key means local rules; a configured but failed model triggers handover. No telephone call occurs on startup.

## Use the workspace

1. Choose a saved journey snapshot and start a recovery call. By default postcode and energy type are already confirmed.
2. Answer `yes` to consent, then `rent`, `no`, `no`, confirming each read-back with `yes`.
3. Review the completed fields and say `yes` to submit to the local mock.
4. Try the scenario controls for human requests, privacy, payment, confusion, distress, frustration and other signals. Inspect the packet and simulate human acceptance or unavailability.
5. Use **Start call** for a hands-free conversation: the assistant speaks, the microphone reopens by itself, speech is transcribed live and each turn is sent after a pause. **Text only** and the reply box work without a microphone. Use Speak / interrupt for single-turn speech input or to interrupt the assistant mid-reply. Notes are written live beside the transcript; at the end the assistant asks whether to submit the details for further processing, and the call receipt with the full transcript, notes and a text download appears once the call ends. Replies default to OpenAI neural TTS; use the Reply voice selector for the offline device voice. Both support interruption.
6. The session ID shown in the trace can restore a persisted session. Refresh retrieves updates made by telephone webhooks.

## Services

| Service | Role |
|---|---|
| React + Vite, served by Nginx | Operator UI, browser voice and same-origin API proxy |
| Spring Boot / Java 21 | Public API, bearer authentication, PostgreSQL transactions, outbound Twilio calls and signed callbacks |
| Python 3.12 / FastAPI | Internal authenticated decision API |
| LangGraph | Hydrates supplied context and runs the conversation supervisor for each operation |
| LangChain OpenAI connector | Schema-constrained field proposals, sentiment and evidence-backed intent signals |
| PostgreSQL 17 + Flyway | Durable sessions, opt-out suppression and idempotent mock receipts |

Only the UI port is published, bound to localhost. PostgreSQL, the agent service and Spring Boot are reachable inside the Compose network. Nginx forwards `/api/`, `/health`, and `/twilio/` to Spring Boot.

## Tests

See [Neural voice configuration](docs/VOICE.md) for speech settings, playback behavior and the paid TTS smoke test.

```sh
./scripts/test.sh
# Deterministic HTTP/PostgreSQL integration test (running stack required):
OPENAI_API_KEY= docker compose up -d --wait agent
python3 scripts/smoke.py
# Restore configured model and make one small paid analysis call:
docker compose up -d --wait agent
python3 scripts/smoke.py --live
```

The Python suite covers inherited conversation policies, wording variants, telephone prompts, graph transport/authentication and neural speech. PostgreSQL durability is covered by the HTTP smoke script. Java tests cover webhook signatures and the authenticated speech endpoint. The frontend tests the call record formatting, call turn-taking, neural playback/cancellation/replay and the offline voice engine, and runs a production build. The live model test confirms the complete HTTP → graph → model → PostgreSQL handover path; `python3 scripts/smoke_tts.py` independently checks real neural speech.

## Telephone configuration

Configure `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_FROM_NUMBER`, an HTTPS `PUBLIC_BASE_URL` forwarding to the UI port, and comma-separated approved `TEST_NUMBERS`. Set `HUMAN_TEST_NUMBER` to a number in that allowlist. Use a random `PHONEASE_API_TOKEN` of at least 24 characters, then set `TELEPHONY_ENABLED=true` and restart.

Create a session in the consent stage and use the Telephone test call panel to dial an approved destination. A confirmation precedes the real call. The API reserves each dial attempt before contacting Twilio; ambiguous provider failures require manual reconciliation. Twilio uses speech Gather/Say, private briefing and press-1 acceptance before bridging. Live telephone provider calls require configured numbers and have not been verified by automated tests.

Set `TWILIO_VOICE` to select the Twilio `<Say>` voice (default `Polly.Olivia-Neural`, an Australian English neural voice); leave it empty to fall back to Twilio's standard voice. This setting affects telephone prompts and specialist whispers. Browser replies independently default to OpenAI `gpt-4o-mini-tts` with the `marin` voice; the previous browser/OS voice remains selectable as an offline option.

## Documentation

- [Technology stack](docs/TECH_STACK.md)
- [Architecture and API](docs/ARCHITECTURE.md)
- [Feature parity and limitations](docs/FEATURE_PARITY.md)
- [Verification results](docs/VERIFICATION.md)
- [Shared Energy script book](docs/ENERGY_SCRIPTS.md)

This retains the reference's synthetic prototype scope: assumed Energy fields, a local mock receipt, stub external DNC lookup and browser handover simulation. It does not purchase/switch plans, book callbacks, record audio, implement ViciDial, or provide continuous full-duplex telephone audio. Text sentiment is not an acoustic emotion model. PostgreSQL uses one advisory transaction lock to preserve the reference's serialized policy behavior; production concurrency and operator identity require further design.
