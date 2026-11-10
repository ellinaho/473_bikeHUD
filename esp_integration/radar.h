#ifndef RADAR_H
#define RADAR_H

#include <Arduino.h>

// Shared structure to pass target data through the FreeRTOS Queue
struct VehicleThreat {
    float distance_m;
    float approach_angle_deg;
    float closing_speed_mps;
    bool isValid;
};

// Declare the external queue so radar.cpp can push to it, and ble.cpp can read from it
extern QueueHandle_t radarQueue;

// Function prototypes to call from main.ino
void setupRadarHardware();
void readRadarTask(void *pvParameters);

#endif