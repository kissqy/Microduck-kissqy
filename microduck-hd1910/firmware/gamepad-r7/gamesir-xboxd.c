#define _GNU_SOURCE
#include <dirent.h>
#include <errno.h>
#include <fcntl.h>
#include <linux/input.h>
#include <linux/uinput.h>
#include <poll.h>
#include <signal.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/stat.h>
#include <sys/time.h>
#include <time.h>
#include <unistd.h>

#define PAD_NAME "GameSir-Nova 2 Lite"
#define CONSUMER_NAME "GameSir-Nova 2 Lite Consumer Control"
#define XBOX_NAME "Xbox 360 Controller (GameSir Nova 2 Lite)"
#define NBITS(x) ((((x) - 1) / (8 * sizeof(unsigned long))) + 1)

static volatile sig_atomic_t running = 1;

struct axis_map {
    int src;
    int dst;
    int in_min;
    int in_max;
    int out_min;
    int out_max;
};

static void stop_running(int sig) {
    (void)sig;
    running = 0;
}

static bool bit_is_set(const unsigned long *bits, int bit) {
    return (bits[bit / (8 * sizeof(unsigned long))] >>
            (bit % (8 * sizeof(unsigned long)))) & 1UL;
}

static bool has_abs(int fd, int code) {
    unsigned long bits[NBITS(ABS_MAX + 1)];
    memset(bits, 0, sizeof(bits));
    if (ioctl(fd, EVIOCGBIT(EV_ABS, sizeof(bits)), bits) < 0)
        return false;
    return bit_is_set(bits, code);
}

static int find_named_input(const char *wanted, char *path, size_t path_len,
                            bool require_axes) {
    for (int i = 0; i < 96; i++) {
        char candidate[64];
        char name[256] = {0};
        snprintf(candidate, sizeof(candidate), "/dev/input/event%d", i);
        int fd = open(candidate, O_RDONLY | O_NONBLOCK | O_CLOEXEC);
        if (fd < 0)
            continue;
        if (ioctl(fd, EVIOCGNAME(sizeof(name)), name) >= 0 &&
            strcmp(name, wanted) == 0 &&
            (!require_axes || (has_abs(fd, ABS_X) && has_abs(fd, ABS_Y)))) {
            snprintf(path, path_len, "%s", candidate);
            return fd;
        }
        close(fd);
    }
    return -1;
}

static int find_pad(char *path, size_t path_len) {
    return find_named_input(PAD_NAME, path, path_len, true);
}

static int add_axis(int fd, struct axis_map *maps, int *count,
                    int src, int dst, int out_min, int out_max) {
    if (!has_abs(fd, src))
        return 0;
    struct input_absinfo info;
    if (ioctl(fd, EVIOCGABS(src), &info) < 0)
        return -1;
    maps[*count] = (struct axis_map){
        .src = src, .dst = dst,
        .in_min = info.minimum, .in_max = info.maximum,
        .out_min = out_min, .out_max = out_max,
    };
    (*count)++;
    return 0;
}

static int add_trigger_axis(int fd, struct axis_map *maps, int *count,
                            int src, int dst) {
    if (!has_abs(fd, src))
        return 0;
    struct input_absinfo info;
    if (ioctl(fd, EVIOCGABS(src), &info) < 0)
        return -1;

    /* Some Android HID firmwares report an untouched trigger at the maximum
     * end of its range.  Xbox/gilrs expects 0 when released, so infer the
     * direction from the live resting value when the bridge starts. */
    int distance_to_min = abs(info.value - info.minimum);
    int distance_to_max = abs(info.maximum - info.value);
    int out_at_min = distance_to_min <= distance_to_max ? 0 : 255;
    int out_at_max = distance_to_min <= distance_to_max ? 255 : 0;

    maps[*count] = (struct axis_map){
        .src = src, .dst = dst,
        .in_min = info.minimum, .in_max = info.maximum,
        .out_min = out_at_min, .out_max = out_at_max,
    };
    (*count)++;
    return 0;
}

struct candidate_axis {
    int code;
    int center_error;
};

static int axis_center_error(int fd, int code) {
    struct input_absinfo info;
    if (ioctl(fd, EVIOCGABS(code), &info) < 0 || info.maximum <= info.minimum)
        return 1000000;
    int64_t range = (int64_t)info.maximum - info.minimum;
    int64_t from_min = (int64_t)info.value - info.minimum;
    int64_t error = llabs(2 * from_min - range);
    return (int)(error * 1000 / range);
}

static void sort_by_center(struct candidate_axis *axes, int count) {
    for (int i = 0; i < count; i++) {
        for (int j = i + 1; j < count; j++) {
            if (axes[j].center_error < axes[i].center_error) {
                struct candidate_axis tmp = axes[i];
                axes[i] = axes[j];
                axes[j] = tmp;
            }
        }
    }
}

