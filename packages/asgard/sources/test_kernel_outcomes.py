#!/usr/bin/env python3
# spec: KERN-1 KERN-2 KERN-3 KERN-4 KERN-5 KERN-6 KERN-7 KERN-8
# requires: file:packages/linux/src/Makefile
# Tree check for a rebase: the code that delivers each KERN outcome is still there (comments don't count), so dropping one of
# these patches fails here. It shows only that: whether the outcome holds on a Thor is test-device.sh and docs/human-checks.md.
import os
import re
import sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
KSRC = os.environ.get("KERNEL_SRC", os.path.join(ROOT, "packages/linux/src"))  # another tree: to see this go red
THOR = "arch/arm64/boot/dts/qcom/qcs8550-ayn-thor.dts"
COMMON = "arch/arm64/boot/dts/qcom/qcs8550-ayn-common.dtsi"
QMP_COMBO = "drivers/phy/qualcomm/phy-qcom-qmp-combo.c"
FORCE_PM = r"SYSTEM_SLEEP_PM_OPS\(pm_runtime_force_suspend, pm_runtime_force_resume\)"

# rule, kernel file, what must be in its code (a regex), or not be, when it starts with "!"; the patch or reason
HAS = [
    ("KERN-1", "drivers/gpu/drm/panel/panel-chipone-icna35xx.c", r"icna3520_modes\[\] = \{.*?\* 120 / 1000.*?\* 60 / 1000.*?\n\};", "top panel: 120 and 60 Hz"),
    ("KERN-1", "drivers/gpu/drm/panel/panel-ddic-ch13726a.c", r"drm_mode_duplicate\(connector->dev, &thor_display_mode_120\)", "9059: bottom panel 120 Hz"),
    ("KERN-1", "drivers/gpu/drm/panel/panel-ddic-ch13726a.c", r"thor_display_mode = \{.*?\* 60 / 1000", "9046: bottom panel 60 Hz"),
    ("KERN-1", "drivers/gpu/drm/panel/panel-chipone-icna35xx.c", r"if \(ultra_black\) \{\s*mipi_dsi_dcs_write_seq_multi\(&dsi_ctx, 0xB7, 0x00, 0x11, 0x11", "9001, 9061: Ultra Black"),
    ("KERN-1", "drivers/video/backlight/sy7758.c", r"\"silergy,sy7758\"", "0060: SY7758 driver"),
    ("KERN-1", THOR, r"compatible = \"chipone,icna3520\"", "the top panel's driver matches"),
    ("KERN-1", THOR, r"compatible = \"ch13726a,thor\"", "the bottom panel's driver matches"),
    ("KERN-1", THOR, r"compatible = \"focaltech,ft5426\".*compatible = \"focaltech,ft5452\"", "both touchscreens"),
    ("KERN-2", "drivers/input/joystick/rsinput.c", r"schedule_delayed_work\(&drv->resume_work", "9058: a failed resume init retries"),
    ("KERN-2", "drivers/input/joystick/rsinput.c", r"drv->vdd_off = true", "9033: MCU rail off in sleep"),
    ("KERN-2", COMMON, r"!vdd-mcu-3v3-regulator \{[^}]*regulator-always-on", "0024: the MCU rail isn't always-on"),
    ("KERN-2", "drivers/input/misc/qcom-hv-haptics.c", r"global_suspended", "9030: no haptics while suspended"),
    ("KERN-2", "drivers/leds/leds-htr3212.c", r"PM_OPS\([^)]*htr3212_suspend,\s*htr3212_resume", "9032: stick LED controllers across sleep"),
    ("KERN-3", "drivers/ufs/host/ufs-qcom.c", r"\"qcom,sm8550-ufshc\"\)\s*\?\s*UFS_HS_G5", "1024: HS-G5"),
    ("KERN-3", "drivers/phy/qualcomm/phy-qcom-qmp-ufs.c", r"\.supply = \"vdda-qref\", \.init_load_uA = 30000", "9048: PHY calibration on resume"),
    ("KERN-3", "drivers/ufs/host/ufs-qcom.c", r"host->phy_kept_on = true", "9017: PHY power across sleep"),
    ("KERN-3", COMMON, r"!&sdhc_2 \{[^}]*sdhci-caps-mask", "0004: no caps mask keeps SD from SDR104"),
    ("KERN-4", "drivers/usb/typec/ucsi/ucsi_glink.c", r"pm_wakeup_dev_event\(ucsi->dev", "9005: a USB-C attach wakes it"),
    ("KERN-4", "drivers/mailbox/qcom-ipcc.c", r"of_machine_is_compatible\(\"ayn,thor\"\) \? IRQF_NO_SUSPEND", "9005: the mailbox stays live asleep"),
    ("KERN-4", "drivers/power/supply/qcom_battmgr.c", r"psy_cfg\.no_wakeup_source = true", "9019: charger updates don't wake it"),
    ("KERN-4", QMP_COMBO, r"!qmp_combo_usb_power_on.*?err_disable_pipe_clk:\s*clk_disable_unprepare\(qmp->pipe_clk\);.*?static int qmp_combo_usb_power_off", "9036: USB resumes after a PHY timeout"),
    ("KERN-5", "drivers/pci/controller/dwc/pcie-qcom.c", r"val &= ~\(PCI_EXP_SLTCAP_HPC \| PCI_EXP_SLTCAP_HPS\)", "9045: the root port can reach D3"),
    ("KERN-5", "drivers/clk/qcom/gcc-sm8550.c", r"pcie_0_gdsc = \{(?:(?!static struct).)*?\.pwrsts = PWRSTS_OFF_ON", "9050: PCIe 0's GDSC powers off"),
    ("KERN-5", "drivers/clk/qcom/gcc-sm8550.c", r"pcie_1_gdsc = \{(?:(?!static struct).)*?\.pwrsts = PWRSTS_OFF_ON", "9050: PCIe 1's GDSC powers off"),
    ("KERN-5", "drivers/pci/controller/pci-host-common.c", r"if \(endpoint_d3cold\)", "9051: only endpoints veto D3cold"),
    ("KERN-6", "drivers/gpu/drm/msm/adreno/a6xx_gmu.c", r"dev_pm_opp_set_opp\(&gpu->pdev->dev, bw_index \? NULL : opp\)", "9009: the boot bus vote goes"),
    ("KERN-6", COMMON, r"&crypto \{\s*status = \"disabled\";", "crypto engine off: no driver since 7.3, its vote blocks DDR collapse"),
    ("KERN-7", "sound/soc/qcom/sc8280xp.c", r"card->suspend_post = sc8280xp_snd_suspend_post", "9047: the I2S clock drops in sleep"),
    ("KERN-7", "sound/soc/codecs/lpass-rx-macro.c", FORCE_PM, "9047: RX macro"),
    ("KERN-7", "sound/soc/codecs/lpass-tx-macro.c", FORCE_PM, "9047: TX macro"),
    ("KERN-7", "sound/soc/codecs/lpass-va-macro.c", FORCE_PM, "9047: VA macro"),
    ("KERN-7", "drivers/pinctrl/qcom/pinctrl-sm8550-lpass-lpi.c", FORCE_PM, "9047: LPI pinctrl"),
    ("KERN-7", "drivers/soundwire/qcom.c", r"return pm_runtime_force_suspend\(dev\)", "9052: SoundWire"),
    ("KERN-7", "sound/soc/qcom/qdsp6/q6apm-dai.c", r"q6apm_dai_release_graph\(prtd, substream->stream\)", "9012: open PCMs release their graphs"),
    ("KERN-8", "drivers/hwmon/pwm-fan.c", r"pwm_fan_quiesce_tachs\(ctx\);", "9035: tach IRQs and RPM timer quiet in sleep"),
    ("KERN-8", "drivers/power/supply/qcom_battmgr.c", r"return qcom_battmgr_set_charge_current\(battmgr, pval->intval\)", "9020: the charge current can be set"),
    ("KERN-8", "drivers/power/supply/qcom_battmgr.c", r"le32_to_cpu\(resp->intval\.result\) \? -EIO : 0", "9021: a refused set is an error"),
]
# Upstream fixes picked ahead of our stable base (not a spec outcome): drop a row once the base carries the fix.
PICKED = [
    ("drivers/gpu/drm/msm/adreno/a6xx_gmu.c", r"a6xx_gmu_rpmh_dep_votes_init\(&gpu->pdev->dev,", "7.4 eab0aff8965e: GPU dependency votes resolve against the GPU's OPP table"),
    ("drivers/gpu/drm/msm/adreno/a6xx_gmu.c", r"if \(sec\[j\] >= pri\[pindex\]\)", "7.4 128a0edde507: the secondary rail matches the quantized primary level"),
]
# Outside the kernel: the build config that uses them, and this tree's rule and command line.
CONFIG = [("KERN-1", f"CONFIG_{c}=y") for c in ("DRM_PANEL_CHIPONE_ICNA35XX", "DRM_PANEL_DDIC_CH13726A", "BACKLIGHT_SY7758", "TOUCHSCREEN_EDT_FT5X06")]
CONFIG += [("KERN-2", "CONFIG_JOYSTICK_RSINPUT=y"), ("KERN-2", "CONFIG_LEDS_HTR3212=y"), ("KERN-2", "CONFIG_INPUT_QCOM_HV_HAPTICS=y"),
           ("KERN-8", "CONFIG_SENSORS_PWM_FAN=m"), ("KERN-8", "CONFIG_BATTERY_QCOM_BATTMGR=m")]


