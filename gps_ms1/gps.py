"""
Python function declarations for GPS module, ran on Raspberry Pi

If we want quicker updates, either increase CHUNK for quicker read. Also lower sleep() vals to prevent blocking.
"""

import math
import time
from smbus2 import SMBus, i2c_msg

I2C_BUS = 1             # using pins 3/5 on pi
CHUNK = 32              # bytes per I2C read
ACK_TIMEOUT = 2.0       # seconds to wait for GPS to acknowledge a command

KNOTS_TO_KPH = 1.852    # RMC gives speed in knots
MIN_SPEED_KPH = 1.5     # below this counts as stopped to prevent gps jitters, increase if reduce jitters at low speeds
STALE_TIMEOUT = 3.0     # how long w/o rmc before data is invalid
EARTH_RADIUS_KM = 6371.0

#PMTK314 sets which sentences the GPS outputs and how often (0 = off, 1 = every position update(fix), n = every nth position update up to 5)
#field order: GLL, RMC, VTG, GGA, GSA, GSV, then 13 unused/reserved
#RMC = speed, direction(deg), lat/lon, valid flag 
#GGA = satellite count, need for HDOP param which tells us lat/lon accuracy
PMTK_OUTPUT_RMC_GGA = "PMTK314,0,1,0,1,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0"

#basic checksum
def nmea_checksum(body: str) -> int:
    """
    - XOR of every char between '$' and '*'
    """
    calc = 0
    for c in body:
        calc ^= ord(c)
    return calc


