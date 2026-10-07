#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "dxl_protocol.h"
#include "id200_app.h"

static size_t build_instruction(uint8_t id,
                                uint8_t instruction,
                                const uint8_t *parameters,
                                size_t parameter_count,
                                uint8_t *packet,
                                size_t capacity)
{
    const size_t length_field = parameter_count + 3u;
    const size_t total = 7u + length_field;
    assert(total <= capacity);
    packet[0] = 0xFFu;
    packet[1] = 0xFFu;
    packet[2] = 0xFDu;
    packet[3] = 0x00u;
    packet[4] = id;
    packet[5] = (uint8_t)length_field;
    packet[6] = (uint8_t)(length_field >> 8);
    packet[7] = instruction;
    if (parameter_count != 0u) {
        memcpy(packet + 8u, parameters, parameter_count);
    }
    const uint16_t crc = dxl2_crc16(packet, total - 2u);
    packet[total - 2u] = (uint8_t)crc;
    packet[total - 1u] = (uint8_t)(crc >> 8);
    return total;
}

static void verify_data_status(const uint8_t *packet,
                               size_t length,
                               const uint8_t expected[ID200_DATA_LENGTH])
{
    uint8_t body[DXL2_MAX_PACKET];
    dxl2_instruction_t parsed;
    assert(length == 23u);
    assert(dxl2_parse_instruction(packet, length, &parsed,
                                  body, sizeof(body)));
    assert(parsed.id == ID200_DEVICE_ID);
    assert(parsed.instruction == DXL2_STATUS_INSTRUCTION);
    assert(parsed.parameter_count == 13u);
    assert(parsed.parameters[0] == 0u);
    assert(memcmp(parsed.parameters + 1u, expected, ID200_DATA_LENGTH) == 0);
}

static void test_official_ping_crc_vector(void)
{
    const uint8_t ping_without_crc[] = {
        0xFFu, 0xFFu, 0xFDu, 0x00u, 0x01u, 0x03u, 0x00u, 0x01u
    };
    assert(dxl2_crc16(ping_without_crc, sizeof(ping_without_crc)) == 0x4E19u);
}

static void test_ping(void)
{
    uint8_t request[64];
    uint8_t response[64];
    uint8_t body[64];
    dxl2_instruction_t parsed;
    id200_state_t state;
    id200_init(&state);
    const size_t request_length = build_instruction(
        ID200_DEVICE_ID, 0x01u, NULL, 0u, request, sizeof(request));
    const size_t response_length = id200_handle_packet(
        &state, request, request_length, response, sizeof(response));
    assert(response_length == 14u);
    assert(dxl2_parse_instruction(response, response_length,
                                  &parsed, body, sizeof(body)));
    assert(parsed.instruction == 0x55u);
    assert(parsed.parameter_count == 4u);
    assert(parsed.parameters[0] == 0u);
    assert(parsed.parameters[1] == 0x00u);
    assert(parsed.parameters[2] == 0xF2u);
    assert(parsed.parameters[3] == 0x02u);
}

static void test_direct_read_live_block(void)
{
    const uint8_t params[] = {0x7Cu, 0x00u, 0x0Cu, 0x00u};
    const uint8_t live[ID200_DATA_LENGTH] = {
        0x34u, 0x12u, 0xFEu, 0xFFu, 0x55u, 0xAAu,
        0x00u, 0x30u, 0x00u, 0x38u, 0x00u, 0xB0u
    };
    uint8_t request[64];
    uint8_t response[64];
    id200_state_t state;
    id200_init(&state);
    id200_set_imu_block(&state, live);
    const size_t request_length = build_instruction(
        ID200_DEVICE_ID, 0x02u, params, sizeof(params),
        request, sizeof(request));
    size_t n = id200_handle_packet(&state, request, request_length,
                                   response, sizeof(response));
    verify_data_status(response, n, live);
    n = id200_handle_packet(&state, request, request_length,
                            response, sizeof(response));
    verify_data_status(response, n, live);
}

