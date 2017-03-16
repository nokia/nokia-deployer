# Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).
import threading
import ConfigParser
import logging
import time
import traceback
import importlib

from vendor import beanstalkc

from . import api
from .worker import DeployerWorker, AsyncFetchWorker
from . import execution, mail, notification, websocket, database
from .withings import architect
from .withings.xmppnotifier import XmppHttpNotifier


def _import_class(class_path):
	parts = class_path.split(".")
	module = importlib.import_module(".".join(parts[:-1]))
	return getattr(module, parts[-1])


class WorkerSupervisor(object):
	"""Spawns and manages all the deployer workers.
	All workers must define the start (will be called in a new thread), stop (can be called from any thread),
	and name properties.
	"""

	# Main entry point for the deployer
	def __init__(self, config_path):
		logging.info("Using configuration file at {}".format(config_path))
		config = ConfigParser.ConfigParser()
		config.read(config_path)
		self.config_path = config_path
		database.init_db(config.get("database", "connection"))
		self.threads = []
		workers = self._build_workers(config)
		self._spawn_workers(workers)
		self._running = True
		self.lock = threading.Lock()
		t = threading.Thread(name="supervisor", target=self._monitor)
		t.daemon = True  # we can forcefully kill this thread
		t.start()

	def _build_notifiers(self, ws_worker, mail_sender, notify_mails, carbon_host, carbon_port, other_deployer_urls, deployer_username, deployer_token, provider):
		mail = notification.MailNotifier(mail_sender, notify_mails)
		websocket = notification.WebSocketNotifier(ws_worker)
		graphite = notification.GraphiteNotifier(carbon_host, carbon_port)
		remote = notification.RemoteDeployerNotifier(other_deployer_urls, deployer_username, deployer_token)
		more_notifiers = provider.build_notifiers()
		return notification.NotifierCollection(mail, websocket, graphite, remote, *more_notifiers), websocket

	def _build_integration_module(self, config):
		provider_class = _import_class(config.get('integration', 'provider'))
		return provider_class(config)

	def _build_workers(self, config):
		provider = self._build_integration_module(config)
		workers = []

		general_config = execution.GeneralConfig(
			base_repos_path=config.get("general", "local_repo_path"),
			haproxy_user=config.get("general", "haproxy_user"),
			haproxy_password=config.get("general", "haproxy_pass"),
			notify_mails=config.get('general', "notify_mails").split(","),
			mail_sender=config.get('mail', 'sender')
		)
		notify_mails = [s.strip() for s in config.get('general', 'notify_mails').split(",")]
		carbon_host = config.get('general', 'carbon_host')
		carbon_port = config.getint('general', 'carbon_port')
		deployers_urls = [s.strip() for s in config.get('cluster', 'deployers_urls').split(",")]
		other_deployers_urls = list(deployers_urls)
		other_deployers_urls.remove(config.get('cluster', 'this_deployer_url'))
		deployer_username = config.get('cluster', 'this_deployer_username')
		deployer_token = config.get('cluster', 'this_deployer_token')
		mail_sender = config.get('mail', 'sender')

		ws_worker = websocket.WebSocketWorker(port=config.getint('general', 'websocket_port'))
		workers.append(ws_worker)

		self.notifier, websocket_notifier = self._build_notifiers(
			ws_worker, mail_sender, notify_mails, carbon_host, carbon_port, other_deployers_urls, deployer_username, deployer_token, provider
		)

		for i in range(5):
			conn = beanstalkc.Connection(host=config.get('general', 'beanstalk_host'), port=11300)
			deployer_worker = DeployerWorker(conn, general_config, self.notifier, provider.detect_artifact, str(i))
			workers.append(deployer_worker)

		mail_worker = mail.MailWorker(config.get("mail", "mta"))
		workers.append(mail_worker)

		api_worker = api.ApiWorker(self.config_path, config, self.notifier, websocket_notifier, provider.authentificator())
		workers.append(api_worker)

		async_fetch_workers = [
			AsyncFetchWorker(
				config,
				self.notifier,
				"async-fetch-worker-{}".format(id_worker))
			for id_worker in range(1, 4)
		]

		for worker in async_fetch_workers:
			workers.append(worker)

		return workers

	def run(self):
		"""Blocks until exit() is called (from another thread)"""
		while self._running:
			time.sleep(1)
		self._exit()

	def _spawn_workers(self, workers):
		for w in workers:
			self._add_worker(w)
		self.notifier.dispatch(notification.Notification.deployer_started())

	def _add_worker(self, worker, *args, **kwargs):
		logging.debug("Starting worker {}".format(worker.name))
		t = threading.Thread(name=worker.name, target=worker.start, args=args, kwargs=kwargs)
		self.threads.append((t, worker))
		t.start()

	def exit(self):
		logging.info("Stopping the deployer (this can take a few seconds)...")
		self._running = False

	def _exit(self):
		with self.lock:
			self._running = False
			timeout = 10
			for _, worker in self.threads:
				try:
					worker.stop()
				except Exception as e:
					logging.error("Error when stoping the worker {}: {}".format(worker.name, traceback.format_exc(e)))
			for t, _ in self.threads:
				t.join(timeout)
			still_alive = [t for t, _ in self.threads if t.isAlive()]
			if len(still_alive) > 0:  # this was not a triumph
				for t in still_alive:
					logging.error("The thread '{}' is still alive after {} seconds (maybe because of a deployment in progress?). If you want to force the exit, send SIGKILL to the deployer daemon.".format(t.name, timeout))
			self.threads = []
			self.notifier.dispatch(notification.Notification.deployer_stopped())

	def _monitor(self):
		while self._running:
			with self.lock:
				for t, _ in self.threads:
					if not t.isAlive():
						logging.error("The thread {} died. You should examine the logs to find out what went wrong, and probably restart the deployer.".format(t.name))
			time.sleep(20)
