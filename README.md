# 473_bikeHUD

## Running Integration

Full Pi setup (flashing, config, packages, run on boot) is a step-by-step guide in [pi_integration/README.md](pi_integration/README.md). If the boot service is running, stop it first (`systemctl --user stop bikehud`) before running `main.py` by hand.

To run the HUD by hand over SSH (draws on the Pi's HDMI output; Pi OS Lite, no desktop):
```bash
cd 473_bikeHUD/pi_integration
./run_hud.sh            # same as: SDL_VIDEODRIVER=kmsdrm ../.venv/bin/python main.py
```

To see the HUD on your laptop (no HDMI display needed):
```bash
cd 473_bikeHUD/pi_integration                  # on the Pi, over normal ssh
systemctl --user stop bikehud                  # if the boot service is running
../.venv/bin/python main.py --web
```
Then open `http://<pi-address>:8000` in a browser on the laptop. Logs stay in the SSH terminal; Ctrl+C to quit. Nothing is drawn on the HDMI display in this mode.

## Common Issues & Solutions

If ESP doesn't want to connect, run in the Pi terminal:
```bash
bluetoothctl remove 8C:94:DF:B8:5A:0A # Whatever the MAC is
```