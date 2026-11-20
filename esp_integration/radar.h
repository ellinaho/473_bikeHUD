#ifndef RADAR_H
#define RADAR_H

#include <Arduino.h>

// threat packet struct to send over BLE
struct VehicleThreat {
    float distance_m; // distance to object in meters
    float approach_angle_deg; // angle of approach in degrees (TODO: verify)
    float closing_speed_mps; // closing speed in meters per second
    bool isThreat; // true if object detected is threat, based on threshold 
};

// Declare the external queue so radar.cpp can push to it, and ble.cpp can read from it
extern QueueHandle_t radarQueue;

// Function prototypes to call from main.ino
void setupRadarHardware();
void readRadarTask(void *pvParameters);

#endif