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

Android app, code goes in `android/`.

### Stack
- Kotlin + Jetpack Compose, Android Studio
- minSdk 29 (Android 10)
- Routing: Google Routes API, `travelMode: BICYCLE`
- Phone GPS: FusedLocationProvider, high accuracy, 1 update/sec

### API Key
- Put the key in `android/local.properties` as `MAPS_API_KEY=...` (gitignored), load it with the Secrets Gradle Plugin. Never commit it.
- In Google Cloud, restrict the key to Routes API + our package name + SHA-1 of each debug keystore that builds the app.
- Because of the Android app restriction, every Routes API request must include `X-Android-Package: com.bikehud.app` and `X-Android-Cert: <SHA-1, no colons>`. Read the SHA-1 from the app's signing cert at runtime (don't hardcode) so it works on everyone's build.

### Destination
- User types an address, sent straight to Routes API as the destination (no Places API for now).
- Origin is the phone's current location.

### Routes API Request
Field mask (polyline is needed for off-route detection):
```
routes.distanceMeters,routes.polyline,routes.legs.steps.distanceMeters,routes.legs.steps.polyline,
routes.legs.steps.startLocation,routes.legs.steps.endLocation,routes.legs.steps.navigationInstruction
```

### Maneuver to Turn Type

| Google `maneuver` | Turn type |
|---|---|
| `TURN_LEFT` / `TURN_RIGHT` | 2 / 3 |
| `TURN_SLIGHT_LEFT` / `TURN_SLIGHT_RIGHT` | 4 / 5 |
| `TURN_SHARP_LEFT` / `TURN_SHARP_RIGHT` | 6 / 7 |
| `UTURN_LEFT`, `UTURN_RIGHT` | 8 |
| `ROUNDABOUT_LEFT`, `ROUNDABOUT_RIGHT` | 9 |
| `FORK_LEFT` / `FORK_RIGHT` | 11 / 12 |
| `MERGE` | 13 |
| `RAMP_LEFT` / `RAMP_RIGHT` | 14 / 15 |
| `STRAIGHT`, `NAME_CHANGE`, `DEPART`, missing, anything else | 1 |
| (app decides) last step reached | 10 |

Street name isn't its own field, it's pulled from `navigationInstruction.instructions` (text after "onto" / "on", cut at the next comma or newline). Empty string if not found.

### Route Following

| Setting | Value |
|---|---|
| Advance to next step | within 15 m of current step's end |
| Off route | > 30 m from route polyline for 3 fixes in a row |
| Reroute cooldown | min 15 s between Routes API requests |
| Arrived | within 20 m of destination, send turn 10 then stop nav |
| Distance to turn | along the route to the end of the current step, in meters |

Packets are sent on change and at least once per second (see BLE Interface).

### Background + Permissions
- Navigation + BLE run in a foreground service (persistent "Navigating" notification) so it works with the screen off.
- Ask user to disable battery optimization for the app. On Samsung (test phone is a Galaxy A14) also add it to Settings → Battery → Background usage limits → Never sleeping apps.
- Permissions: `BLUETOOTH_SCAN`, `BLUETOOTH_CONNECT`, `ACCESS_FINE_LOCATION`, `POST_NOTIFICATIONS`. No background location needed since the service is started from the app.
- Foreground service: declare `foregroundServiceType="location|connectedDevice"` and request `FOREGROUND_SERVICE`, `FOREGROUND_SERVICE_LOCATION`, `FOREGROUND_SERVICE_CONNECTED_DEVICE` (required on Android 14+, crashes without it).

### BLE
- First connect: scan for the nav service UUID, then save that Pi's address and only reconnect to it.
- Auto reconnect if the helmet power cycles.
- Request MTU 64 after connecting.
- Write without response.

### Later
- Simulation mode: fake location that moves along the route, for indoor testing and demos.
- Places Autocomplete for destination search.
- Map screen.

### Helmet Display
- Imperial. Packet is always meters, the Pi converts (ft under 0.1 mi, then mi).

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
4. The Pi should print `NAV left in 150 m onto 'State St'`.

## Usage

```python
from nav_receiver import NavReceiver

rx = NavReceiver()
await rx.start()                # inside an asyncio loop

while True:
    n = rx.get_nav()            # n.valid, n.turn, n.dist, n.street, n.remaining
```
