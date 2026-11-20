"""
BLE watchdog: owns both BikeHUD BLE links and reconnects them as fast as possible.

  ESP32 radar  (Pi = central)    : Pi connects to the ESP, subscribes to radar notifications.
  Phone nav    (Pi = peripheral) : Pi runs the GATT server + advertising, phone app connects to it.

Everything runs in one asyncio loop (one thread) so the two links can coordinate, e.g. if the ESP
recovery has to reset the adapter, the phone server is re-registered right after.

ESP: reconnect immediately on drop. A link is considered dropped when
  - bleak's disconnect callback fires, or
  - no radar packet for RADAR_STALE_S (ESP sends every radar frame, so silence = dead link), or
  - the BT stack was reset underneath us.
  Repeated connect failures escalate:
    2+ fails   -> bluetoothctl disconnect + remove <ESP MAC>  (clears stale BlueZ cache)
    every 5th  -> power-cycle the adapter
    every 10th -> restart bluetooth.service

Phone: the phone app is the one that (re)connects, so the Pi's job is to always be connectable:
  - re-register GATT server + advertisement whenever bluetoothd restarts / adapter is reset
  - re-register if nothing is connected and the advertisement disappeared
  - if the phone is "connected" but hasn't written for PHONE_STALE_S, kick it so the app reconnects

Use from main.py:
    threading.Thread(target=ble_worker, args=(event_queue,), daemon=True).start()
Or standalone to test both links without the display:
    python3 ble_watchdog.py
"""

import asyncio
import os
import queue
import re
import struct
import time

from bleak import BleakClient
from phone_receiver import PhoneReceiver
from phone_packet import TURN_NAMES, format_imperial

ESP32_MAC = "8C:94:DF:B8:5A:0A"
RADAR_CHAR_UUID = "beb5483e-36e1-4688-b7f5-ea07361b26a8"

CONNECT_TIMEOUT_S = 5.0    # bleak scan+connect timeout per attempt
RADAR_STALE_S = 3.0        # no radar notify for this long while connected -> reconnect
PHONE_STALE_S = 15.0       # phone connected but silent this long -> disconnect it (None to disable)
PHONE_POLL_S = 1.0         # phone/adapter health check period
REMOVE_AFTER = 2           # consecutive ESP failures before `bluetoothctl remove`
POWER_CYCLE_EVERY = 5      # ...before power-cycling the adapter
RESTART_BT_EVERY = 10      # ...before restarting bluetoothd

AS_ROOT = [] if os.geteuid() == 0 else ["sudo", "-n"]   # Pi default user has passwordless sudo


def log(tag, msg):
    print(f"[{tag} {time.strftime('%H:%M:%S')}] {msg}", flush=True)


async def sh(*cmd, timeout=8.0):
    """Run a command without blocking the loop. Returns stdout ('' on failure). Never raises."""
    try:
        p = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT)
    except FileNotFoundError:
        return ""
    try:
        out, _ = await asyncio.wait_for(p.communicate(), timeout)
        return out.decode(errors="replace")
    except asyncio.TimeoutError:
        p.kill()
        return ""


def btctl(*args, timeout=8.0):
    return sh("bluetoothctl", *args, timeout=timeout)


