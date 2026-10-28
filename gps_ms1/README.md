# GPS

`gps.py` reads the PA1616D GPS over UART on the Raspberry Pi and returns speed, pace, distance, lat/lon, heading, and fix validity as a `GPSData` object.

The GPS needs to be exposed to the sky to get valid readings. 

## Setup

### Wiring
GPS TX -> Pi RXD / GPIO15 (physical pin 10)

GPS RX <- Pi TXD / GPIO14 (physical pin 8)

GPS VCC <> Pi 3.3V (physical pin 1, through the PCB ferrite bead)

GPS GND <> Pi GND (physical pin 6)

These are the default Raspberry Pi Zero 2 W UART pins. The PCB already connects them through the UART series resistors. Use `/dev/serial0` at 9600 baud, 8N1, with no flow control.

### Installing Dependencies 
```bash
sudo raspi-config
```

Go to Interface Options > Serial Port. Select **No** for the serial login shell and **Yes** for serial port hardware, then reboot.

```bash
# in your venv
python -m pip install pyserial
```

## Test

```bash
python3 nmea_raw_test.py
```

Use this for a basic hardware connection debug test. Stop this test before running `gps.py` so only one program reads the UART.

## Run

```bash
python3 gps.py
```

Shows `no fix` until satellites are found, which needs a view of the sky.

## Usage

```python
from gps import PA1616D_GPS

gps = PA1616D_GPS()
gps.gps_init()                  # true if GPS acknowledged config

while True:
    new_rmc = gps.get_nmea_data()  # call often, true on a new RMC message
    d = gps.update_gps_obj()       # call every loop to check for stale data
    # Use d.valid before displaying readings as current.
```
