# Rotary Encoder README

## Installing Dependencies
`sudo apt-get install python3-evdev`

`pip install evdev`

## Kernal Overlay
```
dtoverlay=rotary-encoder,pin_a=23,pin_b=24,relative_axis=1
dtoverlay=gpio-key,gpio=25,keycode=28,label="ENTER"
```

## Permissions
`sudo usermod -a -G input $USER`

Then `sudo reboot`. 