static void sort_codes(int *a, int *b) {
    if (*a > *b) {
        int tmp = *a;
        *a = *b;
        *b = tmp;
    }
}

static int setup_abs(int ufd, int code, int min, int max, int flat) {
    if (ioctl(ufd, UI_SET_ABSBIT, code) < 0)
        return -1;
    struct uinput_abs_setup abs = {0};
    abs.code = code;
    abs.absinfo.minimum = min;
    abs.absinfo.maximum = max;
    abs.absinfo.flat = flat;
    return ioctl(ufd, UI_ABS_SETUP, &abs);
}

static int create_xbox(struct axis_map *maps, int map_count) {
    int ufd = open("/dev/uinput", O_WRONLY | O_NONBLOCK | O_CLOEXEC);
    if (ufd < 0) {
        perror("open /dev/uinput");
        return -1;
    }

    ioctl(ufd, UI_SET_EVBIT, EV_KEY);
    /* Keep this descriptor identical to a normal Linux Xbox 360 pad.
     *
     * In particular, do not advertise BTN_TL2/BTN_TR2 together with the
     * analogue ABS_Z/ABS_RZ triggers.  SDL/gilrs addresses the Xbox buttons
     * by their evdev ordinal: inserting TL2/TR2 would move BTN_TR2 into b7
     * (START), move the real BTN_START into b9 (left-stick click), and make
     * one RT press both chirp and toggle the robot policy. */
    const int keys[] = {
        BTN_SOUTH, BTN_EAST, BTN_NORTH, BTN_WEST,
        BTN_TL, BTN_TR,
        BTN_SELECT, BTN_START, BTN_MODE, BTN_THUMBL, BTN_THUMBR,
    };
    for (size_t i = 0; i < sizeof(keys) / sizeof(keys[0]); i++)
        ioctl(ufd, UI_SET_KEYBIT, keys[i]);

    ioctl(ufd, UI_SET_EVBIT, EV_ABS);
    setup_abs(ufd, ABS_X, -32768, 32767, 128);
    setup_abs(ufd, ABS_Y, -32768, 32767, 128);
    setup_abs(ufd, ABS_RX, -32768, 32767, 128);
    setup_abs(ufd, ABS_RY, -32768, 32767, 128);
    setup_abs(ufd, ABS_Z, 0, 255, 0);
    setup_abs(ufd, ABS_RZ, 0, 255, 0);
    setup_abs(ufd, ABS_HAT0X, -1, 1, 0);
    setup_abs(ufd, ABS_HAT0Y, -1, 1, 0);

    struct uinput_setup setup = {0};
    setup.id.bustype = BUS_USB;
    setup.id.vendor = 0x045e;
    setup.id.product = 0x028e;
    setup.id.version = 0x0114;
    snprintf(setup.name, sizeof(setup.name), "%s", XBOX_NAME);
    if (ioctl(ufd, UI_DEV_SETUP, &setup) < 0 || ioctl(ufd, UI_DEV_CREATE) < 0) {
        perror("create virtual Xbox controller");
        close(ufd);
        return -1;
    }

    (void)maps;
    (void)map_count;
    return ufd;
}

static bool xbox_key(int code) {
    switch (code) {
    case BTN_SOUTH: case BTN_EAST: case BTN_NORTH: case BTN_WEST:
    case BTN_TL: case BTN_TR:
    case BTN_SELECT: case BTN_START: case BTN_MODE:
    case BTN_THUMBL: case BTN_THUMBR:
        return true;
    default:
        return false;
    }
}

static bool consumer_home_key(int code) {
    return code == KEY_HOMEPAGE || code == KEY_HOME || code == KEY_MENU;
}

static int scaled(const struct axis_map *m, int value) {
    if (value < m->in_min) value = m->in_min;
    if (value > m->in_max) value = m->in_max;
    if (m->in_max == m->in_min) return m->out_min;
    int64_t num = (int64_t)(value - m->in_min) * (m->out_max - m->out_min);
    return m->out_min + (int)(num / (m->in_max - m->in_min));
}

static int emit_event(int ufd, unsigned short type, unsigned short code, int value) {
    struct input_event out = {0};
    gettimeofday(&out.time, NULL);
    out.type = type;
    out.code = code;
    out.value = value;
    return write(ufd, &out, sizeof(out)) == (ssize_t)sizeof(out) ? 0 : -1;
}

static int open_consumer_input(void) {
    char path[64] = {0};
    int fd = find_named_input(CONSUMER_NAME, path, sizeof(path), false);
    if (fd >= 0) {
        if (ioctl(fd, EVIOCGRAB, 1) < 0)
            perror("EVIOCGRAB Consumer Control");
        fprintf(stderr, "Consumer Control isolated: %s (not part of Xbox input)\n",
                path);
    }
    return fd;
}

