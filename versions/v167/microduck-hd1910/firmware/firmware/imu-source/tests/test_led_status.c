#include <assert.h>
#include <stdint.h>
#include <stdio.h>

#include "ft_led_status.h"

int main(void)
{
    ft_led_status_t state;
    ft_led_status_init(&state, 100u);

    assert(ft_led_status_output(&state, 1099u) == FT_LED_OFF);
    assert(ft_led_status_output(&state, 1100u) == FT_LED_FAULT);

    ft_led_status_note_quaternion(&state, 1101u);
    assert(ft_led_status_output(&state, 1101u) == FT_LED_OFF);
    ft_led_status_note_response(&state, 1101u);
    assert(ft_led_status_output(&state, 1101u) == FT_LED_ACTIVITY);
    assert(ft_led_status_output(&state, 1105u) == FT_LED_ACTIVITY);
    assert(ft_led_status_output(&state, 1106u) == FT_LED_OFF);

    /* No 500 ms throttle: every response can start a new short pulse. */
    ft_led_status_note_response(&state, 1121u);
    assert(ft_led_status_output(&state, 1121u) == FT_LED_ACTIVITY);
    assert(ft_led_status_output(&state, 1126u) == FT_LED_OFF);
    assert(ft_led_status_output(&state, 1601u) == FT_LED_FAULT);
    ft_led_status_note_response(&state, 1601u);
    assert(ft_led_status_output(&state, 1601u) == FT_LED_FAULT);

    ft_led_status_note_quaternion(&state, 1602u);
    ft_led_status_note_response(&state, 1602u);
    assert(ft_led_status_output(&state, 1602u) == FT_LED_ACTIVITY);

    ft_led_status_init(&state, UINT32_MAX - 100u);
    ft_led_status_note_quaternion(&state, UINT32_MAX - 50u);
    assert(ft_led_status_output(&state, 448u) == FT_LED_OFF);
    assert(ft_led_status_output(&state, 449u) == FT_LED_FAULT);

    puts("Feetech LED health/activity tests PASS");
    return 0;
}
