"""
BLE navigation receiver, ran on Raspberry Pi

Pi acts as a BLE peripheral (GATT server) that the phone app connects to. The app writes nav packets
(see nav_packet.py) to NAV_CHAR_UUID and the newest one is kept in self.nav for the display.
"""

import asyncio
import time
from bless import (
    BlessServer,
    BlessGATTCharacteristic,
    GATTCharacteristicProperties,
    GATTAttributePermissions,
)
from nav_packet import NAV_SERVICE_UUID, NAV_CHAR_UUID, NavData, TURN_NAMES, unpack_nav, check_stale

DEVICE_NAME = "BikeHUD"


class NavReceiver:
    def __init__(self):
        self.nav = NavData()    #most recent nav data, returned by get_nav
        self.server = None

    async def start(self):
        """
        - creates GATT server with one writable characteristic for nav packets
        - starts advertising, service uuid is included so iOS can find the Pi while app is in background
        """
        self.server = BlessServer(name=DEVICE_NAME)
        self.server.read_request_func = self.on_read
        self.server.write_request_func = self.on_write

        await self.server.add_new_service(NAV_SERVICE_UUID)
        await self.server.add_new_characteristic(
            NAV_SERVICE_UUID,
            NAV_CHAR_UUID,
            GATTCharacteristicProperties.write | GATTCharacteristicProperties.write_without_response,
            None,
            GATTAttributePermissions.writeable,
        )
        await self.server.start()

    async def stop(self):
        if self.server:
            await self.server.stop()

    def on_write(self, characteristic: BlessGATTCharacteristic, value, **kwargs):
        """
        - called by bless when the phone writes a packet
        - bad packets are dropped, last good data is kept
        """
        characteristic.value = value
        nav = unpack_nav(bytes(value))
        if nav is None:
            return
        nav.last_update = time.monotonic()
        self.nav = nav

    def on_read(self, characteristic: BlessGATTCharacteristic, **kwargs):
        return characteristic.value

    def get_nav(self) -> NavData:
        """
        - returns newest NavData, valid = false if phone stopped sending
        """
        return check_stale(self.nav)


async def main():
    #test: advertise and print nav data every second
    rx = NavReceiver()
    await rx.start()
    print(f"Advertising as {DEVICE_NAME}, waiting for phone...")
    try:
        while True:
            n = rx.get_nav()
            status = "NAV  " if n.valid else "no nav"
            print(f"{status} {TURN_NAMES.get(n.turn, n.turn):>12}  in {n.dist:5d} m  onto '{n.street}'  "
                  f"remaining {n.remaining} m")
            await asyncio.sleep(1.0)
    finally:
        await rx.stop()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
