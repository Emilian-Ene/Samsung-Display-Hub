# Auto Update Backend (Next Pi)

Use these commands on a new Pi to enable backend auto-update from Git.

```bash
cd /home/paragon-av/Samsung-Display-Hub
git fetch origin && git reset --hard origin/main

sudo cp ./backend/systemd/samsung-auto-update.sh /usr/local/bin/samsung-auto-update.sh
sudo sed -i 's/\r$//' /usr/local/bin/samsung-auto-update.sh
sudo chmod +x /usr/local/bin/samsung-auto-update.sh
bash -n /usr/local/bin/samsung-auto-update.sh

sudo cp ./backend/systemd/samsung-auto-update.service /etc/systemd/system/
sudo cp ./backend/systemd/samsung-auto-update.timer /etc/systemd/system/

sudo systemctl daemon-reload
sudo systemctl enable --now samsung-auto-update.timer

systemctl status samsung-auto-update.timer --no-pager
sudo systemctl start samsung-auto-update.service
sudo journalctl -u samsung-auto-update.service -n 50 --no-pager
```

## What this does

- Checks Git `origin/main` every 5 minutes
- Pulls updates only when commit changed
- Restarts `samsung-backend`
- Restarts `samsung-option-b-agent` if installed

## Disable later

```bash
sudo systemctl disable --now samsung-auto-update.timer
```
