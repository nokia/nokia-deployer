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

from deployment.artifact import NoArtifactDetected
from deployment import samodels as m
from deployment.auth import NoMatchingUser, InvalidSession, check_hash


class Dummy(object):

    def __init__(self, config):
        """This constructor will be called by the deployer.

            Args:
            config (ConfigParser.ConfigParser): the parsed contents of the deployer configuration file
        """
        pass

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

    def authentificator(self):
        return DummyAuthentificator()

    def inventory_authentificator(self):
        return DummyInventoryAuthentificator()


class DummyAuthentificator(object):
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


class DummyInventoryAuthentificator(object):
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
