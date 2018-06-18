# Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).
# -*- coding: utf-8 -*-

import json
from logging import getLogger
import requests
import time
import urllib3
import threading


from . import database, samodels as m

try:
    from queue import PriorityQueue, Empty
except ImportError:
    from Queue import PriorityQueue, Empty

logger = getLogger(__name__)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

UPDATE_QUEUE = PriorityQueue(maxsize=0)
EVENTS = {}
lock = threading.Lock()



def add_cluster_to_update(cluster_id, priority):
    UPDATE_QUEUE.put((priority, cluster_id))

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


# TODO : enable routes customization ?
class InventoryHost(object):
    cluster_queue = PriorityQueue(maxsize=0)
    block = False

    def __init__(self, host, authentificator):
        self.last_remote_update = None
        self.last_update = None
        self.host = host
        self.authentificator = authentificator

    def check_last_update(self):
        hmac_header = self.authentificator.get_token_header()
        res = requests.get("{}/api/last_update".format(self.host), headers=hmac_header, verify=False)
        try:
            payload = res.json()
            if "last_update" not in payload:
                raise ValueError("bad response from inventory")
            hash = payload["last_update"].encode('utf8')
            if hash != self.last_update:
                return hash
            else:
                return None
        except Exception as e:
            print e.message # TODO : handle errors

    def update_remote_timestamp(self, ts):
        self.last_remote_update = ts

    def update_timestamp(self):
        if self.last_remote_update != self.last_update:
            self.last_update = self.last_remote_update
            logger.info("[InventoryHost] local hash updated and up to date with inventory")

    def get_clusters(self):
        hmac_header = self.authentificator.get_token_header()
        clusters_json = requests.get("{}/api/clusters".format(self.host), headers=hmac_header, verify=False)
        try:
            clusters = clusters_json.json()
            if 'clusters' not in clusters:
                raise Exception('No data returned from inventory')
            i = 0;
            for cluster in clusters['clusters']:
                cluster['inventory_key'] = cluster['id']
                cluster['id'] = i
                i += 1
                for server in cluster['servers']:
                    server['inventory_key'] = server['id']
            return clusters['clusters']
        except Exception as e:
            print e.message
            return None #TODO: handle errors

    def get_cluster(self, inventory_key):
        hmac_header = self.authentificator.get_token_header()
        raw = requests.get("%s/api/cluster/%s" % (self.host, inventory_key),
                               headers=hmac_header, verify=False)
        try:
            res = raw.json()
            if res['status'] > 0 or len(res['cluster']) == 0:
                return None, []
            cluster = res['cluster']
            servers = []
            if "servers" in cluster:
                for server in cluster["servers"]:
                    servers.append(m.Server(inventory_key=server["id"], name=server["name"], activated=server["activated"]))
            cluster = m.Cluster(inventory_key=inventory_key, name=cluster['name'])
            return cluster, servers
        except Exception as e:
            print e.message # TODO : handle errors
            return None, None

    # useless for now
    def is_blocked(self):
        return self.block


