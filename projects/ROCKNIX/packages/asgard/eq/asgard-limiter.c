/* asgard-limiter: stereo-linked lookahead peak limiter, as a LADSPA plugin for PipeWire's filter-chain.
 * The Thor's "Joey" speaker EQ adds +15 dB (JamesDSP's output gain) and needs this after it, like JamesDSP's limiter.
 * The audio is delayed by LOOKAHEAD so the gain is already down when a peak arrives; release is exponential.
 * A final clamp at the threshold catches what a 1 ms attack can't.
 * The LADSPA 1.1 ABI is declared here (the header isn't in the toolchain): it's a fixed, tiny C struct API. */
#include <math.h>
#include <stdlib.h>
#include <string.h>

typedef float LADSPA_Data;
typedef void *LADSPA_Handle;
typedef int LADSPA_PortDescriptor;
typedef int LADSPA_PortRangeHintDescriptor;
typedef struct { LADSPA_PortRangeHintDescriptor HintDescriptor; LADSPA_Data LowerBound, UpperBound; } LADSPA_PortRangeHint;
typedef struct _LADSPA_Descriptor {
	unsigned long UniqueID;
	const char *Label;
	int Properties;
	const char *Name, *Maker, *Copyright;
	unsigned long PortCount;
	const LADSPA_PortDescriptor *PortDescriptors;
	const char *const *PortNames;
	const LADSPA_PortRangeHint *PortRangeHints;
	void *ImplementationData;
	LADSPA_Handle (*instantiate)(const struct _LADSPA_Descriptor *, unsigned long rate);
	void (*connect_port)(LADSPA_Handle, unsigned long port, LADSPA_Data *data);
	void (*activate)(LADSPA_Handle);
	void (*run)(LADSPA_Handle, unsigned long samples);
	void (*run_adding)(LADSPA_Handle, unsigned long samples);
	void (*set_run_adding_gain)(LADSPA_Handle, LADSPA_Data gain);
	void (*deactivate)(LADSPA_Handle);
	void (*cleanup)(LADSPA_Handle);
} LADSPA_Descriptor;
#define PORT_INPUT 1
#define PORT_OUTPUT 2
#define PORT_CONTROL 4
#define PORT_AUDIO 8
#define HINT_BOUNDED_BELOW 1
#define HINT_BOUNDED_ABOVE 2
#define HINT_DEFAULT_MAXIMUM 0x100
#define HINT_DEFAULT_MIDDLE 0x80
#define PROP_HARD_RT_CAPABLE 4

enum { IN_L, IN_R, OUT_L, OUT_R, THRESHOLD, RELEASE, PORTS };
#define LOOKAHEAD_MS 1.5f
#define MAXDELAY 1024   /* samples: covers LOOKAHEAD_MS up to 384 kHz */

typedef struct {
	LADSPA_Data *port[PORTS];
	float rate, gain, buf[2][MAXDELAY];
	unsigned pos, delay;
} Limiter;

static LADSPA_Handle instantiate(const LADSPA_Descriptor *d, unsigned long rate)
{
	Limiter *l = calloc(1, sizeof(*l));
	(void)d;
	if (!l)
		return NULL;
	l->rate = rate;
	l->delay = (unsigned)(rate * LOOKAHEAD_MS / 1000);
	if (l->delay >= MAXDELAY)
		l->delay = MAXDELAY - 1;
	l->gain = 1;
	return l;
}

static void connect_port(LADSPA_Handle h, unsigned long p, LADSPA_Data *data) { ((Limiter *)h)->port[p] = data; }

static void activate(LADSPA_Handle h)
{
	Limiter *l = h;
	memset(l->buf, 0, sizeof(l->buf));
	l->pos = 0;
	l->gain = 1;
}

