#include "radar.h"
#include "ble.h"

// Define the global queue handle here.
// radarQueue is declared as 'extern' in radar.h, so both radar.cpp and ble.cpp share this exact queue.
QueueHandle_t radarQueue;

void setup() {
    // FIX 1: the Python bridge (Radar_Bridge, ESP_BAUD) opens this port at 921600.
    //        Old code used 115200 -> both directions were garbage, so the radar
    //        never got its config and the ESP never got valid radar frames.
    //        If you change one, change the other.
    // FIX 2: setRxBufferSize() ONLY works BEFORE Serial.begin() on ESP32.
    //        Without it the RX buffer is 256 B and radar frames overflow it.
    Serial.setRxBufferSize(16384);
    Serial.begin(921600);

    // Create a queue that can hold up to 10 VehicleThreat alerts
    radarQueue = xQueueCreate(10, sizeof(VehicleThreat));
    if (radarQueue == NULL) {
        Serial.println("Error: Failed to create queue!");
        while(1);
    }

    // Initialize hardware and protocols
    setupRadarHardware();
    setupBLE();

    // CORE 1: The Sensor Processor (High Priority)
    xTaskCreatePinnedToCore(readRadarTask, "ReadRadar", 8192, NULL, 2, NULL, 1);

    // CORE 0: The Bluetooth Networker (Lower Priority)
    xTaskCreatePinnedToCore(bleTask, "BLE_Task", 8192, NULL, 1, NULL, 0);
}

void loop() {
    // We are fully RTOS now. The default loop is not needed.
    vTaskDelete(NULL);
}
