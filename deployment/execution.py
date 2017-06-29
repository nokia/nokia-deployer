# Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).
import enum
from logging import getLogger, LoggerAdapter
import functools
import traceback
import datetime
import socket
import os
import time
import json
import multiprocessing
from multiprocessing.dummy import Pool
import sys

from sqlalchemy import inspect

from . import mail, authorization, gitutils, database, filelock, samodels as m
from .artifact import GitArtifact, NoArtifactDetected
from .executils import run_cmd_by_ssh, exec_script, remote_check_file_exists, \
    exec_script_remote, exec_cmd, Host
from .notification import Notification
from .samodels import Severity, DeploymentStatus, LogEntry

from .haproxyapi import haproxy

logger = getLogger(__name__)


class DeploymentError(Exception):
    pass


class PrefixedLoggerAdapter(LoggerAdapter):

    def __init__(self, logger, prefix):
        self.prefix = prefix
        super(PrefixedLoggerAdapter, self).__init__(logger, None)

    def process(self, msg, kwargs):
        return "{} {}".format(self.prefix, msg), kwargs


class GeneralConfig(object):

    def __init__(self, base_repos_path, haproxy_user, haproxy_password, notify_mails, mail_sender):
        """
        Args:
            base_repos_path (str): path to the deployer working directory, ie the folder that will contains the cloned repositories
            haproxy_user (str): user to use to authentificate to HAroxy
            haproxy_password (str): password for the HAproxy user
            notify_mails (list of str): always put these email adresses in CC of mails sent for this deployment
            mail_sender (str): field 'From:' in emails sent by the deployer
        """
        self.base_repos_path = base_repos_path
        self.haproxy_auth = (haproxy_user, haproxy_password)
        self.notify_mails = notify_mails
        self.mail_sender = mail_sender


# TODO: make the whole thing simpler
def run_step(deployment, step, *args, **kwargs):
    """Run a deployment step, and register its result in the provided deployment.

    Args:
        deployment (Deployment): the current deployment object
        step (generator): the step to run. A step is a generator that must yield:
            * first, a string (type str) describing the step (such as "cloning the repo")
            * then, zero or more LogEntry objects, that will be registered in the deployment log.
              Yielding a log entry with an ERROR severity will mark the step as failed (unless _abort_on_error is True).
            * the last yielded value (which may be of any type) will be the result of the step (and returned by run_step).
        args, kwargs: arguments to pass to the step function
        _abort_on_error: if False, yielding an error (LogEntry with severity ERROR) will not abort the deployment. If an exception is raised, the step is still marked as failed regardless of this parameter.

    Return:
        the last value yielded by the generator

    Example:
        >>> def my_step(some_value, fail_it=False):
        yield "Print some_value"  # step description
        print(some_value)
        yield LogEntry("it worked")
        if fail_it:
        yield LogEntry("this step will fail", severity=Severity.ERROR)
        yield some_value + 2  # step result (not mandatory)
        >>> out = run_step(deployment, my_step, 3, _abort_on_error=False)
        >>> print(out)
        5
    """

    # Python 2 forces us to manually parse the arguments
    _abort_on_error = kwargs.pop('_abort_on_error', True)
    session = kwargs.pop('_session', None)

    # So we don't have to pass the session to each call to run_step
    if not session:
        session = inspect(deployment.view).session

    # Get the step description
    try:
        it = step(*args, **kwargs)
        description = it.next()
        deployment.log.info('Running step: {}'.format(description))
        if not isinstance(description, str) and not isinstance(description, unicode):
            raise ValueError('The step description must be a string, got {}'.format(type(description)))
    except Exception as e:  # This should not happen, but makes debugging easier
        deployment.log.error(traceback.format_exc(e))
        entry = LogEntry(
            message="Error when initializing a step: {}".format(str(e)),
            severity=Severity.ERROR.format()
        )
        deployment.view.log_entries.append(entry)
        session.commit()
        raise

    deployment.view.log_entries.append(LogEntry(message='Step: {}'.format(description)))
    session.commit()
    deployment.notifier.dispatch(Notification.deployment_step_start(deployment.view, description))

    # Collect log entries
    out = None
    errored = False
    try:
        try:
            while True:
                out = it.next()
                if isinstance(out, LogEntry):
                    deployment.view.log_entries.append(out)
                    if out.severity == Severity.ERROR.format():
                        errored = True
                    session.commit()
        except StopIteration:
            pass
        return out
    except Exception as e:
        deployment.log.error(traceback.format_exc(e))
        errored = True
        e = LogEntry(
            message="Error when running step '{}': {}".format(description, str(e)),
            severity=Severity.ERROR.format()
        )
        deployment.view.log_entries.append(e)
        session.commit()
        raise
    finally:
        deployment.notifier.dispatch(
            Notification.deployment_step_end(deployment.view, description, errored)
        )
        if _abort_on_error and errored:
            message = "Step '{}' failed".format(description)
            deployment.log.error(message)
            raise DeploymentError(message)
    return out


