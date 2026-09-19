"""Testes unitários: lotes do batch_upsert, list_all, novas tentativas, rede, codificação."""

from __future__ import annotations

import copy
import pickle
import socket
import time
import unittest
from datetime import date, datetime, timedelta, timezone
from email.utils import format_datetime

from bfocus import (
    BATCH_MAX,
    UNSET,
    Bfocus,
    BfocusError,
    NetworkError,
    Page,
    RateLimitError,
    ServerError,
    sign_widget_identity,
    sign_widget_identity_v2,
)
from bfocus._transport import parse_retry_after

from _support import FakeServer, fail, json_body, ok


def _customer(n: int) -> dict:
    return {"id": f"id-{n}", "external_id": f"C{n}", "name": f"Cliente {n}"}


class _ServerCase(unittest.TestCase):
    server: FakeServer

    @classmethod
    def setUpClass(cls) -> None:
        cls.server = FakeServer().start()

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.stop()

    def client(self, responses: list, **kwargs) -> Bfocus:
        self.server.reset(responses)
        bf = Bfocus("bf_live_unit", base_url=self.server.base_url, **kwargs)
        self.sleeps: list = []
        bf._sleep = self.sleeps.append
        return bf

    @property
    def requests(self) -> list:
        return self.server.requests


class BatchUpsertTest(_ServerCase):
    @staticmethod
    def _chunk_response(chunk: list) -> dict:
        return ok({
            "results": [
                {"external_id": a["external_id"], "ok": True, "action": "created",
                 "error": None, "article": None}
                for a in chunk
            ],
            "created": len(chunk), "updated": 0, "unchanged": 0, "failed": 0,
        })

    def test_divide_em_lotes_de_100_e_agrega(self) -> None:
        articles = [{"external_id": f"git:a{i}", "title": f"A{i}"} for i in range(250)]
        responses = [self._chunk_response(articles[i:i + 100]) for i in range(0, 250, 100)]
        bf = self.client(responses)

        out = bf.kb.articles.batch_upsert(articles)

        self.assertEqual(len(self.requests), 3)
        bodies = [json_body(r) for r in self.requests]
        self.assertEqual([len(b["articles"]) for b in bodies], [100, 100, 50])
        self.assertEqual(
            [a["external_id"] for b in bodies for a in b["articles"]],
            [a["external_id"] for a in articles],
        )
        for r in self.requests:
            self.assertEqual(r["method"], "POST")
            self.assertEqual(r["path"], "/api/v1/integration/kb/articles/batch")
        # cada lote é uma chamada lógica: ids próprios
        self.assertEqual(len({r["headers"]["idempotency-key"] for r in self.requests}), 3)
        self.assertEqual(len({r["headers"]["x-request-id"] for r in self.requests}), 3)

        self.assertEqual([r["external_id"] for r in out["results"]],
                         [a["external_id"] for a in articles])
        self.assertEqual(
            (out["created"], out["updated"], out["unchanged"], out["failed"]), (250, 0, 0, 0)
        )

    def test_exatamente_100_vai_em_um_lote(self) -> None:
        articles = [{"external_id": f"git:a{i}"} for i in range(100)]
        bf = self.client([self._chunk_response(articles)])
        bf.kb.articles.batch_upsert(articles)
        self.assertEqual(len(self.requests), 1)

    def test_idempotency_key_do_usuario_por_lote(self) -> None:
        articles = [{"external_id": f"git:a{i}"} for i in range(150)]
        bf = self.client([self._chunk_response(articles[:100]),
                          self._chunk_response(articles[100:])])
        bf.kb.articles.batch_upsert(articles, idempotency_key="sync-42")
        self.assertEqual([r["headers"]["idempotency-key"] for r in self.requests],
                         ["sync-42", "sync-42:2"])

        many = [{"external_id": f"git:a{i}"} for i in range(250)]
        bf = self.client([self._chunk_response(many[i:i + 100]) for i in range(0, 250, 100)])
        bf.kb.articles.batch_upsert(many, idempotency_key="k")
        self.assertEqual([r["headers"]["idempotency-key"] for r in self.requests],
                         ["k", "k:2", "k:3"])

        bf = self.client([self._chunk_response(articles[:1])])
        bf.kb.articles.batch_upsert(articles[:1], idempotency_key="sync-43")
        self.assertEqual(self.requests[0]["headers"]["idempotency-key"], "sync-43")

    def test_soma_contadores_mistos(self) -> None:
        a = [{"external_id": f"git:a{i}"} for i in range(101)]
        first = ok({"results": [{"external_id": "x", "ok": True}] * 100,
                    "created": 60, "updated": 30, "unchanged": 9, "failed": 1})
        second = ok({"results": [{"external_id": "y", "ok": False}],
                     "created": 0, "updated": 0, "unchanged": 0, "failed": 1})
        out = self.client([first, second]).kb.articles.batch_upsert(a)
        self.assertEqual(len(out["results"]), 101)
        self.assertEqual(
            (out["created"], out["updated"], out["unchanged"], out["failed"]), (60, 30, 9, 2)
        )

    def test_vazio_nao_chama_a_api(self) -> None:
        out = self.client([]).kb.articles.batch_upsert([])
        self.assertEqual(self.requests, [])
        self.assertEqual(out, {"results": [], "created": 0, "updated": 0,
                               "unchanged": 0, "failed": 0})

    def test_valida_external_id_antes_de_enviar(self) -> None:
        bf = self.client([])
        with self.assertRaises(ValueError):
            bf.kb.articles.batch_upsert([{"title": "sem id"}])
        with self.assertRaises(ValueError):
            bf.kb.articles.batch_upsert([{"external_id": "docs/guia"}])
        self.assertEqual(self.requests, [])

    def test_product_null_explicito_e_preservado(self) -> None:
        article = {"external_id": "git:global", "title": "G", "product": None}
        bf = self.client([self._chunk_response([article])])
        bf.kb.articles.batch_upsert([article])
        self.assertEqual(json_body(self.requests[0]),
                         {"articles": [{"external_id": "git:global", "title": "G",
                                        "product": None}]})


