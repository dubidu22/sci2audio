"""Shared test configuration.

Hypothesis profiles (select with the HYPOTHESIS_PROFILE environment variable):
- dev (default): quick, for local runs
- ci: every pull request; deterministic, so a red run can be reproduced
- nightly: many more examples to find rare edge cases
"""

import os

from hypothesis import HealthCheck, settings

settings.register_profile("dev", max_examples=50)
settings.register_profile(
    "ci",
    max_examples=100,
    derandomize=True,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow],
)
settings.register_profile("nightly", max_examples=2000, deadline=None)
settings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "dev"))
