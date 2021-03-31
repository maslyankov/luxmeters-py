import logging
import sys

# Create a custom logger
logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

# - Create handlers
# Console log
c_handler = logging.StreamHandler()
c_handler.setLevel(getattr(logging, "DEBUG"))

c_format = logging.Formatter("%(asctime)s;%(levelname)s;%(message)s",
                              "%Y-%m-%d %H:%M:%S")
c_handler.setFormatter(c_format)

# File
# f_handler = logging.FileHandler(constants.LOG_FILE)
# f_handler.setLevel(getattr(logging, constants.LOG_LEVEL_FILE))
# f_format = logging.Formatter(f'%(asctime)s > [%(process)7d - {log_prefix}] [%(levelname)s]: %(message)s',
#                              '%d-%b-%y %H:%M:%S')
# f_handler.setFormatter(f_format)

# Add handlers to the logger
logger.addHandler(c_handler)
# logger.addHandler(f_handler)

logger.info('App started!')
