# Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).
import unittest
import tempfile
import os
import shutil
import datetime
import json

from deployment import samodels as m, execution, executils, database

from freezegun import freeze_time

try:
    from unittest import mock
except ImportError as e:
    import mock


class DummyStore():

    def register_log_entry(self, deploy_id, log_entry):
        pass


class MyException(Exception):
    pass


class TestDeployment(unittest.TestCase):

    def setUp(self):
        config = execution.GeneralConfig(base_repos_path='/tmp/tests/',
                                         haproxy_user="hauser",
                                         haproxy_password="hapwd",
                                         mail_sender='deploy@withings.com',
                                         notify_mails=[])
        self.deployment = execution.Deployment(1, config, mock.MagicMock(), mock.MagicMock())
        self.deployment.view = m.DeploymentView()
        self.session = mock.MagicMock()

    def _dummy_step(self, raise_exception=True, log_error=False):
        yield "Step description"
        if raise_exception:
            raise MyException("I was asked to raise an exception")
        yield m.LogEntry('some log', execution.Severity.INFO)
        if log_error:
            yield m.LogEntry('some error', execution.Severity.ERROR)
        yield "Step result"

    def test_run_step(self):
        step_output = execution.run_step(self.deployment, self._dummy_step, False, _session=self.session)
        self.assertEqual(step_output, "Step result")
        # First log entry is the step description
        self.assertEqual(2, len(self.deployment.view.log_entries))
        log_entry = self.deployment.view.log_entries[1]
        self.assertEqual("some log", log_entry.message)
        self.assertEqual(execution.Severity.INFO.format(), log_entry.severity)

    def test_run_step_failing(self):
        with self.assertRaises(execution.DeploymentError):
            execution.run_step(self.deployment, self._dummy_step, _session=self.session)

    def test_run_step_logging_error(self):
        with self.assertRaises(execution.DeploymentError):
            execution.run_step(self.deployment, self._dummy_step, False, True, _session=self.session)

    def test_run_step_no_abort_on_error(self):
        execution.run_step(self.deployment, self._dummy_step, raise_exception=False, log_error=True, _abort_on_error=False, _session=self.session)


class TestUtils(unittest.TestCase):

    def test_capture_only_stdout(self):
        entries = execution.capture("lambda", lambda x: 'stdout', 42)
        self.assertEqual(1, len(entries))
        entry = entries[0]
        self.assertEqual('lambda: stdout', entry.message)
        self.assertEqual(execution.Severity.INFO.format(), entry.severity)

    def test_capture_success(self):
        entries = execution.capture('success', lambda: (0, "stdout", "stderr"))
        self.assertEqual(2, len(entries))
        self.assertEqual('success: stdout', entries[0].message)
        self.assertEqual('success: stderr', entries[1].message)
        self.assertEqual(execution.Severity.INFO.format(), entries[0].severity)
        self.assertEqual(execution.Severity.WARN.format(), entries[1].severity)

    def test_capture_error(self):
        entries = execution.capture('error', lambda: (1, "stdout", "stderr"))
        self.assertEqual(3, len(entries))
        self.assertEqual('error: stdout', entries[0].message)
        self.assertEqual('error: stderr', entries[1].message)
        self.assertEqual('error: exited with code 1', entries[2].message)
        self.assertEqual(execution.Severity.INFO.format(), entries[0].severity)
        self.assertEqual(execution.Severity.ERROR.format(), entries[1].severity)
        self.assertEqual(execution.Severity.ERROR.format(), entries[2].severity)

    @mock.patch('deployment.haproxyapi.haproxy')
    def test_haproxy_action_unnormalized_keys(self, mock):
        with self.assertRaises(execution.InvalidHAProxyKeyFormat):
            execution.haproxy_action("fr-hq-vip-01", ["BADKEY"], "secret", "UP", execution.HAProxyAction.DISABLE)

    @mock.patch('deployment.execution.haproxy', autospec=True)
    def test_haproxy_action_disable(self, mock):
        mock(None, None).status.side_effect = lambda backend, server: {'status': 'UP'}
        mock(None, None).disable.side_effect = lambda backend, server: "OK"
        execution.haproxy_action("fr-hq-vip-01", ["BACKEND,SERVER-01", "BACKEND,SERVER-02"], "secret", "UP", execution.HAProxyAction.DISABLE)

    @mock.patch('deployment.execution.haproxy', autospec=True)
    def test_haproxy_action_enable(self, mock):
        mock(None, None).status.side_effect = lambda backend, server: {'status': 'MAINT'}
        mock(None, None).enable.side_effect = lambda backend, server: "OK"
        execution.haproxy_action("fr-hq-vip-01", ["BACKEND,SERVER-01", "BACKEND,SERVER-02"], "secret", "MAINT", execution.HAProxyAction.ENABLE)

    @mock.patch('deployment.execution.haproxy', autospec=True)
    def test_haproxy_action_unexpected_status(self, mock):
        mock(None, None).status.side_effect = lambda backend, server: {'status': 'MAINT'}
        with self.assertRaises(execution.UnexpectedHAproxyServerStatus):
            execution.haproxy_action("fr-hq-vip-01", ["BACKEND,SERVER-01", "BACKEND,SERVER-02"], "secret", "UP", execution.HAProxyAction.ENABLE)

    @mock.patch('deployment.execution.haproxy', autospec=True)
    def test_haproxy_action_failed(self, mock):
        mock(None, None).status.side_effect = lambda backend, server: {'status': 'MAINT'}
        mock(None, None).enable.side_effect = lambda backend, server: "Error: 42"
        with self.assertRaises(execution.UnexpectedHAproxyServerStatus):
            execution.haproxy_action("fr-hq-vip-01", ["BACKEND,SERVER-01", "BACKEND,SERVER-02"], "secret", "MAINT", execution.HAProxyAction.ENABLE)


