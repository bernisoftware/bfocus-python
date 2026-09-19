"""SDK oficial em Python da API pública do bFocus.

    from bfocus import Bfocus

    bf = Bfocus("bf_live_...")
    bf.customers.upsert("ERP 1042", name="Padaria Estrela")

Zero dependências (só biblioteca padrão). Python 3.9+.
"""

from ._client import Bfocus
from ._transport import CLIENT_ID, DEFAULT_BASE_URL
from ._version import __version__
from .errors import (
    AuthenticationError,
    BfocusError,
    ConflictError,
    NetworkError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
    ServerError,
    ValidationError,
)
from .types import UNSET, Page
from .widget import sign_widget_identity

__all__ = [
    "Bfocus",
    "Page",
    "UNSET",
    "sign_widget_identity",
    "BfocusError",
    "AuthenticationError",
    "PermissionDeniedError",
    "NotFoundError",
    "ConflictError",
    "ValidationError",
    "RateLimitError",
    "ServerError",
    "NetworkError",
    "DEFAULT_BASE_URL",
    "CLIENT_ID",
    "__version__",
]
