import io

from openai import AsyncOpenAI

from app.config import settings

client = AsyncOpenAI(api_key=settings.openai_api_key)


async def transcribe_audio(audio_bytes: bytes, filename: str = "audio.webm") -> str:
    """STT: transcribe audio del cliente usando Whisper."""
    buffer = io.BytesIO(audio_bytes)
    buffer.name = filename
    transcript = await client.audio.transcriptions.create(
        model="whisper-1",
        file=buffer,
        language="es",
    )
    return transcript.text.strip()


async def synthesize_speech(text: str) -> bytes:
    """TTS: genera respuesta hablada del agente."""
    response = await client.audio.speech.create(
        model="tts-1",
        voice="nova",
        input=text,
        response_format="mp3",
    )
    return response.content
