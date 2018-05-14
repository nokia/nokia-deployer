# Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).
# -*- coding: utf-8 -*-

import json
from logging import getLogger
import re
import requests

from . import database, samodels as m
from .HMAClib import HMAC

logger = getLogger(__name__)


class InventoryHost(object):

    def __init__(self, config):
        self.host = config["inventory.api_host"]
        # TODO : enable other token generation
        self.hmac_key = config["inventory.hmac_key"]
        self.hmac_username = config["inventory.hmac_username"]

    def get_hmac_token(self):
        # TODO : import hmac script
        hmac = HMAC(self.hmac_username, self.hmac_key)
        hmac_token = hmac.generate_authtoken()
        return hmac_token

    def get_servers_by_zone_and_tag_id(self, zone, tag):
        hmac_token = self.get_hmac_token()
        servers = requests.get("%s/api/search/server?zone_name=%s&tag_name=%s" % (self.host, zone, tag), headers={"X-Auth": hmac_token}, verify=False)
        ret = servers.text.split(" ")
        if ret == ['']:
            ret = []
        return ret

    def get_tags_by_name_and_zone(self, zone, name, with_completion=False):
        hmac_token = self.get_hmac_token()
        tags = requests.get("%s/api/search/tags?zone_name=%s&tag_name=%s&with_auto_completion=%s" % (self.host, zone, name, str(with_completion)), headers={"X-Auth": hmac_token}, verify=False)
        try:
            ret = tags.json()
        except Exception as e:
            print("RAW:", tags, tags.text)
            # raise e
        return ret

    def find_cluster(self, cluster_name, zone_name, auto):
        results = self.get_tags_by_name_and_zone(zone_name, cluster_name, auto)
        if len(results) == 0:
            return {}
        clusters = []
        for id, metadata in results.iteritems():
            if re.match(r"^\d+$", id is None):
                return []  # return error or drop this one ?
            if "cluster_name" not in metadata:
                continue # or return error ?
            clusters.append(m.Cluster(distant_id=id, name=metadata["cluster_name"], zone=zone_name))

        return clusters

    def get_cluster(self, distant_id, zone_name):
        cluster = self.get_servers_by_zone_and_tag_id(zone_name, distant_id) # change this method above
        if len(cluster) == 0:
            return None, []
        servers = []
        if "hosts" in cluster:
            for server in cluster["hosts"]:
                servers.append(m.Server(distant_id= server["id"], name=server["name"]))
        cluster = m.Cluster(name=distant_id, zone=zone_name)
        return cluster, servers


def get_cluster(inventory_host, zone_name, distant_id):
    cluster = inventory_host.get_servers_by_zone_and_tag_id(zone_name, distant_id)
    if len(cluster) == 0:
        return {}, {}
    servers = []
    for server in cluster:
        servers.append(m.Server(name=server))
    cluster = m.Cluster(name=distant_id, zone=zone_name)
    return cluster, servers


def format_name(name_str):
    return re.sub(r'[\n\t\'\"\s]*', '', name_str)


def update_environment_clusters(inventory_host, environment_id):
    with database.session_scope() as session:
        clusters = session.query(m.Environment).filter(m.Environment.id == environment_id).one_or_none().clusters
        for cluster in clusters:
            logger.debug(cluster.name)
            distant_hosts = inventory_host.get_servers_by_zone_and_tag_id(cluster.zone, cluster.distant_id)
            logger.debug(distant_hosts)
            up_to_date = compare_cluster(distant_hosts, cluster.id)
            if not up_to_date:
                update_cluster(distant_hosts, cluster.id)
    logger.debug("ceci est un premier test")


def compare_cluster(hosts, cluster_id):
    if len(hosts) == 0:
        return False
    with database.session_scope() as session:
        actual_hosts = session.query(m.Cluster)\
            .filter(m.ClusterServerAssociation.cluster_id == cluster_id).all()
        deployer_hosts = [elem.name for elem in actual_hosts]
        if len(hosts) != len(deployer_hosts):
            return False
        for host_name in hosts:
            if host_name not in deployer_hosts:
                return False
        else:
            return True


def update_cluster(inventory_hosts, cluster_id):
    for host in inventory_hosts:
        with database.session_scope() as session:
            server, created = database.get_or_create(session, m.Server, defaults={"activated": True, "port":22}, name=host)
            logger.debug("server %s was %s" %(server.name, "added" if created else "already in db"))

            # create clusters_servers associatation
            defaults = {
                "haproxy_key":None
            }
            association, created = database.get_or_create(session, m.ClusterServerAssociation, defaults, cluster_id=cluster_id, server_def=server)
            logger.debug("server %s was %s cluster %s" %(server.name, "added to" if created else "already in", association.cluster_id))
            session.add(association)
