// Asgard defaults for Firefox (the user's about:config changes still win). The image is read-only: no updates.
pref("app.update.auto", false);
pref("app.update.enabled", false);
pref("browser.shell.checkDefaultBrowser", false);
pref("browser.aboutwelcome.enabled", false);
pref("browser.startup.homepage_override.mstone", "ignore");
pref("startup.homepage_welcome_url", "");
pref("datareporting.policy.dataSubmissionEnabled", false);
pref("datareporting.healthreport.uploadEnabled", false);
pref("toolkit.telemetry.enabled", false);
pref("browser.tabs.warnOnClose", false);
// ponytail: top screen is 1920x1080 on a 6" panel; 1.5 = a 1280x720 desktop-layout viewport. Tune in about:config.
pref("layout.css.devPixelsPerPx", "1.5");
// Video: H.264 in software. Without AV1/VP9 YouTube sends H.264 (up to 1080p), far lighter to decode than VP9.
// Firefox's V4L2 hardware decode (Iris, through ffmpeg's *_v4l2m2m) played sound over a frozen picture (2026-10-27).
pref("media.hardware-video-decoding.enabled", false);
pref("media.av1.enabled", false);
pref("media.mediasource.vp9.enabled", false);
// Session restore: tabs come back after Home's quit (which kills Firefox).
pref("browser.startup.page", 3);
pref("browser.sessionstore.resume_from_crash", true);
