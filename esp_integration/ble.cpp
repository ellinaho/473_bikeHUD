#include "ble.h"
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLE2902.h>

#define SERVICE_UUID        "4fafc201-1fb5-459e-8fcc-c5c9c331914b"
#define CHARACTERISTIC_UUID "beb5483e-36e1-4688-b7f5-ea07361b26a8"

static BLECharacteristic *pCharacteristic = NULL;
static bool deviceConnected = false;

// Callbacks to manage connection state
class ServerCallbacks: public BLEServerCallbacks {
    void onConnect(BLEServer* pServer) { 
        deviceConnected = true; 
        Serial.println("[BLE] Device connected!");
    };
    
    void onDisconnect(BLEServer* pServer) { 
        deviceConnected = false;
        Serial.println("[BLE] Device disconnected. Restarting advertising...");
        pServer->getAdvertising()->start(); 
    }
};

void setupBLE() {
    BLEDevice::init("ESP32_Radar_Node");
    
    Serial.print("[BLE] MAC Address: ");
    Serial.println(BLEDevice::getAddress().toString().c_str());

    BLEServer *pServer = BLEDevice::createServer();
    pServer->setCallbacks(new ServerCallbacks());

    BLEService *pService = pServer->createService(SERVICE_UUID);
    
    pCharacteristic = pService->createCharacteristic(
                        CHARACTERISTIC_UUID,
                        BLECharacteristic::PROPERTY_NOTIFY
                      );
    pCharacteristic->addDescriptor(new BLE2902());
    
    pService->start();
    pServer->getAdvertising()->start();
    Serial.println("[BLE] Setup complete. Waiting for connections...");
}

// ---------------------------------------------------------
// THE RTOS BLE TASK (Runs on Core 0)
// ---------------------------------------------------------
void bleTask(void *pvParameters) {
    for (;;) {
        VehicleThreat txData;
        
        // Wait indefinitely (portMAX_DELAY) for radar data to appear in the queue.
        // This consumes ZERO CPU cycles while waiting.
        if (xQueueReceive(radarQueue, &txData, portMAX_DELAY) == pdPASS) {
            
            // If we have a connected phone/Pi, send the struct
            if (deviceConnected) {
                // Cast the entire struct to raw bytes and blast it over BLE
                pCharacteristic->setValue((uint8_t*)&txData, sizeof(VehicleThreat));
                pCharacteristic->notify();
            }
        }
    }
}