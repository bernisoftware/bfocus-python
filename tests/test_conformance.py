"""Conformidade: roda TODOS os casos de ``clients/conformance/cases.json`` (BRIEF §7).

Para cada caso, um servidor HTTP local confere cada troca — método, caminho exatamente
como codificado, query, corpo JSON, ``Authorization``, ``X-Bfocus-Client``, ``X-Request-Id``,
``Idempotency-Key`` — e, entre novas tentativas da mesma chamada, que os ids se repetem.
Depois compara o retorno (ou o erro) com ``expect``.

Endpoint novo sem método na SDK quebra este teste: todo ``op`` dos casos precisa estar em
``OPS`` (a menos que esteja em ``sdk_excluded_ops``).
"""

from __future__ import annotations

import collections.abc
import copy
import json
import re
import unittest
from typing import Any, Callable, Dict

import bfocus
from bfocus import Bfocus, Page, errors, sign_widget_identity

from _support import (
    MONOREPO_CASES,
    MONOREPO_SPEC,
    VENDORED_CASES,
    FakeServer,
    load_cases,
)

CASES = load_cases()
API_KEY = CASES["api_key"]
EXCLUDED = set(CASES.get("sdk_excluded_ops", []))
HELPERS: Dict[str, str] = CASES.get("sdk_helper_ops", {})
CLIENT_RE = re.compile(r"^bfocus-python/" + re.escape(bfocus.__version__) + r"$")
REQUEST_ID_RE = re.compile(r"^[0-9a-f]{32}$")
WRITES = {"POST", "PUT", "PATCH", "DELETE"}
SENT = "$sent"  # em expect.error.request_id: "o X-Request-Id que a SDK enviou"

# op (neutro) → método da SDK. Os ``args`` dos casos já estão em snake_case e batem com os
# nomes dos parâmetros, então a chamada é ``metodo(**args)``.
OPS: Dict[str, Callable[[Bfocus], Callable[..., Any]]] = {
    "customers.upsert": lambda bf: bf.customers.upsert,
    "customers.get": lambda bf: bf.customers.get,
    "customers.list": lambda bf: bf.customers.list,
    "customers.list_all": lambda bf: bf.customers.list_all,
    "customers.delete": lambda bf: bf.customers.delete,
    "customers.contacts.list": lambda bf: bf.customers.contacts.list,
    "customers.contacts.upsert": lambda bf: bf.customers.contacts.upsert,
    "customers.contacts.delete": lambda bf: bf.customers.contacts.delete,
    "customers.products.list": lambda bf: bf.customers.products.list,
    "customers.products.attach": lambda bf: bf.customers.products.attach,
    "customers.products.detach": lambda bf: bf.customers.products.detach,
    "customers.interactions.list": lambda bf: bf.customers.interactions.list,
    "customers.interactions.list_all": lambda bf: bf.customers.interactions.list_all,
    "customers.interactions.create": lambda bf: bf.customers.interactions.create,
    "products.list": lambda bf: bf.products.list,
    "products.get": lambda bf: bf.products.get,
    "products.upsert": lambda bf: bf.products.upsert,
    "products.archive": lambda bf: bf.products.archive,
    "release_notes.list": lambda bf: bf.release_notes.list,
    "release_notes.list_all": lambda bf: bf.release_notes.list_all,
    "release_notes.get": lambda bf: bf.release_notes.get,
    "release_notes.upsert": lambda bf: bf.release_notes.upsert,
    "release_notes.publish": lambda bf: bf.release_notes.publish,
    "kb.articles.list": lambda bf: bf.kb.articles.list,
    "kb.articles.list_all": lambda bf: bf.kb.articles.list_all,
    "kb.articles.get": lambda bf: bf.kb.articles.get,
    "kb.articles.upsert": lambda bf: bf.kb.articles.upsert,
    "kb.articles.batch_upsert": lambda bf: bf.kb.articles.batch_upsert,
    "kb.articles.publish": lambda bf: bf.kb.articles.publish,
    "kb.articles.unpublish": lambda bf: bf.kb.articles.unpublish,
    "kb.articles.delete": lambda bf: bf.kb.articles.delete,
    "kb.search": lambda bf: bf.kb.search,
    "ai_agents.list": lambda bf: bf.ai_agents.list,
    "ai_agents.get": lambda bf: bf.ai_agents.get,
    "ai_agents.preview": lambda bf: bf.ai_agents.preview,
}

