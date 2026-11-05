import threading
import queue
import time
import asyncio
import struct
from bleak import BleakClient

# --- Import custom peripherals ---
from gps import PA1010D_GPS
from encoder import HUDEncoder, HUDMode, HUDAction
from phone_receiver import PhoneReceiver
from hud import HUDDisplay

# --- Global State Struct ---
class HUDState:
    def __init__(self):
        self.radar = {"tier": 0, "dist": 0.0, "speed": 0.0, "angle": 0.0}
        self.gps = None
        self.nav = None
        self.mode = HUDMode.MODE0
        self.display_on = True

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
    """Runs the I2C GPS reads."""
    gps = PA1010D_GPS()
    if not gps.gps_init():
        print("[GPS] Failed to initialize")
        return
        
    while True:
        if gps.get_nmea_data():
            d = gps.update_gps_obj()
            # Priority 3: Speed tracking
            q.put((3, time.monotonic(), ("gps", d)))
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
    
    # Initialize graphics engine
    display = HUDDisplay()

    # Start all hardware peripherals as background daemon threads
    threading.Thread(target=gps_worker, args=(event_queue,), daemon=True).start()
    threading.Thread(target=encoder_worker, args=(event_queue,), daemon=True).start()
    threading.Thread(target=nav_worker, args=(event_queue,), daemon=True).start()
    threading.Thread(target=run_radar, args=(event_queue,), daemon=True).start()

    print("BikeHUD Engine running. Waiting for sensor data...")

    try:
        while True:
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
                        if data["cmd"] == "toggle_display":
                            state.display_on = not state.display_on
                            
                except queue.Empty:
                    break
            
            # 2. Render the display
            display.render(state)
            
            # 3. Lock framerate to ~30 FPS
            time.sleep(0.033)
            
    except KeyboardInterrupt:
        print("\nShutting down HUD Engine.")

if __name__ == "__main__":
    main()