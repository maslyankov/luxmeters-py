# coding=utf-8
"""
       Command type                              Command
 Read measurement data (X, Y, Z)                   01
 Read measurement data (EV, x, y)                  02
 Read measurement data (EV, u', v')                03
 Read measurement data (EV, TCP, Δuv)              08
 Read measurement data (EV, DW, P)                 15
 Set EXT mode; Take measurements                   40
 Read measurement data (X2, Y, Z) *                45
 Read coefficients for user calibration *          47
 Set coefficients for user calibration *           48
 Set PC connection mode                            54
 Set Hold status                                   55
"""

from serial import Serial, SerialException, PARITY_NONE, STOPBITS_ONE, EIGHTBITS, PARITY_EVEN, STOPBITS_TWO, SEVENBITS
from time import sleep

from serial_utils import list_ports, find_all_luxmeters
from logs import logger

SKIP_CHECK_LIST = True

cl200a_cmd_dict = {'command_01': '00011200',
                   'command_02': '00021200',
                   'command_03': '00031200',
                   'command_08': '00081200',
                   'command_15': '00151200',
                   'command_40': '004010  ',
                   'command_40r': '994021  ',  # New parameter due to cmd 40 is for set hold mode and read measurements
                   'command_45': '00451000',
                   'command_47a': '004711',
                   'command_47b': '004721',
                   'command_47c': '004731',
                   'command_48a': '004811  ',
                   'command_48b': '004821  ',
                   'command_48c': '004831  ',
                   'command_54': '00541   ',
                   'command_54r': '0054    ',
                   'command_55': '99551  0', }


def connection_konica(ser) -> bool:
    """Switch the CL-200A to PC connection mode. (Command "54").
    In order to perform communication with a PC, this command must be used to set the CL-200A to PC connection mode.
    """
    logger.info("Setting CL-200A to PC connection mode")
    # cmd_request = utils.cmd_formatter(self.cl200a_cmd_dict['command_54'])
    cmd_request = chr(2) + '00541   ' + chr(3) + '13\r\n'
    cmd_response = cmd_formatter(cl200a_cmd_dict['command_54r'])
    return_connection = None
    for i in range(2):
        write_serial_port(ser=ser, cmd=cmd_request, sleep_time=0.5)
        try:
            ser_read = ser.readline()
        except SerialException as e:
            logger.exception(e)
            return_connection = False

            return return_connection

        pc_connected_mode = ser_read.decode('ascii')
        ser.flushInput()
        ser.flushOutput()

        # Check that the response from the CL-200A is correct.
        if SKIP_CHECK_LIST:
            return_connection = True
        else:
            if cmd_response in pc_connected_mode:
                return_connection = True
            elif i == 0:
                continue
            else:
                return_connection = False

    return return_connection


def serial_port_luxmeter() -> str:
    """
    Find out which port is for each luxmeter
    :return: String containing COM port number
    """
    comports = find_all_luxmeters('FTDI')
    port = None
    ser = None
    for comport in comports:
        ser = connect_serial_port(port=comport, parity=PARITY_EVEN, bytesize=SEVENBITS, stopbits=STOPBITS_TWO)
        konica = connection_konica(ser=ser)
        if konica:
            port = comport
    try:
        ser.close()
    except AttributeError as e:
        logger.critical(e)
    return port


def connect_serial_port(port, baudrate=9600, parity=PARITY_NONE,
                        stopbits=STOPBITS_ONE, bytesize=EIGHTBITS, timeout=3) -> object:
    """
    Perform serial connection
    :param port: Int containing the COM port.
    :param baudrate: Baudrate
    :param parity: Parity bit
    :param stopbits: Stop Bit
    :param bytesize: Byte size
    :param timeout: Timeout to perform the connection.
    :return: Serial object.
    """
    ser = Serial(port=port,
                 baudrate=baudrate,
                 parity=parity,
                 stopbits=stopbits,
                 bytesize=bytesize,
                 timeout=timeout, )
    clean_obj_port(ser)
    return ser


def cmd_formatter(cmd) -> str:
    """
    Given a command, verify XOR ( Or Exclusive) byte per byte.
    :param cmd: String with a serial command.
    :return: Ascii with the entire command converted.
    """
    j = 0x0
    stx = chr(2)
    etx = chr(3)
    delimiter = '\r\n'
    to_hex = ([hex(ord(c)) for c in cmd + etx])
    for i in to_hex:
        j ^= int(i, base=16)
    bcc = str(j).zfill(2)
    return stx + cmd + etx + bcc + delimiter


def write_serial_port(ser, cmd, sleep_time, obj=None) -> None:
    """
    Writes in any serial port.
    :param ser: Serial object
    :param cmd: String containing the command
    :param sleep_time: Int or float containing the sleep time.
    :param obj: Luxmeter object so we can pass it isAlive False if sth happens
    :return: None
    """
    try:
        ser.write(cmd.encode())
    except SerialException:
        if obj:
            obj.isAlive = False
        logger.error("Connection to Luxmeter was lost.")
        return

    sleep(sleep_time)
    ser.reset_input_buffer()


def check_measurement(result) -> None:
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


def calc_lux(result) -> float:
    if result[9] == '+':
        signal = 1
    else:
        signal = -1
    lux_num = float(result[10:14])
    lux_pow = float(result[14]) - 4

    # lux = float(signal * lux_num * (10 ** lux_pow))
    lux = round(float(signal * lux_num * (10 ** lux_pow)), 3)

    return lux


def clean_obj_port(obj) -> None:
    """ Perform object buffer cleaning """
    obj.close()
    if not obj.isOpen():
        obj.open()
