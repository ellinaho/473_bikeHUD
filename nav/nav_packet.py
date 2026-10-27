"""
Navigation packet format shared between the phone app and the Pi

Phone app does all routing and sends the next turn to the Pi over BLE. The app side must build
packets in exactly this layout (see README.md). No BLE code here so it can be tested anywhere.
"""

import struct
import time

#BLE ids, must match the phone app
NAV_SERVICE_UUID = "e92011aa-4b4e-452d-ba3a-33271a383755"
NAV_CHAR_UUID = "6b16fa29-fdf4-4eed-a96a-3fc13b8d85db"   #phone writes packets here

PACKET_VERSION = 1
HEADER_FMT = "<BBHHB"   #version, turn, dist_m, remaining_m, name_len (little endian)
HEADER_SIZE = struct.calcsize(HEADER_FMT)   #7 bytes
MAX_NAME_BYTES = 40     #app truncates street name to this many UTF-8 bytes

STALE_TIMEOUT = 5.0     #no packet for this long -> nav data invalid

#turn types, add new ones at the end so old numbers keep their meaning
TURN_NONE = 0           #no active route
TURN_STRAIGHT = 1
TURN_LEFT = 2
TURN_RIGHT = 3
TURN_SLIGHT_LEFT = 4
TURN_SLIGHT_RIGHT = 5
TURN_SHARP_LEFT = 6
TURN_SHARP_RIGHT = 7
TURN_UTURN = 8
TURN_ROUNDABOUT = 9
TURN_ARRIVE = 10
TURN_FORK_LEFT = 11
TURN_FORK_RIGHT = 12
TURN_MERGE = 13
TURN_RAMP_LEFT = 14
TURN_RAMP_RIGHT = 15

TURN_NAMES = {
    TURN_NONE: "none",
    TURN_STRAIGHT: "straight",
    TURN_LEFT: "left",
    TURN_RIGHT: "right",
    TURN_SLIGHT_LEFT: "slight left",
    TURN_SLIGHT_RIGHT: "slight right",
    TURN_SHARP_LEFT: "sharp left",
    TURN_SHARP_RIGHT: "sharp right",
    TURN_UTURN: "u-turn",
    TURN_ROUNDABOUT: "roundabout",
    TURN_ARRIVE: "arrive",
    TURN_FORK_LEFT: "fork left",
    TURN_FORK_RIGHT: "fork right",
    TURN_MERGE: "merge",
    TURN_RAMP_LEFT: "ramp left",
    TURN_RAMP_RIGHT: "ramp right",
}


class NavData:
    def __init__(self, turn=TURN_NONE, dist=0, remaining=0, street="", valid=False):
        self.turn = turn            #turn type, one of TURN_*
        self.dist = dist            #distance to the turn (m)
        self.remaining = remaining  #distance left on the route (m), 0 if app doesn't send it
        self.street = street        #street name to turn onto
        self.valid = valid          #true if a good packet came in within STALE_TIMEOUT
        self.last_update = 0.0      #time.monotonic() of last good packet


def pack_nav(turn: int, dist: int, street: str, remaining: int = 0) -> bytes:
    """
    - builds a packet, reference for the app side + used for testing
    - distances are clamped to 0..65535 m (uint16)
    - street name is cut to MAX_NAME_BYTES without splitting a UTF-8 character
    """
    name = street.encode("utf-8")[:MAX_NAME_BYTES].decode("utf-8", errors="ignore").encode("utf-8")
    dist = max(0, min(int(dist), 0xFFFF))
    remaining = max(0, min(int(remaining), 0xFFFF))
    return struct.pack(HEADER_FMT, PACKET_VERSION, turn, dist, remaining, len(name)) + name


def unpack_nav(data: bytes) -> NavData | None:
    """
    - parses a packet from the app
    - returns None if the packet is too short, wrong version, or name length doesn't match
    """
    if len(data) < HEADER_SIZE:
        return None
    version, turn, dist, remaining, name_len = struct.unpack_from(HEADER_FMT, data)
    if version != PACKET_VERSION or len(data) < HEADER_SIZE + name_len:
        return None
    street = bytes(data[HEADER_SIZE:HEADER_SIZE + name_len]).decode("utf-8", errors="replace")
    return NavData(turn, dist, remaining, street, valid=True)


def check_stale(nav: NavData) -> NavData:
    """
    - marks nav invalid if no packet for STALE_TIMEOUT sec (phone disconnected or app closed)
    - old values are kept so the display can choose what to show
    """
    if nav.valid and time.monotonic() - nav.last_update > STALE_TIMEOUT:
        nav.valid = False
    return nav
