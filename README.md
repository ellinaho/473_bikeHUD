# 473_bikeHUD

## Running Integration

To start the HUD automatically on boot, see "Run on boot (systemd)" in [pi_integration/README.md](pi_integration/README.md). Stop it first (`systemctl --user stop bikehud`) before running `main.py` by hand.

To run display over SSH:
```bash
XDG_RUNTIME_DIR=/run/user/$(id -u) WAYLAND_DISPLAY=wayland-0 SDL_VIDEODRIVER=wayland python3 main.py
```

To open a small HUD window on your Mac over SSH (X11 forwarding):
```bash
# one time on the Mac: brew install --cask xquartz, then log out and back in
ssh -Y <user>@<pi-address>                     # on the Mac

cd 473_bikeHUD/pi_integration                  # on the Pi
SDL_VIDEODRIVER=x11 python3 main.py --window
```
A 640x360 window opens on the Mac; logs stay in the SSH terminal. ESC or close the window to quit.

## Common Issues & Solutions

If ESP doesn't want to connect, run in the Pi terminal:
```bash
bluetoothctl remove 8C:94:DF:B8:5A:0A # Whatever the MAC is
```