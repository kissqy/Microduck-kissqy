#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "ft_imu.h"

static ft_imu_state_t state;
static uint8_t request[FT_MAX_PACKET], response[FT_MAX_PACKET];
static size_t call(uint8_t id, uint8_t code, const uint8_t *p, size_t n, uint32_t time)
{
    const size_t length = ft_build(id, code, p, n, request, sizeof(request));
    assert(length != 0u);
    return ft_imu_handle(&state, request, length, response, sizeof(response), time);
}

int main(void)
{
    ft_imu_init(&state);
    ft_packet_t parsed;
    size_t n = call(200u, 1u, NULL, 0u, 0u);
    assert(n == 6u && ft_parse(response, n, &parsed) && parsed.instruction == 0u);
    const uint8_t version[] = {0u, 2u};
    n = call(200u, 2u, version, sizeof(version), 0u);
    assert(n == 8u && response[5] == 6u && response[6] == 0u);
    const uint8_t identity[] = {3u, 2u};
    n = call(200u, 2u, identity, sizeof(identity), 0u);
    assert(n == 8u && response[5] == 0u && response[6] == 0xf2u);
    const uint8_t data_range[] = {124u, 20u};
    n = call(200u, 2u, data_range, sizeof(data_range), 0u);
    assert(n == 26u && response[21] == 255u && response[22] == 255u);
    assert(response[23] == 0u && response[24] == 1u);
    assert(state.data_read_count == 1u);

    const uint8_t live[12] = {0x34,0x12,0xfe,0xff,0x55,0xaa,0,0x30,0,0x38,0,0xb0};
    ft_imu_set(&state, live, true, 100u);
    n = call(200u, 2u, data_range, sizeof(data_range), 109u);
    assert(ft_parse(response, n, &parsed) && parsed.parameter_count == 20u);
    assert(memcmp(parsed.parameters, live, 12u) == 0);
    assert(parsed.parameters[12] == 1u && parsed.parameters[16] == 9u && parsed.parameters[18] == 1u);
    ft_imu_set(&state, live, false, 200u);
    assert(state.sequence == 1u && state.last_quaternion_ms == 100u);
    state.sequence = UINT32_MAX;
    ft_imu_set(&state, live, true, UINT32_MAX - 5u);
    n = call(200u, 2u, data_range, sizeof(data_range), 4u);
    assert(state.sequence == 0u && response[21] == 10u);
    n = call(200u, 2u, data_range, sizeof(data_range), 100000u);
    assert(response[21] == 255u && response[22] == 255u);

    const uint8_t short_range[] = {124u, 12u};
    assert(call(200u, 2u, short_range, sizeof(short_range), 0u) == 18u);
    const uint8_t first[] = {124u,20u,200u,1u,2u};
    assert(call(254u,0x82u,first,sizeof(first),0u) == 26u);
    const uint8_t sync_alias[] = {56u,15u,200u,1u,2u};
    ft_imu_set(&state,live,true,100u);
    n = call(254u,0x82u,sync_alias,sizeof(sync_alias),109u);
    assert(n == 21u && ft_parse(response,n,&parsed));
    assert(parsed.parameter_count == 15u);
    assert(memcmp(parsed.parameters,live,12u) == 0);
    assert(parsed.parameters[12] == 1u && parsed.parameters[13] == 0u && parsed.parameters[14] == 0u);
    const uint8_t direct_alias[] = {56u,15u};
    n = call(200u,2u,direct_alias,sizeof(direct_alias),130u);
    assert(n == 21u && ft_parse(response,n,&parsed));
    assert(parsed.parameters[13] == 0u); /* 30 ms freshness boundary. */
    n = call(200u,2u,direct_alias,sizeof(direct_alias),131u);
    assert(ft_parse(response,n,&parsed) && parsed.parameters[13] == FT_IMU_STALE);
    state.sequence = 255u;
    ft_imu_set(&state, live, true, 132u);
    n = call(200u,2u,direct_alias,sizeof(direct_alias),132u);
    assert(ft_parse(response,n,&parsed) && parsed.parameters[12] == 0u);
    /* Old 56/20 must fail, not silently return a truncated/new-layout block. */
    const uint8_t old_layout[] = {56u,20u};
    assert(call(200u,2u,old_layout,sizeof(old_layout),132u) == 6u && response[4] == 8u);
    const uint8_t later[] = {124u,20u,1u,200u};
    assert(call(254u,0x82u,later,sizeof(later),0u) == 0u);
    const uint8_t crossing_alias[] = {55u,20u};
    assert(call(200u,2u,crossing_alias,sizeof(crossing_alias),0u) == 6u &&
           response[4] == 8u);
    assert(call(1u,2u,data_range,sizeof(data_range),0u) == 0u);
    assert(call(254u,1u,NULL,0u,0u) == 0u);
    const uint8_t write_id[] = {5u,1u};
    assert(call(200u,3u,write_id,sizeof(write_id),0u) == 6u && response[4] == 0x40u);
    assert(call(254u,3u,write_id,sizeof(write_id),0u) == 0u);
    const uint8_t wrong[] = {143u,2u};
    assert(call(200u,2u,wrong,sizeof(wrong),0u) == 6u && response[4] == 8u);

    n = ft_build(200u,2u,data_range,2u,request,sizeof(request));
    request[n-1u] ^= 1u;
    assert(!ft_parse(request,n,&parsed));
    assert(ft_imu_handle(&state,request,n,response,sizeof(response),0u) == 0u);
    const uint8_t dxl[] = {255u,255u,253u,0u,200u,3u,0u,1u,0u,0u};
    assert(!ft_parse(dxl,sizeof(dxl),&parsed));
    assert(ft_build(200u,0u,live,12u,response,17u) == 0u);

    /* 15 servo command rows, stream length 128: the IMU must stay silent. */
    uint8_t rows[122] = {41u,7u};
    for (size_t i = 0u; i < 15u; ++i) { rows[2u + 8u*i] = (uint8_t)(i+1u); }
    n = ft_build(254u,0x83u,rows,sizeof(rows),request,sizeof(request));
    assert(n == 128u);
    ft_stream_t stream = {0};
    for (size_t i = 0u; i < n; ++i) { assert(ft_stream_push(&stream,request[i],0u) == (i+1u == n)); }
    assert(ft_imu_handle(&state,stream.bytes,stream.count,response,sizeof(response),0u) == 0u);
    ft_stream_reset(&stream);
    for (size_t i = 0u; i < sizeof(dxl); ++i) { (void)ft_stream_push(&stream,dxl[i],1u); }
    n = ft_build(200u,1u,NULL,0u,request,sizeof(request));
    for (size_t i = 0u; i < n; ++i) { assert(ft_stream_push(&stream,request[i],10u) == (i+1u == n)); }
    assert(ft_parse(stream.bytes,stream.count,&parsed));
    puts("Feetech protocol/IMU/stream tests PASS");
    return 0;
}