# The corresponding database object is called a DeploymentView
class Deployment(object):

    MAX_PARALLEL_SYNC = 20

    def __init__(self, deploy_id, general_config, notifier, artifact_detector):
        """
        Args:
            deploy_id (int)
            general_config (GeneralConfig)
            notifier: an object implementing a dispatch function - see the notifications module
            artifact_detector: a callable that returns an artifact object (see the artifact module)
                               or raise a NoArtifactDetected error
        """
        self.deploy_id = deploy_id
        self.general_config = general_config
        self.notifier = notifier
        self.artifact_detector = artifact_detector

        self.log = PrefixedLoggerAdapter(logger, "[deploy {}]".format(deploy_id))
        self.screenshot_files = None
        self.artifact = None
        self.view = None
        self.step_results = []

    def write_entry(self, entry):
        """Log the provided LogEntry, according to its severity"""
        if entry.severity == Severity.INFO:
            return self.log.info(entry.message)
        elif entry.severity == Severity.WARN:
            return self.log.warn(entry.message)
        elif entry.severity == Severity.ERROR:
            return self.log.error(entry.message)
        assert False, "Code should not reach here"

    def _update_status(self, status, session):
        self.view.status = status.to_db_format()
        session.commit()

    def _check_configuration(self, session):
        self.log.info("START deploy")
        self.notifier.dispatch(Notification.deployment_start(self.view))

        run_step(self, check_configuration, self.view)

        self._update_status(DeploymentStatus.INIT, session)
        self.notifier.dispatch(Notification.deployment_configuration_loaded(self.view))
        environment = self.view.environment
        self.log.prefix = "[{} {}/{}]".format(self.view.id, environment.name, environment.repository.name)

        # Check whether we can proceed (permissions)
        run_step(self, check_deploy_allowed, self.view.user, environment.id, environment.name)

        run_step(self, check_servers_availability, session, self.view.id, self.view.target_servers,
                 environment.name, self.view.branch, self.view.commit)

    def _get_artifact(self, local_repo_path, repo, mail_sender, mail_test_report_to):
        environment = self.view.environment
        run_step(self, update_repo, local_repo_path, self.view.commit, repo)
        self.notifier.dispatch(Notification.commits_fetched(
            environment_id=environment.id,
            local_repo_path=local_repo_path,
            git_server=environment.repository.git_server,
            repository=environment.repository.name,
            deployment_id=self.deploy_id,
            deploy_branch=environment.deploy_branch
        ))

        self.artifact = run_step(
            self, detect_artifact, local_repo_path, environment.repository.git_server,
            environment.repository.name, self.view.commit, environment.name, self.artifact_detector
        )
        run_step(self, get_artifact, self.artifact)

        if self.artifact.should_run_predeploy_scripts():
            # Predeploy script
            run_step(self, run_and_delete_predeploy, local_repo_path, environment.name, self.view.commit)

            # Run local tests
            # The local tests script require a server as a parameter. If we are deploying on more than one server,
            # then it can accept any server.
            dummy_host = Host.from_server(list(self.view.target_servers)[0], environment.remote_user)
            run_step(self, run_local_tests, environment, local_repo_path,
                     self.view.branch, self.view.commit, dummy_host, mail_sender, mail_test_report_to,
                     _abort_on_error=environment.fail_deploy_on_failed_tests)

    def _copy_to_remotes(self, cluster, mail_sender, mail_test_report_to):
        environment = self.view.environment
        hosts = [Host.from_server(s, environment.remote_user) for s in cluster.activated_servers]
        destination_path = environment.release_path(self.view.branch, self.view.commit)
        run_step(
            self,
            parallel_sync,
            destination_path, environment.sync_options, self.view.branch, self.view.commit, self.artifact.local_path,
            hosts,
            self.MAX_PARALLEL_SYNC
        )

        for host, server in zip(hosts, cluster.activated_servers):
            run_step(self, release, host, environment.repository.deploy_method, environment.remote_repo_path(), environment.production_folder(), destination_path)
            self.notifier.dispatch(Notification.released_on_server(self.view, server, datetime.datetime.utcnow(), self.view.branch, self.view.commit))
            run_step(self, run_and_delete_deploy, host, environment.target_path, environment.name, self.view.commit)
            run_step(self, run_remote_tests, environment, self.view.branch, self.view.commit, host, mail_sender, mail_test_report_to, _abort_on_error=environment.fail_deploy_on_failed_tests)

    def _cluster_orchestration(self, target_clusters, haproxy_auth):
        # Deploy the code cluster by cluster
        old_version_clusters = list(target_clusters)
        new_version_clusters = []

        run_step(self, ensure_clusters_up, old_version_clusters, haproxy_auth)
        while len(old_version_clusters) > 0:
            cluster = old_version_clusters.pop()
            if len(new_version_clusters) == 0:
                pass   # Nothing to do
            elif len(new_version_clusters) == 1:
                # One cluster has already been updated, so deactivate all the old ones
                time.sleep(1)  # Give some time to the cluster to activate
                run_step(self, ensure_clusters_up, new_version_clusters, haproxy_auth)
                if len(old_version_clusters) != 0:
                    run_step(self, disable_clusters, old_version_clusters, haproxy_auth)
            else:
                # More than one cluster has already been updated
                run_step(self, ensure_clusters_up, new_version_clusters, haproxy_auth)
            # In any case, deactivate the cluster we are updating
            run_step(self, disable_clusters, [cluster], haproxy_auth)
            yield cluster
            # Activate the updated cluster
            new_version_clusters.append(cluster)
            run_step(self, enable_clusters, [cluster], haproxy_auth)

    def _take_screenshot(self, local_repo_path):
        deploy_conf = run_step(self, load_repo_configuration_file, local_repo_path)
        environment = self.view.environment
        screenshot_files = None
        if 'url' in deploy_conf and environment.name in deploy_conf['url']:
            screenshot_files = run_step(self, screenshot, deploy_conf['url'][environment.name],
                                        environment.repository.name, environment.name)
        return screenshot_files

    def execute(self):
        screenshots = []
        with database.session_scope() as session:
            try:
                self.view = session.query(m.DeploymentView).get(self.deploy_id)
                if self.view is None:
                    raise AssertionError('No configuration found for deploy ID {}'.format(self.deploy_id))

                self._check_configuration(session)
                self._update_status(DeploymentStatus.PRE_DEPLOY, session)

                environment = self.view.environment
                local_repo_path = os.path.join(self.general_config.base_repos_path, environment.local_repo_directory_name)
                mail_test_report_to = set(environment.repository.notify_owners_mails + self.general_config.notify_mails)
                mail_sender = self.general_config.mail_sender

                # Ensure the repo exist on disk
                run_step(self, clone_repo, local_repo_path, environment.repository.name, environment.repository.git_server)

                with gitutils.lock_repository_write(local_repo_path) as repo:
                    self._get_artifact(local_repo_path, repo, mail_sender, mail_test_report_to)

                    for cluster in self._cluster_orchestration(self.view.target_clusters, self.general_config.haproxy_auth):
                        self._copy_to_remotes(cluster, mail_sender, mail_test_report_to)

                self._update_status(DeploymentStatus.POST_DEPLOY, session)
                screenshots = self._take_screenshot(local_repo_path)
                self.log.info("END deploy")
            except Exception:
                # Do not log the stack trace here, as we are raising the exception again, it will be logged
                # further up the chain
                self.view.end(DeploymentStatus.FAILED)
                exctype, value = sys.exc_info()[:2]
                self.log.error('An error was encountered during deployment ({}). Deployment failed.'.
                               format("\n".join(traceback.format_exception_only(exctype, value))).strip())
                raise
            else:
                self.view.end(DeploymentStatus.COMPLETE)
            finally:
                if self.artifact is not None:
                    self.artifact.cleanup()
                self.notifier.dispatch(Notification.deployment_end(self.view, screenshots))
                session.commit()


