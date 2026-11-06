#include "radar.h"
#include <string.h>
#include <math.h>

// ==============================================================================
// 473_bikeHUD HARDWARE TOGGLE
// Leave this uncommented while testing with the Python script on the laptop.
// COMMENT THIS OUT WHEN THE PCB ARRIVES AND THE RADAR IS WIRED TO THE ESP32!
#define USE_USB_BRIDGE 
// ==============================================================================

// --- ESP32 Hardware Pins (Used only when PCB arrives) ---
#define RADAR_CLI_RX  16  
#define RADAR_CLI_TX  17  
#define RADAR_DATA_RX 19  
#define RADAR_DATA_TX 18  
#define LED_PIN       2

static const char* RADAR_CONFIG_COMMANDS[] = {
    "sensorStop", "flushCfg", "dfeDataOutputMode 1", "channelCfg 15 7 0",
    "adcCfg 2 1", "adcbufCfg -1 0 1 1 1",
    "profileCfg 0 60 359 7 57.14 0 0 70 1 256 5209 0 0 158",
    "chirpCfg 0 0 0 0 0 0 0 1", "chirpCfg 1 1 0 0 0 0 0 2", "chirpCfg 2 2 0 0 0 0 0 4",
    "frameCfg 0 2 16 0 100 1 0", "lowPower 0 0", "guiMonitor -1 1 1 0 0 0 1",
    "cfarCfg -1 0 2 8 4 3 0 15 1", "cfarCfg -1 1 0 4 2 3 1 15 1",
    "multiObjBeamForming -1 1 0.5", "clutterRemoval -1 0",
    "calibDcRangeSig -1 0 -5 8 256", "extendedMaxVelocity -1 0",
    "lvdsStreamCfg -1 0 0 0",
    "compRangeBiasAndRxChanPhase 0.0 1 0 -1 0 1 0 -1 0 1 0 -1 0 1 0 -1 0 1 0 -1 0 1 0 -1 0",
    "measureRangeBiasAndRxChanPhase 0 1.5 0.2",
    "CQRxSatMonitor 0 3 5 121 0", "CQSigImgMonitor 0 127 4",
    "analogMonitor 0 0", "aoaFovCfg -1 -90 90 -90 90",
    "cfarFovCfg -1 0 0 8.92", "cfarFovCfg -1 1 -1 1.00",
    "calibData 0 0 0", "sensorStart"
};

static const size_t NUM_CONFIG_COMMANDS = sizeof(RADAR_CONFIG_COMMANDS) / sizeof(RADAR_CONFIG_COMMANDS[0]);

#define HEADER_SIZE 40
#define TLV_HEADER_SIZE 8
#define MAX_PACKET_SIZE 8192
#define TLV_TYPE_POINT_CLOUD 1

// --- detection parameters --- 
#define MIN_REAR_DIST_M    0.2f
#define MAX_REAR_DIST_M    10.0f
#define MAX_LANE_OFFSET_M  6.0f
#define MIN_APPROACH_VEL_MS -0.2f

static const uint8_t MAGIC_WORD[8] = {0x02, 0x01, 0x04, 0x03, 0x06, 0x05, 0x08, 0x07};

struct __attribute__((packed)) MMWaveFrameHeader {
    uint8_t magicWord[8];
    uint32_t version;
    uint32_t totalPacketLen;
    uint32_t platform;
    uint32_t frameNumber;
    uint32_t timeCpuCycles;
    uint32_t numDetectedObj;
    uint32_t numTLVs;
    uint32_t subFrameNumber;
};

struct __attribute__((packed)) TLVHeader {
    uint32_t type;
    uint32_t length;
};

struct __attribute__((packed)) DetectedObject {
    float x;
    float y;
    float z;
    float velocity;
};

static uint8_t packetBuffer[MAX_PACKET_SIZE];
static size_t packetLength = 0;
static size_t expectedPacketLength = 0;
static uint8_t syncBuffer[8] = {0};
static bool collectingPacket = false;

// ---------------------------------------------------------
// CONFIGURATION SENDER
// ---------------------------------------------------------
void sendRadarConfiguration() {
#ifdef USE_USB_BRIDGE
    // Uses the Python script to bounce commands to the radar
    Serial.println("ESP32_READY");
    for (size_t i = 0; i < NUM_CONFIG_COMMANDS; i++) {
        Serial.println(RADAR_CONFIG_COMMANDS[i]);
        delay(200);
    }
    Serial.println("CONFIG_SENT");
#else
    // Sends commands directly to the physical radar via hardware TX/RX pins
    Serial.println("[RADAR] Sending config to physical CLI port...");
    for (size_t i = 0; i < NUM_CONFIG_COMMANDS; i++) {
        Serial1.println(RADAR_CONFIG_COMMANDS[i]);
        delay(200);
    }
    Serial.println("[RADAR] Config sent.");
#endif
}

