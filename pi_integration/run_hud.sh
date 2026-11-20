#!/bin/bash
# Launches main.py on the Pi's display. Used by systemd/bikehud.service, also fine to run by hand.
# Targets Raspberry Pi OS Lite (no desktop): SDL draws straight to HDMI through KMS/DRM.

cd "$(dirname "$(readlink -f "$0")")"

# kmsdrm = draw to the screen with no desktop. Override for dev, e.g. SDL_VIDEODRIVER=x11 over ssh -Y.
export SDL_VIDEODRIVER="${SDL_VIDEODRIVER:-kmsdrm}"
export SDL_AUDIODRIVER="${SDL_AUDIODRIVER:-dummy}"   # no sound used; skips audio probing at startup
export PYTHONUNBUFFERED=1   # print() shows up in journalctl immediately

# After boot, wait (up to 30s) for the GPU's DRM device before opening the display
for _ in $(seq 30); do
    ls /dev/dri/card* >/dev/null 2>&1 && break
    sleep 1
done

# Use the project venv if there is one, otherwise system python3
for v in venv .venv ../venv ../.venv "$HOME/venv" "$HOME/.venv"; do
    [ -x "$v/bin/python" ] && exec "$v/bin/python" main.py "$@"
done
exec python3 main.py "$@"
