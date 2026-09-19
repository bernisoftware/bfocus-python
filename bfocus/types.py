"""Tipos da SDK do bFocus.

As respostas são ``dict`` comuns anotados com ``TypedDict``: campos que a API passar a
devolver no futuro continuam no dicionário (nunca viram erro). ``Page`` é o retorno das
listas paginadas.
"""

from dataclasses import dataclass
from typing import Any, Dict, Generic, Iterator, List, Literal, Optional, TypedDict, TypeVar, Union

__all__ = [
    "UNSET",
    "Unset",
    "MaybeUnset",
    "Page",
    # entradas
    "CustomFieldInput",
    "KBBatchItem",
    "AgentTurn",
    # saídas
    "CustomField",
    "Customer",
    "Contact",
    "ProductRef",
    "Product",
    "Interaction",
    "ReleaseNote",
    "KBArticleSummary",
    "KBArticle",
    "KBSearchHit",
    "KBBatchResult",
    "KBBatchOutcome",
    "AIAgent",
    "AgentPreview",
    "Deleted",
]

T = TypeVar("T")


# ── "omitido" x "null" ───────────────────────────────────────────────────────────


class Unset:
    """Marca de argumento **não informado** (diferente de ``None``, que envia ``null``).

    Os upserts são parciais: só o que você passa muda; ``None`` explícito LIMPA o campo.
    Você nunca precisa usar esta classe — ela é o valor padrão dos kwargs opcionais.
    """

    _instance: "Optional[Unset]" = None

    def __new__(cls) -> "Unset":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "UNSET"

    def __bool__(self) -> bool:
        return False

    def __copy__(self) -> "Unset":
        return self

    def __deepcopy__(self, memo: Any) -> "Unset":
        return self

    def __reduce__(self) -> str:
        return "UNSET"


#: Valor padrão dos kwargs opcionais de corpo: "não envie este campo".
UNSET = Unset()

#: ``MaybeUnset[Optional[str]]`` = ``str`` | ``None`` (envia ``null``) | não informado.
MaybeUnset = Union[T, Unset]


# ── paginação ───────────────────────────────────────────────────────────────────


@dataclass
class Page(Generic[T]):
    """Uma página de resultados. Iterável sobre ``items``.

    Para percorrer tudo sem controlar páginas, use o ``list_all(...)`` do recurso.
    """

    items: List[T]
    page: int
    page_size: int
    total: int
    pages: int

    def __iter__(self) -> Iterator[T]:
        return iter(self.items)

    def __len__(self) -> int:
        return len(self.items)

    @property
    def has_next(self) -> bool:
        """``True`` se existe página depois desta."""
        return self.page < self.pages


# ── entradas ────────────────────────────────────────────────────────────────────


class _CustomFieldInputRequired(TypedDict):
    key: str


class CustomFieldInput(_CustomFieldInputRequired, total=False):
    """Campo personalizado de cliente. Enviar a lista SUBSTITUI a lista inteira."""

    label: str
    type: Literal[
        "text", "textarea", "email", "phone", "url", "number", "date", "datetime",
        "bool", "select", "file",
    ]
    value: Any
    options: Optional[List[str]]


class _KBBatchItemRequired(TypedDict):
    external_id: str


class KBBatchItem(_KBBatchItemRequired, total=False):
    """Item do ``kb.articles.batch_upsert``. ``product: None`` torna o artigo global."""

    title: Optional[str]
    body_html: Optional[str]
    body_markdown: Optional[str]
    product: Optional[str]
    status: Optional[Literal["draft", "published"]]


class AgentTurn(TypedDict):
    """Turno do histórico de ``ai_agents.preview``."""

    role: Literal["customer", "bot"]
    content: str


# ── saídas ──────────────────────────────────────────────────────────────────────


class CustomField(TypedDict):
    key: str
    label: Optional[str]
    type: str
    value: Any
    visibility: str


class Customer(TypedDict):
    id: str
    external_id: str
    name: str
    document: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    website: Optional[str]
    notes: Optional[str]
    custom_fields: List[CustomField]
    is_active: bool
    created_at: Optional[str]
    updated_at: Optional[str]


class Contact(TypedDict):
    id: str
    external_id: Optional[str]
    name: str
    role: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    notes: Optional[str]
    is_primary: bool
    created_at: Optional[str]
    updated_at: Optional[str]


class ProductRef(TypedDict):
    id: str
    slug: str
    name: str
    is_active: bool


class Product(TypedDict):
    id: str
    slug: str
    name: str
    description: Optional[str]
    color: Optional[str]
    icon: Optional[str]
    is_active: bool
    sort_order: int
    current_version: str
    ai_level: str
    created_at: Optional[str]
    updated_at: Optional[str]


class Interaction(TypedDict):
    id: str
    content: str
    is_internal: bool
    author_kind: str
    author_name: Optional[str]
    created_at: Optional[str]


class ReleaseNote(TypedDict):
    id: str
    product: str
    version: str
    title: str
    description_html: str
    audience: str
    is_published: bool
    require_ack_internal: bool
    require_ack_external: bool
    published_at: Optional[str]
    created_at: Optional[str]
    updated_at: Optional[str]


class KBArticleSummary(TypedDict):
    """Artigo sem o corpo — itens de ``kb.articles.list``/``list_all`` e do ``batch_upsert``."""

    id: str
    external_id: Optional[str]
    product: Optional[str]
    title: str
    excerpt: str
    status: str
    origin: str
    published_at: Optional[str]
    created_at: Optional[str]
    updated_at: Optional[str]


class KBArticle(KBArticleSummary):
    """Artigo completo (``get``/``upsert``/``publish``/``unpublish``): resumo + ``body_html``."""

    body_html: Optional[str]


class KBSearchHit(TypedDict):
    id: str
    external_id: Optional[str]
    title: str
    excerpt: str


class KBBatchResult(TypedDict):
    external_id: str
    ok: bool
    action: Optional[Literal["created", "updated", "unchanged"]]
    error: Optional[str]
    article: Optional[KBArticleSummary]


class KBBatchOutcome(TypedDict):
    """Resultado agregado de ``batch_upsert`` (todos os lotes, na ordem enviada)."""

    results: List[KBBatchResult]
    created: int
    updated: int
    unchanged: int
    failed: int


class AIAgent(TypedDict):
    id: str
    name: str
    product: ProductRef
    active: bool
    persona: Optional[str]
    scope: Optional[str]
    avatar_url: Optional[str]
    created_at: Optional[str]
    updated_at: Optional[str]


class AgentPreview(TypedDict):
    """Resposta simulada do agente. ``action``: ``answer``, ``handoff`` ou ``refuse``."""

    action: str
    answer_html: Optional[str]
    escalated: bool
    refused: bool
    handoff_reason: Optional[str]
    confidence: Optional[float]
    topic: Optional[str]
    guards: List[str]
    citations: List[Any]
    sources: List[Dict[str, Any]]
    collected: Dict[str, Any]
    missing: List[Any]


class Deleted(TypedDict):
    deleted: bool
