"""Recursos da API pública: ``customers``, ``products``, ``release_notes``, ``kb``, ``ai_agents``.

Convenções (iguais em todos os métodos):

* Argumentos obrigatórios são posicionais; os opcionais são **keyword-only**.
* Campos de corpo opcionais têm padrão :data:`~bfocus.types.UNSET` — não informado = não
  enviado. ``None`` explícito vai como ``null`` e **limpa** o campo na API.
* Filtros de query com ``None`` são omitidos.
* Toda chamada aceita ``timeout=`` (segundos, por tentativa); as escritas aceitam
  ``idempotency_key=`` (senão a SDK gera uma e a repete nas novas tentativas).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import (
    Any,
    Callable,
    Dict,
    Iterator,
    List,
    Mapping,
    Optional,
    Sequence,
    TypeVar,
    Union,
    cast,
)

from ._transport import Transport, compact, path_segment
from .types import (
    UNSET,
    AgentPreview,
    AgentTurn,
    AIAgent,
    Contact,
    Customer,
    CustomFieldInput,
    Deleted,
    Interaction,
    KBArticle,
    KBArticleSummary,
    KBBatchItem,
    KBBatchOutcome,
    KBSearchHit,
    MaybeUnset,
    Page,
    Product,
    ProductRef,
    ReleaseNote,
)

T = TypeVar("T")
DateLike = Union[datetime, date, str]

__all__ = [
    "Customers",
    "CustomerContacts",
    "CustomerProducts",
    "CustomerInteractions",
    "Products",
    "ReleaseNotes",
    "KnowledgeBase",
    "KBArticles",
    "AIAgents",
]


def _page(data: Any, pagination: Optional[Mapping[str, Any]]) -> Page[Any]:
    items = list(data or [])
    if not pagination:  # a API sempre manda; defensivo para não quebrar a iteração
        return Page(items=items, page=1, page_size=len(items), total=len(items), pages=1)
    return Page(
        items=items,
        page=int(pagination.get("page", 1)),
        page_size=int(pagination.get("page_size", len(items))),
        total=int(pagination.get("total", len(items))),
        pages=int(pagination.get("pages", 1)),
    )


def _iterate(fetch: Callable[[int], Page[T]]) -> Iterator[T]:
    page = 1
    while True:
        current = fetch(page)
        for item in current.items:
            yield item
        if not current.items or current.page >= current.pages:
            return
        page += 1


def _dicts(value: Any) -> Any:
    """Lista de mapeamentos → lista de dicts (preserva UNSET/None)."""
    if value is UNSET or value is None:
        return value
    return [dict(item) for item in value]


class _Resource:
    def __init__(self, transport: Transport) -> None:
        self._t = transport


# ── clientes ────────────────────────────────────────────────────────────────────


class CustomerContacts(_Resource):
    """Contatos (pessoas) de um cliente — ``client.customers.contacts``."""

    def list(self, external_id: str, *, timeout: Optional[float] = None) -> List[Contact]:
        """Contatos do cliente. ``GET /customers/{external_id}/contacts``"""
        ext = path_segment(external_id, "external_id")
        data, _ = self._t.request("GET", f"/customers/{ext}/contacts", timeout=timeout)
        return cast(List[Contact], data)

    def upsert(
        self,
        external_id: str,
        contact_external_id: str,
        *,
        name: MaybeUnset[Optional[str]] = UNSET,
        role: MaybeUnset[Optional[str]] = UNSET,
        email: MaybeUnset[Optional[str]] = UNSET,
        phone: MaybeUnset[Optional[str]] = UNSET,
        notes: MaybeUnset[Optional[str]] = UNSET,
        is_primary: MaybeUnset[Optional[bool]] = UNSET,
        idempotency_key: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> Contact:
        """Cria ou atualiza um contato pelo ``external_id`` dele. Só o que vier muda.

        ``PUT /customers/{external_id}/contacts/{contact_external_id}``
        """
        ext = path_segment(external_id, "external_id")
        cext = path_segment(contact_external_id, "contact_external_id")
        body = compact(
            {
                "name": name,
                "role": role,
                "email": email,
                "phone": phone,
                "notes": notes,
                "is_primary": is_primary,
            }
        )
        data, _ = self._t.request(
            "PUT",
            f"/customers/{ext}/contacts/{cext}",
            body=body,
            idempotency_key=idempotency_key,
            timeout=timeout,
        )
        return cast(Contact, data)

    def delete(
        self,
        external_id: str,
        contact_external_id: str,
        *,
        idempotency_key: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> Deleted:
        """Remove um contato. ``DELETE /customers/{external_id}/contacts/{contact_external_id}``"""
        ext = path_segment(external_id, "external_id")
        cext = path_segment(contact_external_id, "contact_external_id")
        data, _ = self._t.request(
            "DELETE",
            f"/customers/{ext}/contacts/{cext}",
            idempotency_key=idempotency_key,
            timeout=timeout,
        )
        return cast(Deleted, data)


class CustomerProducts(_Resource):
    """Produtos vinculados a um cliente — ``client.customers.products``."""

    def list(self, external_id: str, *, timeout: Optional[float] = None) -> List[ProductRef]:
        """Produtos do cliente. ``GET /customers/{external_id}/products``"""
        ext = path_segment(external_id, "external_id")
        data, _ = self._t.request("GET", f"/customers/{ext}/products", timeout=timeout)
        return cast(List[ProductRef], data)

    def attach(
        self,
        external_id: str,
        product_slug: str,
        *,
        idempotency_key: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> ProductRef:
        """Vincula um produto ao cliente (idempotente). ``PUT /customers/{external_id}/products/{slug}``"""
        ext = path_segment(external_id, "external_id")
        slug = path_segment(product_slug, "product_slug")
        data, _ = self._t.request(
            "PUT",
            f"/customers/{ext}/products/{slug}",
            idempotency_key=idempotency_key,
            timeout=timeout,
        )
        return cast(ProductRef, data)

    def detach(
        self,
        external_id: str,
        product_slug: str,
        *,
        idempotency_key: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> Deleted:
        """Desvincula um produto. ``DELETE /customers/{external_id}/products/{slug}``"""
        ext = path_segment(external_id, "external_id")
        slug = path_segment(product_slug, "product_slug")
        data, _ = self._t.request(
            "DELETE",
            f"/customers/{ext}/products/{slug}",
            idempotency_key=idempotency_key,
            timeout=timeout,
        )
        return cast(Deleted, data)


class CustomerInteractions(_Resource):
    """Histórico de interações de um cliente — ``client.customers.interactions``."""

    def list(
        self,
        external_id: str,
        *,
        page: Optional[int] = None,
        page_size: Optional[int] = None,
        timeout: Optional[float] = None,
    ) -> Page[Interaction]:
        """Uma página de interações. ``GET /customers/{external_id}/interactions``"""
        ext = path_segment(external_id, "external_id")
        data, pagination = self._t.request(
            "GET",
            f"/customers/{ext}/interactions",
            query={"page": page, "page_size": page_size},
            timeout=timeout,
        )
        return cast(Page[Interaction], _page(data, pagination))

    def list_all(
        self,
        external_id: str,
        *,
        page_size: int = 100,
        timeout: Optional[float] = None,
    ) -> Iterator[Interaction]:
        """Todas as interações, página a página (gerador preguiçoso)."""
        path_segment(external_id, "external_id")
        return _iterate(
            lambda n: self.list(external_id, page=n, page_size=page_size, timeout=timeout)
        )

    def create(
        self,
        external_id: str,
        content: str,
        *,
        is_internal: MaybeUnset[bool] = UNSET,
        author_email: MaybeUnset[Optional[str]] = UNSET,
        idempotency_key: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> Interaction:
        """Registra uma interação (nota) no cliente. ``POST /customers/{external_id}/interactions``

        Args:
            content: Texto/HTML da interação.
            is_internal: Nota interna (padrão da API: ``True``).
            author_email: E-mail de um usuário do bFocus para constar como autor.
        """
        ext = path_segment(external_id, "external_id")
        body = compact(
            {"content": content, "is_internal": is_internal, "author_email": author_email}
        )
        data, _ = self._t.request(
            "POST",
            f"/customers/{ext}/interactions",
            body=body,
            idempotency_key=idempotency_key,
            timeout=timeout,
        )
        return cast(Interaction, data)


class Customers(_Resource):
    """Clientes (empresas) — ``client.customers``.

    Sub-recursos: :attr:`contacts`, :attr:`products`, :attr:`interactions`.
    """

    def __init__(self, transport: Transport) -> None:
        super().__init__(transport)
        self.contacts = CustomerContacts(transport)
        self.products = CustomerProducts(transport)
        self.interactions = CustomerInteractions(transport)

    def upsert(
        self,
        external_id: str,
        *,
        name: MaybeUnset[Optional[str]] = UNSET,
        document: MaybeUnset[Optional[str]] = UNSET,
        email: MaybeUnset[Optional[str]] = UNSET,
        phone: MaybeUnset[Optional[str]] = UNSET,
        website: MaybeUnset[Optional[str]] = UNSET,
        notes: MaybeUnset[Optional[str]] = UNSET,
        custom_fields: MaybeUnset[Optional[Sequence[CustomFieldInput]]] = UNSET,
        idempotency_key: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> Customer:
        """Cria ou atualiza um cliente pelo ``external_id`` do seu sistema.

        ``PUT /customers/{external_id}``. Só os campos informados mudam; ``None`` limpa.
        ``custom_fields``, quando enviado, **substitui** a lista inteira.
        """
        ext = path_segment(external_id, "external_id")
        body = compact(
            {
                "name": name,
                "document": document,
                "email": email,
                "phone": phone,
                "website": website,
                "notes": notes,
                "custom_fields": _dicts(custom_fields),
            }
        )
        data, _ = self._t.request(
            "PUT", f"/customers/{ext}", body=body,
            idempotency_key=idempotency_key, timeout=timeout,
        )
        return cast(Customer, data)

    def get(self, external_id: str, *, timeout: Optional[float] = None) -> Customer:
        """Um cliente. ``GET /customers/{external_id}``"""
        ext = path_segment(external_id, "external_id")
        data, _ = self._t.request("GET", f"/customers/{ext}", timeout=timeout)
        return cast(Customer, data)

    def list(
        self,
        *,
        q: Optional[str] = None,
        updated_since: Optional[DateLike] = None,
        page: Optional[int] = None,
        page_size: Optional[int] = None,
        timeout: Optional[float] = None,
    ) -> Page[Customer]:
        """Uma página de clientes. ``GET /customers``

        Args:
            q: Busca por nome/documento/e-mail.
            updated_since: Só os alterados a partir deste instante (``datetime`` vira
                ISO 8601 UTC com ``Z``; string passa como veio).
        """
        data, pagination = self._t.request(
            "GET",
            "/customers",
            query={"q": q, "updated_since": updated_since, "page": page, "page_size": page_size},
            timeout=timeout,
        )
        return cast(Page[Customer], _page(data, pagination))

    def list_all(
        self,
        *,
        q: Optional[str] = None,
        updated_since: Optional[DateLike] = None,
        page_size: int = 100,
        timeout: Optional[float] = None,
    ) -> Iterator[Customer]:
        """Todos os clientes, página a página (gerador preguiçoso).

        Ideal para sincronização incremental: guarde o instante da última rodada e passe
        em ``updated_since``.
        """
        return _iterate(
            lambda n: self.list(
                q=q, updated_since=updated_since, page=n, page_size=page_size, timeout=timeout
            )
        )

    def delete(
        self,
        external_id: str,
        *,
        idempotency_key: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> Deleted:
        """Exclui um cliente. ``DELETE /customers/{external_id}``"""
        ext = path_segment(external_id, "external_id")
        data, _ = self._t.request(
            "DELETE", f"/customers/{ext}", idempotency_key=idempotency_key, timeout=timeout
        )
        return cast(Deleted, data)


# ── produtos ────────────────────────────────────────────────────────────────────


class Products(_Resource):
    """Catálogo de produtos — ``client.products``."""

    def list(
        self, *, include_inactive: Optional[bool] = None, timeout: Optional[float] = None
    ) -> List[Product]:
        """Produtos do catálogo. ``GET /products``

        Args:
            include_inactive: ``True`` inclui os arquivados.
        """
        data, _ = self._t.request(
            "GET", "/products", query={"include_inactive": include_inactive}, timeout=timeout
        )
        return cast(List[Product], data)

    def get(self, slug: str, *, timeout: Optional[float] = None) -> Product:
        """Um produto. ``GET /products/{slug}``"""
        data, _ = self._t.request(
            "GET", f"/products/{path_segment(slug, 'slug')}", timeout=timeout
        )
        return cast(Product, data)

    def upsert(
        self,
        slug: str,
        *,
        name: MaybeUnset[Optional[str]] = UNSET,
        description: MaybeUnset[Optional[str]] = UNSET,
        color: MaybeUnset[Optional[str]] = UNSET,
        icon: MaybeUnset[Optional[str]] = UNSET,
        is_active: MaybeUnset[Optional[bool]] = UNSET,
        sort_order: MaybeUnset[Optional[int]] = UNSET,
        idempotency_key: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> Product:
        """Cria ou atualiza um produto pelo ``slug``. ``PUT /products/{slug}``"""
        body = compact(
            {
                "name": name,
                "description": description,
                "color": color,
                "icon": icon,
                "is_active": is_active,
                "sort_order": sort_order,
            }
        )
        data, _ = self._t.request(
            "PUT", f"/products/{path_segment(slug, 'slug')}", body=body,
            idempotency_key=idempotency_key, timeout=timeout,
        )
        return cast(Product, data)

    def archive(
        self,
        slug: str,
        *,
        idempotency_key: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> Product:
        """Arquiva um produto (não apaga). ``DELETE /products/{slug}``"""
        data, _ = self._t.request(
            "DELETE", f"/products/{path_segment(slug, 'slug')}",
            idempotency_key=idempotency_key, timeout=timeout,
        )
        return cast(Product, data)


# ── release notes ───────────────────────────────────────────────────────────────


class ReleaseNotes(_Resource):
    """Release notes por produto — ``client.release_notes``."""

    @staticmethod
    def _base(product_slug: str) -> str:
        return f"/products/{path_segment(product_slug, 'product_slug')}/release-notes"

    def list(
        self,
        product_slug: str,
        *,
        published: Optional[bool] = None,
        page: Optional[int] = None,
        page_size: Optional[int] = None,
        timeout: Optional[float] = None,
    ) -> Page[ReleaseNote]:
        """Uma página de release notes. ``GET /products/{slug}/release-notes``

        Args:
            published: ``True`` só publicadas, ``False`` só rascunhos, ``None`` todas.
        """
        data, pagination = self._t.request(
            "GET",
            self._base(product_slug),
            query={"published": published, "page": page, "page_size": page_size},
            timeout=timeout,
        )
        return cast(Page[ReleaseNote], _page(data, pagination))

    def list_all(
        self,
        product_slug: str,
        *,
        published: Optional[bool] = None,
        page_size: int = 100,
        timeout: Optional[float] = None,
    ) -> Iterator[ReleaseNote]:
        """Todas as release notes do produto, página a página (gerador preguiçoso)."""
        self._base(product_slug)
        return _iterate(
            lambda n: self.list(
                product_slug, published=published, page=n, page_size=page_size, timeout=timeout
            )
        )

    def get(
        self, product_slug: str, version: str, *, timeout: Optional[float] = None
    ) -> ReleaseNote:
        """Uma release note. ``GET /products/{slug}/release-notes/{version}``"""
        ver = path_segment(version, "version")
        data, _ = self._t.request("GET", f"{self._base(product_slug)}/{ver}", timeout=timeout)
        return cast(ReleaseNote, data)

    def upsert(
        self,
        product_slug: str,
        version: str,
        *,
        title: MaybeUnset[Optional[str]] = UNSET,
        description_html: MaybeUnset[Optional[str]] = UNSET,
        description_markdown: MaybeUnset[Optional[str]] = UNSET,
        audience: MaybeUnset[Optional[str]] = UNSET,
        require_ack_internal: MaybeUnset[Optional[bool]] = UNSET,
        require_ack_external: MaybeUnset[Optional[bool]] = UNSET,
        publish: MaybeUnset[bool] = UNSET,
        idempotency_key: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> ReleaseNote:
        """Cria ou atualiza a release note de uma versão (SemVer, aceita ``v`` na frente).

        ``PUT /products/{slug}/release-notes/{version}``. Com ``publish=True`` já publica —
        é o caminho para publicar direto do CI.

        Args:
            audience: ``"internal"``, ``"external"`` ou ``"both"``.
            description_markdown: Alternativa a ``description_html`` (a API converte).
        """
        ver = path_segment(version, "version")
        body = compact(
            {
                "title": title,
                "description_html": description_html,
                "description_markdown": description_markdown,
                "audience": audience,
                "require_ack_internal": require_ack_internal,
                "require_ack_external": require_ack_external,
                "publish": publish,
            }
        )
        data, _ = self._t.request(
            "PUT", f"{self._base(product_slug)}/{ver}", body=body,
            idempotency_key=idempotency_key, timeout=timeout,
        )
        return cast(ReleaseNote, data)

    def publish(
        self,
        product_slug: str,
        version: str,
        *,
        idempotency_key: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> ReleaseNote:
        """Publica uma release note. ``POST /products/{slug}/release-notes/{version}/publish``"""
        ver = path_segment(version, "version")
        data, _ = self._t.request(
            "POST", f"{self._base(product_slug)}/{ver}/publish",
            idempotency_key=idempotency_key, timeout=timeout,
        )
        return cast(ReleaseNote, data)


# ── base de conhecimento ────────────────────────────────────────────────────────


def _article_id(external_id: str) -> str:
    return path_segment(external_id, "external_id", allow_slash=False)


class KBArticles(_Resource):
    """Artigos da base de conhecimento — ``client.kb.articles``."""

    #: Limite da API por requisição de ``batch_upsert``; a SDK divide acima disso.
    BATCH_SIZE = 100

    def list(
        self,
        *,
        product: Optional[str] = None,
        status: Optional[str] = None,
        q: Optional[str] = None,
        updated_since: Optional[DateLike] = None,
        page: Optional[int] = None,
        page_size: Optional[int] = None,
        timeout: Optional[float] = None,
    ) -> Page[KBArticleSummary]:
        """Uma página de artigos (resumo, sem ``body_html``). ``GET /kb/articles``

        Args:
            product: Slug do produto.
            status: ``"draft"`` ou ``"published"``.
            q: Busca no título e no texto.
            updated_since: ``datetime`` (vira ISO UTC com ``Z``) ou string.
        """
        data, pagination = self._t.request(
            "GET",
            "/kb/articles",
            query={
                "product": product,
                "status": status,
                "q": q,
                "updated_since": updated_since,
                "page": page,
                "page_size": page_size,
            },
            timeout=timeout,
        )
        return cast(Page[KBArticleSummary], _page(data, pagination))

    def list_all(
        self,
        *,
        product: Optional[str] = None,
        status: Optional[str] = None,
        q: Optional[str] = None,
        updated_since: Optional[DateLike] = None,
        page_size: int = 100,
        timeout: Optional[float] = None,
    ) -> Iterator[KBArticleSummary]:
        """Todos os artigos (com os filtros), página a página (gerador preguiçoso)."""
        return _iterate(
            lambda n: self.list(
                product=product, status=status, q=q, updated_since=updated_since,
                page=n, page_size=page_size, timeout=timeout,
            )
        )

    def get(self, external_id: str, *, timeout: Optional[float] = None) -> KBArticle:
        """Um artigo (com ``body_html``). ``GET /kb/articles/{external_id}``"""
        data, _ = self._t.request(
            "GET", f"/kb/articles/{_article_id(external_id)}", timeout=timeout
        )
        return cast(KBArticle, data)

    def upsert(
        self,
        external_id: str,
        *,
        title: MaybeUnset[Optional[str]] = UNSET,
        body_html: MaybeUnset[Optional[str]] = UNSET,
        body_markdown: MaybeUnset[Optional[str]] = UNSET,
        product: MaybeUnset[Optional[str]] = UNSET,
        status: MaybeUnset[Optional[str]] = UNSET,
        idempotency_key: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> KBArticle:
        """Cria ou atualiza um artigo pelo ``external_id`` (sem ``/``; use ``:``).

        ``PUT /kb/articles/{external_id}``. ``product=None`` (explícito) torna o artigo
        global; ``status="published"`` publica.
        """
        body = compact(
            {
                "title": title,
                "body_html": body_html,
                "body_markdown": body_markdown,
                "product": product,
                "status": status,
            }
        )
        data, _ = self._t.request(
            "PUT", f"/kb/articles/{_article_id(external_id)}", body=body,
            idempotency_key=idempotency_key, timeout=timeout,
        )
        return cast(KBArticle, data)

    def batch_upsert(
        self,
        articles: Sequence[Union[KBBatchItem, Mapping[str, Any]]],
        *,
        idempotency_key: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> KBBatchOutcome:
        """Cria/atualiza **qualquer quantidade** de artigos. ``POST /kb/articles/batch``

        A SDK divide em lotes de 100 (limite da API), envia em sequência e devolve UM
        resultado: ``results`` na ordem enviada e contadores somados. Falha de um item
        não derruba os outros (``ok=False`` + ``error`` no resultado dele).

        Cada item precisa de ``external_id``; os demais campos seguem a regra do
        :meth:`upsert` (ausente = não muda; ``product: None`` = global).

        Se um lote falhar por inteiro (rede, 429 esgotado…), a exceção sobe e os lotes
        anteriores já foram aplicados — rodar de novo é seguro (é upsert).

        Args:
            idempotency_key: O 1º lote usa a chave como veio; os seguintes, ``"<chave>:<n>"``
                (n = 2, 3, …). Sem chave, cada lote gera a sua.
        """
        items: List[Dict[str, Any]] = []
        for index, article in enumerate(articles):
            if not isinstance(article, Mapping):
                raise TypeError(f"articles[{index}] precisa ser um dict.")
            ext = article.get("external_id")
            if not isinstance(ext, str) or not ext:
                raise ValueError(f"articles[{index}]: external_id é obrigatório.")
            if "/" in ext:
                raise ValueError(
                    f"articles[{index}]: external_id não aceita '/' — use ':' ({ext!r})"
                )
            items.append(dict(article))

        outcome: Dict[str, Any] = {
            "results": [], "created": 0, "updated": 0, "unchanged": 0, "failed": 0,
        }
        chunks = [items[i:i + self.BATCH_SIZE] for i in range(0, len(items), self.BATCH_SIZE)]
        for number, chunk in enumerate(chunks, start=1):
            key = idempotency_key
            if key and number > 1:
                key = f"{key}:{number}"
            data, _ = self._t.request(
                "POST", "/kb/articles/batch", body={"articles": chunk},
                idempotency_key=key, timeout=timeout,
            )
            data = data or {}
            for field, value in data.items():
                if field == "results":
                    outcome["results"].extend(value or [])
                elif isinstance(value, int) and not isinstance(value, bool):
                    outcome[field] = int(outcome.get(field) or 0) + value
                else:  # campo novo não numérico: preservado (o último lote vence)
                    outcome[field] = value
        return cast(KBBatchOutcome, outcome)

    def publish(
        self,
        external_id: str,
        *,
        idempotency_key: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> KBArticle:
        """Publica um artigo. ``POST /kb/articles/{external_id}/publish``"""
        data, _ = self._t.request(
            "POST", f"/kb/articles/{_article_id(external_id)}/publish",
            idempotency_key=idempotency_key, timeout=timeout,
        )
        return cast(KBArticle, data)

    def unpublish(
        self,
        external_id: str,
        *,
        idempotency_key: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> KBArticle:
        """Volta um artigo para rascunho. ``POST /kb/articles/{external_id}/unpublish``"""
        data, _ = self._t.request(
            "POST", f"/kb/articles/{_article_id(external_id)}/unpublish",
            idempotency_key=idempotency_key, timeout=timeout,
        )
        return cast(KBArticle, data)

    def delete(
        self,
        external_id: str,
        *,
        idempotency_key: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> Deleted:
        """Exclui um artigo. ``DELETE /kb/articles/{external_id}``"""
        data, _ = self._t.request(
            "DELETE", f"/kb/articles/{_article_id(external_id)}",
            idempotency_key=idempotency_key, timeout=timeout,
        )
        return cast(Deleted, data)


class KnowledgeBase(_Resource):
    """Base de conhecimento — ``client.kb`` (artigos em :attr:`articles`)."""

    def __init__(self, transport: Transport) -> None:
        super().__init__(transport)
        self.articles = KBArticles(transport)

    def search(
        self,
        q: str,
        *,
        product: Optional[str] = None,
        limit: Optional[int] = None,
        timeout: Optional[float] = None,
    ) -> List[KBSearchHit]:
        """Busca semântica/textual nos artigos publicados. ``GET /kb/search``

        Args:
            q: Pergunta ou termos.
            product: Slug do produto para restringir.
            limit: Máximo de resultados (padrão da API: 5; máximo 20).
        """
        data, _ = self._t.request(
            "GET", "/kb/search", query={"q": q, "product": product, "limit": limit},
            timeout=timeout,
        )
        return cast(List[KBSearchHit], data)


# ── agentes de IA ───────────────────────────────────────────────────────────────


class AIAgents(_Resource):
    """Agentes de IA — ``client.ai_agents``."""

    def list(self, *, timeout: Optional[float] = None) -> List[AIAgent]:
        """Agentes de IA da conta. ``GET /ai-agents``"""
        data, _ = self._t.request("GET", "/ai-agents", timeout=timeout)
        return cast(List[AIAgent], data)

    def get(self, agent_id: str, *, timeout: Optional[float] = None) -> AIAgent:
        """Um agente. ``GET /ai-agents/{agent_id}``"""
        data, _ = self._t.request(
            "GET", f"/ai-agents/{path_segment(agent_id, 'agent_id')}", timeout=timeout
        )
        return cast(AIAgent, data)

    def preview(
        self,
        agent_id: str,
        message: str,
        *,
        history: MaybeUnset[Sequence[AgentTurn]] = UNSET,
        idempotency_key: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> AgentPreview:
        """Testa a resposta do agente a uma mensagem (consome IA da conta).

        ``POST /ai-agents/{agent_id}/preview``

        Args:
            history: Turnos anteriores, ``[{"role": "customer"|"bot", "content": ...}]``
                (até 20).
        """
        body = compact({"message": message, "history": _dicts(history)})
        data, _ = self._t.request(
            "POST", f"/ai-agents/{path_segment(agent_id, 'agent_id')}/preview", body=body,
            idempotency_key=idempotency_key, timeout=timeout,
        )
        return cast(AgentPreview, data)
