import json
import uuid

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_POST

from .models import AudioMonitoringSession

MAX_BODY_BYTES = 128 * 1024
MAX_EVENTS = 250

def _bounded_number(value, minimum, maximum, integer=False):
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = 0.0
    number = max(minimum, min(maximum, number))
    return int(round(number)) if integer else number

def _clean_events(events):
    if not isinstance(events, list):
        return []

    cleaned = []
    for event in events[-MAX_EVENTS:]:
        if not isinstance(event, dict):
            continue
        details = event.get("details", {})
        if not isinstance(details, dict):
            details = {}
        # Mantiene el registro acotado aunque un cliente envíe datos inesperados.
        details_text = json.dumps(details, ensure_ascii=False)[:2048]
        try:
            safe_details = json.loads(details_text)
        except json.JSONDecodeError:
            safe_details = {}
        confidence = event.get("confidence")
        cleaned.append({
            "type": str(event.get("type", "unknown"))[:64],
            "label": str(event.get("label", ""))[:128],
            "at_seconds": _bounded_number(event.get("at_seconds"), 0, 86400),
            "confidence": None if confidence is None else _bounded_number(confidence, 0, 1),
            "details": safe_details,
        })
    return cleaned

@require_POST
@csrf_protect
def update_audio_monitoring(request):
    subject_id = request.session.get("payid")
    if not subject_id:
        return JsonResponse({"error": "Session expired"}, status=403)

    try:
        content_length = int(request.META.get("CONTENT_LENGTH") or 0)
    except ValueError:
        content_length = 0
    if content_length > MAX_BODY_BYTES:
        return JsonResponse({"error": "Payload too large"}, status=413)

    if len(request.body) > MAX_BODY_BYTES:
        return JsonResponse({"error": "Payload too large"}, status=413)

    try:
        payload = json.loads(request.body.decode("utf-8"))
        session_id = uuid.UUID(str(payload.get("session_id")))
    except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError, AttributeError):
        return JsonResponse({"error": "Invalid payload"}, status=400)

    task_id = str(payload.get("task_id", ""))[:64]
    if not task_id:
        return JsonResponse({"error": "Missing task_id"}, status=400)

    metrics = payload.get("metrics", {})
    if not isinstance(metrics, dict):
        metrics = {}
    finalized = bool(payload.get("final", False))

    defaults = {
        "subject_id": subject_id,
        "task_id": task_id,
        "client_version": str(payload.get("client_version", "unknown"))[:32],
        "client_timezone": str(payload.get("client_timezone") or "")[:64],
        "client_utc_offset_minutes": None if payload.get("client_utc_offset_minutes") is None else _bounded_number(payload.get("client_utc_offset_minutes"), -840, 840, True),
        "duration_seconds": _bounded_number(metrics.get("durationSeconds"), 0, 86400, True),
        "speech_seconds": _bounded_number(metrics.get("speechSeconds"), 0, 86400, True),
        "silence_seconds": _bounded_number(metrics.get("silenceSeconds"), 0, 86400, True),
        "noise_seconds": _bounded_number(metrics.get("noiseSeconds"), 0, 86400, True),
        "average_speech_probability": _bounded_number(metrics.get("averageSpeechProbability"), 0, 1),
        "longest_silence_seconds": _bounded_number(metrics.get("longestSilenceSeconds"), 0, 86400, True),
        "speech_events": _bounded_number(metrics.get("speechEvents"), 0, 100000, True),
        "non_speech_events": _bounded_number(metrics.get("nonSpeechEvents"), 0, 100000, True),
        "vad_alerts": _bounded_number(metrics.get("vadAlerts"), 0, 100000, True),
        "music_alerts": _bounded_number(metrics.get("musicAlerts"), 0, 100000, True),
        "singing_alerts": _bounded_number(metrics.get("singingAlerts"), 0, 100000, True),
        "last_audio_label": str(metrics.get("lastAudioLabel", ""))[:64],
        "events": _clean_events(payload.get("events")),
        "finalized": finalized,
        "user_agent": request.META.get("HTTP_USER_AGENT", "")[:512],
    }
    if finalized:
        defaults["completed_at"] = timezone.now()

    existing = AudioMonitoringSession.objects.filter(session_id=session_id).only("subject_id").first()
    if existing and existing.subject_id != subject_id:
        return JsonResponse({"error": "Invalid session owner"}, status=403)

    monitor_session, created = AudioMonitoringSession.objects.update_or_create(
        session_id=session_id,
        defaults=defaults,
    )
    return JsonResponse({
        "success": True,
        "created": created,
        "session_id": str(monitor_session.session_id),
    })
