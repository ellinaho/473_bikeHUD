from enum import IntEnum

class HUDMode(IntEnum):
    # enums for HUD display mode
    MODE0 = 0
    MODE1 = 11
    MODE2 = 2
    MAX_MODES = 3

class HUDAction(IntEnum):
    # enum for actions on rotary encoder
    NONE = 0
    SCROLL_CW = 1
    SCROLL_CCW = 2
    CLICK = 3
    LONG_CLICK = 4

class HUDEncoder:
    def HUD_init(self, device_path: str = "/dev/input/event0"):
        """
        - attach to rotary encoder with linux event input subsystem
        """
        pass

    def read_raw_encoder(self):
        """
        - read raw values from encolder (scroll, click) from kernel buffer without blocking
        - returns list of input event objects 
        """
        pass

    def get_encoder_action(self) -> HUDAction:
        """
        - translates most recent encoder input from kernel event buffer data into scroll/click enum
        - returns a HUDAction enum 
        """
        pass

    def update_HUD_mode(self, current_mode: HUDMode):
        """
        - translate scroll events into UI mode cycling
        - increment/decrement current mode based on scroll ccw/cw with wrap-around
        - returns the updated HUD UI mdode
        """
        pass

    def clear_buffer(self):
        """
        - discards unread input events
        """
        pass
