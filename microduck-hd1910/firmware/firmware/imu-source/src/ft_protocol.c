#include "ft_protocol.h"
#include <string.h>

bool ft_parse(const uint8_t *bytes, size_t length, ft_packet_t *out)
{
    if (bytes == NULL || out == NULL || length < 6u || length > FT_MAX_PACKET ||
        bytes[0] != 255u || bytes[1] != 255u || bytes[2] == 255u ||
        bytes[3] < 2u || (size_t)bytes[3] + 4u != length) { return false; }
    uint8_t sum = 0u;
    for (size_t i = 2u; i < length; ++i) { sum = (uint8_t)(sum + bytes[i]); }
    if (sum != 255u) { return false; }
    out->id = bytes[2];
    out->instruction = bytes[4];
    out->parameters = bytes + 5u;
    out->parameter_count = length - 6u;
    return true;
}

size_t ft_build(uint8_t id, uint8_t code, const uint8_t *params, size_t count,
                uint8_t *out, size_t capacity)
{
    if (id == 255u || count > 253u || out == NULL || capacity < count + 6u ||
        (count != 0u && params == NULL)) { return 0u; }
    out[0] = 255u; out[1] = 255u; out[2] = id;
    out[3] = (uint8_t)(count + 2u); out[4] = code;
    if (count != 0u) { memcpy(out + 5u, params, count); }
    uint8_t sum = 0u;
    for (size_t i = 2u; i < count + 5u; ++i) { sum = (uint8_t)(sum + out[i]); }
    out[count + 5u] = (uint8_t)~sum;
    return count + 6u;
}

void ft_stream_reset(ft_stream_t *stream)
{
    /* Retain bytes: the caller parses the completed buffer after resetting. */
    stream->count = 0u; stream->expected = 0u; stream->header_state = 0u;
}

bool ft_stream_push(ft_stream_t *stream, uint8_t byte, uint32_t now_ms)
{
    if ((stream->count != 0u || stream->header_state != 0u) &&
        (uint32_t)(now_ms - stream->last_byte_tick) > 3u) { ft_stream_reset(stream); }
    stream->last_byte_tick = now_ms;
    if (stream->count == 0u) {
        if (stream->header_state < 2u) {
            stream->header_state = (byte == 255u) ? (uint8_t)(stream->header_state + 1u) : 0u;
        } else if (byte != 255u) {
            stream->bytes[0] = 255u; stream->bytes[1] = 255u; stream->bytes[2] = byte;
            stream->count = 3u; stream->header_state = 0u;
        }
        return false;
    }
    if (stream->count >= sizeof(stream->bytes)) { ft_stream_reset(stream); return false; }
    stream->bytes[stream->count++] = byte;
    if (stream->count == 4u) {
        if (byte < 2u) { ft_stream_reset(stream); return false; }
        stream->expected = (size_t)byte + 4u;
    }
    return stream->expected != 0u && stream->count == stream->expected;
}
