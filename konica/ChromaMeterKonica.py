# coding=utf-8
from time import sleep
from serial import PARITY_EVEN, SEVENBITS, SerialException

from logs import logger
from utils import cl200a_cmd_dict, cmd_formatter, write_serial_port, serial_port_luxmeter, connect_serial_port

SKIP_CHECK_LIST = True


class ChromaMeterKonica(object):
    """
    Konica Minolta (CL - 200A)

    All documentation can be found:
    http://www.konicaminolta.com.cn/instruments/download/software/pdf/CL-200A_communication_specifications.pdf
    """

    def __init__(self):
        self.cmd_dict = cl200a_cmd_dict
        self.port = serial_port_luxmeter()
        self.is_alive = True

        try:
            self.ser = connect_serial_port(self.port, parity=PARITY_EVEN, bytesize=SEVENBITS)
        except SerialException:
            logger.error('Error: Could not connect to Lux Meter')
            self.is_alive = False
            return
        try:
            self.__connection()
            self.__hold_mode()
            self.__ext_mode()
        except SerialException:
            logger.error(f"'Lux meter not found. Check that the cable is properly connected.'")

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
                    logger.error('Konica Minolta CL-200a has an error. Please verify USB cable.')

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
                logger.error(err)
                raise ConnectionError(err)
            else:
                break

    def get_lux(self):
        """
        Perform lux level measurement.
        :return: String with lux measured.
        """
        if not self.is_alive:
            return

        self.ser.reset_input_buffer()
        self.ser.reset_output_buffer()
        # Check if device still here

        # Perform measurement
        cmd_ext = cmd_formatter(self.cmd_dict['command_40r'])
        cmd_read = cmd_formatter(self.cmd_dict['command_02'])
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
            self.is_alive = False
            logger.error('Connection to Luxmeter was lost.')
            return

        try:
            if result[6] in ['1', '2', '3']:
                err = 'Switch off the CL-200A and then switch it back on'
                logger.error(f'Error {err}')
                raise ConnectionResetError(err)
            if result[6] == '5':
                logger.error('Measurement value over error. The measurement exceed the CL-200A measurement range.')
            if result[6] == '6':
                err = 'Low luminance error. Luminance is low, resulting in reduced calculation accuracy ' \
                      'for determining chromaticity'
                logger.error(f'{err}')
            # if result[7] == '6':
            #     err= 'Switch off the CL-200A and then switch it back on'
            #     raise Exception(err)
            if result[8] == '1':
                err = 'Battery is low. The battery should be changed immediately or the AC adapter should be used.'
                logger.error(err)
                raise ConnectionAbortedError(err)
            # Convert Measurement
            if result[9] == '+':
                signal = 1
            else:
                signal = -1
            lux_num = float(result[10:14])
            lux_pow = float(result[14]) - 4
            # lux = float(signal * lux_num * (10 ** lux_pow))
            lux = round(float(signal * lux_num * (10 ** lux_pow)), 3)

            # logger.debug(f"Returning {lux} luxes")
            return lux
        except IndexError as e:
            logger.debug(f"result: {result}")
            logger.error(e)
            exit(1)


if __name__ == "__main__":
    luxmeter = ChromaMeterKonica()
    timeout = 3

    while True:
        curr_lux = luxmeter.get_lux()

        if curr_lux:
            print(f"Reading: {curr_lux} LUX")
        else:
            print(f"Reading is {curr_lux}, sleeping 1 sec")
            print(f"Is alive: {luxmeter.is_alive}")
            sleep(1)
            timeout -= 1
            if not timeout:
                print("Timeout!")
                break

        # sleep(1)
