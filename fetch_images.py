#!/usr/bin/env python3
import shutil
from pathlib import Path
from urllib.request import Request, urlopen

TARGET_DIR = Path("/var/www/vanravenswaaij/public/img")
OG_TARGET = Path("/var/www/vanravenswaaij/public/og-image.jpg")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
}

FOTOS = {
    "hero.jpg": "https://hoveniernederland.nl/wp-content/gallery/van-ravenswaaij-tuinen/270016183_4707998472624343_1133775664332859324_n-1-1024x772.jpg",
    "team.jpg": "https://www.vanravenswaaijtuinen.nl/wp-content/uploads/189705757_1933183450177735_1955753090342860881_n-1.jpg",
    "dienst-ontwerp.jpg": "https://www.vanravenswaaijtuinen.nl/wp-content/uploads/259502579_4609264289164429_593684756178023998_n.jpg",
    "dienst-aanleg.jpg": "https://www.vanravenswaaijtuinen.nl/wp-content/uploads/217517240_4188302014593994_1216074056041544645_n-1.jpg",
    "dienst-onderhoud.jpg": "https://www.vanravenswaaijtuinen.nl/wp-content/uploads/269808579_4690381647719359_2559192434801672610_n.jpg",
    "dienst-renovatie.jpg": "https://www.vanravenswaaijtuinen.nl/wp-content/uploads/260807983_4617775228313335_7564904186680278841_n.jpg",
    "project-oosterbeek.jpg": "https://www.vanravenswaaijtuinen.nl/wp-content/uploads/12.jpg",
    "project-son.jpg": "https://hoveniernederland.nl/wp-content/gallery/van-ravenswaaij-tuinen/267503153_4707998485957675_4064247391804144052_n-1024x771.jpg",
    "project-overkapping.jpg": "https://www.vanravenswaaijtuinen.nl/wp-content/uploads/268766365_4657671754323682_2673476244692315855_n-1.jpg",
    "project-malden.jpg": "https://www.vanravenswaaijtuinen.nl/wp-content/uploads/264093465_4617774424980082_4615348913829321838_n.jpg",
    "project-bunnik.jpg": "https://www.vanravenswaaijtuinen.nl/wp-content/uploads/8.jpg",
    "project-noordwijk.jpg": "https://www.vanravenswaaijtuinen.nl/wp-content/uploads/269285040_4669763419781182_6127510666414253647_n.jpg",
    "vhg.jpg": "https://www.vanravenswaaijtuinen.nl/wp-content/uploads/VHG-logo-lid-van-RGB-1.jpg",
    "tuinkeur.jpg": "https://www.vanravenswaaijtuinen.nl/wp-content/uploads/Tuinkeur-gecertificeerd-witte-rand-CMYK-4-1.jpg",
}


def download_file(url: str, dest: Path) -> bool:
    req = Request(url, headers={**HEADERS, "Referer": url})
    with urlopen(req, timeout=25) as resp:
        data = resp.read()
    if len(data) < 2000:
        raise ValueError(f"Bestand te klein ({len(data)} bytes)")
    dest.write_bytes(data)
    return True


def main() -> None:
    TARGET_DIR.mkdir(parents=True, exist_ok=True)
    ok_count = 0

    for filename, url in FOTOS.items():
        dest = TARGET_DIR / filename
        try:
            download_file(url, dest)
            print(f"[OK]   {dest} ({dest.stat().st_size:,} bytes)")
            ok_count += 1
        except Exception as exc:
            print(f"[FOUT] {filename}: {exc}")

    hero_file = TARGET_DIR / "hero.jpg"
    if hero_file.exists():
        OG_TARGET.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(hero_file, OG_TARGET)
        print(f"[OK]   {OG_TARGET} bijgewerkt vanuit hero.jpg")

    print(f"\nKlaar: {ok_count}/{len(FOTOS)} bestanden opgeslagen in {TARGET_DIR}")


if __name__ == "__main__":
    main()
