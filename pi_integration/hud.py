import board
import digitalio
import adafruit_rgb_display.st7735 as st7735
from phone_packet import TURN_NAMES
from PIL import Image, ImageDraw, ImageFont, ImageOps

class HUDDisplay:
    def __init__(self):
        # 1. Define SPI and Command Pins
        self.cs_pin = digitalio.DigitalInOut(board.D16)
        self.dc_pin = digitalio.DigitalInOut(board.D25)
        self.reset_pin = digitalio.DigitalInOut(board.D24)

        # 2. Setup Backlight Control
        self.backlight = digitalio.DigitalInOut(board.D26)
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
            blank = Image.new("RGB", (self.width, self.height), color=(0, 0, 0))
            self.disp.image(blank)
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
            draw.text((10, 5), "RADAR RAW DATA", font=self.font_small, fill=(255, 255, 255))
            
            if radar_valid:
                # Extract all variables (defaults to 0 if not found)
                tier = state.radar.get("tier", 1)
                speed = state.radar.get("speed", 0.0) 
                angle = state.radar.get("angle", 0.0)
                
                # Draw the stacked metrics
                draw.text((10, 22), f"DIST:  {radar_dist:.1f} m", font=self.font_small, fill=(255, 0, 0))
                draw.text((10, 37), f"SPEED: {speed:.1f} m/s", font=self.font_small, fill=(255, 100, 100))
                draw.text((10, 52), f"ANGLE: {angle:.1f} deg", font=self.font_small, fill=(255, 150, 0))
                draw.text((10, 67), f"TIER:  {tier}", font=self.font_small, fill=(255, 255, 0))
            else:
                draw.text((10, 30), "CLEAR", font=self.font_large, fill=(0, 255, 0))

        elif current_mode == "MODE2":
            # Mode 2: Nav / Diagnostic
            draw.text((10, 5), "SYSTEM", font=self.font_small, fill=(255, 255, 255))
            gps_status = "FIX" if (state.gps and state.gps.valid) else "NO FIX"
            draw.text((10, 25), f"GPS: {gps_status}", font=self.font_small, fill=(255, 255, 255))
            
            if state.nav and state.nav.valid:
                # Translate the integer (e.g., 1) to a word (e.g., "Right")
                turn_str = TURN_NAMES.get(state.nav.turn, str(state.nav.turn))
                
                # Stack the instructions vertically to fit the TFT screen
                draw.text((10, 45), f"{turn_str} in {state.nav.dist:.0f} ft", font=self.font_small, fill=(0, 255, 0))
                draw.text((10, 60), f"{state.nav.street}", font=self.font_small, fill=(0, 150, 255))
                
        # Mirror the image for the HUD optic flip
        # image = ImageOps.mirror(image)

        # Send the final image to the TFT
        self.disp.image(image)


if __name__ == "__main__":
    import time

    # 1. Create a dummy state structure to mimic main.py
    class MockMode:
        def __init__(self, name):
            self.name = name

    class MockGPS:
        def __init__(self):
            self.speed = 24.5  # kph
            self.valid = True

    class MockNav:
        def __init__(self):
            self.turn = "RIGHT on South State St"
            self.valid = True

    class MockState:
        def __init__(self):
            self.display_on = True
            self.mode = MockMode("MODE0")
            self.gps = MockGPS()
            self.nav = MockNav()
            self.radar = {"tier": 1, "dist": 8.5}

    # 2. Run the test loop
    print("Testing HUD Display Graphics...")
    try:
        display = HUDDisplay()
        test_state = MockState()
        
        while True:
            # Render the current mock state
            display.render(test_state)
            
            # Simulate cycling through the modes every 2 seconds
            time.sleep(2.0)
            if test_state.mode.name == "MODE0":
                test_state.mode.name = "MODE1"
            elif test_state.mode.name == "MODE1":
                test_state.mode.name = "MODE2"
            else:
                test_state.mode.name = "MODE0"
                
    except KeyboardInterrupt:
        print("\nExiting display test.")
