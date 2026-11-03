#include "radar.h"
#include "ble.h"

// Define the global queue handle here. 
// radarQueue is declared as 'extern' in radar.h, so both radar.cpp and ble.cpp share this exact queue.
QueueHandle_t radarQueue;

void setup() {
    Serial.begin(115200); 
    
    // Create a queue that can hold up to 10 VehicleThreat alerts
    radarQueue = xQueueCreate(10, sizeof(VehicleThreat));
    if (radarQueue == NULL) {
        Serial.println("Error: Failed to create queue!");
        while(1);
    }

    // Initialize hardware and protocols
    setupRadarHardware();
    setupBLE();

    // ---------------------------------------------------------
    // CORE 1: The Sensor Processor (High Priority)
    // ---------------------------------------------------------
    xTaskCreatePinnedToCore(
        readRadarTask,   // Function defined in radar.cpp
        "ReadRadar",     
        8192,            
        NULL,            
        2,               // Priority 2 (Higher than BLE)
        NULL,            
        1                // Pin to Core 1
    );

    // ---------------------------------------------------------
    // CORE 0: The Bluetooth Networker (Lower Priority)
    // ---------------------------------------------------------
    xTaskCreatePinnedToCore(
        bleTask,         // Function defined in ble.cpp
        "BLE_Task", 
        8192, 
        NULL, 
        1,               // Priority 1
        NULL, 
        0                // Pin to Core 0 (Where the radio stack naturally lives)
    );
}

void loop() {
    // We are fully RTOS now. The default loop is not needed.
    vTaskDelete(NULL); 
}