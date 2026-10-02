"""
Python function declarations for the HUD display, ran on Raspberry Pi
draws the UI to the HDMI panel using an existing graphics library (pygame)

screen layout:
    top left     clock, always shown
    top right    speed from GPS, always shown
    middle       rear vehicle alert, only shown when a target is present
    bottom       next navigation cue, only shown in navigation mode
    everything else is left black so it is transparent through the combiner
"""

from dataclasses import dataclass
from enum import IntEnum
from ble import RadarTarget
from gps import GPSData
from encoder import HUDMode

class NavTurn(IntEnum):
    # enums for which arrow icon to draw at the bottom
    NONE = 0
    STRAIGHT = 1
    LEFT = 2
    RIGHT = 3
    UTURN = 4
    ARRIVED = 5

@dataclass
class NavCue:
    turn: NavTurn       # arrow icon to draw
    dist: int           # distance to the turn in m
    street: str         # name of road to turn onto, "" if none


class HUDDisplay:
    def display_init(self, width: int = 1920, height: int = 1080, fps: int = 60):
        """
        - open fullscreen window on the HDMI output, hide the mouse cursor
        - load fonts and alert/arrow icons once so render loop doesn't reload them
        - returns false if the panel could not be opened
        """
        pass

    def set_mode(self, mode: HUDMode):
        """
        - called when encoder changes the mode (encoder.update_HUD_mode)
        - decides which regions are drawn, ex: nav cue only in navigation mode
        """
        pass

    def update_speed(self, gps: GPSData):
        """
        - stores speed from most recent GPSData for the top right region
        - if gps.valid is false, shows "--" instead of a number
        """
        pass

    def update_alert(self, targets: list[RadarTarget]):
        """
        - takes targets from HelmetBLE.get_targets()
        - picks the closest target with tier > 0 for the middle region
        - tier picks icon size/color, 1 = small, 2 = medium, 3 = large + flashing
        - alert clears if no target seen for ~1 s (3 missed packets)
        """
        pass

    def update_nav(self, cue: NavCue):
        """
        - stores most recent nav cue from the phone BLE link for the bottom region
        - keeps last cue if phone disconnects so rider still sees next turn
        """
        pass

    def render(self):
        """
        - draws clock, speed, alert, and nav cue to the frame buffer, then flips to the screen
        - called once per loop at fps, clock is read from system time here
        - alert is drawn last so it is always on top
        """
        pass

    def display_close(self):
        """
        - blanks the screen and releases the HDMI output on shutdown
        """
        pass
