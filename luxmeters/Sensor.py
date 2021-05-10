from luxmeters.ut382.ut382 import ut382
from luxmeters.konica.CL200A import CL200A
from luxmeters.logs import logger

from numpy import array as np_array
from colour import XY_TO_CCT_METHODS, XYZ_to_xy, xy_to_CCT


DEBUG = False
# Available sensors and their capabilities
SENSORS = {
    "ut382": {
        "object": ut382,
        "flags": {
            "lux": 1
        }
    },

    "cl200a": {
        "object": CL200A,
        "flags": {
            "lux": 1,
            "xyz": 1,
            "delta_uv": 1
        }
    }
}
SENSORS_LIST = list(SENSORS.keys())


class Sensor:
    def __init__(self, model=SENSORS_LIST[0]):
        if model not in SENSORS_LIST:
            raise ValueError(f"Invalid sensor model. Expected one of: {SENSORS_LIST}")

        self.model = model
        self.model_data = SENSORS[model]
        self.model_flags = self.model_data["flags"]
        self.model_id = SENSORS_LIST.index(model)

        logger.debug(f"Sensor {model} has flags: {self.model_flags}")
        logger.info(f"Initializing {model} Sensor device...")

        self.obj = self.model_data["object"]()

        if self.obj is None:
            print(f"self.model_data['object'] = {self.model_data['object']}")
            exit(1)

    def get(self, type='lux'):
        available_types = list(self.model_flags.keys()) + ["cct", "all"]
        if type not in available_types:
            raise ValueError(f"Invalid measurement type. Expected one of: {available_types}")

        if type == "lux":
            return self.obj.get_lux() if self.has_flag("lux") else None
        elif type == "xyz":
            return self.obj.get_xyz() if self.has_flag("xyz") else None
        elif type == "cct":
            return self.get_cct() if self.has_flag("xyz") else None
        elif type == "delta_uv":
            return self.obj.get_delta_uv() if self.has_flag("delta_uv") else None
        elif type == "all":
            ret = ""
            ret += f"Lux: \t\t\t    {self.obj.get_lux()} lux, \n" if self.has_flag("lux") else ""
            ret += f"(X, Y, Z): \t\t\t{self.obj.get_xyz()}, \n" if self.has_flag("xyz") else ""
            ret += f"CCT: \t\t\t    {self.get_cct()} K, \n" if self.has_flag("xyz") else ""
            ret += f"EV, TCP, Δuv: \t\t{self.obj.get_delta_uv()}, \n" if self.has_flag("delta_uv") else ""
            return ret

    def get_cct(self, methods="Hernandez 1999"):
        '''
        approximate CCT using CIE 1931 xy values
        '''
        x, y, z = self.obj.get_xyz()

        if 0 in [x, y, z]:
            return 0.0

        logger.debug(f"x = {x}, y = {y}, z = {z}")

        if isinstance(methods, str):
            methods = [methods]

        ccts = list()

        for curr_method in methods:
            if curr_method == 'me_mccamy':
                # McCamy's Approx
                small_x = x/(x+y+z)
                small_y = y/(x+y+z)

                n = (small_x-0.3320)/(0.1858-small_y)
                cct = 437*(n**3) + 3601*(n**2) + 6861*n + 5517

                if DEBUG:
                    logger.debug(f"[me_mccamy] calc x = {small_x}, calc y = {small_y} | Calc CCT = {cct} K")
            elif curr_method in XY_TO_CCT_METHODS:
                xyz_arr = np_array([x, y, z])
                xy_arr = XYZ_to_xy(xyz_arr)
                cct = xy_to_CCT(xy_arr, curr_method)
                if DEBUG:
                    logger.debug(f"[{curr_method}] calc x,y = {xy_arr} | CCT = {cct}")
            else:
                options = ["me_mccamy"] + list(XY_TO_CCT_METHODS)

                logger.error(f"{curr_method} Not found!\nCCT calculation methods: \n {options}")

                return

            ccts.append(int(cct))

        if len(ccts) == 1:
            return ccts[0]
        else:
            return ccts

    def has_flag(self, flag):
        if flag in self.model_flags:
            if self.model_flags[flag]:
                return True
        return False

    def __del__(self):
        pass
