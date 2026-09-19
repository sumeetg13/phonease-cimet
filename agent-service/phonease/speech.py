"""Neural synthesis for server-selected assistant replies; never receives caller audio."""
import os
from fastapi import HTTPException
from openai import OpenAI, OpenAIError

INSTRUCTIONS = (
    'You are the Phonease AI energy assistant. Speak in a warm, calm, conversational '
    'Australian English accent, at an unhurried but natural pace. Use gentle sentence '
    'pauses and natural intonation, not a sales or announcer voice. Read the supplied '
    'text faithfully, without adding words. Read four-digit postcodes digit by digit.'
)

def synthesize(text: str) -> bytes:
    key = os.getenv('OPENAI_API_KEY', '').strip()
    if not key:
        raise HTTPException(503, 'Neural speech is not configured. Choose device voice or configure OpenAI.')
    try:
        # No retries: do not silently multiply paid requests on failure.
        with OpenAI(api_key=key, timeout=12.0, max_retries=0) as client:
            response = client.audio.speech.create(
                model=os.getenv('OPENAI_TTS_MODEL') or 'gpt-4o-mini-tts',
                voice=os.getenv('OPENAI_TTS_VOICE') or 'marin',
                input=text, instructions=INSTRUCTIONS, response_format='mp3',
            )
            audio = response.content
        if not audio or len(audio) > 8 * 1024 * 1024:
            raise HTTPException(502, 'Invalid speech response from provider.')
        return audio
    except OpenAIError:
        # Never expose provider errors, request text or credentials.
        raise HTTPException(502, 'Neural speech unavailable. Text remains available; try device voice.') from None
