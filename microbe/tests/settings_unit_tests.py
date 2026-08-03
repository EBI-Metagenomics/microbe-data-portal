from microbe.settings import *

UNIT_TESTING = True

MICROBE_CONFIG = MicrobeConfig(
    _env_file=microbe_config_env,
)

del STORAGES  # disable whitenoise static file serving
