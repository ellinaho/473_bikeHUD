# Tri-Node Bluetooth

* `esp_ble.c`: Code file for ESP32 BLE with Pi. For now, sends user serial input data to Pi
* `pi_esp.py`: Code file on Pi to listen to BLE packets from esp32 (pi central, esp32 peripheral)
* `pi_phone.py`: code file on pi to listen to packets from phone (pi central, phone peripheral, will flip later)

## Pi Setup
In /boot/firmware/config.txt, comment out `dtoverlay=disable-bt`

Then at the bottom at the [all] section, add:
```bash
enable_uart=1
dtoverlay=miniuart-bt
```

Then `sudo reboot`

In your venv, `pip install bleak`

## Running ESP32 -> Pi
1. upload `esp_ble.c` to ESP32, open serial monitor at 115200 baud
2. copy printed MAC address
3. paste the MAC address into `ESP32_MAC` global variable in `pi_esp.py`
4. run `pi_esp.py`

## Running Phone -> Pi
* set things up on LightBlue App
* for the milestone, we have the pi as central and lightblue as peripheral for preliminary testing without an entire app. for the actual product, we want to make pi the peripheral and the companion app as central for more stable conenction. 
* proves stuff works thoooo