#include "dxl_protocol.h"

static bool has_header(const uint8_t *packet, size_t length)
{
    return length >= 10u && packet[0] == 0xFFu && packet[1] == 0xFFu &&
           packet[2] == 0xFDu && packet[3] == 0x00u;
}

uint16_t dxl2_crc16(const uint8_t *data, size_t length)
{
    uint16_t crc = 0u;
    for (size_t i = 0u; i < length; ++i) {
        crc ^= (uint16_t)data[i] << 8;
        for (unsigned bit = 0u; bit < 8u; ++bit) {
            if ((crc & 0x8000u) != 0u) {
                crc = (uint16_t)((crc << 1) ^ 0x8005u);
            } else {
                crc <<= 1;
            }
        }
    }
    return crc;
}

static size_t unstuff(const uint8_t *input,
                      size_t input_length,
                      uint8_t *output,
                      size_t output_capacity)
{
    size_t out = 0u;
    for (size_t i = 0u; i < input_length; ++i) {
        if (out >= output_capacity) {
            return 0u;
        }
        output[out++] = input[i];
        if (out >= 3u && output[out - 3u] == 0xFFu &&
            output[out - 2u] == 0xFFu && output[out - 1u] == 0xFDu &&
            i + 1u < input_length && input[i + 1u] == 0xFDu) {
            ++i;
        }
    }
    return out;
}

static size_t stuff(const uint8_t *input,
                    size_t input_length,
                    uint8_t *output,
                    size_t output_capacity)
{
    size_t out = 0u;
    for (size_t i = 0u; i < input_length; ++i) {
        if (out >= output_capacity) {
            return 0u;
        }
        output[out++] = input[i];
        if (i >= 2u && input[i - 2u] == 0xFFu &&
            input[i - 1u] == 0xFFu && input[i] == 0xFDu) {
            if (out >= output_capacity) {
                return 0u;
            }
            output[out++] = 0xFDu;
        }
    }
    return out;
}

bool dxl2_parse_instruction(const uint8_t *packet,
                            size_t packet_length,
                            dxl2_instruction_t *result,
                            uint8_t *unstuffed_body,
                            size_t unstuffed_capacity)
{
    if (packet == NULL || result == NULL || unstuffed_body == NULL ||
        !has_header(packet, packet_length)) {
        return false;
    }

    const size_t encoded_length = (size_t)packet[5] | ((size_t)packet[6] << 8);
    if (encoded_length < 3u || packet_length != 7u + encoded_length) {
        return false;
    }

    const uint16_t packet_crc = (uint16_t)packet[packet_length - 2u] |
                                ((uint16_t)packet[packet_length - 1u] << 8);
    if (dxl2_crc16(packet, packet_length - 2u) != packet_crc) {
        return false;
    }

    const size_t stuffed_body_length = encoded_length - 2u;
    const size_t body_length = unstuff(packet + 7u,
                                       stuffed_body_length,
                                       unstuffed_body,
                                       unstuffed_capacity);
    if (body_length == 0u) {
        return false;
    }

    result->id = packet[4];
    result->instruction = unstuffed_body[0];
    result->parameters = unstuffed_body + 1u;
    result->parameter_count = body_length - 1u;
    return true;
}

size_t dxl2_build_status(uint8_t id,
                         uint8_t error,
                         const uint8_t *parameters,
                         size_t parameter_count,
                         uint8_t *output,
                         size_t output_capacity)
{
    uint8_t body[DXL2_MAX_PACKET];
    uint8_t stuffed_body[DXL2_MAX_PACKET];
    if (output == NULL || parameter_count + 2u > sizeof(body)) {
        return 0u;
    }

    body[0] = DXL2_STATUS_INSTRUCTION;
    body[1] = error;
    for (size_t i = 0u; i < parameter_count; ++i) {
        body[i + 2u] = parameters[i];
    }

    const size_t stuffed_length = stuff(body,
                                        parameter_count + 2u,
                                        stuffed_body,
                                        sizeof(stuffed_body));
    const size_t length_field = stuffed_length + 2u;
    const size_t packet_length = 7u + length_field;
    if (stuffed_length == 0u || length_field > 0xFFFFu ||
        packet_length > output_capacity) {
        return 0u;
    }

    output[0] = 0xFFu;
    output[1] = 0xFFu;
    output[2] = 0xFDu;
    output[3] = 0x00u;
    output[4] = id;
    output[5] = (uint8_t)length_field;
    output[6] = (uint8_t)(length_field >> 8);
    for (size_t i = 0u; i < stuffed_length; ++i) {
        output[7u + i] = stuffed_body[i];
    }

    const uint16_t crc = dxl2_crc16(output, packet_length - 2u);
    output[packet_length - 2u] = (uint8_t)crc;
    output[packet_length - 1u] = (uint8_t)(crc >> 8);
    return packet_length;
}
