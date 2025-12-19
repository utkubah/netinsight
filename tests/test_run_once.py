
"""
Smoke test for the main NetInsight loop.

"""


import main
from datetime import datetime, timezone

def test_run_once_does_not_crash():
    # If this returns without raising, the test passes.
    round_id = datetime.now(timezone.utc).isoformat()
    main.run_once(round_id)