def capture(prefix, func, *args, **kwargs):
    """Given a function returning a tuple (return_code, stdout, stderr) when executed on args and kwargs,
    return a list of LogEntry.

    If return_code is not 0, then a LogEntry with an ERROR severity will be generated.

    Also works with function returning only a string S, in which case S is considered standard output.
    """
    out = func(*args, **kwargs)
    if out is None:
        return []
    entries = []
    if isinstance(out, str) or isinstance(out, unicode):
        out = (0, out, None)
    (code, stdout, stderr) = out
    now = datetime.datetime.utcnow()
    if stdout is not None and len(stdout) >= 1:
        entries.append(LogEntry("{}: {}".format(prefix, stdout), date=now))
    if stderr is not None and len(stderr) >= 1:
        if code != 0:
            entries.append(LogEntry("{}: {}".format(prefix, stderr), Severity.ERROR, date=now))
        else:
            entries.append(LogEntry("{}: {}".format(prefix, stderr), Severity.WARN, date=now))
    if code != 0:
        entries.append(LogEntry("{}: exited with code {}".format(prefix, code), Severity.ERROR))
    return entries


##################
# Steps definition
##################

def check_configuration(view):
    yield "Check configuration for deployment {})".format(view.id)
    yield LogEntry("Deployment handled by {}".format(socket.gethostname()))
    view.date_start_deploy = datetime.datetime.utcnow()
    if view.environment_id is None:
        yield LogEntry("No environment ID for with this deployment, can not proceed", severity=Severity.ERROR)
        yield None
        return
    if view.user_id is None:
        yield LogEntry("No user ID associated with this deployment, can not proceed", severity=Severity.ERROR)
        yield None
        return
    yield LogEntry('Found configuration: username {}, repo {}, environment {}, branch {}, commit {}'.
                   format(view.user.username, view.environment.repository.name, view.environment.name, view.branch, view.commit))

    for s in view.deactivated_servers:
        yield LogEntry("Server {} is deactivated, will be ignored for this deployment.".format(s.name), severity=Severity.WARN)

    if len(view.target_servers) == 0:
        yield LogEntry(
            "This deployment has no target servers (the target cluster is empty).", severity=Severity.ERROR)
        yield None
        return

    if len(view.target_servers) == len(view.deactivated_servers):
        yield LogEntry(
            "All target servers are deactivated.", severity=Severity.ERROR)
        yield None
        return

    if view.status != "QUEUED":
        yield LogEntry("This deployment has the status {} (expected QUEUED). "
                       "It was probably interrupted (by a deployer restart?), "
                       "or there is another deeper issue (several deployer instances using the same queue? TTR exceeded?). "
                       "In any case, aborting here.".format(view.status), severity=Severity.ERROR)



