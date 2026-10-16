import asyncio
import struct
from bleak import BleakClient

ESP32_MAC = "8c:94:df:b8:5a:0a"
CHARACTERISTIC_UUID = "beb5483e-36e1-4688-b7f5-ea07361b26a8"

# Shared state dictionary
radar_data = {"tier": 0, "dist": 0, "speed": 0, "angle": 0}

def handle_radar_packet(sender, data):
    tier, dist, speed, angle = struct.unpack('<iiii', data)

    radar_data["tier"] = tier
    radar_data["dist"] = dist
    radar_data["speed"] = speed
    radar_data["angle"] = angle

async def esp32_worker():
    """Background task handling BLE connection and auto-reconnect."""
    while True:
        try:
            print(f"Connecting to ESP32: {ESP32_MAC}...")
            async with BleakClient(ESP32_MAC) as client:
                print("Connected! Listening to radar packets...")
                await client.start_notify(CHARACTERISTIC_UUID, handle_radar_packet)
                
                # Keep the loop alive and print directly from here
                while client.is_connected:
                    print(f"Radar Data : {radar_data}")
                    await asyncio.sleep(1.0)
                    
        except Exception as e:
            # Reconnect loop if ESP32 disconnects or goes out of range
            print(f"BLE connection dropped: {e}. Retrying in 2 seconds...")
            await asyncio.sleep(2.0)

async def main():
    # Just run the ESP32 worker directly
    await esp32_worker()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nDisconnecting and shutting down...")