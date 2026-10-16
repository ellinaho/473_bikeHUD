import asyncio
from bleak import BleakClient, BleakScanner

# LightBlue's default characteristic for its "Blank" virtual device
COMPANION_APP_CHAR_UUID = "00002222-0000-1000-8000-00805f9b34fb"

# This callback fires instantly whenever the phone pushes new data
def navigation_callback(sender, data):
    # For the milestone, we decode simple text. 
    # Later, this will be struct.unpack('<if', data) for packed binary bytes.
    nav_instruction = data.decode('utf-8', errors='ignore')
    print(f"\n[HUD DISPLAY] >>> {nav_instruction} <<<")

async def companion_app_worker():
    while True:
        try:
            print("[PHONE] Scanning for Companion App...")
            
            # Look for the simulated app broadcast
            device = await BleakScanner.find_device_by_filter(
                lambda d, ad: d.name and "Blank" in d.name,
                timeout=5.0
            )

            if device:
                print(f"[PHONE] Found {device.name}! Connecting...")
                async with BleakClient(device) as client:
                    print("[PHONE] Connected! Subscribing to navigation stream...")
                    
                    # Tell the phone we want to be notified of any data changes
                    await client.start_notify(COMPANION_APP_CHAR_UUID, navigation_callback)
                    
                    # Keep the script alive while waiting for pushes
                    while client.is_connected:
                        await asyncio.sleep(1.0)
            else:
                await asyncio.sleep(2.0)
                
        except Exception as e:
            print(f"[PHONE] Link dropped: {e}. Reconnecting...")
            await asyncio.sleep(2.0)

async def main():
    await companion_app_worker()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutting down...")