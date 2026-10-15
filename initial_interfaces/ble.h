/*
 * ble.h
 * BLE function declarations for the radar unit (ESP32)
 * sends radar targets to the helmet (Raspberry Pi)
 */

#ifndef BLE_H
#define BLE_H

#include <stdint.h>
#include <stdbool.h>
#include "radar_sensor.h"

#define BLE_DEVICE_NAME    "BikeHUD-Radar"
#define BLE_MAX_TARGETS    3     //targets that fit in one packet
#define BLE_PACKET_SIZE    192    //1 count byte + 3 targets * 6 bytes

/*
   packet layout (little endian):
     byte 0      number of targets (0 to 3)
     then for each target, 6 bytes:
       target_id    uint8
       tier         uint8    (tier_list_t)
       distance     uint16   in cm
       speed        int8     in km/h, + is toward rider
       angle        int8     in degrees
 */

//start bluetooth and begin advertising, returns false if it failed
bool ble_init(void);

//true if the helmet is connected
bool ble_is_connected(void);

//pack the closest targets from a radar frame into packet, returns number of bytes written
uint8_t ble_build_packet(const radar_frame_t *frame, uint8_t *packet);

//send a packet to the helmet, returns false if not connected
bool ble_send_packet(const uint8_t *packet, uint8_t len);

#endif
