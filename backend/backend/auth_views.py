"""Same-origin session endpoints for the React application."""

import json

from django.contrib.auth import authenticate, login, logout
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from django.views.decorators.http import require_GET, require_POST


def _session_payload(user):
    return {
        "authenticated": user.is_authenticated,
        "username": user.get_username() if user.is_authenticated else None,
        "operator": bool(
            user.is_authenticated
            and (user.is_superuser or user.has_perm("organizer.operate_organizer"))
        ),
    }


@require_GET
@ensure_csrf_cookie
def session(request):
    return JsonResponse(_session_payload(request.user))


@require_POST
@csrf_protect
def session_login(request):
    try:
        payload = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"detail": "Invalid JSON."}, status=400)
    user = authenticate(
        request,
        username=payload.get("username"),
        password=payload.get("password"),
    )
    if user is None or not user.is_active:
        return JsonResponse({"detail": "Invalid credentials."}, status=401)
    login(request, user)
    return JsonResponse(_session_payload(user))


@require_POST
@csrf_protect
def session_logout(request):
    logout(request)
    return JsonResponse({"authenticated": False, "username": None, "operator": False})
