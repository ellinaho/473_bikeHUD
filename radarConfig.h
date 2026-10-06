#ifndef RADAR_CONFIG_H
#define RADAR_CONFIG_H

#include <Arduino.h>

// ---------------------------------------------------------------------------
// Wiring (ESP32-DevKitC-32E)
//   GPIO16 (RX2) <- radar CLI  TX     (115200 baud, config commands)
//   GPIO17 (TX2) -> radar CLI  RX
//   GPIO18 (RX1) <- radar DATA TX     (921600 baud, binary TLV frames)
//   GND          -- radar GND (common ground is required)
// ---------------------------------------------------------------------------
#define CLI_RX_PIN   16
#define CLI_TX_PIN   17
#define DATA_RX_PIN  18
#define CLI_BAUD     115200
#define DATA_BAUD    921600

// ---------------------------------------------------------------------------
// 1. Radar CLI configuration (sent one command at a time, newline added in code)
//
// Design targets (rear-facing, 2-TX azimuth-only, ~60.25 GHz):
//   chirp time        25 us (5 idle + 20 ramp), 2 TX in TDM -> 50 us per TX cycle
//   max unambiguous v ~ +/-24.8 m/s (~89 km/h closing speed)
//   velocity res      ~1.5 m/s (32 loops)
//   max range         ~37 m (we crop to 30 m), range resolution ~0.59 m
//   frame rate        20 Hz
//
// channelCfg 15 5 0 / chirp masks 1 and 4 = TX1 + TX3 (the azimuth pair on
// the AWR6843ISK). If your board differs, change txMask and chirp masks.
// Validate against TI's mmWave Demo Visualizer before trusting it.
// ---------------------------------------------------------------------------
static const char* const RADAR_CONFIG_COMMANDS[] = {
    "sensorStop",
    "flushCfg",
    "dfeDataOutputMode 1",
    "channelCfg 15 5 0",
    "adcCfg 2 1",
    "adcbufCfg -1 0 1 1 1",
    "profileCfg 0 60.25 5 6 20 0 0 20 1 64 5000 0 0 30",
    "chirpCfg 0 0 0 0 0 0 0 1",
    "chirpCfg 1 1 0 0 0 0 0 4",
    "frameCfg 0 1 32 0 50 1 0",
    "lowPower 0 0",
    "guiMonitor -1 1 0 0 0 0 0",
    "cfarCfg -1 0 2 8 4 3 0 15 1",
    "cfarCfg -1 1 0 4 2 3 1 12 1",
    "multiObjBeamForming -1 1 0.5",
    "clutterRemoval -1 1",
    "calibDcRangeSig -1 0 -5 8 256",
    "extendedMaxVelocity -1 0",
    "aoaFovCfg -1 -60 60 -60 60",
    "cfarFovCfg -1 0 0.5 30.0",
    "cfarFovCfg -1 1 -24.0 24.0",
    "lvdsStreamCfg -1 0 0 0",
    "sensorStart"
};

static const size_t NUM_CONFIG_COMMANDS =
    sizeof(RADAR_CONFIG_COMMANDS) / sizeof(RADAR_CONFIG_COMMANDS[0]);

// ---------------------------------------------------------------------------
// 2. TI mmWave frame format (little-endian, tightly packed)
// ---------------------------------------------------------------------------
#define MMWAVE_HEADER_BYTES 40
#define MMWAVE_MAGIC_BYTES  8
#define TLV_TYPE_POINT_CLOUD 1   // SDK 3.x OOB demo: float x,y,z,velocity

struct __attribute__((packed)) MMWaveFrameHeader {
    uint8_t  magicWord[8];
    uint32_t version;
    uint32_t totalPacketLen;   // header + all TLVs + padding
    uint32_t platform;
    uint32_t frameNumber;
    uint32_t timeCpuCycles;
    uint32_t numDetectedObj;
    uint32_t numTLVs;
    uint32_t subFrameNumber;
};
static_assert(sizeof(MMWaveFrameHeader) == MMWAVE_HEADER_BYTES, "Bad frame header size");

