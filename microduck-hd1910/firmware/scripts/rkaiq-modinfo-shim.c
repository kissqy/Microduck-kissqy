/* LD_PRELOAD shim for rkaiq_3A_server on the Radxa Zero 3W (RK3566).
 *
 * librkaiq queries the sensor driver's module info (sensor / module / lens
 * names, used to pick the IQ tuning file in /etc/iqfiles) through the
 * RKMODULE_GET_MODULE_INFO private ioctl. The ioctl number encodes
 * sizeof(struct rkmodule_inf), which drifts between BSP kernel versions —
 * the Radxa camera-engine-rkaiq deb was built against different headers
 * than the Armbian vendor kernel (5203 vs 5207 bytes on 6.1.115), so the
 * ioctl fails with ENOTTY, librkaiq silently ends up with an empty IQ file
 * name ("/etc/iqfiles//") and segfaults.
 *
 * This shim intercepts the mismatched ioctl (type 'V', nr 0xc0 = private 0),
 * probes the kernel's expected struct size once by brute force, performs the
 * call with the kernel's own ioctl number, and copies back the base info
 * (first 96 bytes: sensor[32] + module[32] + lens[32]) which is all librkaiq
 * reads for IQ file selection.
 *
 * Build:   gcc -shared -fPIC -O2 -o rkaiq_modinfo_shim.so rkaiq-modinfo-shim.c -ldl
 * Install: see scripts/setup-rkaiq.sh, which builds it on the board because it
 *          must be aarch64 — and for no other reason. The struct size is a
 *          property of the running kernel, but this probes for it at *runtime*
 *          on the first intercepted ioctl, so the object does not depend on the
 *          kernel it was compiled against and setup-rkaiq.sh only rebuilds it
 *          when the source changes. The systemd drop-in
 *          sets LD_PRELOAD for the rkaiq_3A service alone; nothing else on the
 *          board has this ioctl intercepted.
 *
 * Carried here from the prototype (microduck_runtime/radxa_setup) unchanged in
 * substance: it is the only thing that makes the Radxa engine deb run on the
 * Armbian vendor kernel, and it was arrived at by finding the byte count.
 */
#define _GNU_SOURCE
#include <string.h>
#include <dlfcn.h>
#include <stdarg.h>
#include <sys/ioctl.h>

#define MODINFO_TYPE 0x56 /* 'V' */
#define MODINFO_NR   0xc0 /* BASE_VIDIOC_PRIVATE + 0 */

static int (*real_ioctl)(int, unsigned long, ...);

/* Find the ioctl number the running kernel accepts for GET_MODULE_INFO by
 * scanning candidate struct sizes. Runs once; ~10k failing syscalls ≈ 10 ms. */
static unsigned long probe_kernel_req(int fd) {
    static unsigned long cached;
    if (cached) return cached;
    static char buf[16384];
    for (unsigned sz = 96; sz < sizeof(buf); sz++) {
        unsigned long req = _IOC(_IOC_READ, MODINFO_TYPE, MODINFO_NR, sz);
        if (real_ioctl(fd, req, buf) == 0) {
            cached = req;
            return req;
        }
    }
    return 0;
}

int ioctl(int fd, unsigned long req, ...) {
    if (!real_ioctl) real_ioctl = dlsym(RTLD_NEXT, "ioctl");
    va_list ap; va_start(ap, req); void *arg = va_arg(ap, void*); va_end(ap);

    if (_IOC_TYPE(req) == MODINFO_TYPE && _IOC_NR(req) == MODINFO_NR
        && _IOC_DIR(req) == _IOC_READ) {
        unsigned long kreq = probe_kernel_req(fd);
        if (kreq != 0 && kreq != req) {
            static char kbuf[16384];
            memset(kbuf, 0, sizeof(kbuf));
            int r = real_ioctl(fd, kreq, kbuf);
            if (r == 0 && arg) {
                unsigned sz = _IOC_SIZE(req);
                memset(arg, 0, sz);
                memcpy(arg, kbuf, sz < 96 ? sz : 96);
            }
            return r;
        }
    }
    return real_ioctl(fd, req, arg);
}
