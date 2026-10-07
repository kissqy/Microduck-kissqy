#include "ft_led_status.h"

static bool elapsed(uint32_t now_ms, uint32_t since_ms, uint32_t interval_ms)
{
    return (uint32_t)(now_ms - since_ms) >= interval_ms;
}

static bool imu_fault(const ft_led_status_t *state, uint32_t now_ms)
{
    if (!state->have_quaternion) {
        return elapsed(now_ms, state->started_ms,
                       FT_LED_FIRST_DATA_TIMEOUT_MS);
    }
    return elapsed(now_ms, state->last_quaternion_ms,
                   FT_LED_IMU_STALE_TIMEOUT_MS);
}

void ft_led_status_init(ft_led_status_t *state, uint32_t now_ms)
{
    state->started_ms = now_ms;
    state->last_quaternion_ms = now_ms;
    state->activity_started_ms = now_ms;
    state->have_quaternion = false;
    state->activity_active = false;
}

void ft_led_status_note_quaternion(ft_led_status_t *state, uint32_t now_ms)
{
    state->last_quaternion_ms = now_ms;
    state->have_quaternion = true;
}

void ft_led_status_note_response(ft_led_status_t *state, uint32_t now_ms)
{
    if (imu_fault(state, now_ms)) {
        return;
    }
    state->activity_started_ms = now_ms;
    state->activity_active = true;
}

ft_led_output_t ft_led_status_output(ft_led_status_t *state, uint32_t now_ms)
{
    if (imu_fault(state, now_ms)) {
        state->activity_active = false;
        return FT_LED_FAULT;
    }
    if (state->activity_active &&
        !elapsed(now_ms, state->activity_started_ms,
                 FT_LED_ACTIVITY_PULSE_MS)) {
        return FT_LED_ACTIVITY;
    }
    state->activity_active = false;
    return FT_LED_OFF;
}