struct __attribute__((packed)) TLVHeader {
    uint32_t type;
    uint32_t length;           // payload bytes, excluding this 8-byte header
};
static_assert(sizeof(TLVHeader) == 8, "Bad TLV header size");

struct __attribute__((packed)) DetectedObject {
    float x;         // lateral (m). Sign is from the RADAR's point of view; the
                     // sensor faces backward, so radar-right = rider-LEFT.
                     // Walk past it and check the sign before trusting L/R.
    float y;         // distance straight behind the rider (m)
    float z;         // height offset (m)
    float velocity;  // Doppler (m/s), negative = closing in
};
static_assert(sizeof(DetectedObject) == 16, "Bad point size");

// ---------------------------------------------------------------------------
// 3. Processed threat
// ---------------------------------------------------------------------------
struct VehicleThreat {
    float   distance;       // m
    float   angle;          // deg, -60..+60
    float   approachSpeed;  // km/h (relative closing speed)
    float   ttc;            // s
    uint8_t threatTier;     // 0 none, 1 low, 2 medium, 3 high
    bool    isDirectPath;   // true = in line with the bike, false = adjacent lane
};

// ---------------------------------------------------------------------------
// 4. Threat tuning
// ---------------------------------------------------------------------------
static const float MAX_RANGE_M      = 30.0f;
static const float MAX_LATERAL_M    = 3.5f;    // ignore anything farther sideways
static const float MIN_APPROACH_KMH = 3.0f;    // ignore static/receding

// "Direct path" window in radar x (m). Asymmetric on purpose: a bike usually
// rides near the lane edge, so traffic directly behind you is offset to one
// side. If traffic is on the other side of your bike, flip these two values
// (e.g. -2.0 and +0.75). Calibrate with real recordings.
static const float DIRECT_X_MIN_M       = -0.75f;
static const float DIRECT_X_MAX_M       =  2.0f;
// Azimuth error grows with range, so widen the window by this much per metre
// of distance (0.04 -> +0.8 m each side at 20 m).
static const float DIRECT_WIDEN_PER_M   = 0.04f;

// Direct-path tiers
static const float DIRECT_TIER3_TTC_S   = 3.0f;
static const float DIRECT_TIER3_KMH     = 40.0f;
static const float DIRECT_TIER2_TTC_S   = 6.0f;
// Passing-lane tiers
static const float PASS_TIER2_TTC_S     = 2.0f;
static const float PASS_TIER2_KMH       = 50.0f;

// Temporal filtering (frames at 20 Hz)
static const uint8_t CONFIRM_FRAMES     = 2;   // consecutive detections before alerting
static const uint8_t CLEAR_FRAMES       = 3;   // empty frames before clearing alert
static const uint8_t PATH_FLIP_FRAMES   = 2;   // frames before direct/passing flag may flip

// ---------------------------------------------------------------------------
// 5. BLE
// ---------------------------------------------------------------------------
#define SERVICE_UUID        "41234567-89ab-cdef-0123-456789abcdef"
#define CHARACTERISTIC_UUID "41234567-89ab-cdef-0123-456789abcde0"

// Bit 7 of the tier byte = direct-path flag.
//   HUD decode:  tier = byte0 & 0x7F;   direct = (byte0 >> 7) & 1;
#define PACKET_DIRECT_FLAG 0x80

// 6-byte notification payload (little-endian):
//   tier|flag(u8) distCm(u16) speedKmh(u8) angleDeg(i8) ttcTenthsSec(u8)
struct __attribute__((packed)) ThreatPacket {
    uint8_t  tier;        // low 7 bits = tier, bit 7 = direct path
    uint16_t distCm;
    uint8_t  speedKmh;
    int8_t   angleDeg;
    uint8_t  ttcDs;
};
static_assert(sizeof(ThreatPacket) == 6, "Bad packet size");

#endif