def check_deploy_allowed(account, environment_id, environment_name):
    yield "Check whether the user '{}' is allowed to deploy".format(account.username)

    if os.path.exists('/tmp/global_ops_lock') and not account.has_permission(authorization.SuperAdmin()):
        yield LogEntry("Denied: your beloved Platform Ops team is blocking all deployments until further notice.", Severity.ERROR)
        yield False
        return

    if account.has_permission(authorization.Deploy(environment_id)):
        yield True
        return

    if account.has_permission(authorization.DeployBusinessHours(environment_id)):
        protected_envs = ['prod']
        if environment_name in protected_envs:
            today = datetime.datetime.now()
            max_hour_friday = 14
            if today.weekday() == 4 and today.hour >= max_hour_friday:
                yield LogEntry("Denied: no deployment allowed during Fridays after 2pm in environment '{}'".format(environment_name), Severity.ERROR)
                yield False
                return
            if today.weekday() >= 5:
                yield LogEntry("Denied: no deployment allowed during week-ends in environment '{}'".format(environment_name), Severity.ERROR)
                yield False
                return
            min_hour = 8
            max_hour = 18
            max_minutes = 30
            if today.hour < min_hour or (today.hour == max_hour and today.minute >= max_minutes) or (today.hour > max_hour):
                yield LogEntry("Denied: no deployment allowed before 8:00 or after 18:30 in environment '{}'".format(environment_name), Severity.ERROR)
                yield False
                return
            # Hardcoded list of days such as France bank holidays (and sometimes the day before)
            current_year = datetime.datetime.now().year
            forbidden = [
                datetime.date(current_year, 1, 1),     # New Year's Day
                datetime.date(current_year, 5, 1),     # Labor Day
                datetime.date(current_year, 5, 8),     # WWII Victory Day
                datetime.date(current_year, 7, 14),    # Bastille Day
                datetime.date(current_year, 11, 1),    # All Saint's Day
                datetime.date(current_year, 11, 11),   # Armistice Day
                datetime.date(current_year, 12, 24),   # Christmas Eve
                datetime.date(current_year, 12, 25),   # Christmas Day
                datetime.date(current_year, 12, 26),   # No deployments just after Christmas either
                datetime.date(current_year, 12, 31)    # New Year's Eve
            ]
            if today.date() in forbidden:
                yield LogEntry("Denied: no deployment allowed today in environment '{}'".format(environment_name), Severity.ERROR)
                yield False
                return
        yield True
        return

    yield LogEntry('Denied (insufficient permissions)', Severity.ERROR)
    yield False


