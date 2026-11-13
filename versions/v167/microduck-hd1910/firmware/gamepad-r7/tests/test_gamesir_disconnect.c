#define _GNU_SOURCE
#include <assert.h>
#include <fcntl.h>
#include <stdarg.h>
#include <sys/ioctl.h>
#include <sys/types.h>
#include <time.h>
#include <unistd.h>
#include <sys/wait.h>

static ssize_t test_read(int fd, void *buffer, size_t size);
static int test_close(int fd);
static int test_ioctl(int fd, unsigned long request, ...);
static int test_open(const char *path, int flags, ...);

/* Compile the production event/error/reconnect functions into this test.
 * Only hardware discovery, ioctl and fault injection are replaced. */
#define main gamesir_xboxd_main
#define read test_read
#define close test_close
#define ioctl test_ioctl
#define open test_open
#include "../gamesir-xboxd.c"
#undef main
#undef read
#undef close
#undef ioctl
#undef open

static int failing_read_fd = -1;
static int read_error = 0;
static int watched_fd = -1;
static int watched_closes = 0;
static bool fake_consumer_available = false;
static int fake_consumer_template = -1;
static int fake_consumer_fd = -1;
static int discovery_opens = 0;
static int consumer_grabs = 0;

static ssize_t test_read(int fd, void *buffer, size_t size) {
    if (fd == failing_read_fd) {
        errno = read_error;
        return read_error == 0 ? 0 : -1;
    }
    return read(fd, buffer, size);
}

static int test_close(int fd) {
    if (fd == watched_fd)
        watched_closes++;
    return close(fd);
}

static int test_ioctl(int fd, unsigned long request, ...) {
    va_list args;
    va_start(args, request);
    if (request == EVIOCGRAB) {
        int grab = va_arg(args, int);
        if (fd == fake_consumer_fd && grab)
            consumer_grabs++;
        va_end(args);
        return 0;
    }
    if (fd == fake_consumer_fd && request == EVIOCGNAME(256)) {
        char *name = va_arg(args, char *);
        snprintf(name, 256, "%s", CONSUMER_NAME);
        va_end(args);
        return (int)strlen(name);
    }
    va_end(args);
    errno = ENOTTY;
    return -1;
}

static int test_open(const char *path, int flags, ...) {
    (void)flags;
    if (strncmp(path, "/dev/input/event", 16) == 0) {
        discovery_opens++;
        if (fake_consumer_available && strcmp(path, "/dev/input/event3") == 0) {
            fake_consumer_fd = dup(fake_consumer_template);
            return fake_consumer_fd;
        }
    }
    errno = ENOENT;
    return -1;
}


struct fixture {
    int primary[2];
    int auxiliary[2];
    int output[2];
    struct pollfd inputs[2];
};

static void make_fixture(struct fixture *f) {
    assert(pipe2(f->primary, O_NONBLOCK | O_CLOEXEC) == 0);
    assert(pipe2(f->auxiliary, O_NONBLOCK | O_CLOEXEC) == 0);
    assert(pipe2(f->output, O_NONBLOCK | O_CLOEXEC) == 0);
    f->inputs[0] = (struct pollfd){.fd = f->primary[0], .events = POLLIN};
    f->inputs[1] = (struct pollfd){.fd = f->auxiliary[0], .events = POLLIN};
    watched_fd = f->auxiliary[0];
    watched_closes = 0;
    failing_read_fd = -1;
}

static void destroy_fixture(struct fixture *f) {
    failing_read_fd = -1;
    close_consumer_input(&f->inputs[1]);
    close(f->primary[0]);
    if (f->primary[1] >= 0) close(f->primary[1]);
    if (f->auxiliary[1] >= 0) close(f->auxiliary[1]);
    close(f->output[0]);
    close(f->output[1]);
    watched_fd = -1;
}

static void assert_event(const struct input_event *e, int type, int code, int value) {
    assert(e->type == type);
    assert(e->code == code);
    assert(e->value == value);
}

