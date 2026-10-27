# Nav

The phone app does all routing and turn-by-turn tracking. It sends the next turn to the Pi over BLE. The Pi only receives and displays it.

- `nav_packet.py`: packet format, turn types, UUIDs (no BLE, can be tested on any computer)
- `nav_receiver.py`: BLE GATT server on the Pi that the phone connects to

## BLE Interface

The Pi is the peripheral (server), the phone is the central (client).

| | UUID |
|---|---|
| Nav service | `e92011aa-4b4e-452d-ba3a-33271a383755` |
| Nav characteristic (phone writes) | `6b16fa29-fdf4-4eed-a96a-3fc13b8d85db` |

- The characteristic supports write and write-without-response.
- The Pi advertises the service UUID. On iOS, scan for this UUID (not the device name), since background scanning only matches on service UUID.
- Send a packet when the turn, street, or distance changes, and at least once per second. If the Pi gets nothing for 5 s it marks nav as invalid.

## Packet Format

Little endian. 7 byte header + street name.

| Offset | Size | Type | Field |
|---|---|---|---|
| 0 | 1 | uint8 | version, currently `1` |
| 1 | 1 | uint8 | turn type (table below) |
| 2 | 2 | uint16 | distance to turn (m), max 65535 |
| 4 | 2 | uint16 | remaining route distance (m), `0` if not used |
| 6 | 1 | uint8 | street name length N (bytes) |
| 7 | N | UTF-8 | street name, max 40 bytes, don't split a character |

Max packet size is 47 bytes. iOS negotiates a large enough MTU automatically. On Android, request a larger MTU (e.g. 64+) after connecting, since the default only fits 20 bytes.

### Turn Types

| Value | Turn |
|---|---|
| 0 | none (no active route) |
| 1 | straight |
| 2 | left |
| 3 | right |
| 4 | slight left |
| 5 | slight right |
| 6 | sharp left |
| 7 | sharp right |
| 8 | u-turn |
| 9 | roundabout |
| 10 | arrive |
| 11 | fork left |
| 12 | fork right |
| 13 | merge |
| 14 | ramp left |
| 15 | ramp right |

New types get added at the end so old numbers don't change.

### Example

Left turn in 150 m onto "State St", 1200 m remaining:

```
01 02 96 00 B0 04 08 53 74 61 74 65 20 53 74
```

## Phone App Design

Android app, code goes in `android/`. Google Navigation SDK does the navigation (routing, step tracking, off-route detection, rerouting). The app only converts its turn-by-turn feed into our packet and sends it over BLE.

### Stack
- Kotlin + Jetpack Compose, Android Studio
- minSdk 29 (Android 10)
- Google Navigation SDK for Android 8.0.0, travel mode `CYCLING` (needs Kotlin 2.3+, core library desugaring)
- Package name `com.bikehud.app`

