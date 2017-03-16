#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).
#
"""Main entry point for the deployer. Starts the web API and the background workers."""

import daemon
import os
import argparse
import traceback
import logging
import ConfigParser
import signal

from deployment import supervisor


def read_args():
	parser = argparse.ArgumentParser(description="Start the deployer daemon")
	parser.add_argument("-f", "--file", dest="settings_file", 
					 help="Path to the settings file", default="daemon.ini")
	# For now, only "restart" is supported
	parser.add_argument("command", choices=["restart"])
	args = parser.parse_args()
	return args


def setup_logging(config):
	log_file = config.get("general", "log_file")
	logging.basicConfig(filename=log_file, level=logging.DEBUG, format='%(asctime)s T%(thread)d [%(levelname)s] %(message)s')


class App(object):

	def __init__(self, config_path):
		self.config_path = config_path
		self.supervisor = None

	def start(self):
		config = ConfigParser.ConfigParser()
		config.read(self.config_path)
		setup_logging(config)
		logging.info("=== Starting the Deployer ===")
		try:
			self.supervisor = supervisor.WorkerSupervisor(self.config_path)
		except Exception as e:
			logging.error(traceback.format_exc(e))
			logging.error("Could not start the deployer!")
			return
		try:
			logging.info("Deployer initialization is complete")
			self.supervisor.run()
		except Exception as e:
			logging.error(traceback.format_exc(e))
		logging.info("** Deployer stopped **")

	def stop(self, signum, frame):
		self.supervisor.exit()


def main():
	args = read_args()
	config_file = os.path.abspath(args.settings_file)
	if not os.path.exists(config_file):
		logging.error("Could not find a configuration file at {}".format(config_file))
	app = App(config_file)
	with daemon.DaemonContext(signal_map={signal.SIGTERM: app.stop}):
		app.start()


if __name__ == '__main__':
	main()