def clone_repo(working_directory, repo_name, git_server):
    yield "Clone repository {}".format(repo_name)
    if os.path.exists(working_directory):
        yield LogEntry("Repository already cloned, skipping.")
        return
    gitutils.clone(gitutils.build_repo_url(repo_name, git_server), working_directory)


def update_repo(local_repo_path, commit, write_repo_lock):
    yield "Switch to commit {}".format(commit)
    if not os.path.exists(local_repo_path):
        yield LogEntry('Git repository not found at {}'.format(local_repo_path), Severity.ERROR)
        return
    try:
        with gitutils.lock_repository_fetch(local_repo_path) as repo:
            yield LogEntry("Update objects (git fetch)")
            repo.fetch()
    except filelock.AlreadyLocked:
        pass
    yield LogEntry("Reset local copy to commit {}".format(commit))
    write_repo_lock.switch_to(commit)


def detect_artifact(local_repo_path, git_server, repository_name, commit, environment_name,
                    artifact_detector):
    yield "Detect artifact source"
    try:
        artifact = artifact_detector(local_repo_path, git_server, repository_name, commit, environment_name)
        assert artifact is not None
    except NoArtifactDetected:
        # Default artifact: just copy the repo
        artifact = GitArtifact(local_repo_path)
    yield LogEntry("Artifact type: {}".format(artifact.description()))
    yield artifact
    return


def get_artifact(artifact):
    yield "Obtain a local copy of the artifact to deploy"
    yield artifact.obtain()
    return


def run_and_delete_predeploy(working_directory, environment_name, commit):
    yield "Run 'predeploy.sh'"
    for e in capture("predeploy.sh", exec_script, working_directory, 'predeploy.sh', [environment_name, commit]): yield e
    yield LogEntry(working_directory)
    for e in capture('delete predeploy.sh', exec_cmd, cmd=['cd', working_directory, '&&', 'rm', '-f', 'predeploy.sh'], use_shell=True): yield e


def parallel_sync(destination_path, sync_options, branch, commit, local_path, hosts, max_parallel_sync):
    yield "Sync to hosts {}".format(', '.join(host.name for host in hosts))
    if sync_options is None or len(sync_options) == 0:
        sync_options = '-az --delete'
    destination_path = destination_path + '/' if not destination_path.endswith('/') else destination_path

    partial = functools.partial(sync, destination_path, sync_options, branch, commit, local_path)
    try:
        pool = Pool(min(len(hosts), max_parallel_sync))
        it = pool.imap_unordered(partial, hosts)
        for entry_group in it:  # Block until the copy is complete
            for entry in entry_group:
                yield entry
    finally:
        pool.close()
    yield LogEntry("Copy on all servers complete.")


# sync options is a str for now
def sync(destination_path, sync_options, branch, commit, local_path, host):
    log_entries = []
    try:
        release_status = get_release_status(host, destination_path)
        log_entries.append(LogEntry("On {}, previous release: {}".format(host.name, release_status.format_commit())))
        log_entries.append(LogEntry("Copying to {}@{}:{}".format(host.username, host.name, destination_path)))
        for e in capture('mkdir', run_cmd_by_ssh, host, ['mkdir', '-p', destination_path]):
            log_entries.append(e)
        destination = "{}@{}:{}".format(host.username, host.name, destination_path)
        cmd = ['rsync', '-e', 'ssh -p {}'.format(host.port), '--exclude=.git'] + sync_options.split(" ") + [local_path, destination]
        for e in capture(' '.join(cmd), exec_cmd, cmd):
            log_entries.append(e)

        # Copy release file
        now = datetime.datetime.utcnow()
        release_file_contents = gitutils.release_file_contents(branch, commit, now, destination_path)
        for e in capture('copy release file', run_cmd_by_ssh, host, ['echo', "'{}'".format(release_file_contents), '>', os.path.join(destination_path, '.git_release')]):
            log_entries.append(e)
    except Exception as e:
        log_entries.append("Error when syncing to server {}".format(host.name), severity=Severity.ERROR)
        log_entries.append(str(e))
    return log_entries


