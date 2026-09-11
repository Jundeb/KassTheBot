#!/usr/bin/env bash
# One-time setup for running Kass the Bot on a Raspberry Pi as a systemd service
# with automatic weekly yt-dlp updates. Safe to re-run (e.g. after `git pull`).
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_USER="$(whoami)"
PYTHON_BIN="$(command -v python3)"
PIP_BIN="$(command -v pip3 || command -v pip)"

echo "==> Installing system dependencies (ffmpeg)"
sudo apt update
sudo apt install -y ffmpeg python3-pip

echo "==> Installing Python dependencies"
"$PIP_BIN" install -r "$REPO_DIR/requirements.txt" --break-system-packages

if [ ! -f "$REPO_DIR/token.txt" ]; then
    echo
    read -rp "Enter your Discord bot token: " BOT_TOKEN
    printf '%s\n' "$BOT_TOKEN" > "$REPO_DIR/token.txt"
    echo "==> Saved token to $REPO_DIR/token.txt"
else
    echo "==> token.txt already exists, leaving it as is"
fi

echo "==> Writing /etc/systemd/system/kassthebot.service"
sudo tee /etc/systemd/system/kassthebot.service > /dev/null <<EOF
[Unit]
Description=Kass the Bot (Discord music bot)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$SERVICE_USER
WorkingDirectory=$REPO_DIR
ExecStartPre=$PIP_BIN install -U yt-dlp --break-system-packages
ExecStart=$PYTHON_BIN $REPO_DIR/main.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

echo "==> Writing /etc/systemd/system/kassthebot-update.service"
sudo tee /etc/systemd/system/kassthebot-update.service > /dev/null <<EOF
[Unit]
Description=Restart Kass the Bot (picks up latest yt-dlp via ExecStartPre)

[Service]
Type=oneshot
ExecStart=/usr/bin/systemctl restart kassthebot
EOF

echo "==> Writing /etc/systemd/system/kassthebot-update.timer"
sudo tee /etc/systemd/system/kassthebot-update.timer > /dev/null <<EOF
[Unit]
Description=Weekly yt-dlp update for Kass the Bot

[Timer]
OnCalendar=weekly
Persistent=true

[Install]
WantedBy=timers.target
EOF

echo "==> Enabling and starting services"
sudo systemctl daemon-reload
sudo systemctl enable kassthebot.service
sudo systemctl restart kassthebot.service
sudo systemctl enable --now kassthebot-update.timer

echo
echo "Done. Kass the Bot is running as user '$SERVICE_USER' from $REPO_DIR."
echo "It will auto-update yt-dlp and restart itself weekly — nothing more to do."
echo
echo "Check status:  sudo systemctl status kassthebot"
echo "Live logs:     journalctl -u kassthebot -f"
echo "Next update:   systemctl list-timers kassthebot-update.timer"
