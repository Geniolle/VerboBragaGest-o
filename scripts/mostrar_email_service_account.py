"""Mostra o e-mail da service account contido no ficheiro JSON de credenciais.

Use este e-mail para partilhar a spreadsheet "AppPastoreioGestao" no Drive
(com permissao de Editor) antes de correr qualquer outro script.

Uso:
    uv run python scripts/mostrar_email_service_account.py caminho/para/chave.json
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> None:
    if len(sys.argv) != 2:
        print("Uso: python scripts/mostrar_email_service_account.py <caminho_do_json>")
        raise SystemExit(1)

    path = Path(sys.argv[1])
    if not path.exists():
        print(f"Ficheiro nao encontrado: {path}")
        raise SystemExit(1)

    data = json.loads(path.read_text(encoding="utf-8"))
    email = data.get("client_email")
    if not email:
        print("Este ficheiro JSON nao parece ser uma chave de service account valida.")
        raise SystemExit(1)

    print(f"E-mail da service account: {email}")
    print("Partilhe a spreadsheet com este e-mail (permissao: Editor).")


if __name__ == "__main__":
    main()
