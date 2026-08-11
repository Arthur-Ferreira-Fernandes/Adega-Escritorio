import logging

from django.contrib.auth.signals import (
    user_logged_in,
    user_logged_out,
    user_login_failed,
)
from django.dispatch import receiver

logger = logging.getLogger("apps.usuarios")


def _ip_do_request(request):
    if request is None:
        return None
    return request.META.get("REMOTE_ADDR")


@receiver(user_logged_in)
def registrar_login(sender, request, user, **kwargs):
    logger.info(
        "Login realizado", extra={"usuario": user.username, "ip": _ip_do_request(request)}
    )


@receiver(user_logged_out)
def registrar_logout(sender, request, user, **kwargs):
    if user is None:
        return
    logger.info(
        "Logout realizado", extra={"usuario": user.username, "ip": _ip_do_request(request)}
    )


@receiver(user_login_failed)
def registrar_falha_login(sender, credentials, request=None, **kwargs):
    logger.warning(
        "Falha de login",
        extra={
            "usuario_tentado": credentials.get("username"),
            "ip": _ip_do_request(request),
        },
    )
