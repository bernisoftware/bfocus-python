# bfocus

SDK oficial em **Python** da API pública do [bFocus](https://bfocus.com.br): clientes, pessoas dos
clientes, produtos, release notes, base de conhecimento e agentes de IA.

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
| `customers:read` | Ler clientes, contatos, pessoas, produtos vinculados e interações |
| `customers:write` | Cadastrar, atualizar e excluir clientes, contatos, pessoas, identificadores extras e interações (inclui os lotes) |
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

## Recursos e métodos

| Recurso | Métodos |
| --- | --- |
| `bf.customers` | `upsert`, `get`, `list`, `list_all`, `delete`, `batch` |
| `bf.customers.contacts` | `list`, `upsert`, `delete` |
| `bf.customers.products` | `list`, `attach`, `detach` |
| `bf.customers.interactions` | `list`, `list_all`, `create` |
| `bf.customers.identifiers` | `add`, `remove` |
| `bf.people` | `upsert`, `list`, `delete`, `batch` |
| `bf.people.identifiers` | `list`, `add`, `remove` |
| `bf.products` | `list`, `get`, `upsert`, `archive` |
| `bf.release_notes` | `list`, `list_all`, `get`, `upsert`, `publish` |
| `bf.kb` | `search` |
| `bf.kb.articles` | `list`, `list_all`, `get`, `upsert`, `batch_upsert`, `publish`, `unpublish`, `delete` |
| `bf.ai_agents` | `list`, `get`, `preview` |
| `bfocus` (funções) | `sign_widget_identity`, `sign_widget_identity_v2` (locais, sem rede) |

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

## Pessoas

Pessoas são quem usa o sistema do seu cliente e abre chamados/conversas no widget. O
`external_id` da pessoa é o mesmo `user_external_id` que você assina para o widget — por isso
**não pode ter `:`**.

```python
p = bf.people.upsert(
    "erp-1042",                 # o cliente
    "app-77",                   # a pessoa (o usuário no seu sistema)
    name="Paula Reis",
    email="paula@padaria.example",
    role="Financeiro",
    is_primary=True,
    extra_emails=["paula.reis@pessoal.example"],  # somam aos que já existem
)
print(p["status"])              # "created", "updated" ou "unchanged"

for pessoa in bf.people.list("erp-1042"):
    print(pessoa["name"], pessoa["access"])

bf.people.delete("erp-1042", "app-77")                # retira o acesso
bf.people.upsert("erp-1042", "app-77", access=True)   # devolve o acesso
```

- **Nunca duplica**: se o e-mail (ou o telefone) já pertence a uma pessoa que chegou por e-mail
  ou por outro sistema, ela é **adotada** e ganha o seu `external_id`.
- A mesma pessoa informada com **outro cliente** NÃO é transferida: ela é **ligada** também a
  esse cliente e a resposta volta com `linked=True`. O cadastro é único e a mesma pessoa circula
  por vários clientes e vários produtos.
- **O acesso é do vínculo.** `delete` (e `access=False`) tira o acesso dela NESTE cliente, não nos
  outros: `unlinked=True` na resposta quer dizer que ela segue ativa em algum outro.
- `delete` **retira o acesso** (devolve a pessoa com `access=False`); ela continua no histórico
  de chamados e conversas. Um `upsert` com `access=True` devolve o acesso.
- Como nos outros upserts, só o que você passa muda; `name` é obrigatório ao criar.

### Campos personalizados da pessoa

`custom_fields` leva o que só existe no seu sistema (matrícula, centro de custo, filial). É a
**exceção** ao "só o que vier muda": a lista enviada **substitui a lista inteira** — campo que
ficar de fora é **removido**. Mande sempre a lista que o seu sistema tem hoje; omitir o argumento não mexe
em nada, como em qualquer outro campo.

A `visibility` é decidida no bFocus e **preservada entre sincronizações** — por isso ela não vai
no envio, só volta na resposta: o seu ERP não rebaixa nem promove a exposição de um dado sem
querer.

Vale no upsert de pessoa, no lote de pessoas e na listagem de pessoas do cliente.

```python
p = bf.people.upsert(
    "erp-1042",
    "app-77",
    custom_fields=[                      # a lista INTEIRA do seu sistema
        {"key": "matricula", "label": "Matrícula", "value": "4471"},
        {"key": "filial", "label": "Filial", "value": "Centro"},
    ],
)
for campo in p["custom_fields"]:
    print(campo["key"], campo["value"], campo["visibility"])   # visibility vem do bFocus
```

### Apagar o e-mail ou o telefone da pessoa

Um contato gravado errado ficava preso para sempre: enquanto a ficha errada segurasse o
telefone, nenhum reenvio o soltava. `clear` apaga.

```python
bf.people.upsert("erp-1042", "app-77", clear=["phone"])          # some o telefone
bf.people.upsert("erp-1042", "app-77", clear=["email", "phone"]) # some os dois
```

Três regras que parecem contraintuitivas e são de propósito:

- **Apagar é explícito.** `phone=None`, `clear=[]` e não passar o argumento continuam
  significando **"não mexe"** — a SDK não traduz `None` em `clear`. Fazer o `None` apagar
  teria apagado, em silêncio e na primeira carga seguinte, o dado de todo sistema que manda
  `None` para "não tenho esse valor".
- **Campo fora da lista é recusado, não ignorado**: hoje só `"email"` e `"phone"`; qualquer
  outro devolve 422 `PERSON_CLEAR_FIELD_INVALID` (`ValidationError`).
- **Só se limpa a própria ficha.** Se você alcançou a pessoa por um identificador **extra**, a
  API recusa com 409 `PERSON_CLEAR_NOT_OWN_RECORD` (`ConflictError`): apagar o contato de uma
  ficha alcançada por apelido seria apagar dado de outro sistema. Para saber se o id que você
  tem em mãos é o principal ou um extra, use `bf.people.identifiers.list(...)`.

Vale no `people.upsert` e no `people.batch` (`{"clear": ["phone"]}` no item).

### Contato já usado: um 409 que você consegue resolver

`PERSON_EMAIL_TAKEN` e `PERSON_PHONE_TAKEN` (409) não são "tente de novo": o e-mail (ou o
telefone) já é de outra pessoa da conta. O erro diz **de quem**, em `err.data` (a API repete o mesmo
detalhe em `err.validation`, por compatibilidade):

| campo | o que é |
| --- | --- |
| `field` | `email` ou `phone` — qual contato está tomado |
| `owner_external_id` | o identificador da pessoa que já usa esse contato |
| `owner_name` | o nome dela |
| `owner_customer_external_id` | o cliente a que ela pertence |

**É o `owner_customer_external_id` que decide a ação**, e os dois casos pedem coisas opostas:

- **mesmo cliente que você enviou** → é quase sempre a MESMA pessoa em dois sistemas. Uma pessoa
  tem **N identificadores**: registre o seu como **extra** dela. A partir daí o seu id encontra
  essa pessoa.
- **outro cliente** → ninguém decide sozinho a quem a pessoa pertence. Não force: registre o caso
  e leve para quem conhece o cadastro. Unificar dois clientes é decisão de gente, não de um
  casamento por e-mail.

```python
from bfocus import ConflictError

try:
    bf.people.upsert("erp-1042", "app-77", name="Paula Reis", email="paula@padaria.example")
except ConflictError as err:
    if err.code not in ("PERSON_EMAIL_TAKEN", "PERSON_PHONE_TAKEN"):
        raise
    dono = err.data
    if dono.get("owner_customer_external_id") == "erp-1042":
        # A mesma pessoa, com dois ids: o seu vira mais um identificador dela.
        bf.people.identifiers.add(dono["owner_external_id"], "app-77", label="ERP")
    else:
        # Dono em OUTRO cliente: não decida sozinho — registre e leve para o cadastro.
        avisar_cadastro(err.code, dono)
```

`PERSON_CONTACT_OTHER_CUSTOMER` (409) é o mesmo assunto pelo outro lado, e é **recusa
definitiva**: a API não move mais uma pessoa de um cliente para outro só porque o e-mail (ou o
telefone) casou. Repetir a chamada não resolve — trate como caso para o cadastro, nunca como
falha temporária.

## Lotes

`customers.batch` e `people.batch` criam/atualizam **até 500 itens por chamada** (`bfocus.BATCH_MAX`).
Acima disso a SDK levanta `ValueError` antes de chamar a API — ela **não** divide sozinha, porque
o `index` de cada resultado é a posição no lote que você enviou. Divida em fatias:

```python
from bfocus import BATCH_MAX

clientes = [
    {"external_id": "erp-1042", "name": "Padaria Estrela", "document": "12.345.678/0001-90"},
    {"external_id": "erp-1043", "name": "Mercado Sol", "email": "contato@mercadosol.example"},
    # ... quantos forem
]

for inicio in range(0, len(clientes), BATCH_MAX):
    fatia = clientes[inicio:inicio + BATCH_MAX]
    res = bf.customers.batch(fatia)
    print(res["summary"])  # {"created": 1, "updated": 1, "unchanged": 0, "error": 0}
    for r in res["results"]:
        if r["status"] == "error":
            item = fatia[r["index"]]             # index = posição NESTA fatia
            print("falhou:", item["external_id"], r["error"], r["code"])  # ex.: NAME_REQUIRED 422
        elif r["merged_into"]:
            print(fatia[r["index"]]["external_id"], "é extra; o principal é", r["merged_into"])
```

- Item de `customers.batch`: os campos do `customers.upsert` + `external_id` (obrigatório).
  Chave ausente não muda; `None` limpa.
- Item de `people.batch` (plano): `customer_external_id` + `external_id` da pessoa + os campos
  do `people.upsert`:

  ```python
  bf.people.batch([
      {"customer_external_id": "erp-1042", "external_id": "app-77",
       "name": "Paula Reis", "email": "paula@padaria.example", "is_primary": True},
      {"customer_external_id": "erp-1043", "external_id": "app-78", "name": "Rui Lima"},
  ])
  ```

- Resultado por item: `index`, `status` (`created`, `updated`, `unchanged` ou `error`),
  `external_id`, `merged_into` (o id enviado é extra: este é o principal), `error` (código
  estável) e `code` (status HTTP que o item teria sozinho); mais `summary` com os contadores.
- **Um item com erro não desfaz os outros.** Lista vazia devolve o resultado zerado sem fazer
  requisição.

## Identificadores extras

Ligue o id de **outro** sistema seu (CRM, e-commerce…) ao mesmo cadastro, sem duplicar. É
idempotente; se o id já pertence a outro cadastro, a API responde 409 `IDENTIFIER_IN_USE`
(`ConflictError`).

```python
c = bf.customers.identifiers.add("erp-1042", "crm-88", label="CRM")
print(c["identifiers"])   # [{"external_id": "crm-88", "label": "CRM", "source": "api"}]
bf.customers.identifiers.remove("erp-1042", "crm-88")

bf.people.identifiers.add("app-77", "crm-p5")       # sem label
bf.people.identifiers.remove("app-77", "crm-p5")
```

Num lote, um item enviado com um id extra volta com o principal em `merged_into`.

### Ler os identificadores da pessoa (para reconciliar)

`bf.people.list(...)` mostra só o identificador **principal** de cada pessoa. Quando dois
cadastros seus eram a mesma pessoa, um dos ids virou **extra** — e some da listagem sem ter
sumido do cadastro. É isso que faz a sua conferência fechar "633 de 636" sem explicar os 3.

`people.identifiers.list` é a fonte de verdade dessa conferência, e é **leitura**: antes dela
era preciso ESCREVER (tentar um `add`) para descobrir o que tinha acontecido. Aceita no
caminho o id principal **ou qualquer um dos extras**.

```python
ids = bf.people.identifiers.list("crm-p5")   # o id extra que "sumiu" da listagem
print(ids["external_id"])                    # "app-77" — o principal do cadastro
for i in ids["identifiers"]:
    print(i["external_id"], i["label"], i["source"])
```

## Sincronizar clientes e usuários do seu sistema

**Ids com o prefixo do sistema, sem `:`** — a assinatura do widget recusa `:`. Use `-` como
separador (`erp-1042` para clientes, `app-77` para pessoas) ou UUIDs puros. Assim vários
sistemas seus convivem no mesmo bFocus sem colisão.

**1. Carga inicial (no deploy da integração)**: clientes em fatias de 500 → vínculo com o produto →
pessoas em fatias de 500. Confira `summary["error"]` e registre os itens com erro.

```python
import logging
import os

from bfocus import BATCH_MAX, Bfocus

log = logging.getLogger("bfocus-sync")
bf = Bfocus(os.environ["BFOCUS_API_KEY"])  # escopo customers:write


def em_fatias(itens, rodada):
    for inicio in range(0, len(itens), BATCH_MAX):
        fatia = itens[inicio:inicio + BATCH_MAX]
        res = rodada(fatia)
        if res["summary"]["error"]:
            for r in res["results"]:
                if r["status"] == "error":
                    log.warning("bfocus: %s -> %s", fatia[r["index"]]["external_id"], r["error"])


clientes = [{"external_id": f"erp-{c.id}", "name": c.nome, "document": c.cnpj}
            for c in Cliente.objects.all()]
em_fatias(clientes, bf.customers.batch)

for c in clientes:
    bf.customers.products.attach(c["external_id"], "erp-cloud")  # idempotente

pessoas = [{"customer_external_id": f"erp-{u.cliente_id}", "external_id": f"app-{u.id}",
            "name": u.nome, "email": u.email}
           for u in Usuario.objects.all()]
em_fatias(pessoas, bf.people.batch)
```

**2. No dia a dia**: cada mudança no seu sistema vira uma chamada.

| No seu sistema | No bFocus |
| --- | --- |
| criou/alterou cliente | `bf.customers.upsert(...)` (+ `bf.customers.products.attach(...)` para ligar ao produto) |
| criou/alterou usuário | `bf.people.upsert(...)` |
| excluiu/desativou usuário | `bf.people.delete(...)` |
| excluiu cliente | `bf.customers.delete(...)` |

Se a resposta trouxer `merged_into`, atualize o id do seu lado.

**Nunca bloqueie a requisição do seu usuário esperando o bFocus**: enfileire (job/outbox) e
tente de novo com backoff. A SDK já repete 429/5xx com a mesma `Idempotency-Key`; a fila cobre
indisponibilidades longas.

```python
# no seu código de aplicação: só enfileira
def usuario_salvo(usuario):
    fila.enqueue(sincronizar_usuario, usuario.id)


# no worker (Celery, RQ, cron…): chama o bFocus; se falhar, a fila tenta de novo com backoff
def sincronizar_usuario(usuario_id):
    u = Usuario.objects.get(id=usuario_id)
    if not u.ativo:
        bf.people.delete(f"erp-{u.cliente_id}", f"app-{u.id}")
        return
    bf.people.upsert(f"erp-{u.cliente_id}", f"app-{u.id}", name=u.nome, email=u.email,
                     access=True)
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

Além de `code`, `status`, `message`, `request_id`, `validation`, `retry_after` e
`required_scope`, o erro tem **`data`**: o `data` do corpo, com o detalhe estruturado que alguns
erros trazem (`{}` quando não há). É por ele que um 409 de contato tomado diz de **quem** é o
contato — veja [Pessoas](#pessoas).

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
no `external_id` de um artigo; mais de 500 itens num `customers.batch`/`people.batch`; `:` no
usuário da assinatura v2 do widget) levanta `ValueError`/`TypeError` na hora, sem chamar a API.

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

### Identidade v2 (com validade)

A v2 carrega o instante da assinatura e expira: a API aceita de **7 dias atrás até 5 minutos à
frente**. Gere a cada renderização da página e nunca guarde. Vai no mesmo lugar da v1 (o
`userHash` do widget); a v1 continua aceita.

```python
from bfocus import sign_widget_identity_v2

assinatura = sign_widget_identity_v2(
    os.environ["BFOCUS_WIDGET_SECRET"],
    user_external_id="app-77",          # SEM ":" (é o separador; a SDK levanta ValueError)
    customer_external_id="erp-1042",
)
# "v2.<ts>.<hex>": ts = segundos unix de agora; hex = HMAC-SHA256 de "v2:<ts>:app-77:erp-1042"
```

Para testes, fixe o instante com `now=` (segundos unix `int`/`float` — não milissegundos — ou
`datetime`; sem fuso é tratado como UTC).

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
