"""
measured_link_model.py
=======================
Measured conditional link-headroom model for the RWSCP LoRaWAN deployment,
built to serve as the "measured oracle" in the idealized-vs-measured replay
experiment (cross-device allocation-error / X).

It exposes TWO oracles over SNR margin (dB):

  idealized_margin(sf)            -> deterministic SF->margin map (the assumption
                                     ISAC-IoT allocators make: margin is a clean
                                     function of the allocated SF, zero device/
                                     residual spread).

  measured_margin_dist(sf, dev,   -> (mean, sd) of the REAL conditional
                        load)        distribution P(margin | SF, device, load),
                                     fitted by a mixed-effects model on RWSCP.

Headline empirical facts encoded here (all measured on 1,008 readings, 59 devices):
  * SF alone explains eta^2 = 0.026 (CI 1.4-5.3%) of margin variance -> as a
    fleet-wide channel-state proxy, SF is uninformative.
  * Within a device, SF gain is large (+0 -> +7.0 dB, SF7->SF12) BUT the baseline
    of devices parked at each SF falls +6.6 -> -1.8 dB; corr(SF, baseline) = -0.92.
    The two cancel -> flat ~11 dB fleet margin. SF is ENDOGENOUS (set by ADR in
    response to the hidden baseline), not an exogenous channel observation.
  * Residual sd ~3.2 dB is irreducible: margin is intrinsically noisy beyond any
    (SF, device, load) model. This bounds how precise any oracle / X can be.

IMPORTANT (honest-use notes):
  - Do NOT use the SF fixed effect WITHOUT the device term as a predictor: out of
    sample it is worse (5.07 dB RMSE) than guessing the grand mean (3.67), because
    the SF coefficient is an endogeneity artifact. The device baseline is the
    informative part the idealized allocator has no parameter for.
  - Reliability is NOT modeled here. SNR exists only for RECEIVED frames; missed
    frames have no SNR -> survivorship bias. Treat reliability separately and
    cautiously in the replay.
  - Single deployment, 32 days, no GPS. The device baseline is partly RSSI-linked
    (r=0.57) and only moderately time-stable (r=0.46): a per-device offset SF can't
    see, NOT a static path-loss constant.

Author: built for V. Laniku (RWSCP / ISAC-IoT reality-check paper).
"""
from __future__ import annotations
import json, os, math
import numpy as np

_P = json.load(open(os.path.join(os.path.dirname(__file__), "measured_link_params.json")))

# ---- exposed fitted parameters -------------------------------------------------
INTERCEPT       = _P["intercept"]
LOAD_COEF       = _P["load_coef"]
SF_FIXED_EFFECT = {int(k): v for k, v in _P["sf_fixed_effect_vs_sf7"].items()}  # vs SF7
DEVICE_VAR      = _P["device_var"]
RESIDUAL_VAR    = _P["residual_var"]
RESIDUAL_SD     = _P["residual_sd"]
DEVICE_BASELINE = _P["device_baselines"]          # {dev_eui(str): BLUP offset dB}
IDEALIZED_MAP   = {int(k): v for k, v in _P["idealized_margin_db"].items()}
DEMOD_LIMIT     = {int(k): v for k, v in _P["demod_limit_db"].items()}
SFS             = _P["sfs"]
ETA2_SF_ONLY    = _P["eta2_sf_only"]
CORR_SF_BASELINE= _P["corr_sf_baseline"]
HOLDOUT_RMSE    = _P["holdout_rmse_db"]

_UNKNOWN_DEV_SD = math.sqrt(DEVICE_VAR + RESIDUAL_VAR)   # spread when device unknown


def idealized_margin(sf: int) -> float:
    """Field-assumption oracle: deterministic SF -> margin (dB), spread = 0.
    This is what an ISAC-IoT allocator that treats SF as a channel-state proxy
    believes the link delivers. Use as the 'idealized oracle' in the replay."""
    return IDEALIZED_MAP[int(sf)]


def measured_margin_dist(sf: int, device: str | None = None, load: float = 0.0):
    """Real conditional distribution P(margin | SF, device, load) as (mean_dB, sd_dB).

    device known  -> mean includes the per-device baseline the allocator can't see;
                     sd = residual_sd (~3.2 dB).
    device None    -> mean = fleet margin at SF (~flat); sd = sqrt(device_var+resid_var)
                     (~5 dB), i.e. you genuinely cannot pin a new device from SF alone.
    """
    sf = int(sf)
    if device is not None and str(device) in DEVICE_BASELINE:
        mean = INTERCEPT + SF_FIXED_EFFECT[sf] + LOAD_COEF * load + DEVICE_BASELINE[str(device)]
        return float(mean), float(RESIDUAL_SD)
    return float(IDEALIZED_MAP[sf]), float(_UNKNOWN_DEV_SD)


def sample_measured_margin(sf: int, device: str | None = None, load: float = 0.0,
                           n: int = 1, rng: np.random.Generator | None = None):
    """Draw n samples of margin (dB) from the measured conditional distribution."""
    rng = rng or np.random.default_rng()
    mean, sd = measured_margin_dist(sf, device, load)
    return rng.normal(mean, sd, size=n)


def decode_threshold_margin() -> float:
    """Margin (dB) at the decode boundary. margin = SNR - demod_limit, so the
    threshold is 0 dB by construction. Provided for the reliability layer the
    CALLER must build (with the survivorship caveat in the module docstring)."""
    return 0.0


def device_ids():
    return list(DEVICE_BASELINE.keys())


if __name__ == "__main__":
    # self-test: reproduce fleet-level margin at each SF from the two oracles
    print(f"devices={len(DEVICE_BASELINE)}  eta2(SF)={ETA2_SF_ONLY}  corr(SF,baseline)={CORR_SF_BASELINE}")
    print(f"residual_sd={RESIDUAL_SD:.2f} dB  unknown-device sd={_UNKNOWN_DEV_SD:.2f} dB")
    # Counterfactual: force EVERY device to each SF (removing ADR's baseline sorting).
    # Margin then rises 4.9 -> 11.9 dB with SF -> the *pure* SF gain. The flat
    # observed fleet margin (idealized col) is that gain cancelled by ADR sorting.
    print("\nSF | observed fleet (ADR-sorted) | counterfactual: all devices @ this SF")
    for sf in SFS:
        ms = np.mean([measured_margin_dist(sf, d)[0] for d in DEVICE_BASELINE])
        print(f"SF{sf:<2d} |  {idealized_margin(sf):6.2f}  |  {ms:6.2f}")
    print("\nhold-out RMSE (dB):", HOLDOUT_RMSE)
