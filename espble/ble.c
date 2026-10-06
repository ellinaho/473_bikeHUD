#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLE2902.h>

#define SERVICE_UUID        "4fafc201-1fb5-459e-8fcc-c5c9c331914b"
#define CHARACTERISTIC_UUID "beb5483e-36e1-4688-b7f5-ea07361b26a8"

BLECharacteristic *pCharacteristic;
bool deviceConnected = false;

// 12-byte contiguous struct
struct __attribute__((packed)) SensorPayload {
  float f1;
  float f2;
  int32_t i1;
};
SensorPayload txData;

class ServerCallbacks: public BLEServerCallbacks {
    void onConnect(BLEServer* pServer) { deviceConnected = true; };
    void onDisconnect(BLEServer* pServer) { 
      deviceConnected = false;
      pServer->getAdvertising()->start(); 
    }
};

void setup() {
  Serial.begin(115200);
  
  BLEDevice::init("ESP32_Node");
  
  // Print MAC address for the Pi script
  Serial.print("ESP32 MAC Address: ");
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
}

void loop() {
  if (deviceConnected) {
    txData.f1 = 3.14f; 
    
    txData.f2 = 9.81f;
    txData.i1 = 42;

    pCharacteristic->setValue((uint8_t*)&txData, sizeof(txData));
    pCharacteristic->notify();
    
    delay(100); 
  }
}