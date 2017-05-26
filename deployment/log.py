import logging
from logging import getLogger
from logging.handlers import SysLogHandler


def configure_logging():
    # Use syslog compatible format
    formatter = logging.Formatter(
        "app.deployer[%(process)d]: [%(asctime)s] [%(thread)-5d] [%(levelname)7s] --- %(message)s      (%(name)s:%(lineno)d)", "%Y-%m-%d %H:%M:%S"   # noqa
    )
    handlers = [
        logging.StreamHandler(),
        SysLogHandler('/dev/log')
    ]
    getLogger().handlers = []
    for handler in handlers:
        getLogger().addHandler(handler)
        handler.setFormatter(formatter)
    getLogger().setLevel(logging.DEBUG)
    # we don't care when the urllib is making new TCP connections
    # so silence messages like "establishing new connection to..."
    getLogger("requests.packages.urllib3.connectionpool").setLevel(logging.ERROR)
    # we don't care when we open or close websockets
    getLogger("ws4py").setLevel(logging.ERROR)
    # we don't care about cherrypy answering 101 to websocket upgrade requests
    getLogger("cherrypy.access").setLevel(logging.ERROR)
    # we don't care about every git command executed (provided it was successful of course)
    getLogger("git.cmd").setLevel(logging.INFO)
