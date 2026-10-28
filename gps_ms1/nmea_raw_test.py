"""
tldr: use this test to check gps hardware connection

Raw NMEA test for the PA1616D GPS over UART, ran on Raspberry Pi
prints every NMEA sentence the GPS sends, with checksum result, to confirm wiring + UART reads work

setup:
    sudo raspi-config -> Interface Options -> Serial Port
    serial login shell: No
    serial hardware: Yes
    reboot
    python -m pip install pyserial

usage:
    python3 nmea_raw_test.py            # print all sentences
    python3 nmea_raw_test.py --bytes    # also dump raw bytes from each UART read
"""

import argparse
import time
import serial

UART_PORT = "/dev/serial0"  # Pi UART port
GPS_BAUD = 9600     # PA1616D default baud rate
CHUNK = 256         # bytes per UART read
IDLE_SLEEP = 0.05   # sleep when GPS has nothing to send


def read_chunk(uart):
    """
    - plain UART read, GPS returns its next bytes of NMEA output
    - Returns empty bytes when nothing is available
    """
    return uart.read(min(uart.in_waiting, CHUNK))


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
    parser.add_argument("--bytes", action="store_true", help="dump raw bytes from each UART read")
    args = parser.parse_args()

    buf = b""
    good = bad = 0
    with serial.Serial(UART_PORT, GPS_BAUD, timeout=0) as uart:
        print(f"reading GPS at {UART_PORT}, ctrl+c to stop")
        try:
            while True:
                data = read_chunk(uart)
                if args.bytes:
                    print("raw:", data)

                # empty reads
                if not data:
                    time.sleep(IDLE_SLEEP)
                    continue

                buf += data
                # newline-separated messages
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
