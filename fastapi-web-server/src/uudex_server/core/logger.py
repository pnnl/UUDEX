import logging
import sys

logger = logging.getLogger()

formatter = logging.Formatter(fmt="(asctime)s %(levelno)s %(module)s(%(lineno)d) - %(message)s")

stream_handler = logging.StreamHandler(sys.stdout)
# For http handler of logging
# http_handler = HTTPHandler(host="localhost:9000", url="/log/uudex", method="POST")
# http_handler.setFormatter(formatter)
# logger.addHandler(http_handler)

logger.addHandler(stream_handler)
logger.setLevel(logging.DEBUG)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
