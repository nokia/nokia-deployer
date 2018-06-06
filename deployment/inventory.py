# Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).
# -*- coding: utf-8 -*-

import json
from logging import getLogger
import re
import requests
import time
import urllib3

from . import database, samodels as m
from .HMAClib import HMAC

try:
    from queue import PriorityQueue, Empty
except ImportError:
    from Queue import PriorityQueue, Empty

logger = getLogger(__name__)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

UPDATE_QUEUE = PriorityQueue(maxsize=0)


def add_cluster_to_update(cluster_id, priority):
    UPDATE_QUEUE.put((priority, cluster_id))


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
            print e.message
            pass  # TODO : handle errors

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
            print clusters_json.text
            return None
            #TODO: handle errors

    def get_cluster(self, inventory_key):
        hmac_header = self.authentificator.get_token_header()
        raw = requests.get("%s/api/cluster/%s" % (self.host, inventory_key),
                               headers=hmac_header, verify=False)
        try:
            res = raw.json()
            if res['status'] > 0 or len(res['cluster']) == 0 :
                return None, []
            cluster = res['cluster']
            servers = []
            if "servers" in cluster:
                for server in cluster["servers"]:
                    servers.append(m.Server(inventory_key=server["id"], name=server["name"], activated=server["status"]))
            cluster = m.Cluster(inventory_key=inventory_key, name=cluster['name'])
            return cluster, servers
        except Exception as e:
            print e.message
            pass  # TODO : handle errors

    def block_update(self, is_blocked):
        self.block = is_blocked

    def is_blocked(self):
        return self.block


class AsyncInventoryWorker(object):
    """DESCRIPTION HERE."""

    refresh_duration = 2

    def __init__(self, inventory_host):
        self._running = True
        self.inventory_host = inventory_host
        self.block = False # TODO : check all deployments in progress

    def start(self):
        while self._running:
            try:
                if self.inventory_host.is_blocked():
                    time.sleep(self.refresh_duration)
                    continue
                try:
                    _, cluster_id = self.get_cluster_to_update(block=True, timeout=self.refresh_duration)
                except Empty:
                    self.inventory_host.update_timestamp()
                    continue
                updated = self.update_cluster(cluster_id)
                if updated == 0:
                    logger.info("cluster id:{} updated form inventory".format(cluster_id))
                elif updated == 1:
                    logger.info("cluster id:{} deleted".format(cluster_id))
                elif updated == 2:
                    logger.error("[AsyncInventoryWorker] error in update of cluster id:{}".format(cluster_id))
                    # TODO: log error or send mail or whatever (see notification object)
            except:
                logger.exception("[AsyncInventoryWorker] unhandled error when updating cluster: ")

    def stop(self):
        self._running = False

    def get_cluster_to_update(self, block=False, timeout=0):
        if self.block is False:
            return UPDATE_QUEUE.get(block=block, timeout=timeout)
        else:
            raise Empty

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
                    if len(servers) == 0:
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
                        cluster_servers.pop(server.inventory_key)
                    else:
                        m.ClusterServerAssociation(cluster_def=cluster, server_def=server)
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

    def start(self):
        self._running = True
        while self._running:
            try:
                # TODO : check any deployment is running
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
                else:
                    logger.info("[inventory-synchronizer] up to date, inventory hash: {}".format(self.inventory_host.last_remote_update))
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