ERROR_TYPES = {
    "authentication": errors.AuthenticationError,
    "permission_denied": errors.PermissionDeniedError,
    "not_found": errors.NotFoundError,
    "conflict": errors.ConflictError,
    "validation": errors.ValidationError,
    "rate_limit": errors.RateLimitError,
    "server": errors.ServerError,
    "network": errors.NetworkError,
    "api": errors.BfocusError,
}


def normalize(value: Any) -> Any:
    """Retorno da SDK → JSON neutro (``Page`` vira dict; iterador vira lista)."""
    if isinstance(value, Page):
        return {
            "items": [normalize(i) for i in value.items],
            "page": value.page,
            "page_size": value.page_size,
            "total": value.total,
            "pages": value.pages,
        }
    if isinstance(value, collections.abc.Iterator):
        return [normalize(i) for i in value]
    return value


def canonical(value: Any) -> str:
    """Forma canônica: distingue ``true`` de ``1`` (em Python ``True == 1``)."""
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


class ConformanceTest(unittest.TestCase):
    server: FakeServer

    @classmethod
    def setUpClass(cls) -> None:
        cls.server = FakeServer().start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.stop()

    def assertJSONEqual(self, actual: Any, expected: Any, what: str) -> None:
        self.assertEqual(actual, expected, what)
        self.assertEqual(canonical(actual), canonical(expected), f"{what} (tipos JSON)")

    def run_case(self, case: Dict[str, Any]) -> None:
        op = case["op"]
        self.assertIn(op, OPS, f"op {op!r} sem método na SDK (e fora de sdk_excluded_ops)")
        exchanges = case["exchanges"]
        self.server.reset([ex["response"] for ex in exchanges])

        bf = Bfocus(API_KEY, base_url=self.server.base_url)
        sleeps: list = []
        bf._sleep = sleeps.append  # esperas desligadas: a suíte não dorme

        result: Any = None
        error: Any = None
        try:
            result = normalize(OPS[op](bf)(**copy.deepcopy(case["args"])))
        except errors.BfocusError as exc:
            error = exc

        self.check_exchanges(exchanges, self.server.requests)

        expect = case["expect"]
        if "error" in expect:
            want = expect["error"]
            self.assertIsNotNone(error, f"esperava erro {want['type']}, veio {result!r}")
            cls = ERROR_TYPES[want["type"]]
            self.assertIs(type(error), cls, f"classe do erro: {type(error).__name__}")
            self.assertEqual(error.code, want["code"])
            self.assertEqual(error.status, want["status"])
            if "request_id" in want:
                expected_id = want["request_id"]
                if expected_id == SENT:
                    expected_id = self.server.requests[-1]["headers"].get("x-request-id")
                    self.assertTrue(expected_id)
                self.assertEqual(error.request_id, expected_id)
            if "retry_after" in want:
                self.assertEqual(error.retry_after, want["retry_after"])
            if "required_scope" in want:
                self.assertEqual(error.required_scope, want["required_scope"])
            if "validation" in want:
                self.assertEqual(error.validation, want["validation"])
            self.assertIn(want["code"], error.message)
        else:
            self.assertIsNone(error, f"erro inesperado: {error!r}")
            self.assertJSONEqual(result, expect["result"], "resultado")

    def check_exchanges(self, exchanges: list, requests: list) -> None:
        self.assertEqual(
            len(requests),
            len(exchanges),
            "nº de requisições: " + ", ".join(f"{r['method']} {r['path']}" for r in requests),
        )
        previous_headers = None
        for index, (exchange, got) in enumerate(zip(exchanges, requests)):
            want = exchange["request"]
            where = f"troca {index}"
            headers = got["headers"]

            self.assertEqual(got["method"], want["method"], f"{where}: método")
            self.assertEqual(got["path"], want["path"], f"{where}: caminho")
            self.assertEqual(
                sorted(got["query"]), sorted(want["query"].items()), f"{where}: query"
            )
            if want["body"] is None:
                self.assertEqual(got["body"], b"", f"{where}: não devia ter corpo")
                self.assertNotIn("content-type", headers, f"{where}: Content-Type sem corpo")
            else:
                self.assertEqual(headers.get("content-type"), "application/json")
                self.assertJSONEqual(json.loads(got["body"].decode("utf-8")), want["body"],
                                     f"{where}: corpo")

            self.assertEqual(headers.get("authorization"), f"Bearer {API_KEY}")
            self.assertEqual(headers.get("accept"), "application/json")
            self.assertRegex(headers.get("x-bfocus-client", ""), CLIENT_RE)
            self.assertEqual(headers.get("user-agent"), headers.get("x-bfocus-client"))
            self.assertRegex(headers.get("x-request-id", ""), REQUEST_ID_RE)
            if want["method"] in WRITES:
                self.assertTrue(headers.get("idempotency-key"), f"{where}: Idempotency-Key")
            else:
                self.assertNotIn("idempotency-key", headers, f"{where}: Idempotency-Key em GET")

            self.assertIn("retry", exchange, f"{where}: troca sem o campo 'retry'")
            if index == 0:
                self.assertFalse(exchange["retry"], "a 1ª troca não pode ser nova tentativa")
            elif exchange["retry"]:
                # nova tentativa da MESMA chamada: ids repetidos
                self.assertEqual(headers.get("x-request-id"), previous_headers.get("x-request-id"),
                                 f"{where}: X-Request-Id da nova tentativa")
                self.assertEqual(headers.get("idempotency-key"),
                                 previous_headers.get("idempotency-key"),
                                 f"{where}: Idempotency-Key da nova tentativa")
            else:
                # chamada lógica nova (ex.: próxima página do list_all): ids novos
                self.assertNotEqual(headers.get("x-request-id"),
                                    previous_headers.get("x-request-id"),
                                    f"{where}: chamada nova precisa de X-Request-Id novo")
                if "idempotency-key" in headers:
                    self.assertNotEqual(headers["idempotency-key"],
                                        previous_headers.get("idempotency-key"))
            previous_headers = headers


