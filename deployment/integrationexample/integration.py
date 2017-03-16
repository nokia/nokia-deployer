# Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).
"""Dummy module describing the interfaces to implement
to integrate the deployer to a specific environment.

Integration capabilities are currently limited and somewhat inflexible,
so the interfaces here should not be considered stable.

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
		The deployer already has some built-in notifiers.

		Return:
			list of notifiers: a notifier is an object implementing a dispatch(self, event) method.
				See the deployment.notifications module for examples. These notifiers will be added to the build-in list.
		"""
		return []

	def detect_artifact(self, local_repo_path, git_server, repository_name, commit, environment_name):
		"""
		By default, the deployer directly deploys Git repositories.
		This method is called during a deployment ; you can return an artifact object
		describing what to deploy instead.
		Raise a deployment.artifact.NoArtifactDetected exception
		if you want to proceed with the default (deploying the repository contents.)

		The interface to be implemented by an artifact object is documented in the deployment.artifact module.

		Args:
			local_repo_path (str): path to the local directory containing the repo (as cloned by the deployer)
			git_server (str): URL of the git server
			repository_name (str)
			commit (str): SHA1 of the commit to be deployed
			environment_name (str)

		Returns:
			an object with an interface compatible with artifact.Artifact

		Raises:
			NoArtifactDetected
		"""
		raise NoArtifactDetected()

	def authentificator(self):
		return DummyAuthentificator()


class DummyAuthentificator(object):
	"""This object implements methods to get an user from a token or a sessionid."""

	def get_user_by_sessionid(self, sessionid, db):
		"""
		sessionid authentification flow:
		1) the client provides a sessionid
		2) you make sure this sessionid is valid, and matches an accountid
		3) you return the corresponding user in DB

		See the README for the complete authentification flow.

		This example directly matches sessionid to accountid.
		This is a terrible idea for a real deployment.
		Instead, use an external API to exchange the sessionid against the accountid.
		"""
		if sessionid is 'an example invalid session':
			raise InvalidSession()
		user = db.query(m.User).filter(m.User.accountid == sessionid).one_or_none()
		if user is None:
			raise NoMatchingUser()
		return user

	def get_user_by_token(self, username, token, db):
		"""
		This is a pretty reasonable implementation that you can use as such.
		Raise an exception if you don't want to allow this authentification method.
		"""
		user = db.query(m.User).filter(m.User.username == username).one_or_none()
		if user is None or not check_hash(token, user.auth_token):
			raise NoMatchingUser()
		return user
