import os
import sys
import threading
import queue
import time
from copy import copy

# --- Import custom peripherals ---
from gps import PA1616D_GPS
from encoder import HUDEncoder, HUDMode, HUDAction
from ble_watchdog import ble_worker
from display import SixVisionDisplay, update_display_data
import web_view

# --- Global State Struct ---
class HUDState:
    def __init__(self):
        self.radar = {"tier": 0, "dist": 0.0, "speed": 0.0, "angle": 0.0}
        self.gps = None
        self.nav = None
        self.mode = HUDMode.MODE0
        self.ble = None          # link status from ble_watchdog
        self.gps_time = 0.0      # monotonic time of last GPS / radar update (debug screen)
        self.radar_time = 0.0
        self.debug = False       # short click toggles the debug screen

# --- Worker Threads ---

def gps_worker(q):
    """Runs the UART GPS reads."""
    gps = PA1616D_GPS()
    if not gps.gps_init():
        print("[GPS] Failed to initialize")
        return

    last_valid = None
    while True:
        new_reading = gps.get_nmea_data()
        # update_gps_obj also detects stale fixes when no new sentence arrives
        d = gps.update_gps_obj()
        if new_reading or d.valid != last_valid:
            q.put((3, time.monotonic(), ("gps", copy(d))))
            last_valid = d.valid
        time.sleep(0.05)

def encoder_worker(q):
    """Listens to kernel input events."""
    enc = HUDEncoder()
    try:
        enc.encoder_init() 
        enc.clear_buff() 
    except FileNotFoundError:
        print("[ENCODER] Not found in /dev/input")
        return
        
    curr_mode = HUDMode.MODE0
    
    while True:
        action = enc.get_encoder_action()
        if action != HUDAction.NONE:
            new_mode = enc.update_HUD_mode(curr_mode, action)
            curr_mode = new_mode
            # Priority 4: UI Updates
            q.put((4, time.monotonic(), ("encoder", {"mode": new_mode, "action": action, "cmd": enc.handle_clicks(action)})))
        time.sleep(0.01)

# --- Main Engine ---
def main():
    event_queue = queue.PriorityQueue()
    state = HUDState()

    # Initialize graphics engine using the new display implementation
    # --window: 640x360 window instead of fullscreen (e.g. X11-forwarded over ssh -Y)
    # --web: no window at all; view the HUD in a browser at http://<pi-address>:8000
    web = "--web" in sys.argv
    if web:
        os.environ["SDL_VIDEODRIVER"] = "dummy"
        web_view.start()
    if web or "--window" in sys.argv:
        display = SixVisionDisplay(width=640, height=360, fullscreen=False)
    else:
        display = SixVisionDisplay()
    if not display.display_init():
        raise RuntimeError("Failed to initialize SixVision display")

    # Start all hardware peripherals as background daemon threads
    threading.Thread(target=gps_worker, args=(event_queue,), daemon=True).start()
    threading.Thread(target=encoder_worker, args=(event_queue,), daemon=True).start()
    # Both BLE links (ESP radar + phone nav) with auto-reconnect
    threading.Thread(target=ble_worker, args=(event_queue,), daemon=True).start()

    print("BikeHUD Engine running. Waiting for sensor data...")

    try:
        while True:
            if display.should_quit():
                break

            # 1. Drain the priority queue
            while not event_queue.empty():
                try:
                    priority_rank, timestamp, payload = event_queue.get_nowait()
                    source, data = payload
                    
                    if source == "radar":
                        state.radar = data
                        state.radar_time = timestamp
                    elif source == "gps":
                        state.gps = data
                        state.gps_time = timestamp
                    elif source == "nav":
                        state.nav = data
                    elif source == "ble":
                        state.ble = data
                    elif source == "encoder":
                        state.mode = data["mode"]
                        cmd = data["cmd"]
                        
                        # --- Process the physical clicks ---
                        if cmd == "toggle_display":
                            display.handle_command(cmd)
                        elif cmd == "click_only":
                            state.debug = not state.debug
                            print(f"[UI] Debug screen {'ON' if state.debug else 'OFF'}")
                            
                except queue.Empty:
                    break

            # update the shared display data before rendering
            update_display_data(state)

            # render will now respect the display object's own on/off state
            display.render()
            if web:
                web_view.publish(display.screen)
            
    except KeyboardInterrupt:
        print("\nShutting down HUD Engine.")
    finally:
        display.display_close()

if __name__ == "__main__":
    main()
