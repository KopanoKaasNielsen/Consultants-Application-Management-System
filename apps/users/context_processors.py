"""Custom context processors for the users app."""

from apps.users.views import _user_is_admin


def user_is_admin(request):
    """Expose whether the current user is an admin to templates."""
    return {
        "user_is_admin": _user_is_admin(request.user)
        if request.user.is_authenticated
        else False,
    }
