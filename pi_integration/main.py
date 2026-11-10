import threading
import queue
import time
import asyncio
import struct
from copy import copy
from bleak import BleakClient

# --- Import custom peripherals ---
from gps import PA1616D_GPS
from encoder import HUDEncoder, HUDMode, HUDAction
from phone_receiver import PhoneReceiver
from display import SixVisionDisplay, update_display_data

# --- Global State Struct ---
class HUDState:
    def __init__(self):
        self.radar = {"tier": 0, "dist": 0.0, "speed": 0.0, "angle": 0.0}
        self.gps = None
        self.nav = None
        self.mode = HUDMode.MODE0

# --- Worker Threads ---

def run_radar(q):
    """Background task for ESP32 BLE Radar connection."""
    ESP32_MAC = "8c:94:df:b8:5a:0a"
    CHARACTERISTIC_UUID = "beb5483e-36e1-4688-b7f5-ea07361b26a8"

    def handle_radar_packet(sender, data):
        # Extract 3 floats and 1 bool to match the C++ struct
        dist, angle, speed, is_valid = struct.unpack('<fff?', data[:13])
        tier = 1 if is_valid else 0
        # Priority 1: Safety Critical
        q.put((1, time.monotonic(), ("radar", {"tier": tier, "dist": dist, "speed": speed, "angle": angle})))

    async def esp32_worker():
        while True:
            try:
                async with BleakClient(ESP32_MAC) as client:
                    await client.start_notify(CHARACTERISTIC_UUID, handle_radar_packet)
                    while client.is_connected:
                        await asyncio.sleep(1.0)
            except asyncio.CancelledError:
                break
            except Exception as e:
                await asyncio.sleep(2.0)
                
    asyncio.run(esp32_worker())

def nav_worker(q):
    """Runs the phone BLE GATT server."""
    async def run():
        rx = PhoneReceiver()
        await rx.start()
        while True:
            # Priority 2: Navigation
            q.put((2, time.monotonic(), ("nav", rx.get_nav())))
            await asyncio.sleep(1.0)
    asyncio.run(run())

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

    # Timer for the mock radar alert
    state.clear_radar_time = 0.0

    # Initialize graphics engine using the new display implementation
    display = SixVisionDisplay()
    if not display.display_init():
        raise RuntimeError("Failed to initialize SixVision display")

    # Start all hardware peripherals as background daemon threads
    threading.Thread(target=gps_worker, args=(event_queue,), daemon=True).start()
    threading.Thread(target=encoder_worker, args=(event_queue,), daemon=True).start()
    threading.Thread(target=nav_worker, args=(event_queue,), daemon=True).start()
    threading.Thread(target=run_radar, args=(event_queue,), daemon=True).start()

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
                    elif source == "gps":
                        state.gps = data
                    elif source == "nav":
                        state.nav = data
                    elif source == "encoder":
                        state.mode = data["mode"]
                        cmd = data["cmd"]
                        
                        # --- Process the physical clicks ---
                        if cmd == "toggle_display":
                            display.handle_command(cmd)
                        elif cmd == "click_only":
                            print("[TEST] Fake radar alert injected!")
                            state.radar = {"tier": 1, "dist": 12.4, "speed": 30.0, "angle": 240.0}
                            state.clear_radar_time = time.monotonic() + 3.0
                            
                except queue.Empty:
                    break

            # 2. Automatically clear the fake radar alert after 3 seconds
            if state.clear_radar_time > 0 and time.monotonic() > state.clear_radar_time:
                state.radar = {"tier": 0, "dist": 0.0, "speed": 0.0, "angle": 0.0}
                state.clear_radar_time = 0.0

            # update the shared display data before rendering
            update_display_data(state)

            # render will now respect the display object's own on/off state
            display.render()
            
    except KeyboardInterrupt:
        print("\nShutting down HUD Engine.")
    finally:
        display.display_close()

if __name__ == "__main__":
    main()
