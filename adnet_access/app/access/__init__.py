"""AD.NET Access – Zutrittskontrolle als Home-Assistant-Add-on."""
import os

__version__ = os.environ.get("ADNET_VERSION", "dev")   # vom HA-Build gesetzt (BUILD_VERSION)
