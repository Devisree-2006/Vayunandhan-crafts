"""
Notifications app views — only the WhatsApp webhook endpoint lives here.
"""
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from .services import verify_whatsapp_webhook


@csrf_exempt
def whatsapp_webhook(request):
    """
    GET  → Meta webhook verification challenge.
    POST → Incoming WhatsApp messages / status updates (not processed yet).
    """
    if request.method == 'GET':
        ok, challenge = verify_whatsapp_webhook(request)
        if ok:
            return HttpResponse(challenge, content_type='text/plain')
        return HttpResponse('Verification failed', status=403)

    if request.method == 'POST':
        # Future: handle inbound messages / delivery status callbacks here.
        return HttpResponse('OK')

    return HttpResponse(status=405)
