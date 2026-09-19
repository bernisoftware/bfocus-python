"""bFocus — quickstart da SDK Python.

Rodar:
    pip install bfocus
    BFOCUS_API_KEY=bf_live_... python examples/quickstart.py

Opcional: BFOCUS_BASE_URL=http://localhost:8000 para apontar para a API local.
A chave precisa dos escopos customers:write, products:read e kb:read.
"""

import os
import sys

from bfocus import Bfocus, BfocusError, sign_widget_identity


def main() -> int:
    api_key = os.environ.get("BFOCUS_API_KEY")
    if not api_key:
        print("Defina BFOCUS_API_KEY (Integrações → Chaves de API no bFocus).", file=sys.stderr)
        return 2

    bf = Bfocus(api_key, base_url=os.environ.get("BFOCUS_BASE_URL") or "https://api.bfocus.com.br")

    try:
        # 1) Cliente: cria ou atualiza pelo id do SEU sistema. Só o que você passa muda.
        customer = bf.customers.upsert(
            "ERP 1042",
            name="Padaria Estrela",
            email="contato@padaria.example",
            custom_fields=[{"key": "plano", "label": "Plano", "value": "ouro"}],
        )
        print("cliente:", customer["id"], customer["name"])

        # 2) Registro no histórico do cliente.
        bf.customers.interactions.create("ERP 1042", "Cliente sincronizado pelo quickstart.")

        # 3) Catálogo de produtos.
        for product in bf.products.list():
            print("produto:", product["slug"], "-", product["name"])

        # 4) Busca na base de conhecimento.
        for hit in bf.kb.search("como emitir nota fiscal", limit=3):
            print("artigo:", hit["title"])

        # 5) Clientes alterados (percorre todas as páginas sozinho).
        total = sum(1 for _ in bf.customers.list_all(q="padaria"))
        print("clientes com 'padaria':", total)
    except BfocusError as err:
        # Decida pelo `code` (estável); informe o `request_id` ao suporte.
        print(f"erro {err.code} (HTTP {err.status}) request_id={err.request_id}", file=sys.stderr)
        return 1

    # 6) Identidade do widget: assinada no SEU backend, sem rede e sem chave de API.
    secret = os.environ.get("BFOCUS_WIDGET_SECRET")
    if secret:
        print("assinatura do widget:", sign_widget_identity(secret, "USR-1", "ERP 1042"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
