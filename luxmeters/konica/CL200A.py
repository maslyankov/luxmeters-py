# coding=utf-8
from time import sleep
from serial import PARITY_EVEN, SEVENBITS, SerialException

from luxmeters import logs
from luxmeters.konica import CL200A_utils

SKIP_CHECK_LIST = True
DEBUG = False


class CL200A(object):
    """
    Konica Minolta (CL - 200A)

    All documentation can be found:
    http://www.konicaminolta.com.cn/instruments/download/software/pdf/CL-200A_communication_specifications.pdf
    """

    def __init__(self):
        self.cmd_dict = CL200A_utils.cl200a_cmd_dict
        self.port = CL200A_utils.serial_port_luxmeter()

        try:
            self.ser = CL200A_utils.connect_serial_port(self.port, parity=PARITY_EVEN, bytesize=SEVENBITS)
        except SerialException:
            # logs.logger.error('Error: Could not connect to Lux Meter')
            raise Exception("Could not connect to luxmeter")
        try:
            self.__connection()
            self.__hold_mode()
            self.__ext_mode()
        except SerialException as err:
            logs.logger.error(err)
            raise Exception(f"Lux meter not found. Check that the cable is properly connected.")

    def __connection(self):
        """
        Switch the CL-200A to PC connection mode. (Command "54").
        In order to perform communication with a PC,
        this command must be used to set the CL-200A to PC connection mode.
        :return: None
        """

        # cmd_request = CL200A_utils.cmd_formatter(self.CL200A_utils.cl200a_cmd_dict['command_54'])
        cmd_request = chr(2) + '00541   ' + chr(3) + '13\r\n'
        cmd_response = CL200A_utils.cmd_formatter(self.cmd_dict['command_54r'])

        for i in range(2):
            CL200A_utils.write_serial_port(obj=self, ser=self.ser, cmd=cmd_request, sleep_time=0.5)
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
                    logs.logger.warn(f'Error: Attempt one more time')
                    continue
                else:
                    raise SerialException('Konica Minolta CL-200A has an error. Please verify USB cable.')

    def __hold_mode(self):
        """
        Aux function that sets Konica in to hold mode.
        :return: None
        """
        cmd = CL200A_utils.cmd_formatter(self.cmd_dict['command_55'])
        # Hold status
        self.ser.reset_input_buffer()
        self.ser.reset_output_buffer()
        CL200A_utils.write_serial_port(obj=self, ser=self.ser, cmd=cmd, sleep_time=0.5)

    def __ext_mode(self):
        """
        Set hold mode on Konica Lux Meter. This is necessary in order to set EXT mode. EXT mode can not be performed
        without first setting the CL-200A to Hold status.
        EXT mode is the mode for taking measurements according to the timing commands from the PC.
        :return: None
        """
        cmd = CL200A_utils.cmd_formatter(self.cmd_dict['command_40'])
        self.ser.reset_input_buffer()
        self.ser.reset_output_buffer()

        for i in range(2):
            # set CL-200A to EXT mode
            CL200A_utils.write_serial_port(obj=self, ser=self.ser, cmd=cmd, sleep_time=0.125)
            ext_mode_err = self.ser.readline().decode('ascii')
            # If an error occurred when setting EXT mode (ERR byte = "4"), hold_mode was not completed
            # correctly. Repeat hold_mode and then set EXT mode again.
            if ext_mode_err[6:7] == '4':
                self.__hold_mode()
                continue
            elif ext_mode_err[6:7] in ['1', '2', '3']:
                logs.logger.error('Set hold mode error')
                err = "Switch off the CL-200A and then switch it back on"
                logs.logger.info(err)
                raise ConnectionError(err)
            else:
                break

    def perform_measurement(self, read_cmd) -> str:
        self.ser.reset_input_buffer()
        self.ser.reset_output_buffer()
        # Check if device still here

        # Perform measurement
        cmd_ext = CL200A_utils.cmd_formatter(self.cmd_dict['command_40r'])
        cmd_read = CL200A_utils.cmd_formatter(read_cmd)
        CL200A_utils.write_serial_port(obj=self, ser=self.ser, cmd=cmd_ext, sleep_time=0.5)
        # read data
        CL200A_utils.write_serial_port(obj=self, ser=self.ser, cmd=cmd_read, sleep_time=0)
        try:
            serial_ret = self.ser.readline()
            if not len(serial_ret):
                logs.logger.debug(f"Serial got: {serial_ret}")
                return

            result = serial_ret.decode('ascii')
        except SerialException:
            raise ConnectionAbortedError('Connection to Luxmeter was lost.')

        CL200A_utils.check_measurement(result)

        if DEBUG:
            logs.logger.debug(f"Got raw data: {result.rstrip()}")

        return result

    def get_lux(self) -> float:
        """
        Perform lux level measurement.
        :return: String with lux measured.
        """
        try:
            result = self.perform_measurement(self.cmd_dict['command_02'])

            # Convert Measurement
            lux = CL200A_utils.calc_lux(result)

            if DEBUG:
                logs.logger.debug(f"Returning {lux} luxes")

            return lux
        except IndexError as err:
            logs.logger.debug(f"result: {result}")
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
                logs.logger.debug(f"X: {x}, Y: {y}, Z: {z}")

            return x, y, z
        except IndexError as err:
            logs.logger.debug(f"result: {result}")
            raise ValueError(err)

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
            lux = CL200A_utils.calc_lux(result)

            tcp = float(result[16:20]) / 10
            delta_uv = float(result[22:26]) / 10

            if DEBUG:
                logs.logger.debug(f"Illuminance: {lux} lux, TCP: {tcp}, DeltaUV: {delta_uv}")

            return lux, tcp, delta_uv
        except IndexError as err:
            logs.logger.debug(f"result: {result}")
            raise ValueError(err)


if __name__ == "__main__":
    try:
        luxmeter = CL200A()
    except Exception as e:
        logs.logger.exception(e)
        exit(0)

    timeout = 3

    while True:
        # curr_lux = luxmeter.get_lux()
        luxmeter.get_lux()
        # print(luxmeter.get_xyz())
        # test_suite = ["me_mccamy", "Hernandez 1999"]
        #
        # logs.logger.debug("Testing...")

        # tests = luxmeter.get_cct(test_suite)
        #
        # for num, test in enumerate(test_suite):
        #     logs.logger.info(f"{test}: {tests[num]} K")

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
