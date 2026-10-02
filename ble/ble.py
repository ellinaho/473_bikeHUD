"""
Python function declarations for BLE, ran on Raspberry Pi
receives radar targets from the radar unit (ESP32)
"""

from dataclasses import dataclass

@dataclass
class RadarTarget:
    target_id: int      # id for each unique target
    tier: int           # alert tier, 0 = none, 1 = slow, 2 = medium, 3 = fast
    dist: float         # distance from rider in m
    speed: int          # approaching speed in kph, + is toward rider
    angle: int          # angle of arrival in degrees


class HelmetBLE:
    def ble_init(self, device_name: str = "BikeHUD-Radar"):
        """
        - scan for radar unit by name and connect to it
        - subscribe to radar packet notifications
        """
        pass

    def is_connected(self):
        """
        - returns true if radar unit is connected
        """
        pass

    def parse_packet(self, data: bytes):
        """
        - unpack raw packet bytes from radar unit (packet format in ble.h)
        - first byte is number of targets, then 6 bytes per target
        - returns list of RadarTarget, empty list if packet is bad
        """
        pass

    def get_targets(self):
        """
        - returns list of RadarTarget from the most recent packet
        - returns empty list if not connected or no packet received yet
        """
        pass
