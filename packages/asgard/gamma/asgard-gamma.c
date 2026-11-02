// asgard-gamma: per-screen white balance through the DPU's gamma tables (wlr-gamma-control). The two Thor panels'
// whites differ; this holds a ramp per output for as long as it runs (sway drops a ramp when its client exits).
// Settings (system.cfg): asgard.warmth.top|bottom and asgard.tint.top|bottom, -10..10, 0 = the panel's own.
// Bottom defaults (unset keys): tint +3, contrast +3 (exponent 1.3), chosen by eye on the Thor (2026-10-29) with
// Ultra Black on or off. Measured references (webcam): tint +10 (green x0.80) matched the top's white within ~1 % at
// 50 % brightness; contrast +10 (exponent 2.0) put the bottom on the top's curve with Ultra Black on (grey 128 at
// ~20 % of white, sRGB's ~22 %), +6 with it off. +3 keeps more shadow detail than either.
// SIGHUP re-reads them. Gains only ever lower a channel, so nothing clips.
// A running game's own values are in /run/asgard-screen-override.cfg (asgard-perf-profile.sh), and win over system.cfg.
#define _GNU_SOURCE
#include <errno.h>
#include <math.h>
#include <poll.h>
#include <signal.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/signalfd.h>
#include <unistd.h>
#include <wayland-client.h>
#include "wlr-gamma-control-unstable-v1-client-protocol.h"

struct out {
	struct wl_output *wl;
	struct zwlr_gamma_control_v1 *gc;
	char name[32];
	uint32_t size;
};
static struct out outs[4];
static int nouts;
static struct zwlr_gamma_control_manager_v1 *mgr;

static int file_int(const char *path, const char *key, int v)
{
	FILE *f = fopen(path, "r");
	char line[256];
	size_t n = strlen(key);
	if (!f)
		return v;
	while (fgets(line, sizeof line, f))   // the last one wins, like `sed -n ... | tail -1`
		if (!strncmp(line, key, n) && line[n] == '=')
			v = atoi(line + n + 1);
	fclose(f);
	return v;
}

static int cfg_int(const char *key, int v)
{
	const char *path = getenv("CFG") ? getenv("CFG") : "/storage/.config/system/configs/system.cfg";
	const char *over = getenv("CFG_OVERRIDE") ? getenv("CFG_OVERRIDE") : "/run/asgard-screen-override.cfg";
	v = file_int(over, key, file_int(path, key, v));
	return v < -10 ? -10 : v > 10 ? 10 : v;
}

// warmth > 0 lowers blue (and a little green), < 0 lowers red; tint > 0 lowers green (magenta), < 0 red and blue.
void gains(int warmth, int tint, double g[3])
{
	g[0] = g[1] = g[2] = 1;
	if (warmth > 0) { g[2] -= 0.03 * warmth; g[1] -= 0.01 * warmth; }
	if (warmth < 0) { g[0] += 0.03 * warmth; g[1] += 0.01 * warmth; }
	if (tint > 0) g[1] *= 1 - 0.02 * tint;
	if (tint < 0) { g[0] *= 1 + 0.02 * tint; g[2] *= 1 + 0.02 * tint; }
}

double exponent(int contrast)
{
	return 1 + contrast / 10.0;
}

static void apply(struct out *o)
{
	// DSI-2 is the top panel, DSI-1 the bottom one (ROCKNIX's `brightness` numbering is the other way round).
	const char *which = !strcmp(o->name, "DSI-2") ? "top" : !strcmp(o->name, "DSI-1") ? "bottom" : NULL;
	char kw[40], kt[40], kc[40];
	double g[3];
	if (!o->gc || !o->size || !which)
		return;
	snprintf(kw, sizeof kw, "asgard.warmth.%s", which);
	snprintf(kt, sizeof kt, "asgard.tint.%s", which);
	snprintf(kc, sizeof kc, "asgard.contrast.%s", which);
	int bottom = !strcmp(which, "bottom");
	gains(cfg_int(kw, 0), cfg_int(kt, bottom ? 3 : 0), g);
	double e = exponent(cfg_int(kc, bottom ? 3 : 0));

	size_t len = o->size * 3 * sizeof(uint16_t);
	int fd = memfd_create("asgard-gamma", MFD_CLOEXEC);
	if (fd < 0 || ftruncate(fd, len) < 0)
		return;
	uint16_t *r = mmap(NULL, len, PROT_WRITE, MAP_SHARED, fd, 0);
	if (r != MAP_FAILED) {
		for (uint32_t i = 0; i < o->size; i++)
			for (int c = 0; c < 3; c++)
				r[c * o->size + i] = (uint16_t)lround(65535.0 * pow((double)i / (o->size - 1), e) * g[c]);
		munmap(r, len);
		zwlr_gamma_control_v1_set_gamma(o->gc, fd);
		fprintf(stderr, "%s: gains %.3f %.3f %.3f, exponent %.1f\n", o->name, g[0], g[1], g[2], e);
	}
	close(fd);
}

static void gc_size(void *data, struct zwlr_gamma_control_v1 *gc, uint32_t size)
{
	struct out *o = data;
	o->size = size;
	apply(o);
}

