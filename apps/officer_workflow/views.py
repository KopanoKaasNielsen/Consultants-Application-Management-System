from django.http import JsonResponse


def workflow_status(request):
    """Simple health endpoint for the officer workflow API."""
    return JsonResponse({"status": "ok"})
