"""
tldr: use this test to check gps hardware connection

Raw NMEA test for the PA1010D GPS over I2C, ran on Raspberry Pi
prints every NMEA sentence the GPS sends, with checksum result, to confirm wiring + I2C reads work

setup:
    sudo raspi-config  ->  Interface Options -> I2C -> Enable, reboot
    i2cdetect -y 1     ->  should show 10
    pip3 install smbus2

usage:
    python3 nmea_raw_test.py            # print all sentences
    python3 nmea_raw_test.py --bytes    # also dump raw bytes from each I2C read
"""

import argparse
import time
from smbus2 import SMBus, i2c_msg

I2C_BUS = 1         # Pi header pins 3 (SDA) / 5 (SCL)
GPS_ADDR = 0x10     # PA1010D default address
CHUNK = 32          # bytes per I2C read
IDLE_SLEEP = 0.05   # sleep when GPS has nothing to send


def read_chunk(bus):
    """
    - plain I2C read (no register byte), GPS returns its next bytes of NMEA output
    - when GPS buffer is empty it pads with '\n' (0x0A)
    """
    msg = i2c_msg.read(GPS_ADDR, CHUNK)
    bus.i2c_rdwr(msg)
    return bytes(msg)


def checksum_ok(sentence):
    """
    - XOR of every char between '$' and '*' must equal the 2 hex digits after '*'
    """
    if not sentence.startswith("$") or "*" not in sentence:
        return False
    body, _, given = sentence[1:].partition("*")
    calc = 0
    for c in body:
        calc ^= ord(c)
    try:
        return calc == int(given[:2], 16)
    except ValueError:
        return False


def describe_rmc(sentence):
    """
    - short summary of RMC so it's easy to see when the GPS gets a fix
    """
    f = sentence.split("*")[0].split(",")
    if len(f) < 9:
        return ""
    status = "FIX" if f[2] == "A" else "no fix"
    try:
        kph = float(f[7]) * 1.852
        return f"  <- RMC {status}, {kph:.1f} km/h, course {f[8] or '-'}"
    except ValueError:
        return f"  <- RMC {status}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bytes", action="store_true", help="dump raw bytes from each I2C read")
    args = parser.parse_args()

    buf = b""
    good = bad = 0
    with SMBus(I2C_BUS) as bus:
        print(f"reading GPS at 0x{GPS_ADDR:02x} on i2c-{I2C_BUS}, ctrl+c to stop")
        try:
            while True:
                data = read_chunk(bus)
                if args.bytes:
                    print("raw:", data)

                # all padding means GPS has nothing new yet
                if data.count(b"\n") == len(data):
                    time.sleep(IDLE_SLEEP)
                    continue

                buf += data
                # padding '\n' just shows up as empty lines and gets skipped
                *lines, buf = buf.split(b"\n")
                for line in lines:
                    s = line.strip(b"\r").decode("ascii", errors="replace")
                    if not s:
                        continue
                    if checksum_ok(s):
                        good += 1
                        extra = describe_rmc(s) if s[3:6] == "RMC" else ""
                        print(f"OK   {s}{extra}")
                    else:
                        bad += 1
                        print(f"BAD  {s}")
        except KeyboardInterrupt:
            print(f"\n{good} good, {bad} bad checksum")


if __name__ == "__main__":
    main()
