#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/var/www/vanravenswaaij"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== Installatie Van Ravenswaaij Tuinen ==="
sudo mkdir -p "$APP_DIR"
sudo chown -R "$USER:$USER" "$APP_DIR"

cp -r "$SCRIPT_DIR/"* "$APP_DIR/"
if [ -f "$SCRIPT_DIR/.env" ]; then
    cp "$SCRIPT_DIR/.env" "$APP_DIR/.env"
fi

chmod +x "$APP_DIR/server.py" "$APP_DIR/fetch_images.py"

if command -v apt-get >/dev/null 2>&1; then
    if ! python3 -c "import dns.resolver" 2>/dev/null; then
        sudo apt-get update -qq && sudo apt-get install -y -qq python3-dnspython || true
    fi
fi

# Haal de originele foto's op van www.vanravenswaaijtuinen.nl en plaats ze in public/img/ + og-image.jpg
python3 "$APP_DIR/fetch_images.py" || echo "[WAARSCHUWING] Afbeeldingen ophalen overgeslagen; voer later 'python3 /var/www/vanravenswaaij/fetch_images.py' uit."

SERVICE_TMP="/tmp/ravenswaaij.service"
sed "s/^User=.*/User=$USER/" "$APP_DIR/ravenswaaij.service" > "$SERVICE_TMP"
sudo cp "$SERVICE_TMP" /etc/systemd/system/ravenswaaij.service
rm -f "$SERVICE_TMP"

sudo systemctl daemon-reload
sudo systemctl enable --now ravenswaaij
sudo systemctl restart ravenswaaij

echo "=== Klaar! Status van de service: ==="
sudo systemctl status ravenswaaij --no-pager || true
