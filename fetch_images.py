#!/usr/bin/env python3
import json
import os
import re
import shutil
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

BASE_URL = "https://www.vanravenswaaijtuinen.nl/portfolio/"
BASE_DIR = Path(__file__).resolve().parent
IMG_DIR = BASE_DIR / "public" / "img"
MANIFEST_PATH = BASE_DIR / "public" / "portfolio.json"
OG_IMAGE_PATH = BASE_DIR / "public" / "og-image.jpg"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


class PortfolioParser(HTMLParser):
    def __init__(self, base_url: str):
        super().__init__()
        self.base_url = base_url
        self.images: list[dict] = []
        self.project_links: list[str] = []
        self._seen_img: set[str] = set()
        self._seen_links: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]):
        attr = {k.lower(): (v or "").strip() for k, v in attrs}
        t = tag.lower()

        if t == "a":
            href = attr.get("href", "")
            if href and not href.startswith(("#", "mailto:", "tel:", "javascript:")):
                full = urljoin(self.base_url, href)
                parsed = urlparse(full)
                if "vanravenswaaijtuinen.nl" in parsed.netloc and "/portfolio/" in parsed.path and full != self.base_url:
                    if full not in self._seen_links:
                        self._seen_links.add(full)
                        self.project_links.append(full)

        elif t == "img":
            src = (
                attr.get("data-src")
                or attr.get("data-lazy-src")
                or attr.get("data-original")
                or attr.get("src")
                or ""
            )
            if not src or src.startswith("data:"):
                return
            full_img = urljoin(self.base_url, src)
            low = full_img.lower()
            if any(bad in low for bad in ("logo", "favicon", "gravatar", "emoji", "sprite", "icon")):
                return
            if full_img not in self._seen_img:
                self._seen_img.add(full_img)
                self.images.append({
                    "url": full_img,
                    "alt": attr.get("alt", "").strip(),
                })


def fetch_text(url: str) -> str:
    req = Request(url, headers=HEADERS)
    with urlopen(req, timeout=20) as resp:
        return resp.read().decode("utf-8", errors="replace")


def download_image(url: str, dest: Path) -> bool:
    try:
        req = Request(url, headers={**HEADERS, "Referer": BASE_URL})
        with urlopen(req, timeout=25) as resp:
            data = resp.read()
        if len(data) < 4000:
            return False
        dest.write_bytes(data)
        return True
    except Exception as exc:
        print(f"[WAARSCHUWING] Kon {url} niet ophalen: {exc}")
        return False


def make_filename(url: str, alt: str, index: int) -> str:
    ext = os.path.splitext(urlparse(url).path)[1].lower()
    if ext not in {".jpg", ".jpeg", ".png", ".webp"}:
        ext = ".jpg"
    base_label = alt or os.path.splitext(os.path.basename(urlparse(url).path))[0]
    slug = re.sub(r"[^a-z0-9]+", "-", base_label.lower()).strip("-")
    if not slug:
        slug = f"tuin-{index:02d}"
    return f"{index:02d}-{slug[:45]}{ext}"


def main() -> None:
    IMG_DIR.mkdir(parents=True, exist_ok=True)

    main_html = fetch_text(BASE_URL)
    parser = PortfolioParser(BASE_URL)
    parser.feed(main_html)

    for link in parser.project_links[:15]:
        try:
            sub_html = fetch_text(link)
            sub_parser = PortfolioParser(link)
            sub_parser.feed(sub_html)
            for item in sub_parser.images:
                if item["url"] not in {x["url"] for x in parser.images}:
                    parser.images.append(item)
        except Exception as exc:
            print(f"[INFO] Subpagina overgeslagen ({link}): {exc}")

    items = []
    counter = 1
    for entry in parser.images:
        fname = make_filename(entry["url"], entry["alt"], counter)
        target = IMG_DIR / fname
        if download_image(entry["url"], target):
            items.append({
                "id": counter,
                "titel": entry["alt"] or f"Portfolio project {counter}",
                "bestand": fname,
                "pad": f"/img/{fname}",
                "bron": entry["url"],
            })
            if counter == 1:
                shutil.copyfile(target, OG_IMAGE_PATH)
            counter += 1

    MANIFEST_PATH.write_text(json.dumps(items, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Klaar: {len(items)} foto's opgeslagen in {IMG_DIR}")


if __name__ == "__main__":
    main()
