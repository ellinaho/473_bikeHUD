"""
SixOS - the operating system powering the SixVision helmet
User Interface Design by Ishan Kumar

Run standalone to test:
    python3 display.py            # fullscreen at the panel's native resolution (what the Pi does)
    python3 display.py --window   # 640x360 window for dev on a laptop
"""

import io
import math
import os
import re
import sys
import pygame
import random
import time
from datetime import datetime

from phone_packet import TURN_NAMES, TURN_NONE, format_imperial

# color definitions
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
GREY = (90, 90, 90)
RED = (232, 44, 30)
GREEN = (60, 200, 90)
LIGHT_GREY = (170, 170, 170)

# assets path
ASSETS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")

# Hard-coded mock values until real data is wired in
DISPLAY_DATA = {
    "speed": 15,
    "units": "mph",
    "mode": 0,
    "nav_valid": False,
    "turn_dist": 0,
    "turn_distance": "0 ft",
    "turn_direction": None,
    "time": "4:00 PM",
    "radar_alert": False,
    "radar_alert_angle": 0,
    "debug": False,          # short click toggles the debug screen
    "debug_cols": [[], []],  # [(text, color, is_header), ...] for left / right column
}

ticks = 0

def load_svg(name: str, height: int) -> pygame.Surface:
    """Load an SVG from the assets folder, rasterized at the given height (aspect preserved).

    This function is important because earlier I was running into issues where SVGs would
    look very blurry when scaled up. This fucntion fixes that.
    """
    path = os.path.join(ASSETS, name)
    svg = open(path, encoding="utf-8").read()
    vb = re.search(r'viewBox="([\d.\s-]+)"', svg)
    _, _, vw, vh = map(float, vb.group(1).split())
    width = max(1, round(vw * height / vh))
    svg = re.sub(r'\s(width|height)="[^"]*"', "", svg, count=2)  # drop any declared size
    svg = svg.replace("<svg", f'<svg width="{width}" height="{height}"', 1)
    img = pygame.image.load(io.BytesIO(svg.encode("utf-8")), name).convert_alpha()
    # force white: pygame's SVG rasterizer ignores CSS <style> fills, leaving them black
    img.fill(WHITE + (0,), special_flags=pygame.BLEND_RGBA_ADD)
    return img


def draw_arc(surface, color, center, radius, start_deg, end_deg, width):
    """Helper function to draw arc bands. Angles in degrees, 0 = right, 90 = up, counterclockwise."""
    cx, cy = center
    steps = max(2, int(abs(end_deg - start_deg)))
    outer, inner = [], []
    for i in range(steps + 1):
        a = math.radians(start_deg + (end_deg - start_deg) * i / steps)
        outer.append((cx + radius * math.cos(a), cy - radius * math.sin(a)))
        inner.append((cx + (radius - width) * math.cos(a), cy - (radius - width) * math.sin(a)))
    pygame.draw.polygon(surface, color, outer + inner[::-1])


