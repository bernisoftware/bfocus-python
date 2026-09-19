"""Identidade do widget de atendimento (assinatura local, sem rede)."""

from __future__ import annotations

import hashlib
import hmac
import math
import time
from datetime import datetime, timezone
from typing import Optional, Union

__all__ = ["sign_widget_identity", "sign_widget_identity_v2"]


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


def _unix_seconds(now: Union[int, float, datetime, None]) -> int:
    if now is None:
        return int(math.floor(time.time()))
    if isinstance(now, bool):
        raise TypeError("sign_widget_identity_v2: now precisa ser int/float (segundos unix) ou datetime.")
    if isinstance(now, datetime):
        if now.tzinfo is None:  # sem fuso = UTC (mesma regra das datas da SDK)
            now = now.replace(tzinfo=timezone.utc)
        seconds = math.floor(now.timestamp())
    elif isinstance(now, (int, float)):
        if isinstance(now, float) and not math.isfinite(now):
            raise ValueError("sign_widget_identity_v2: now precisa ser um número finito.")
        seconds = math.floor(now)
    else:
        raise TypeError("sign_widget_identity_v2: now precisa ser int/float (segundos unix) ou datetime.")
    if seconds < 0:
        raise ValueError("sign_widget_identity_v2: now não pode ser negativo (segundos unix).")
    return int(seconds)


def sign_widget_identity_v2(
    secret: Union[str, bytes],
    user_external_id: str,
    customer_external_id: str,
    *,
    now: Optional[Union[int, float, datetime]] = None,
) -> str:
    """Assina a identidade do usuário logado **com validade** (v2) para abrir o widget.

    Como a v1, roda no seu backend e não exige chave de API. Devolve ``"v2.<ts>.<hex>"``:
    ``ts`` = segundos unix inteiros do instante (padrão: agora) e ``hex`` = HMAC-SHA256 em
    hexadecimal minúsculo de ``"v2:" + ts + ":" + user_external_id + ":" +
    customer_external_id`` (UTF-8). Vai no mesmo lugar da v1 (``userHash`` do widget).

    A API aceita a assinatura de 7 dias atrás até 5 minutos à frente: gere a cada
    renderização da página, nunca guarde. A v1 continua aceita.

    Args:
        secret: Segredo de identidade do widget (painel do bFocus).
        user_external_id: ``external_id`` do usuário no seu sistema — **sem** ``:`` (é o
            separador; a API recusa).
        customer_external_id: ``external_id`` do cliente (empresa) — pode ter ``:``.
        now: Instante da assinatura: segundos unix (``int``/``float``, não milissegundos)
            ou ``datetime`` (sem fuso = UTC). Padrão: agora.

    Example:
        >>> sign_widget_identity_v2("bf_whs_x", "USR-1", "ACME-1", now=1789000000)[:30]
        'v2.1789000000.bfbf2a0390fbb9d6'
    """
    key = secret.encode("utf-8") if isinstance(secret, str) else bytes(secret)
    if not key:
        raise ValueError("sign_widget_identity_v2: secret é obrigatório.")
    if ":" in str(user_external_id):
        raise ValueError(
            "sign_widget_identity_v2: user_external_id não pode ter ':' (é o separador da "
            f"assinatura; a API recusa): {user_external_id!r}"
        )
    ts = _unix_seconds(now)
    msg = f"v2:{ts}:{user_external_id}:{customer_external_id}".encode("utf-8")
    return f"v2.{ts}.{hmac.new(key, msg, hashlib.sha256).hexdigest()}"
