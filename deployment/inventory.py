# Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).
# -*- coding: utf-8 -*-
# import hashlib
from logging import getLogger
from requests import RequestException
import time
import threading

from sqlalchemy.orm.exc import NoResultFound

from . import database, samodels as m

try:
    from queue import PriorityQueue, Empty
except ImportError:
    from Queue import PriorityQueue, Empty

logger = getLogger(__name__)

update_queue = PriorityQueue(maxsize=0)
EVENTS = {}
lock = threading.Lock()


def add_cluster_to_update(cluster_id, priority):
    update_queue.put((priority, cluster_id))


def add_event(id):
    lock.acquire()
    if id not in EVENTS:
        EVENTS[id] = threading.Event()
    else:
        EVENTS[id].clear()
    lock.release()
    return EVENTS[id]


def clear_event(id):
    lock.acquire()
    if id in EVENTS:
        EVENTS[id].set()
    lock.release()


class InventoryError(Exception):
    """DESCRIPTION HERE"""

    def __init__(self, message):
        self.message = message

    def __str__(self):
        return self.message


class AsyncInventoryWorker(object):
    """The clusters updater. Check if updates are pending, handle errors, change last_update fields."""

    refresh_duration = 2

    def __init__(self, inventory_host):
        self._running = True
        self.inventory_host = inventory_host
        self.already_done = True
         # TODO : check all deployments in progress

    def start(self):
        while self._running:
            cluster_key = self.get_cluster_in_queue(block=True, timeout=self.refresh_duration)
            if cluster_key is not None:
                self.sync_cluster(cluster_key)

    def sync_cluster(self, cluster_key):
        try:
            with database.session_scope() as session:
                cluster = session.query(m.Cluster).filter_by(inventory_key=cluster_key).one_or_none()
                status, inventory_cluster, inventory_servers = self.inventory_host.get_cluster(cluster_key) #TODO : + return event
                if status == "existing":
                    if cluster is None:
                        self.add_cluster(inventory_cluster, inventory_servers)
                    else:
                        self.update_cluster(inventory_cluster, inventory_servers)
                elif status == "deleted":
                    self.delete_cluster(cluster_key)
        except Exception as e:
            logger.exception(e)
            raise e

    def add_cluster(self, inventory_cluster, inventory_servers):
        cluster_key = inventory_cluster['inventory_key']
        try:
            with database.session_scope() as session:
                cluster = m.Cluster(**inventory_cluster)
                for distant_server in inventory_servers:
                    server = database.get_and_update(session, m.Server, distant_server, inventory_key=distant_server['inventory_key'])
                    if server is None:
                        # get_or_create only for transition: find servers without inventory_key
                        server = database.create_or_update(session, m.Server, distant_server, name=distant_server['name'])
                    m.ClusterServerAssociation(cluster_def=cluster, server_def=server)
                    logger.info("server {} added in cluster {}".format(server.name, cluster.name))
                session.add(cluster)
        except InventoryError as e:
            self.log_error(cluster_key, e.message)
            logger.exception(e)
        except Exception as e:
            self.log_error(cluster_key, e.message)
            raise e
        else:
            self.log_success(cluster_key, "created")

    def update_cluster(self, inventory_cluster, inventory_servers):
        cluster_key = inventory_cluster['inventory_key']
        try:
            with database.session_scope() as session: # TODO :modif
                cluster = database.get_and_update(session, m.Cluster, inventory_cluster, inventory_key=cluster_key)
                old_servers = dict((server.server_def.inventory_key, server) for server in cluster.servers)
                for distant_server in inventory_servers:
                    server = database.get_and_update(session, m.Server, distant_server, inventory_key=distant_server['inventory_key'])
                    if server is None:
                        # get_or_create only for transition: find servers without inventory_key
                        server = database.create_or_update(session, m.Server, distant_server, name=distant_server['name'])
                    if server.inventory_key in old_servers:
                        old_servers.pop(server.inventory_key)
                    else:
                        m.ClusterServerAssociation(cluster_def=cluster, server_def=server)
                        logger.info("server {} added in cluster {}".format(server.name, cluster.name))
                for _, asso in old_servers.iteritems():
                    name = asso.server_def.name
                    session.delete(asso)
                    logger.info("server {} was remove of cluster {}".format(name, cluster.name))
        except InventoryError as e:
            self.log_error(cluster_key, e.message)
            logger.exception(e)
        except Exception as e:
            self.log_error(cluster_key, e.message)
            raise e
        else:
            self.log_success(cluster_key)

    def delete_cluster(self, cluster_key):
        try:
            with database.session_scope() as session:
                cluster = session.query(m.Cluster).filter_by(inventory_key=cluster_key).one()
                for asso in cluster.servers:
                    session.delete(asso)
                session.commit()
                for asso in cluster.environments:
                    session.delete(asso)
                session.commit()
                session.delete(cluster)
        except NoResultFound:
            self.log_success(cluster_key, "handled: already deleted (maybe by another instance of the deployer)")
        except Exception as e:
            self.log_error(cluster_key, e.message)
            logger.exception(e)
            raise e
        else:
            self.log_success(cluster_key, "deleted")

    def get_cluster_in_queue(self, block, timeout=0):
        try:
            _, cluster_id = update_queue.get(block=block, timeout=timeout)
            self.already_done = False
            return cluster_id
        except Empty:
            if self.already_done is False:
                # self.inventory_host.is_up_to_date()
                self.already_done = True
            return None

    def log_error(self, cluster_id, message="unknown error"):
        logger.error("[AsyncInventoryWorker] error when updating cluster {}: {}".format(cluster_id, message))

    def log_success(self, cluster_id, message="updated"):
        clear_event(cluster_id)
        logger.info("[AsyncInventoryWorker] cluster {}: successfully {}".format(cluster_id, message))

    def stop(self):
        self._running = False

    @property
    def name(self):
        return "async-inventory-updater"