static void test_sync_read(void)
{
    const uint8_t params[] = {
        0x7Cu, 0x00u, 0x0Cu, 0x00u, ID200_DEVICE_ID, 0x01u
    };
    uint8_t request[64];
    uint8_t response[64];
    id200_state_t state;
    const uint8_t live[ID200_DATA_LENGTH] = {
        1u, 2u, 3u, 4u, 5u, 6u, 7u, 8u, 9u, 10u, 11u, 12u
    };
    id200_init(&state);
    id200_set_imu_block(&state, live);
    const size_t request_length = build_instruction(
        DXL2_BROADCAST_ID, 0x82u, params, sizeof(params),
        request, sizeof(request));
    const size_t n = id200_handle_packet(&state, request, request_length,
                                         response, sizeof(response));
    verify_data_status(response, n, live);
}

static void test_rejections(void)
{
    uint8_t request[64];
    uint8_t response[64];
    id200_state_t state;
    id200_init(&state);

    const uint8_t wrong_range[] = {0x7Du, 0x00u, 0x0Cu, 0x00u};
    size_t n = build_instruction(ID200_DEVICE_ID, 0x02u,
                                 wrong_range, sizeof(wrong_range),
                                 request, sizeof(request));
    assert(id200_handle_packet(&state, request, n,
                               response, sizeof(response)) == 0u);

    const uint8_t wrong_order[] = {
        0x7Cu, 0x00u, 0x0Cu, 0x00u, 0x01u, ID200_DEVICE_ID
    };
    n = build_instruction(DXL2_BROADCAST_ID, 0x82u,
                          wrong_order, sizeof(wrong_order),
                          request, sizeof(request));
    assert(id200_handle_packet(&state, request, n,
                               response, sizeof(response)) == 0u);

    const uint8_t good_range[] = {0x7Cu, 0x00u, 0x0Cu, 0x00u};
    n = build_instruction(ID200_DEVICE_ID, 0x02u,
                          good_range, sizeof(good_range),
                          request, sizeof(request));
    request[n - 1u] ^= 0x80u;
    assert(id200_handle_packet(&state, request, n,
                               response, sizeof(response)) == 0u);
}

static void test_status_byte_stuffing(void)
{
    const uint8_t params[] = {0x12u, 0xFFu, 0xFFu, 0xFDu, 0x34u};
    uint8_t packet[64];
    uint8_t body[64];
    dxl2_instruction_t parsed;
    const size_t n = dxl2_build_status(200u, 0u, params, sizeof(params),
                                       packet, sizeof(packet));
    assert(n != 0u);
    assert(dxl2_parse_instruction(packet, n, &parsed, body, sizeof(body)));
    assert(parsed.parameter_count == sizeof(params) + 1u);
    assert(parsed.parameters[0] == 0u);
    assert(memcmp(parsed.parameters + 1u, params, sizeof(params)) == 0);
}

static void test_random_input_safety(void)
{
    uint8_t request[DXL2_MAX_PACKET];
    uint8_t response[DXL2_MAX_PACKET];
    uint32_t random = 0xC001D00Du;
    id200_state_t state;
    id200_init(&state);
    for (size_t round = 0u; round < 100000u; ++round) {
        random = random * 1664525u + 1013904223u;
        const size_t length = random % (sizeof(request) + 1u);
        for (size_t i = 0u; i < length; ++i) {
            random = random * 1664525u + 1013904223u;
            request[i] = (uint8_t)(random >> 24);
        }
        (void)id200_handle_packet(&state, request, length,
                                  response, sizeof(response));
    }
}

int main(void)
{
    test_official_ping_crc_vector();
    test_ping();
    test_direct_read_live_block();
    test_sync_read();
    test_rejections();
    test_status_byte_stuffing();
    test_random_input_safety();
    puts("PASS: DXL2 CRC, stuffing, Ping, Read, Sync Read, rejection, 100k fuzz");
    return 0;
}
