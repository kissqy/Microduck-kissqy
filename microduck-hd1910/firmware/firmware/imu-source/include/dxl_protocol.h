#ifndef DXL_PROTOCOL_H
#define DXL_PROTOCOL_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define DXL2_MAX_PACKET 256u
#define DXL2_BROADCAST_ID 0xFEu
#define DXL2_STATUS_INSTRUCTION 0x55u

typedef struct {
    uint8_t id;
    uint8_t instruction;
    const uint8_t *parameters;
    size_t parameter_count;
} dxl2_instruction_t;

uint16_t dxl2_crc16(const uint8_t *data, size_t length);

bool dxl2_parse_instruction(const uint8_t *packet,
                            size_t packet_length,
                            dxl2_instruction_t *result,
                            uint8_t *unstuffed_body,
                            size_t unstuffed_capacity);

size_t dxl2_build_status(uint8_t id,
                         uint8_t error,
                         const uint8_t *parameters,
                         size_t parameter_count,
                         uint8_t *output,
                         size_t output_capacity);

#endif
