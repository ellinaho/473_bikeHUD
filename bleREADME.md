# Tri-Node Bluetooth

## Running ESP32 -> Pi
1. upload `esp_ble.c` to ESP32, open serial monitor at 115200 baud
2. copy printed MAC address
3. paste the MAC address into `ESP32_MAC` global variable in `pi_ble.py`
4. run `pi_ble.py`


## esp_ble.c
Code file for ESP32 BLE with Pi. For now, sends user serial input data to Pi. 

Todo later: 

* change payload struct based on what is actually transmitted





# BLE Setup on Raspberry Pi

In /boot/firmware/config.txt, comment out the following line:
`dtoverlay=disable-bt`

Then at the bottom at the [all] section, add:
```
enable_uart=1
dtoverlay=miniuart-bt
```

Then `sudo reboot`

Also `pip install bleak`