def nmea_to_degrees(value: str, hemisphere: str) -> float:
    """
    - converts nmea lat (ddmm.mmmm) or lon (dddmm.mmmm) to decimal degrees
    - ex: 4216.8530,N -> 42 + 16.8530/60 = 42.28088
    - S and W become negative
    """
    raw = float(value)
    degrees = int(raw // 100)       #4216.8530 -> 42
    minutes = raw - degrees * 100   #4216.8530 -> 16.8530
    result = degrees + minutes / 60
    if hemisphere in ("S", "W"):
        result = -result
    return result


#calculates distance between two points on earth to tell how far user moved
def distance_km(lat1, lon1, lat2, lon2) -> float:
    """
    - haversine formula
    - distance between 2 lat/lon points along the earth's curve
    """
    #converting degrees to rad
    lat1, lon1, lat2, lon2 = map(math.radians, (lat1, lon1, lat2, lon2))

    #a is a number between 0 and 1 which represents how apart two points are as a fraction of the globe
    a = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    
    #returning length of arc along surface -> aka -> dist
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


class GPSData:
    def __init__(self, speed=0.0, pace=0.0, dist=0.0, valid=False,
                 lat=0.0, lon=0.0, heading=0.0, sats=0, hdop=0.0):
        self.speed = speed      #ground speed in (kph)
        self.pace = pace        #pace = 60/speed, in min/km, 0.0 if stationary
        self.dist = dist        #total distance travelled (km)
        self.valid = valid      #will be true if GPS data from satellite is valid
        self.lat = lat          #latitude in decimal degrees (pos = N, neg = S)
        self.lon = lon          #longitude in decimal degree (pos = W, neg = E)
        self.heading = heading  #direction of travel in deg, 0 = N, 90 = E
        self.sats = sats        #number of satellites used (GGA)
        self.hdop = hdop        #lat/lon accuracy (GGA)

#insert hdop chart here later maybe



class PA1010D_GPS:
    def gps_init(self, i2c_address: int = 0x10, update_rate_ms: int = 1000):
        """
        - initialize i2c bus
        - configure gps chip to output only needed data (speed, direction, lat/lon, valid)
        - set data update rate, 1000 ms = 1 Hz, 200 ms = 5 Hz; default is 1000 ms, ceiling is 100ms = 10hz
        - returns true if GPS acknowledges both commands
        """
        self.addr = i2c_address
        self.bus = SMBus(I2C_BUS)

        #leftover bytes buffer b/c read grabs 32 bytes
        self.buf = b""

        #newest verified sentences from get_nmea_data; initialized to none until first read
        self.rmc = None
        self.gga = None
        self.new_rmc = False

        #most recent reading, returned by update_gps_obj
        self.data = GPSData()
        self.last_rmc_time = time.monotonic()
        self.last_point = None  #(lat, lon) of last moving update for distance calc

        #initializing nmea setence type and update rate
        sentences_ok = self.send_command(PMTK_OUTPUT_RMC_GGA)
        rate_ok = self.send_command(f"PMTK220,{update_rate_ms}")

        #both commands need to return true or init fails
        return sentences_ok and rate_ok 

    def send_command(self, cmd) -> bool:
        """
        - wraps cmd as $<cmd>*<checksum>\r\n and writes to the GPS
        - waits for the GPS acknowledgement msg: $PMTK001,<cmd number>,<flag>, where flag 3 = success
        - returns true on success
        - returns false if failed or no reply within timeout (ACK_TIMEOUT)
        """
        sentence = f"${cmd}*{nmea_checksum(cmd):02X}\r\n"
        self.bus.i2c_rdwr(i2c_msg.write(self.addr, sentence.encode("ascii")))

        cmd_num = cmd[4:7] #grabbing cmd num: PMTK314 -> 314

        deadline = time.monotonic() + ACK_TIMEOUT #creating timeout deadline
        while time.monotonic() < deadline:
            #parsing each reply line and splitting for needed cmd txt
            for line in self.read_lines():
                fields = line.split("*")[0].split(",")
                if fields[0] == "$PMTK001" and len(fields) >= 3 and fields[1] == cmd_num:
                    return fields[2] == "3"
            time.sleep(0.05)
        return False

    def read_lines(self) -> list[str]:
        """
        - I2C read
        - returns complete lines received so far
        - partial line appends in self.buf until remainder arrives
        - GPS uses '\n' when it has nothing to send so those are skipped
        """
        msg = i2c_msg.read(self.addr, CHUNK) #prepares request
        self.bus.i2c_rdwr(msg) #does  request
        self.buf += bytes(msg) #appending to buffer
        *lines, self.buf = self.buf.split(b"\n")

        #building list
        result = []
        for l in lines:
            s = l.strip(b"\r").decode("ascii", errors="replace") #replacing noise with unknown
            if s:
                result.append(s)
        return result
    
    def get_nmea_data(self) -> bool:
        """
        - reads GPS, checks checksum of each full sentence
        - saves newest RMC and GGA sentence for update_gps_obj
        - returns true if a new RMC came in (new position update)
        - returns false if nothing new yet (between updates or bad checksum)
        - called by background loop to keep GPS buffer empty
        """
        got_rmc = False
        for line in self.read_lines():
            #needs to look like $<body>*<checksum>
            if not line.startswith("$") or "*" not in line:
                continue
            body, given = line[1:].split("*", 1)

            #compare checksum with the one the GPS sent
            try:
                if nmea_checksum(body) != int(given[:2], 16):
                    continue
            except ValueError:
                continue

            #fields[0][2:] drops talker id: GNRMC -> RMC
            fields = body.split(",")

            if fields[0][2:] == "RMC":
                self.rmc = fields
                self.new_rmc = True
                got_rmc = True

            elif fields[0][2:] == "GGA":
                self.gga = fields
        return got_rmc

    def update_gps_obj(self) -> GPSData:
        """
        - turns newest RMC/GGA sentences from get_nmea_data into values
        - changes data when a new RMC came in, otherwise returns same data as last time
        - if no fix (RMC status V) or no RMC for STALE_TIMEOUT sec, valid = false and old values kept
        - returns GPSData with most recent speed, pace, dist, lat/lon, heading, valid
        """
        #grabbign stored data obj
        d = self.data

        #no new RMC, just check if GPS went quiet
        if not self.new_rmc:
            if time.monotonic() - self.last_rmc_time > STALE_TIMEOUT:
                d.valid = False
            return d
        self.new_rmc = False
        self.last_rmc_time = time.monotonic()

        #GGA fields: 
        #[7] satellites used
        #[8] hdop
        if self.gga:
            try:
                d.sats = int(self.gga[7] or 0)
                d.hdop = float(self.gga[8] or 0)
            except (ValueError, IndexError):
                pass

        #RMC fields: 
        # [2] status Active/Void (A/V) 
        # [3][4] lat + [5][6] lon 
        # [7] speed in knots 
        # [8] course in deg

        f = self.rmc
        #checking if status is valid (A/V)
        if f[2] != "A":
            d.valid = False     
            return d
        try:
            lat = nmea_to_degrees(f[3], f[4])
            lon = nmea_to_degrees(f[5], f[6])
            speed = float(f[7]) * KNOTS_TO_KPH
            heading = float(f[8]) if f[8] else d.heading 

        except (ValueError, IndexError):
            d.valid = False
            return d

        #if below min speed treat as not moving due to gpa low speed jitters
        if speed < MIN_SPEED_KPH:
            speed = 0.0
            heading = d.heading
        else:
            #only add distance while moving so gps drift doesn't add fake distance
            if self.last_point:
                d.dist += distance_km(*self.last_point, lat, lon)
            self.last_point = (lat, lon)

        #obj update
        d.speed = speed
        d.pace = 60 / speed if speed > 0 else 0.0
        d.lat = lat
        d.lon = lon
        d.heading = heading
        d.valid = True

        return d


if __name__ == "__main__":
    #test: configure GPS then print GPSData on every position update
    gps = PA1010D_GPS()
    print("gps_init:", "OK" if gps.gps_init() else "FAILED (no ack)")
    try:
        while True:
            if gps.get_nmea_data():
                d = gps.update_gps_obj()
                status = "FIX   " if d.valid else "no fix"
                print(f"{status} {d.speed:5.1f} km/h  pace {d.pace:5.2f}  dist {d.dist:.3f} km  "
                      f"{d.lat:.6f}, {d.lon:.6f}  heading {d.heading:5.1f}  sats {d.sats}  hdop {d.hdop}")
            time.sleep(0.05)
    except KeyboardInterrupt:
        pass
