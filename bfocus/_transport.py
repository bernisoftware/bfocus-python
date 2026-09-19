"""Transporte HTTP: headers, codificação, novas tentativas e tradução de erros.

Só biblioteca padrão (``urllib``). Nada aqui faz rede na importação/construção.
"""

from __future__ import annotations

import http.client
import json
import random
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Callable, Dict, Mapping, Optional, Tuple

from ._version import __version__
from .errors import BfocusError, NetworkError, error_for_status
from .types import Unset

DEFAULT_BASE_URL = "https://api.bfocus.com.br"
API_PREFIX = "/api/v1/integration"
#: Vai em ``X-Bfocus-Client`` e ``User-Agent``. É por ele que a API sabe qual versão da
#: SDK a conta roda — e avisa quando uma correção exigir atualizar.
CLIENT_ID = f"bfocus-python/{__version__}"
DEFAULT_TIMEOUT = 30.0
DEFAULT_MAX_RETRIES = 2

RETRY_STATUSES = frozenset({429, 502, 503, 504})
WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
MAX_RETRY_AFTER = 60.0
MAX_BACKOFF = 8.0

# Falhas de transporte que viram NetworkError (e são repetidas). ``socket.timeout`` e
# ``ConnectionError`` são OSError; ``RemoteDisconnected``/``IncompleteRead`` são HTTPException.
_NETWORK_FAILURES = (urllib.error.URLError, OSError, http.client.HTTPException)


# ── codificação ─────────────────────────────────────────────────────────────────


def path_segment(value: Any, name: str, *, allow_slash: bool = True) -> str:
    """Percent-encode de UM segmento de caminho (``ERP 1042`` → ``ERP%201042``)."""
    if isinstance(value, Unset) or value is None:
        raise ValueError(f"{name} é obrigatório.")
    text = str(value)
    if text == "":
        raise ValueError(f"{name} não pode ser vazio.")
    if text in (".", ".."):
        # O cliente HTTP resolveria "%2E%2E" como navegação de caminho e chamaria outra rota.
        raise ValueError(f"{name} não pode ser {text!r}.")
    if not allow_slash and "/" in text:
        raise ValueError(
            f"{name} não aceita '/' (a API recusa) — use ':' para hierarquia: {text!r}"
        )
    return urllib.parse.quote(text, safe="")


