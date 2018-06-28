# Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).
"""Dummy module describing the interfaces to implement
to integrate the deployer to a specific environment.

Integration capabilities are currently limited and somewhat inflexible,
so the interfaces here should not be considered stable. We will try to
maintain backward-compatibility as much as possible however.

In the deployer configuration file, add the following section to use this module

[integration]
provider=deployment.integrationexample.integration.Dummy
"""
import hashlib
import time

import requests
from deployment.artifact import NoArtifactDetected
from deployment import samodels as m, database
from deployment.auth import NoMatchingUser, InvalidSession, check_hash
from deployment.inventory import InventoryError


class Dummy(object):

    def __init__(self, config):
        """This constructor will be called by the deployer.

            Args:
            config (ConfigParser.ConfigParser): the parsed contents of the deployer configuration file
        """
        self.config = config

    def build_notifiers(self):
        """
        Use this method to act upon deployer events (for instance, you can publish deployments to your chat).
        The deployer already has some built-in notifiers (email, Graphite...).

        Return:
            list of notifiers: a notifier is an object implementing a dispatch(self, event) method.
            See the deployment.notifications module for examples. These notifiers will be added to the
            built-in list.
        """
        return []

    def detect_artifact(self, local_repo_path, git_server, repository_name, commit, environment_name):
        """
        By default, the deployer directly deploys the content of Git repositories.
        You can integrate it with a build system for some (or all) repositories if you need to.

        This method is called during a deployment ; you can return an artifact object
        describing what to deploy instead.
        Raise a deployment.artifact.NoArtifactDetected exception if you want to proceed with
        the default (deploying the repository contents).

        The interface to be implemented by an artifact object is documented in the deployment.artifact module.

        Args:
            local_repo_path (str): path to the local directory containing the repo (as cloned by the deployer)
            git_server (str): URL of the git server
            repository_name (str)
            commit (str): SHA1 of the commit to be deployed
            environment_name (str)

        Returns:
            an object with an interface compatible with deployment.artifact.Artifact

        Raises:
            NoArtifactDetected
        """
        raise NoArtifactDetected()

    def inventory_host(self):
        host = self.config.get('inventory', 'host')
        return StandardInventoryHost(host, self.inventory_authenticator())

    def authenticator(self):
        return DummyAuthenticator()

    def inventory_authenticator(self):
        return DummyInventoryAuthenticator()


class DummyAuthenticator(object):
    """This object implements methods to get an user from a token (password) or a sessionid."""

    def get_user_by_sessionid(self, sessionid, db):
        """
        sessionid authentification flow:
        1) the client provides a sessionid to /api/auth/wssession

        curl -X POST -d '{"sessionid": "my-id"}' http://deployer.example.com/api/auth/wssession

        This sessionid can also be passed in the request cookies
        (see the integration.sessionid_cookie configuratino parameter).

        2) you make sure this sessionid is valid, and matches an accountid in the deployer DB.
        This may be handed to an external service.

        3) you return the corresponding user in DB

        This example hard-codes some sessionids to accountids. Deactivated by default for security reasons :)
        """
        # Deactivate this example (comment the line below to use it)
        raise InvalidSession("unsupported authentification method")

        # Actual example
        if sessionid is 'an example invalid session':
            raise InvalidSession()
        sessionid_to_accountid = {
            'admin': 1,
            'default': 2,
            'joedoe': 3
        }
        if sessionid not in sessionid_to_accountid:
            raise NoMatchingUser()
        user = db.query(m.User).filter(m.User.accountid == sessionid_to_accountid[sessionid]).one_or_none()
        if user is None:
            raise NoMatchingUser()
        return user

    def get_user_by_token(self, username, token, db):
        """
        token (aka username + password) authentification flow:
        1) the user provides a username and a token to /api/auth/token

        curl -X POST -d '{"username": "joe", "auth_token": "my-token"}' http://deployer.example.com/api/auth/token

        2) you match this combination to a user in DB
        This may be handed to an external service.

        Raise an exception if you don't want to allow this authentification method.

        This example is a reasonable implementation that you can use as such.
        """
        user = db.query(m.User).filter(m.User.username == username).one_or_none()
        if user is None or not check_hash(token, user.auth_token):
            raise NoMatchingUser()
        return user