class TestSteps(unittest.TestCase):

    def setUp(self):
        database.init_db("sqlite:////tmp/test.db")
        database.drop_all()
        database.create_all()
        self.session = database.Session()
        self._load_fixtures(self.session)
        self.admin_user = self.session.query(m.User).get(1)
        self.deploy_user = self.session.query(m.User).get(2)

    def _load_fixtures(self, session):
        users = [
            m.User(id=1, email="admin@withings.com", username="admin", accountid="a"),
            m.User(id=2, email="jdoe@withings.com", username="jdoe", accountid="b")
        ]
        clusters = [
            m.Cluster(id=1, haproxy_host='fr-hq-vip-01', name='vip-01'),
            m.Cluster(id=2, haproxy_host='fr-hq-vip-02', name='vip-02'),
        ]
        entities = [
            m.Environment(id=1, repository_id=2, name="dev", clusters=[clusters[1]], target_path="/path"),
            m.Environment(id=2, repository_id=1, name="dev", clusters=[clusters[0]], target_path="/path"),
            m.Role(id=1, name="admin", permissions=json.dumps({'admin': True}), users=[users[0]]),
            m.Role(id=2, name="deployer", permissions=json.dumps({'deploy_business_hours': [1]}), users=[users[1]]),
            m.Server(id=1, name='fr-hq-important-01', activated=True, port=22),
            m.Server(id=2, name='fr-hq-important-02', activated=True, port=22),
            m.Server(id=3, name='fr-hq-important-03', activated=True, port=22),
            m.Server(id=4, name='fr-hq-deactivated-01', activated=False, port=22),
            m.ClusterServerAssociation(server_id=1, cluster_id=1, haproxy_key="IMPORTANT-01"),
            m.ClusterServerAssociation(server_id=2, cluster_id=1, haproxy_key="IMPORTANT-02"),
            m.ClusterServerAssociation(server_id=4, cluster_id=2, haproxy_key=None),
            m.Repository(id=1, name="my repo", git_server="git", deploy_method="inplace"),
            m.Repository(id=2, name="another repo", git_server="git", deploy_method="inplace"),
            m.DeploymentView(id=1, repository_name="my repo", environment_name="dev", environment_id=2, cluster_id=None, server_id=None, branch="master", commit="abcde", user_id=1, status="QUEUED", queued_date=datetime.datetime.now()),
            m.DeploymentView(id=2, repository_name="another repo", environment_name="dev", environment_id=1, cluster_id=None, server_id=4, branch="master", commit="abcde", user_id=1, status="QUEUED", queued_date=datetime.datetime.now())

        ]
        for entity in clusters + users + entities:
            self.session.add(entity)
        self.session.commit()

    def tearDown(self):
        self.session.rollback()
        database.drop_all()
        database.stop_engine()

    # Returns the last value of a generator and the log entries it yielded. Asserts that the first value is a string, and all other (except maybe the last one) are of type LogEntry.
    def _unwind(self, generator, assert_no_error=False):
        step_description = generator.next()
        self.assertTrue(isinstance(step_description, str) or isinstance(step_description, unicode))
        entries = []
        out = None
        entry = None
        try:
            while True:
                entry = generator.next()
                if not(isinstance(entry, m.LogEntry)):
                    with self.assertRaises(StopIteration):
                        out = generator.next()
                else:
                    entries.append(entry)
                    if assert_no_error:
                        self.assertNotEquals(entry.severity, m.Severity.ERROR.format())
        except StopIteration:
            out = entry
            return out, entries

    def test_load_configuration(self):
        view = self.session.query(m.DeploymentView).get(1)
        self._unwind(execution.check_configuration(view), assert_no_error=True)

    def test_load_configuration_deactivated_servers(self):
        view = self.session.query(m.DeploymentView).get(2)
        _, entries = self._unwind(execution.check_configuration(view))
        self.assertTrue(any(entry.severity == m.Severity.ERROR.format() for entry in entries))

    # This is a Friday
    @freeze_time('2015-11-28 15:00')
    def test_check_deploy_allowed_friday_afternoon(self):
        authorized, _ = self._unwind(execution.check_deploy_allowed(self.deploy_user, 1, 'prod'))
        self.assertFalse(authorized)

    # This is a Sunday
    @freeze_time('2015-11-28')
    def test_check_deploy_allowed_super_user(self):
        authorized, _ = self._unwind(execution.check_deploy_allowed(self.admin_user, 1, 'prod'))
        self.assertTrue(authorized)

    # This is a Sunday
    @freeze_time('2015-11-28')
    def test_check_deploy_allowed_weekend(self):
        authorized, _ = self._unwind(execution.check_deploy_allowed(self.deploy_user, 1, 'prod'))
        self.assertFalse(authorized)

    # This is a Wednesday
    @freeze_time('2015-11-25 23:00')
    def test_check_deploy_allowed_late(self):
        authorized, _ = self._unwind(execution.check_deploy_allowed(self.deploy_user, 1, 'prod'))
        self.assertFalse(authorized)

    # This is Christmas! Yay!
    @freeze_time('2017-12-25 10:00')
    def test_check_deploy_allowed_bank_holiday(self):
        authorized, _ = self._unwind(execution.check_deploy_allowed(self.deploy_user, 1, 'prod'))
        self.assertFalse(authorized)

    @mock.patch('git.Repo.clone_from')
    def test_clone_repo(self, mock_func):
        self._unwind(execution.clone_repo('/tmp/deploy/my_repo_branch', 'my_repo', 'git'))
        mock_func.assert_called_with('git@git:my_repo', '/tmp/deploy/my_repo_branch')

    def test_run_predeploy(self):
        try:
            repo_path = tempfile.mkdtemp()
            with open(os.path.join(repo_path, 'predeploy.sh'), 'w') as f:
                f.write('echo -n "it works for env $1 commit $2"')
                f.flush()
            _, entries = self._unwind(execution.run_and_delete_predeploy(repo_path, "dev", "abcde"))
            self.assertEqual(2, len(entries))
            entry = entries[0]
            self.assertEqual("predeploy.sh: it works for env dev commit abcde", entry.message)
        finally:
            shutil.rmtree(repo_path)

    @mock.patch('deployment.execution.haproxy_action')
    def test_enable_clusters(self, mock_func):
        servers_1 = [(m.Server(id=1, name='fr-hq-server-01'), "BACKEND,01"), (m.Server(id=2, name='fr-hq-server-02'), "BACKEND,02")]
        servers_2 = [(m.Server(id=3, name='fr-hq-server-03'), "BACKEND,03"), (m.Server(id=4, name='fr-hq-server-04'), "BACKEND,04")]
        cluster_1 = m.Cluster(id=1, name="1", haproxy_host="fr-hq-vip-01")
        cluster_2 =	m.Cluster(id=2, name="2", haproxy_host="fr-hq-vip-02")
        asso_1 = [m.ClusterServerAssociation(server_def=server, cluster_def=cluster_1, haproxy_key=haproxy_key)
                  for server, haproxy_key in servers_1]
        asso_2 = [m.ClusterServerAssociation(server_def=server, cluster_def=cluster_2, haproxy_key=haproxy_key)
                  for server, haproxy_key in servers_2]
        clusters = [cluster_1, cluster_2]
        self._unwind(execution.enable_clusters(clusters, "secret"))
        mock_func.assert_has_calls([
            mock.call("fr-hq-vip-01", ["BACKEND,01", "BACKEND,02"], "secret", '', execution.HAProxyAction.ENABLE),
            mock.call("fr-hq-vip-02", ["BACKEND,03", "BACKEND,04"], "secret", '', execution.HAProxyAction.ENABLE)
        ])

    @mock.patch('deployment.execution.haproxy_action')
    def test_disable_clusters(self, mock_func):
        servers_1 = [(m.Server(id=1, name='fr-hq-server-01'), "BACKEND,01"), (m.Server(id=2, name='fr-hq-server-02'), "BACKEND,02")]
        servers_2 = [(m.Server(id=3, name='fr-hq-server-03'), "BACKEND,03"), (m.Server(id=4, name='fr-hq-server-04'), "BACKEND,04")]
        cluster_1 = m.Cluster(id=1, name="1", haproxy_host="fr-hq-vip-01")
        cluster_2 =	m.Cluster(id=2, name="2", haproxy_host="fr-hq-vip-02")
        asso_1 = [m.ClusterServerAssociation(server_def=server, cluster_def=cluster_1, haproxy_key=haproxy_key)
                  for server, haproxy_key in servers_1]
        asso_2 = [m.ClusterServerAssociation(server_def=server, cluster_def=cluster_2, haproxy_key=haproxy_key)
                  for server, haproxy_key in servers_2]
        clusters = [cluster_1, cluster_2]
        self._unwind(execution.disable_clusters(clusters, "secret"))
        mock_func.assert_has_calls([
            mock.call("fr-hq-vip-01", ["BACKEND,01", "BACKEND,02"], "secret", '', execution.HAProxyAction.DISABLE),
            mock.call("fr-hq-vip-02", ["BACKEND,03", "BACKEND,04"], "secret", '', execution.HAProxyAction.DISABLE)
        ])

    @mock.patch('deployment.execution.haproxy_action')
    def test_ensure_clusters_up(self, mock_func):
        servers_1 = [(m.Server(id=1, name='fr-hq-server-01'), "BACKEND,01"), (m.Server(id=2, name='fr-hq-server-02'), "BACKEND,02")]
        servers_2 = [(m.Server(id=3, name='fr-hq-server-03'), "BACKEND,03"), (m.Server(id=4, name='fr-hq-server-04'), "BACKEND,04")]
        cluster_1 = m.Cluster(id=1, name="1", haproxy_host="fr-hq-vip-01")
        cluster_2 =	m.Cluster(id=2, name="2", haproxy_host="fr-hq-vip-02")
        asso_1 = [m.ClusterServerAssociation(server_def=server, cluster_def=cluster_1, haproxy_key=haproxy_key)
                  for server, haproxy_key in servers_1]
        asso_2 = [m.ClusterServerAssociation(server_def=server, cluster_def=cluster_2, haproxy_key=haproxy_key)
                  for server, haproxy_key in servers_2]
        clusters = [cluster_1, cluster_2]
        self._unwind(execution.ensure_clusters_up(clusters, "secret"))
        mock_func.assert_has_calls([
            mock.call("fr-hq-vip-01", ["BACKEND,01", "BACKEND,02"], "secret", 'UP', execution.HAProxyAction.ENABLE),
            mock.call("fr-hq-vip-02", ["BACKEND,03", "BACKEND,04"], "secret", 'UP', execution.HAProxyAction.ENABLE)
        ])

    @freeze_time('2015-11-25 23:00')
    @mock.patch('deployment.executils.exec_cmd', autospec=True)
    @mock.patch('deployment.execution.exec_cmd', autospec=True)
    def test_sync(self, mock_func, mock_func_2):
        mock_func.side_effect = lambda *args, **kwargs: (0, "stdout", "stderr")
        mock_func_2.side_effect = lambda *args, **kwargs: (0, "stdout", "stderr")
        host = executils.Host("fr-hq-deployment-01", "scaleweb", 22)
        self._unwind(execution.parallel_sync("/home/scaleweb/project", "-cr --delete-after", "master", "abcde", "/home/deploy/project/", [host], 1))
        mock_func.assert_has_calls([
            mock.call(["rsync", "-e", "ssh -p 22", "--exclude=.git", "-cr", "--delete-after", "--exclude", ".git_release", "/home/deploy/project/", "scaleweb@fr-hq-deployment-01:/home/scaleweb/project/"]),
        ])
        mock_func_2.assert_has_calls([
            mock.call(['ssh', 'scaleweb@fr-hq-deployment-01', '-p', '22', 'mkdir', '-p', "/home/scaleweb/project/"], timeout=600),
            mock.call(['ssh', 'scaleweb@fr-hq-deployment-01', '-p', '22', 'echo', "'master\nabcde\n2015-11-25T23:00:00.000000\n/home/scaleweb/project/'", '>', '/home/scaleweb/project/.git_release'], timeout=600)
        ], any_order=True)  # TODO: investiguate the extra calls without parameters

    @mock.patch('deployment.executils.exec_cmd', autospec=True)
    def test_release_inplace(self, mock_func):
        host = executils.Host("some-server", "scaleweb", 22)
        self._unwind(execution.release(host, "inplace", "/home/scaleweb", "/home/scaleweb/", "project"))
        self.assertItemsEqual(mock_func.call_args_list, [])

    @mock.patch('deployment.executils.exec_cmd', autospec=True)
    def test_release_symlink(self, mock_func):
        mock_func.side_effect = lambda *args, **kwargs: (0, "stdout", "stderr")
        host = executils.Host("fr-hq-deployment-01", "scaleweb", 22)
        self._unwind(execution.release(host, "symlink", "/home/scaleweb/", "production", "/home/scaleweb/production_releases/20151204_prod_abcde/"))
        mock_func.assert_called_with(['ssh', 'scaleweb@fr-hq-deployment-01', '-p', '22', 'cd', '/home/scaleweb/', '&&', 'ln', '-s',  "/home/scaleweb/production_releases/20151204_prod_abcde/", 'tmp-link', '&&', 'mv', '-T', 'tmp-link', "/home/scaleweb/production"], timeout=600)

    @mock.patch('deployment.execution.exec_script_remote', autospec=True)
    @mock.patch('deployment.execution.run_cmd_by_ssh', autospec=True)
    def test_run_deploy(self, mock_script_func, mock_ssh_func):
        mock_script_func.side_effect = lambda *args, **kwargs: (0, "stdout", "stderr")
        mock_ssh_func.side_effect = lambda *args, **kwargs: (0, "stdout", "stderr")
        # Just run the method to catch obvious mistakes
        # It's too complex to write a robust non-trivial test against this (very simple) method.
        host = executils.Host("some-server", "scaleweb", 22)
        self._unwind(execution.run_and_delete_deploy(host, '/home/scaleweb/project', 'dev', 'abcde'), assert_no_error=True)

    @mock.patch('deployment.executils.exec_cmd', autospec=True)
    def test_run_tests(self, mock_func):
        mock_func.side_effect = lambda *args, **kwargs: (0, "ok", "still ok")
        env = self.session.query(m.Environment).get(2)
        host = executils.Host.from_server(env.servers[0], "scaleweb")

        # Remote
        report = execution.run_test(env, "master", "abcde", host=host,
                                    mail_sender="deploy@withings.com", local=False)
        self.assertEquals(False, report.failed)

        # Local
        report = execution.run_test(env, "master", "abcde", host=host,
                                    mail_sender="deploy@withings.com", local=True,
                                    local_repo_path="/home/deploy/project")
        self.assertIsNone(report)

    def test_check_servers_availability(self):
        servers = [self.session.query(m.Server).get(1)]
        ok, entries = self._unwind(execution.check_servers_availability(self.session, 2, servers, "prod", "prod", "abcde"))
        self.assertFalse(ok)
        servers = [self.session.query(m.Server).get(4)]
        ok, entries = self._unwind(execution.check_servers_availability(self.session, 2, servers, "prod", "prod", "abcde"))
        self.assertTrue(ok)


class TestSeverity(unittest.TestCase):

    def test_severity_format(self):
        self.assertEqual("info", execution.Severity.INFO.format())
        self.assertEqual("warn", execution.Severity.WARN.format())
        self.assertEqual("error", execution.Severity.ERROR.format())

    def test_severity_from_string(self):
        self.assertEqual(execution.Severity.INFO, execution.Severity.from_string("info"))
        self.assertEqual(execution.Severity.WARN, execution.Severity.from_string("warn"))
        self.assertEqual(execution.Severity.ERROR, execution.Severity.from_string("error"))
