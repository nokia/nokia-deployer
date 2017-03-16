#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).
import os
import json
import logging
import traceback
import itertools
import urlparse
import datetime
import requests

from . import execution, notification, gitutils, database, samodels as m

from Queue import Queue, Empty

DEPLOYMENT_JOBS_TUBE = "deployer-deployments"

# Some deployments include a lengthy build step (yes, we should have a separate build pipeline)
# so we need a high value here
DEPLOYMENT_JOB_TIME_TO_RUN = 30 * 60


def create_deployment_job(beanstalk, notifier, repository_name, environment_name, environment_id, cluster_id, server_id, branch, commit, user_id):
	with database.session_scope() as session:
		deployment = m.DeploymentView(
			repository_name=repository_name,
			environment_name=environment_name,
			environment_id=environment_id,
			cluster_id=cluster_id,
			server_id=server_id,
			branch=branch,
			commit=commit,
			user_id=user_id,
			status=m.DeploymentStatus.QUEUED.to_db_format(),
			queued_date=datetime.datetime.utcnow()
		)
		session.add(deployment)
		session.commit()
		deploy_id = deployment.id
	beanstalk.put(DeploymentJob(deploy_id, repository_name, environment_name).serialize(), ttr=DEPLOYMENT_JOB_TIME_TO_RUN)
	notifier.dispatch(notification.Notification.deployment_queued(
		deploy_id,
		environment_id,
		repository_name,
		environment_name,
		branch,
		commit,
		user_id
	))
	return deploy_id


# Commit can be None ; in this case, skip auto deploy, just fetch
def handle_autodeploy_notification(repository_name, branch, commit, beanstalk, notifier, auto_deploy_account, deployer_urls):
	logging.debug('Autodeploy: got notification for repo {}, branch {}'.format(repository_name, branch))
	with database.session_scope() as session:
		envs = session.query(m.Environment).filter(m.Environment.repository_name == repository_name).all()
		if commit is not None:
			auto_deploy_envs = [e for e in envs if e.auto_deploy and e.deploy_branch == branch]
		else:
			auto_deploy_envs = []

		for env in auto_deploy_envs:
			deploy_id = create_deployment_job(
					beanstalk,
					notifier,
					repository_name,
					env.name,
					env.id,
					None,
					None,
					branch, commit,
					auto_deploy_account.id
				)
			logging.info("Autodeploy: queued job {} for {}/{}".format(deploy_id, repository_name, env.name))

		for env, url in itertools.product(envs, deployer_urls):
			try:
				fetch_url = urlparse.urljoin(url, 'api/environments/{}/fetch'.format(env.id))
				r = requests.post(fetch_url, timeout=3)
				logging.info("Autodeploy: notified {} to fetch objects for {}/{}. Response code: {}".format(fetch_url, repository_name, env.name, r.status_code))
			except Exception as e:
				logging.error("Caught exception when notifying {}".format(url))
				logging.exception(e)


