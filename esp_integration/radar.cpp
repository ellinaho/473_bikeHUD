#include "radar.h"
#include <string.h>
#include <math.h>

// ==============================================================================
// 473_bikeHUD HARDWARE TOGGLE
// Leave this uncommented while testing with the Python script on the laptop.
// COMMENT THIS OUT WHEN THE PCB ARRIVES AND THE RADAR IS WIRED TO THE ESP32!
#define USE_USB_BRIDGE
// ==============================================================================

// ==============================================================================
// MODE TOGGLE
//   BENCH_MODE defined   -> desk testing with a hand-held object (bottle/iPad)
//   BENCH_MODE commented -> real bike: rear-facing, detects cars approaching
//
// Why two configs: the old config could only measure speeds up to ~±1 m/s.
// Anything faster "wraps around" (aliases), e.g. an iPad pushed toward the radar
// at 1.5 m/s gets reported as +0.4 m/s (moving AWAY) and was filtered out.
// That config can never see a car (5-20 m/s). The BIKE config goes to ~±25 m/s
// but its speed steps are ~1.5 m/s, so slow hand motion reads as 0 there.
#define BENCH_MODE
// ==============================================================================

// Uncomment RADAR_DEBUG to ALSO print every frame + raw points (x, y, v) on top of
// the normal CLEAR / THREAT_DETECTED lines. Useful when nothing is being detected.
// #define RADAR_DEBUG

// --- ESP32 Hardware Pins (Used only when PCB arrives) ---
#define RADAR_CLI_RX  16
#define RADAR_CLI_TX  17
#define RADAR_DATA_RX 19
#define RADAR_DATA_TX 18
#define LED_PIN       2

