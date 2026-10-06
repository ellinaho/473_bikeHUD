import asyncio
import struct
from bleak import BleakClient

ESP32_MAC = "XX:XX:XX:XX:XX:XX"
CHARACTERISTIC_UUID = "beb5483e-36e1-4688-b7f5-ea07361b26a8"

# Shared dictionary prepared for future integration
telem_data = {"i1": 0.0, "i2": 0.0, "i3": 0}

def notification_handler(sender, data):
    i1, i2, i3 = struct.unpack('<iii', data)

    telem_data["i1"] = i1
    telem_data["i2"] = i2
    telem_data["i3"] = i3

async def main():
    print(f"Connecting to {ESP32_MAC}...")
    
    async with BleakClient(ESP32_MAC) as client:
        print("Connected! Subscribing to notifications...")
        await client.start_notify(CHARACTERISTIC_UUID, notification_handler)
        
        try:
            # standalone loop
            while True:
                print(f"Current State -> {telem_data}")
                await asyncio.sleep(1.0)
                
        except KeyboardInterrupt:
            print("\nDisconnecting...")
            
        await client.stop_notify(CHARACTERISTIC_UUID)

if __name__ == "__main__":
    asyncio.run(main())