class ListAllTest(_ServerCase):
    def test_percorre_todas_as_paginas(self) -> None:
        pages = [
            ok([_customer(1), _customer(2)], pagination={"page": 1, "page_size": 2, "total": 5, "pages": 3}),
            ok([_customer(3), _customer(4)], pagination={"page": 2, "page_size": 2, "total": 5, "pages": 3}),
            ok([_customer(5)], pagination={"page": 3, "page_size": 2, "total": 5, "pages": 3}),
        ]
        bf = self.client(pages)
        it = bf.customers.list_all(q="padaria", page_size=2)
        self.assertEqual(self.requests, [], "list_all é preguiçoso")
        got = [c["external_id"] for c in it]
        self.assertEqual(got, ["C1", "C2", "C3", "C4", "C5"])
        self.assertEqual(
            [dict(r["query"]) for r in self.requests],
            [{"q": "padaria", "page": str(n), "page_size": "2"} for n in (1, 2, 3)],
        )

    def test_page_size_padrao_100(self) -> None:
        bf = self.client([ok([], pagination={"page": 1, "page_size": 100, "total": 0, "pages": 0})])
        self.assertEqual(list(bf.customers.list_all()), [])
        self.assertEqual(dict(self.requests[0]["query"]), {"page": "1", "page_size": "100"})

    def test_para_em_pagina_vazia(self) -> None:
        bf = self.client([ok([], pagination={"page": 1, "page_size": 2, "total": 9, "pages": 5})])
        self.assertEqual(list(bf.customers.list_all(page_size=2)), [])
        self.assertEqual(len(self.requests), 1)

    def test_outros_list_all(self) -> None:
        one = {"page": 1, "page_size": 100, "total": 1, "pages": 1}
        bf = self.client([ok([{"id": "i"}], pagination=one)] * 3)
        self.assertEqual(len(list(bf.customers.interactions.list_all("ERP 1")))
                         + len(list(bf.release_notes.list_all("erp", published=False)))
                         + len(list(bf.kb.articles.list_all(product="erp", status="draft"))), 3)
        self.assertEqual(
            [(r["path"], dict(r["query"])) for r in self.requests],
            [
                ("/api/v1/integration/customers/ERP%201/interactions",
                 {"page": "1", "page_size": "100"}),
                ("/api/v1/integration/products/erp/release-notes",
                 {"published": "false", "page": "1", "page_size": "100"}),
                ("/api/v1/integration/kb/articles",
                 {"product": "erp", "status": "draft", "page": "1", "page_size": "100"}),
            ],
        )

    def test_page_iteravel(self) -> None:
        bf = self.client([ok([_customer(1)], pagination={"page": 1, "page_size": 1, "total": 2, "pages": 2})])
        page = bf.customers.list(page_size=1)
        self.assertIsInstance(page, Page)
        self.assertEqual([c["external_id"] for c in page], ["C1"])
        self.assertEqual(len(page), 1)
        self.assertTrue(page.has_next)


