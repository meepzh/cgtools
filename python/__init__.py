"""Personal repository for small CG-related Python tools."""
import logging
import logging.config
import os

from cgtools.agnostic.layered_config import LayeredConfig


config = LayeredConfig(__name__).get_config("logging")
logging.config.dictConfig(config)

logger = logging.getLogger(__name__)
env_level = os.getenv("CGTOOLS_LOG_LEVEL")
if env_level:
    logger.setLevel(env_level)
