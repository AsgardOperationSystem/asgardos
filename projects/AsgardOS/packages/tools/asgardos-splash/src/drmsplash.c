#include <fcntl.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <sys/ioctl.h>
#include <sys/mman.h>
#include <unistd.h>
#include <drm/drm.h>
#include <drm/drm_mode.h>
#include "fbsplash.h"

/* drm_init: draw through KMS on the largest connected panel only, with a buffer of its own size, and switch
 * the other panels off. The fbdev console is mirrored to every panel at the size they all share (the AYN
 * Thor's bottom panel, 1080x1240), so on the bigger top panel a framebuffer splash covered only part of it and
 * could not be centred. KMS state lasts while the fd is open: for long-running modes (--animate) only.
 * Returns NULL (callers fall back to /dev/fb0) when there is no DRM device or no master. */
#define MAXN 16

static int conn_crtc(int fd, uint32_t encoder_id, const uint32_t *crtcs, uint32_t ncrtcs) {
    struct drm_mode_get_encoder enc = {.encoder_id = encoder_id};
    if (!encoder_id || ioctl(fd, DRM_IOCTL_MODE_GETENCODER, &enc))
        return 0;
    if (enc.crtc_id)
        return enc.crtc_id;
    for (uint32_t i = 0; i < ncrtcs; i++)
        if (enc.possible_crtcs & (1u << i))
            return crtcs[i];
    return 0;
}

Framebuffer *drm_init(void) {
    int fd = open("/dev/dri/card0", O_RDWR | O_CLOEXEC);
    if (fd < 0)
        return NULL;
    ioctl(fd, DRM_IOCTL_SET_MASTER, 0);   /* the first opener is master anyway; SETCRTC below fails without */

    uint32_t conns[MAXN], crtcs[MAXN], encs[MAXN];
    struct drm_mode_card_res res = {0};
    if (ioctl(fd, DRM_IOCTL_MODE_GETRESOURCES, &res))
        goto fail;
    if (res.count_connectors > MAXN) res.count_connectors = MAXN;
    if (res.count_crtcs > MAXN) res.count_crtcs = MAXN;
    if (res.count_encoders > MAXN) res.count_encoders = MAXN;
    res.count_fbs = 0;
    res.connector_id_ptr = (uintptr_t)conns;
    res.crtc_id_ptr = (uintptr_t)crtcs;
    res.encoder_id_ptr = (uintptr_t)encs;
    if (ioctl(fd, DRM_IOCTL_MODE_GETRESOURCES, &res))
        goto fail;

    struct drm_mode_modeinfo best_mode = {0};
    uint32_t best_conn = 0, best_enc = 0, area = 0;
    uint32_t other_enc[MAXN], nother = 0;
    for (uint32_t i = 0; i < res.count_connectors; i++) {
        struct drm_mode_get_connector c = {.connector_id = conns[i]};
        if (ioctl(fd, DRM_IOCTL_MODE_GETCONNECTOR, &c) || c.connection != 1 || !c.count_modes)
            continue;
        struct drm_mode_modeinfo *modes = calloc(c.count_modes, sizeof *modes);
        if (!modes)
            continue;
        c.modes_ptr = (uintptr_t)modes;
        c.count_props = c.count_encoders = 0;
        c.props_ptr = c.prop_values_ptr = c.encoders_ptr = 0;
        if (!ioctl(fd, DRM_IOCTL_MODE_GETCONNECTOR, &c) && c.count_modes) {
            const uint32_t a = (uint32_t)modes[0].hdisplay * modes[0].vdisplay;   /* modes[0]: preferred */
            if (a > area) {
                if (best_enc && nother < MAXN)
                    other_enc[nother++] = best_enc;
                area = a, best_mode = modes[0], best_conn = conns[i], best_enc = c.encoder_id;
            } else if (c.encoder_id && nother < MAXN) {
                other_enc[nother++] = c.encoder_id;
            }
        }
        free(modes);
    }
    const uint32_t crtc = conn_crtc(fd, best_enc, crtcs, res.count_crtcs);
    if (!best_conn || !crtc)
        goto fail;

    struct drm_mode_create_dumb cd = {.width = best_mode.hdisplay, .height = best_mode.vdisplay, .bpp = 32};
    if (ioctl(fd, DRM_IOCTL_MODE_CREATE_DUMB, &cd))
        goto fail;
    struct drm_mode_fb_cmd fbc = {.width = cd.width, .height = cd.height, .pitch = cd.pitch, .bpp = 32,
                                  .depth = 24, .handle = cd.handle};
    struct drm_mode_map_dumb md = {.handle = cd.handle};
    if (ioctl(fd, DRM_IOCTL_MODE_ADDFB, &fbc) || ioctl(fd, DRM_IOCTL_MODE_MAP_DUMB, &md))
        goto fail;
    uint8_t *map = mmap(NULL, cd.size, PROT_READ | PROT_WRITE, MAP_SHARED, fd, md.offset);
    if (map == MAP_FAILED)
        goto fail;
    memset(map, 0, cd.size);

    for (uint32_t i = 0; i < nother; i++) {   /* the other panels off (they showed the mirrored console) */
        struct drm_mode_crtc off = {.crtc_id = conn_crtc(fd, other_enc[i], crtcs, res.count_crtcs)};
        if (off.crtc_id && off.crtc_id != crtc)
            ioctl(fd, DRM_IOCTL_MODE_SETCRTC, &off);
    }
    struct drm_mode_crtc set = {.crtc_id = crtc, .fb_id = fbc.fb_id, .set_connectors_ptr = (uintptr_t)&best_conn,
                                .count_connectors = 1, .mode = best_mode, .mode_valid = 1};
    if (ioctl(fd, DRM_IOCTL_MODE_SETCRTC, &set)) {
        munmap(map, cd.size);
        goto fail;
    }

    Framebuffer *fb = calloc(1, sizeof *fb);
    if (!fb || !(fb->buffer = calloc(1, cd.size))) {
        free(fb);
        munmap(map, cd.size);
        goto fail;
    }
    fb->fd = fd;
    fb->map = map;
    fb->screensize = cd.size;
    fb->vinfo.xres = fb->vinfo.xres_virtual = cd.width;
    fb->vinfo.yres = fb->vinfo.yres_virtual = cd.height;
    fb->vinfo.bits_per_pixel = 32;
    fb->finfo.line_length = cd.pitch;
    return fb;

fail:
    close(fd);
    return NULL;
}
