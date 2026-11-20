#include "radar.h"
#include <string.h>
#include <math.h>

// comment out when pcb works
#define USE_USB_BRIDGE 
// ==============================================================================

// --- ESP32 Hardware Pins (Used only when PCB arrives) ---
#define RADAR_CLI_RX  16  
#define RADAR_CLI_TX  17  
#define RADAR_DATA_RX 19  
#define RADAR_DATA_TX 18  
#define LED_PIN       2

// RADAR CONFIGS: run on radar chip before data gets to esp32
static const char* RADAR_CONFIG_COMMANDS[] = {
    "sensorStop",
    "flushCfg",
    "dfeDataOutputMode 1",      // Standard frame-based chirp mode
    "channelCfg 15 7 0",        // Enable all 4 RX antennas (15) and 3 TX antennas (7)
    "adcCfg 2 1",               // 16-bit ADC, complex 1x output
    "adcbufCfg -1 0 1 1 1",

    // [TUNE] RF CHIRP PROFILE (Controls max range, resolution, and RX gain)
    // Format: profileCfg <id> <startFreqGHz> <idleTimeUs> <adcStartUs> <rampEndUs>
    //                    <txOutPwr> <txPhase> <freqSlopeMHz/us> <txStartUs>
    //                    <numAdcSamples> <digOutSampleRateKsps> <hpf1> <hpf2> <rxGainDb>
    // - Last number (158): RX Gain. Usually leave as-is unless saturating at close range.
    // - NOTE: If you need much longer range (e.g., 30-50m for cars), regenerate this
    //   profile + chirpCfg using the TI mmWave Sensing Estimator tool.
    "profileCfg 0 60 359 7 57.14 0 0 70 1 256 5209 0 0 158",

    "chirpCfg 0 0 0 0 0 0 0 1", // TX1
    "chirpCfg 1 1 0 0 0 0 0 2", // TX2
    "chirpCfg 2 2 0 0 0 0 0 4", // TX3

    // [TUNE] FRAME RATE / UPDATE SPEED
    // Format: frameCfg <startChirp> <endChirp> <numLoops> <numFrames> <framePeriodMs> <trigger> <delay>
    // - 5th param (100): Frame periodicity in ms. 100ms = 10 Hz update rate.
    //   Lower (e.g., 50 = 20 Hz) for faster reaction to speeding cars; higher to save power.
    "frameCfg 0 2 16 0 100 1 0",

    "lowPower 0 0",

    // [TUNE] OUTPUT DATA BANDWIDTH
    // Format: guiMonitor -1 <detectedObjects> <logMagRange> <noiseProfile> <rangeAzimuth> <rangeDoppler> <stats>
    // - Currently sending Point Cloud (1), Range Profile (1), and Stats (1).
    // - TIP: Change to "guiMonitor -1 1 0 0 0 0 0" in the field! You only parse the
    //   Point Cloud TLV anyway, so turning off the others cuts UART traffic and prevents dropped packets.
    "guiMonitor -1 1 1 0 0 0 1",

    // [TUNE] SENSITIVITY - RANGE CFAR (Hardware noise floor threshold)
    // Format: cfarCfg -1 0 <mode> <noiseWin> <guardLen> <divShift> <cyclic> <thresholdScale> <peakGrouping>
    // - 2nd-to-last param (10): Detection threshold in dB.
    //   LOWER (e.g., 6-8)  = More sensitive (sees cars farther away, but more false alarms/ghosts).
    //   HIGHER (e.g., 14-18) = Less sensitive (cleaner signal, fewer ghosts, might miss distant bikes/cars).
    "cfarCfg -1 0 2 8 4 3 0 10 1",

    // [TUNE] SENSITIVITY - DOPPLER/VELOCITY CFAR
    // - 2nd-to-last param (10): Same dB threshold rule as above, applied to velocity bins.
    "cfarCfg -1 1 0 4 2 3 1 10 1",

    "multiObjBeamForming -1 1 0.5",

    // [TUNE] STATIC CLUTTER REMOVAL (CRITICAL FOR BIKE RADAR!)
    // Format: clutterRemoval -1 <0=OFF, 1=ON>
    // - Currently OFF (0) for workbench testing.
    // - Change to "clutterRemoval -1 1" for field testing! This tells the radar to ignore
    //   stationary objects (parked cars, trees, road signs, buildings) and only report moving targets.
    "clutterRemoval -1 0",

    "calibDcRangeSig -1 0 -5 8 256",

    // [TUNE] EXTENDED MAX VELOCITY
    // Format: extendedMaxVelocity -1 <0=OFF, 1=ON>
    // - If fast cars wrap around and show up as negative/wrong speeds, try setting this to 1.
    "extendedMaxVelocity -1 0",

    "lvdsStreamCfg -1 0 0 0",
    "compRangeBiasAndRxChanPhase 0.0 1 0 -1 0 1 0 -1 0 1 0 -1 0 1 0 -1 0 1 0 -1 0 1 0 -1 0",
    "measureRangeBiasAndRxChanPhase 0 1.5 0.2",
    "CQRxSatMonitor 0 3 5 121 0",
    "CQSigImgMonitor 0 127 4",
    "analogMonitor 0 0",

    // [TUNE] HARDWARE FIELD OF VIEW (Angle of Arrival)
    // Format: aoaFovCfg -1 <minAzimuthDeg> <maxAzimuthDeg> <minElevationDeg> <maxElevationDeg>
    // - Currently -90 to +90 deg (full 180 deg behind you).
    // - Narrow azimuth (e.g., -45 45) in the field to ignore sidewalks/oncoming lanes.
    // - Narrow elevation (e.g., -15 15) to ignore overhead bridges and ground bounce.
    "aoaFovCfg -1 -90 90 -90 90",

    // [TUNE] HARDWARE RANGE FILTER (Direction 0 = Range in meters)
    // Format: cfarFovCfg -1 0 <minDistM> <maxDistM>
    // - WARNING: Currently capped at 8.92m! Even if you raise MAX_REAR_DIST_M below,
    //   the radar will NOT output anything past 8.92m until you increase this number.
    "cfarFovCfg -1 0 0 8.92",

    // [TUNE] HARDWARE VELOCITY FILTER (Direction 1 = Velocity in m/s)
    // Format: cfarFovCfg -1 1 <minVelM/s> <maxVelM/s>
    // - WARNING: Currently capped at -1.0 to +1.0 m/s (~2.2 mph) for hand-waving tests!
    // - For road testing, widen this (e.g., "cfarFovCfg -1 1 -30.0 30.0") or fast cars
    //   will be completely invisible to the ESP32.
    "cfarFovCfg -1 1 -1 1.00",

    "calibData 0 0 0",
    "sensorStart"
};