class DummyInventoryAuthenticator(object):
    """
    This object implements methods to get a valid token for the inventory
    and to check validity of token of incoming requests from the inventory.
    """

    def get_token_header(self):
        """
        method called by the inventoryHost object to build a request for the inventory
        It generates the auth token accepted by the inventory

        returns:
            a HTTP header line formatted in python object

        Dummy:
            no auth token
        """
        return {}

    def check_auth_token(self, request):
        """
        check if the emitter of a hook notification has the rights to do it
        this method gets the request object to extract the headers needed

        returns:
            True if the auth is good
            False if there is no auth token or if the auth is not valid

        Dummy:
            no auth needed, always returns True (except in case of null request object)
        """
        if request is None:
            return False
        else:
            return True


class StandardInventoryHost(object):
    """
    This object implements methods to fetch information from the inventory
    such as clusters' data or last_update.
    Also used to compute the last_update on the deployer.

    This current object is one possible implementation of the inventory.
    It is encouraged to follow the following schema for the inventory API.
    """

    def __init__(self, host, authenticator):
        self.host = host
        self.authenticator = authenticator

    def is_up_to_date(self):
        """
        Method called by the workers related to the synchronisation.
        It checks if the deployer is up-to-date with the inventory.

        returns:
            True if the deployer is up-to-date
            False otherwise.
        """
        most_recent_version = self._fetch_most_recent_version()
        local_version = self._get_local_version()
        if local_version == most_recent_version:
            return True
        else:
            return False

    def _get_local_version(self):
        """
        FYI: NOT MANDATORY, could be integrated in is_up_to_date() function

        Returns an image of the last update performed on the deployer
        Here, a hash of the concatenation of the clusters last_update is computed and returned

        It is possible to store a value in db rather than compute the value each time.
        """
        dates_concat = ''
        with database.session_scope() as session:
            clusters = session.query(m.Cluster).filter(m.Cluster.inventory_key!=None).order_by(m.Cluster.inventory_key).all()
            for cluster in clusters:
                dates_concat += str(time.mktime(cluster.updated_at.utctimetuple()))
        return hashlib.sha256(dates_concat).hexdigest()

    def _fetch_most_recent_version(self):
        """
        FYI: NOT MANDATORY, could be integrated in is_up_to_date() function

        Returns an image of the last update of the inventory.
        Here, it calls inventory api route 'api/last_update'
        """
        header = self.authenticator.get_token_header()
        res = requests.get("{}/api/last_update".format(self.host), headers=header)
        payload = res.json()
        if "last_update" not in payload:
            raise InventoryError("bad response from inventory")
        return payload["last_update"]

    def get_clusters(self):
        """
        Method called by the inventory-update-checker worker for a full update.
        Retrieves all the clusters available from the inventory

        returns:
            List of all inventory keys: [inventory_key_1, inventory_key_2, ...]
        """
        header = self.authenticator.get_token_header()
        clusters_json = requests.get("{}/api/clusters".format(self.host), headers=header)
        clusters = clusters_json.json()
        if clusters['status'] == 0:
            return clusters['clusters']
        else:
            raise InventoryError('bad response from inventory')

    def get_cluster(self, inventory_key):
        """
        Method called by the async-inventory-updater worker to update a cluster.
        Fetch the information about one cluster, given an inventory_key.

        returns:
            1. a flag: 'existing' or 'deleted' if the cluster is still present in the inventory
            2. cluster data: {'inventory_key': _, 'name': _, 'updated_at': _} is the minimal payload
            3. servers data: array of all servers in the cluster. Minimal data:
                [{'inventory_key': _, 'name': _, 'activated': _}, {...}, ...]
        """
        header = self.authenticator.get_token_header()
        raw = requests.get("%s/api/cluster/%s" % (self.host, inventory_key), headers=header)
        res = raw.json()
        if 'cluster' not in res:
            raise InventoryError("bad response from inventory")
        else:
            if len(res['cluster']) == 0:
                return 'deleted', None, None
            else:
                if "servers" not in res['cluster']:
                    raise InventoryError('missing servers in payload')
                servers = res['cluster'].pop("servers")
                cluster = res['cluster']
                return "existing", cluster, servers
