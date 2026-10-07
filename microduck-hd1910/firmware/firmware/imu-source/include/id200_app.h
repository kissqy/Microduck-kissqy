#ifndef ID200_APP_H
#define ID200_APP_H

#include <stddef.h>
#include <stdint.h>

#define ID200_DEVICE_ID 200u
#define ID200_DATA_ADDRESS 124u
#define ID200_DATA_LENGTH 12u

typedef struct {
    uint8_t imu_block[ID200_DATA_LENGTH];
    uint32_t valid_request_count;
} id200_state_t;

void id200_init(id200_state_t *state);
void id200_set_imu_block(id200_state_t *state,
                         const uint8_t block[ID200_DATA_LENGTH]);

size_t id200_handle_packet(id200_state_t *state,
                           const uint8_t *request,
                           size_t request_length,
                           uint8_t *response,
                           size_t response_capacity);

#endif