static const size_t NUM_CONFIG_COMMANDS = sizeof(RADAR_CONFIG_COMMANDS) / sizeof(RADAR_CONFIG_COMMANDS[0]);

// --- TI mmWave Binary Packet Constants ---
#define HEADER_SIZE 40
#define TLV_HEADER_SIZE 8
#define MAX_PACKET_SIZE 8192
#define TLV_TYPE_POINT_CLOUD 1

// ==============================================================================
// [TUNE] SOFTWARE DETECTION & THREAT FILTERING (ESP32 Side)
// These filter the points that survive the hardware config above.
// Coordinate system (looking straight out the front of the radar):
//   +Y = Straight behind the bike (distance)
//   +X / -X = Left / Right lateral offset (lane width)
//   Velocity = Negative (-) means approaching you; Positive (+) means moving away.
// ==============================================================================
#define MIN_REAR_DIST_M     0.00f  // [TUNE] Ignore reflections closer than this (e.g., 0.5m to ignore your own rear wheel/frame)
#define MAX_REAR_DIST_M     10.0f  // [TUNE] Max alert distance in meters (bump to 30.0f - 50.0f for road testing; match cfarFovCfg!)
#define MAX_LANE_OFFSET_M   6.0f   // [TUNE] Half-width of detection corridor (e.g., 2.5f - 3.5f covers your lane + adjacent lane)
#define MIN_APPROACH_VEL_MS -0.5f  // [TUNE] Min closing speed to trigger alert (m/s). Must be NEGATIVE.
                                   //        -0.5 m/s (~1 mph) is sensitive; try -1.5f or -2.0f (~4.5 mph) to ignore slow jitter.

// TI mmWave frame sync pattern ("Magic Word")
static const uint8_t MAGIC_WORD[8] = {0x02, 0x01, 0x04, 0x03, 0x06, 0x05, 0x08, 0x07};

// Packed structs match the exact byte layout sent by the radar DSP
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
    float x;        // Lateral offset in meters (left/right)
    float y;        // Longitudinal distance in meters (behind bike)
    float z;        // Vertical height in meters (up/down) - not currently filtered
    float velocity; // Radial velocity in m/s (negative = approaching)
};

// Packet parser state variables
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
        delay(200); // Gives radar CLI time to parse each line
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
    // Large 16KB RX buffer prevents dropping bytes during high-speed binary bursts
    Serial.setRxBufferSize(16384);
    delay(3000);
