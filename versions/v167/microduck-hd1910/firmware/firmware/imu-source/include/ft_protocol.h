#ifndef FT_PROTOCOL_H
#define FT_PROTOCOL_H
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define FT_MAX_PACKET 259u
#define FT_BROADCAST 254u
typedef struct {
    uint8_t id, instruction;
    const uint8_t *parameters;
    size_t parameter_count;
} ft_packet_t;
typedef struct {
    uint8_t bytes[FT_MAX_PACKET];
    size_t count, expected;
    uint8_t header_state;
    uint32_t last_byte_tick;
} ft_stream_t;

bool ft_parse(const uint8_t *bytes, size_t length, ft_packet_t *out);
size_t ft_build(uint8_t id, uint8_t code, const uint8_t *params, size_t count,
                uint8_t *out, size_t capacity);
void ft_stream_reset(ft_stream_t *stream);
bool ft_stream_push(ft_stream_t *stream, uint8_t byte, uint32_t now_ms);
#endif