static void test_auxiliary_hup_and_primary_forwarding(void) {
    struct fixture f;
    make_fixture(&f);
    close(f.auxiliary[1]);
    f.auxiliary[1] = -1;
    assert(poll(f.inputs, 2, 20) > 0);
    assert(f.inputs[1].revents & POLLHUP);
    assert(forward_ready_inputs(f.inputs, f.output[1], NULL, 0));
    assert(f.inputs[0].fd == f.primary[0]);
    assert(f.inputs[1].fd == -1);
    assert(fcntl(f.auxiliary[0], F_GETFD) == -1 && errno == EBADF);
    assert(watched_closes == 1);

    /* The old production branch returned immediately forever here. */
    struct timespec before, after;
    assert(clock_gettime(CLOCK_MONOTONIC, &before) == 0);
    assert(poll(f.inputs, 2, 40) == 0);
    assert(clock_gettime(CLOCK_MONOTONIC, &after) == 0);
    double elapsed_ms = (after.tv_sec - before.tv_sec) * 1000.0 +
                        (after.tv_nsec - before.tv_nsec) / 1000000.0;
    assert(elapsed_ms >= 20.0);

    const struct axis_map maps[] = {
        {.src = ABS_X, .dst = ABS_X, .in_min = 0, .in_max = 1023,
         .out_min = -32768, .out_max = 32767},
        {.src = ABS_BRAKE, .dst = ABS_Z, .in_min = 0, .in_max = 100,
         .out_min = 0, .out_max = 255},
        {.src = ABS_GAS, .dst = ABS_RZ, .in_min = 0, .in_max = 100,
         .out_min = 255, .out_max = 0},
    };
    const struct input_event events[] = {
        {.type = EV_KEY, .code = BTN_START, .value = 1},
        {.type = EV_KEY, .code = BTN_TL2, .value = 1},
        {.type = EV_ABS, .code = ABS_X, .value = 1023},
        {.type = EV_ABS, .code = ABS_BRAKE, .value = 100},
        {.type = EV_ABS, .code = ABS_GAS, .value = 0},
        {.type = EV_SYN, .code = SYN_REPORT},
    };
    assert(write(f.primary[1], events, sizeof(events)) == sizeof(events));
    assert(poll(f.inputs, 2, 20) > 0);
    assert(forward_ready_inputs(f.inputs, f.output[1], maps, 3));
    struct input_event output[16];
    assert(read(f.output[0], output, sizeof(output)) == 5 * sizeof(output[0]));
    assert_event(&output[0], EV_KEY, BTN_START, 1);
    assert_event(&output[1], EV_ABS, ABS_X, 32767);
    assert_event(&output[2], EV_ABS, ABS_Z, 255);
    assert_event(&output[3], EV_ABS, ABS_RZ, 255);
    assert_event(&output[4], EV_SYN, SYN_REPORT, 0);
    close_consumer_input(&f.inputs[1]);
    assert(watched_closes == 1);
    destroy_fixture(&f);
    printf("PASS auxiliary HUP removed; next poll waited %.3f ms; "
           "main START/stick/triggers/SYN preserved; no duplicate close\n", elapsed_ms);
}

static void test_primary_hup(void) {
    struct fixture f;
    make_fixture(&f);
    close(f.primary[1]);
    f.primary[1] = -1;
    assert(poll(f.inputs, 2, 20) > 0);
    assert(!forward_ready_inputs(f.inputs, f.output[1], NULL, 0));
    /* Main ownership remains with run_bridge's caller for reconnect cleanup. */
    assert(fcntl(f.primary[0], F_GETFD) >= 0);
    assert(f.inputs[1].fd == f.auxiliary[0]);
    assert(watched_closes == 0);
    destroy_fixture(&f);
    assert(watched_closes == 1);
    puts("PASS primary HUP exits; auxiliary cleanup closes once");
}

static void test_permanent_and_temporary_errors(void) {
    const short poll_errors[] = {POLLERR, POLLNVAL};
    const int permanent_errors[] = {0, ENODEV, EBADF, EIO};
    const int temporary_errors[] = {EAGAIN, EWOULDBLOCK, EINTR};
    for (int source = 0; source < 2; source++) {
        for (size_t i = 0; i < sizeof(poll_errors) / sizeof(poll_errors[0]); i++) {
            struct fixture f;
            make_fixture(&f);
            f.inputs[source].revents = poll_errors[i];
            assert(forward_ready_inputs(f.inputs, f.output[1], NULL, 0) == (source == 1));
            assert(watched_closes == (source == 1 ? 1 : 0));
            assert(source == 0 || f.inputs[1].fd == -1);
            destroy_fixture(&f);
            assert(watched_closes == 1);
        }
        for (size_t i = 0; i < sizeof(permanent_errors) / sizeof(permanent_errors[0]); i++) {
            struct fixture f;
            make_fixture(&f);
            f.inputs[source].revents = POLLIN;
            failing_read_fd = f.inputs[source].fd;
            read_error = permanent_errors[i];
            assert(forward_ready_inputs(f.inputs, f.output[1], NULL, 0) == (source == 1));
            assert(watched_closes == (source == 1 ? 1 : 0));
            assert(source == 0 || f.inputs[1].fd == -1);
            destroy_fixture(&f);
            assert(watched_closes == 1);
        }
        for (size_t i = 0; i < sizeof(temporary_errors) / sizeof(temporary_errors[0]); i++) {
            struct fixture f;
            make_fixture(&f);
            f.inputs[source].revents = POLLIN;
            failing_read_fd = f.inputs[source].fd;
            read_error = temporary_errors[i];
            assert(forward_ready_inputs(f.inputs, f.output[1], NULL, 0));
            assert(f.inputs[0].fd == f.primary[0]);
            assert(f.inputs[1].fd == f.auxiliary[0]);
            assert(watched_closes == 0);
            destroy_fixture(&f);
        }
    }
    puts("PASS both sources: POLLERR/POLLNVAL/EOF/ENODEV/EBADF/EIO; "
         "EAGAIN/EWOULDBLOCK/EINTR preserve descriptors");
}