class AsyncInventoryWorker(object):
    """DESCRIPTION HERE."""

    refresh_duration = 2

    def __init__(self, inventory_host):
        self._running = True
        self.inventory_host = inventory_host
        self.block = False # TODO : check all deployments in progress
        self.errors = []

    def start(self):
        while self._running:
            try:
                _, cluster_id = self.get_cluster_to_update(block=True, timeout=self.refresh_duration)
                if cluster_id == 0:
                    continue
            except Empty:
                if not self.errors:
                    self.inventory_host.update_timestamp()
                continue

            try:
                updated = self.update_cluster(cluster_id)
                if updated == 0:
                    logger.info("cluster id:{} updated from inventory".format(cluster_id))
                    clear_event(cluster_id)
                    if cluster_id in self.errors:
                        self.errors.remove(cluster_id)
                elif updated == 1:
                    logger.info("cluster id:{} deleted".format(cluster_id))
                    if cluster_id in self.errors:
                        self.errors.remove(cluster_id)
                elif updated == 2:
                    logger.error("[AsyncInventoryWorker] error in update of cluster id:{}".format(cluster_id))
                    if cluster_id not in self.errors:
                        self.errors.append(cluster_id)
            except:
                if cluster_id not in self.errors:
                    self.errors.append(cluster_id)
                logger.exception("[AsyncInventoryWorker] unhandled error when updating cluster: ")

    def stop(self):
        self._running = False

    def get_cluster_to_update(self, block=False, timeout=0):
        if self.block is False:
            return UPDATE_QUEUE.get(block=block, timeout=timeout)
        else:
            time.sleep(timeout)
            return 0

    def update_cluster(self, cluster_id):
        try:
            with database.session_scope() as session:
                cluster = session.query(m.Cluster).get(cluster_id)
                if cluster is None:
                    logger.error("[AsyncInventoryWorker] error when updating cluster, cluster {} not found in db".format(cluster_id))
                    return 2
                distant_cluster, servers = self.inventory_host.get_cluster(cluster.inventory_key)
                logger.info("updating cluster {}".format(cluster.name))
                if distant_cluster is None:
                    if servers is not None:
                        for asso in cluster.servers:
                            session.delete(asso)
                        session.commit()
                        for asso in cluster.environments:
                            session.delete(asso)
                        session.commit()
                        session.delete(cluster)
                        return 1
                    else:
                        return 2
                cluster.name = distant_cluster.name
                cluster_servers = {}
                for server_asso in cluster.servers:
                    cluster_servers[server_asso.server_def.inventory_key] = server_asso
                for distant_server in servers:
                    created = False
                    server = session.query(m.Server).filter_by(inventory_key=distant_server.inventory_key).one_or_none()
                    if server is None:
                        # get_or_create only for transition: find servers without inventory_key
                        server, created = database.get_or_create(session, m.Server, distant_server,
                                                             name=distant_server.name)
                    if not created:
                        server.inventory_key = distant_server.inventory_key
                        server.name = distant_server.name
                        server.activated = distant_server.activated
                    else:
                        logger.info("server {} created from inventory".format(server.name))
                    if server.inventory_key in cluster_servers:
                        current_server_asso = cluster_servers.pop(server.inventory_key)
                    else:
                        current_server_asso = m.ClusterServerAssociation(cluster_def=cluster, server_def=server)
                        logger.info("server {} added in cluster {}".format(server.name, cluster.name))

                for _, asso in cluster_servers.iteritems():
                    name = asso.server_def.name
                    session.delete(asso)
                    logger.info("server {} was remove of cluster {}".format(name, cluster.name))
            return 0
        except Exception as e:
            logger.exception('[AsyncInventoryWorker] '+e.message)
            return 2

    @property
    def name(self):
        return "async-inventory-updater"


class InventoryWorker(object):
    """DESCRIPTION HERE."""

    def __init__(self, inventory_host, frequency):
        self._running = True
        self.inventory_host = inventory_host
        self.steps = int(frequency*60/5)
        self.retries = 0

    def start(self):
        self._running = True
        while self._running:
            try:
                logger.info("[inventory-synchronizer] inventory worker waked up")
                last_update = self.inventory_host.check_last_update()
                if last_update is not None:
                    logger.info("[inventory-synchronizer] deployer [{}] : inventory [{}]".format(self.inventory_host.last_remote_update, last_update))
                    with database.session_scope() as session:
                        clusters = session.query(m.Cluster).filter(m.Cluster.inventory_key != None).all()
                        logger.info("[inventory-synchronizer] updating {} clusters...".format(len(clusters)))
                        for cluster in clusters:
                            add_cluster_to_update(cluster.id, 2)
                    self.inventory_host.update_remote_timestamp(last_update)
                    if self.retries > 5:
                        logger.info("[inventory-synchronizer] full sync often run, it might be a error with a cluster: see logs to more info.")
                    self.retries += 1
                else:
                    logger.info("[inventory-synchronizer] up to date, inventory hash: {}".format(self.inventory_host.last_remote_update))
                    self.retries = 0
            except Exception as e:
                logger.error(e)
            for i in range(self.steps):
                if self._running is False:
                    break
                time.sleep(5)

    def stop(self):
        self._running = False

    @property
    def name(self):
        return "inventory-synchronizer"