### API Key
- Put the key in `android/local.properties` as `MAPS_API_KEY=...` (gitignored), `app/build.gradle.kts` reads it into the manifest as a placeholder. Never commit it.
- In Google Cloud, restrict the key to Navigation SDK + Maps SDK for Android (+ Routes API as backup), and to our package name + SHA-1 of each debug keystore that builds the app.
- The SDK sends the package/cert headers itself. Only if we call the Routes API directly does the request need `X-Android-Package: com.bikehud.app` and `X-Android-Cert: <SHA-1, no colons>` (read the SHA-1 at runtime, don't hardcode).

### Cost Safety
Navigation SDK bills per destination set (`setDestination`, only called in `NavSession.start()`), including when using the simulator. Routes API bills per request.
- Only set a destination when the user taps Start. Never in a loop, retry loop, or on app launch.
- No automatic retries on failure, show the error and let the user tap again.
- App-side cap: max 30 destinations per day, counted in SharedPreferences. Start button is disabled past the cap.
- Unit tests never call the real SDK or API, use fakes.
- Hard cap in Google Cloud: per-day quotas on Navigation SDK and Routes API (APIs & Services → the API → Quotas). Budget alerts only email, they don't stop charges.

### Destination
- User types an address and taps Find. Android's built-in `Geocoder` turns it into lat/lon (free, not a Maps API) and shows the address it matched.
- Start passes it to the SDK as a `Waypoint`. Only Start is billed, so a wrong match costs nothing.
- Places Autocomplete can replace this later.

### Navigation Flow
1. Ask for location, Bluetooth, and notification permissions on launch. Getting the navigator shows Google's terms dialog the first time.
2. Get the `Navigator`, set travel mode to cycling, set the destination waypoint, start guidance.
3. Register our service for the turn-by-turn data feed (`registerServiceForNavUpdates`). The SDK sends a `NavInfo` about once a second.
4. Convert each `NavInfo` to a packet and send it over BLE.
5. Use the SDK's built-in simulator (simulate locations along the route) for indoor testing and demos.

### NavInfo to Packet

| Packet field | From `NavInfo` |
|---|---|
| turn | current step's maneuver (table below) |
| dist | distance to the current step (m) |
| remaining | distance to final destination (m) |
| street | current step's road name, cut to 40 bytes |

Nav state: enroute sends the packet as normal. Rerouting sends the last turn with dist unchanged until the new route arrives. Stopped sends turn 0 (none), except right after arriving it keeps sending arrive.

Street uses the step's simple road name, falls back to the full road name.

### Maneuver to Turn Type

The SDK's `Maneuver` list is longer than ours, so map by group (`nav/ManeuverMap.kt`).

| SDK maneuver group | Turn type |
|---|---|
| turn left / right | 2 / 3 |
| turn slight left / right, keep left / right | 4 / 5 |
| turn sharp left / right | 6 / 7 |
| u-turn (either direction) | 8 |
| any roundabout | 9 |
| destination (any side) | 10 |
| fork left / right | 11 / 12 |
| any merge | 13 |
| on/off ramp left / right (incl. keep, slight, sharp) | 14 / 15 |
| on/off ramp u-turn | 8 |
| straight, depart, name change, ferry, unspecified ramp, unknown, anything else | 1 |

Packets are sent on every `NavInfo` update and at least once per second (see BLE Interface).

### Background + Permissions
- During guidance the SDK runs its own foreground service (location type) with a navigation notification, which keeps the app process alive with the screen off. BLE lives in the app process (`BikeHudApp`), so no second service is needed.
- Ask user to disable battery optimization for the app. On Samsung (test phone is a Galaxy A14) also add it to Settings → Battery → Background usage limits → Never sleeping apps.
- Runtime permissions asked on launch: `ACCESS_FINE_LOCATION`, `BLUETOOTH_SCAN`, `BLUETOOTH_CONNECT`, `POST_NOTIFICATIONS`. The SDK adds its own manifest permissions (foreground service, background location).
- If the screen-off test shows nav stopping, the SDK docs recommend also asking for "Allow all the time" location.

### BLE
- First connect: scan for the nav service UUID, then save that Pi's address and only reconnect to it.
- Auto reconnect if the helmet power cycles.
- Request MTU 64 after connecting.
- Write without response.

### Later
- Places Autocomplete for destination search.
- Attribution/licensing screen (required by the SDK terms).
- Google Play location declaration if the app is ever published (SDK 8.0.0 requirement), not needed for sideloading.

### Helmet Display
- Imperial. Packet is always meters, the Pi converts with `format_imperial()` in `nav_packet.py` (ft under 0.1 mi, then mi with 1 decimal). The app uses the same rule.

## Setup on Pi

BLE needs to be enabled (see `ble/README.md`). Then:

```bash
pip install bless
```

## Run

```bash
cd nav
python3 nav_receiver.py
```

Prints `no nav` until a packet comes in.

## Test Without the App

1. Run `nav_receiver.py` on the Pi.
2. On a phone, open **nRF Connect** (free, iOS and Android) and scan. Connect to the Pi (it might show up as the Pi's hostname instead of `BikeHUD`).
3. Find the nav service, tap the upload arrow on the nav characteristic, and write the example bytes above as hex.
4. The Pi should print `NAV left in 492 ft 'State St'`.

## Usage

```python
from nav_receiver import NavReceiver

rx = NavReceiver()
await rx.start()                # inside an asyncio loop

while True:
    n = rx.get_nav()            # n.valid, n.turn, n.dist, n.street, n.remaining
```