def release(host, method, remote_repo_path, production_folder, release_path):
    yield "Release on {}".format(host.name)
    if method == 'inplace':
        pass  # Nothing to do, remore_repo_path + production_folder == release_path in this case
    elif method == 'symlink':
        # Atomic link change (thanks to rename with 'mv -T')
        ln_cmd = ['cd', remote_repo_path, '&&', 'ln', '-s', release_path, 'tmp-link', '&&', 'mv', '-T', 'tmp-link', os.path.join(remote_repo_path, production_folder)]
        for e in capture('symlink', run_cmd_by_ssh, host, ln_cmd): yield e
    else:
        raise ValueError('Unsupported release method: {}'.format(method))


def run_and_delete_deploy(host, remote_working_directory, environment_name, commit):
    yield "Run 'deploy.sh' on {}".format(host.name)
    out = capture("Run 'deploy.sh'", exec_script_remote, host, remote_working_directory, "deploy.sh", [environment_name, host.name, commit])
    for e in out:
        yield e
    rm_cmd = ['cd', remote_working_directory, '&&', 'rm', '-f', 'deploy.sh']
    for e in capture("delete 'deploy.sh'", run_cmd_by_ssh, host, rm_cmd): yield e


def disable_clusters(clusters, haproxy_auth):
    for r in cluster_action(clusters, haproxy_auth, HAProxyAction.DISABLE):
        yield r


def enable_clusters(clusters, haproxy_auth):
    for r in cluster_action(clusters, haproxy_auth, HAProxyAction.ENABLE):
        yield r


def ensure_clusters_up(clusters, haproxy_auth):
    yield "Ensure all servers in clusters {} are up".format(", ".join(cluster.name for cluster in clusters))
    for cluster in clusters:
        host = cluster.haproxy_host
        if host is None:
            continue
        keys = [s.haproxy_key for s in cluster.servers]
        # Will raise an exception if the cluster is not UP (I know, I know... TODO refactor)
        haproxy_action(host, keys, haproxy_auth, 'UP', HAProxyAction.ENABLE)


def cluster_action(clusters, haproxy_auth, action):
    if action == HAProxyAction.ENABLE:
        verb = "Enable"
    elif action == HAProxyAction.DISABLE:
        verb = "Disable"
    yield "{} clusters {}".format(verb, ", ".join(cluster.name for cluster in clusters))
    for cluster in clusters:
        if cluster.haproxy_host is None:
            yield LogEntry('Cluster {} has no HAProxy configured, skipping.'.format(cluster.name))
            continue
        servers_description = ", ".join("{} ({})".format(server.server_def.name, server.haproxy_key) for server in cluster.servers)
        yield LogEntry('{} cluster {} (servers {})'.format(verb, cluster.name, servers_description))
        haproxy_action(cluster.haproxy_host, [server.haproxy_key for server in cluster.servers], haproxy_auth, '', action)


def run_local_tests(environment, local_repo_path, branch, commit, host, mail_sender, mail_report_to):
    yield "Run local tests (execute tests/run_local_tests.sh)"
    report = run_test(environment, branch, commit, host, mail_sender, local=True, local_repo_path=local_repo_path, mail_report_to=mail_report_to)

    if report is None:
        yield LogEntry("No script 'tests/run_local_tests.sh', skipping.")
        return

    yield LogEntry(report.format())

    if report.failed:
        yield LogEntry("Tests failed.", severity=Severity.ERROR)


def run_remote_tests(environment, branch, commit, host, mail_sender, mail_report_to):
    yield "Run remote tests (execute tests/run_tests.sh on the remote server)"
    report = run_test(environment, branch, commit, host, mail_sender, local=False, mail_report_to=mail_report_to)

    if report is None:
        yield LogEntry("No script 'tests/run_tests.sh', skipping.")
        return

    yield LogEntry(report.format())

    if report.failed:
        yield LogEntry("Tests failed on the remote server.", severity=Severity.ERROR)


