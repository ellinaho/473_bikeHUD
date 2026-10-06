import time
from enum import IntEnum
try:
    import evdev
except ImportError:
    raise ImportError("Install with: pip install evdev")

class HUDMode(IntEnum):
    MODE0 = 0
    MODE1 = 1
    MODE2 = 2
    MAX_MODES = 3

class HUDAction(IntEnum):
    NONE = 0
    SCROLL_CW = 1
    SCROLL_CCW = 2
    SHORT_PRESS = 3
    LONG_PRESS = 4

class HUDEncoder:
    def __init__(self):
        self.devices = []
        self.time_pressed = 0.0
        self.long_press_thresh = 0.5  # seconds

    def encoder_init(self, target_names: list = ["rotary", "enter"]):
        """
        Find and attach device 
        """
        device_paths = evdev.list_devices()
        
        for path in device_paths:
            dev = evdev.InputDevice(path)
            # if device names contains rotary or enter 
            if any(target.lower() in dev.name.lower() for target in target_names):
                self.devices.append(dev)
                print(f"connected to {dev.name} -> {dev.path}")
                
        if not self.devices:
            raise FileNotFoundError("cannot find encoder! check hardware or dtoverlay")

    def read_raw_encoder(self) -> list:
        """read raw values of button and spinning without blocking"""
        all_events = []
        
        for dev in self.devices:
            try:
                # read button press or spinning, read as ev_rel ev_key
                all_events.extend(list(dev.read()))
            except BlockingIOError:
                continue
                
        return all_events

    def get_encoder_action(self) -> HUDAction:
        """translate encoder input"""
        events = self.read_raw_encoder()
        action = HUDAction.NONE
        
        for event in events:
            # for spinning
            if event.type == evdev.ecodes.EV_REL:
                if event.value > 0:
                    action = HUDAction.SCROLL_CW
                elif event.value < 0:
                    action = HUDAction.SCROLL_CCW
            
            # for clicking
            elif event.type == evdev.ecodes.EV_KEY:
                if event.value == 1:  # key was pressed down (falling edge)
                    self.time_pressed = event.timestamp()
                elif event.value == 0:  # key was released (rising)
                    press_duration = event.timestamp() - self.time_pressed
                    if press_duration >= self.long_press_thresh:
                        action = HUDAction.LONG_PRESS
                    else:
                        action = HUDAction.SHORT_PRESS
                        
        return action

    def update_HUD_mode(self, curr_mode: HUDMode, action: HUDAction) -> HUDMode:
        """translate encoder events to mode switching on HUD"""
        if action == HUDAction.SCROLL_CW:
            new_mode = (int(curr_mode) + 1) % HUDMode.MAX_MODES
            return HUDMode(new_mode)
            
        elif action == HUDAction.SCROLL_CCW:
            new_mode = (int(curr_mode) - 1) % HUDMode.MAX_MODES
            return HUDMode(new_mode)
            
        return curr_mode

    def handle_clicks(self, action: HUDAction) -> str:
        """translate click actions into commands"""
        if action == HUDAction.LONG_PRESS:
            return "toggle_display"
        elif action == HUDAction.SHORT_PRESS:
            return "click_onlyD"
            
        return "NONE"

    def clear_buff(self):
        """throw away unread events in buffer"""
        self.read_raw_encoder()

# --- Main ---
if __name__ == "__main__":
    encoder = HUDEncoder()
    encoder.encoder_init() 
    
    curr_mode = HUDMode.MODE0
    display_on = True 
    
    print("listening to encoder events:")
    encoder.clear_buff() # flush events during boot
    
    try:
        while True:
            action = encoder.get_encoder_action()
            
            if action != HUDAction.NONE:
                new_mode = encoder.update_HUD_mode(curr_mode, action)
                if new_mode != curr_mode:
                    print(f"Mode changed: {curr_mode.name} -> {new_mode.name}")
                    curr_mode = new_mode
                
                click_cmd = encoder.handle_clicks(action)
                if click_cmd == "toggle_display":
                    display_on = not display_on
                    state_str = "ON" if display_on else "OFF"
                    print(f"Command Executed: Turning Display {state_str}")
                    
                elif click_cmd == "click_only":
                    print(f"Command Executed: User clicked inside {curr_mode.name}")
            
            time.sleep(0.01)
            
    except KeyboardInterrupt:
        print("\nExiting.")