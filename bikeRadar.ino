#include <Arduino.h>
#include <math.h>
#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#if ESP_ARDUINO_VERSION_MAJOR < 3
#include <BLE2902.h>   // core 3.x adds the notify descriptor automatically
#endif
#include "radarConfig.h"

// Two separate radar UARTs: CLI for config, DATA for binary frames
#define CliSerial  Serial2
#define DataSerial Serial1

// BLE globals
BLEServer*         pServer         = nullptr;
BLECharacteristic* pCharacteristic = nullptr;
volatile bool      deviceConnected = false;

// TI mmWave sync pattern
static const uint8_t SYNC_MAGIC_WORD[8] = {0x02, 0x01, 0x04, 0x03, 0x06, 0x05, 0x08, 0x07};

// Frame buffer (everything after the 40-byte header)
static uint8_t frameBuf[4096];

// Prototypes
VehicleThreat evaluateThreat(const DetectedObject& obj);
bool          sendRadarCommand(const char* cmd, uint32_t timeoutMs, bool fatal);
VehicleThreat parseFrame(const uint8_t* p, size_t len, uint32_t numTLVs);
void          updateThreatState(const VehicleThreat& best);
void          processIncomingData();
void          broadcastThreat(const VehicleThreat& threat);

// ---------------------------------------------------------------------------
// BLE callbacks
// ---------------------------------------------------------------------------
class ServerCallbacks : public BLEServerCallbacks {
    void onConnect(BLEServer* server) override {
        deviceConnected = true;
        Serial.println("BLE client connected (HUD)");
    }
    void onDisconnect(BLEServer* server) override {
        deviceConnected = false;
        Serial.println("BLE client disconnected");
        BLEDevice::startAdvertising();   // let the HUD reconnect
    }
};

// ---------------------------------------------------------------------------
// Threat evaluation
// ---------------------------------------------------------------------------
VehicleThreat evaluateThreat(const DetectedObject& obj) {
    VehicleThreat t = {0.0f, 0.0f, 0.0f, 99.0f, 0, false};

    if (!isfinite(obj.x) || !isfinite(obj.y) || !isfinite(obj.velocity)) return t;

    t.distance      = sqrtf(obj.x * obj.x + obj.y * obj.y);
    t.angle         = atan2f(obj.x, obj.y) * RAD_TO_DEG;
    t.approachSpeed = -obj.velocity * 3.6f;   // negative Doppler = closing

    // Ignore: behind the sensor plane, too far sideways, too far away,
    // static, or receding
    if (obj.y <= 0.0f ||
        fabsf(obj.x) > MAX_LATERAL_M ||
        t.distance > MAX_RANGE_M ||
        t.approachSpeed < MIN_APPROACH_KMH) {
        t.approachSpeed = 0.0f;
        return t;
    }

    t.ttc = t.distance / (t.approachSpeed / 3.6f);

    // In your path or in the passing lane? The window widens with range because
    // azimuth error grows with distance.
    float widen = DIRECT_WIDEN_PER_M * obj.y;
    t.isDirectPath = (obj.x >= DIRECT_X_MIN_M - widen) &&
                     (obj.x <= DIRECT_X_MAX_M + widen);

    if (t.isDirectPath) {
        // Direct path: escalate quickly
        if (t.ttc <= DIRECT_TIER3_TTC_S || t.approachSpeed > DIRECT_TIER3_KMH) {
            t.threatTier = 3;
        } else if (t.ttc <= DIRECT_TIER2_TTC_S) {
            t.threatTier = 2;
        } else {
            t.threatTier = 1;
        }
    } else {
        // Passing lane: lower severity, it is bypassing you
        if (t.ttc <= PASS_TIER2_TTC_S && t.approachSpeed > PASS_TIER2_KMH) {
            t.threatTier = 2;   // fast pass close by
        } else {
            t.threatTier = 1;   // informational
        }
    }
    return t;
}

// Higher = more important. Severity first, direct path breaks ties.
// (To make ANY direct threat outrank passing ones, use: direct*4 + tier.)
static inline uint8_t threatRank(const VehicleThreat& v) {
    return v.threatTier * 2 + (v.isDirectPath ? 1 : 0);
}