class BLEWatchdog:
    def __init__(self, q, esp_mac=ESP32_MAC):
        self.q = q
        self.esp_mac = esp_mac.upper()
        self.stack_gen = 0          # bumped whenever the BT stack is reset; phone server re-registers
        self.bt_pid = None
        self.last_radar = 0.0
        self.esp_connected = False
        self.phone_mac = None
        self.radar_count = 0        # radar packets received since start (debug screen)

    # ---------------- shared adapter helpers ----------------

    async def bump_if_stack_reset(self):
        """Detect bluetoothd restarts / adapter power loss and make sure the adapter is on."""
        pid = (await sh("systemctl", "show", "-p", "MainPID", "--value", "bluetooth", timeout=3)).strip()
        if pid and self.bt_pid and pid != self.bt_pid:
            log("BLE", "bluetoothd restarted")
            self.stack_gen += 1
        self.bt_pid = pid or self.bt_pid

        if "Powered: yes" not in await btctl("show"):
            log("BLE", "adapter off -> powering on")
            await sh(*AS_ROOT, "rfkill", "unblock", "bluetooth")
            await btctl("power", "on")
            self.stack_gen += 1

    async def power_cycle_adapter(self):
        log("BLE", "power-cycling adapter")
        await btctl("power", "off")
        await asyncio.sleep(1.0)
        await sh(*AS_ROOT, "rfkill", "unblock", "bluetooth")
        await btctl("power", "on")
        self.stack_gen += 1

    async def restart_bluetoothd(self):
        log("BLE", "restarting bluetooth.service")
        await sh(*AS_ROOT, "systemctl", "restart", "bluetooth", timeout=20)
        await asyncio.sleep(2.0)
        await sh(*AS_ROOT, "rfkill", "unblock", "bluetooth")
        await btctl("power", "on")
        self.stack_gen += 1

    async def connected_devices(self):
        out = await btctl("devices", "Connected")
        return [m.upper() for m in re.findall(r"Device ([0-9A-Fa-f:]{17})", out)]

    # ---------------- ESP32 radar (Pi = central) ----------------

    def on_radar(self, _sender, data):
        dist, angle, speed, is_valid = struct.unpack('<fff?', data[:13])
        self.last_radar = time.monotonic()
        self.radar_count += 1
        # Priority 1: Safety Critical
        self.q.put((1, time.monotonic(), ("radar", {
            "tier": 1 if is_valid else 0, "dist": dist, "speed": speed, "angle": angle,
            "raw": bytes(data).hex(" ")})))

    async def esp_recover(self, fails):
        if fails >= REMOVE_AFTER:
            log("RADAR", f"remove {self.esp_mac} from BlueZ")
            await btctl("disconnect", self.esp_mac)
            await btctl("remove", self.esp_mac)
        if fails % RESTART_BT_EVERY == 0:
            await self.restart_bluetoothd()
        elif fails % POWER_CYCLE_EVERY == 0:
            await self.power_cycle_adapter()

    async def esp_session(self):
        """Connect, stream until the link is lost, then return. Raises on connect failure."""
        dropped = asyncio.Event()
        client = BleakClient(self.esp_mac, timeout=CONNECT_TIMEOUT_S,
                             disconnected_callback=lambda _c: dropped.set())
        gen = self.stack_gen
        await client.connect()
        try:
            await client.start_notify(RADAR_CHAR_UUID, self.on_radar)
            self.last_radar = time.monotonic()
            self.esp_connected = True
            log("RADAR", "connected")
            while True:
                try:
                    await asyncio.wait_for(dropped.wait(), 0.25)
                    log("RADAR", "disconnected")
                    return
                except asyncio.TimeoutError:
                    pass
                if time.monotonic() - self.last_radar > RADAR_STALE_S:
                    log("RADAR", f"no data for {RADAR_STALE_S}s, forcing reconnect")
                    return
                if self.stack_gen != gen:
                    log("RADAR", "BT stack reset, reconnecting")
                    return
        finally:
            self.esp_connected = False
            try:
                await asyncio.wait_for(client.disconnect(), 3.0)
            except Exception:
                pass

    async def esp_loop(self):
        await btctl("disconnect", self.esp_mac)   # clear any link left over from a previous run
        fails = 0
        while True:
            try:
                await self.esp_session()
                fails = 0                         # had a good session; retry right away
            except Exception as e:
                fails += 1
                log("RADAR", f"connect failed ({fails}): {e or type(e).__name__}")
                await self.esp_recover(fails)
                await asyncio.sleep(0.2)

    # ---------------- Phone nav (Pi = peripheral) ----------------

    async def phone_loop(self):
        rx, gen = None, None
        silent_since = None
        while True:
            await self.bump_if_stack_reset()

            if rx is None or gen != self.stack_gen:
                if rx is not None:
                    log("NAV", "re-registering GATT server")
                    try:
                        await asyncio.wait_for(rx.stop(), 3.0)
                    except Exception:
                        pass
                try:
                    gen = self.stack_gen
                    rx = PhoneReceiver()
                    await asyncio.wait_for(rx.start(), 10.0)
                    log("NAV", "advertising, waiting for phone")
                except Exception as e:
                    log("NAV", f"GATT server start failed: {e or type(e).__name__}, retrying")
                    rx = None
                    await asyncio.sleep(1.0)
                    continue

            nav = rx.get_nav()
            # Priority 2: Navigation
            self.q.put((2, time.monotonic(), ("nav", nav)))

            phones = [m for m in await self.connected_devices() if m != self.esp_mac]
            phone = phones[0] if phones else None
            if phone != self.phone_mac:
                log("NAV", f"phone connected ({phone})" if phone else "phone disconnected")
                self.phone_mac, silent_since = phone, time.monotonic()

            if phone:
                if nav.valid:
                    silent_since = time.monotonic()
                elif PHONE_STALE_S and time.monotonic() - silent_since > PHONE_STALE_S:
                    log("NAV", f"phone silent {PHONE_STALE_S}s, dropping link so app reconnects")
                    await btctl("disconnect", phone)
                    silent_since = time.monotonic()
            else:
                m = re.search(r"ActiveInstances:\s*0x([0-9a-fA-F]+)", await btctl("show"))
                if m and int(m.group(1), 16) == 0:
                    log("NAV", "advertisement lost")
                    gen = None    # forces re-register next pass

            # link status for the debug screen
            self.q.put((2, time.monotonic(), ("ble", {
                "esp": self.esp_connected, "phone": self.phone_mac,
                "radar_count": self.radar_count, "last_radar": self.last_radar})))

            await asyncio.sleep(PHONE_POLL_S)

    # ---------------- entry ----------------

    async def run(self):
        await asyncio.gather(self.esp_loop(), self.phone_loop())


def ble_worker(q):
    """Thread target for main.py."""
    asyncio.run(BLEWatchdog(q).run())


if __name__ == "__main__":
    # Standalone test: run both links and print what comes in.
    import threading
    q = queue.PriorityQueue()
    threading.Thread(target=ble_worker, args=(q,), daemon=True).start()
    last_nav = 0.0
    try:
        while True:
            _, _, (src, d) = q.get()
            if src == "radar" and d["tier"]:
                print(f"  radar: {d['dist']:.1f}m {d['speed']:.1f}m/s {d['angle']:.0f}deg")
            elif src == "nav" and time.monotonic() - last_nav > 5:
                last_nav = time.monotonic()
                print(f"  nav: {'OK ' if d.valid else '-- '} {TURN_NAMES.get(d.turn, d.turn)} "
                      f"in {format_imperial(d.dist)} '{d.street}'")
    except KeyboardInterrupt:
        pass
