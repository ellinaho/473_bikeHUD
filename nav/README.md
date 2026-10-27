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

New types get added at the end so old numbers don't change.

### Example

Left turn in 150 m onto "State St", 1200 m remaining:

```
01 02 96 00 B0 04 08 53 74 61 74 65 20 53 74
```

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
