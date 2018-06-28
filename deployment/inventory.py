# Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).
# -*- coding: utf-8 -*-
from logging import getLogger
from requests import RequestException
import time
import random

from sqlalchemy.orm.exc import NoResultFound

from . import database, samodels as m

try:
    from queue import PriorityQueue, Empty
except ImportError:
    from Queue import PriorityQueue, Empty

logger = getLogger(__name__)

update_queue = PriorityQueue(maxsize=0)


def add_cluster_to_update(cluster_id, priority):
    update_queue.put((priority, cluster_id))


def add_cluster(inventory_cluster, inventory_servers):
    """
    function called to add a new cluster with data from the inventory.
    A new cluster object is created and linked to its servers.
    If a server doesn't exist in db, it will create them with data from params, otherwise it will UPDATE them with data.
    Each server is found by inventory_key first, and by name if the inventory_key returned nothing. The search by
    name is done to avoid duplicated servers with the same name (one from the legacy db and another one created with
    the inventory.
    :param inventory_cluster: data of the new cluster, pattern: {'inventory_key':,'name':,'updated_at':}
    :param inventory_servers: servers linked to the new cluster, pattern: { 'inventory_key':,'name':,'activated':}
    :return: "created" if succeeded
    """
    cluster_key = inventory_cluster['inventory_key']
    with database.session_scope() as session:
        cluster = m.Cluster(**inventory_cluster)
        for distant_server in inventory_servers:
            server = database.get_and_update(session, m.Server, distant_server, inventory_key=distant_server['inventory_key'])
            if server is None:
                # upsert only for transition: find servers without inventory_key
                server = database.upsert(session, m.Server, distant_server, name=distant_server['name'])
            m.ClusterServerAssociation(cluster_def=cluster, server_def=server)
            logger.info("server {} added in cluster {}".format(server.name, cluster.name))
        session.add(cluster)
    return "created"


def update_cluster(inventory_cluster, inventory_servers):
    """
    function used to update a cluster with data from the inventory.
    it is called when a full update is running or when a cluster is modified. Modified means:
    - cluster params changed,
    - server(s) added or removed in the cluster
    - linked servers params updated (there is no route to notify the update of a server)
    If a server doesn't exist in db, it will create them with data from params, otherwise it will UPDATE them with data.
    Each server is found by inventory_key first, and by name if the inventory_key returned nothing. The search by
    name is done to avoid duplicated servers with the same name (one from the legacy db and another one created with
    the inventory.
    :param inventory_cluster: data of the new cluster, pattern: {'inventory_key':,'name':,'updated_at':}
    :param inventory_servers: servers linked to the new cluster, pattern: { 'inventory_key':,'name':,'activated':}
    :return: "updated" if succeeded
    """
    cluster_key = inventory_cluster['inventory_key']
    with database.session_scope() as session:
        cluster = database.get_and_update(session, m.Cluster, inventory_cluster, inventory_key=cluster_key)
        old_servers = dict((server.server_def.inventory_key, server) for server in cluster.servers)
        for distant_server in inventory_servers:
            server = database.get_and_update(session, m.Server, distant_server, inventory_key=distant_server['inventory_key'])
            if server is None:
                # upsert only for transition: find servers without inventory_key
                server = database.upsert(session, m.Server, distant_server, name=distant_server['name'])
            if server.inventory_key in old_servers:
                old_servers.pop(server.inventory_key)
            else:
                m.ClusterServerAssociation(cluster_def=cluster, server_def=server)
                logger.info("server {} added in cluster {}".format(server.name, cluster.name))
        for _, asso in old_servers.iteritems():
            name = asso.server_def.name
            session.delete(asso)
            logger.info("server {} was removed from cluster {}".format(name, cluster.name))
    return "updated"


def delete_cluster(cluster_key):
    try:
        with database.session_scope() as session:
            cluster = session.query(m.Cluster).filter_by(inventory_key=cluster_key).one()
            for server_asso in cluster.servers:
                session.delete(server_asso)
            for env_asso in cluster.environments:
                session.delete(env_asso)
            session.refresh(cluster)
            session.delete(cluster)
            return "deleted"
    except NoResultFound:
        return "handled: already deleted (maybe by another instance of the deployer)"


