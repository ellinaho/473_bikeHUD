# Rotary Encoder README

## Setup

### Installing Dependencies
```bash
sudo apt-get install python3-evdev

# inside your venv
pip install evdev
```

### Kernel Device Tree Overlay
```bash
sudo nano /boot/firmware/config.txt
```

add the following under [all] at the very bottom:

```bash
dtoverlay=rotary-encoder,pin_a=23,pin_b=24,relative_axis=1
dtoverlay=gpio-key,gpio=25,keycode=28,label="ENTER"
```

then set permissions:
```bash
sudo usermod -a -G input $USER
sudo reboot
```

### Wiring
Encoder CLK <> Pi GPIO23

Encoder DT <> Pi GPIO24

Encoder SW <> Pi GPIO25

Encoder + <> Pi 3.3V

Encoder GND <> Pi GND