class RetryTest(_ServerCase):
    def test_backoff_exponencial_com_jitter(self) -> None:
        bf = self.client([fail(503, "X"), fail(504, "X"), ok({"deleted": True})])
        self.assertEqual(bf.customers.delete("C1"), {"deleted": True})
        self.assertEqual(len(self.sleeps), 2)
        self.assertTrue(0.5 <= self.sleeps[0] <= 0.625, self.sleeps)
        self.assertTrue(1.0 <= self.sleeps[1] <= 1.25, self.sleeps)
        keys = {r["headers"]["idempotency-key"] for r in self.requests}
        rids = {r["headers"]["x-request-id"] for r in self.requests}
        self.assertEqual((len(keys), len(rids)), (1, 1))

    def test_retry_after_tem_teto_de_60s(self) -> None:
        bf = self.client([fail(429, "RATE_LIMITED", {"Retry-After": "120"}), ok({"id": "x"})])
        bf.products.get("erp")
        self.assertEqual(self.sleeps, [60.0])

    def test_retry_after_em_503(self) -> None:
        bf = self.client([fail(503, "X", {"Retry-After": "3"}), ok({"id": "x"})])
        bf.products.get("erp")
        self.assertEqual(self.sleeps, [3.0])

    def test_500_e_4xx_nao_repetem(self) -> None:
        bf = self.client([fail(500, "INTERNAL_ERROR")])
        with self.assertRaises(ServerError):
            bf.products.get("erp")
        self.assertEqual((len(self.requests), self.sleeps), (1, []))

        bf = self.client([fail(400, "BAD_REQUEST")])
        with self.assertRaises(BfocusError) as ctx:
            bf.products.get("erp")
        self.assertIs(type(ctx.exception), BfocusError)
        self.assertEqual((len(self.requests), self.sleeps), (1, []))

    def test_max_retries_zero(self) -> None:
        bf = self.client([fail(429, "RATE_LIMITED", {"Retry-After": "2"})], max_retries=0)
        with self.assertRaises(RateLimitError) as ctx:
            bf.products.get("erp")
        self.assertEqual(ctx.exception.retry_after, 2)
        self.assertEqual((len(self.requests), self.sleeps), (1, []))

    def test_nao_json_esgotado(self) -> None:
        bad = {"status": 502, "headers": {}, "body": "Bad Gateway"}
        bf = self.client([bad, bad, bad])
        with self.assertRaises(ServerError) as ctx:
            bf.products.get("erp")
        self.assertEqual((ctx.exception.code, ctx.exception.status), ("HTTP_502", 502))
        self.assertEqual(len(self.requests), 3)

    def test_parse_retry_after(self) -> None:
        self.assertEqual(parse_retry_after("7"), 7)
        self.assertEqual(parse_retry_after("1.5"), 1.5)
        self.assertIsNone(parse_retry_after(None))
        self.assertIsNone(parse_retry_after("amanhã"))
        future = format_datetime(datetime.now(timezone.utc) + timedelta(seconds=30), usegmt=True)
        self.assertTrue(25 <= parse_retry_after(future) <= 31)


