#ifndef BLE_H
#define BLE_H

#include <Arduino.h>
#include "radar.h" 

void setupBLE();
void bleTask(void *pvParameters); // Task for BLE communication, runs on Core 0

#endif