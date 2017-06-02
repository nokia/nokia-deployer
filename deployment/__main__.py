#! /usr/bin/env python
# -*- coding: utf-8 -*-

import os
import argparse
from logging import getLogger
import signal

from deployment import supervisor
from deployment.log import configure_logging

logger = getLogger(__name__)


def read_args():
    parser = argparse.ArgumentParser(description="Start the deployer daemon")
    parser.add_argument("-f", "--file", dest="settings_file",
                        help="Path to the settings file", default="/etc/deployer/deployer.ini")
    # For now, only "run" is supported
    parser.add_argument("command", choices=["run"])
    args = parser.parse_args()
    return args


class App(object):

    def __init__(self, config_path):
        self.config_path = config_path
        self.supervisor = None

    def start(self):
        logger.info("=== Starting the Deployer ===")
        try:
            self.supervisor = supervisor.WorkerSupervisor(self.config_path)
        except Exception:
            logger.exception("Could not start the deployer!")
            return
        try:
            logger.info("Deployer initialization is complete")
            self.supervisor.run()
        except Exception:
            logger.exception("Fatal error, the deployer will stop.")
        logger.info("** Deployer stopped **")

    def stop(self, signum, frame):
        logger.info("Received SIGTERM, will exit after cleanup.")
        if self.supervisor is not None:
            self.supervisor.exit()


def main():
    configure_logging()
    args = read_args()
    config_file = os.path.abspath(args.settings_file)
    if not os.path.exists(config_file):
        logger.error("Could not find a configuration file at {}".format(config_file))
    app = App(config_file)
    signal.signal(signal.SIGTERM, app.stop)
    signal.signal(signal.SIGINT, app.stop)
    app.start()


if __name__ == '__main__':
    main()