def check_servers_availability(session, current_deploy_id, servers, environment_name, branch, commit):
    yield "Check that the servers are available"
    server_ids = [s.id for s in servers]
    q = session.query(m.DeploymentView).\
        filter(m.DeploymentView.server_id.in_(server_ids)).\
        union(
            session.query(m.DeploymentView).
            join(m.Cluster).
            join(m.ClusterServerAssociation).
            filter(m.ClusterServerAssociation.server_id.in_(server_ids)),
            session.query(m.DeploymentView).
            filter(m.DeploymentView.server_id == None).
            filter(m.DeploymentView.cluster_id == None).
            join(m.DeploymentView.environment).
            join(m.Environment.clusters).
            join(m.Cluster.servers).
            filter(m.ClusterServerAssociation.server_id.in_(server_ids))
        ).\
        filter(m.DeploymentView.status != "COMPLETE").\
        filter(m.DeploymentView.status != "FAILED").\
        filter(m.DeploymentView.id != current_deploy_id)

    other_deployments = q.all()
    for deployment in other_deployments:
        if deployment.date_start_deploy is not None and deployment.date_start_deploy + datetime.timedelta(minutes=20) < datetime.datetime.utcnow():
            yield LogEntry('Deployment (id {}, repo {}, env {}) already in progress since more than 20 minutes ago, marking it as failed and going on...'.format(deployment.id, deployment.repository_name, deployment.environment_name), severity=Severity.WARN)
            entry = m.LogEntry("Timeout", severity=Severity.ERROR)
            deployment.log_entries.append(entry)
            deployment.end(DeploymentStatus.FAILED)
            session.commit()
            continue
        if environment_name.startswith('beta') or environment_name.startswith('prod'):
            yield LogEntry('Conflict with deployment (id {}, repo {}, env {})'.format(deployment.id, deployment.repository_name, deployment.environment_name), severity=Severity.ERROR)
            yield False
            return
        if deployment.branch == branch and deployment.commit == commit:
            yield LogEntry('Conflict with deployment (id {}) for the same branch ({}) and commit ({})'.format(deployment.id, branch, commit), severity=Severity.ERROR)
            yield False
            return
    yield True


def screenshot(url, repository_name, environment_name):
    yield "Take a screenshot of {}".format(url)
    fn = "/tmp/{}_{}.png".format(repository_name, environment_name)
    for e in capture("takepng", exec_cmd, ['/usr/local/bin/phantomjs/bin/phantomjs', '--ssl-protocol=any', '/usr/local/bin/phantomjs/bin/takepng.js', url, fn]):
        yield e
    files = [fn]
    yield files


def load_repo_configuration_file(local_repo_path):
    yield "Load deploy.json"
    filename = os.path.join(local_repo_path, 'deploy.json')

    if not os.path.exists(filename):
        yield LogEntry("No 'deploy.json' file found in the repository, skipping.")
        yield {}
        return

    with open(filename) as f:
        opt = json.loads(f.read())
        yield opt


#########
# Helpers
#########
def _get_git_release(host, target_path, timeout=4):
    remote_path = os.path.join(target_path, ".git_release")
    cmd = ['cat', remote_path]
    return run_cmd_by_ssh(host, cmd, timeout)


class ReleaseStatus(object):

    @classmethod
    def error(klass, error):
        return klass(error=error)

    @classmethod
    def release(klass, release):
        return klass(release=release)

    def __init__(self, release=None, error=None):
        assert release or error
        self._release = release
        self._error = error

    def to_dict(self, environment_id, server_id):
        id = "{}_{}".format(environment_id, server_id)
        if self._error:
            return {
                'id': id,
                'server_id': server_id,
                'environment_id': environment_id,
                'get_info_successful': False,
                'get_info_error': self._error,
            }
        elif self._release:
            return {
                'id': id,
                'server_id': server_id,
                'environment_id': environment_id,
                'get_info_successful': True,
                'release': self._release.to_dict(),
            }
        assert False, "Code should not reach here."

    def format_commit(self):
        if self._error:
            return "unknown"
        elif self._release:
            return "commit {}".format(self._release.commit)
        assert False, "Code should not reach here."


def get_release_status(host, target_path, timeout=4):
    (status, stdout, stderr) = _get_git_release(host, target_path, timeout)
    if status != 0:
        return ReleaseStatus.error(stdout + "\n" + stderr)
    try:
        return ReleaseStatus.release(gitutils.parse_release_file_contents(stdout))
    except gitutils.InvalidReleaseFile:
        return ReleaseStatus.error("Could not parse the .git_release file")


def concurrent_get_release_status(targets, timeout=4):
    """
    Args:
        target (list of tuples): a list of (host, target_path)
    """
    if len(targets) == 0:
        return []
    pool = multiprocessing.dummy.Pool(min(20, len(targets)))

    def _inner_get_release_status(target):
        host, path = target
        return get_release_status(host, path, timeout)

    try:
        return pool.map(_inner_get_release_status, targets, chunksize=1)
    finally:
        pool.close()


