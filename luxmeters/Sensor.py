from luxmeters.ut382 import ut382
from luxmeters.konica import CL200A


# Available sensors and their capabilities
SENSORS = {
    "ut382": {
        "lux": 1
    },

    "cl200a": {
        "lux": 1,
        "xyz": 1,
        "delta_uv": 1
    }
}
SENSORS_LIST = list(SENSORS.keys())


class Sensor:
    def __init__(self, model=SENSORS_LIST[0]):
        logger.info("Initializing Sensor device...")

        if model not in SENSORS_LIST:
            raise ValueError(f"Invalid sensor model. Expected one of: {SENSORS_LIST}")

    def get_measurement(self):
        pass

    def __del__(self):
        pass
