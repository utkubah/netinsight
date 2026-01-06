import logging
import os


def setup_logging(level="INFO"):
    """
    Simple logging setup.
    - Uses NETINSIGHT_LOG_LEVEL if set
    - Doesn't reconfigure if handlers already exist
    """
    root = logging.getLogger()
    if root.handlers:
        return

    level_name = os.environ.get("NETINSIGHT_LOG_LEVEL", level).upper()
    level_value = getattr(logging, level_name, logging.INFO)

    logging.basicConfig(
        level=level_value,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
