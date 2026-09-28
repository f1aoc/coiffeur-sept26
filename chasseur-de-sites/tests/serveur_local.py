"""Petit serveur HTTP local qui sert tests/pages (aucun accès Internet)."""

from __future__ import annotations

import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PAGES = Path(__file__).resolve().parent / "pages"


class _Gestionnaire(SimpleHTTPRequestHandler):
    extensions_map = {**SimpleHTTPRequestHandler.extensions_map, ".html": "text/html; charset=utf-8"}

    def log_message(self, *args):  # silence dans la sortie de pytest
        pass

    def do_GET(self):
        if self.path.startswith("/statut/"):  # /statut/500 → erreur serveur simulée
            code = int(self.path.split("/")[2].split("?")[0])
            self.send_response(code)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(f"<h1>Erreur {code}</h1>".encode())
            return
        super().do_GET()


class ServeurLocal:
    def __init__(self, dossier: Path = PAGES):
        self._serveur = ThreadingHTTPServer(("127.0.0.1", 0), partial(_Gestionnaire, directory=str(dossier)))
        self.port = self._serveur.server_address[1]
        self._fil = threading.Thread(target=self._serveur.serve_forever, daemon=True)

    def url(self, page: str) -> str:
        return f"http://127.0.0.1:{self.port}/{page}"

    def __enter__(self) -> "ServeurLocal":
        self._fil.start()
        return self

    def __exit__(self, *exc) -> None:
        self._serveur.shutdown()
        self._serveur.server_close()
