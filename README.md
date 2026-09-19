# bfocus

SDK oficial em **Python** da API pública do [bFocus](https://bfocus.com.br): clientes, produtos,
release notes, base de conhecimento e agentes de IA.

Zero dependências (só biblioteca padrão) · Python 3.9+ · tipada (`py.typed`) · novas tentativas e
idempotência automáticas.

## Instalação

```bash
pip install bfocus==0.1.0
```

## Hello world

```python
from bfocus import Bfocus

bf = Bfocus("bf_live_...")

cliente = bf.customers.upsert("ERP 1042", name="Padaria Estrela", email="contato@padaria.example")
print(cliente["id"], cliente["name"])
```

`upsert` cria ou atualiza pelo `external_id` do **seu** sistema — rodar de novo não duplica.

## Autenticação

Crie a chave no bFocus em **Integrações → Chaves de API**, marcando só os escopos de que a
integração precisa. Ela vai em `Authorization: Bearer <chave>` em toda requisição (a SDK cuida disso).

| Escopo | Permite |
| --- | --- |
| `customers:read` | Ler clientes, contatos, produtos vinculados e interações |
| `customers:write` | Cadastrar, atualizar e excluir clientes, contatos e interações |
| `products:read` | Ler o catálogo de produtos |
| `products:write` | Cadastrar, atualizar e arquivar produtos |
| `kb:read` | Ler e buscar artigos da base de conhecimento |
| `kb:write` | Criar, atualizar, publicar e excluir artigos da base de conhecimento |
| `ai_agents:read` | Ler os agentes de IA |
| `ai_agents:preview` | Testar a resposta de um agente de IA (consome IA da conta) |
| `release_notes:read` | Ler release notes |
| `release_notes:write` | Criar, atualizar e publicar release notes |

A chave legada (`bf_sk_…`) só alcança clientes (`customers:*`). Guarde a chave fora do código:

```python
import os
from bfocus import Bfocus

bf = Bfocus(
    os.environ["BFOCUS_API_KEY"],
    base_url="https://api.bfocus.com.br",  # padrão; em dev: "http://localhost:8000"
    timeout=30,                            # segundos, por tentativa
    max_retries=2,                         # novas tentativas além da primeira (0 desliga)
)
```

Construir o cliente não faz nenhuma chamada de rede.

## Como os métodos funcionam

- **Retorno desembrulhado**: o método devolve o `data` da resposta, como `dict` (anotado com
  `TypedDict` — veja `bfocus.types`). Campos novos que a API passar a devolver aparecem no dict;
  nunca viram erro.
- **Listas paginadas** devolvem `Page` (`items`, `page`, `page_size`, `total`, `pages`), que é
  iterável. Para percorrer tudo, use `list_all(...)` (clientes, interações, release notes e
  artigos): um gerador preguiçoso que busca página por página (`page_size` padrão 100) e para na
  última página ou numa página vazia.
- **Só o que você passa muda.** Os upserts são parciais: argumento não informado não é enviado;
  `None` explícito vai como `null` e **limpa** o campo.

  ```python
  bf.customers.upsert("ERP 1042", phone="11 3333-4444")  # só o telefone muda
  bf.customers.upsert("ERP 1042", phone=None)            # apaga o telefone
  ```

- Obrigatórios são posicionais; opcionais são nomeados. Toda chamada aceita `timeout=`; as de
  escrita aceitam `idempotency_key=` (veja [Novas tentativas](#novas-tentativas-e-idempotência)).
- Datas (`updated_since`) aceitam `datetime` — convertido para ISO 8601 em UTC com `Z`; sem fuso é
  tratado como UTC — ou string, que passa como veio.

## Clientes

```python
from datetime import datetime, timedelta, timezone

bf.customers.upsert(
    "ERP 1042",
    name="Padaria Estrela",
    document="12.345.678/0001-90",
    custom_fields=[{"key": "plano", "label": "Plano", "value": "ouro"}],  # substitui a lista
)

cliente = bf.customers.get("ERP 1042")

pagina = bf.customers.list(q="padaria", page=1, page_size=50)
print(pagina.total, [c["name"] for c in pagina])

# Sincronização incremental: tudo o que mudou desde a última rodada, todas as páginas.
desde = datetime.now(timezone.utc) - timedelta(hours=1)
for c in bf.customers.list_all(updated_since=desde):
    print(c["external_id"], c["updated_at"])

bf.customers.delete("ERP 1042")
```

### Contatos, produtos vinculados e interações

```python
bf.customers.contacts.upsert("ERP 1042", "CT-1", name="Ana Souza", role="Financeiro",
                             email="ana@padaria.example", is_primary=True)
bf.customers.contacts.list("ERP 1042")
bf.customers.contacts.delete("ERP 1042", "CT-1")

bf.customers.products.attach("ERP 1042", "erp-cloud")
bf.customers.products.list("ERP 1042")
bf.customers.products.detach("ERP 1042", "erp-cloud")

bf.customers.interactions.create("ERP 1042", "Pedido 1042 faturado.",
                                 author_email="carla@suaempresa.com.br")
for i in bf.customers.interactions.list_all("ERP 1042"):
    print(i["created_at"], i["content"])
```

## Produtos

```python
bf.products.upsert("erp-cloud", name="ERP Cloud", description="Gestão na nuvem", color="#6366F1")
bf.products.get("erp-cloud")
bf.products.list(include_inactive=True)
bf.products.archive("erp-cloud")  # arquiva, não apaga
```

## Release notes — publicar direto do CI

Um passo no pipeline de release: cria ou atualiza a nota da versão e já publica.

```python
# scripts/publicar_release_note.py — roda no CI a cada tag
import os
import pathlib

from bfocus import Bfocus

bf = Bfocus(os.environ["BFOCUS_API_KEY"])  # escopo release_notes:write
versao = os.environ["GITHUB_REF_NAME"]     # "v2.3.0" — o "v" na frente é aceito

bf.release_notes.upsert(
    "erp-cloud",
    versao,
    title=f"Versão {versao.lstrip('v')}",
    description_markdown=pathlib.Path(f"release-notes/{versao}.md").read_text(encoding="utf-8"),
    audience="external",  # "internal" | "external" | "both"
    publish=True,         # cria/atualiza e publica numa chamada só
)
```

Rodar de novo para a mesma versão atualiza a nota (é upsert). Também há:

```python
bf.release_notes.get("erp-cloud", "2.3.0")
bf.release_notes.list("erp-cloud", published=False)  # rascunhos
bf.release_notes.publish("erp-cloud", "2.3.0")
```

## Base de conhecimento — sincronizar a partir de arquivos Markdown

Mantenha a documentação no repositório e sincronize a cada push. `batch_upsert` aceita **qualquer
quantidade** de artigos: a SDK divide em lotes de 100 (o limite da API), envia em sequência e
devolve um único resultado.

```python
import os
import pathlib

from bfocus import Bfocus

bf = Bfocus(os.environ["BFOCUS_API_KEY"])  # escopos kb:read e kb:write
docs = pathlib.Path("docs")

artigos = []
for arquivo in sorted(docs.rglob("*.md")):
    texto = arquivo.read_text(encoding="utf-8")
    titulo = next((l[2:].strip() for l in texto.splitlines() if l.startswith("# ")), arquivo.stem)
    artigos.append({
        # id estável e SEM "/": o caminho do arquivo com ":" no lugar das barras.
        # Aceita letras, números e . _ : ~ @ + = -
        "external_id": "git:" + ":".join(arquivo.relative_to(docs).with_suffix("").parts),
        "title": titulo,
        "body_markdown": texto,
        "product": "erp-cloud",  # ou None (explícito) para um artigo global
    })

res = bf.kb.articles.batch_upsert(artigos)
print(f"{res['created']} criados, {res['updated']} atualizados, "
      f"{res['unchanged']} sem mudança, {res['failed']} com falha")

for r in res["results"]:          # na mesma ordem enviada
    if not r["ok"]:
        print("falhou:", r["external_id"], r["error"])  # ex.: KB_ARTICLE_TITLE_REQUIRED
    elif r["action"] in ("created", "updated"):
        bf.kb.articles.publish(r["external_id"])        # publica o que entrou ou mudou

# Remove do bFocus o que saiu do repositório.
locais = {a["external_id"] for a in artigos}
for artigo in bf.kb.articles.list_all(product="erp-cloud"):
    ext = artigo["external_id"] or ""
    if ext.startswith("git:") and ext not in locais:
        bf.kb.articles.delete(ext)
```

Um item com problema não derruba os outros: ele volta com `ok=False` e o motivo em `error`. Para
publicar já no lote, mande `"status": "published"` em cada item. Artigo a artigo:

```python
bf.kb.articles.upsert("notion:emitir-nfse", title="Como emitir NFS-e",
                      body_markdown="# Passo a passo\n\n1. Abra o menu **Fiscal**",
                      product=None, status="published")
bf.kb.articles.get("notion:emitir-nfse")          # artigo completo, com body_html
bf.kb.articles.list(status="draft", q="nota")     # Page de resumos (sem body_html)
bf.kb.articles.unpublish("notion:emitir-nfse")
bf.kb.articles.delete("notion:emitir-nfse")
```

### Busca

```python
for hit in bf.kb.search("como emitir nota fiscal", product="erp-cloud", limit=3):
    print(hit["title"], "—", hit["excerpt"])
```

## Agentes de IA

```python
agentes = bf.ai_agents.list()
agente = bf.ai_agents.get(agentes[0]["id"])

resposta = bf.ai_agents.preview(
    agente["id"],
    "Como emito uma NFS-e?",
    history=[{"role": "customer", "content": "Oi"},
             {"role": "bot", "content": "Olá! Como posso ajudar?"}],
)
print(resposta["action"], resposta["answer_html"], resposta["sources"])
```

`preview` consome IA da conta (escopo `ai_agents:preview`).

## Erros

Qualquer resposta fora de 2xx levanta `BfocusError` (ou uma subclasse):

| Classe | Quando |
| --- | --- |
| `AuthenticationError` | 401 — chave ausente, inválida ou revogada |
| `PermissionDeniedError` | 403 — chave desligada, IP não liberado ou escopo faltando (`required_scope`) |
| `NotFoundError` | 404 |
| `ConflictError` | 409 — ex.: `KB_ARTICLE_EMPTY`, `AI_DISABLED` |
| `ValidationError` | 422 — motivos por campo em `validation` |
| `RateLimitError` | 429 — `retry_after` em segundos (depois de esgotar as novas tentativas) |
| `ServerError` | 5xx |
| `NetworkError` | conexão/timeout — `status == 0`, `code == "NETWORK_ERROR"` |

**Decida pelo `code`** — ele é estável (`CUSTOMER_NOT_FOUND`, `INTEGRATION_SCOPE_MISSING`,
`VALIDATION_ERROR`…). O `message` é texto para humanos e pode mudar. Ao falar com o suporte,
informe o `request_id`: ele vem do corpo da resposta, senão do header `X-Request-Id`, senão é o id
que a própria SDK enviou (a API ecoa o do cliente) — então está sempre preenchido, inclusive em
`NetworkError`.

Se uma resposta 2xx chegar sem o envelope JSON da API (um proxy devolvendo HTML, corpo vazio), a
SDK não devolve `None` calado: levanta `BfocusError` com `code == "INVALID_RESPONSE"` e o status
recebido. Corpo de erro que não é JSON vira `code == "HTTP_<status>"`.

```python
from bfocus import BfocusError, NotFoundError

try:
    bf.customers.get("ERP 9999")
except NotFoundError:
    print("não existe")
except BfocusError as err:
    if err.code == "INTEGRATION_SCOPE_MISSING":
        print("a chave não tem o escopo", err.required_scope)
    elif err.code == "VALIDATION_ERROR":
        print(err.validation)             # {"email": "value is not a valid email address"}
    else:
        print(err.code, err.status, err.request_id)
```

Argumento inválido no seu código (chave vazia; parâmetro de caminho vazio, `"."` ou `".."`; `/`
no `external_id` de um artigo) levanta `ValueError`/`TypeError` na hora, sem chamar a API.

## Novas tentativas e idempotência

A SDK tenta de novo sozinha em **erro de rede/timeout, 429, 502, 503 e 504** — até `max_retries`
vezes (padrão 2). Espera o `Retry-After` quando a API manda (teto de 60 s); senão 0,5 s, 1 s, 2 s…
(teto de 8 s) + até 25% de variação aleatória. Um 500 ou outro 4xx volta na hora.

Toda escrita (POST/PUT/DELETE) leva um `Idempotency-Key`, e **a mesma chave vai em todas as
tentativas** da chamada: se a primeira chegou a executar e só a resposta se perdeu, a API devolve a
resposta original (`Idempotent-Replayed: true`) em vez de executar de novo. O `X-Request-Id` também
se repete, para o suporte ver as tentativas como uma chamada só.

Para que a proteção valha também quando o **seu** processo roda de novo (um job reexecutado), passe
uma chave derivada do evento:

```python
bf.customers.interactions.create(
    "ERP 1042", "Pedido 1042 faturado.",
    idempotency_key="pedido-1042-faturado",
)
```

A mesma chave com outra requisição volta `IDEMPOTENCY_KEY_REUSED`. No `batch_upsert`, o 1º lote
usa a sua chave como veio e os seguintes `"<chave>:2"`, `"<chave>:3"`… (sem chave, cada lote gera
a sua).

## Identidade do widget

Para o widget de atendimento reconhecer o usuário logado, o **seu backend** assina a identidade
dele com o segredo do widget (que nunca vai para o navegador). É local — sem rede e sem chave de API:

```python
import os
from bfocus import sign_widget_identity

assinatura = sign_widget_identity(
    os.environ["BFOCUS_WIDGET_SECRET"],
    user_external_id="USR-1",          # o usuário no seu sistema
    customer_external_id="ERP 1042",   # a empresa (cliente) dele
)
# HMAC-SHA256 em hex minúsculo de "v1:USR-1:ERP 1042" — entregue junto dos dois ids à página
# que abre o widget.
```

## Versões

**Fixe a versão exata** (`bfocus==0.1.0` no `requirements.txt` / `pyproject.toml`) e suba de uma
versão para a outra de propósito. Cada release declara se muda a superfície pública (`additive` ou
`breaking: …`), então dá para saber o que revisar antes de subir.

A SDK se identifica em toda requisição (`X-Bfocus-Client: bfocus-python/<versão>`): quando uma
correção exigir atualizar, o bFocus avisa as contas que rodam a versão afetada.

## Exemplo

Um script rodável está em [`examples/quickstart.py`](examples/quickstart.py):

```bash
BFOCUS_API_KEY=bf_live_... python examples/quickstart.py
```

## Licença

MIT © Berni Software
