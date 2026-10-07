/*
 * Flat C API over the VL53L8CX ULD, for `tof`'s Rust wrapper.
 *
 * Nothing but scalars and arrays crosses this boundary. That is the whole
 * point: `VL53L8CX_Configuration` embeds the platform struct, the firmware
 * staging buffer and the results block, and mirroring it as `repr(C)` in Rust
 * would be a large hand-written struct that must track ST's header forever.
 * Twelve functions taking `u8`/`i16` do not.
 *
 * All functions return 0 on success — the ULD's convention, where 0 is
 * VL53L8CX_STATUS_OK — except `vl8_is_alive` and `vl8_data_ready`, which
 * answer 1/0 (and -1 for a bus error).
 *
 * **One sensor per process.** The configuration is a file-scope static because
 * the ULD wants a stable address for a ~16 KB struct and this daemon drives one
 * sensor. `tof::Sensor` enforces the single instance on the Rust side, so the
 * static cannot be entered twice.
 */

#include <fcntl.h>
#include <stdint.h>
#include <string.h>
#include <unistd.h>

#include "vl53l8cx_api.h"

static VL53L8CX_Configuration dev;
static VL53L8CX_ResultsData results;

int vl8_open(const char *dev_path, uint8_t addr_7bit)
{
    memset(&dev, 0, sizeof(dev));
    dev.platform.address = (uint16_t)(addr_7bit << 1);
    dev.platform.fd = open(dev_path, O_RDWR);
    return dev.platform.fd < 0 ? -1 : 0;
}

void vl8_close(void)
{
    if (dev.platform.fd >= 0) {
        close(dev.platform.fd);
        dev.platform.fd = -1;
    }
}

/* 1 = a live VL53L8CX answers at the configured address. */
int vl8_is_alive(void)
{
    uint8_t alive = 0;
    if (vl53l8cx_is_alive(&dev, &alive)) return 0;
    return alive ? 1 : 0;
}

/* Firmware upload + default config (~90 kB, a few seconds at 400 kHz). */
int vl8_init(void)
{
    return (int)vl53l8cx_init(&dev);
}

int vl8_set_address(uint8_t new_addr_7bit)
{
    return (int)vl53l8cx_set_i2c_address(&dev, (uint16_t)(new_addr_7bit << 1));
}

int vl8_start(uint8_t freq_hz)
{
    uint8_t s = vl53l8cx_set_resolution(&dev, VL53L8CX_RESOLUTION_8X8);
    if (s) return (int)s;
    s = vl53l8cx_set_ranging_frequency_hz(&dev, freq_hz);
    if (s) return (int)s;
    return (int)vl53l8cx_start_ranging(&dev);
}

int vl8_stop(void)
{
    return (int)vl53l8cx_stop_ranging(&dev);
}

/* 1 = a new frame is ready, 0 = not yet, -1 = bus error. */
int vl8_data_ready(void)
{
    uint8_t ready = 0;
    if (vl53l8cx_check_data_ready(&dev, &ready)) return -1;
    return ready ? 1 : 0;
}

/* Copies the 8x8 frame out. dist_mm and status must hold 64 entries each. */
int vl8_get_frame(int16_t *dist_mm, uint8_t *status)
{
    uint8_t s = vl53l8cx_get_ranging_data(&dev, &results);
    if (s) return (int)s;
    memcpy(dist_mm, results.distance_mm, 64 * sizeof(int16_t));
    memcpy(status, results.target_status, 64);
    return 0;
}