// ---------------------------------------------------------
// HARDWARE INITIALIZATION
// ---------------------------------------------------------
void setupRadarHardware() {
    pinMode(LED_PIN, OUTPUT);
    digitalWrite(LED_PIN, LOW);

#ifdef USE_USB_BRIDGE
    // We only need the main USB serial when routing through the laptop
    Serial.setRxBufferSize(16384);
    delay(3000);
#else
    // Initialize the two physical UART ports for the PCB
    Serial1.begin(115200, SERIAL_8N1, RADAR_CLI_RX, RADAR_CLI_TX);
    Serial2.setRxBufferSize(16384);
    Serial2.begin(921600, SERIAL_8N1, RADAR_DATA_RX, RADAR_DATA_TX);
    delay(3000);
#endif

    sendRadarConfiguration();
}

// ---------------------------------------------------------
// PACKET PARSING (Identical for both modes)
// ---------------------------------------------------------
void processRadarPacket(const uint8_t* data, size_t length) {
    if (length < HEADER_SIZE) return;

    MMWaveFrameHeader header;
    memcpy(&header, data, sizeof(header));

    if (header.totalPacketLen != length || header.numTLVs > 64) return;

    size_t offset = HEADER_SIZE;
    VehicleThreat primaryThreat = {999.0f, 0.0f, 0.0f, false};

    for (uint32_t t = 0; t < header.numTLVs; t++) {
        if (offset + TLV_HEADER_SIZE > length) return;

        TLVHeader tlv;
        memcpy(&tlv, data + offset, sizeof(tlv));
        offset += TLV_HEADER_SIZE;

        if (tlv.length > length - offset) return;

        if (tlv.type == TLV_TYPE_POINT_CLOUD) {
            uint32_t objectCount = tlv.length / sizeof(DetectedObject);

            for (uint32_t i = 0; i < objectCount; i++) {
                DetectedObject obj;
                memcpy(&obj, data + offset + i * sizeof(DetectedObject), sizeof(DetectedObject));

                if (obj.y >= MIN_REAR_DIST_M && obj.y <= MAX_REAR_DIST_M && fabs(obj.x) <= MAX_LANE_OFFSET_M) {
                    if (obj.velocity < MIN_APPROACH_VEL_MS) {
                        float dist = sqrtf(obj.x * obj.x + obj.y * obj.y);
                        
                        if (dist < primaryThreat.distance_m) {
                            primaryThreat.distance_m = dist;
                            primaryThreat.approach_angle_deg = atan2f(obj.x, obj.y) * (180.0f / M_PI);
                            primaryThreat.closing_speed_mps = fabsf(obj.velocity);
                            primaryThreat.isValid = true;
                        }
                    }
                }
            }
        }
        offset += tlv.length;
    }

    if (primaryThreat.isValid) {
        digitalWrite(LED_PIN, HIGH);
        
        // Push the threat struct into the RTOS queue without blocking
        if (radarQueue != NULL) {
            xQueueSend(radarQueue, &primaryThreat, (TickType_t)0);
        }
        
#ifndef USE_USB_BRIDGE
        // Only print debug info if we aren't using the USB bridge 
        // (printing this mid-stream can confuse the Python script)
        Serial.printf("TARGET_ALERT | Dist: %5.2fm | Speed: %5.1fm/s\n",
                      primaryThreat.distance_m,
                      primaryThreat.closing_speed_mps);
#endif
    } else {
        digitalWrite(LED_PIN, LOW);
    }
}

void resetPacketParser() {
    packetLength = 0;
    expectedPacketLength = 0;
    collectingPacket = false;
}

void receiveRadarByte(uint8_t value) {
    if (!collectingPacket) {
        memmove(syncBuffer, syncBuffer + 1, 7);
        syncBuffer[7] = value;

        if (memcmp(syncBuffer, MAGIC_WORD, 8) == 0) {
            memcpy(packetBuffer, MAGIC_WORD, 8);
            packetLength = 8;
            expectedPacketLength = 0;
            collectingPacket = true;
        }
        return;
    }

    if (packetLength >= MAX_PACKET_SIZE) {
        resetPacketParser();
        return;
    }

    packetBuffer[packetLength++] = value;

    if (packetLength == HEADER_SIZE) {
        uint32_t totalLength;
        memcpy(&totalLength, packetBuffer + 12, sizeof(totalLength));

        if (totalLength < HEADER_SIZE || totalLength > MAX_PACKET_SIZE) {
            resetPacketParser();
            return;
        }
        expectedPacketLength = totalLength;
    }

    if (expectedPacketLength > 0 && packetLength == expectedPacketLength) {
        processRadarPacket(packetBuffer, packetLength);
        resetPacketParser();
    }
}

// ---------------------------------------------------------
// THE RTOS SENSOR TASK
// ---------------------------------------------------------
void readRadarTask(void *pvParameters) {
    for (;;) {
#ifdef USE_USB_BRIDGE
        // Read binary data funneled down the laptop USB cable
        while (Serial.available() > 0) {
            uint8_t value = (uint8_t)Serial.read();
            receiveRadarByte(value);
        }
#else
        // Read binary data directly from the physical radar pin
        while (Serial2.available() > 0) {
            uint8_t value = (uint8_t)Serial2.read();
            receiveRadarByte(value);
        }
#endif
        // Yield to the RTOS scheduler
        vTaskDelay(pdMS_TO_TICKS(5));
    }
}