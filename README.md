# 473_bikeHUD

## Run the Helmet

`main.py` runs GPS, radar BLE, phone nav BLE, and the encoder together on the Pi.

```bash
pip install smbus2 bleak bless evdev
python3 main.py
```

Prints one status line per second. Any part that can't start (missing hardware or library) is skipped. Turn parts off with `--no-gps`, `--no-radar`, `--no-nav`, `--no-encoder`.

Setup for each part is in its folder's README (`gps_ms1/`, `ble/`, `nav/`, `encoder_ms1/`).
