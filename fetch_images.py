import json
import os
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

PORTFOLIO_URL = "https://www.vanravenswaaijtuinen.nl/portfolio/"
BASE_DIR = Path(__file__).resolve().parent
OUT_IMG_DIR = BASE_DIR / "public" / "img" / "portfolio"
OUT_JSON = BASE_DIR / "public" / "portfolio.json"


class ImageExtractor(HTMLParser):
    def __init__(self, base_url: str):
        super().__init__()
        self.base_url = base_url
        self.images: list[dict] = []
        self._seen: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        if tag.lower() != "img":
            return
        attr_map = {k.lower(): (v or "") for k, v in attrs}
        raw_src = (
            attr_map.get("data-src")
            or attr_map.get("data-lazy-src")
            or attr_map.get("src")
            or ""
        ).strip()
        if not raw_src or raw_src.startswith("data:"):
            return

        full_url = urljoin(self.base_url, raw_src)
        lower = full_url.lower()
        if any(skip in lower for skip in ("logo", "favicon", "gravatar", "emoji", "sprite")):
            return

        if full_url not in self._seen:
            self._seen.add(full_url)
            self.images.append({
                "url": full_url,
                "alt": attr_map.get("alt", "").strip(),
            })


def safe_filename(url: str, index: int) -> str:
    path = urlparse(url).path
    ext = os.path.splitext(path)[1].lower()
    if ext not in {".jpg", ".jpeg", ".png", ".webp"}:
        ext = ".jpg"
    stem = re.sub(r"[^a-z0-9_-]+", "-", os.path.splitext(os.path.basename(path))[0].lower()).strip("-")
    if not stem:
        stem = f"project-{index:02d}"
    return f"{index:02d}-{stem}{ext}"


def fetch_html(url: str) -> str:
    req = Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; PortfolioFetcher/1.0)"})
    with urlopen(req, timeout=20) as resp:
        return resp.read().decode("utf-8", errors="replace")


def download_file(url: str, dest: Path) -> bool:
    try:
        req = Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; PortfolioFetcher/1.0)"})
        with urlopen(req, timeout=25) as resp:
            data = resp.read()
        if len(data) < 2000:
            return False
        dest.write_bytes(data)
        return True
    except Exception as exc:
        print(f"Fout bij downloaden {url}: {exc}")
        return False


def main():
    OUT_IMG_DIR.mkdir(parents=True, exist_ok=True)
    html = fetch_html(PORTFOLIO_URL)
    parser = ImageExtractor(PORTFOLIO_URL)
    parser.feed(html)

    saved = []
    idx = 1
    for item in parser.images:
        fname = safe_filename(item["url"], idx)
        dest = OUT_IMG_DIR / fname
        if download_file(item["url"], dest):
            saved.append({
                "id": idx,
                "alt": item["alt"],
                "source_url": item["url"],
                "local_path": f"/img/portfolio/{fname}",
            })
            idx += 1

    OUT_JSON.write_text(json.dumps(saved, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Opgeslagen: {len(saved)} afbeeldingen in {OUT_IMG_DIR}")
    print(f"Manifest geschreven naar {OUT_JSON}")


if __name__ == "__main__":
    main()
