/**
 * @file radar_sensor.h
 *
 * Provides control, configuration, and data acquisition for the
 * radar sensor. Creates 30m detection envelope, 60 degree field of view 
 * and velocity/angle.
 */

#ifndef RADAR_SENSOR_H
#define RADAR_SENSOR_H

#include <stdint.h>
#include <stdbool.h>


/* CONSTANTS */

#define RADAR_MAX_TARGETS         8         /* Max amount of targets in view  */
#define RADAR_MAX_RANGE           30.0f    /* 30 meter maximum range */
#define RADAR_FOV_HALF_ANGLE      30.0f   /* ±30 (60 degree total) */

// Error messages
 
typedef enum {
    RADAR_OK = 0,
    RADAR_ERR_INIT_FAILED,
    RADAR_ERR_COMM_TIMEOUT,
    RADAR_ERR_INVALID_PARAM,
    RADAR_ERR_BUSY
} radar_status_t;

// Collison alert tiers 

typedef enum {
    NO_TARGET = 0,      /* No target detected or receding target */
    SLOW_TARGET,       /* Slow approaching vehicle */
    MEDIUM_TARGET,    /* Moderate speed approaching vehicle */
    FAST_TARGET      /* Fast approaching vehicle */
} tier_list_t;

// Individual reflection point from raw mmWave point cloud
 
typedef struct {
    float x;               /* postion along x axis */
    float y;              /* position along y axis */
    float z;             /* height in meters */
    float velocity;     /* relative velocity */
} radar_point_t;

// Clustering parameters
 
typedef struct {
    float max_cluster_distance;    /* max distance between points to be considered a group */
    float max_velocity_diff;      /* max velocity diff between points to be considered a group */
    uint8_t min_points_cluster;  /* min points to be considered a group */
} radar_cluster_t;

// Target data structs
 
typedef struct {
    uint8_t target_id;                   /* identifier for each unique target */
    float distance;                     /* distance from biker */
    float approaching_speed;           /* relative velocity to biker (+ is toward rider, - is away)*/
    float approach_angle_horizontal;  /* angle of arrival  */
    tier_list_t tier;                /* approaching speed alert tier */
    uint32_t timestamp_ms;          /* current time of last seen */
} radar_target_t;

// struct containing current frame data, quantity 

typedef struct {
    uint8_t active_targets;                       /* number of active targets */
    radar_target_t targets[RADAR_MAX_TARGETS];   /* array of active targets */
    uint16_t frame_processing_time_ms;          /* Frame processing time */
    uint16_t num_points;                       /* How many points were detected */
    float sensor_temp;                        /* Internal chip temp return */
} radar_frame_t;

/* RADAR INTERFACE FUNCTIONS */

// Inialize radar connection and SPI connection
 
radar_status_t radar_load_cli_config(const char *cli_config_str);
radar_status_t radar_init(void);

// Configure radar parameters (Range envelope, FOV, and update frequency)
radar_status_t radar_configure(float max_range, float fov_deg);

//Groups raw point cloud reflections into tracked targets
radar_status_t radar_cluster_points(const radar_point_t *points, uint16_t num_points, const radar_cluster_t *config, radar_frame_t *frame);


// Get a frame from the radar system

radar_status_t radar_get_frame(radar_frame_t *frame);


// Enter low power mode when not in use
radar_status_t radar_sleep(void);

#endif /* RADAR_SENSOR_H */