class NetworkTest(unittest.TestCase):
    def test_porta_fechada_vira_network_error(self) -> None:
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        sock.close()  # ninguém escuta nesta porta

        bf = Bfocus("bf_live_unit", base_url=f"http://127.0.0.1:{port}", timeout=2)
        sleeps: list = []
        bf._sleep = sleeps.append
        with self.assertRaises(NetworkError) as ctx:
            bf.customers.get("C1")
        err = ctx.exception
        self.assertIsInstance(err, BfocusError)
        self.assertEqual((err.status, err.code), (0, "NETWORK_ERROR"))
        self.assertEqual(len(sleeps), 2, "rede é repetida max_retries vezes")
        self.assertIn("NETWORK_ERROR", str(err))

    def test_timeout_vira_network_error(self) -> None:
        # Aceita a conexão (backlog) mas nunca responde.
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        sock.listen(8)
        try:
            port = sock.getsockname()[1]
            bf = Bfocus("bf_live_unit", base_url=f"http://127.0.0.1:{port}", max_retries=0)
            started = time.monotonic()
            with self.assertRaises(NetworkError):
                bf.customers.get("C1", timeout=0.3)  # timeout por chamada vence o do cliente
            self.assertLess(time.monotonic() - started, 5)
        finally:
            sock.close()


class EncodingTest(_ServerCase):
    def test_updated_since_datetime_vira_utc_z(self) -> None:
        brt = timezone(timedelta(hours=-3))
        cases = [
            (datetime(2026, 9, 1, 0, 0, tzinfo=brt), "2026-09-01T03:00:00Z"),
            (datetime(2026, 9, 1, 3, 0), "2026-09-01T03:00:00Z"),  # sem fuso = UTC
            (datetime(2026, 9, 1, 3, 0, 0, 250000, tzinfo=timezone.utc), "2026-09-01T03:00:00.250000Z"),
            (date(2026, 9, 1), "2026-09-01T00:00:00Z"),
            ("2026-09-01T00:00:00-03:00", "2026-09-01T00:00:00-03:00"),  # string passa como veio
        ]
        empty = {"page": 1, "page_size": 50, "total": 0, "pages": 0}
        bf = self.client([ok([], pagination=empty)] * len(cases))
        for value, _ in cases:
            bf.customers.list(updated_since=value)
        self.assertEqual([dict(r["query"])["updated_since"] for r in self.requests],
                         [want for _, want in cases])

    def test_booleano_e_omitidos_na_query(self) -> None:
        bf = self.client([ok([]), ok([])])
        bf.products.list(include_inactive=False)
        bf.products.list()
        self.assertEqual([r["query"] for r in self.requests], [[("include_inactive", "false")], []])

    def test_omitido_x_null(self) -> None:
        bf = self.client([ok({}), ok({}), ok({})])
        bf.customers.upsert("C1")
        bf.customers.upsert("C1", phone=None, name="Novo")
        bf.customers.upsert("C1", custom_fields=[])
        self.assertEqual([json_body(r) for r in self.requests],
                         [{}, {"phone": None, "name": "Novo"}, {"custom_fields": []}])
        self.assertEqual(self.requests[0]["headers"]["content-type"], "application/json")

    def test_caminho_codificado_por_segmento(self) -> None:
        bf = self.client([ok({})] * 3)
        bf.customers.get("ERP/1042 ç")
        bf.customers.contacts.delete("A B", "c?d")
        bf.release_notes.get("erp", "v2.3.0")
        self.assertEqual(
            [r["path"] for r in self.requests],
            [
                "/api/v1/integration/customers/ERP%2F1042%20%C3%A7",
                "/api/v1/integration/customers/A%20B/contacts/c%3Fd",
                "/api/v1/integration/products/erp/release-notes/v2.3.0",
            ],
        )

    def test_artigo_recusa_barra_e_ids_vazios(self) -> None:
        bf = self.client([])
        for call in (
            lambda: bf.kb.articles.get("docs/guia"),
            lambda: bf.kb.articles.upsert("a/b", title="x"),
            lambda: bf.customers.get(""),
            lambda: bf.customers.get("."),
            lambda: bf.customers.delete(".."),
            lambda: bf.customers.contacts.upsert("C1", ""),
            lambda: bf.customers.products.attach("C1", ".."),
            lambda: bf.release_notes.get("erp", "."),
            lambda: bf.release_notes.list_all(""),
            lambda: bf.customers.interactions.list_all(".."),
            lambda: bf.kb.articles.publish(".."),
        ):
            with self.assertRaises(ValueError):
                call()
        self.assertEqual(self.requests, [])

    def test_idempotency_key_por_chamada_e_so_em_escrita(self) -> None:
        bf = self.client([ok({}), ok({}), ok({})])
        bf.customers.upsert("C1", name="x", idempotency_key="minha-chave")
        bf.customers.get("C1")
        bf.customers.products.attach("C1", "erp")
        h0, h1, h2 = (r["headers"] for r in self.requests)
        self.assertEqual(h0["idempotency-key"], "minha-chave")
        self.assertNotIn("idempotency-key", h1)
        self.assertNotIn("content-type", h1)
        self.assertTrue(h2["idempotency-key"])  # PUT sem corpo continua sendo escrita
        self.assertNotIn("content-type", h2)
        self.assertEqual(self.requests[2]["body"], b"")

    def test_corpo_utf8(self) -> None:
        bf = self.client([ok({})])
        bf.customers.interactions.create("C1", "Pedido faturado — ação ✓", is_internal=False)
        self.assertEqual(json_body(self.requests[0]),
                         {"content": "Pedido faturado — ação ✓", "is_internal": False})