static void close_consumer_input(struct pollfd *input) {
    if (input->fd >= 0) {
        ioctl(input->fd, EVIOCGRAB, 0);
        close(input->fd);
        input->fd = -1;
    }
    input->revents = 0;
}

static int64_t monotonic_ms(void) {
    struct timespec now = {0};
    clock_gettime(CLOCK_MONOTONIC, &now);
    return (int64_t)now.tv_sec * 1000 + now.tv_nsec / 1000000;
}

static void retry_consumer_input(struct pollfd *input, int64_t *next_retry_ms) {
    if (input->fd >= 0)
        return;
    int64_t now = monotonic_ms();
    if (now < *next_retry_ms)
        return;
    /* The main node may produce events continuously, so retry on a clock
     * deadline rather than waiting for poll to time out. */
    *next_retry_ms = now + 1000;
    input->fd = open_consumer_input();
    input->revents = 0;
}

static bool input_disconnected(struct pollfd *input, int source) {
    if (source == 0)
        return false;
    /* A hung-up auxiliary fd stays immediately ready forever.  Remove it
     * without destroying the working main pad or its virtual Xbox device. */
    close_consumer_input(input);
    fprintf(stderr, "Consumer Control disconnected; main gamepad remains active\n");
    return true;
}

static bool forward_ready_inputs(struct pollfd pollfds[2], int ufd,
                                 const struct axis_map *maps, int n) {
    for (int source = 0; source < 2; source++) {
        struct pollfd *input = &pollfds[source];
        if (input->fd < 0)
            continue;
        if (input->revents & (POLLERR | POLLHUP | POLLNVAL)) {
            if (!input_disconnected(input, source))
                return false;
            continue;
        }
        if (!(input->revents & POLLIN))
            continue;
        struct input_event events[32];
        ssize_t got = read(input->fd, events, sizeof(events));
        if (got < 0 && (errno == EINTR || errno == EAGAIN || errno == EWOULDBLOCK))
            continue;
        if (got <= 0) {
            if (!input_disconnected(input, source))
                return false;
            continue;
        }
        size_t count = (size_t)got / sizeof(events[0]);
        for (size_t i = 0; i < count; i++) {
            struct input_event *e = &events[i];
            if (e->type == EV_SYN && e->code == SYN_REPORT) {
                emit_event(ufd, EV_SYN, SYN_REPORT, 0);
            } else if (source == 1 && e->type == EV_KEY &&
                       consumer_home_key(e->code)) {
                /* Consumer-media keys are not gamepad START.  The real
                 * three-line menu key arrives as BTN_START on the main node. */
                if (e->value == 1)
                    fprintf(stderr, "ignored Consumer Control HOME event\n");
            } else if (source == 1 && e->type == EV_KEY && e->value == 1) {
                fprintf(stderr, "unmapped Consumer Control key code=%u\n", e->code);
            } else if (source == 0 && e->type == EV_KEY && xbox_key(e->code)) {
                /* TL2/TR2 are deliberately excluded.  Their analogue
                 * values are emitted below as ABS_Z/ABS_RZ, exactly as a
                 * normal Xbox 360 controller exposes its triggers. */
                emit_event(ufd, EV_KEY, e->code, e->value);
            } else if (source == 0 && e->type == EV_ABS) {
                for (int j = 0; j < n; j++) {
                    if (maps[j].src == e->code)
                        emit_event(ufd, EV_ABS, maps[j].dst,
                                   scaled(&maps[j], e->value));
                }
            }
        }
    }
    return true;
}

