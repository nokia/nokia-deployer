# Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).
import unittest
import os
import shutil
import datetime
import json


from io import BytesIO
import mock
from bottle import request, tob, HTTPError, default_app

from deployment import gitutils, database, samodels as m, api
from deployment.integrationexample.integration import DummyAuthentificator


def _mocked_get_git_release(host, cmd, timeout):
    message = """prod
ee31430cc3b28596857d50e67c117a5ec8825fec
2016-02-16 16:44:32.238700
/home/scaleweb/websites/backend/
    """
    return (0, message, None)


# Compute this only once to speed up tests
AUTH_TOKEN = api.hash_token("iamarobot", 4)


class TestApi(unittest.TestCase):

    def setUp(self):
        database.init_db("sqlite:////tmp/test.db")
        # Speed up tests
        default_app().config["deployer.bcrypt_log_rounds"] = 4
        default_app().config["deployer.authentificator"] = DummyAuthentificator()
        database.drop_all()
        database.create_all()
        self.session = database.Session()
        self._load_fixtures(self.session)

    def tearDown(self):
        self.session.rollback()
        database.drop_all()
        database.stop_engine()
        # Bottle memoizes the 'request.json' attribute.
        # We don't want it memoized between two unit tests.
        # So let's dememoize it (yes, I don't think that word exists either).
        request.environ.pop('bottle.request.json', None)
        request.environ.pop('bottle.request.body', None)

    def _set_body_json(self, data):
        body = json.dumps(data)
        request.environ['CONTENT_LENGTH'] = str(len(tob(body)))
        request.environ['CONTENT_TYPE'] = 'application/json'
        request.environ['wsgi.input'] = BytesIO()
        request.environ['wsgi.input'].write(tob(body))
        request.environ['wsgi.input'].seek(0)

    def _load_fixtures(self, session):
        users = [
            m.User(id=1, username='username', email='username@withings.com', accountid=123456),
            m.User(id=2, username='root', email='root@withings.com', accountid=1234567),
            m.User(id=3, username='impersonator', email='also_root@withings.com', accountid=-1, auth_token=AUTH_TOKEN),
            m.User(id=4, username='default', email='default@withings.com', accountid=-1),
        ]
        # By default, test as a superadmin
        request.account = users[1]
        servers = [
            m.Server(name='fr-hq-important-01', port=22),
            m.Server(name='fr-hq-important-02', port=22),
            m.Server(name='fr-hq-important-03', port=22),
        ]
        clusters = [
            m.Cluster(haproxy_host='fr-hq-vip-01', name='vip-01'),
            m.Cluster(haproxy_host='fr-hq-vip-02', name='vip-02'),
        ]
        entities = [
            m.Role(id=1, name="deployer", permissions=json.dumps({'deploy': [1]}), users=[users[0]]),
            m.Role(id=2, name="admin", permissions=json.dumps({'admin': True}), users=[users[1]]),
            m.Role(id=3, name="impersonator", permissions=json.dumps({'impersonate': True}), users=[users[2]]),
            m.Role(id=4, name="useless", permissions=json.dumps({"deploy": [42]}), users=[users[3]]),
            m.Environment(id=1, repository_id=2, name="dev", remote_user="deploy", target_path="/path"),
            m.Environment(id=2, repository_id=1, name="dev", deploy_branch="master", env_order=1, clusters=[clusters[0]], target_path="/path"),
            m.Environment(id=3, repository_id=1, name="beta", deploy_branch="prod", env_order=2, target_path="/path"),
            m.Environment(id=4, repository_id=1, name="prod", deploy_branch="prod", env_order=3, target_path="/path"),
            m.ClusterServerAssociation(server_def=servers[0], cluster_def=clusters[0], haproxy_key="IMPORTANT-01"),
            m.ClusterServerAssociation(server_def=servers[1], cluster_def=clusters[0], haproxy_key="IMPORTANT-02"),
            m.Repository(id=1, name="my repo", git_server="git", deploy_method="inplace", _notify_owners_mails="toto@withings.com, tata@withings.com"),
            m.Repository(id=2, name="another repo", git_server="git", deploy_method="inplace", _notify_owners_mails="toto@withings.com, tata@withings.com"),
            m.Repository(id=3, name="another repo again", git_server="git", deploy_method="inplace", _notify_owners_mails="toto@withings.com, tata@withings.com"),
            m.DeploymentView(id=1, repository_name="my repo", environment_name="dev", branch="master", commit="abcde", user_id=1, status="COMPLETE", queued_date=datetime.datetime.now(), date_start_deploy=datetime.datetime.now(), environment_id=2),
            m.DeploymentView(id=2, repository_name="my other repo", environment_name="dev", branch="master", commit="defg", user_id=1, status="DEPLOY", queued_date=datetime.datetime.now(), date_start_deploy=datetime.datetime.now(), environment_id=None),
            m.DeploymentView(id=3, repository_name="my repo", environment_name="beta", branch="prod", commit="defg", user_id=1, status="COMPLETE", queued_date=datetime.datetime.now(), date_start_deploy=datetime.datetime.now(), environment_id=3),
            m.LogEntry(id=1, deploy_id=1, date=datetime.datetime.now(), severity=m.Severity.INFO.format(), message="some entry"),
        ]
        for entity in entities + users + servers + clusters:
            session.add(entity)
        session.commit()

    def test_list_environments(self):
        parsed = json.loads(api.environments_list(self.session))
        for env in parsed['environments']:
            self.assertTrue(env['deploy_authorized'])
        request.account = self.session.query(m.User).filter_by(username="username").one()
        parsed = json.loads(api.environments_list(self.session))
        for env in parsed['environments']:
            if env['id'] == 1:
                self.assertTrue(env['deploy_authorized'])
            else:
                self.assertFalse(env['deploy_authorized'])

    def test_get_environments(self):
        parsed = json.loads(api.environment_get(1, self.session))
        self.assertTrue(parsed['environment']['deploy_authorized'])

    def test_list_repositories(self):
        out = api.repositories_list(self.session)
        parsed = json.loads(out)
        self.assertEqual(3, len(parsed['repositories']))
        repo = parsed['repositories'][0]
        self.assertEqual("my repo", repo['name'])

    def test_get_repository_by_name(self):
        out = api.repository_get_by_name('my repo', self.session)
        parsed = json.loads(out)
        self.assertEqual("my repo", parsed['repository']['name'])
        self.assertEqual([2, 3, 4], parsed['repository']['environments'])

    def test_get_repository_by_id(self):
        out = api.repository_get_by_id(1, self.session)
        parsed = json.loads(out)
        self.assertEqual("my repo", parsed['repository']['name'])
        self.assertEqual([2, 3, 4], parsed['repository']['environments'])

    def test_list_repository_environments(self):
        out = api.repository_environments(1, self.session)
        parsed = json.loads(out)
        self.assertEqual(3, len(parsed['environments']))
        env = parsed['environments'][0]
        self.assertEqual('dev', env['name'])
        self.assertEqual('scaleweb', env['remote_user'])

    def test_list_deployments(self):
        out = api.deployments_list("my repo", self.session)
        parsed = json.loads(out)
        self.assertEqual(2, len(parsed['deployments']))
        deploy = parsed['deployments'][0]
        self.assertEqual('my repo', deploy['repository_name'])
        self.assertEqual('beta', deploy['environment_name'])

    def test_get_deployment(self):
        out = api.deployment_get(1, self.session)
        parsed = json.loads(out)
        self.assertEqual(1, parsed['deployment']['id'])

    def test_list_servers(self):
        out = api.servers_get(self.session)
        parsed = json.loads(out)
        self.assertEqual(3, len(parsed['servers']))

    def test_post_server(self):
        self._set_body_json({'name': 'fr-hq-server-01', 'port': 22})
        out = api.servers_post(self.session)
        parsed = json.loads(out)
        self.assertEqual('fr-hq-server-01', parsed['server']['name'])

    def test_delete_server(self):
        out = api.servers_delete(1, self.session)
        parsed = json.loads(out)
        self.assertEqual(1, parsed['server']['id'])

    def test_update_server(self):
        self._set_body_json({'name': 'fr-hq-renamed', 'port': 22})
        out = api.server_put(1, self.session)
        parsed = json.loads(out)
        self.assertEqual('fr-hq-renamed', parsed['server']['name'])

    def test_list_clusters(self):
        out = api.clusters_get(self.session)
        parsed = json.loads(out)
        candidates = [c for c in parsed['clusters'] if c['name'] == "vip-01"]
        self.assertEqual(1, len(candidates))
        cluster = candidates[0]
        self.assertEqual(2, len(cluster['servers']))

    def test_post_cluster(self):
        self._set_body_json({
            'name': 'cluster',
            'haproxy_host': 'vip',
            'servers': [
                {
                    'server_id': 1,
                    'haproxy_key': 'SERV01'
                }
            ]
        })
        out = api.clusters_post(self.session)
        parsed = json.loads(out)
        self.assertEqual('fr-hq-important-01', parsed['cluster']['servers'][0]['server']['name'])
        self.assertTrue(1 < parsed['cluster']['id'])

    def test_delete_cluster(self):
        out = api.clusters_delete(1, self.session)
        parsed = json.loads(out)
        self.assertEqual(1, parsed['cluster']['id'])

    def test_update_cluster(self):
        self._set_body_json({
            'name': 'renamed',
            'haproxy_host': 'new host',
            'servers': [
                {
                    'server_id': 2,
                    'haproxy_key': 'new_key'
                }
            ]
        })
        out = api.cluster_put(1, self.session)
        parsed = json.loads(out)
        self.assertEqual(1, parsed['cluster']['id'])
        # Make sure the change was effective
        out = api.clusters_get(self.session)
        parsed = json.loads(out)
        candidates = [c for c in parsed['clusters'] if c['name'] == 'renamed']
        self.assertEqual(1, len(candidates))
        cluster = candidates[0]
        self.assertEqual('renamed', cluster['name'])
        self.assertEqual('new host', cluster['haproxy_host'])
        self.assertEqual(1, len(cluster['servers']))
        server = cluster['servers'][0]
        self.assertEqual('new_key', server['haproxy_key'])
        self.assertEqual('fr-hq-important-02', server['server']['name'])

    def test_update_repository(self):
        self._set_body_json({
            'name': 'renamed',
            'notify_owners_mails': 'owner@withings.com',
            'deploy_method': 'inplace',
            'git_server': 'the-other-git.corp.withings.com',
            'branches': ['preprod']
        })
        out = api.repository_put(1, self.session)
        parsed = json.loads(out)
        self.assertEqual(1, parsed['repository']['id'])

    def test_insert_repository(self):
        self._set_body_json({
            'name': 'new_repo',
            'notify_owners_mails': 'owner@withings.com',
            'deploy_method': 'inplace',
            'git_server': 'git.corp.withings.com',
            'branches': ['master']
        })
        out = api.repository_post(self.session)
        parsed = json.loads(out)
        self.assertEqual('new_repo', parsed['repository']['name'])

    def test_delete_repository(self):
        out = api.repository_delete(3, self.session)
        parsed = json.loads(out)
        self.assertEqual('another repo again', parsed['repository']['name'])

    def test_insert_environment(self):
        self._set_body_json({
            'name': 'new env',
            'repository_name': 'my repo',
            'target_path': '/project_folder',
            'auto_deploy': True,
            'remote_user': 'scaleweb',
            'sync_options': '-cr --delete-after',
            'env_order': 1,
            'deploy_branch': 'master',
            'clusters_id': [1],
            'fail_deploy_on_failed_tests': False
        })
        parsed = json.loads(api.repository_environments(1, self.session))
        before = len(parsed['environments'])
        parsed = json.loads(api.repository_environments_post(1, self.session))
        self.assertEqual(1, len(parsed['environment']['clusters']))
        self.assertNotEquals(-1, parsed['environment']['id'])
        parsed = json.loads(api.repository_environments(1, self.session))
        self.assertEqual(before + 1, len(parsed["environments"]))

    def test_update_environment(self):
        self._set_body_json({
            'name': 'renamed env',
            'repository_name': 'my repo',
            'target_path': '/remote/repo/path',
            'auto_deploy': True,
            'remote_user': 'scaleweb',
            'sync_options': '-cr --delete-after',
            'env_order': 1,
            'deploy_branch': 'master',
            'clusters_id': [1],
            'fail_deploy_on_failed_tests': False
        })
        parsed = json.loads(api.environment_put(1, self.session))
        self.assertEquals(1, parsed['environment']['id'])

    def test_delete_environment(self):
        parsed = json.loads(api.environment_delete(1, self.session))
        self.assertEqual(1, parsed['environment']['id'])
        self.assertEqual(2, parsed['environment']['repository_id'])

    def test_list_recent_deployments(self):
        parsed = json.loads(api.deployments_recent(self.session))
        self.assertEqual(3, len(parsed['deployments']))

    @mock.patch('deployment.api.default_app')
    def test_start_deployment(self, mocked):
        self._set_body_json({
            'target': {
                'cluster': None,
                'server': None
            },
            'branch': 'master',
            'commit': 'abcde'
        })
        api.environments_start_deployment(1, self.session)

    @mock.patch('deployment.api.default_app')
    def test_start_deployment_non_admin(self, mocked):
        request.account = self.session.query(m.User).filter(m.User.username == 'username').one()
        self._set_body_json({
            'target': {
                'cluster': None,
                'server': None
            },
            'branch': 'master',
            'commit': 'abcde'
        })
        api.environments_start_deployment(1, self.session)

    @mock.patch('deployment.api.default_app')
    def test_start_deployment_with_impersonating(self, mocked):
        request.account = self.session.query(m.User).filter(m.User.username == 'impersonator').one()
        request.environ['HTTP_X_IMPERSONATE_USERNAME'] = 'username'
        self._set_body_json({
            'target': {
                'cluster': None,
                'server': None
            },
            'branch': 'master',
            'commit': 'abcde'
        })
        api.environments_start_deployment(1, self.session)

    @mock.patch('deployment.api.default_app')
    def test_start_deployment_with_impersonating_unprivilegied_user(self, mocked):
        request.account = self.session.query(m.User).filter(m.User.username == 'impersonator').one()
        request.environ['HTTP_X_IMPERSONATE_USERNAME'] = 'username'
        self._set_body_json({
            'target': {
                'cluster': None,
                'server': None
            },
            'branch': 'master',
            'commit': 'abcde'
        })
        with self.assertRaises(HTTPError) as cm:
            api.environments_start_deployment(2, self.session)
            self.assertEquals(403, cm.exception.code)

    def test_users_list(self):
        parsed = json.loads(api.users_list(self.session))
        self.assertEquals(4, len(parsed['users']))

    def test_users_get(self):
        parsed = json.loads(api.users_get(1, self.session))
        self.assertEqual('username', parsed['user']['username'])

    def test_users_post_with_auth_token(self):
        self._set_body_json({
            'roles': [1],
            'username': 'tototherobot',
            'email': 'toto.therobot@withings.com',
            'accountid': -1,
            'auth_token': 'iamarobotnoreally'
        })
        parsed = json.loads(api.users_post(self.session))
        self.assertEqual('tototherobot', parsed['user']['username'])
        # Try to get a session token for this user
        self._set_body_json({
            'username': 'tototherobot',
            'auth_token': 'iamarobotnoreally'
        })
        parsed = json.loads(api.auth_token(self.session))
        self.assertTrue('token' in parsed)

    def test_users_put(self):
        self._set_body_json({
            'roles': [1],
            'username': 'jdoe',
            'email': 'jdoe@withings.com',
            'accountid': '12485456'
        })
        parsed = json.loads(api.users_put(1, self.session))
        self.assertEqual('jdoe', parsed['user']['username'])

    def test_users_put_with_auth_token(self):
        self._set_body_json({
            'roles': [1],
            'username': 'tototherobot',
            'email': 'toto.therobot@withings.com',
            'accountid': -1,
            'auth_token': 'iamarobotnoreally'
        })
        parsed = json.loads(api.users_put(1, self.session))
        self.assertEqual('tototherobot', parsed['user']['username'])
        # Try to get a session token for this user
        self._set_body_json({
            'username': 'tototherobot',
            'auth_token': 'iamarobotnoreally'
        })
        parsed = json.loads(api.auth_token(self.session))
        self.assertTrue('token' in parsed)

    def test_users_delete(self):
        json.loads(api.users_delete(1, self.session))
        parsed = json.loads(api.users_list(self.session))
        self.assertEquals(3, len(parsed['users']))

    def test_roles_list(self):
        parsed = json.loads(api.roles_list(self.session))
        self.assertEquals(4, len(parsed['roles']))

    def test_roles_get(self):
        parsed = json.loads(api.roles_get(1, self.session))
        self.assertTrue('admin' not in parsed['role']['permissions'] or not parsed['role']['permissions']['admin'])
        parsed = json.loads(api.roles_get(2, self.session))
        self.assertEquals(True, parsed['role']['permissions']['admin'])

    def test_roles_delete(self):
        json.loads(api.roles_delete(1, self.session))
        parsed = json.loads(api.roles_list(self.session))
        self.assertEquals(3, len(parsed['roles']))

    def test_auth_using_token(self):
        self._set_body_json({
            'username': 'impersonator',
            'auth_token': 'iamarobot'
        })
        parsed = json.loads(api.auth_token(self.session))
        self.assertTrue('token' in parsed)
        self.assertEquals('impersonator', parsed['user']['username'])

    def test_auth_using_invalid_token(self):
        self._set_body_json({
            'username': 'impersonator',
            'auth_token': 'iamnotreallyarobot'
        })
        with self.assertRaises(HTTPError):
            api.auth_token(self.session)

    @mock.patch("deployment.execution.run_cmd_by_ssh", side_effect=_mocked_get_git_release)
    def test_fetch_server_status(self, mocked):
        parsed = json.loads(api.environments_servers(2, self.session))
        self.assertTrue(2, len(parsed['servers_status']))
        release_data = parsed['servers_status']['1']
        self.assertEqual("fr-hq-important-01", release_data['server']['name'])
        self.assertTrue(release_data['release_status']['get_info_successful'])
        self.assertEqual("prod", release_data['release_status']['release']['branch'])
        self.assertEqual("ee31430cc3b28596857d50e67c117a5ec8825fec", release_data['release_status']['release']['commit'])

    @mock.patch("deployment.execution.run_cmd_by_ssh", side_effect=_mocked_get_git_release)
    def test_fetch_server_releases(self, mocked):
        parsed = json.loads(api.servers_get_environments(1, self.session))
        self.assertTrue(1, len(parsed['releases']))
        release_data = parsed['releases'][0]
        self.assertEqual(2, release_data['environment']['id'])
        self.assertEqual(2, len(release_data['servers']))
        server = release_data['servers'][0]
        self.assertEqual("fr-hq-important-01", server['server']['name'])
        self.assertTrue(server['release_status']['get_info_successful'])
        self.assertEqual("prod", server['release_status']['release']['branch'])
        self.assertEqual("ee31430cc3b28596857d50e67c117a5ec8825fec", server['release_status']['release']['commit'])

    @mock.patch("deployment.execution.run_cmd_by_ssh",
                side_effect=lambda host, cmd, timeout: (1, "error", "oups"))
    def test_fetch_server_status_failed(self, mocked):
        parsed = json.loads(api.environments_servers(2, self.session))
        self.assertTrue(2, len(parsed['servers_status']))
        release_data = parsed['servers_status']['1']
        self.assertEqual("fr-hq-important-01", release_data['server']['name'])
        self.assertFalse(release_data['release_status']['get_info_successful'])
        self.assertEquals("error\noups", release_data['release_status']['get_info_error'])

    @mock.patch("deployment.gitutils.LocalRepository")
    def test_env_order(self, mock):
        default_app().config["general.local_repo_path"] = "/tmp/deployerrepo"
        # Required, otherwise the API does not even try to read the commits (and so our mock is useless)
        for env_id in range(2, 5):
            dirname = self.session.query(m.Environment).get(env_id).local_repo_directory_name
            gitutils.mkdir_p(os.path.join("/tmp/deployerrepo", dirname))
        try:
            now = datetime.datetime.now()
            commits = [
                gitutils.Commit("first commit", "me@withings.com", "abcde", now),
                gitutils.Commit("second commit", "still.me@withings.com", "aaaaa", now),
                gitutils.Commit("second commit", "still.me@withings.com", "defg", now),
            ]
            mock().list_commits.return_value = commits

            parsed = json.loads(api.get_commits_by_env(2, self.session))
            self.assertEqual(3, len(parsed['commits']))
            for commit in parsed['commits']:
                self.assertTrue(commit['deployable'])

            parsed = json.loads(api.get_commits_by_env(3, self.session))
            self.assertEqual(3, len(parsed['commits']))
            for commit in parsed['commits']:
                self.assertTrue(commit['deployable'])

            parsed = json.loads(api.get_commits_by_env(4, self.session))
            self.assertEqual(3, len(parsed['commits']))
            deployable = [c for c in parsed['commits'] if c["deployable"]]
            self.assertEqual(1, len(deployable))
            self.assertEqual("defg", deployable[0]["hexsha"])
            for commit in parsed['commits']:
                if commit['hexsha'] != "defg":
                    self.assertFalse(commit['deployable'])
        finally:
            shutil.rmtree("/tmp/deployerrepo")

    def test_expunge_user(self):
        user = self.session.query(m.User).get(1)
        api._expunge_user(user, self.session)
        self.session.close()
        # Make sure we can access attributes after the session is closed
        self.assertEqual(1, len(user.roles))
        self.assertEqual(1, len(user.default_roles))

    def test_expunge_default_user(self):
        user = self.session.query(m.User).filter_by(username="default").one()
        api._expunge_user(user, self.session)
        self.session.close()
        # Make sure we can access attributes after the session is closed
        self.assertEqual(1, len(user.roles))
        self.assertEqual(0, len(user.default_roles))

    def test_diff_requires_login(self):
        # The default user should not be able to read diff
        user = self.session.query(m.User).filter_by(username="default").one()
        request.account = user
        request.query['from'] = 'ab'
        request.query['to'] = 'de'
        with self.assertRaises(HTTPError) as e:
            api.repositories_diff(1, self.session)
        self.assertEqual(403, e.exception.status_code)

    def test_list_deployments_requires_read(self):
        user = self.session.query(m.User).filter_by(username="default").one()
        request.account = user
        deploys = json.loads(api.deployments_list("my repo", self.session))['deployments']
        self.assertEqual(0, len(deploys))
        user = self.session.query(m.User).filter_by(username="root").one()
        request.account = user
        deploys = json.loads(api.deployments_list("my repo", self.session))['deployments']
        self.assertGreater(len(deploys), 0)