class InventoryError(Exception):

    pass


class AsyncInventoryWorker(object):
    """The clusters updater. Check if updates are pending, handle errors, change last_update fields."""

    refresh_duration = 2

    def __init__(self, inventory_host):
        self._running = True
        self.inventory_host = inventory_host
         # TODO : check all deployments in progress

    def start(self):
        while self._running:
            cluster_key = self.get_cluster_in_queue(block=True, timeout=self.refresh_duration)
            if cluster_key is not None:
                try:
                    self.sync_cluster(cluster_key)
                except Exception as e:
                    self.log_error(cluster_key, e.message)
                    logger.exception(e)

    def sync_cluster(self, cluster_key):
        status, inventory_cluster, inventory_servers = self.inventory_host.get_cluster(cluster_key)
        with database.session_scope(expire_on_commit=False) as session:
            cluster_already_in_db = session.query(m.Cluster).filter_by(inventory_key=cluster_key).count() > 0
        if status == "existing":
            if not cluster_already_in_db:
                res = add_cluster(inventory_cluster, inventory_servers)
            else:
                res = update_cluster(inventory_cluster, inventory_servers)
        elif status == "deleted":
            res = delete_cluster(cluster_key)
        self.log_success(cluster_key, res)

    def get_cluster_in_queue(self, block, timeout=0):
        try:
            _, cluster_id = update_queue.get(block=block, timeout=timeout)
            return cluster_id
        except Empty:
            return None

    def log_error(self, cluster_id, message="unknown error"):
        logger.error("[AsyncInventoryWorker] error when updating cluster {}: {}".format(cluster_id, message))

    def log_success(self, cluster_id, message="updated"):
        logger.info("[AsyncInventoryWorker] cluster {}: successfully {}".format(cluster_id, message))

    def stop(self):
        self._running = False

    @property
    def name(self):
        return "async-inventory-updater"


class InventoryUpdateChecker(object):
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
        self.successive_resync = 0

    def start(self):
        self._running = True
        self.delay_start()
        while self._running:
            self.log('info', 'inventory worker woke up')
            for i in range(self.steps):
                if self._running is False:
                    break
                if i == 0:
                    if not update_queue.empty():
                        self.log('info', 'an update is in progress, retry in 5 seconds')
                        time.sleep(5)
                        break
                    try:
                        updated = self.inventory_host.is_up_to_date()
                        if not updated:
                            inventory_clusters = self.inventory_host.get_clusters()
                            with database.session_scope(expire_on_commit=False) as session:
                                database_clusters = session.query(m.Cluster).filter(m.Cluster.inventory_key.notin_(inventory_clusters)).all()
                            for cluster in database_clusters:
                                if cluster.inventory_key is not None:
                                    inventory_clusters.insert(0, cluster.inventory_key)
                            self.log('info', "syncing {} clusters...".format(len(inventory_clusters)))
                            for cluster in inventory_clusters:
                                add_cluster_to_update(cluster, 1) # 1 is the lowest priority

                            self.successive_resync += 1
                            if self.successive_resync > 5:
                                self.log('warning', "full sync often run, it might be a error with a cluster: see logs for more info.")
                        else:
                            self.log('info', "up to date")
                            self.successive_resync = 0
                    except RequestException as e:
                        self.log('error', 'communication issues with the inventory. Retry in {} minutes'.format(self.frequency))
                        logger.exception(e)
                time.sleep(5)

    def delay_start(self):
        """
        The start of this worker is randomly delayed to avoid 2 instances of the deployer to perform full updates
        simultaneously.
        """
        sleep_time = random.randrange(self.frequency * 60)
        print sleep_time
        i = 0
        while i < (sleep_time/5) and self._running:
            time.sleep(5)
            i += 1

    def log(self, log_type, message):
        message = "[" + self.name + "] " + message
        if log_type == 'info':
            logger.info(message)
        if log_type == 'warning':
            logger.warning(message)
        if log_type == 'error':
            logger.error(message)

    def stop(self):
        self._running = False

    @property
    def name(self):
        return "inventory-update-checker"