static void test_consumer_keys_stay_isolated(void) {
    struct fixture f;
    make_fixture(&f);
    const struct input_event events[] = {
        {.type = EV_KEY, .code = KEY_HOMEPAGE, .value = 1},
        {.type = EV_KEY, .code = KEY_VOLUMEUP, .value = 1},
        {.type = EV_SYN, .code = SYN_REPORT},
    };
    assert(write(f.auxiliary[1], events, sizeof(events)) == sizeof(events));
    assert(poll(f.inputs, 2, 20) > 0);
    assert(forward_ready_inputs(f.inputs, f.output[1], NULL, 0));
    struct input_event output[4];
    assert(read(f.output[0], output, sizeof(output)) == sizeof(output[0]));
    assert_event(&output[0], EV_SYN, SYN_REPORT, 0);
    destroy_fixture(&f);
    puts("PASS Consumer HOME/media keys remain excluded from Xbox buttons");
}

static void test_consumer_hotplug_recovers_without_timer_scans(void) {
    int auxiliary[2];
    assert(pipe2(auxiliary, O_NONBLOCK | O_CLOEXEC) == 0);
    fake_consumer_template = auxiliary[0];
    struct pollfd consumer = {.fd = -1, .events = POLLIN};
    reopen_consumer_input(&consumer);
    assert(consumer.fd == -1);
    int attempts = discovery_opens;
    assert(attempts > 0);
    fake_consumer_available = true;
    reopen_consumer_input(&consumer);
    assert(consumer.fd >= 0);
    assert(consumer_grabs == 1);
    attempts = discovery_opens;
    reopen_consumer_input(&consumer);
    assert(discovery_opens == attempts);
    watched_fd = consumer.fd;
    watched_closes = 0;
    close_consumer_input(&consumer);
    close_consumer_input(&consumer);
    assert(watched_closes == 1);
    close(auxiliary[0]);
    close(auxiliary[1]);
    watched_fd = -1;
    puts("PASS auxiliary hotplug reopens/grabs; live auxiliary causes no scans");
}

static void test_real_input_hotplug_waits_and_late_directory(void) {
    char parent[] = "/tmp/duck-input-watch-XXXXXX";
    assert(mkdtemp(parent));
    char directory[256], event[288];
    snprintf(directory, sizeof(directory), "%s/input", parent);
    snprintf(event, sizeof(event), "%s/event9", directory);
    struct input_watch watch;
    assert(start_input_watch(&watch, directory, parent) == 0);
    assert(watch.input < 0);
    assert(mkdir(directory, 0700) == 0);
    assert(wait_input_change(&watch));
    assert(watch.input >= 0);
    struct pollfd fd = {.fd = watch.fd, .events = POLLIN};
    input_changed(&watch);
    int before_opens = discovery_opens;
    assert(poll(&fd, 1, 30) == 0);
    assert(discovery_opens == before_opens);
    pid_t child = fork();
    assert(child >= 0);
    if (!child) {
        struct timespec delay = {.tv_nsec = 40000000};
        nanosleep(&delay, NULL);
        int created = open(event, O_CREAT | O_WRONLY | O_CLOEXEC, 0600);
        if (created < 0) _exit(1);
        close(created);
        _exit(0);
    }
    struct timespec start, stop;
    clock_gettime(CLOCK_MONOTONIC, &start);
    assert(wait_input_change(&watch));
    clock_gettime(CLOCK_MONOTONIC, &stop);
    double elapsed = (stop.tv_sec-start.tv_sec)*1000.0+(stop.tv_nsec-start.tv_nsec)/1000000.0;
    assert(elapsed >= 20.0);
    int status;
    assert(waitpid(child, &status, 0) == child && WIFEXITED(status) && WEXITSTATUS(status) == 0);
    input_changed(&watch);
    assert(chmod(event, 0640) == 0);
    assert(wait_input_change(&watch));
    assert(unlink(event) == 0);
    assert(wait_input_change(&watch));
    assert(rmdir(directory) == 0);
    input_changed(&watch);
    assert(watch.input < 0);
    assert(mkdir(directory, 0700) == 0);
    assert(wait_input_change(&watch));
    assert(watch.input >= 0);
    close(watch.fd);
    assert(rmdir(directory) == 0 && rmdir(parent) == 0);
    puts("PASS actual inotify: idle blocks, late directory, creation/permissions/removal/recreation; no discovery timer");
}

int main(void) {
    test_auxiliary_hup_and_primary_forwarding();
    test_primary_hup();
    test_permanent_and_temporary_errors();
    test_consumer_keys_stay_isolated();
    test_consumer_hotplug_recovers_without_timer_scans();
    test_real_input_hotplug_waits_and_late_directory();
    puts("All GameSir disconnect regressions passed (production C paths, no hardware).");
    return 0;
}
