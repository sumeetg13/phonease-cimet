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

## Neural voice upgrade — 19 September 2026

- Reviewed and preserved the existing `energy-demo-v3` wording variants, script registry/exporter/tests, Polly Neural telephone adapter, and energy-plan-comparison data-flow document.
- All 76 Python tests and 16 browser voice tests passed. The Spring Boot build and eight Java tests passed; React production build passed.
- Live authenticated TTS smoke returned a valid 185,856-byte MP3; missing authentication and stale revision requests were rejected.
- Chrome decoded and played an 11.352-second OpenAI neural reply. Replay produced a second playback with the synthesis request count still at one. Disabling spoken replies paused playback and removed the audio source.
- The browser check exposed a native API receiver-binding error; fixed and covered by a regression test. The repeated browser run reported no errors.
- Offline device-voice selection worked without another neural request. Mobile 390×844 layout had no horizontal overflow, and the current v3 script remained visible.
- Full deterministic HTTP/PostgreSQL smoke passed again after the upgrade. The configured OpenAI service was restored afterwards.
- Compose now preserves an explicitly empty `TWILIO_VOICE`, matching its documented fallback behavior. Your private `.env` was not changed.

These checks establish transport, decoding and playback behavior, not subjective naturalness. Live telephone audio and real microphone input remain unverified. See [VOICE.md](VOICE.md) for configuration, charges, cancellation limitations and the repeatable TTS smoke test.

## Hands-free call mode — 19 September 2026

- The browser conversation now runs as a call: the assistant speaks, the microphone reopens on its own, interim speech is captioned live in the transcript, and a turn is sent after ~1.2 s of silence. Typing a caller reply and the existing single-turn Speak / interrupt input are unchanged and still work during a call.
- New `frontend/src/call.js` holds the turn-taking; both voice engines gained an `onDone` callback so the line is handed back only when a reply finishes, never when it is interrupted.
- 28 browser tests passed (10 new call tests, plus turn-handback coverage for the neural and device engines) and the React production build passed inside the image build.
- Verified by unit test, not by microphone: real recognition accuracy, audible barge-in behavior and speech-service latency remain unverified, as does telephone audio. The line is half-duplex by design — the microphone is closed while a reply plays, so the assistant cannot hear itself.
- No Python, Java or database code was changed for call mode. A failing Python run observed during this work came from a stale `agent` image, not from the source; after `docker compose build agent` the full suite passes.

## Call notes, submission consent and the call receipt — 19 September 2026

- The assistant now asks "Should we submit these details for further processing?" at review; nothing is submitted before the caller agrees, and declining or changing a field still works.
- The agent service writes live call notes (opening, carried-over answers, consent, each confirmed or corrected answer, what the caller raised, handover, outcome). A topic is noted once and never quotes the caller, so pre-consent notes hold no caller speech.
- Every ended call produces a `summary` — outcome, details in script order, notes and the full two-sided transcript — and the submitted receipt carries a copy of the transcript and notes. The receipt is the snapshot at submission; the closing line and the outcome note follow it in the session record.
- 98 Python tests (9 new) and 34 browser tests (6 new) passed; Java build/tests and the React production build passed inside the image builds.
- `scripts/smoke.py` was stale for the v4 script (5 fields, no name question) and now walks the current journey and asserts the notes, the record and the receipt transcript survive PostgreSQL. The full offline smoke passed; a receipt row in PostgreSQL held 43 transcript lines and 12 notes.
- Chrome check with the deterministic agent: the receipt panel showed outcome, receipt ID, adapter, consent, ten details in script order with spoken labels, 14 notes and 46 transcript lines, with no console errors. The live notes console renders the same notes during a call.
- The agent's configured OpenAI key returned one transient failure during manual checks, which correctly handed the call to a human (`model_unavailable`). The configured service was restored afterwards; your `.env` was not changed.
- Not verified: subjective note quality, notes from a real microphone conversation, and telephone audio. Notes are rule-derived from the script and signals, not model-generated summaries.