class ClientTest(unittest.TestCase):
    def test_chave_vazia_e_erro_de_argumento(self) -> None:
        for bad in ("", "   "):
            with self.assertRaises(ValueError) as ctx:
                Bfocus(bad)
            self.assertNotIsInstance(ctx.exception, BfocusError)
        with self.assertRaises(TypeError):
            Bfocus(None)  # type: ignore[arg-type]

    def test_padroes_e_sem_rede_na_construcao(self) -> None:
        bf = Bfocus("bf_live_unit")
        self.assertEqual(bf.base_url, "https://api.bfocus.com.br")
        self.assertEqual((bf.timeout, bf.max_retries), (30.0, 2))
        bf = Bfocus("bf_live_unit", base_url="http://127.0.0.1:1/", timeout=5, max_retries=0)
        self.assertEqual(bf.base_url, "http://127.0.0.1:1")
        self.assertNotIn("bf_live_unit", repr(bf))

    def test_opcoes_invalidas(self) -> None:
        with self.assertRaises(ValueError):
            Bfocus("k", max_retries=-1)
        with self.assertRaises(ValueError):
            Bfocus("k", timeout=0)

    def test_unset(self) -> None:
        self.assertEqual(repr(UNSET), "UNSET")
        self.assertFalse(UNSET)
        self.assertIs(copy.deepcopy(UNSET), UNSET)
        self.assertIs(pickle.loads(pickle.dumps(UNSET)), UNSET)

    def test_assinatura_str_e_bytes(self) -> None:
        a = sign_widget_identity("bf_whs_x", "USR-1", "ACME-1")
        self.assertEqual(a, sign_widget_identity(b"bf_whs_x", "USR-1", "ACME-1"))
        self.assertRegex(a, r"^[0-9a-f]{64}$")
        with self.assertRaises(ValueError):
            sign_widget_identity("", "u", "c")