#else
    // Initialize the two physical UART ports for the PCB:
    // Serial1 = 115200 baud CLI (text config), Serial2 = 921600 baud Data (binary point cloud)
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

    // Sanity check: drop corrupted packets
    if (header.totalPacketLen != length || header.numTLVs > 64) return;

    size_t offset = HEADER_SIZE;
    // Default "no threat" struct (distance initialized to 999m so any real threat is closer)
    VehicleThreat primaryThreat = {999.0f, 0.0f, 0.0f, false};

    // Walk through all TLV (Type-Length-Value) payloads in this frame
    for (uint32_t t = 0; t < header.numTLVs; t++) {
        if (offset + TLV_HEADER_SIZE > length) return;

        TLVHeader tlv;
        memcpy(&tlv, data + offset, sizeof(tlv));
        offset += TLV_HEADER_SIZE;

        if (tlv.length > length - offset) return;

        // We only care about Type 1: Detected Points (x, y, z, velocity)
        if (tlv.type == TLV_TYPE_POINT_CLOUD) {
            uint32_t objectCount = tlv.length / sizeof(DetectedObject);

            for (uint32_t i = 0; i < objectCount; i++) {
                DetectedObject obj;
                memcpy(&obj, data + offset + i * sizeof(DetectedObject), sizeof(DetectedObject));

                // 1. Spatial Filter: Is the point inside our rear detection box?
                // (Optional [TUNE]: You can also filter obj.z here if ground/road reflections trigger alerts)
                if (obj.y >= MIN_REAR_DIST_M && obj.y <= MAX_REAR_DIST_M && fabs(obj.x) <= MAX_LANE_OFFSET_M) {
                    
                    // 2. Velocity Filter: Is it moving TOWARD us fast enough?
                    if (obj.velocity < MIN_APPROACH_VEL_MS) {
                        float dist = sqrtf(obj.x * obj.x + obj.y * obj.y);
                        
                        // 3. Threat Selection: Keep only the CLOSEST approaching target
                        // [TUNE] Note: In the field, a single noisy point can trigger this.
                        // If you get flickering false alerts, consider requiring a target to appear
                        // for 2-3 consecutive frames before setting isThreat = true.
                        if (dist < primaryThreat.distance_m) {
                            primaryThreat.distance_m = dist;
                            primaryThreat.approach_angle_deg = atan2f(obj.x, obj.y) * (180.0f / M_PI);
                            primaryThreat.closing_speed_mps = fabsf(obj.velocity);
                            primaryThreat.isThreat = true;
                        }
                    }
                }
            }
        }
        offset += tlv.length;
    }

    // Update onboard LED & debug serial output
    if (primaryThreat.isThreat) {
        digitalWrite(LED_PIN, HIGH);
        
#ifdef USE_USB_BRIDGE
        Serial.print("THREAT_DETECTED Dist: ");
        Serial.println(primaryThreat.distance_m);
#else
        // Only print debug info if we aren't using the USB bridge 
        // (printing this mid-stream can confuse the Python script)
        Serial.printf("TARGET_ALERT | Dist: %5.2fm | Speed: %5.1fm/s\n",
                      primaryThreat.distance_m,
                      primaryThreat.closing_speed_mps);
#endif
    } else {
        digitalWrite(LED_PIN, LOW);
#ifdef USE_USB_BRIDGE
        Serial.println("CLEAR");
#endif
    }

    // --- ALWAYS send to Bluetooth/HUD task, even if no threat (so HUD clears old alerts) ---
    if (radarQueue != NULL) {
        xQueueSend(radarQueue, &primaryThreat, (TickType_t)0);
    }
}

void resetPacketParser() {
    packetLength = 0;
    expectedPacketLength = 0;
    collectingPacket = false;
}

// Byte-by-byte state machine that hunts for MAGIC_WORD and assembles full frames
void receiveRadarByte(uint8_t value) {
    if (!collectingPacket) {
        // Shift 8-byte sliding window and check for Magic Word
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

    // Guard against buffer overflow
    if (packetLength >= MAX_PACKET_SIZE) {
        resetPacketParser();
        return;
    }

    packetBuffer[packetLength++] = value;

    // Once we have the 40-byte header, extract totalPacketLen (at byte offset 12)
    if (packetLength == HEADER_SIZE) {
        uint32_t totalLength;
        memcpy(&totalLength, packetBuffer + 12, sizeof(totalLength));

        if (totalLength < HEADER_SIZE || totalLength > MAX_PACKET_SIZE) {
            resetPacketParser();
            return;
        }
        expectedPacketLength = totalLength;
    }

    // Full packet received -> parse it and reset for the next frame
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
        // Drain all available bytes from laptop USB bridge
        while (Serial.available() > 0) {
            uint8_t value = (uint8_t)Serial.read();
            receiveRadarByte(value);
        }
#else
        // Drain all available bytes from physical radar UART2
        while (Serial2.available() > 0) {
            uint8_t value = (uint8_t)Serial2.read();
            receiveRadarByte(value);
        }
#endif
        // Yield 5ms to RTOS scheduler so Bluetooth/HUD tasks can run
        vTaskDelay(pdMS_TO_TICKS(5));
    }
}