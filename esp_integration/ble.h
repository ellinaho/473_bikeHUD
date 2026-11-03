#ifndef BLE_H
#define BLE_H

#include <Arduino.h>
#include "radar.h" // Needed so this file knows about VehicleThreat and radarQueue

void setupBLE();
void bleTask(void *pvParameters);

#endif