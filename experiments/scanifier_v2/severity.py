"""Shared severity sampling for three-band scanner profiles."""

import numpy as np


BAND_BOUNDARIES = (0.0, 0.4, 0.75, 1.0)
BAND_WEIGHTS = (0.55, 0.35, 0.10)


def severity_parameters(rng, severity, curves, nominal):
    if severity is None:
        band = rng.choice(len(BAND_WEIGHTS), p=BAND_WEIGHTS)
        severity = float(rng.uniform(BAND_BOUNDARIES[band], BAND_BOUNDARIES[band + 1]))
    if not 0 <= severity <= 1:
        raise ValueError("severity must be between 0 and 1")
    return {
        "severity": severity,
        **{
            key: float(np.interp(severity, BAND_BOUNDARIES, (*values, nominal[key])))
            for key, values in curves.items()
        },
    }
