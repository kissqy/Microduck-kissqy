#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "ft_fast_sync.h"

int main(void)
{
    uint8_t request[FT_MAX_PACKET];
    const uint8_t sync_parameters[] = {
        FT_IMU_SYNC_ADDRESS, FT_IMU_SYNC_LENGTH, FT_IMU_ID, 1u, 2u
    };
    size_t request_length = ft_build(
        FT_BROADCAST, 0x82u, sync_parameters, sizeof(sync_parameters),
        request, sizeof(request));
    assert(request_length == 11u);
    assert(ft_fast_sync_request_matches(request, request_length));

    ft_fast_sync_detector_t detector = {0};
    for (size_t i = 0u; i < request_length; ++i) {
        assert(ft_fast_sync_detector_push(&detector, request[i], 0u) ==
               (i + 1u == request_length));
    }

    /* Final robot request: IMU first, followed by all 15 joint IDs. */
    const uint8_t full_robot_parameters[] = {
        FT_IMU_SYNC_ADDRESS, FT_IMU_SYNC_LENGTH, FT_IMU_ID,
        20u, 21u, 22u, 23u, 24u,
        30u, 31u, 32u, 33u, 34u,
        10u, 11u, 12u, 13u, 14u
    };
    request_length = ft_build(
        FT_BROADCAST, 0x82u, full_robot_parameters,
        sizeof(full_robot_parameters), request, sizeof(request));
    assert(request_length == 24u);
    assert(ft_fast_sync_request_matches(request, request_length));
    for (size_t i = 0u; i < request_length; ++i) {
        assert(ft_fast_sync_detector_push(&detector, request[i], 0u) ==
               (i + 1u == request_length));
    }

    request_length = ft_build(
        FT_BROADCAST, 0x82u, sync_parameters, sizeof(sync_parameters),
        request, sizeof(request));

    request[request_length - 1u] ^= 1u;
    assert(!ft_fast_sync_request_matches(request, request_length));
    for (size_t i = 0u; i < request_length; ++i) {
        assert(!ft_fast_sync_detector_push(&detector, request[i], 1u));
    }
    request[request_length - 1u] ^= 1u;

    uint8_t parameters[sizeof(sync_parameters)];
    memcpy(parameters, sync_parameters, sizeof(parameters));
    parameters[2] = 1u;
    parameters[3] = FT_IMU_ID;
    request_length = ft_build(FT_BROADCAST, 0x82u, parameters,
                              sizeof(parameters), request, sizeof(request));
    assert(!ft_fast_sync_request_matches(request, request_length));

    /* A timed-out partial frame must not hide the next valid request. */
    ft_fast_sync_detector_reset(&detector);
    for (size_t i = 0u; i < 5u; ++i) {
        assert(!ft_fast_sync_detector_push(&detector, request[i], 10u));
    }
    request_length = ft_build(
        FT_BROADCAST, 0x82u, sync_parameters, sizeof(sync_parameters),
        request, sizeof(request));
    for (size_t i = 0u; i < request_length; ++i) {
        assert(ft_fast_sync_detector_push(&detector, request[i], 20u) ==
               (i + 1u == request_length));
    }
    parameters[2] = FT_IMU_ID;
    parameters[0] = FT_IMU_ADDRESS;
    request_length = ft_build(FT_BROADCAST, 0x82u, parameters,
                              sizeof(parameters), request, sizeof(request));
    assert(!ft_fast_sync_request_matches(request, request_length));
    parameters[0] = FT_IMU_SYNC_ADDRESS;
    parameters[1] = FT_IMU_SYNC_LENGTH - 1u;
    request_length = ft_build(FT_BROADCAST, 0x82u, parameters,
                              sizeof(parameters), request, sizeof(request));
    assert(!ft_fast_sync_request_matches(request, request_length));

    ft_imu_state_t state;
    ft_imu_init(&state);
    ft_fast_sync_response_t fast;
    ft_fast_sync_response_prepare(&fast, &state);
    ft_fast_sync_response_finalize(&fast, 0u, &state);
    ft_packet_t parsed;
    assert(sizeof(fast.bytes) == 21u);
    assert(ft_parse(fast.bytes, sizeof(fast.bytes), &parsed));
    assert(parsed.parameter_count == 15u);
    assert(parsed.parameters[13] == FT_IMU_NOT_READY && parsed.parameters[14] == 0u);
    const uint8_t live[12] = {0x34,0x12,0xfe,0xff,0x55,0xaa,0,0x30,0,0x38,0,0xb0};
    const uint8_t valid_parameters[] = {56u,15u,200u,20u,21u};
    request_length = ft_build(254u,0x82u,valid_parameters,sizeof(valid_parameters),request,sizeof(request));
    uint8_t normal[FT_MAX_PACKET];
    /* Compare ISR and normal READ/SYNC serializers through byte and timer wrap,
     * including stale cached snapshots whose main-loop publication has stopped. */
    const uint32_t times[] = {0u, 9u, 30u, 31u, 65536u};
    const uint32_t sequences[] = {1u, 255u, 256u, UINT32_MAX, 0u};
    for (size_t i=0u;i<sizeof(sequences)/sizeof(sequences[0]);++i) {
        for (size_t j=0u;j<sizeof(times)/sizeof(times[0]);++j) {
            ft_imu_set(&state,live,true,UINT32_MAX-5u);
            state.sequence=sequences[i];
            state.read_before=true;
            state.last_read_sequence=state.sequence-2u;
            const uint32_t now=state.last_quaternion_ms+times[j];
            ft_fast_sync_response_prepare(&fast,&state);
            ft_fast_sync_response_finalize(&fast,now,&state);
            assert(ft_parse(fast.bytes,sizeof(fast.bytes),&parsed));
            assert(parsed.parameters[12] == (uint8_t)state.sequence);
            assert(parsed.parameters[13] == (times[j] > 30u ? FT_IMU_STALE : 0u));
            const size_t n=ft_imu_handle(&state,request,request_length,normal,sizeof(normal),now);
            assert(n==sizeof(fast.bytes) && memcmp(normal,fast.bytes,n)==0);
        }
    }
    ft_imu_set(&state,live,true,100u);
    ft_fast_sync_response_prepare(&fast,&state);
    ft_imu_note_read(&state,state.sequence-5u);
    ft_fast_sync_response_finalize(&fast,109u,&state);
    assert(ft_parse(fast.bytes,sizeof(fast.bytes),&parsed));
    assert(parsed.parameters[13] == FT_IMU_READER_SLOW);
    ft_imu_note_read(&state,fast.sequence);
    ft_fast_sync_response_finalize(&fast,131u,&state);
    assert(ft_parse(fast.bytes,sizeof(fast.bytes),&parsed));
    assert(parsed.parameters[13] == FT_IMU_STALE); /* no republish required */
    puts("FT6 compact IRQ/normal parity, stale cache, wrap and checksum tests PASS");
    return 0;
}