static int run_bridge(int pfd, const char *path) {
    struct axis_map maps[12];
    int n = 0;

    add_axis(pfd, maps, &n, ABS_X, ABS_X, -32768, 32767);
    add_axis(pfd, maps, &n, ABS_Y, ABS_Y, -32768, 32767);

    bool brake_gas_triggers = has_abs(pfd, ABS_BRAKE) && has_abs(pfd, ABS_GAS);
    int secondary_codes[] = {ABS_Z, ABS_RX, ABS_RY, ABS_RZ};
    struct candidate_axis candidates[4];
    int candidate_count = 0;
    for (size_t i = 0; i < sizeof(secondary_codes) / sizeof(secondary_codes[0]); i++) {
        int code = secondary_codes[i];
        if (has_abs(pfd, code)) {
            candidates[candidate_count++] = (struct candidate_axis){
                .code = code,
                .center_error = axis_center_error(pfd, code),
            };
        }
    }

    int right_x = -1, right_y = -1, left_trigger = -1, right_trigger = -1;
    if (brake_gas_triggers) {
        /* Android's named brake/gas axes are unambiguous.  Among the remaining
         * axes, use the two resting closest to their centre as the right stick. */
        sort_by_center(candidates, candidate_count);
        if (candidate_count >= 2) {
            right_x = candidates[0].code;
            right_y = candidates[1].code;
            sort_codes(&right_x, &right_y);
        }
    } else if (candidate_count >= 4) {
        /* The 3537:100e generic HID descriptor exposes four anonymous secondary
         * axes.  Sticks rest in the middle; triggers rest at an endpoint.  This
         * detects the actual live layout instead of guessing RX/RY vs Z/RZ. */
        sort_by_center(candidates, candidate_count);
        right_x = candidates[0].code;
        right_y = candidates[1].code;
        left_trigger = candidates[2].code;
        right_trigger = candidates[3].code;
        sort_codes(&right_x, &right_y);
        sort_codes(&left_trigger, &right_trigger);

        /* GameSir's generic HID order follows its SDL layout: the lower-numbered
         * endpoint axis is RT and the higher-numbered one is LT. */
        int tmp = left_trigger;
        left_trigger = right_trigger;
        right_trigger = tmp;
    } else if (candidate_count >= 2) {
        /* Conventional xpad-compatible fallback: Z/RZ are LT/RT. */
        sort_by_center(candidates, candidate_count);
        left_trigger = candidates[candidate_count - 2].code;
        right_trigger = candidates[candidate_count - 1].code;
        sort_codes(&left_trigger, &right_trigger);
    }

    if (right_x >= 0 && right_y >= 0) {
        add_axis(pfd, maps, &n, right_x, ABS_RX, -32768, 32767);
        add_axis(pfd, maps, &n, right_y, ABS_RY, -32768, 32767);
    }

    if (brake_gas_triggers) {
        add_trigger_axis(pfd, maps, &n, ABS_BRAKE, ABS_Z);
        add_trigger_axis(pfd, maps, &n, ABS_GAS, ABS_RZ);
    } else if (left_trigger >= 0 && right_trigger >= 0) {
        add_trigger_axis(pfd, maps, &n, left_trigger, ABS_Z);
        add_trigger_axis(pfd, maps, &n, right_trigger, ABS_RZ);
    }
    fprintf(stderr,
            "axis map: right-stick=%d/%d LT=%d RT=%d (ABS codes)\n",
            right_x, right_y,
            brake_gas_triggers ? ABS_BRAKE : left_trigger,
            brake_gas_triggers ? ABS_GAS : right_trigger);
    add_axis(pfd, maps, &n, ABS_HAT0X, ABS_HAT0X, -1, 1);
    add_axis(pfd, maps, &n, ABS_HAT0Y, ABS_HAT0Y, -1, 1);

    int ufd = create_xbox(maps, n);
    if (ufd < 0)
        return -1;

    if (ioctl(pfd, EVIOCGRAB, 1) < 0)
        perror("EVIOCGRAB");

    int cfd = open_consumer_input();
    if (cfd < 0) {
        fprintf(stderr, "HOME source absent: %s not found\n", CONSUMER_NAME);
    }

    fprintf(stderr, "GameSir Xbox bridge active: %s -> %s\n", path, XBOX_NAME);
    struct pollfd pollfds[2] = {
        {.fd = pfd, .events = POLLIN},
        {.fd = cfd, .events = POLLIN},
    };
    int64_t next_consumer_retry_ms = monotonic_ms() + 1000;
    while (running) {
        retry_consumer_input(&pollfds[1], &next_consumer_retry_ms);
        int pr = poll(pollfds, 2, 1000);
        if (pr < 0) {
            if (errno == EINTR) continue;
            break;
        }
        if (pr == 0) continue;
        bool had_consumer = pollfds[1].fd >= 0;
        if (!forward_ready_inputs(pollfds, ufd, maps, n))
            break;
        if (had_consumer && pollfds[1].fd < 0)
            next_consumer_retry_ms = monotonic_ms() + 1000;
    }

    ioctl(pfd, EVIOCGRAB, 0);
    close_consumer_input(&pollfds[1]);
    ioctl(ufd, UI_DEV_DESTROY);
    close(ufd);
    return 0;
}

int main(void) {
    signal(SIGINT, stop_running);
    signal(SIGTERM, stop_running);
    fprintf(stderr, "waiting for %s over Bluetooth\n", PAD_NAME);

    while (running) {
        char path[64] = {0};
        int pfd = find_pad(path, sizeof(path));
        if (pfd < 0) {
            sleep(1);
            continue;
        }
        run_bridge(pfd, path);
        close(pfd);
        if (running) {
            fprintf(stderr, "GameSir disconnected; waiting for it to return\n");
            sleep(1);
        }
    }
    return 0;
}
