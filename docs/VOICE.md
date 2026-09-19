# Neural voice

Phonease uses two independent speech engines:

| Path | Default | Configuration |
|---|---|---|
| Browser assistant replies | OpenAI `gpt-4o-mini-tts`, `marin` voice | `OPENAI_API_KEY`, `OPENAI_TTS_MODEL`, `OPENAI_TTS_VOICE` |
| Twilio caller prompts and specialist whispers | Amazon Polly Neural Australian English | `TWILIO_VOICE=Polly.Olivia-Neural` |
| Optional offline browser replies | Existing browser/OS speech synthesis | Choose **Device voice (offline)** in the UI |

Defaults apply even when the new variables are absent from an existing `.env`; the existing key is not changed. To customize, add the settings to Phonease's private `.env` and rerun `./scripts/run.sh`. The conversation-analysis `OPENAI_MODEL` is independent of the TTS model. Use a TTS model supporting the `instructions` parameter; the implementation supplies natural pacing and Australian English delivery guidance. The accent is requested, not guaranteed.

## Call mode

**Start call** runs the browser conversation hands-free, like a telephone call: the assistant speaks its reply, the microphone reopens by itself, the caller's words are transcribed live under the transcript, and the turn is sent automatically after a short pause in speech. The call status line shows whose turn it is (connecting, assistant speaking, listening, thinking). **Hang up** ends it; **Start call** again begins a new session.

One microphone stream stays open across pauses (`continuous`, `interimResults`) and is reopened when the browser closes an idle stream, so a pause is not mistaken for the end of a call. Words are only sent once ~1.2 seconds pass with no new speech, so a sentence resumed after a pause is one turn, not two. The line is half-duplex: the microphone is closed while a reply plays, which prevents the assistant from hearing itself. **Interrupt & speak** cancels the reply and reopens the microphone immediately; the recognized confidence is passed to the turn API exactly as with the existing push-to-talk input.

**Text only** starts the same session without the microphone, and typing a caller reply works at any time, including during a call — this is the demo path when no microphone, no permission, or no speech recognition support is available. If the browser has no speech recognition, the call is not opened and the UI says so instead of appearing to listen.

A turn arriving while another is in flight, a browser that denies microphone permission, a terminal conversation state, and a failed or blocked reply all hand the line back or end the call rather than leaving the microphone closed and the call stalled. Speech recognition uses the browser's own service (Chrome sends audio to Google); Phonease neither receives nor records caller audio, and only the recognized text is sent to the API. Interim captions are never persisted — only the sent turn is.

## Call notes and the end-of-call receipt

The agent service writes **live call notes** as the conversation happens, and the UI streams them beside the transcript: the call opening, any answers carried over from the earlier journey, consent, every answer the caller confirms or corrects, anything the caller raises (hardship, a privacy question, a request for a person, a bad line), a handover, and the outcome. A topic is noted once, in the service's own words — a note never quotes the caller, so notes taken before consent contain no caller speech.

At the end the assistant reads the collected answers back and asks **"Should we submit these details for further processing?"** Nothing is submitted before the caller says yes: they can also say *change* followed by a field name, or decline. Answering yes writes the receipt.

When the call ends in any state, a **call receipt** panel appears with the outcome, the receipt ID and adapter (or a plain statement that nothing was submitted), the confirmed details in script order, the call notes, and the full transcript of both sides. **Download call record** and **Copy as text** produce the same record as plain text. The transcript and notes are stored with the session in PostgreSQL, and a copy of both travels inside the submitted receipt — the receipt is the snapshot taken at submission, so the closing line and the outcome note follow it in the session's own record.

Only text is kept. Caller audio is never recorded or stored by Phonease, payment utterances are withheld from the transcript before it is persisted, and a call without consent produces a receipt that says nothing was stored.

## Browser behavior

The UI sends only a session ID and revision to authenticated `POST /api/speech`. Spring Boot selects the current persisted assistant message and rejects stale requests or requests after human acceptance. The authenticated internal Python `/speech` endpoint synthesizes an MP3 through OpenAI. The API key stays in the Python service, never in browser code. No transcript, caller audio, or model-generated tool instructions are sent by the browser to the synthesis endpoint.

Speech is AI-generated, not a human voice, and is disclosed in the UI. Assistant reply text is sent to OpenAI, including confirmed details repeated in a reply; use synthetic data. The pre-consent opening can be synthesized, but the conversation-analysis consent policy is unchanged.

**Speak / interrupt**, disabling spoken replies, switching engines, starting/restoring/refreshing a session, submitting a turn, and accepting a handover cancel audio and invalidate late responses. **Replay reply** reuses the most recently generated audio while it is still retained, including when browser autoplay requires a direct click. Switching or cancelling releases that audio; a later replay then generates a new paid request. Browser cancellation cannot guarantee cancellation of an already-started provider request or its charges.

Provider errors are visible; the UI does not silently switch to a different voice. Text continues to work, and the operator can explicitly choose the device voice. Provider retries are disabled. Audio is returned with `Cache-Control: no-store`, kept only in browser memory for the current reply, and not written to PostgreSQL or an audio directory. One full reply is generated before playback; this is not streaming or a full-duplex voice agent.

## Telephone behavior

The existing Polly Neural implementation is preserved for every `<Say>`, including handover, terminal messages and specialist whispers. `TWILIO_VOICE` is passed through Compose; an explicitly empty value now correctly omits the voice attribute (Twilio account defaults apply). Keep the selected voice compatible with the current `en-AU` language. This uses Twilio's Polly integration, not separate AWS credentials. No OpenAI speech request is needed for telephone playback.

The existing Twilio configuration, allowlist, signed callbacks and explicit human acceptance remain unchanged. Neural TTS does not turn Gather/Say into full-duplex audio. Live calls still require approved test numbers and have separate provider charges.

## Verification

`./scripts/test.sh` runs the Python and browser regression tests and builds/tests Java and React. New coverage includes the live notes, the end-of-call record and the receipt transcript, call turn-taking (live captions, silence endpointing, stream reopening, interruption, denied microphones, unsupported browsers), service authentication, text limits, neural provider failures, binary delivery, stale revisions, human acceptance, late audio cancellation, autoplay/replay and neural telephone prompts.

With the stack running, `python3 scripts/smoke_tts.py` makes one small paid OpenAI TTS request, checks the MP3 response, authentication and revision protection, and leaves a synthetic session in PostgreSQL. It does not place a telephone call or assess subjective voice quality.

Implementation references: [OpenAI speech guide](https://developers.openai.com/api/docs/guides/text-to-speech), [Twilio Say](https://www.twilio.com/docs/voice/twiml/say), [Twilio voice identifiers](https://github.com/twilio/twilio-java/blob/main/src/main/java/com/twilio/twiml/voice/Say.java).
