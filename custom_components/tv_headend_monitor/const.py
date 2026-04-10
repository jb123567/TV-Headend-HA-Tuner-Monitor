"""Constants for the TVHeadend Tuner Monitor integration."""

DOMAIN = "tvheadend_tuner"

# Config entry keys
CONF_HOST = "host"
CONF_PORT = "port"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_SCAN_INTERVAL = "scan_interval"

# Defaults
DEFAULT_PORT = 9981
DEFAULT_SCAN_INTERVAL = 30  # seconds
DEFAULT_USERNAME = ""
DEFAULT_PASSWORD = ""

# TVHeadend API endpoints
TVH_API_SERVERINFO = "/api/serverinfo"
TVH_API_STATUS_INPUTS = "/api/status/inputs"

# Platforms
PLATFORMS = ["binary_sensor", "sensor", "button"]
