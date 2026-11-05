import board
import digitalio
import adafruit_rgb_display.st7735 as st7735
from PIL import Image, ImageDraw, ImageFont, ImageOps

class HUDDisplay:
    def __init__(self):
        # 1. Define SPI and Command Pins
        self.cs_pin = digitalio.DigitalInOut(board.CE0)
        self.dc_pin = digitalio.DigitalInOut(board.D25)
        self.reset_pin = digitalio.DigitalInOut(board.D24)

        # 2. Setup Backlight Control
        self.backlight = digitalio.DigitalInOut(board.D22)
        self.backlight.direction = digitalio.Direction.OUTPUT
        self.backlight.value = True 

        # 3. Initialize SPI bus
        self.spi = board.SPI()

        # 4. Create the ST7735 display setup
        self.disp = st7735.ST7735R(
            self.spi,
            cs=self.cs_pin,
            dc=self.dc_pin,
            rst=self.reset_pin,
            width=80,
            height=160,
            x_offset=26,
            y_offset=1,
            rotation=90
        )

        self.width = self.disp.height
        self.height = self.disp.width

        # 5. Load TrueType fonts
        try:
            self.font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 12)
            self.font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 20)
        except IOError:
            self.font_small = ImageFont.load_default()
            self.font_large = ImageFont.load_default()

    def render(self, state):
        """Draws the current global state to the screen based on the active mode."""
        # Hardware toggle for the backlight based on state
        self.backlight.value = state.display_on
        
        if not state.display_on:
            return

        # Create a new blank black image for transparency on the combiner glass
        image = Image.new("RGB", (self.width, self.height), color=(0, 0, 0))
        draw = ImageDraw.Draw(image)

        # Extract values safely
        speed_kph = state.gps.speed if (state.gps and state.gps.valid) else 0.0
        mph = speed_kph * 0.621371
        
        radar_dist = state.radar.get("dist", 0.0)
        radar_valid = state.radar.get("tier", 0) > 0 # Using tier as the valid flag
        
        current_mode = state.mode.name # e.g., "MODE0"

        # --- Draw UI based on Encoder Mode ---
        if current_mode == "MODE0":
            # Mode 0: Speed focused
            draw.text((10, 5), "SPEED", font=self.font_small, fill=(255, 255, 255))
            draw.text((10, 25), f"{mph:.1f} MPH", font=self.font_large, fill=(0, 255, 0))
            
            # Show radar alert at bottom if a car is tracking
            if radar_valid:
                draw.text((10, 55), f"CAR: {radar_dist:.1f}m", font=self.font_small, fill=(255, 0, 0))

        elif current_mode == "MODE1":
            # Mode 1: Radar focused
            draw.text((10, 5), "RADAR STATUS", font=self.font_small, fill=(255, 255, 255))
            if radar_valid:
                draw.text((10, 25), f"DIST: {radar_dist:.1f}m", font=self.font_large, fill=(255, 0, 0))
            else:
                draw.text((10, 25), "CLEAR", font=self.font_large, fill=(0, 255, 0))

        elif current_mode == "MODE2":
            # Mode 2: Nav / Diagnostic
            draw.text((10, 5), "SYSTEM", font=self.font_small, fill=(255, 255, 255))
            gps_status = "FIX" if (state.gps and state.gps.valid) else "NO FIX"
            draw.text((10, 25), f"GPS: {gps_status}", font=self.font_small, fill=(255, 255, 255))
            if state.nav and state.nav.valid:
                draw.text((10, 45), f"NAV: {state.nav.turn}", font=self.font_small, fill=(0, 150, 255))

        # Mirror the image for the HUD optic flip
        image = ImageOps.mirror(image)

        # Send the final image to the TFT
        self.disp.image(image)