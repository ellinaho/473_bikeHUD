"""
Main helmet program, ran on Raspberry Pi Zero 2 W

Runs every subsystem in one process:
    - GPS (I2C) on its own thread, gps.py blocks on I2C reads + sleeps
    - radar BLE link to the ESP32 (Pi is the client, bleak)
    - nav BLE link from the phone app (Pi is the server, bless)
    - rotary encoder for mode + display on/off
Prints a status line every second. Display is not hooked up yet (display.py is still stubs).

If a subsystem fails to start (missing hardware or library), it is skipped and the rest keep running.

usage:
    python3 main.py                     # everything
    python3 main.py --no-radar          # skip a subsystem: --no-gps --no-radar --no-nav --no-encoder
"""

import argparse
import asyncio
import os
import sys
import threading
import time

ROOT = os.path.dirname(os.path.abspath(__file__))
for folder in ("gps_ms1", "ble", "nav", "encoder_ms1"):
    sys.path.insert(0, os.path.join(ROOT, folder))

KPH_TO_MPH = 0.621371
STATUS_PERIOD = 1.0         # seconds between status prints
RADAR_RETRY = 5.0           # seconds between ESP32 reconnect attempts
ENCODER_POLL = 0.01         # seconds between encoder reads


class GPSThread:
    """
    - runs the PA1010D read loop on a background thread
    - self.data is the most recent GPSData, None until the GPS starts
    """
    def __init__(self):
        self.data = None
        self.error = ""
        self.running = False

    def start(self):
        self.running = True
        threading.Thread(target=self.run, daemon=True).start()

    def run(self):
        try:
            from gps import PA1010D_GPS
            gps = PA1010D_GPS()
            if not gps.gps_init():
                print("GPS: no ack from config commands, reading anyway")
            while self.running:
                gps.get_nmea_data()
                self.data = gps.update_gps_obj()    #also marks data stale if GPS goes quiet
                time.sleep(0.05)
        except Exception as e:
            self.error = str(e)
            print(f"GPS: stopped ({e})")

    def stop(self):
        self.running = False


async def run_radar(state):
    """
    - connects to the ESP32 and listens for radar packets, reconnects if the link drops
    - packets are parsed by ble.handle_radar_packet into ble.radar_data
    """
    try:
        import ble
        from bleak import BleakClient
    except ImportError as e:
        print(f"Radar: skipped ({e})")
        state["radar_enabled"] = False
        return

    if ble.ESP32_MAC.startswith("XX"):
        print("Radar: skipped (set ESP32_MAC in ble/ble.py)")
        state["radar_enabled"] = False
        return

    while True:
        try:
            disconnected = asyncio.Event()
            async with BleakClient(ble.ESP32_MAC, disconnected_callback=lambda c: disconnected.set()) as client:
                await client.start_notify(ble.CHARACTERISTIC_UUID, ble.handle_radar_packet)
                state["radar_connected"] = True
                print("Radar: connected")
                await disconnected.wait()
        except asyncio.CancelledError:
            raise
        except Exception as e:
            print(f"Radar: {e}")
        state["radar_connected"] = False
        await asyncio.sleep(RADAR_RETRY)


async def run_encoder(state):
    """
    - polls the rotary encoder without blocking
    - scroll changes HUD mode, long press toggles the display
    """
    try:
        from encoder import HUDEncoder, HUDMode
        enc = HUDEncoder()
        enc.encoder_init()
    except Exception as e:
        print(f"Encoder: skipped ({e})")
        return

    enc.clear_buff()    #flush events from boot
    state["mode"] = HUDMode.MODE0
    while True:
        action = enc.get_encoder_action()
        state["mode"] = enc.update_HUD_mode(state["mode"], action)
        if enc.handle_clicks(action) == "toggle_display":
            state["display_on"] = not state["display_on"]
        await asyncio.sleep(ENCODER_POLL)


async def start_nav():
    """
    - starts the BLE server the phone app connects to, returns the NavReceiver or None
    """
    try:
        from nav_receiver import NavReceiver
        rx = NavReceiver()
        await rx.start()
        print("Nav: advertising, waiting for phone")
        return rx
    except Exception as e:
        print(f"Nav: skipped ({e})")
        return None


def status_line(gps_thread, nav_rx, state) -> str:
    parts = []

    if gps_thread:
        d = gps_thread.data
        if d is None:
            parts.append("GPS " + (f"error: {gps_thread.error}" if gps_thread.error else "starting"))
        elif d.valid:
            parts.append(f"GPS {d.speed * KPH_TO_MPH:4.1f} mph  sats {d.sats}")
        else:
            parts.append("GPS no fix")

    if state["radar_enabled"]:
        if state["radar_connected"]:
            import ble
            r = ble.radar_data
            parts.append(f"radar tier {r['tier']} dist {r['dist']}")
        else:
            parts.append("radar --")

    if nav_rx:
        from nav_packet import TURN_NAMES, format_imperial
        n = nav_rx.get_nav()
        if n.valid:
            parts.append(f"nav {TURN_NAMES.get(n.turn, n.turn)} in {format_imperial(n.dist)} '{n.street}'")
        else:
            parts.append("nav --")

    if state["mode"] is not None:
        parts.append(f"{state['mode'].name} display {'ON' if state['display_on'] else 'OFF'}")

    return "  |  ".join(parts)


async def main(args):
    state = {"radar_enabled": not args.no_radar, "radar_connected": False, "mode": None, "display_on": True}
    tasks = []

    gps_thread = None
    if not args.no_gps:
        gps_thread = GPSThread()
        gps_thread.start()

    nav_rx = None if args.no_nav else await start_nav()

    if not args.no_radar:
        tasks.append(asyncio.create_task(run_radar(state)))
    if not args.no_encoder:
        tasks.append(asyncio.create_task(run_encoder(state)))

    try:
        while True:
            print(status_line(gps_thread, nav_rx, state))
            # TODO: feed gps / radar / nav / mode into display.py once it's implemented
            await asyncio.sleep(STATUS_PERIOD)
    finally:
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
        if nav_rx:
            await nav_rx.stop()
        if gps_thread:
            gps_thread.stop()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="BikeHUD helmet main program")
    parser.add_argument("--no-gps", action="store_true")
    parser.add_argument("--no-radar", action="store_true")
    parser.add_argument("--no-nav", action="store_true")
    parser.add_argument("--no-encoder", action="store_true")
    try:
        asyncio.run(main(parser.parse_args()))
    except KeyboardInterrupt:
        print("\nExiting.")