class SixVisionDisplay:
    def __init__(self, width: int = 0, height: int = 0, fullscreen: bool = True, fps: int = 30):
        # width/height of 0 means "use the current screen resolution" when fullscreen
        self.width = width
        self.height = height
        self.fullscreen = fullscreen
        self.fps = fps
        self.screen = None
        self.clock = None
        self.display_on = True

    def display_init(self) -> bool:
        """Open the window, hide the cursor, load fonts and assets once. Returns False if the panel can't be opened."""
        pygame.init()
        flags = pygame.FULLSCREEN if self.fullscreen else 0
        try:
            self.screen = pygame.display.set_mode((self.width, self.height), flags)
        except pygame.error as e:
            print(f"[DISPLAY] Could not open display: {e}")
            return False

        # read back the real size in case we asked for (0, 0)
        self.width, self.height = self.screen.get_size()
        pygame.display.set_caption("SixOS")
        pygame.mouse.set_visible(False)
        self.clock = pygame.time.Clock()

        H = self.height
        # using the SF Pro font (thank you apple ily)
        display_bold = os.path.join(ASSETS, "SF-Pro-Display-Bold.otf")
        text_bold = os.path.join(ASSETS, "SF-Pro-Text-Bold.otf")
        self.font_speed = pygame.font.Font(display_bold, int(H * 0.36))
        self.font_units = pygame.font.Font(display_bold, int(H * 0.14))
        self.font_small = pygame.font.Font(text_bold, int(H * 0.09))
        self.font_debug_head = pygame.font.Font(display_bold, int(H * 0.06))
        self.font_debug = pygame.font.Font(text_bold, int(H * 0.045))
        self.logo = load_svg("smallLogo.svg", int(H * 0.17))
        self.turn_icon_left = load_svg("turnLeft.svg", int(H * 0.19))
        self.turn_icon_right = load_svg("turnRight.svg", int(H * 0.19))

        print(f"Started SixOS with dimensions {self.width}x{self.height}")
        return True

    def handle_command(self, cmd: str):
        """Handle a high-level UI command from the main loop."""
        if cmd == "toggle_display":
            self.display_on = not self.display_on
            if not self.display_on:
                self.screen.fill(BLACK)
                pygame.display.flip()
        return self.display_on

    def render(self):
        """Draw one frame and push it to the screen."""
        if not self.display_on:
            if self.screen is not None:
                self.screen.fill(BLACK)
                pygame.display.flip()
                self.clock.tick(self.fps)
            return

        if DISPLAY_DATA["debug"]:
            self.render_debug()
            return

        W, H = self.width, self.height
        s = self.screen

        # set background. becomes transparent when projected on vision
        s.fill(BLACK)

        center = (W / 2, -H * 0.095)

        # main ring: gray circle centred above the top edge so only the lower arc shows
        draw_arc(s, GREY, center, H * 0.71, 180, 360, H * 0.025)

        # red car indicators, just outside the ring
        if DISPLAY_DATA["mode"] != 1 and DISPLAY_DATA["radar_alert"]:
            display_angle = 270 - DISPLAY_DATA["radar_alert_angle"]
            draw_arc(s, RED, center, H * 0.785,
                     max(180, display_angle - 10), min(360, display_angle + 10), H * 0.028)

        # speed + units
        if DISPLAY_DATA["mode"] != 2:
            speed = self.font_speed.render(str(DISPLAY_DATA["speed"]), True, WHITE)
            s.blit(speed, speed.get_rect(center=(W / 2, H * 0.235)))
            units = self.font_units.render(DISPLAY_DATA["units"], True, WHITE)
            s.blit(units, units.get_rect(center=(W / 2, H * 0.46)))

        # next turn, bottom-left
        if DISPLAY_DATA["nav_valid"]:
            if DISPLAY_DATA["turn_direction"] == "left":
                s.blit(self.turn_icon_left, self.turn_icon_left.get_rect(topleft=(W * 0.05, H * 0.64)))
            elif DISPLAY_DATA["turn_direction"] == "right":
                s.blit(self.turn_icon_right, self.turn_icon_right.get_rect(topleft=(W * 0.05, H * 0.64)))
            dist = self.font_small.render(DISPLAY_DATA["turn_distance"], True, WHITE)
            s.blit(dist, dist.get_rect(midleft=(W * 0.05, H * 0.875)))

        # logo, bottom-centre
        s.blit(self.logo, self.logo.get_rect(center=(W / 2, H * 0.84)))

        # clock, bottom-right
        clock = self.font_small.render(DISPLAY_DATA["time"], True, WHITE)
        s.blit(clock, clock.get_rect(midright=(W * 0.95, H * 0.875)))

        pygame.display.flip()
        self.clock.tick(self.fps)

    def render_debug(self):
        """Debug screen: two columns of sensor / link status built by build_debug_cols()."""
        W, H = self.width, self.height
        s = self.screen
        s.fill(BLACK)

        title = self.font_debug_head.render("DEBUG  (click to exit)", True, WHITE)
        s.blit(title, (W * 0.04, H * 0.03))
        clock = self.font_debug.render(DISPLAY_DATA["time"], True, LIGHT_GREY)
        s.blit(clock, clock.get_rect(topright=(W * 0.96, H * 0.04)))

        for col, x in zip(DISPLAY_DATA["debug_cols"], (W * 0.04, W * 0.52)):
            y = H * 0.15
            for text, color, header in col:
                if header:
                    y += H * 0.02
                font = self.font_debug_head if header else self.font_debug
                s.blit(font.render(text, True, color), (x, y))
                y += font.get_linesize()

        pygame.display.flip()
        self.clock.tick(self.fps)

    def should_quit(self) -> bool:
        """Drain the event queue. True if the window was closed or ESC was pressed."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return True
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                return True
        return False

    def display_close(self):
        """Release the display on shutdown."""
        pygame.quit()

# ELLINA <------------------------------------------------------
# this function is for YOU
# everything inside here is mock data. So feel free to delete
# it all and update the DISPLAY_DATA however you want, and integrate
# with the data sources. Note, this runs ~30 times per second
# ---
# i would recomend keeping the ticks tho since it helps with scheduling
# periodic functions/polling/sensor reading
# ---
# I would also reccomend keeping the time update
def _age(t):
    """'1.2s ago' for a time.monotonic() timestamp, 'never' if 0."""
    return f"{time.monotonic() - t:.1f}s ago" if t else "never"


def build_debug_cols(state):
    """Debug screen text. Left: GPS + BLE links. Right: radar packet + nav packet."""
    H, T = True, False   # header / normal line

    # --- GPS ---
    g = state.gps
    gps = [("GPS", WHITE, H)]
    if g is None:
        gps.append(("no data from GPS", RED, T))
    else:
        gps.append((f"fix: {'YES' if g.valid else 'NO'}   sats: {g.sats}   hdop: {g.hdop:.1f}",
                    GREEN if g.valid else RED, T))
        gps.append((f"lat {g.lat:.5f}   lon {g.lon:.5f}", WHITE, T))
        gps.append((f"speed {g.speed:.1f} kph   hdg {g.heading:.0f}\u00b0", WHITE, T))
        gps.append((f"dist {g.dist:.2f} km", WHITE, T))
    gps.append((f"last update: {_age(state.gps_time)}", LIGHT_GREY, T))

    # --- BLE links ---
    b = state.ble or {}
    ble = [("BLE", WHITE, H)]
    if state.ble is None:
        ble.append(("no status from watchdog yet", RED, T))
    else:
        ble.append((f"ESP32: {'connected' if b.get('esp') else 'DISCONNECTED'}",
                    GREEN if b.get("esp") else RED, T))
        ble.append((f"phone: {b.get('phone') or 'DISCONNECTED'}",
                    GREEN if b.get("phone") else RED, T))

    # --- Radar packet ---
    r = state.radar or {}
    threat = r.get("tier", 0) > 0
    raw = r.get("raw", "").split()
    radar = [("RADAR", WHITE, H),
             (f"threat: {'YES' if threat else 'no'}", RED if threat else GREEN, T),
             (f"dist {r.get('dist', 0.0):.2f} m   speed {r.get('speed', 0.0):.2f} m/s", WHITE, T),
             (f"angle {r.get('angle', 0.0):.1f}\u00b0", WHITE, T)]
    for i in range(0, len(raw), 8):
        radar.append((("raw: " if i == 0 else "     ") + " ".join(raw[i:i + 8]), LIGHT_GREY, T))
    radar.append((f"pkts {b.get('radar_count', 0)}   last: {_age(state.radar_time)}", LIGHT_GREY, T))

    # --- Nav packet ---
    n = state.nav
    nav = [("NAV", WHITE, H)]
    if n is None:
        nav.append(("no data from phone", RED, T))
    else:
        nav.append((f"valid: {'YES' if n.valid else 'NO'}", GREEN if n.valid else RED, T))
        nav.append((f"{TURN_NAMES.get(n.turn, n.turn)} in {format_imperial(n.dist)}", WHITE, T))
        nav.append((f"'{n.street}'", WHITE, T))
        nav.append((f"last update: {_age(n.last_update)}", LIGHT_GREY, T))

    return [gps + ble, radar + nav]


def update_display_data(state=None):
    """Function that runs every 1/30 seconds and updates the display data.

    When a HUD state object is provided, it maps the live sensor data into the
    display's data dictionary. Without a state, it keeps the mock demo values.
    """

    global ticks

    if state is not None:
        DISPLAY_DATA["mode"] = int(state.mode)
        DISPLAY_DATA["debug"] = getattr(state, "debug", False)
        if DISPLAY_DATA["debug"]:
            DISPLAY_DATA["debug_cols"] = build_debug_cols(state)

        if state.gps and getattr(state.gps, "valid", False):
            speed_kph = float(getattr(state.gps, "speed", 0.0))
            DISPLAY_DATA["speed"] = max(0, int(speed_kph * 0.621371))
            DISPLAY_DATA["units"] = "mph"
        else:
            DISPLAY_DATA["speed"] = 0
            DISPLAY_DATA["units"] = "mph"

        if state.nav and getattr(state.nav, "valid", False):
            turn_code = getattr(state.nav, "turn", 0)
            turn_name = TURN_NAMES.get(turn_code, "").lower()
            if "left" in turn_name:
                DISPLAY_DATA["turn_direction"] = "left"
            elif "right" in turn_name:
                DISPLAY_DATA["turn_direction"] = "right"
            else:
                DISPLAY_DATA["turn_direction"] = None
            DISPLAY_DATA["nav_valid"] = turn_code != TURN_NONE
            DISPLAY_DATA["turn_distance"] = format_imperial(int(getattr(state.nav, "dist", 0)))
        else:
            DISPLAY_DATA["nav_valid"] = False
            DISPLAY_DATA["turn_dist"] = 0
            DISPLAY_DATA["turn_distance"] = "0 ft"
            DISPLAY_DATA["turn_direction"] = None

        if state.radar and state.radar.get("tier", 0) > 0:
            DISPLAY_DATA["radar_alert"] = True
            DISPLAY_DATA["radar_alert_angle"] = float(state.radar.get("angle", 0.0))
        else:
            DISPLAY_DATA["radar_alert"] = False
            DISPLAY_DATA["radar_alert_angle"] = 0

        DISPLAY_DATA["time"] = datetime.now().strftime("%I:%M %p")
        return

    # 30 ticks = ~1s
    if (ticks % 5) == 0:
        DISPLAY_DATA["speed"] += int((random.random() * 4) - 2)
        if DISPLAY_DATA["speed"] < 1:
            DISPLAY_DATA["speed"] = 1

    if (ticks % 25) == 0:
        if (DISPLAY_DATA["turn_dist"] == 0):
            DISPLAY_DATA["turn_dist"] = 500
            DISPLAY_DATA["turn_direction"] = "left" if DISPLAY_DATA["turn_direction"] == "right" else "right"

        DISPLAY_DATA["turn_dist"] -= 50
        DISPLAY_DATA["nav_valid"] = True
        DISPLAY_DATA["turn_distance"] = f'{DISPLAY_DATA["turn_dist"]} ft'

    DISPLAY_DATA["radar_alert_angle"] = ((DISPLAY_DATA["radar_alert_angle"] - 2 + 90) % 180) - 90
    DISPLAY_DATA["radar_alert"] = True

    now = datetime.now()
    DISPLAY_DATA["time"] = now.strftime("%H:%M %p")

    if ticks == 100000:
        ticks = 0

    ticks += 1

# --- Main ---
if __name__ == "__main__":
    # window mode for easy laptop dev away from pi
    if "--window" in sys.argv:
        display = SixVisionDisplay(width=640, height=360, fullscreen=False)
    else:
        display = SixVisionDisplay()

    if not display.display_init():
        sys.exit(1)

    try:
        # only keep the display on while window open
        # (lets the x button close it)
        while not display.should_quit():
            update_display_data()
            display.render()
    except KeyboardInterrupt:
        pass
    finally:
        display.display_close()