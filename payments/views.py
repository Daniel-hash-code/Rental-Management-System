
import json

from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from payments.services.daraja import (
    process_stk_callback,
)


@csrf_exempt
@require_POST
def stk_callback(request):
    """
    Public endpoint receiving Safaricom STK Push callbacks.
    """

    try:
        payload = json.loads(request.body)

    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse(
            {"error": "Invalid JSON payload."},
            status=400,
        )

    if not isinstance(payload, dict):
        return JsonResponse(
            {"error": "Invalid callback structure."},
            status=400,
        )

    try:
        process_stk_callback(payload)

    except Exception:
        # Do not expose internal errors to the callback sender.
        # Production logging and alerting should capture details.
        return JsonResponse(
            {"ResultCode": 1, "ResultDesc": "Processing error"},
            status=500,
        )

    # Acknowledge the callback without revealing payment details.
    return JsonResponse(
        {
            "ResultCode": 0,
            "ResultDesc": "Callback received successfully.",
        },
        status=200,
    )