// ---------------------------------------------------------------------------
// Send one CLI command and wait for the radar's reply
// ---------------------------------------------------------------------------
bool sendRadarCommand(const char* cmd, uint32_t timeoutMs, bool fatal) {
    while (CliSerial.available()) CliSerial.read();   // drop stale bytes

    CliSerial.print(cmd);
    CliSerial.print('\n');

    String resp;
    uint32_t start = millis();
    while (millis() - start < timeoutMs) {
        while (CliSerial.available()) {
            resp += (char)CliSerial.read();
            if (resp.length() > 512) resp.remove(0, 256);
        }
        if (resp.indexOf("Done") >= 0 || resp.indexOf("Ignored") >= 0 ||
            resp.indexOf("Skipped") >= 0) {
            Serial.printf("OK    : %s\n", cmd);
            return true;
        }
        if (resp.indexOf("Error") >= 0 || resp.indexOf("not recognized") >= 0) {
            Serial.printf("ERROR : %s\n%s\n", cmd, resp.c_str());
            return !fatal;
        }
        delay(2);
    }
    Serial.printf("TIMEOUT: %s (no reply)\n", cmd);
    return !fatal;
}

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------
void setup() {
    Serial.begin(115200);
    delay(500);

    // CLI port
    CliSerial.begin(CLI_BAUD, SERIAL_8N1, CLI_RX_PIN, CLI_TX_PIN);

    // Data port (RX only). Buffer size must be set BEFORE begin().
    DataSerial.setRxBufferSize(4096);
    DataSerial.begin(DATA_BAUD, SERIAL_8N1, DATA_RX_PIN, -1);
    DataSerial.setTimeout(50);   // inter-byte timeout for readBytes()

    delay(1000);

    // 1. Configure radar, stop on first real error
    Serial.println("Configuring AWR6843...");
    bool radarOk = true;
    for (size_t i = 0; i < NUM_CONFIG_COMMANDS; i++) {
        bool fatal = (i != 0);   // sensorStop may legitimately complain if already stopped
        if (!sendRadarCommand(RADAR_CONFIG_COMMANDS[i], 1500, fatal)) {
            radarOk = false;
            break;
        }
    }
    Serial.println(radarOk ? "Radar configured and started."
                           : "RADAR CONFIG FAILED - check wiring, firmware, and config above.");

    // 2. BLE server
    BLEDevice::init("BikeRadar_ESP32");
    pServer = BLEDevice::createServer();
    pServer->setCallbacks(new ServerCallbacks());

    BLEService* pService = pServer->createService(SERVICE_UUID);
    pCharacteristic = pService->createCharacteristic(
        CHARACTERISTIC_UUID,
        BLECharacteristic::PROPERTY_READ | BLECharacteristic::PROPERTY_NOTIFY);
#if ESP_ARDUINO_VERSION_MAJOR < 3
    pCharacteristic->addDescriptor(new BLE2902());
#endif
    ThreatPacket idle = {0, 0, 0, 0, 255};
    pCharacteristic->setValue((uint8_t*)&idle, sizeof(idle));
    pService->start();

    BLEAdvertising* pAdvertising = BLEDevice::getAdvertising();
    pAdvertising->addServiceUUID(SERVICE_UUID);
    pAdvertising->setScanResponse(true);
    BLEDevice::startAdvertising();

    Serial.println("System ready. Listening for radar frames and BLE HUD...");
}

void loop() {
    processIncomingData();
    delay(2);   // yield to the BLE / system tasks
}

// ---------------------------------------------------------------------------
// Frame sync + whole-frame read
// ---------------------------------------------------------------------------
void processIncomingData() {
    static uint8_t syncIndex = 0;

    while (DataSerial.available()) {
        uint8_t b = (uint8_t)DataSerial.read();

        if (b == SYNC_MAGIC_WORD[syncIndex]) {
            syncIndex++;
        } else {
            // The breaking byte may itself start a new sync word
            syncIndex = (b == SYNC_MAGIC_WORD[0]) ? 1 : 0;
            continue;
        }
        if (syncIndex < MMWAVE_MAGIC_BYTES) continue;
        syncIndex = 0;

        // Read the remaining 32 header bytes
        uint8_t hdrBytes[MMWAVE_HEADER_BYTES];
        memcpy(hdrBytes, SYNC_MAGIC_WORD, MMWAVE_MAGIC_BYTES);
        if (DataSerial.readBytes(hdrBytes + MMWAVE_MAGIC_BYTES,
                                 MMWAVE_HEADER_BYTES - MMWAVE_MAGIC_BYTES)
            != MMWAVE_HEADER_BYTES - MMWAVE_MAGIC_BYTES) continue;

        MMWaveFrameHeader hdr;
        memcpy(&hdr, hdrBytes, sizeof(hdr));

        // Sanity check, then read the rest of the frame into memory
        if (hdr.totalPacketLen < MMWAVE_HEADER_BYTES) continue;
        size_t bodyLen = hdr.totalPacketLen - MMWAVE_HEADER_BYTES;
        if (bodyLen > sizeof(frameBuf)) continue;   // oversize: resync on next frame
        if (DataSerial.readBytes(frameBuf, bodyLen) != bodyLen) continue;

        VehicleThreat best = parseFrame(frameBuf, bodyLen, hdr.numTLVs);
        updateThreatState(best);
    }
}

