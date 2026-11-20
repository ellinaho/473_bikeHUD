#include "ble.h"
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLE2902.h> 

#define SERVICE_UUID        "4fafc201-1fb5-459e-8fcc-c5c9c331914b" // main category (eg "radar service")
#define CHARACTERISTIC_UUID "beb5483e-36e1-4688-b7f5-ea07361b26a8" // specific data point (eg "threat data")

static BLECharacteristic *pCharacteristic = NULL; // pointer to the characteristic so we can update its value later
static bool deviceConnected = false;              // tracks if a Pi is currently connected to the ESP32


// SERVER CALLBACKS: listens for background events (pi connecting or disconnecting)
class ServerCallbacks: public BLEServerCallbacks {
    // triggered when a device connects
    void onConnect(BLEServer* pServer) { 
        deviceConnected = true; 
        Serial.println("[BLE] Device connected!");
    };
    
    // triggered automatically when pi disconnects or goes out of range
    void onDisconnect(BLEServer* pServer) { 
        deviceConnected = false;
        Serial.println("[BLE] Device disconnected. Restarting advertising...");
        
        // when pi disconnects, esp32 stops broadcasting, so need to start it again
        pServer->getAdvertising()->start(); 
    }
};

// BLE INITIALIZATION: called once in main setup() loop.
void setupBLE() {
    // initialize the BLE hardware and set the device name 
    BLEDevice::init("ESP32_Radar_Node");
    
    // print esp32 mac addr to serial for debugging
    Serial.print("[BLE] MAC Address: ");
    Serial.println(BLEDevice::getAddress().toString().c_str());

    // create BLE server (esp32 is server, pi is client)
    BLEServer *pServer = BLEDevice::createServer();
    
    // attach connection/disconnection event listeners from ServerCallbacks class above
    pServer->setCallbacks(new ServerCallbacks());

    // create service with UUID above 
    BLEService *pService = pServer->createService(SERVICE_UUID);
    
    // create characteristic inside the service 
    // set PROPERTY_NOTIFY because we want the ESP32 to push data to pi automatically
    pCharacteristic = pService->createCharacteristic(
                        CHARACTERISTIC_UUID,
                        BLECharacteristic::PROPERTY_NOTIFY
                      );
                      
    // standard descriptor for notifications 
    pCharacteristic->addDescriptor(new BLE2902());
    
    // start service
    pService->start();
    
    // start broadcasting so pi can see esp32
    pServer->getAdvertising()->start();
    Serial.println("[BLE] Setup complete. Waiting for connections...");
}

// RTOS BLE TASK: Runs on Core 0. 
void bleTask(void *pvParameters) {
    for (;;) {
        VehicleThreat txData; // temp struct for incoming radar data
        
        // read from rtos queue named radar queue, tell esp32 to pause task until data arrives
        // uses 0% cpu while waiting for radar sensor to get smth 
        if (xQueueReceive(radarQueue, &txData, portMAX_DELAY) == pdPASS) {
            // if reached here, got data from queue, check if pi connected/listening
            if (deviceConnected) {
                
                // cast memory addr of struct to byte pointer, tell BLE how many bytes (BLE uses raw bytes)
                pCharacteristic->setValue((uint8_t*)&txData, sizeof(VehicleThreat));
                
                // send notification  
                pCharacteristic->notify();
            }
        }
    }
}