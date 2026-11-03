# Setup

## Install dependencies
```
sudo apt update
sudo apt install -y python3-venv python3-dev bluez libbluetooth-dev libglib2.0-dev
```

create your venv and install dependencies
```
python3 -m venv .venv
source .venv/bin/activate

pip install evdev pyserial bleak bless
```

## Systemd services

Create a file at `/etc/systemd/system/bikehud.service`, and enter:
```
[Unit]
Description=473_bikeHUD Main Engine
Requires=dbus.service bluetooth.service
After=dbus.service bluetooth.service systemd-udevd.service

[Service]
Type=simple
User=pi
SupplementaryGroups=input dialout bluetooth

# Prevents print() buffering so you can read logs in real-time
Environment=PYTHONUNBUFFERED=1

# Forces the service to use the virtual environment packages
Environment="PATH=/home/pi/hud_project/venv/bin:/usr/bin:/sbin:/bin"
WorkingDirectory=/home/pi/hud_project

# Explicitly points to the Python executable inside your virtual environment
ExecStart=/home/pi/hud_project/venv/bin/python3 main.py

# Aggressive restart logic for headless reliability
Restart=always
RestartSec=3
StartLimitIntervalSec=60
StartLimitBurst=5

[Install]
WantedBy=multi-user.target
```

Then run
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now bikehud.service
```