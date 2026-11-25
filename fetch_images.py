#!/usr/bin/env python3
import re
import ssl
import urllib.request
from pathlib import Path
from urllib.parse import urljoin, urlparse

BASE_URL = "https://www.vanravenswaaijtuinen.nl/"
PUBLIC_DIR = Path(__file__).resolve().parent / "public"
IMG_DIR = PUBLIC_DIR / "img"
IMG_DIR.mkdir(parents=True, exist_ok=True)

TARGET_FILES = [
    "hero.jpg",
    "team.jpg",
    "dienst-ontwerp.jpg",
    "dienst-aanleg.jpg",
    "dienst-onderhoud.jpg",
    "dienst-renovatie.jpg",
    "project-oosterbeek.jpg",
    "project-veenendaal.jpg",
    "project-bestrating.jpg",
    "project-cortenstaal.jpg",
    "project-gazon.jpg",
    "project-onderhoud.jpg",
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0 Safari/537.36"
}


def haal_html(url: str, ctx: ssl.SSLContext) -> str:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def vind_afbeeldingen():
    ctx = ssl.create_default_context()
    bezocht = set()
    te_bezoeken = [BASE_URL]
    gevonden_urls = []

    while te_bezoeken and len(bezocht) < 15:
        url = te_bezoeken.pop(0)
        if url in bezocht:
            continue
        bezocht.add(url)
        try:
            html = haal_html(url, ctx)
        except Exception as e:
            print(f"[WAARSCHUWING] Kon {url} niet openen: {e}")
            continue

        # Zoek interne subpagina's van vanravenswaaijtuinen.nl
        for href in re.findall(r'href=["\']([^"\']+)["\']', html, re.I):
            full = urljoin(url, href).split("#")[0]
            if urlparse(full).netloc == urlparse(BASE_URL).netloc and full not in bezocht:
                if not re.search(r"\.(jpg|jpeg|png|webp|gif|pdf|css|js)$", full, re.I):
                    te_bezoeken.append(full)

        # Zoek afbeeldingen in src, data-src, srcset en CSS url(...)
        for match in re.findall(
            r'(?:src|data-src|content)=["\']([^"\']+\.(?:jpg|jpeg|png|webp)(?:\?[^"\']*)?)["\']|url\(["\']?([^"\'\)]+\.(?:jpg|jpeg|png|webp)(?:\?[^"\'\)]*)?)["\']?\)',
            html,
            re.I,
        ):
            raw = match[0] or match[1]
            img_url = urljoin(url, raw)
            # Filter kleine iconen / trackers weg
            if any(skip in img_url.lower() for skip in ("favicon", "logo-klein", "pixel", "1x1", "spacer")):
                continue
            if img_url not in gevonden_urls:
                gevonden_urls.append(img_url)

    return gevonden_urls, ctx


def main():
    print(f"Afbeeldingen ophalen van {BASE_URL} ...")
    urls, ctx = vind_afbeeldingen()
    print(f"Gevonden unieke afbeeldings-URL's: {len(urls)}")

    gedownload = []
    for idx, img_url in enumerate(urls, 1):
        try:
            req = urllib.request.Request(img_url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
                data = resp.read()
            # Sla kleine iconen (< 8 KB) over
            if len(data) < 8192:
                continue
            orig_name = Path(urlparse(img_url).path).name or f"orig_{idx}.jpg"
            orig_path = IMG_DIR / f"orig_{idx}_{orig_name}"
            orig_path.write_bytes(data)
            gedownload.append(orig_path)
            print(f"  [{len(gedownload)}] {img_url} -> {orig_path.name} ({len(data)//1024} KB)")
        except Exception as e:
            print(f"  [FOUT] {img_url}: {e}")

    if not gedownload:
        print("[FOUT] Geen bruikbare foto's gedownload van de originele site.")
        return

    # Koppel gedownloade foto's aan de verwachte bestandsnamen in public/img/
    for i, target in enumerate(TARGET_FILES):
        bron = gedownload[i % len(gedownload)]
        doel = IMG_DIR / target
        doel.write_bytes(bron.read_bytes())
        print(f"  Gekoppeld: {doel.name} <- {bron.name}")

    # Stel ook og-image.jpg in op basis van hero.jpg
    og_doel = PUBLIC_DIR / "og-image.jpg"
    og_doel.write_bytes((IMG_DIR / "hero.jpg").read_bytes())
    print(f"  Gekoppeld: og-image.jpg <- hero.jpg")
    print("Klaar! Alle afbeeldingen van de originele site zijn geplaatst.")


if __name__ == "__main__":
    main()
