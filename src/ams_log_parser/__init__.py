"""Backward-compatibility module alias for AMS_Parser."""

import sys
import AMS_Parser

sys.modules["ams_log_parser"] = AMS_Parser
from AMS_Parser import *  # noqa: F401, F403
