from __future__ import annotations

import argparse
import os
from html import escape
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional
from urllib.parse import unquote, urlsplit


RECAPTCHA_SITE_KEY_ENV = "RECAPTCHA_SITE_KEY"
RECAPTCHA_SITE_KEY_TOKEN = "__RECAPTCHA_SITE_KEY__"


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()

        if value and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]

        os.environ.setdefault(key, value)


def make_handler(root: Path, recaptcha_site_key: str):
    root_resolved = root.resolve()
    safe_site_key = escape(recaptcha_site_key, quote=True)

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(root), **kwargs)

        def _resolve_html_file(self) -> Optional[Path]:
            request_path = unquote(urlsplit(self.path).path)
            if request_path in {"", "/"}:
                candidate_rel_paths = ["index.html"]
            else:
                clean_path = request_path.strip("/")
                if not clean_path:
                    candidate_rel_paths = ["index.html"]
                elif clean_path.endswith(".html"):
                    candidate_rel_paths = [clean_path]
                elif "." in Path(clean_path).name:
                    return None
                else:
                    candidate_rel_paths = [f"{clean_path}.html", f"{clean_path}/index.html"]

            for relative_path in candidate_rel_paths:
                candidate = (root / relative_path).resolve()
                if not candidate.exists() or not candidate.is_file():
                    continue

                try:
                    candidate.relative_to(root_resolved)
                except ValueError:
                    continue

                return candidate

            return None

        def _serve_html(self, include_body: bool) -> bool:
            html_file = self._resolve_html_file()
            if html_file is None:
                return False

            html = html_file.read_text(encoding="utf-8")
            html = html.replace(RECAPTCHA_SITE_KEY_TOKEN, safe_site_key)
            payload = html.encode("utf-8")

            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()

            if include_body:
                self.wfile.write(payload)

            return True

        def do_GET(self) -> None:
            if self._serve_html(include_body=True):
                return
            super().do_GET()

        def do_HEAD(self) -> None:
            if self._serve_html(include_body=False):
                return
            super().do_HEAD()

    return Handler


def run(port: int) -> None:
    root = Path(__file__).resolve().parent
    load_dotenv(root / ".env")
    recaptcha_site_key = os.getenv(RECAPTCHA_SITE_KEY_ENV, "").strip()

    handler = make_handler(root, recaptcha_site_key)
    server = ThreadingHTTPServer(("", port), handler)
    print(f"Serving {root} at http://localhost:{port}")
    if recaptcha_site_key:
        print(f"Loaded {RECAPTCHA_SITE_KEY_ENV} from environment.")
    else:
        print(
            f"WARNING: {RECAPTCHA_SITE_KEY_ENV} is empty. "
            "Set it in .env to render reCAPTCHA on /review."
        )

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve the landing page locally.")
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", 8000)))
    args = parser.parse_args()
    run(args.port)


if __name__ == "__main__":
    main()