class InventoryWorker(object):
    """
    Worker launched each _frequency_ minutes to check if the clusters are up to date.
    Nothing is done if the update hashes are the same.
    Otherwise, it adds all the clusters in updating queue.
    """

    def __init__(self, inventory_host, frequency):
        self._running = True
        self.inventory_host = inventory_host
        self.frequency = frequency
        self.steps = int(frequency*60/5)
        self.retries = 0
        self.priority = 1

    def start(self):
        self._running = True
        while self._running:
            logger.info("[inventory-synchronizer] inventory worker waked up")
            if update_queue.empty():
                self.priority = 1
            else:
                self.priority = 2 # be sure all the remaining clusters will update
            try:
                updated = self.inventory_host.is_up_to_date()
                if not updated:
                    try:
                        inventory_clusters = self.inventory_host.get_clusters()
                    except RequestException as e:
                        logger.exception(e)
                        continue
                    logger.info("[inventory-synchronizer] syncing {} clusters...".format(len(inventory_clusters)))
                    for cluster in inventory_clusters:
                        add_cluster_to_update(cluster, self.priority) # 2 is the lowest priority
                    inventory_clusters.append('')
                    with database.session_scope() as session:
                        database_clusters = session.query(m.Cluster).filter(m.Cluster.inventory_key.notin_(inventory_clusters)).all()
                        for cluster in database_clusters:
                            add_cluster_to_update(cluster.inventory_key, self.priority)
                    self.add_retry()
                else:
                    self.flush_retries()
            except RequestException as e:
                logger.error('communication issues with the inventory. Retry in {} minutes'.format(self.frequency))
                logger.exception(e)

            for i in range(self.steps):
                if self._running is False:
                    break
                time.sleep(5)

    def add_retry(self):
        self.retries += 1
        if self.retries > 5:
            logger.info("[inventory-synchronizer] full sync often run, it might be a error with a cluster: see logs for more info.")

    def flush_retries(self):
        logger.info("[inventory-synchronizer] up to date")
        self.retries = 0

    def stop(self):
        self._running = False

    @property
    def name(self):
        return "inventory-synchronizer"
