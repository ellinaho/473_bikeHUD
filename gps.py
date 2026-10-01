"""
Python function declarations for GPS module, ran on Raspberry Pi
"""

from dataclasses import dataclass

@dataclass
class GPSData:
    speed: float        # ground speed from GPS NMEA parsing, in kph
    pace: float         # pace = 60/speed, in min/km, 0.0 if stationary
    dist: float         # total distance travelled in km
    valid: bool         # will be true if GPS data from satellite is valid


class PA1010D_GPS:
    def gps_init(self, i2c_address: int = 0x10):
        """ 
        - initialize i2c bus
        - configure gps chip to output only needed data (speed, valid)
        - set data update rate
        """
        pass

    def get_nmea_data(self):
        """
        - queries GPS, grabs ascii bytes from i2c buffer, piece into nmea sentence, verify checksum
        - returns true if nmea sentence successfully assembled
        - returns false if sentence assembly failed (sensor only sent partially)
        - called by background loop to keep i2c bfufer empty
        """
        pass

    def update_gps_obj(self):
        """
        - takes successfully parsed NMEA string, parse/calculate/package into GPS object state vars
        - if nmea data from previous functio was incomplete, set valid = 0 and retain previous obj data
        - returns GPSData object with most recent speed, pace, dist, valid. 
        """
        pass



    