def _make_test(case: Dict[str, Any]) -> Callable[[ConformanceTest], None]:
    def test(self: ConformanceTest) -> None:
        self.run_case(case)

    test.__doc__ = f"caso {case['id']}"
    return test


for _case in CASES["cases"]:
    _name = "test_case_" + re.sub(r"\W+", "_", _case["id"]).strip("_")
    assert not hasattr(ConformanceTest, _name), f"id de caso duplicado: {_case['id']}"
    setattr(ConformanceTest, _name, _make_test(_case))


class CoverageTest(unittest.TestCase):
    def test_todo_op_dos_casos_tem_metodo(self) -> None:
        missing = sorted({c["op"] for c in CASES["cases"]} - set(OPS) - EXCLUDED)
        self.assertEqual(missing, [], "ops sem método na SDK — implemente ou exclua")

    def test_helpers_apontam_para_ops_mapeados(self) -> None:
        for helper, base in HELPERS.items():
            self.assertIn(helper, OPS)
            self.assertIn(base, OPS)

    def test_excluidos_nao_estao_na_sdk(self) -> None:
        self.assertEqual(sorted(EXCLUDED & set(OPS)), [])

    @unittest.skipUnless(MONOREPO_SPEC.is_file(), "public.json só existe no monorepo")
    def test_toda_operacao_da_spec_tem_metodo(self) -> None:
        spec = json.loads(MONOREPO_SPEC.read_text(encoding="utf-8"))
        op_ids = {
            op["operationId"]
            for item in spec["paths"].values()
            for op in item.values()
            if isinstance(op, dict) and "operationId" in op
        }
        self.assertEqual(sorted(op_ids - set(OPS) - EXCLUDED), [])

    @unittest.skipUnless(MONOREPO_CASES.is_file(), "fonte dos casos só existe no monorepo")
    def test_copia_dos_casos_em_dia(self) -> None:
        self.assertEqual(
            VENDORED_CASES.read_bytes(),
            MONOREPO_CASES.read_bytes(),
            "tests/fixtures/cases.json desatualizado — rode "
            "`python3 clients/conformance/generate.py` (ele escreve a cópia; não edite à mão)",
        )


class SignatureVectorsTest(unittest.TestCase):
    def test_vetores(self) -> None:
        self.assertTrue(CASES["signatures"])
        for vector in CASES["signatures"]:
            with self.subTest(user=vector["user_external_id"]):
                got = sign_widget_identity(
                    vector["secret"], vector["user_external_id"], vector["customer_external_id"]
                )
                self.assertEqual(got, vector["expected"])
                self.assertEqual(
                    Bfocus.sign_widget_identity(
                        vector["secret"], vector["user_external_id"],
                        vector["customer_external_id"],
                    ),
                    vector["expected"],
                )


if __name__ == "__main__":
    unittest.main()
