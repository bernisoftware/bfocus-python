"""A versão existe em dois lugares e eles não podem divergir.

``bfocus/_version.py`` vai no header ``X-Bfocus-Client`` de TODA requisição — é por ele que
a API sabe quem avisar quando uma correção exige atualizar a SDK. Se ele congelar (no
bZapper congelou em 0.3.0 por releases seguidas), o aviso vai para o alvo errado.
"""

from __future__ import annotations

import re
import unittest

import bfocus
from bfocus import CLIENT_ID

from _support import PACKAGE_ROOT

PYPROJECT = PACKAGE_ROOT / "pyproject.toml"
VERSION_PY = PACKAGE_ROOT / "bfocus" / "_version.py"

# Os mesmos padrões do scripts/release-sdks.sh — se não casarem, o bump não acontece.
PYPROJECT_RE = r'(?m)^(version\s*=\s*")([^"]+)"'
VERSION_PY_RE = r'(__version__\s*=\s*")([^"]+)"'


class VersionTest(unittest.TestCase):
    def test_versao_bate_com_o_pyproject(self) -> None:
        matches = re.findall(PYPROJECT_RE, PYPROJECT.read_text(encoding="utf-8"))
        self.assertEqual(len(matches), 1, "uma única linha version = \"...\" no pyproject")
        self.assertEqual(
            bfocus.__version__,
            matches[0][1],
            "bfocus.__version__ divergiu do pyproject.toml — o bump precisa alterar os dois",
        )

    def test_padrao_do_release_casa_em_version_py(self) -> None:
        matches = re.findall(VERSION_PY_RE, VERSION_PY.read_text(encoding="utf-8"))
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0][1], bfocus.__version__)

    def test_identificacao_do_cliente(self) -> None:
        self.assertEqual(CLIENT_ID, f"bfocus-python/{bfocus.__version__}")
        self.assertRegex(CLIENT_ID, r"^bfocus-python/\d+\.\d+\.\d+$")


if __name__ == "__main__":
    unittest.main()