#ifdef BENCH_MODE
// ---- BENCH: original TI demo profile. ~4 cm range res, max speed ~±1 m/s ----
static const char* RADAR_CONFIG_COMMANDS[] = {
    "sensorStop", "flushCfg", "dfeDataOutputMode 1", "channelCfg 15 7 0",
    "adcCfg 2 1", "adcbufCfg -1 0 1 1 1",
    "profileCfg 0 60 359 7 57.14 0 0 70 1 256 5209 0 0 158",
    "chirpCfg 0 0 0 0 0 0 0 1", "chirpCfg 1 1 0 0 0 0 0 2", "chirpCfg 2 2 0 0 0 0 0 4",
    "frameCfg 0 2 16 0 100 1 0", "lowPower 0 0",
    "guiMonitor -1 1 0 0 0 0 0",   // points only (was also sending a 512 B range profile + stats every frame)
    "cfarCfg -1 0 2 8 4 3 0 10 1", "cfarCfg -1 1 0 4 2 3 1 10 1",
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
#else
// ---- BIKE: from initial_interfaces/radarConfig.h (2 TX, ~37 m, ~±24.8 m/s, 20 Hz)
// plus the monitor/calib lines the SDK 3.x demo wants before sensorStart
// (CQ monitor slice counts scaled for 64 ADC samples).
// !! Load this in TI mmWave Demo Visualizer once to confirm every line says "Done".
static const char* RADAR_CONFIG_COMMANDS[] = {
    "sensorStop", "flushCfg", "dfeDataOutputMode 1", "channelCfg 15 5 0",
    "adcCfg 2 1", "adcbufCfg -1 0 1 1 1",
    "profileCfg 0 60.25 5 6 20 0 0 20 1 64 5000 0 0 30",
    "chirpCfg 0 0 0 0 0 0 0 1", "chirpCfg 1 1 0 0 0 0 0 4",
    "frameCfg 0 1 32 0 50 1 0", "lowPower 0 0",
    "guiMonitor -1 1 0 0 0 0 0",
    "cfarCfg -1 0 2 8 4 3 0 15 1", "cfarCfg -1 1 0 4 2 3 1 12 1",
    "multiObjBeamForming -1 1 0.5", "clutterRemoval -1 1",
    "calibDcRangeSig -1 0 -5 8 256", "extendedMaxVelocity -1 0",
    "lvdsStreamCfg -1 0 0 0",
    "compRangeBiasAndRxChanPhase 0.0 1 0 -1 0 1 0 -1 0 1 0 -1 0 1 0 -1 0 1 0 -1 0 1 0 -1 0",
    "measureRangeBiasAndRxChanPhase 0 1.5 0.2",
    "CQRxSatMonitor 0 3 5 31 0", "CQSigImgMonitor 0 31 4",
    "analogMonitor 0 0", "aoaFovCfg -1 -60 60 -60 60",
    "cfarFovCfg -1 0 0.5 30.0", "cfarFovCfg -1 1 -24.0 24.0",
    "calibData 0 0 0", "sensorStart"
};
#endif

static const size_t NUM_CONFIG_COMMANDS = sizeof(RADAR_CONFIG_COMMANDS) / sizeof(RADAR_CONFIG_COMMANDS[0]);

#define HEADER_SIZE 40
#define TLV_HEADER_SIZE 8
#define MAX_PACKET_SIZE 8192
#define TLV_TYPE_POINT_CLOUD 1

// --- detection parameters ---
// TI convention: y = distance straight out from the radar, NEGATIVE velocity = coming closer.
#ifdef BENCH_MODE
  #define MIN_REAR_DIST_M    0.10f   // skip junk right at the antenna
  #define MAX_REAR_DIST_M    8.0f
  #define MAX_LANE_OFFSET_M  3.0f
  #define MIN_MOVING_SPEED   0.10f   // |v| >= this = "moving". Either sign counts,
                                     // because fast hand motion aliases to the wrong sign.
#else
  #define MIN_REAR_DIST_M    0.5f
  #define MAX_REAR_DIST_M    30.0f
  #define MAX_LANE_OFFSET_M  3.5f    // ignore stuff off the side of the road
  #define MIN_APPROACH_VEL_MS -0.8f  // ~3 km/h closing; ignores parked cars / receding
#endif

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

// --- diagnostics ---
static uint32_t statBytes = 0;
static uint32_t statFrames = 0;
static uint32_t statBadPackets = 0;
static uint32_t lastStatMs = 0;

// ---------------------------------------------------------
// CONFIGURATION SENDER
// ---------------------------------------------------------
void sendRadarConfiguration() {
#ifdef USE_USB_BRIDGE
    // The Python bridge forwards these lines to the radar CLI.
    // Watch its console: every command should get a "[RADAR CLI] ... Done".
    // If you see "Error" on any line (esp. sensorStart), the radar is NOT running.
    Serial.println("ESP32_READY");
    for (size_t i = 0; i < NUM_CONFIG_COMMANDS; i++) {
        Serial.println(RADAR_CONFIG_COMMANDS[i]);
        delay(200);
    }
    Serial.println("CONFIG_SENT");
#else
    Serial.println("[RADAR] Sending config to physical CLI port...");
    for (size_t i = 0; i < NUM_CONFIG_COMMANDS; i++) {
        Serial1.println(RADAR_CONFIG_COMMANDS[i]);
        delay(200);
        while (Serial1.available()) Serial.write(Serial1.read());   // show Done/Error
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
    // NOTE: Serial.setRxBufferSize() used to be here, but it does NOTHING after
    // Serial.begin() has run. It now lives in esp_main.c, right before begin().
    delay(3000);
#else
    Serial1.begin(115200, SERIAL_8N1, RADAR_CLI_RX, RADAR_CLI_TX);
    Serial2.setRxBufferSize(16384);   // fine here: before begin()
    Serial2.begin(921600, SERIAL_8N1, RADAR_DATA_RX, RADAR_DATA_TX);
    delay(3000);
#endif

    sendRadarConfiguration();
}

static bool isThreat(const DetectedObject& obj) {
    if (obj.y < MIN_REAR_DIST_M || obj.y > MAX_REAR_DIST_M) return false;
    if (fabsf(obj.x) > MAX_LANE_OFFSET_M) return false;
#ifdef BENCH_MODE
    return fabsf(obj.velocity) >= MIN_MOVING_SPEED;
#else
    return obj.velocity <= MIN_APPROACH_VEL_MS;
#endif
}

// ---------------------------------------------------------
// PACKET PARSING
// ---------------------------------------------------------
void processRadarPacket(const uint8_t* data, size_t length) {
    if (length < HEADER_SIZE) { statBadPackets++; return; }

    MMWaveFrameHeader header;
    memcpy(&header, data, sizeof(header));

    if (header.totalPacketLen != length || header.numTLVs > 64) { statBadPackets++; return; }
    statFrames++;

#ifdef RADAR_DEBUG
    Serial.printf("[FRAME] #%lu pts=%lu\n",
                  (unsigned long)header.frameNumber, (unsigned long)header.numDetectedObj);
#endif

    size_t offset = HEADER_SIZE;
    VehicleThreat primaryThreat = {999.0f, 0.0f, 0.0f, false};

    for (uint32_t t = 0; t < header.numTLVs; t++) {
        if (offset + TLV_HEADER_SIZE > length) break;

        TLVHeader tlv;
        memcpy(&tlv, data + offset, sizeof(tlv));
        offset += TLV_HEADER_SIZE;

        if (tlv.length > length - offset) break;

        if (tlv.type == TLV_TYPE_POINT_CLOUD) {
            uint32_t objectCount = tlv.length / sizeof(DetectedObject);

            for (uint32_t i = 0; i < objectCount; i++) {
                DetectedObject obj;
                memcpy(&obj, data + offset + i * sizeof(DetectedObject), sizeof(DetectedObject));

#ifdef RADAR_DEBUG
                if (i < 8) {
                    Serial.printf("   pt x=%6.2f y=%6.2f z=%6.2f v=%6.2f\n",
                                  obj.x, obj.y, obj.z, obj.velocity);
                }
#endif
                if (isThreat(obj)) {
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
        offset += tlv.length;
    }

    if (primaryThreat.isValid) {
        digitalWrite(LED_PIN, HIGH);
        Serial.printf("THREAT_DETECTED Dist: %.2f m | Angle: %.1f deg | Speed: %.2f m/s\n",
                      primaryThreat.distance_m,
                      primaryThreat.approach_angle_deg,
                      primaryThreat.closing_speed_mps);
    } else {
        digitalWrite(LED_PIN, LOW);
        Serial.println("CLEAR");
    }

    // --- ALWAYS send to Bluetooth, even if empty ---
    if (radarQueue != NULL) {
        xQueueSend(radarQueue, &primaryThreat, (TickType_t)0);
    }
}

void resetPacketParser() {
    packetLength = 0;
    expectedPacketLength = 0;
    collectingPacket = false;
    memset(syncBuffer, 0, sizeof(syncBuffer));
}

void receiveRadarByte(uint8_t value) {
    statBytes++;

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
        statBadPackets++;
        resetPacketParser();
        return;
    }

    packetBuffer[packetLength++] = value;

    if (packetLength == HEADER_SIZE) {
        uint32_t totalLength;
        memcpy(&totalLength, packetBuffer + 12, sizeof(totalLength));

        if (totalLength < HEADER_SIZE || totalLength > MAX_PACKET_SIZE) {
            statBadPackets++;
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

// Health line every 2 s
static void printRadarStats() {
    uint32_t now = millis();
    if (now - lastStatMs < 2000) return;
    lastStatMs = now;
    Serial.printf("[RADAR STATS] bytes=%lu frames=%lu bad=%lu%s\n",
                  (unsigned long)statBytes, (unsigned long)statFrames,
                  (unsigned long)statBadPackets,
                  statBytes == 0  ? "  <-- NO DATA from bridge (radar not started? wrong COM port?)" :
                  statFrames == 0 ? "  <-- bytes but no valid frames (RX overflow / baud mismatch)" : "");
}

// ---------------------------------------------------------
// THE RTOS SENSOR TASK
// ---------------------------------------------------------
void readRadarTask(void *pvParameters) {
    for (;;) {
#ifdef USE_USB_BRIDGE
        while (Serial.available() > 0) {
            receiveRadarByte((uint8_t)Serial.read());
        }
#else
        while (Serial2.available() > 0) {
            receiveRadarByte((uint8_t)Serial2.read());
        }
#endif
        printRadarStats();
        // 1 tick (was 5 ms): at 921600 baud ~460 bytes arrive every 5 ms
        vTaskDelay(1);
    }
}
