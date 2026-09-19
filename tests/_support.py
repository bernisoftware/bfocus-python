"""Apoio dos testes: servidor HTTP falso (stdlib) e localização dos casos de conformidade.

Os casos moram em ``clients/conformance/cases.json`` no monorepo. O espelho público
(``bernisoftware/bfocus-python``) recebe só ``clients/python`` — por isso existe a cópia
``tests/fixtures/cases.json``, escrita pelo ``clients/conformance/generate.py`` (não edite à
mão). Um teste trava que ela seja idêntica à fonte quando as duas existem (no monorepo).
"""

from __future__ import annotations

import json
import pathlib
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qsl

TESTS_DIR = pathlib.Path(__file__).resolve().parent
PACKAGE_ROOT = TESTS_DIR.parent  # clients/python (ou a raiz do espelho público)
VENDORED_CASES = TESTS_DIR / "fixtures" / "cases.json"
# No monorepo: <raiz>/clients/python/tests. Fora dele (espelho, container) estes caminhos
# simplesmente não existem e os testes que dependem deles são pulados.
MONOREPO_CASES = PACKAGE_ROOT.parent / "conformance" / "cases.json"
MONOREPO_SPEC = PACKAGE_ROOT.parent.parent / "api" / "openapi" / "public.json"


def cases_path() -> pathlib.Path:
    return MONOREPO_CASES if MONOREPO_CASES.is_file() else VENDORED_CASES


def load_cases() -> Dict[str, Any]:
    with cases_path().open(encoding="utf-8") as fh:
        return json.load(fh)


class FakeServer:
    """Servidor local que responde, em ordem, as respostas enfileiradas e grava as requisições.

    Requisição a mais (fila vazia) recebe 418 ``UNEXPECTED_REQUEST`` — status que a SDK não
    repete — e fica gravada para o teste acusar.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._responses: List[Dict[str, Any]] = []
        self.requests: List[Dict[str, Any]] = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def _handle(self) -> None:
                length = int(self.headers.get("Content-Length") or 0)
                raw = self.rfile.read(length) if length else b""
                path, _, qs = self.path.partition("?")
                record = {
                    "method": self.command,
                    "path": path,
                    "query": parse_qsl(qs, keep_blank_values=True),
                    "headers": {k.lower(): v for k, v in self.headers.items()},
                    "body": raw,
                }
                with outer._lock:
                    outer.requests.append(record)
                    resp: Optional[Dict[str, Any]] = (
                        outer._responses.pop(0) if outer._responses else None
                    )
                if resp is None:
                    resp = {
                        "status": 418,
                        "headers": {},
                        "body": {"code": 418, "data": None, "message": "UNEXPECTED_REQUEST",
                                 "error": "UNEXPECTED_REQUEST"},
                    }
                body = resp.get("body")
                if body is None:
                    payload, ctype = b"", None
                elif isinstance(body, str):
                    payload, ctype = body.encode("utf-8"), "text/plain; charset=utf-8"
                else:
                    payload, ctype = json.dumps(body).encode("utf-8"), "application/json"
                self.send_response(int(resp["status"]))
                if ctype:
                    self.send_header("Content-Type", ctype)
                self.send_header("Content-Length", str(len(payload)))
                for key, value in (resp.get("headers") or {}).items():
                    self.send_header(key, str(value))
                self.end_headers()
                if payload:
                    self.wfile.write(payload)

            do_GET = do_POST = do_PUT = do_PATCH = do_DELETE = _handle

            def log_message(self, format: str, *args: Any) -> None:  # silencia o stderr
                pass

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.httpd.daemon_threads = True
        self._thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)

    @property
    def base_url(self) -> str:
        host, port = self.httpd.server_address[:2]
        return f"http://{host}:{port}"

    def start(self) -> "FakeServer":
        self._thread.start()
        return self

    def stop(self) -> None:
        self.httpd.shutdown()
        self.httpd.server_close()

    def reset(self, responses: List[Dict[str, Any]]) -> None:
        with self._lock:
            self._responses = list(responses)
            self.requests = []


def ok(data: Any, status: int = 200, pagination: Optional[Dict[str, int]] = None,
       headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Resposta de sucesso no envelope da API."""
    body: Dict[str, Any] = {"code": status, "data": data, "message": "Executado com sucesso"}
    if pagination is not None:
        body["pagination"] = pagination
    return {"status": status, "headers": headers or {}, "body": body}


def fail(status: int, code: str, headers: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
    """Resposta de erro no envelope da API."""
    return {
        "status": status,
        "headers": headers or {},
        "body": {"code": status, "data": None, "message": code, "error": code,
                 "validation": {}, "request_id": "req-unit"},
    }


def json_body(record: Dict[str, Any]) -> Any:
    raw = record["body"]
    return json.loads(raw.decode("utf-8")) if raw else None
