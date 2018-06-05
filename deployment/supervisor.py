# Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).
import ConfigParser
from functools import wraps
import importlib
from logging import getLogger
import os
import threading
import time

import beanstalkc

from . import api
from . import execution, mail, notification, websocket, database
from .instancehealth import InstanceHealth
from .log import configure_logging
from .checkreleases import CheckReleasesWorker
from .cleaner import CleanerWorker
from .worker import DeployerWorker, AsyncFetchWorker
from .inventory import InventoryHost, InventoryWorker, AsyncInventoryWorker

logger = getLogger(__name__)


def _import_class(class_path):
    parts = class_path.split(".")
    module = importlib.import_module(".".join(parts[:-1]))
    return getattr(module, parts[-1])


class WorkerSupervisor(object):
    """Spawns and manages all the deployer workers.

    A worker is a class with the following interface:
    * the `start` method must be a blocking method, and will be called in a new thread.
      If this method exits by raising an exception, it will be called again.
    * the `stop` method can be called from any thread and must cause the `start` method to return.
    * the `name` property describes the worker
    """

    # Main entry point for the deployer
    def __init__(self, config_path):
        self.threads = []
        self._health = InstanceHealth()
        self._running = True
        self.lock = threading.Lock()

        configure_logging()

        logger.info("Using configuration file at {}".format(config_path))
        if not os.path.isfile(config_path):
            raise ValueError("Can not read the configuration file at {}".format(config_path))
        config = ConfigParser.ConfigParser()
        config.read(config_path)
        self.config_path = config_path

        database.init_db(config.get("database", "connection"))

        workers = self._build_workers(config)
        self._spawn_workers(workers)

        t = threading.Thread(name="supervisor", target=self._monitor)
        t.daemon = True  # we can forcefully kill this thread
        t.start()

    def _restart_function_on_exception(self, f, context):
        """If the callable f raises an exception, log the exception then call f again.

        This function will not propagate exceptions, and will return only when f returns without raising
        an exception.
        This is useful to ensure that a worker thread does not die.
        The function will not be called again is the deployer is exiting.

        Args:
            f (callable)
            context (str): will be displayed in log messages if an exception occurs
        """

        @wraps(f)
        def wrapped(*args, **kwargs):
            while self._running:
                try:
                    out = f(*args, **kwargs)
                    if self._running:
                        logger.error("A worker main function returned while the deployer is still running, "
                                     "this is a bug ({}).".format(context))
                    return out
                except Exception:
                    logger.exception("Unhandled exception ({}), will restart the worker.".format(context))
                time.sleep(30)

        return wrapped

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

        # START FEATURE FLAG: inventory
        self.inventory_host = None
        if config.getboolean('inventory', 'activate') is True:
            self.inventory_host = InventoryHost(config.get('inventory', 'api_host'), config.get('inventory', 'hmac_key'), config.get('inventory', 'hmac_inventory_username'), config.get('inventory', 'hmac_local_username'))
            if config.has_option('inventory', 'update_frequency'):
                inventory_frequency = config.getint('inventory', 'update_frequency')
            else:
                inventory_frequency = 60
            inventory_worker = InventoryWorker(self.inventory_host, inventory_frequency)
            workers.append(inventory_worker)

            async_synchronizer = AsyncInventoryWorker(self.inventory_host)
            workers.append(async_synchronizer)
        # END FEATURE FLAG

        api_worker = api.ApiWorker(self.config_path, config, self.notifier, websocket_notifier, provider.authentificator(), self._health, self.inventory_host)
        workers.append(api_worker)

        if config.has_option("general", "check_releases_frequency"):
            frequency = config.getint("general", "check_releases_frequency")
            if frequency > 0:
                ignore_envs = config.get("general", "check_releases_ignore_environments").split(",") if config.has_option("general", "check_releases_ignore_environments") else []
                check_releases_workers = CheckReleasesWorker(frequency, ignore_envs, self._health)
                workers.append(check_releases_workers)

        async_fetch_workers = [
            AsyncFetchWorker(
                config,
                self.notifier,
                "async-fetch-worker-{}".format(id_worker))
            for id_worker in range(1, 4)
        ]

        for worker in async_fetch_workers:
            workers.append(worker)

        workers.append(CleanerWorker(general_config.base_repos_path))

        return workers

    def run(self):
        """Blocks until exit() is called (from another thread)"""
        try:
            while self._running:
                time.sleep(1)
        finally:
            self._exit()

    def _spawn_workers(self, workers):
        for w in workers:
            self._start_worker(w)
        self.notifier.dispatch(notification.Notification.deployer_started())

    def _start_worker(self, worker, *args, **kwargs):
        t = threading.Thread(name=worker.name,
                             target=self._restart_function_on_exception(
                                 worker.start,
                                 context="in worker {}".format(worker.name)
                             ),
                             args=args,
                             kwargs=kwargs)
        self.threads.append((t, worker))
        t.start()
        logger.debug("Started worker {} (tid {})".format(worker.name, t.ident))

    def exit(self):
        logger.info("Stopping the deployer (this can take a few seconds)...")
        self._running = False

    def _exit(self):
        with self.lock:
            self._running = False
            timeout = 10
            for t, worker in self.threads:
                try:
                    logger.debug("Stopping worker {} (tid {})".format(worker.name, t.ident))
                    worker.stop()
                except Exception:
                    logger.exception("Error when stopping the worker {}:".format(worker.name))
            for t, worker in self.threads:
                logger.debug("Waiting for the worker {} to exit (tid {})...".format(worker.name, t.ident))
                t.join(timeout)
            still_alive = [t for t, _ in self.threads if t.isAlive()]
            if len(still_alive) > 0:  # this was not a triumph
                for t in still_alive:
                    logger.error("The thread '{}' is still alive after {} seconds (maybe because of a deployment in progress?). If you want to force the exit, send SIGKILL to the deployer process.".format(t.name, timeout))
            else:
                logger.info("All workers gracefully terminated.")
            self.threads = []

    def _monitor(self):
        while self._running:
            with self.lock:
                for t, _ in self.threads:
                    if not t.isAlive():
                        self._health.add_degraded("workers", "a deployer thread died (see logs for details)")
                        logger.error(
                            "The thread {} (tid {}) died. You should examine the logs to find out "
                            "what went wrong, and probably restart the deployer."
                            .format(t.name, t.ident))
            time.sleep(20)