class AsyncFetchWorker(object):

	job_queue = Queue()

	def __init__(self, config, notifier, name):
		self.config = config
		self._running = True
		self.notifier = notifier
		self.name = name

	@classmethod
	def enqueue_job(klass, environment):
		klass.job_queue.put((
			environment.id,
			environment.local_repo_directory_name,
			environment.repository_name,
			environment.repository.git_server,
			environment.deploy_branch
		))

	def start(self):
		while self._running:
			try:
				try:
					job = self.job_queue.get(block=True, timeout=2)
				except Empty:
					continue
				environment_id, local_repo_directory_name, repository_name, git_server, deploy_branch = job
				base_repos_path = self.config.get("general", "local_repo_path")
				path = os.path.join(base_repos_path, local_repo_directory_name)
				# There is a race condition between two workers here.
				# If both workers attempt to clone, one of them will fail and this will have no consequences.
				# Since there are other places where concurrent clones are possible
				# (deployments can also attempt a clone) and actual cloning is rare day-to-day usage,
				# we prefer failing here rather than using a lock everywhere clones are attempted.
				if not os.path.exists(path):
					logging.info("AsyncFetchWorker: cloning {}".format(path))
					remote_url = gitutils.build_repo_url(repository_name, git_server)
					gitutils.clone(remote_url, path, raise_for_error=True)
				else:
					logging.info("AsyncFetchWorker: fetching {}".format(path))
					with gitutils.lock_repository_fetch(path) as repo:
						repo.fetch()
				logging.info("AsyncFetchWorker: fetching {}: done".format(path))

				self.notifier.dispatch(notification.Notification.commits_fetched(
					environment_id=environment_id,
					local_repo_path=path,
					deployment_id=None,
					repository=repository_name,
					git_server=git_server,
					deploy_branch=deploy_branch
				))
			except Exception as e:
				logging.error("AsyncFetchWorker: unhandled error when fetching from git: {}".format(traceback.format_exc(e)))
		try:
			self._shutdown()
		except Exception as e:
			logging.exception(e)

	def _shutdown(self):
		try:
			while True:
				job = self.job_queue.get(block=False)
				logging.warn("Because of shutdown, will not perform git fetch for {}".format(job))
		except Empty:
			pass

	def stop(self):
		self._running = False


class DeploymentJob(object):

	# Deploy ID is the only information one should act upon
	# The other parameters are for ease of troubleshooting only
	def __init__(self, deploy_id, repository_name, environment_name):
		self.deploy_id = deploy_id
		self.repository_name = repository_name
		self.environment_name = environment_name

	def serialize(self):
		return json.dumps({
			'deploy_id': self.deploy_id,
			'environment_name': self.environment_name,
			'repository_name': self.repository_name
		})

	@classmethod
	def deserialize(klass, data):
		parsed = json.loads(data)
		return klass(
			deploy_id=parsed['deploy_id'],
			repository_name=parsed['repository_name'],
			environment_name=parsed['environment_name']
		)


class DeployerWorker(object):
	"""Perform deployments requests coming from a Beanstalk host."""

	def __init__(self, beanstalk_connection, general_config, notifier, artifact_detector, name_suffix):
		self._running = True
		self._beanstalk = beanstalk_connection
		self.general_config = general_config
		self.notifier = notifier
		self.name_suffix = name_suffix
		self.artifact_detector = artifact_detector

	def start(self):
		self._running = True
		self._beanstalk.watch(DEPLOYMENT_JOBS_TUBE)
		while self._running:
			try:
				job = self._beanstalk.reserve(2)
				if job is None:
					continue
				deploy_job = DeploymentJob.deserialize(job.body)
				release_count = job.stats()['releases']
				logging.info("Received a deployment job (deployment ID is {} ({}/{}), release count is {})".
				 format(deploy_job.deploy_id, deploy_job.repository_name, deploy_job.environment_name, release_count))
				self.perform(deploy_job)
				job.delete()
				logging.info("Job complete, deleting it (deployment ID is {})".format(deploy_job.deploy_id))
			except Exception as e:
				logging.error("Job failed. Error was: {}".format(traceback.format_exc(e)))
				release_count = job.stats()['releases']
				# For now drop everything after the first error, until we have a proper retry strategy (TODO)
				MAX_RELEASE_COUNT = 0
				try:
					if release_count >= MAX_RELEASE_COUNT:
						logging.warning("Job has already been released more than {} times, dropping it.".format(MAX_RELEASE_COUNT))
						job.delete()
					else:
						logging.info("Job released.")
						job.release(delay=10)
				except Exception as e:
					logging.error("Error in the deployer worker error handler.")
					logging.exception(e)

	def stop(self):
		self._running = False
		self._beanstalk.close()

	@property
	def name(self):
		return "deployer-worker-{}".format(self.name_suffix)

	def perform(self, deploy_job):
		deployment = execution.Deployment(deploy_job.deploy_id, self.general_config, self.notifier, self.artifact_detector)
		deployment.execute()
