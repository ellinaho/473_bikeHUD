#!/bin/bash
# Launches main.py on the Pi's display. Used by systemd/bikehud.service, also fine to run by hand.

cd "$(dirname "$(readlink -f "$0")")"

export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
export WAYLAND_DISPLAY="${WAYLAND_DISPLAY:-wayland-0}"
export SDL_VIDEODRIVER=wayland
export PYTHONUNBUFFERED=1   # print() shows up in journalctl immediately

# After boot, wait (up to 60s) for the desktop's Wayland compositor before opening the display
for _ in $(seq 60); do
    [ -S "$XDG_RUNTIME_DIR/$WAYLAND_DISPLAY" ] && break
    sleep 1
done

# Use the project venv if there is one, otherwise system python3
for v in venv .venv ../venv ../.venv "$HOME/venv" "$HOME/.venv"; do
    [ -x "$v/bin/python" ] && exec "$v/bin/python" main.py "$@"
done
exec python3 main.py "$@"
