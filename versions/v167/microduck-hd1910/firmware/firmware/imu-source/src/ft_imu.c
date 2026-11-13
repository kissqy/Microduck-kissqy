#include "ft_imu.h"
#include <string.h>

void ft_imu_init(ft_imu_state_t *state) { memset(state, 0, sizeof(*state)); }
uint8_t ft_imu_compact_status(bool ready, uint32_t age_ms, uint32_t new_samples)
{
    uint8_t status = ready ? 0u : FT_IMU_NOT_READY;
    /* Bound at transmission, including when the main-loop SPI poll stalls.
     * 30 ms + the host's 15 ms bus budget remains below its 50 ms limit. */
    if (ready && age_ms > FT_IMU_FRESH_MS) { status |= FT_IMU_STALE; }
    if (new_samples >= 5u) { status |= FT_IMU_READER_SLOW; }
    return status;
}
void ft_imu_note_read(ft_imu_state_t *state, uint32_t sequence)
{
    state->last_read_sequence = sequence;
    state->read_before = true;
}
void ft_imu_set(ft_imu_state_t *state, const uint8_t block[FT_IMU_BLOCK_LENGTH],
                 bool new_quaternion, uint32_t now_ms)
{
    memcpy(state->block, block, FT_IMU_BLOCK_LENGTH);
    if (new_quaternion) {
        ++state->sequence;
        state->last_quaternion_ms = now_ms;
        state->ready = true;
    }
}

static void snapshot(const ft_imu_state_t *state, uint8_t out[FT_IMU_LENGTH], uint32_t now_ms)
{
    memcpy(out, state->block, FT_IMU_BLOCK_LENGTH);
    for (size_t i = 0u; i < 4u; ++i) { out[12u + i] = (uint8_t)(state->sequence >> (8u * i)); }
    uint32_t age = state->ready ? (uint32_t)(now_ms - state->last_quaternion_ms) : 65535u;
    if (age > 65535u) { age = 65535u; }
    out[16] = (uint8_t)age; out[17] = (uint8_t)(age >> 8);
    out[18] = state->ready ? 1u : 0u; out[19] = 1u;
}

static void compact_snapshot(const ft_imu_state_t *state, uint8_t out[FT_IMU_SYNC_LENGTH], uint32_t now_ms)
{
    memcpy(out, state->block, FT_IMU_BLOCK_LENGTH);
    out[12] = (uint8_t)state->sequence;
    const uint8_t zero[6] = {0};
    const bool ready = state->ready && memcmp(state->block + 6u, zero, sizeof(zero)) != 0;
    out[13] = ft_imu_compact_status(ready, (uint32_t)(now_ms - state->last_quaternion_ms),
        state->read_before ? (uint32_t)(state->sequence - state->last_read_sequence) : 0u);
    out[14] = 0u;
}

size_t ft_imu_handle(ft_imu_state_t *state, const uint8_t *request, size_t request_length,
                      uint8_t *response, size_t capacity, uint32_t now_ms)
{
    ft_packet_t packet;
    if (state == NULL || !ft_parse(request, request_length, &packet)) { return 0u; }
    const bool unicast = packet.id == FT_IMU_ID;
    const bool sync = packet.id == FT_BROADCAST && packet.instruction == 0x82u &&
                      packet.parameter_count >= 3u && packet.parameters[2] == FT_IMU_ID;
    if (!unicast && !sync) { return 0u; }
    if (unicast && packet.instruction == 1u && packet.parameter_count == 0u) {
        ++state->valid_request_count;
        return ft_build(FT_IMU_ID, 0u, NULL, 0u, response, capacity);
    }
    if ((unicast && packet.instruction == 2u && packet.parameter_count == 2u) || sync) {
        const uint8_t address = packet.parameters[0];
        const uint8_t length = packet.parameters[1];
        uint8_t data[FT_IMU_LENGTH];
        const uint8_t *start = NULL;
        bool data_read = false;
        bool compact_read = false;
        /* FT6: incompatible 56/15 layout, explicitly distinguished from FT5. */
        const uint8_t identity[7] = {6u, 0u, 0u, 0u, 0xf2u, FT_IMU_ID, 0u};
        if (length != 0u && address < sizeof(identity) &&
            (size_t)address + length <= sizeof(identity)) {
            start = identity + address;
        } else if (length != 0u) {
            const uint16_t end = (uint16_t)address + length;
            uint8_t offset = 0u;
            bool data_range = false;
            if (address >= FT_IMU_ADDRESS &&
                end <= FT_IMU_ADDRESS + FT_IMU_LENGTH) {
                offset = (uint8_t)(address - FT_IMU_ADDRESS);
                data_range = true;
            } else if (address >= FT_IMU_SYNC_ADDRESS &&
                       end <= FT_IMU_SYNC_ADDRESS + FT_IMU_SYNC_LENGTH) {
                /* Community-compatible compact block; 124 stays diagnostic. */
                offset = (uint8_t)(address - FT_IMU_SYNC_ADDRESS);
                data_range = true;
                compact_read = true;
            }
            if (data_range) {
                if (compact_read) { compact_snapshot(state, data, now_ms); }
                else { snapshot(state, data, now_ms); }
                start = data + offset;
                data_read = true;
            }
        }
        if (start != NULL) {
            const size_t response_length =
                ft_build(FT_IMU_ID, 0u, start, length, response, capacity);
            if (response_length != 0u) {
                ++state->valid_request_count;
                if (data_read) {
                    ++state->data_read_count;
                    if (compact_read) { ft_imu_note_read(state, state->sequence); }
                }
            }
            return response_length;
        }
        return unicast ? ft_build(FT_IMU_ID, 8u, NULL, 0u, response, capacity) : 0u;
    }
    /* No writes, no reset, no baud/ID changes; broadcast never gets an error reply. */
    return unicast ? ft_build(FT_IMU_ID, 0x40u, NULL, 0u, response, capacity) : 0u;
}