class ErrorShapeTest(_ServerCase):
    def test_mensagem_e_campos(self) -> None:
        bf = self.client([{
            "status": 403,
            "headers": {"X-Required-Scope": "kb:write"},
            "body": {"code": 403, "data": None, "message": "INTEGRATION_SCOPE_MISSING",
                     "error": "INTEGRATION_SCOPE_MISSING", "validation": {},
                     "request_id": "req-9"},
        }])
        with self.assertRaises(BfocusError) as ctx:
            bf.kb.articles.publish("git:x")
        err = ctx.exception
        self.assertEqual(err.required_scope, "kb:write")
        self.assertIn("kb:write", err.message)
        self.assertIn("req-9", str(err))
        self.assertIsNone(err.retry_after)

    def test_2xx_sem_envelope_e_invalid_response(self) -> None:
        bodies = [
            {"status": 200, "headers": {}, "body": "<html>proxy</html>"},
            {"status": 200, "headers": {}, "body": None},  # corpo vazio
            {"status": 200, "headers": {}, "body": {"id": "sem envelope"}},
            {"status": 201, "headers": {"X-Request-Id": "req-do-header"}, "body": [1, 2]},
        ]
        bf = self.client(bodies)
        got = []
        for _ in bodies:
            with self.assertRaises(BfocusError) as ctx:
                bf.products.get("erp")
            got.append(ctx.exception)
        for err, record in zip(got, self.requests):
            self.assertIs(type(err), BfocusError)
            self.assertEqual(err.code, "INVALID_RESPONSE")
            self.assertIn("INVALID_RESPONSE", err.message)
        self.assertEqual([e.status for e in got], [200, 200, 200, 201])
        self.assertEqual([e.request_id for e in got[:3]],
                         [r["headers"]["x-request-id"] for r in self.requests[:3]])
        self.assertEqual(got[3].request_id, "req-do-header")

    def test_request_id_cai_para_o_enviado(self) -> None:
        bf = self.client([{"status": 404, "headers": {}, "body": "Not Found"},
                          {"status": 409, "headers": {}, "body": {"code": 409, "error": "X"}}])
        for _ in range(2):
            with self.assertRaises(BfocusError) as ctx:
                bf.products.get("erp")
            self.assertEqual(ctx.exception.request_id,
                             self.requests[-1]["headers"]["x-request-id"])

    def test_code_cai_para_message(self) -> None:
        bf = self.client([{"status": 404, "headers": {},
                           "body": {"code": 404, "message": "TENANT_NOT_FOUND"}}])
        with self.assertRaises(BfocusError) as ctx:
            bf.products.list()
        self.assertEqual(ctx.exception.code, "TENANT_NOT_FOUND")
        self.assertEqual(ctx.exception.validation, {})


def _batch_ok(n: int) -> dict:
    return ok({
        "results": [
            {"index": i, "status": "created", "external_id": f"x{i}", "merged_into": None,
             "error": None, "code": None}
            for i in range(n)
        ],
        "summary": {"created": n, "updated": 0, "unchanged": 0, "error": 0},
    })


class PeopleAndBatchTest(_ServerCase):
    def test_limite_de_500_sem_requisicao(self) -> None:
        self.assertEqual(BATCH_MAX, 500)
        bf = self.client([])
        customers = [{"external_id": f"erp-{i}", "name": f"C{i}"} for i in range(501)]
        people = [{"customer_external_id": "erp-1", "external_id": f"app-{i}", "name": "P"}
                  for i in range(501)]
        with self.assertRaises(ValueError) as ctx:
            bf.customers.batch(customers)
        self.assertIn("customers.batch aceita até 500 itens por chamada (recebeu 501)",
                      str(ctx.exception))
        with self.assertRaises(ValueError) as ctx:
            bf.people.batch(people)
        self.assertIn("people.batch aceita até 500 itens por chamada (recebeu 501)",
                      str(ctx.exception))
        self.assertEqual(self.requests, [])

    def test_500_vai_em_uma_requisicao(self) -> None:
        customers = [{"external_id": f"erp-{i}", "name": f"C{i}"} for i in range(500)]
        people = [{"customer_external_id": "erp-1", "external_id": f"app-{i}"}
                  for i in range(500)]
        bf = self.client([_batch_ok(500), _batch_ok(500)])
        out = bf.customers.batch(customers)
        bf.people.batch(people)
        self.assertEqual(len(self.requests), 2)
        self.assertEqual([r["path"] for r in self.requests],
                         ["/api/v1/integration/customers/batch",
                          "/api/v1/integration/people/batch"])
        self.assertEqual([len(json_body(r)["items"]) for r in self.requests], [500, 500])
        self.assertEqual(out["summary"]["created"], 500)
        self.assertEqual(json_body(self.requests[1])["items"][0],
                         {"customer_external_id": "erp-1", "person": {"external_id": "app-0"}})

    def test_lote_vazio_nao_chama_a_api(self) -> None:
        bf = self.client([])
        empty = {"results": [], "summary": {"created": 0, "updated": 0, "unchanged": 0,
                                            "error": 0}}
        self.assertEqual(bf.customers.batch([]), empty)
        self.assertEqual(bf.people.batch(iter([])), empty)
        self.assertEqual(self.requests, [])

    def test_lote_valida_itens_antes_de_enviar(self) -> None:
        bf = self.client([])
        with self.assertRaises(ValueError):
            bf.customers.batch([{"external_id": "ok"}, {"name": "sem id"}])
        with self.assertRaises(ValueError):
            bf.people.batch([{"external_id": "app-1"}])  # sem customer_external_id
        with self.assertRaises(TypeError):
            bf.people.batch(["app-1"])
        with self.assertRaises(TypeError):
            bf.customers.batch({"external_id": "x"})
        self.assertEqual(self.requests, [])

    def test_lote_idempotency_key_e_omitido_x_null(self) -> None:
        bf = self.client([_batch_ok(1)])
        bf.customers.batch([{"external_id": "erp-1", "phone": None, "notes": UNSET}],
                           idempotency_key="carga-1")
        self.assertEqual(self.requests[0]["headers"]["idempotency-key"], "carga-1")
        self.assertEqual(json_body(self.requests[0]),
                         {"items": [{"external_id": "erp-1", "phone": None}]})

    def test_people_upsert_corpo_e_caminho(self) -> None:
        bf = self.client([ok({"external_id": "app-1", "status": "updated"})])
        bf.people.upsert("erp 1042", "app 1", access=True, extra_phones=("+55 11 9",),
                         email=None)
        record = self.requests[0]
        self.assertEqual(record["path"], "/api/v1/integration/customers/erp%201042/people/app%201")
        self.assertEqual(json_body(record),
                         {"person": {"access": True, "email": None,
                                     "extra_phones": ["+55 11 9"]}})
        with self.assertRaises(TypeError):
            bf.people.upsert("erp-1", "app-1", extra_emails="a@b.example")
        with self.assertRaises(ValueError):
            bf.people.upsert("erp-1", "..")

    def test_identifiers_label_none_explicito(self) -> None:
        bf = self.client([ok({"external_id": "app-1", "identifiers": []})])
        bf.people.identifiers.add("app-1", "crm-5", label=None)
        self.assertEqual(json_body(self.requests[0]), {"label": None})


