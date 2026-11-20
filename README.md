# 473_bikeHUD

## Running Integration

Full Pi setup (flashing, config, packages, run on boot) is a step-by-step guide in [pi_integration/README.md](pi_integration/README.md). If the boot service is running, stop it first (`systemctl --user stop bikehud`) before running `main.py` by hand.

To run the HUD by hand over SSH (draws on the Pi's HDMI output; Pi OS Lite, no desktop):
```bash
cd 473_bikeHUD/pi_integration
./run_hud.sh            # same as: SDL_VIDEODRIVER=kmsdrm venv/bin/python main.py
```

To open a small HUD window on your Mac over SSH (X11 forwarding):
```bash
# one time on the Mac: brew install --cask xquartz, then log out and back in
ssh -Y <user>@<pi-address>                     # on the Mac

cd 473_bikeHUD/pi_integration                  # on the Pi
SDL_VIDEODRIVER=x11 venv/bin/python main.py --window
```
A 640x360 window opens on the Mac; logs stay in the SSH terminal. ESC or close the window to quit.

## Common Issues & Solutions

If ESP doesn't want to connect, run in the Pi terminal:
```bash
bluetoothctl remove 8C:94:DF:B8:5A:0A # Whatever the MAC is
```