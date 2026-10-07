#ifndef FT_LED_STATUS_H
#define FT_LED_STATUS_H

#include <stdbool.h>
#include <stdint.h>

#define FT_LED_FIRST_DATA_TIMEOUT_MS 1000u
#define FT_LED_IMU_STALE_TIMEOUT_MS   500u
#define FT_LED_ACTIVITY_PULSE_MS        5u

typedef enum {
    FT_LED_OFF = 0,
    FT_LED_ACTIVITY,
    FT_LED_FAULT
} ft_led_output_t;

typedef struct {
    uint32_t started_ms;
    uint32_t last_quaternion_ms;
    uint32_t activity_started_ms;
    bool have_quaternion;
    bool activity_active;
} ft_led_status_t;

void ft_led_status_init(ft_led_status_t *state, uint32_t now_ms);
void ft_led_status_note_quaternion(ft_led_status_t *state, uint32_t now_ms);
void ft_led_status_note_response(ft_led_status_t *state, uint32_t now_ms);
ft_led_output_t ft_led_status_output(ft_led_status_t *state, uint32_t now_ms);

#endif
