#ifndef FT_FAST_SYNC_H
#define FT_FAST_SYNC_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "ft_imu.h"

#define FT_FAST_SYNC_RESPONSE_LENGTH (FT_IMU_SYNC_LENGTH + 6u)

typedef struct {
    uint8_t bytes[FT_FAST_SYNC_RESPONSE_LENGTH];
    uint8_t fixed_sum;
    uint32_t last_quaternion_ms;
    uint32_t sequence;
    bool ready;
} ft_fast_sync_response_t;

typedef struct {
    uint16_t count;
    uint16_t expected;
    uint32_t last_byte_tick;
    uint8_t header_state;
    uint8_t sum;
    bool candidate;
} ft_fast_sync_detector_t;

static inline void ft_fast_sync_detector_reset(
    ft_fast_sync_detector_t *detector)
{
    detector->count = 0u;
    detector->expected = 0u;
    detector->header_state = 0u;
    detector->sum = 0u;
    detector->candidate = false;
}

/*
 * Incremental ISR detector. It validates the checksum as bytes arrive, so the
 * final request byte does not trigger a second full-packet parsing pass.
 */
static inline bool ft_fast_sync_detector_push(
    ft_fast_sync_detector_t *detector, uint8_t byte, uint32_t now_ms)
{
    if ((detector->count != 0u || detector->header_state != 0u) &&
        (uint32_t)(now_ms - detector->last_byte_tick) > 3u) {
        ft_fast_sync_detector_reset(detector);
    }
    detector->last_byte_tick = now_ms;

    if (detector->count == 0u) {
        if (detector->header_state < 2u) {
            detector->header_state = (byte == 0xFFu) ?
                (uint8_t)(detector->header_state + 1u) : 0u;
        } else if (byte != 0xFFu) {
            detector->count = 3u;
            detector->expected = 0u;
            detector->header_state = 0u;
            detector->sum = byte;
            detector->candidate = byte == FT_BROADCAST;
        }
        return false;
    }

    const uint16_t index = detector->count;
    detector->sum = (uint8_t)(detector->sum + byte);
    if (index == 3u) {
        if (byte < 2u) {
            ft_fast_sync_detector_reset(detector);
            return false;
        }
        detector->expected = (uint16_t)byte + 4u;
        detector->candidate = detector->candidate && byte >= 5u;
    } else if (detector->candidate) {
        if ((index == 4u && byte != 0x82u) ||
            (index == 5u && byte != FT_IMU_SYNC_ADDRESS) ||
            (index == 6u && byte != FT_IMU_SYNC_LENGTH) ||
            (index == 7u && byte != FT_IMU_ID)) {
            detector->candidate = false;
        }
    }

    ++detector->count;
    if (detector->expected == 0u ||
        detector->count != detector->expected) {
        return false;
    }

    const bool matched = detector->candidate && detector->sum == 0xFFu;
    ft_fast_sync_detector_reset(detector);
    return matched;
}

bool ft_fast_sync_request_matches(const uint8_t *request, size_t length);
void ft_fast_sync_response_prepare(ft_fast_sync_response_t *response,
                                   const ft_imu_state_t *state);
void ft_fast_sync_response_finalize(ft_fast_sync_response_t *response,
                                    uint32_t now_ms, const ft_imu_state_t *state);

#endif
