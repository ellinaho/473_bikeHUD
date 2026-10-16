#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLE2902.h>


#define SERVICE_UUID        "4fafc201-1fb5-459e-8fcc-c5c9c331914b"
#define CHARACTERISTIC_UUID "beb5483e-36e1-4688-b7f5-ea07361b26a8"


BLECharacteristic *pCharacteristic;
bool deviceConnected = false;


// TODO: change based on actual payload
struct __attribute__((packed)) SensorPayload {
  int32_t i1; 
  int32_t i2;
  int32_t i3;
  int32_t i4;
};
SensorPayload txData = {0, 0, 0, 0}; // Start with zeroes


unsigned long lastNotifyTime = 0;


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
  
  Serial.print("ESP32 MAC Address: ");
  Serial.println(BLEDevice::getAddress().toString().c_str());
  Serial.println("Type 4 integers separated by spaces or commas (e.g. '10 20 30 40') and hit Enter.");


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

// for milestone 1 only
void loop() {
  // 1. Check if you typed anything in the Serial Monitor
  if (Serial.available() > 0) {
    txData.i1 = Serial.parseInt();
    txData.i2 = Serial.parseInt();
    txData.i3 = Serial.parseInt();
    txData.i4 = Serial.parseInt();
    
    // Clear out the remaining newline characters from the buffer
    while (Serial.available()) {
      Serial.read();
    }
    
    Serial.printf("Payload updated to: %d, %d, %d, %d\n", txData.i1, txData.i2, txData.i3, txData.i4);
  }


  // 2. Transmit at 10Hz without using delay() so Serial stays responsive
  if (deviceConnected && (millis() - lastNotifyTime > 100)) {
    pCharacteristic->setValue((uint8_t*)&txData, sizeof(txData));
    pCharacteristic->notify();
    lastNotifyTime = millis();
  }
}