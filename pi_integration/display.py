"""
HUD display for the Raspberry Pi, drawn with pygame to the HDMI output.

Run standalone to test:
    python3 display.py            # fullscreen at the panel's native resolution (what the Pi does)
    python3 display.py --window   # 800x480 window for dev on a laptop
"""

import sys
import pygame

BLACK = (0, 0, 0)
WHITE = (255, 255, 255)


class SixVisionDisplay:
    def __init__(self, width: int = 0, height: int = 0, fullscreen: bool = True, fps: int = 30):
        # width/height of 0 means "use the current screen resolution" when fullscreen
        self.width = width
        self.height = height
        self.fullscreen = fullscreen
        self.fps = fps
        self.screen = None
        self.clock = None
        self.font = None

    def display_init(self) -> bool:
        """Open the window, hide the cursor, load the font once. Returns False if the panel can't be opened."""
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
        self.font = pygame.font.Font(None, int(self.height * 0.25))
        print(f"Started SixOS with dimensions {self.width}x{self.height}")
        return True

    def render(self):
        """Draw one frame and push it to the screen."""
        self.screen.fill(BLACK)

        text = self.font.render("hi", True, WHITE)
        self.screen.blit(text, text.get_rect(center=self.screen.get_rect().center))

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


# --- Main ---
if __name__ == "__main__":
    # window mode for easy laptop dev away from pi
    if "--window" in sys.argv:
        display = SixVisionDisplay(width=800, height=450, fullscreen=False)
    else:
        display = SixVisionDisplay()

    if not display.display_init():
        sys.exit(1)

    try:
        # only keep the display on while window open
        # (lets the x button close it)
        while not display.should_quit():
            display.render()
    except KeyboardInterrupt:
        pass
    finally:
        display.display_close()
