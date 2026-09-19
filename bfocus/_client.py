"""Cliente principal: :class:`Bfocus`."""

from __future__ import annotations

from typing import Any, Callable

from ._resources import AIAgents, Customers, KnowledgeBase, People, Products, ReleaseNotes
from ._transport import DEFAULT_BASE_URL, DEFAULT_MAX_RETRIES, DEFAULT_TIMEOUT, Transport
from .widget import sign_widget_identity, sign_widget_identity_v2

__all__ = ["Bfocus"]


class Bfocus:
    """Cliente da API pública do bFocus.

    Args:
        api_key: Chave de API (``Integrações → Chaves de API``). Único argumento
            posicional e obrigatório.
        base_url: URL da API, sem barra final. Padrão: produção
            (``https://api.bfocus.com.br``). Em dev: ``http://localhost:8000``.
        timeout: Segundos por tentativa (padrão 30).
        max_retries: Novas tentativas além da primeira em erro de rede/timeout, 429, 502,
            503 e 504 (padrão 2; ``0`` desliga).

    Nada é chamado na rede ao construir.

    Example:
        >>> from bfocus import Bfocus
        >>> bf = Bfocus("bf_live_...")
        >>> bf.customers.upsert("ERP 1042", name="Padaria Estrela")  # doctest: +SKIP
    """

    #: Também disponível como função do pacote: ``from bfocus import sign_widget_identity``.
    sign_widget_identity = staticmethod(sign_widget_identity)
    #: Também disponível como função do pacote: ``from bfocus import sign_widget_identity_v2``.
    sign_widget_identity_v2 = staticmethod(sign_widget_identity_v2)

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ) -> None:
        if not isinstance(api_key, str):
            raise TypeError("Bfocus: api_key precisa ser str (ex.: 'bf_live_...').")
        if not api_key.strip():
            raise ValueError("Bfocus: api_key é obrigatória (ex.: 'bf_live_...').")
        if not isinstance(max_retries, int) or isinstance(max_retries, bool) or max_retries < 0:
            raise ValueError("Bfocus: max_retries precisa ser um inteiro >= 0.")
        if timeout is None or timeout <= 0:
            raise ValueError("Bfocus: timeout precisa ser > 0 (segundos).")

        self._transport = Transport(
            api_key,
            base_url=(base_url or DEFAULT_BASE_URL),
            timeout=float(timeout),
            max_retries=max_retries,
        )
        #: Clientes (empresas), com ``.contacts``, ``.products``, ``.interactions`` e
        #: ``.identifiers``.
        self.customers = Customers(self._transport)
        #: Pessoas dos clientes (quem abre chamados/conversas), com ``.identifiers``.
        self.people = People(self._transport)
        #: Catálogo de produtos.
        self.products = Products(self._transport)
        #: Release notes por produto.
        self.release_notes = ReleaseNotes(self._transport)
        #: Base de conhecimento: ``.articles`` e ``.search(...)``.
        self.kb = KnowledgeBase(self._transport)
        #: Agentes de IA.
        self.ai_agents = AIAgents(self._transport)

    @property
    def base_url(self) -> str:
        return self._transport.base_url

    @property
    def timeout(self) -> float:
        return self._transport.timeout

    @property
    def max_retries(self) -> int:
        return self._transport.max_retries

    @property
    def _sleep(self) -> Callable[[float], Any]:
        """Espera entre novas tentativas (padrão ``time.sleep``). Substitua nos testes."""
        return self._transport.sleep

    @_sleep.setter
    def _sleep(self, fn: Callable[[float], Any]) -> None:
        self._transport.sleep = fn

    def __repr__(self) -> str:
        key = self._transport.api_key
        masked = key[:8] + "…" if len(key) > 8 else "…"
        return f"Bfocus(api_key={masked!r}, base_url={self.base_url!r})"
