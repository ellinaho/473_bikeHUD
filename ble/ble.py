import asyncio
import struct
from bleak import BleakClient

# TODO: SETUP ESP32 CONNECTION HERE
ESP32_MAC = "XX:XX:XX:XX:XX:XX"
CHARACTERISTIC_UUID = "beb5483e-36e1-4688-b7f5-ea07361b26a8"

# TODO: based on what radar has to send
radar_data = {"tier": 0, "dist": 0, "speed": 0, "angle": 0}

def handle_radar_packet(sender, data):
    tier, dist, speed, angle = struct.unpack('<iiii', data)

    radar_data["tier"] = tier
    radar_data["dist"] = dist
    radar_data["speed"] = speed
    radar_data["angle"] = angle

async def main(): # async makes ble nonblocking
    print(f"Connecting to ESP32: {ESP32_MAC}...")
    
    async with BleakClient(ESP32_MAC) as client:
        print("Connected! Listening to radar packets...")
        await client.start_notify(CHARACTERISTIC_UUID, handle_radar_packet)
        
        try:
            while True:
                print(f"Radar Data : {radar_data}")
                await asyncio.sleep(1.0)
                
        except KeyboardInterrupt:
            print("\nDisconnecting...")
            
        await client.stop_notify(CHARACTERISTIC_UUID)

if __name__ == "__main__":
    asyncio.run(main())
