"""Erros da SDK do bFocus.

Toda resposta fora de 2xx vira um :class:`BfocusError` (ou uma subclasse, pelo status).
Falha de conexão/timeout vira :class:`NetworkError` (``status == 0``).

**Use** :attr:`BfocusError.code` **na sua lógica** — ele é estável (``CUSTOMER_NOT_FOUND``,
``INTEGRATION_SCOPE_MISSING``…). O :attr:`~BfocusError.message` é texto para humanos.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

__all__ = [
    "BfocusError",
    "AuthenticationError",
    "PermissionDeniedError",
    "NotFoundError",
    "ConflictError",
    "ValidationError",
    "RateLimitError",
    "ServerError",
    "NetworkError",
    "error_for_status",
]


class BfocusError(Exception):
    """Erro devolvido pela API do bFocus (ou de rede, em :class:`NetworkError`).

    Attributes:
        code: Código estável do erro (``body.error``; senão ``body.message``; senão
            ``HTTP_<status>`` quando o corpo não é JSON; ``INVALID_RESPONSE`` quando um 2xx
            chega sem o envelope JSON da API). **É nele que a sua lógica decide.**
        message: Texto legível: o ``code`` e o contexto (status, escopo exigido, motivos).
        status: Status HTTP (``0`` em erro de rede).
        request_id: ``request_id`` do corpo, senão o header ``X-Request-Id``, senão o
            ``X-Request-Id`` que a SDK enviou (a API ecoa o do cliente) — sempre preenchido;
            informe-o ao suporte.
        validation: Mapa campo → motivo (erros de validação); ``{}`` quando não há.
        data: O ``data`` do corpo do erro — o detalhe estruturado que alguns erros trazem;
            ``{}`` quando não há. É onde vem, por exemplo, de quem é o contato já usado num
            409 ``PERSON_EMAIL_TAKEN``/``PERSON_PHONE_TAKEN`` (``field``,
            ``owner_external_id``, ``owner_name``, ``owner_customer_external_id``) e o
            ``owner`` de um ``IDENTIFIER_IN_USE``. A API repete esse detalhe em
            :attr:`validation`, por compatibilidade com as SDKs que ainda não expunham
            ``data``.
        retry_after: Segundos sugeridos pelo header ``Retry-After`` (só em 429).
        required_scope: Escopo que faltou na chave (header ``X-Required-Scope``, só em 403).
        body: Corpo da resposta já decodificado (dict), ou o texto cru quando não é JSON.
    """

    def __init__(
        self,
        code: str,
        message: str,
        status: int,
        *,
        request_id: Optional[str] = None,
        validation: Optional[Dict[str, Any]] = None,
        retry_after: Optional[float] = None,
        required_scope: Optional[str] = None,
        body: Any = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.request_id = request_id
        self.validation: Dict[str, Any] = dict(validation or {})
        self.data: Dict[str, Any] = dict(data or {})
        self.retry_after = retry_after
        self.required_scope = required_scope
        self.body = body

    def __str__(self) -> str:
        if self.request_id:
            return f"{self.message} [request_id={self.request_id}]"
        return self.message

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}(code={self.code!r}, status={self.status!r}, "
            f"request_id={self.request_id!r})"
        )


class AuthenticationError(BfocusError):
    """401 — chave ausente, inválida ou revogada."""


class PermissionDeniedError(BfocusError):
    """403 — chave desligada, IP não liberado ou escopo faltando (veja ``required_scope``)."""


class NotFoundError(BfocusError):
    """404 — o recurso (ou a conta) não existe."""


class ConflictError(BfocusError):
    """409 — o estado atual impede a operação (ex.: ``KB_ARTICLE_EMPTY``, ``AI_DISABLED``)."""


class ValidationError(BfocusError):
    """422 — corpo ou parâmetro inválido; os motivos por campo estão em ``validation``."""


class RateLimitError(BfocusError):
    """429 — limite de requisições da chave; ``retry_after`` diz quanto esperar."""


class ServerError(BfocusError):
    """5xx — erro do lado da API. Informe o ``request_id``."""


class NetworkError(BfocusError):
    """Falha de conexão ou timeout (``status == 0``, ``code == "NETWORK_ERROR"``)."""

    def __init__(self, message: str, *, request_id: Optional[str] = None) -> None:
        super().__init__("NETWORK_ERROR", message, 0, request_id=request_id)


_BY_STATUS = {
    401: AuthenticationError,
    403: PermissionDeniedError,
    404: NotFoundError,
    409: ConflictError,
    422: ValidationError,
    429: RateLimitError,
}


def error_for_status(status: int) -> type:
    """Classe de erro para um status HTTP (5xx → :class:`ServerError`, resto → base)."""
    if status in _BY_STATUS:
        return _BY_STATUS[status]
    if 500 <= status <= 599:
        return ServerError
    return BfocusError