def iso_utc(value: datetime) -> str:
    """``datetime`` → ISO 8601 em UTC com ``Z``. Sem fuso = já está em UTC."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return value.replace(tzinfo=None).isoformat() + "Z"


def query_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, datetime):
        return iso_utc(value)
    if isinstance(value, date):
        return value.isoformat() + "T00:00:00Z"
    return str(value)


def compact(fields: Mapping[str, Any]) -> Dict[str, Any]:
    """Corpo só com o que o usuário informou (``None`` fica e vira ``null``)."""
    return {k: v for k, v in fields.items() if not isinstance(v, Unset)}


def _json_default(value: Any) -> Any:
    if isinstance(value, datetime):
        return iso_utc(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, (set, frozenset, tuple)):
        return list(value)
    raise TypeError(f"valor não serializável em JSON: {type(value).__name__}")


def parse_retry_after(raw: Optional[str]) -> Optional[float]:
    """``Retry-After`` em segundos (número ou data HTTP); ``None`` se ausente/inválido."""
    if not raw:
        return None
    raw = raw.strip()
    try:
        seconds = float(raw)
    except ValueError:
        try:
            when = parsedate_to_datetime(raw)
        except (TypeError, ValueError, IndexError):
            return None
        if when is None:
            return None
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        seconds = (when - datetime.now(timezone.utc)).total_seconds()
    if seconds != seconds:  # NaN
        return None
    seconds = max(0.0, seconds)
    return int(seconds) if float(seconds).is_integer() else seconds


# ── erros ───────────────────────────────────────────────────────────────────────


def _decode_json(raw: bytes) -> Tuple[Any, str]:
    text = raw.decode("utf-8", "replace") if raw else ""
    if not text.strip():
        return None, text
    try:
        return json.loads(text), text
    except ValueError:
        return None, text


def build_error(
    status: int,
    headers: Mapping[str, str],
    raw: bytes,
    sent_request_id: Optional[str] = None,
) -> BfocusError:
    """Resposta fora de 2xx → erro. ``request_id``: corpo → header → o id que a SDK enviou."""
    payload, text = _decode_json(raw)
    code: Optional[str] = None
    human: Optional[str] = None
    validation: Dict[str, Any] = {}
    request_id: Optional[str] = None

    if isinstance(payload, dict):
        err, msg = payload.get("error"), payload.get("message")
        if isinstance(err, str) and err:
            code = err
        elif isinstance(msg, str) and msg:
            code = msg
        if isinstance(msg, str) and msg and msg != code:
            human = msg
        if isinstance(payload.get("validation"), dict):
            validation = payload["validation"]
        rid = payload.get("request_id")
        if isinstance(rid, str) and rid:
            request_id = rid
    elif text.strip():
        human = text.strip()[:200]

    if not code:
        code = f"HTTP_{status}"
    if not request_id:
        request_id = headers.get("X-Request-Id") or sent_request_id or None
    retry_after =parse_retry_after(headers.get("Retry-After")) if status == 429 else None
    required_scope = (headers.get("X-Required-Scope") or None) if status == 403 else None

    message = f"{code} (HTTP {status})"
    if human:
        message += f": {human}"
    if required_scope:
        message += f" — escopo exigido: {required_scope}"
    if validation:
        message += " — " + "; ".join(f"{k}: {v}" for k, v in validation.items())
    if retry_after is not None:
        message += f" — tente de novo em {retry_after}s"

    cls = error_for_status(status)
    return cls(
        code,
        message,
        status,
        request_id=request_id,
        validation=validation,
        retry_after=retry_after,
        required_scope=required_scope,
        body=payload if payload is not None else (text or None),
    )


# ── transporte ──────────────────────────────────────────────────────────────────


class Transport:
    """Faz UMA chamada lógica: 1 tentativa + até ``max_retries`` novas tentativas."""

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str,
        timeout: float,
        max_retries: int,
        sleep: Optional[Callable[[float], Any]] = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.max_retries = max_retries
        #: Espera entre tentativas. Substituível (os testes não dormem de verdade).
        self.sleep: Callable[[float], Any] = sleep or time.sleep

    # A espera exponencial usa ``random``; isolado para os testes poderem conferir.
    @staticmethod
    def backoff(attempt: int) -> float:
        base = min(MAX_BACKOFF, 0.5 * (2 ** attempt))
        return base + random.uniform(0, base * 0.25)

    def retry_delay(self, attempt: int, retry_after: Optional[str]) -> float:
        seconds = parse_retry_after(retry_after)
        if seconds is not None:
            return min(float(seconds), MAX_RETRY_AFTER)
        return self.backoff(attempt)

    def build_url(self, path: str, query: Optional[Mapping[str, Any]]) -> str:
        url = self.base_url + API_PREFIX + path
        if query:
            pairs = [(k, query_value(v)) for k, v in query.items() if v is not None]
            if pairs:
                url += "?" + urllib.parse.urlencode(pairs, quote_via=urllib.parse.quote)
        return url

    def request(
        self,
        method: str,
        path: str,
        *,
        query: Optional[Mapping[str, Any]] = None,
        body: Any = None,
        idempotency_key: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> Tuple[Any, Optional[Dict[str, Any]]]:
        """Executa a chamada e devolve ``(data, pagination)`` do envelope.

        ``body=None`` significa SEM corpo (o JSON ``null`` nunca é um corpo válido aqui).
        """
        url = self.build_url(path, query)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
            "X-Bfocus-Client": CLIENT_ID,
            "User-Agent": CLIENT_ID,
            # Mesmo id em todas as tentativas desta chamada: é como o suporte correlaciona.
            "X-Request-Id": uuid.uuid4().hex,
        }
        if method in WRITE_METHODS:
            # Mesma chave em todas as tentativas: a API devolve a resposta original
            # (Idempotent-Replayed: true) em vez de executar de novo.
            headers["Idempotency-Key"] = idempotency_key or str(uuid.uuid4())
        data: Optional[bytes] = None
        if body is not None:
            data = json.dumps(body, ensure_ascii=False, default=_json_default).encode("utf-8")
            headers["Content-Type"] = "application/json"
        per_try = self.timeout if timeout is None else timeout

        attempt = 0
        while True:
            try:
                status, resp_headers, raw = self._send(method, url, headers, data, per_try)
            except _NETWORK_FAILURES as exc:
                if attempt < self.max_retries:
                    self.sleep(self.backoff(attempt))
                    attempt += 1
                    continue
                reason = getattr(exc, "reason", None) or exc
                raise NetworkError(
                    f"NETWORK_ERROR: falha ao falar com {self.base_url} "
                    f"({type(exc).__name__}: {reason})",
                    request_id=headers["X-Request-Id"],
                ) from exc

            if 200 <= status < 300:
                return self._unwrap(status, resp_headers, raw, headers["X-Request-Id"])

            if status in RETRY_STATUSES and attempt < self.max_retries:
                self.sleep(self.retry_delay(attempt, resp_headers.get("Retry-After")))
                attempt += 1
                continue
            raise build_error(status, resp_headers, raw, headers["X-Request-Id"])

    @staticmethod
    def _send(
        method: str,
        url: str,
        headers: Mapping[str, str],
        data: Optional[bytes],
        timeout: float,
    ) -> Tuple[int, Mapping[str, str], bytes]:
        req = urllib.request.Request(url, data=data, headers=dict(headers), method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.status, resp.headers, resp.read()
        except urllib.error.HTTPError as exc:  # status fora de 2xx: é resposta, não rede
            try:
                raw = exc.read()
            except _NETWORK_FAILURES:
                raw = b""
            finally:
                exc.close()
            return exc.code, exc.headers, raw

    @staticmethod
    def _unwrap(
        status: int, headers: Mapping[str, str], raw: bytes, sent_request_id: str
    ) -> Tuple[Any, Optional[Dict[str, Any]]]:
        """2xx → ``(data, pagination)``. Sem envelope JSON válido → ``INVALID_RESPONSE``.

        Nunca devolve ``None`` calado: um proxy que responde 200 com HTML (ou um corpo vazio)
        vira erro, não "sucesso sem dados".
        """
        payload, text = _decode_json(raw)
        if isinstance(payload, dict) and "data" in payload:
            pagination = payload.get("pagination")
            return payload["data"], pagination if isinstance(pagination, dict) else None
        shown = text.strip()[:200]
        raise BfocusError(
            "INVALID_RESPONSE",
            f"INVALID_RESPONSE (HTTP {status}): resposta sem o envelope JSON da API"
            + (f": {shown!r}" if shown else " (corpo vazio)"),
            status,
            request_id=headers.get("X-Request-Id") or sent_request_id,
            body=payload if payload is not None else (text or None),
        )
