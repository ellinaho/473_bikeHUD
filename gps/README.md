# GPS

`gps.py` reads the PA1010D GPS over I2C on the Raspberry Pi and returns speed, pace, distance, lat/lon, heading, and fix validity as a `GPSData` object.

## Dependencies

- Python package: `smbus2`
- Pi setting: I2C enabled

Everything else is from the Python standard library.

## Setup

Wiring: SDA to pin 3, SCL to pin 5, 3.3V, GND. GPS is at I2C address `0x10`.

```bash
sudo raspi-config nonint do_i2c 0
sudo apt install -y python3-smbus2 i2c-tools
i2cdetect -y 1    # should show 10
```

## Run

```bash
python3 gps.py
```

Shows `no fix` until satellites are found, which needs a view of the sky.

## Test

```bash
python3 nmea_raw_test.py
```

Use this for a basic hardware connection debug test.

## Usage

```python
from gps import PA1010D_GPS

gps = PA1010D_GPS()
gps.gps_init()                  # true if GPS acknowledged config

while True:
    if gps.get_nmea_data():     # call often, true on new position
        d = gps.update_gps_obj()
```
