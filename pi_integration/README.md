# Setup Instructions

11/13: Need to update physical pins here that match with PCB

### config.txt
In `/boot/firmware/config.txt`:
* comment out `dtoverlay=disable-bt` if present
* at the bottom at the [all] section, add:
```bash
enable_uart=1
dtoverlay=miniuart-bt
dtoverlay=rotary-encoder,pin_a=17,pin_b=27,relative_axis=1
dtoverlay=gpio-key,gpio=22,keycode=28,label="ENTER" 
```

then set permissions:
```bash
sudo usermod -a -G input $USER
```

Then `sudo reboot`

## Installing libraries and packages 

In your venv, `pip install -r requirements.txt`

```bash
sudo apt-get install python3-evdev

```

We also need to allow serial communication for the GPS. 
```bash
sudo raspi-config
```

Go to Interface Options > Serial Port. Select **No** for the serial login shell and **Yes** for serial port hardware, then reboot.

## Wiring
Encoder CLK <> Pi GPIO17

Encoder DT <> Pi GPIO27

Encoder SW <> Pi GPIO22

Encoder + <> Pi 3.3V

Encoder GND <> Pi GND

## BLE Watchdog (auto-reconnect)

`ble_watchdog.py` owns both BLE links and is started by `main.py` automatically (`ble_worker` thread).

**ESP32 radar:** reconnects immediately when the link drops. It also treats 3s without a radar packet as a dropped link, since the ESP sends on every radar frame. If connecting keeps failing, it escalates:
- 2+ failures: `bluetoothctl disconnect` + `remove 8C:94:DF:B8:5A:0A` (the old manual fix)
- every 5th failure: power-cycles the adapter
- every 10th failure: `sudo systemctl restart bluetooth`

**Phone:** the app does the reconnecting, so the Pi keeps itself connectable:
- re-registers the GATT server and advertising after a bluetoothd restart, an adapter reset, or if advertising disappears
- if the phone stays connected but sends nothing for 15s, drops the link so the app reconnects (`PHONE_STALE_S`, set to `None` to disable)

Needs passwordless `sudo` for `rfkill`/`systemctl` (the default Pi user has it).

To test both links without the display:
```bash
python3 ble_watchdog.py
```

## Run on boot (systemd)

`systemd/bikehud.service` starts `main.py` (through `run_hud.sh`) as soon as the Pi boots to the desktop. If it crashes it restarts after 3s. It's a **user** service, because the HUD draws on your desktop session's display.

The Pi must boot to the desktop with auto-login: `sudo raspi-config` → System Options → Boot / Auto Login → **Desktop Autologin**. The service file assumes the repo is at `~/473_bikeHUD`. Edit `ExecStart` if it's somewhere else.

**Add it to systemd (one time):**
```bash
chmod +x ~/473_bikeHUD/pi_integration/run_hud.sh
mkdir -p ~/.config/systemd/user
cp ~/473_bikeHUD/pi_integration/systemd/bikehud.service ~/.config/systemd/user/
systemctl --user daemon-reload
```
Copy and `daemon-reload` again if you change the service file.

**Activate** (starts now and on every boot):
```bash
systemctl --user enable --now bikehud
```

**Deactivate** (stops now and no longer starts on boot):
```bash
systemctl --user disable --now bikehud
```

**Other useful commands:**
```bash
systemctl --user stop bikehud      # stop until next boot (still enabled)
systemctl --user start bikehud     # start it again
systemctl --user restart bikehud   # restart after pulling new code
systemctl --user status bikehud    # is it running?
journalctl --user -u bikehud -f    # live logs (BLE / GPS / UI prints)
```

Stop the service before running `main.py` by hand. Two copies would fight over the display and the BLE connections.