static void run(LADSPA_Handle h, unsigned long n)
{
	Limiter *l = h;
	const float thr = powf(10, *l->port[THRESHOLD] / 20);
	const float attack = 1 - expf(-1 / (l->rate * LOOKAHEAD_MS / 1000));       /* reach the target within the lookahead */
	const float release = 1 - expf(-1 / (l->rate * fmaxf(*l->port[RELEASE], 1) / 1000));
	const LADSPA_Data *il = l->port[IN_L], *ir = l->port[IN_R];
	LADSPA_Data *ol = l->port[OUT_L], *or_ = l->port[OUT_R];

	for (unsigned long i = 0; i < n; i++) {
		const float peak = fmaxf(fabsf(il[i]), fabsf(ir[i]));            /* stereo-linked: no image shift */
		const float want = peak > thr ? thr / peak : 1;
		l->gain += (want - l->gain) * (want < l->gain ? attack : release);
		const unsigned rd = (l->pos + MAXDELAY - l->delay) % MAXDELAY;
		const float dl = l->buf[0][rd] * l->gain, dr = l->buf[1][rd] * l->gain;
		l->buf[0][l->pos] = il[i];
		l->buf[1][l->pos] = ir[i];
		l->pos = (l->pos + 1) % MAXDELAY;
		ol[i] = fminf(fmaxf(dl, -thr), thr);
		or_[i] = fminf(fmaxf(dr, -thr), thr);
	}
}

static void cleanup(LADSPA_Handle h) { free(h); }

static const LADSPA_PortDescriptor descs[PORTS] = {
	PORT_INPUT | PORT_AUDIO, PORT_INPUT | PORT_AUDIO, PORT_OUTPUT | PORT_AUDIO, PORT_OUTPUT | PORT_AUDIO,
	PORT_INPUT | PORT_CONTROL, PORT_INPUT | PORT_CONTROL,
};
static const char *const names[PORTS] = { "In L", "In R", "Out L", "Out R", "Threshold (dB)", "Release (ms)" };
static const LADSPA_PortRangeHint hints[PORTS] = {
	{ 0, 0, 0 }, { 0, 0, 0 }, { 0, 0, 0 }, { 0, 0, 0 },
	{ HINT_BOUNDED_BELOW | HINT_BOUNDED_ABOVE | HINT_DEFAULT_MAXIMUM, -30, 0 },
	{ HINT_BOUNDED_BELOW | HINT_BOUNDED_ABOVE | HINT_DEFAULT_MIDDLE, 10, 1000 },
};
static const LADSPA_Descriptor descriptor = {
	.UniqueID = 4747, .Label = "asgard_limiter", .Properties = PROP_HARD_RT_CAPABLE,
	.Name = "Asgard stereo lookahead limiter", .Maker = "Asgard OS", .Copyright = "GPL-2.0",
	.PortCount = PORTS, .PortDescriptors = descs, .PortNames = names, .PortRangeHints = hints,
	.instantiate = instantiate, .connect_port = connect_port, .activate = activate, .run = run, .cleanup = cleanup,
};

const LADSPA_Descriptor *ladspa_descriptor(unsigned long index) { return index == 0 ? &descriptor : NULL; }

#ifdef SELFTEST
/* cc -DSELFTEST -O2 asgard-limiter.c -lm && ./a.out: a +12 dB burst never exceeds the threshold, quiet audio passes. */
#include <stdio.h>
int main(void)
{
	float il[48000], ir[48000], ol[48000], or_[48000], thr = -0.1f, rel = 100;   /* 100 ms: recovered by the tail */
	LADSPA_Handle h = instantiate(&descriptor, 48000);
	float *ports[PORTS] = { il, ir, ol, or_, &thr, &rel };
	for (int p = 0; p < PORTS; p++)
		connect_port(h, p, ports[p]);
	activate(h);
	for (int i = 0; i < 48000; i++)
		il[i] = ir[i] = (i > 1000 && i < 3000 ? 4.0f : 0.25f) * sinf(i * 0.05f);
	run(h, 48000);
	float mx = 0, late = 0;
	for (int i = 0; i < 48000; i++) {
		mx = fmaxf(mx, fabsf(ol[i]));
		if (i > 40000) late = fmaxf(late, fabsf(ol[i]));
	}
	printf("max %.4f (limit %.4f), quiet tail peak %.4f\n", mx, powf(10, thr / 20), late);
	return !(mx <= powf(10, thr / 20) + 1e-6f && late > 0.24f && late < 0.26f);
}
#endif
