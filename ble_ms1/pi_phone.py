import asyncio
from bleak import BleakClient, BleakScanner

async def phone_worker():
    print("[PHONE] Scanning for device named 'Blank'...")
    
    device = await BleakScanner.find_device_by_filter(
        lambda d, ad: d.name and "Blank" in d.name,
        timeout=10.0
    )

    if not device:
        print("[PHONE] Not found. Is LightBlue virtual device ON?")
        return

    print(f"[PHONE] Found Phone at {device.address}! Connecting...")
    
    async with BleakClient(device) as client:
        print("[PHONE] Connected! Discovering endpoints...")
        
        # Print all available characteristics to prove the connection holds
        for service in client.services:
            for char in service.characteristics:
                print(f"  -> Found Characteristic: {char.uuid}")
                
                # LightBlue's blank characteristic always contains "2222"
                if "2222" in char.uuid:
                    print(f"\n[PHONE] Polling Nav Data from {char.uuid}...")
                    while client.is_connected:
                        data = await client.read_gatt_char(char.uuid)
                        # Decode and print
                        nav_data = data.decode('utf-8', errors='ignore')
                        print(f"[PHONE] Nav Data: {nav_data}")
                        await asyncio.sleep(1.0)

async def main():
    await phone_worker()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nDisconnecting and shutting down...")