def code(path):
    """A source file without its comments."""
    with open(path, errors="ignore") as f:
        text = f.read()
    return re.sub(r"/\*.*?\*/|//[^\n]*", "", text, flags=re.S)


failed = []
for rule, name, want, why in HAS:
    try:
        text = code(os.path.join(KSRC, name))
    except OSError:
        failed.append(f"{rule}: {name} is missing ({why})")
        continue
    absent = want.startswith("!")
    hit = re.search(want.lstrip("!"), text, re.S)
    if bool(hit) == absent:
        failed.append(f"{rule}: {name}: {why}")

for name, want, why in PICKED:
    if not re.search(want, code(os.path.join(KSRC, name)), re.S):
        failed.append(f"picked fix lost: {name}: {why}")

conf = open(os.path.join(ROOT, "device/linux/linux.aarch64.conf")).read().splitlines()
failed += [f"{rule}: {want} isn't set" for rule, want in CONFIG if want not in conf]
udev = open(os.path.join(ROOT, "device/filesystem/usr/lib/udev/rules.d/99-sm8550-usb-autosuspend.rules")).read()
if not re.search(r'^ACTION=="add".*KERNEL=="a600000\.usb", ATTR\{power/control\}="auto"$', udev, re.M):
    failed.append("KERN-4: the idle USB controller doesn't autosuspend, so it keeps its DDR vote")
options = open(os.path.join(ROOT, "device/options")).read()
if "mem_sleep_default=s2idle" not in options or "pcie_ports=compat" in options:
    failed.append("KERN-5: the command line: s2idle, and no pcie_ports=compat (it leaves the root port in D0)")
if failed:
    sys.exit("\n".join(failed))
print("ok")
