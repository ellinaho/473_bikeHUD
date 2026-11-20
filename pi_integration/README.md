# BikeHUD Pi Setup

Target: **Raspberry Pi Zero 2 W** running **Raspberry Pi OS Lite (64-bit)**, no desktop. The HUD draws straight to the HDMI output (SDL `kmsdrm`), so no desktop or window manager is needed.

11/13: Need to update physical pins here that match with PCB

Do the steps in order. Commands run on the Pi over SSH unless noted.

## 1. Flash the SD card (on your laptop)

1. Open Raspberry Pi Imager. Device: **Raspberry Pi Zero 2 W**. OS: **Raspberry Pi OS (other) → Raspberry Pi OS Lite (64-bit)**.
2. In the OS customisation settings, set a username and password, your Wi-Fi, and **enable SSH**.
3. Flash, put the card in the Pi, **plug in the HDMI display**, then power on.
4. SSH in: `ssh <user>@<hostname>.local`

## 2. Update and get the code

```bash
sudo apt update && sudo apt full-upgrade -y
sudo apt install -y git
git clone https://github.com/ellinaho/473_bikeHUD.git ~/473_bikeHUD
```
If the repo is private, GitHub will ask for a username and a personal access token (not your password).

The rest of this guide assumes the repo is at `~/473_bikeHUD`.

## 3. Turn on the serial port for the GPS

```bash
sudo raspi-config
```
Interface Options → Serial Port. Select **No** for the serial login shell and **Yes** for serial port hardware. Finish, but don't reboot yet.

## 4. Edit config.txt

```bash
sudo nano /boot/firmware/config.txt
```
* comment out `dtoverlay=disable-bt` if present
* make sure `dtoverlay=vc4-kms-v3d` is present and not commented out (it is by default; the display needs it)
* at the bottom, under the `[all]` section, add:
```bash
enable_uart=1
dtoverlay=miniuart-bt
core_freq=250
dtoverlay=rotary-encoder,pin_a=17,pin_b=27,relative_axis=1
dtoverlay=gpio-key,gpio=22,keycode=28,label="ENTER"
```
`miniuart-bt` gives the GPS the good UART on GPIO14/15 and moves Bluetooth to the mini UART. On the Zero 2 W the mini UART's speed follows the GPU core clock, so `core_freq=250` pins it; without it Bluetooth can be flaky.

## 5. Force HDMI on (recommended)

If the display isn't detected at boot, the HUD has no screen to draw on and fails with `Could not open display`. To force HDMI on at a fixed resolution, edit:
```bash
sudo nano /boot/firmware/cmdline.txt
```
Add this to the end of the **existing single line**, with a space before it. Don't put it on a new line:
```
video=HDMI-A-1:1280x720@60D
```
The `D` forces the output on even if nothing is detected. 720p also keeps the frame rate up, since every frame is drawn on the Zero 2's CPU. Use your panel's resolution if it's lower.

## 6. Permissions, then reboot

Add your user to the groups the HUD needs (display, encoder input, GPS serial, Bluetooth):
```bash
sudo usermod -a -G video,render,input,dialout,bluetooth $USER
sudo reboot
```

## 7. Install packages

`pygame` and `evdev` come from apt, not pip. apt's pygame is built against Debian's SDL2, which can draw with no desktop (`kmsdrm`); the pip wheel may not be able to. apt's evdev is prebuilt, so nothing compiles on the Zero 2.

```bash
sudo apt install -y python3-pygame python3-evdev python3-venv bluez
```

Make the venv with `--system-site-packages` so it can see the apt packages, then pip install the rest:
```bash
cd ~/473_bikeHUD/pi_integration
python3 -m venv --system-site-packages venv
venv/bin/pip install -r requirements.txt
```
Don't `pip install pygame` or `evdev` into the venv; that would hide the apt versions.

The Zero 2 W only has 512 MB of RAM. If pip gets killed while installing, add swap: in `/etc/dphys-swapfile` (or `sudo apt install dphys-swapfile` if missing) set `CONF_SWAPSIZE=1024`, then `sudo systemctl restart dphys-swapfile`.

## 8. Test by hand

```bash
cd ~/473_bikeHUD/pi_integration
chmod +x run_hud.sh
venv/bin/python ble_watchdog.py   # BLE links only (ESP32 radar + phone), no display. Ctrl+C to stop.
./run_hud.sh                      # the full HUD on the HDMI display. Ctrl+C to stop.
```
Check the output for `Started SixOS with dimensions ...`, `Connected to rotary@...`, and GPS / BLE messages.

## 9. Run on boot (systemd)

`systemd/bikehud.service` starts `main.py` (through `run_hud.sh`) at boot. If it crashes it restarts after 3s. It's a **user** service; "lingering" makes it start at boot without anyone logging in. No desktop or auto-login is needed. The service file assumes the repo is at `~/473_bikeHUD`. Edit `ExecStart` if it's somewhere else.

**Add it to systemd (one time):**
```bash
sudo loginctl enable-linger $USER
mkdir -p ~/.config/systemd/user
cp ~/473_bikeHUD/pi_integration/systemd/bikehud.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now bikehud
```
Copy and `daemon-reload` again if you change the service file. Reboot to check that it comes up on its own.

**Day-to-day commands:**
```bash
systemctl --user stop bikehud      # stop until next boot (still enabled)
systemctl --user start bikehud     # start it again
systemctl --user restart bikehud   # restart after pulling new code
systemctl --user status bikehud    # is it running?
journalctl --user -u bikehud -f    # live logs (BLE / GPS / UI prints)
systemctl --user disable --now bikehud   # stop and don't start on boot anymore
```

Stop the service before running `main.py` or `run_hud.sh` by hand. Two copies would fight over the display and the BLE connections.

---

# Reference

## Wiring
Encoder CLK <> Pi GPIO17

Encoder DT <> Pi GPIO27

Encoder SW <> Pi GPIO22

Encoder + <> Pi 3.3V

Encoder GND <> Pi GND

## run_hud.sh

What the service runs. It:
1. `cd`s into `pi_integration/` so `main.py` finds `assets/`
2. sets `SDL_VIDEODRIVER=kmsdrm` (draw on HDMI with no desktop) and `SDL_AUDIODRIVER=dummy` (no sound needed). Either can be overridden, e.g. `SDL_VIDEODRIVER=x11 ./run_hud.sh --window` over `ssh -Y`
3. waits up to 30s after boot for the GPU's display device (`/dev/dri/card*`)
4. runs `main.py` with the first venv it finds (`venv`, `.venv`, `../venv`, `~/venv`, ...), or system `python3` if there is none. Extra arguments (like `--window`) are passed through.

## BLE Watchdog (auto-reconnect)

`ble_watchdog.py` owns both BLE links and is started by `main.py` automatically (`ble_worker` thread).

**ESP32 radar:** reconnects immediately when the link drops. It also treats 3s without a radar packet as a dropped link, since the ESP sends on every radar frame. If connecting keeps failing, it escalates:
- 2+ failures: `bluetoothctl disconnect` + `remove 8C:94:DF:B8:5A:0A` (the old manual fix)
- every 5th failure: power-cycles the adapter
- every 10th failure: `sudo systemctl restart bluetooth`

**Phone:** the app does the reconnecting, so the Pi keeps itself connectable:
- re-registers the GATT server and advertising after a bluetoothd restart, an adapter reset, or if advertising disappears
- if the phone stays connected but sends nothing for 15s, drops the link so the app reconnects (`PHONE_STALE_S`, set to `None` to disable)

Needs passwordless `sudo` for `rfkill`/`systemctl` (the user created in Raspberry Pi Imager has it).
