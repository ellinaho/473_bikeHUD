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