// Parse TLVs from the in-memory frame body, return the most important threat
VehicleThreat parseFrame(const uint8_t* p, size_t len, uint32_t numTLVs) {
    VehicleThreat best = {0.0f, 0.0f, 0.0f, 99.0f, 0, false};
    size_t off = 0;

    for (uint32_t i = 0; i < numTLVs && off + sizeof(TLVHeader) <= len; i++) {
        TLVHeader tlv;
        memcpy(&tlv, p + off, sizeof(tlv));
        off += sizeof(tlv);
        if (tlv.length > len - off) break;   // corrupt frame

        if (tlv.type == TLV_TYPE_POINT_CLOUD) {
            for (size_t o = 0; o + sizeof(DetectedObject) <= tlv.length;
                 o += sizeof(DetectedObject)) {
                DetectedObject obj;
                memcpy(&obj, p + off + o, sizeof(obj));
                VehicleThreat t = evaluateThreat(obj);
                if (t.threatTier == 0) continue;

                // Higher rank wins; on a tie, the shorter time-to-collision wins
                if (threatRank(t) > threatRank(best) ||
                    (threatRank(t) == threatRank(best) && t.ttc < best.ttc)) {
                    best = t;
                }
            }
        }
        off += tlv.length;   // skip other TLVs
    }
    return best;
}

// Temporal filtering:
//  - need CONFIRM_FRAMES consecutive detections before alerting
//  - need CLEAR_FRAMES empty frames before clearing
//  - the direct/passing flag only flips after PATH_FLIP_FRAMES frames agree,
//    so cars near the lane boundary don't flicker between the two
void updateThreatState(const VehicleThreat& best) {
    static uint8_t streak     = 0;
    static uint8_t misses     = 0;
    static bool    active     = false;
    static bool    directState = false;
    static uint8_t flipCount  = 0;

    if (best.threatTier > 0) {
        if (streak < 255) streak++;
        misses = 0;
    } else {
        if (misses < 255) misses++;
        streak = 0;
    }

    if (best.threatTier > 0 && streak >= CONFIRM_FRAMES) {
        // Path-flag hysteresis (a fresh alert adopts the first reading)
        if (!active) {
            directState = best.isDirectPath;
            flipCount = 0;
        } else if (best.isDirectPath != directState) {
            if (++flipCount >= PATH_FLIP_FRAMES) {
                directState = best.isDirectPath;
                flipCount = 0;
            }
        } else {
            flipCount = 0;
        }

        VehicleThreat out = best;
        out.isDirectPath = directState;
        active = true;

        Serial.printf("THREAT TIER %d (%s) | %.1f m | %.1f km/h | %.1f deg | TTC %.1f s\n",
                      out.threatTier, out.isDirectPath ? "DIRECT" : "PASSING",
                      out.distance, out.approachSpeed, out.angle, out.ttc);
        broadcastThreat(out);
    } else if (active && misses >= CLEAR_FRAMES) {
        active = false;
        flipCount = 0;
        VehicleThreat clear = {0.0f, 0.0f, 0.0f, 99.0f, 0, false};
        Serial.println("Threat cleared");
        broadcastThreat(clear);
    }
}

// ---------------------------------------------------------------------------
// BLE notify: 6-byte packed packet (fits the default 20-byte payload)
// ---------------------------------------------------------------------------
void broadcastThreat(const VehicleThreat& t) {
    if (!deviceConnected || pCharacteristic == nullptr) return;

    ThreatPacket pkt;
    pkt.tier     = (uint8_t)((t.threatTier & 0x7F) | (t.isDirectPath ? PACKET_DIRECT_FLAG : 0));
    pkt.distCm   = (uint16_t)constrain(lroundf(t.distance * 100.0f), 0L, 65535L);
    pkt.speedKmh = (uint8_t)constrain(lroundf(t.approachSpeed), 0L, 255L);
    pkt.angleDeg = (int8_t)constrain(lroundf(t.angle), -127L, 127L);
    pkt.ttcDs    = (uint8_t)constrain(lroundf(t.ttc * 10.0f), 0L, 255L);

    pCharacteristic->setValue((uint8_t*)&pkt, sizeof(pkt));
    pCharacteristic->notify();
}