static void gc_failed(void *data, struct zwlr_gamma_control_v1 *gc)
{
	struct out *o = data;
	// wlroots refuses an output that is powered off (Home turns the bottom one off when it's unused): main()
	// asks again every 5 s until it has them all.
	fprintf(stderr, "%s: gamma control refused (powered off, or another client holds it); retrying\n", o->name);
	zwlr_gamma_control_v1_destroy(gc);
	o->gc = NULL;
}

static const struct zwlr_gamma_control_v1_listener gc_listener = { gc_size, gc_failed };

static void out_name(void *data, struct wl_output *wl, const char *name)
{
	snprintf(((struct out *)data)->name, sizeof ((struct out *)data)->name, "%s", name);
}
static void out_nop() {}
static const struct wl_output_listener out_listener = {
	.geometry = (void *)out_nop, .mode = (void *)out_nop, .done = (void *)out_nop,
	.scale = (void *)out_nop, .name = out_name, .description = (void *)out_nop,
};

static void global(void *data, struct wl_registry *reg, uint32_t id, const char *iface, uint32_t ver)
{
	if (!strcmp(iface, wl_output_interface.name) && ver >= 4 && nouts < 4) {
		struct out *o = &outs[nouts++];
		o->wl = wl_registry_bind(reg, id, &wl_output_interface, 4);
		wl_output_add_listener(o->wl, &out_listener, o);
	} else if (!strcmp(iface, zwlr_gamma_control_manager_v1_interface.name)) {
		mgr = wl_registry_bind(reg, id, &zwlr_gamma_control_manager_v1_interface, 1);
	}
}
static void global_remove(void *data, struct wl_registry *reg, uint32_t id) {}

// Ask for every output's gamma control we don't hold yet; returns how many are still missing after a roundtrip.
static int request(struct wl_display *d)
{
	int missing = 0;
	for (int i = 0; i < nouts; i++)
		if (!outs[i].gc) {
			outs[i].size = 0;
			outs[i].gc = zwlr_gamma_control_manager_v1_get_gamma_control(mgr, outs[i].wl);
			zwlr_gamma_control_v1_add_listener(outs[i].gc, &gc_listener, &outs[i]);
		}
	wl_display_roundtrip(d);   // gamma_size or failed
	for (int i = 0; i < nouts; i++)
		missing += !outs[i].gc;
	return missing;
}
static const struct wl_registry_listener reg_listener = { global, global_remove };

int main(int argc, char **argv)
{
	if (argc == 3 && !strcmp(argv[1], "--exponent")) {   // the mappings alone, for test_gamma.sh
		printf("%.1f\n", exponent(atoi(argv[2])));
		return 0;
	}
	if (argc == 4 && !strcmp(argv[1], "--cfg")) {
		printf("%d\n", cfg_int(argv[2], atoi(argv[3])));
		return 0;
	}
	if (argc == 4 && !strcmp(argv[1], "--gains")) {
		double g[3];
		gains(atoi(argv[2]), atoi(argv[3]), g);
		printf("%.3f %.3f %.3f\n", g[0], g[1], g[2]);
		return 0;
	}
	struct wl_display *d = wl_display_connect(NULL);
	if (!d) {
		fprintf(stderr, "no wayland display\n");
		return 1;
	}
	wl_registry_add_listener(wl_display_get_registry(d), &reg_listener, NULL);
	wl_display_roundtrip(d);   // globals
	wl_display_roundtrip(d);   // output names
	if (!mgr) {
		fprintf(stderr, "compositor has no wlr-gamma-control\n");
		return 1;
	}
	request(d);

	sigset_t hup;
	sigemptyset(&hup);
	sigaddset(&hup, SIGHUP);
	sigprocmask(SIG_BLOCK, &hup, NULL);
	struct pollfd fds[2] = { { wl_display_get_fd(d), POLLIN }, { signalfd(-1, &hup, SFD_CLOEXEC), POLLIN } };
	for (;;) {
		while (wl_display_prepare_read(d))
			wl_display_dispatch_pending(d);
		wl_display_flush(d);
		int missing = 0;
		for (int i = 0; i < nouts; i++)
			missing += !outs[i].gc;
		int n = poll(fds, 2, missing ? 5000 : -1);
		if (n == 0) {   // retry the refused outputs
			wl_display_cancel_read(d);
			request(d);
			continue;
		}
		if (n < 0 && errno != EINTR) {
			wl_display_cancel_read(d);
			return 1;
		}
		if (fds[0].revents & POLLIN) {
			if (wl_display_read_events(d) < 0)
				return 1;   // compositor gone: systemd restarts us with the next sway
		} else {
			wl_display_cancel_read(d);
		}
		if (fds[0].revents & (POLLERR | POLLHUP))
			return 1;
		wl_display_dispatch_pending(d);
		if (fds[1].revents & POLLIN) {
			struct signalfd_siginfo si;
			if (read(fds[1].fd, &si, sizeof si) == sizeof si)
				for (int i = 0; i < nouts; i++)
					apply(&outs[i]);
		}
	}
}
