"""Fuerza el webhook de voz en el número Twilio (y TwiML App si está vinculada)."""
from twilio.rest import Client

from app.config import settings

WEBHOOK = f"{settings.public_base_url.rstrip('/')}/twilio/voice/incoming"

client = Client(settings.twilio_account_sid, settings.twilio_auth_token)
numbers = client.incoming_phone_numbers.list(phone_number=settings.twilio_phone_number)

if not numbers:
    print("No se encontró el número", settings.twilio_phone_number)
    raise SystemExit(1)

num = numbers[0]
updated = client.incoming_phone_numbers(num.sid).update(
    voice_url=WEBHOOK,
    voice_method="POST",
    voice_fallback_url="",
)
print("OK — Voice URL del número actualizado:")
print(" ", updated.voice_url)
print(" ", updated.voice_method)

app_sid = getattr(updated, "voice_application_sid", None) or getattr(num, "voice_application_sid", None)
if app_sid:
    app = client.applications(app_sid).update(voice_url=WEBHOOK, voice_method="POST")
    print("OK — Voice URL de TwiML App actualizado:")
    print(" ", app.friendly_name)
    print(" ", app.voice_url)
    print(" ", app.voice_method)
else:
    print("(Sin TwiML App vinculada al número)")
