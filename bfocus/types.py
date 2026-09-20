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
    "CustomerBatchItem",
    "PersonBatchItem",
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
    "Person",
    "PersonRevokeResult",
    "PersonUpsertResult",
    "Identifier",
    "CustomerWithIdentifiers",
    "PersonIdentifiers",
    "BatchItemResult",
    "BatchSummary",
    "BatchResult",
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
    """Campo personalizado de cliente **ou de pessoa**. Enviar a lista SUBSTITUI a lista inteira.

    Em pessoa, ``visibility`` **não** é aceito aqui: quem vê o campo é decisão do bFocus e é
    preservada entre sincronizações (o seu sistema não rebaixa nem promove a exposição de um
    dado sem querer).
    """

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


class _CustomerBatchItemRequired(TypedDict):
    external_id: str


class CustomerBatchItem(_CustomerBatchItemRequired, total=False):
    """Item do ``customers.batch``: os campos do ``customers.upsert`` + ``external_id``.

    Chave ausente = não muda; ``None`` explícito vai como ``null`` e limpa o campo.
    """

    name: Optional[str]
    document: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    website: Optional[str]
    notes: Optional[str]
    custom_fields: Optional[List[CustomFieldInput]]


class _PersonBatchItemRequired(TypedDict):
    customer_external_id: str
    external_id: str


class PersonBatchItem(_PersonBatchItemRequired, total=False):
    """Item do ``people.batch``: o cliente, o ``external_id`` da pessoa e os campos dela.

    Plano para quem chama; no fio a SDK envia
    ``{"customer_external_id": ..., "person": {"external_id": ..., ...campos}}``.
    """

    name: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    role: Optional[str]
    access: Optional[bool]
    is_primary: Optional[bool]
    extra_emails: Optional[List[str]]
    extra_phones: Optional[List[str]]
    custom_fields: Optional[List[CustomFieldInput]]
    #: Campos a APAGAR nesta pessoa (hoje ``"email"`` e/ou ``"phone"``). Apagar é explícito:
    #: ``None``, lista vazia ou chave ausente continuam significando "não mexe".
    clear: Optional[List[str]]


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
    #: O nome usado em tudo. Na PJ é o nome fantasia; a razão social fica em ``legal_name``.
    name: str
    #: Tipo do CONTRATANTE: ``"pj"`` (empresa) ou ``"pf"`` (pessoa física); ``None`` = não dá
    #: para saber. Cliente é a CONTA, não a pessoa: uma conta PF pode ter várias pessoas dentro.
    kind: Optional[Literal["pj", "pf"]]
    #: Só PJ.
    legal_name: Optional[str]
    state_registration: Optional[str]
    municipal_registration: Optional[str]
    #: Só PF: RG e órgão emissor (texto livre — o formato varia por estado).
    id_document: Optional[str]
    document: Optional[str]
    email: Optional[str]
    phone: Optional[str]
    website: Optional[str]
    notes: Optional[str]
    custom_fields: List[CustomField]
    is_active: bool
    #: Logotipo do cliente, como a equipe subiu no bFocus (``None`` = sem logotipo).
    logo_url: Optional[str]
    #: E-mails adicionais do cliente (o principal é ``email``).
    extra_emails: List[str]
    #: Telefones adicionais do cliente (o principal é ``phone``).
    extra_phones: List[str]
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


class Person(TypedDict):
    """Pessoa de um cliente (quem abre o widget/portal).

    ``external_id`` ``None`` = contato do cliente sem identificador (sem acesso).
    """

    external_id: Optional[str]
    name: str
    email: Optional[str]
    phone: Optional[str]
    role: Optional[str]
    access: bool
    is_primary: bool
    customer_external_id: str
    custom_fields: List[CustomField]
    #: Identificadores EXTRAS desta pessoa: os outros ids pelos quais ela também é encontrada.
    #: É por aqui que você descobre que o id do SEU sistema virou apelido de outra ficha.
    identifiers: List["Identifier"]


class PersonUpsertResult(Person):
    """Retorno de ``people.upsert``: a pessoa + ``status`` + ``linked``."""

    status: Literal["created", "updated", "unchanged"]
    #: ``True`` = a pessoa JÁ EXISTIA em outro cliente e este envio a ligou também a este.
    #: O cadastro é único e ela circula pelos dois; nada foi transferido nem duplicado.
    linked: bool
    #: Preenchido quando o id que você enviou é um APELIDO: este é o principal do cadastro.
    merged_into: Optional[str]


class PersonRevokeResult(Person):
    """Retorno de ``people.delete``: a pessoa + se ela apenas SAIU deste cliente.

    ``unlinked=True`` = ela continua com acesso, porque também é de outros clientes; o acesso é
    do vínculo. ``False`` = era só deste cliente e foi desligada, como sempre.
    """

    unlinked: bool


class Identifier(TypedDict):
    """Identificador extra (id de outro sistema seu ligado ao mesmo cadastro)."""

    external_id: str
    label: Optional[str]
    source: str


class CustomerWithIdentifiers(Customer):
    """Cliente + identificadores extras (o principal é ``external_id``)."""

    identifiers: List[Identifier]


class PersonIdentifiers(TypedDict):
    external_id: Optional[str]
    identifiers: List[Identifier]


class BatchItemResult(TypedDict):
    """Resultado de um item de ``customers.batch``/``people.batch``.

    ``index`` é a posição no lote enviado (0 = primeiro). ``merged_into`` preenchido = o id
    enviado é extra e este é o principal do cadastro. Em erro: ``error`` (código estável) e
    ``code`` (status HTTP que o item teria sozinho).
    """

    index: int
    status: Literal["created", "updated", "unchanged", "error"]
    external_id: Optional[str]
    merged_into: Optional[str]
    #: A pessoa já existia em outro cliente e este item a ligou também a este (cadastro único).
    linked: bool
    error: Optional[str]
    code: Optional[int]


class BatchSummary(TypedDict):
    created: int
    updated: int
    unchanged: int
    error: int


class BatchResult(TypedDict):
    """Retorno de ``customers.batch``/``people.batch``: um resultado por item + contadores."""

    results: List[BatchItemResult]
    summary: BatchSummary
