import threading
import queue
import time
import asyncio

# --- Import existing peripheral classes ---
from gps import PA1616D_GPS
from encoder import HUDEncoder, HUDMode, HUDAction
from phone_receiver import PhoneReceiver
from radar_receiver import run_radar

# --- Global State Struct for the Display ---
class HUDState:
    def __init__(self):
        self.radar = {"tier": 0, "dist": 0, "speed": 0, "angle": 0}
        self.gps = None
        self.nav = None
        self.mode = HUDMode.MODE0
        self.display_on = True

# --- Worker Threads ---
def gps_worker(q):
    """Runs the GPS UART reads"""
    gps = PA1616D_GPS()
    if not gps.gps_init():
        print("[GPS] Failed to initialize")
        return
        
    while True:
        if gps.get_nmea_data():
            d = gps.update_gps_obj()
            q.put((3, time.monotonic(), ("gps", d)))
        time.sleep(0.05)

def encoder_worker(q):
    """Listens to kernel input events"""
    enc = HUDEncoder()
    enc.encoder_init() 
    enc.clear_buff() 
    curr_mode = HUDMode.MODE0
    
    while True:
        action = enc.get_encoder_action()
        if action != HUDAction.NONE:
            new_mode = enc.update_HUD_mode(curr_mode, action)
            curr_mode = new_mode
            q.put((4, time.monotonic(), ("encoder", {"mode": new_mode, "action": action, "cmd": enc.handle_clicks(action)})))
        time.sleep(0.01)

def nav_worker(q):
    """Runs the phone BLE GATT server"""
    async def run():
        rx = PhoneReceiver()
        await rx.start() 
        while True:
            q.put((2, time.monotonic(), ("nav", rx.get_nav())))
            await asyncio.sleep(1.0)
            
    asyncio.run(run())

# --- Main Engine ---
def main():
    event_queue = queue.PriorityQueue()
    state = HUDState()

    # Start all hardware peripherals as background daemon threads
    threading.Thread(target=gps_worker, args=(event_queue,), daemon=True).start()
    threading.Thread(target=encoder_worker, args=(event_queue,), daemon=True).start()
    threading.Thread(target=nav_worker, args=(event_queue,), daemon=True).start()
    threading.Thread(target=run_radar, args=(event_queue,), daemon=True).start()

    print("BikeHUD Engine running. Waiting for sensor data...")

    try:
        while True:
            # 1. Drain the queue to update the central state
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

            print(f"HUDState | Mode: {state.mode.name} | Display: {state.display_on} | GPS Speed: {state.gps.speed if state.gps and state.gps.valid else 0:.1f} | Radar Dist: {state.radar.get('dist', 0)} | Nav Turn: {state.nav.turn if state.nav else 'None'}")
            
            # 3. Lock framerate to ~30 FPS
            time.sleep(0.033)
            
    except KeyboardInterrupt:
        print("\nShutting down HUD Engine.")

if __name__ == "__main__":
    main()