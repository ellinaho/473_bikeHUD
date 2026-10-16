# GPS

`gps.py` reads the PA1010D GPS over I2C on the Raspberry Pi and returns speed, pace, distance, lat/lon, heading, and fix validity as a `GPSData` object.

The GPS needs to be exposed to the sky to get valid readings. 

## Setup

### Wiring
GPS SDA <> Pi SDA (Pin 3)

GPS SCL <> Pi SCL (Pin 5)

GPS Vin <> Pi 3.3V (Pin 1)

GPS GND <> Pi GND (Pin 6)

GPS has I2C address 0x10

### Installing Dependencies 
```bash
sudo raspi-config nonint do_i2c 0
sudo apt install -y python3-smbus2 i2c-tools
i2cdetect -y 1    # should show 10

# in your venv
pip install smbus2
```

## Test

```bash
python3 nmea_raw_test.py
```

Use this for a basic hardware connection debug test.

## Run

```bash
python3 gps.py
```

Shows `no fix` until satellites are found, which needs a view of the sky.

## Usage

```python
from gps import PA1010D_GPS

gps = PA1010D_GPS()
gps.gps_init()                  # true if GPS acknowledged config

while True:
    if gps.get_nmea_data():     # call often, true on new position
        d = gps.update_gps_obj()
```
