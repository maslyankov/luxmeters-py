import serial.tools.list_ports as serial_list_ports
from logs import logger


def list_ports() -> list():
    ports = serial_list_ports.comports()
    ret_ports = list()

    for port in sorted(ports):
        port_dict = dict()
        for port_item in vars(port):
            port_dict[f"{port_item}"] = getattr(port, port_item)

        ret_ports.append(
            port_dict
        )

    return ret_ports


def find_all_luxmeters(keyword) -> list:
    """ Get all lux meters connected into PC."""
    logger.info("Looking for luxmeters...")
    found_ports = list_ports()

    if found_ports:
        ret = [p["device"] for p in found_ports if "manufacturer" in p and keyword in p["manufacturer"]]

        logger.debug(f"Found luxmeters: {ret}")
        return ret
    else:
        return
