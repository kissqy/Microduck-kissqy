#ifndef FT_IMU_H
#define FT_IMU_H
#include "ft_protocol.h"
#define FT_IMU_ID 200u
#define FT_IMU_ADDRESS 124u
#define FT_IMU_SYNC_ADDRESS 56u
#define FT_IMU_LENGTH 20u
#define FT_IMU_SYNC_LENGTH 15u
#define FT_IMU_FRESH_MS 30u
#define FT_IMU_NOT_READY 0x01u
#define FT_IMU_STALE 0x02u
#define FT_IMU_READER_SLOW 0x08u
#define FT_IMU_BLOCK_LENGTH 12u
typedef struct {
    uint8_t block[FT_IMU_BLOCK_LENGTH];
    uint32_t sequence, last_quaternion_ms, valid_request_count, data_read_count;
    bool ready;
    volatile uint32_t last_read_sequence;
    volatile bool read_before;
} ft_imu_state_t;
uint8_t ft_imu_compact_status(bool ready, uint32_t age_ms, uint32_t new_samples);
void ft_imu_note_read(ft_imu_state_t *state, uint32_t sequence);
void ft_imu_init(ft_imu_state_t *state);
void ft_imu_set(ft_imu_state_t *state, const uint8_t block[FT_IMU_BLOCK_LENGTH],
                 bool new_quaternion, uint32_t now_ms);
size_t ft_imu_handle(ft_imu_state_t *state, const uint8_t *request, size_t request_length,
                      uint8_t *response, size_t capacity, uint32_t now_ms);
#endif
