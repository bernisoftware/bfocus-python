"""Identidade do widget de atendimento (assinatura local, sem rede)."""

from __future__ import annotations

import hashlib
import hmac
from typing import Union

__all__ = ["sign_widget_identity"]


def sign_widget_identity(
    secret: Union[str, bytes],
    user_external_id: str,
    customer_external_id: str,
) -> str:
    """Assina a identidade do usuário logado para abrir o widget do bFocus.

    Roda no **seu backend** (o segredo nunca vai para o navegador) e não exige chave de API.
    Devolve o HMAC-SHA256 em hexadecimal minúsculo de
    ``"v1:" + user_external_id + ":" + customer_external_id`` (UTF-8).

    Args:
        secret: Segredo de identidade do widget (painel do bFocus).
        user_external_id: ``external_id`` do usuário no seu sistema.
        customer_external_id: ``external_id`` do cliente (empresa) desse usuário.

    Example:
        >>> sign_widget_identity("bf_whs_x", "USR-1", "ACME-1")[:16]
        '9a15d2527b855a04'
    """
    key = secret.encode("utf-8") if isinstance(secret, str) else bytes(secret)
    if not key:
        raise ValueError("sign_widget_identity: secret é obrigatório.")
    msg = f"v1:{user_external_id}:{customer_external_id}".encode("utf-8")
    return hmac.new(key, msg, hashlib.sha256).hexdigest()