def run_test(environment, branch, commit, host, mail_sender, local, local_repo_path=None, mail_report_to=None):
    """Run the local test script if local is True, else the remote test script.
    For a local test script, hostname may be any server on which the project will be deployed (for compatibility reasons).

    Also end a mail if tests failed.

    Return:
        None if no test is defined, else a TestReport object
    """
    repository_name = environment.repository.name
    # Check whether tests are defined
    if local:
        if local_repo_path is None:
            raise ValueError("When running local tests, you must provide the local_repo_path ")
        tests_defined = os.path.exists(os.path.join(local_repo_path, "tests/run_local_tests.sh"))
        cmd = (exec_script, local_repo_path, "tests/run_local_tests.sh", [environment.name, host.name, branch, commit])
    else:
        tests_defined = remote_check_file_exists(os.path.join(environment.target_path, "tests/run_tests.sh"), host)
        cmd = (exec_script_remote, host, environment.target_path, "tests/run_tests.sh", [environment.name, host.name, branch, commit])

    if not tests_defined:
        return None

    result = cmd[0](*(cmd[1:]))
    report = m.TestReport.from_command_output(
        result, repository_name, environment.name, host.name, branch, commit)

    if report.failed and mail_report_to is not None:
        mail.send_mail(mail_sender,
                       mail_report_to,
                       "Tests failed for {} ({})".format(repository_name, environment.name),
                       report.format()
                       )

    return report


class InvalidHAProxyKeyFormat(Exception):
    pass


class UnexpectedHAproxyServerStatus(Exception):
    pass


class HAProxyAction(enum.Enum):
    ENABLE = 1,
    DISABLE = 2


# TODO: refactor that, it does two things (status check + change status), and sometimes only one of these
# actions is desired
def haproxy_action(haproxy_host, haproxy_keys, haproxy_auth, expected_status, changeto_status):
    # Setup connection to HAProxy
    haproxy_con = haproxy(haproxy_host, haproxy_auth)

    # Normalize keys (split them into backend, server)
    # TODO: store them normalized in the database!


    # Check that the key name is valid
    if any(k is None for k in haproxy_keys):
        raise InvalidHAProxyKeyFormat("Some HAProxy keys are not defined")
    invalid_keys = [k for k in haproxy_keys if k.count(',') != 1]
    if len(invalid_keys) > 0:
        raise InvalidHAProxyKeyFormat('The following HAProxy keys are invalid: {}'.format(invalid_keys))

    normalized_haproxy_keys = [key.split(',') for key in haproxy_keys]

    # Check status (all must have same status to do anything)
    for ha_backend, ha_server in normalized_haproxy_keys:
        ha_status_raw = haproxy_con.status(ha_backend, ha_server)
        if 'status' not in ha_status_raw:
            raise UnexpectedHAproxyServerStatus("Server [%s] of backend [%s] not found in haproxy, status was:[%s]." % (ha_server, ha_backend, json.dumps(ha_status_raw)))
        ha_status = ha_status_raw['status']
        logger.info("HAProxy current status of [%s/%s]: [%s] expected:[%s]" % (ha_backend, ha_server, ha_status, expected_status))
        if expected_status not in ha_status:
            raise UnexpectedHAproxyServerStatus("Server [%s] of backend [%s] not UP in haproxy." % (ha_server, ha_backend))

    # Disable servers in HAProxy
    for ha_backend, ha_server in normalized_haproxy_keys:
        ha_status = haproxy_con.status(ha_backend, ha_server)['status']
        if changeto_status == HAProxyAction.DISABLE and ("UP" in ha_status):
            logger.info("HAProxy change status of [%s/%s] from [%s] to [%s]" % (ha_backend, ha_server, ha_status, changeto_status))
            ha_ret = haproxy_con.disable(ha_backend, ha_server)
        elif changeto_status== HAProxyAction.ENABLE and ("MAINT" in ha_status):
            logger.info("HAProxy change status of [%s/%s] from [%s] to [%s]" % (ha_backend, ha_server, ha_status, changeto_status))
            ha_ret = haproxy_con.enable(ha_backend, ha_server)
        else:
            ha_ret = "OK"
            logger.info("HAProxy status already OK for [%s/%s] [%s] == [%s]" % (ha_backend, ha_server, ha_status, changeto_status))

        if ha_ret != "OK":
            raise UnexpectedHAproxyServerStatus("Server [%s] of backend [%s] status could not be changed: [%s]." % (ha_server, ha_backend, ha_ret))
