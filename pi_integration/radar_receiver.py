import asyncio
import struct
import time
from bleak import BleakClient

ESP32_MAC = "8c:94:df:b8:5a:0a"
CHARACTERISTIC_UUID = "beb5483e-36e1-4688-b7f5-ea07361b26a8"

async def esp32_worker(event_queue):
    """Background task handling BLE connection and auto-reconnect."""
    
    def handle_radar_packet(sender, data):
        # <fff? decodes 3 little-endian floats and 1 boolean (13 bytes total).
        # data[:13] prevents crashes if the C++ compiler added blank padding bytes to the end of the packet.
        dist, angle, speed, is_valid = struct.unpack('<fff?', data[:13])
        
        # Recreate the integer tier based on the boolean flag
        tier = 1 if is_valid else 0
        
        # Push the parsed data directly to the main thread
        event_queue.put((1, time.monotonic(), ("radar", {"tier": tier, "dist": dist, "speed": speed, "angle": angle})))

    while True:
        try:
            print(f"[RADAR] Connecting to ESP32: {ESP32_MAC}...")
            async with BleakClient(ESP32_MAC) as client:
                print("[RADAR] Connected! Listening to packets...")
                await client.start_notify(CHARACTERISTIC_UUID, handle_radar_packet)
                
                while client.is_connected:
                    await asyncio.sleep(1.0)
                    
        except Exception as e:
            print(f"[RADAR] BLE connection dropped: {e}. Retrying in 2 seconds...")
            await asyncio.sleep(2.0)

def run_radar(event_queue):
    """Wrapper to start the asyncio loop from a standard thread."""
    asyncio.run(esp32_worker(event_queue))