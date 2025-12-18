
"""
Smoke test for the main NetInsight loop.

"""


import main

def test_run_once_does_not_crash():
    # If this returns without raising, the test passes.
    main.run_once()
