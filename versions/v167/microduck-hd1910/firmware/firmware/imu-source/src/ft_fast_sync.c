#include "ft_fast_sync.h"

#include <string.h>

bool ft_fast_sync_request_matches(const uint8_t *request, size_t length)
{
    ft_packet_t packet;

    return ft_parse(request, length, &packet) &&
           packet.id == FT_BROADCAST &&
           packet.instruction == 0x82u &&
           packet.parameter_count >= 3u &&
           packet.parameters[0] == FT_IMU_SYNC_ADDRESS &&
           packet.parameters[1] == FT_IMU_SYNC_LENGTH &&
           packet.parameters[2] == FT_IMU_ID;
}

void ft_fast_sync_response_prepare(ft_fast_sync_response_t *response,
                                   const ft_imu_state_t *state)
{
    if (response == NULL || state == NULL) {
        return;
    }

    response->bytes[0] = 0xFFu;
    response->bytes[1] = 0xFFu;
    response->bytes[2] = FT_IMU_ID;
    response->bytes[3] = FT_IMU_SYNC_LENGTH + 2u;
    response->bytes[4] = 0u;
    memcpy(response->bytes + 5u, state->block, FT_IMU_BLOCK_LENGTH);
    response->bytes[17] = (uint8_t)state->sequence;
    response->bytes[18] = 0u; /* Status is evaluated at TX, not at publication. */
    response->bytes[19] = 0u; /* Community reserved byte. */

    uint8_t sum = 0u;
    for (size_t i = 2u; i < 20u; ++i) {
        if (i != 18u) {
            sum = (uint8_t)(sum + response->bytes[i]);
        }
    }
    response->fixed_sum = sum;
    response->last_quaternion_ms = state->last_quaternion_ms;
    response->sequence = state->sequence;
    const uint8_t zero[6] = {0};
    response->ready = state->ready && memcmp(state->block + 6u, zero, sizeof(zero)) != 0;
    response->bytes[20] = (uint8_t)~sum;
}

void ft_fast_sync_response_finalize(ft_fast_sync_response_t *response,
                                    uint32_t now_ms, const ft_imu_state_t *state)
{
    if (response == NULL || state == NULL) {
        return;
    }

    response->bytes[18] = ft_imu_compact_status(response->ready,
        (uint32_t)(now_ms - response->last_quaternion_ms),
        state->read_before ? (uint32_t)(response->sequence - state->last_read_sequence) : 0u);
    response->bytes[20] = (uint8_t)~(uint8_t)(response->fixed_sum + response->bytes[18]);
}
