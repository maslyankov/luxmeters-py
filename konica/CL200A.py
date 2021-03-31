# coding=utf-8
from time import sleep
from serial import PARITY_EVEN, SEVENBITS, SerialException

from logs import logger
from CL200A_utils import cl200a_cmd_dict, cmd_formatter, write_serial_port, \
                  serial_port_luxmeter, connect_serial_port, check_measurement, calc_lux

from numpy import array as np_array
from colour import XY_TO_CCT_METHODS, XYZ_to_xy, xy_to_CCT

SKIP_CHECK_LIST = True
DEBUG = True


class CL200A(object):
    """
    Konica Minolta (CL - 200A)

    All documentation can be found:
    http://www.konicaminolta.com.cn/instruments/download/software/pdf/CL-200A_communication_specifications.pdf
    """

    def __init__(self) -> object:
        self.cmd_dict = cl200a_cmd_dict
        self.port = serial_port_luxmeter()

        try:
            self.ser = connect_serial_port(self.port, parity=PARITY_EVEN, bytesize=SEVENBITS)
        except SerialException:
            # logger.error('Error: Could not connect to Lux Meter')
            raise Exception("Could not connect to luxmeter")
        try:
            self.__connection()
            self.__hold_mode()
            self.__ext_mode()
        except SerialException as err:
            logger.error(err)
            raise Exception(f"Lux meter not found. Check that the cable is properly connected.")

    def __connection(self):
        """
        Switch the CL-200A to PC connection mode. (Command "54").
        In order to perform communication with a PC,
        this command must be used to set the CL-200A to PC connection mode.
        :return: None
        """

        # cmd_request = utils.cmd_formatter(self.cl200a_cmd_dict['command_54'])
        cmd_request = chr(2) + '00541   ' + chr(3) + '13\r\n'
        cmd_response = cmd_formatter(self.cmd_dict['command_54r'])

        for i in range(2):
            write_serial_port(obj=self, ser=self.ser, cmd=cmd_request, sleep_time=0.5)
            pc_connected_mode = self.ser.readline().decode('ascii')
            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()
            # Check that the response from the CL-200A is correct.
            if SKIP_CHECK_LIST:
                break
            else:
                if cmd_response in pc_connected_mode:
                    break
                elif i == 0:
                    logger.warn(f'Error: Attempt one more time')
                    continue
                else:
                    raise SerialException('Konica Minolta CL-200A has an error. Please verify USB cable.')

    def __hold_mode(self):
        """
        Aux function that sets Konica in to hold mode.
        :return: None
        """
        cmd = cmd_formatter(self.cmd_dict['command_55'])
        # Hold status
        self.ser.reset_input_buffer()
        self.ser.reset_output_buffer()
        write_serial_port(obj=self, ser=self.ser, cmd=cmd, sleep_time=0.5)

    def __ext_mode(self):
        """
        Set hold mode on Konica Lux Meter. This is necessary in order to set EXT mode. EXT mode can not be performed
        without first setting the CL-200A to Hold status.
        EXT mode is the mode for taking measurements according to the timing commands from the PC.
        :return: None
        """
        cmd = cmd_formatter(self.cmd_dict['command_40'])
        self.ser.reset_input_buffer()
        self.ser.reset_output_buffer()

        for i in range(2):
            # set CL-200A to EXT mode
            write_serial_port(obj=self, ser=self.ser, cmd=cmd, sleep_time=0.125)
            ext_mode_err = self.ser.readline().decode('ascii')
            # If an error occurred when setting EXT mode (ERR byte = "4"), hold_mode was not completed
            # correctly. Repeat hold_mode and then set EXT mode again.
            if ext_mode_err[6:7] == '4':
                self.__hold_mode()
                continue
            elif ext_mode_err[6:7] in ['1', '2', '3']:
                logger.error('Set hold mode error')
                err = "Switch off the CL-200A and then switch it back on"
                logger.info(err)
                raise ConnectionError(err)
            else:
                break

    def perform_measurement(self, read_cmd) -> str:
        self.ser.reset_input_buffer()
        self.ser.reset_output_buffer()
        # Check if device still here

        # Perform measurement
        cmd_ext = cmd_formatter(self.cmd_dict['command_40r'])
        cmd_read = cmd_formatter(read_cmd)
        write_serial_port(obj=self, ser=self.ser, cmd=cmd_ext, sleep_time=0.5)
        # read data
        write_serial_port(obj=self, ser=self.ser, cmd=cmd_read, sleep_time=0)
        try:
            serial_ret = self.ser.readline()
            if not len(serial_ret):
                logger.debug(f"Serial got: {serial_ret}")
                return

            result = serial_ret.decode('ascii')
        except SerialException:
            raise ConnectionAbortedError('Connection to Luxmeter was lost.')

        check_measurement(result)

        if DEBUG:
            logger.debug(f"Got raw data: {result.rstrip()}")

        return result

    def get_lux(self) -> float:
        """
        Perform lux level measurement.
        :return: String with lux measured.
        """
        try:
            result = self.perform_measurement(self.cmd_dict['command_02'])

            # Convert Measurement
            lux = calc_lux(result)

            if DEBUG:
                logger.debug(f"Returning {lux} luxes")

            return lux
        except IndexError as err:
            logger.debug(f"result: {result}")
            raise ValueError(err)

    # Read measurement data (X, Y, Z)                   01
    def get_xyz(self) -> tuple:
        try:
            result = self.perform_measurement(self.cmd_dict['command_01'])
            # Convert Measurement
            x = float(result[10:14])/10
            y = float(result[16:20])/10
            z = float(result[22:26])/10
            # sth = result[27:-1]
            # multiply = result[7:9]

            if DEBUG:
                logger.debug(f"X: {x}, Y: {y}, Z: {z}")

            return x, y, z
        except IndexError as err:
            logger.debug(f"result: {result}")
            raise ValueError(err)

    def get_cct(self, methods="Hernandez 1999"):
        '''
        approximate CCT using CIE 1931 xy values
        '''
        x, y, z = self.get_xyz()

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

    # Read measurement data (EV, TCP, Δuv)              08
    def get_delta_uv(self) -> tuple:
        '''
        Return:
             lux, tcp, delta_uv
        '''
        try:
            result = self.perform_measurement(self.cmd_dict['command_08'])
            # Convert Measurement
            # Calc lux
            lux = calc_lux(result)

            tcp = float(result[16:20]) / 10
            delta_uv = float(result[22:26]) / 10

            if DEBUG:
                logger.debug(f"Illuminance: {lux} lux, TCP: {tcp}, DeltaUV: {delta_uv}")

            return lux, tcp, delta_uv
        except IndexError as err:
            logger.debug(f"result: {result}")
            raise ValueError(err)


if __name__ == "__main__":
    try:
        luxmeter = CL200A()
    except Exception as e:
        logger.exception(e)
        exit(0)

    timeout = 3

    while True:
        # curr_lux = luxmeter.get_lux()

        # luxmeter.get_lux()
        # print(luxmeter.get_xyz())
        test_suite = ["me_mccamy", "Hernandez 1999"]

        logger.debug("Testing...")

        tests = luxmeter.get_cct(test_suite)

        for num, test in enumerate(test_suite):
            logger.info(f"{test}: {tests[num]} K")

        # print(luxmeter.get_delta_uv())

        # if curr_lux:
        #     print(f"Reading: {curr_lux} LUX")
        # else:
        #     print(f"Reading is {curr_lux}, sleeping 1 sec")
        #     print(f"Is alive: {luxmeter.is_alive}")
        #     sleep(1)
        #     timeout -= 1
        #     if not timeout:
        #         print("Timeout!")
        #         break

        # sleep(1)
        print("")  # Add a blank line for readability
