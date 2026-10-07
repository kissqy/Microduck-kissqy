#include "id200_app.h"

#include <stdbool.h>
#include <string.h>

#include "dxl_protocol.h"

#define DXL2_INST_PING 0x01u
#define DXL2_INST_READ 0x02u
#define DXL2_INST_SYNC_READ 0x82u

static uint16_t read_u16_le(const uint8_t *bytes)
{
    return (uint16_t)bytes[0] | ((uint16_t)bytes[1] << 8);
}

static bool is_fixed_read(const dxl2_instruction_t *request)
{
    return request->parameter_count == 4u &&
           read_u16_le(request->parameters) == ID200_DATA_ADDRESS &&
           read_u16_le(request->parameters + 2u) == ID200_DATA_LENGTH;
}

static bool is_sync_read_for_id200(const dxl2_instruction_t *request)
{
    if (request->parameter_count < 5u ||
        read_u16_le(request->parameters) != ID200_DATA_ADDRESS ||
        read_u16_le(request->parameters + 2u) != ID200_DATA_LENGTH) {
        return false;
    }

    /* M8 lists ID 200 first. Requiring first position prevents a collision if a
       generic tester sends a different ordering that this RevA proof firmware
       does not yet schedule. */
    return request->parameters[4] == ID200_DEVICE_ID;
}

static size_t build_data_status(id200_state_t *state,
                                uint8_t *response,
                                size_t response_capacity)
{
    ++state->valid_request_count;
    return dxl2_build_status(ID200_DEVICE_ID,
                             0u,
                             state->imu_block,
                             sizeof(state->imu_block),
                             response,
                             response_capacity);
}

void id200_init(id200_state_t *state)
{
    memset(state->imu_block, 0, sizeof(state->imu_block));
    state->valid_request_count = 0u;
}

void id200_set_imu_block(id200_state_t *state,
                         const uint8_t block[ID200_DATA_LENGTH])
{
    if (state != NULL && block != NULL) {
        memcpy(state->imu_block, block, ID200_DATA_LENGTH);
    }
}

size_t id200_handle_packet(id200_state_t *state,
                           const uint8_t *request_packet,
                           size_t request_length,
                           uint8_t *response,
                           size_t response_capacity)
{
    uint8_t body[DXL2_MAX_PACKET];
    dxl2_instruction_t request;
    if (state == NULL || !dxl2_parse_instruction(request_packet,
                                                  request_length,
                                                  &request,
                                                  body,
                                                  sizeof(body))) {
        return 0u;
    }

    if (request.id == ID200_DEVICE_ID &&
        request.instruction == DXL2_INST_PING &&
        request.parameter_count == 0u) {
        /* RevA custom model 0xF200, live LSM6DSV16X firmware v2. */
        const uint8_t identity[3] = {0x00u, 0xF2u, 0x02u};
        ++state->valid_request_count;
        return dxl2_build_status(ID200_DEVICE_ID,
                                 0u,
                                 identity,
                                 sizeof(identity),
                                 response,
                                 response_capacity);
    }

    if (request.id == ID200_DEVICE_ID &&
        request.instruction == DXL2_INST_READ && is_fixed_read(&request)) {
        return build_data_status(state, response, response_capacity);
    }

    if (request.id == DXL2_BROADCAST_ID &&
        request.instruction == DXL2_INST_SYNC_READ &&
        is_sync_read_for_id200(&request)) {
        return build_data_status(state, response, response_capacity);
    }

    return 0u;
}