class SignatureV2Test(unittest.TestCase):
    VECTOR = ("bf_whs_x", "USR-1", "ACME-1")
    EXPECTED = "v2.1789000000.bfbf2a0390fbb9d65f268899acce2b4d7a2606ba13bb25b453ff3a7971fbd7be"

    def test_instante_int_float_datetime(self) -> None:
        self.assertEqual(sign_widget_identity_v2(*self.VECTOR, now=1789000000), self.EXPECTED)
        self.assertEqual(sign_widget_identity_v2(*self.VECTOR, now=1789000000.9), self.EXPECTED)
        when = datetime.fromtimestamp(1789000000, tz=timezone.utc)
        self.assertEqual(sign_widget_identity_v2(*self.VECTOR, now=when), self.EXPECTED)
        self.assertEqual(sign_widget_identity_v2(*self.VECTOR, now=when.replace(tzinfo=None)),
                         self.EXPECTED)
        brt = when.astimezone(timezone(timedelta(hours=-3)))
        self.assertEqual(sign_widget_identity_v2(*self.VECTOR, now=brt), self.EXPECTED)

    def test_padrao_e_agora(self) -> None:
        got = sign_widget_identity_v2(*self.VECTOR)
        prefix, ts, digest = got.split(".")
        self.assertEqual(prefix, "v2")
        self.assertLessEqual(abs(int(ts) - time.time()), 5)
        self.assertRegex(digest, r"^[0-9a-f]{64}$")
        self.assertEqual(got, sign_widget_identity_v2(*self.VECTOR, now=int(ts)))

    def test_validacao(self) -> None:
        with self.assertRaises(ValueError):
            sign_widget_identity_v2("bf_whs_x", "app:1", "ACME-1")
        self.assertTrue(sign_widget_identity_v2("bf_whs_x", "app-1", "erp-1042", now=1)
                        .startswith("v2.1."))
        with self.assertRaises(ValueError):
            sign_widget_identity_v2("", "USR-1", "ACME-1")
        with self.assertRaises(ValueError):
            sign_widget_identity_v2("bf_whs_x", "USR-1", "ACME-1", now=-1)
        with self.assertRaises(TypeError):
            sign_widget_identity_v2("bf_whs_x", "USR-1", "ACME-1", now="1789000000")  # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            sign_widget_identity_v2("bf_whs_x", "USR-1", "ACME-1", 1789000000)  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()
