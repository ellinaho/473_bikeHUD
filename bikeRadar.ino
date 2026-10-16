#include <Arduino.h>
#include <string.h>
#include <math.h>

static const char* RADAR_CONFIG_COMMANDS[] = {
    "sensorStop",
    "flushCfg",
    "dfeDataOutputMode 1",
    "channelCfg 15 7 0",
    "adcCfg 2 1",
    "adcbufCfg -1 0 1 1 1",
    "profileCfg 0 60 359 7 57.14 0 0 70 1 256 5209 0 0 158",
    "chirpCfg 0 0 0 0 0 0 0 1",
    "chirpCfg 1 1 0 0 0 0 0 2",
    "chirpCfg 2 2 0 0 0 0 0 4",
    "frameCfg 0 2 16 0 100 1 0",
    "lowPower 0 0",
    "guiMonitor -1 1 1 0 0 0 1",
    "cfarCfg -1 0 2 8 4 3 0 15 1",
    "cfarCfg -1 1 0 4 2 3 1 15 1",
    "multiObjBeamForming -1 1 0.5",
    "clutterRemoval -1 0",
    "calibDcRangeSig -1 0 -5 8 256",
    "extendedMaxVelocity -1 0",
    "lvdsStreamCfg -1 0 0 0",
    "compRangeBiasAndRxChanPhase 0.0 1 0 -1 0 1 0 -1 0 1 0 -1 0 1 0 -1 0 1 0 -1 0 1 0 -1 0",
    "measureRangeBiasAndRxChanPhase 0 1.5 0.2",
    "CQRxSatMonitor 0 3 5 121 0",
    "CQSigImgMonitor 0 127 4",
    "analogMonitor 0 0",
    "aoaFovCfg -1 -90 90 -90 90",
    "cfarFovCfg -1 0 0 8.92",
    "cfarFovCfg -1 1 -1 1.00",
    "calibData 0 0 0",
    "sensorStart"
};

static const size_t NUM_CONFIG_COMMANDS = sizeof(RADAR_CONFIG_COMMANDS) / sizeof(RADAR_CONFIG_COMMANDS[0]);

#define LED_PIN 2
#define HEADER_SIZE 40
#define TLV_HEADER_SIZE 8
#define MAX_PACKET_SIZE 8192
#define TLV_TYPE_POINT_CLOUD 1

// --- detection parameters --- 
#define MIN_REAR_DIST_M    0.2f    // Minimum distance (20 cm)
#define MAX_REAR_DIST_M    10.0f   // Max distance (10 meters)
#define MAX_LANE_OFFSET_M  6.0f    // Wide field of view across the room
#define MIN_APPROACH_VEL_MS -0.2f  // closing speed

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
    float x;        // Lateral position (m) [Left < 0 < Right]
    float y;        // Rear distance (m) [Behind > 0]
    float z;        // Vertical height (m)
    float velocity; // Relative speed (m/s) [Negative = Closing in]
};

struct VehicleThreat {
    float distance_m;
    float approach_angle_deg;
    float closing_speed_mps;
    bool isValid;
};

static uint8_t packetBuffer[MAX_PACKET_SIZE];
static size_t packetLength = 0;
static size_t expectedPacketLength = 0;
static uint8_t syncBuffer[8] = {0};
static bool collectingPacket = false;

void sendRadarConfiguration() {
    Serial.println("ESP32_READY");
    for (size_t i = 0; i < NUM_CONFIG_COMMANDS; i++) {
        Serial.println(RADAR_CONFIG_COMMANDS[i]);
        delay(200);
    }
    Serial.println("CONFIG_SENT");
}

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

                // --- ROOM TESTING THREAT FILTER ---
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

    // --- OUTPUT TARGET DATA ---
    if (primaryThreat.isValid) {
        digitalWrite(LED_PIN, HIGH);
        
        Serial.printf("TARGET_ALERT | Dist: %5.2fm | Angle: %5.1f deg | Speed: %5.1fm/s (%5.1fkm/h)\n",
                      primaryThreat.distance_m,
                      primaryThreat.approach_angle_deg,
                      primaryThreat.closing_speed_mps,
                      primaryThreat.closing_speed_mps * 3.6f);
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

void setup() {
    pinMode(LED_PIN, OUTPUT);
    digitalWrite(LED_PIN, LOW);

    Serial.setRxBufferSize(16384);
    Serial.begin(921600);

    delay(3000);
    sendRadarConfiguration();
}

void loop() {
    while (Serial.available() > 0) {
        uint8_t value = (uint8_t)Serial.read();
        receiveRadarByte(value);
    }
}
