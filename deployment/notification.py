# Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).
import string
from logging import getLogger
import socket
import time

import requests
import urlparse

from . import mail, websocket, database
from . import samodels as m


logger = getLogger(__name__)


class Notification(object):

    # evt_type is a str, payload is a dict
    def __init__(self, evt_type, payload=None):
        if payload is None:
            payload = {}
        self.evt_type = evt_type
        self.payload = payload

    @classmethod
    def deployment_start(klass, deployment_view):
        return klass('deployment.start', {
            'deploy_id': deployment_view.id
        })

    @classmethod
    def deployment_configuration_loaded(klass, deployment_view):
        return klass('deployment.configuration_loaded', {
            'environment_id': deployment_view.environment_id,
            'deployment': deployment_view
        })

    @classmethod
    def deployment_end(klass, deployment_view, screenshot_files=None):
        if screenshot_files is None:
            screenshot_files = []
        return klass('deployment.end', {
            'environment_id': deployment_view.environment_id,
            'deployment': deployment_view,
            'deploy_id': deployment_view.id,
            'screenshot_files': screenshot_files
        })

    @classmethod
    def deployment_step_start(klass, deployment_view, step_name):
        return klass('deployment.step_start', {
            'environment_id': deployment_view.environment_id,
            'deployment': deployment_view,
            'step_name': step_name
        })

    @classmethod
    def deployment_step_end(klass, deployment_view, step_name, step_failed):
        return klass('deployment.step_end', {
            'environment_id': deployment_view.environment_id,
            'deployment': deployment_view,
            'step_name': step_name,
            'step_failed': step_failed
        })

    @classmethod
    def deployer_started(klass):
        return klass('deployer.start')

    @classmethod
    def deployment_queued(klass, deploy_id, environment_id, repository_name, environment_name, branch, commit, user_id):
        return klass('deployment.queued', {
            'deploy_id': deploy_id,
            'environment_id': environment_id,
            'environment_name': environment_name,
            'repository_name': repository_name,
            'branch': branch,
            'commit': commit,
            'user_id': user_id
        })

    @classmethod
    def released_on_server(klass, deployment_view, server, new_release_date, new_branch, new_commit):
        return klass('deployment.step.release', {
            'deployment': deployment_view,
            'server': server,
            'release_info': {
                'commit': new_commit,
                'release_date': new_release_date,
                'branch': new_branch
            }
        })

    # If deployment_id is not none, it means that commits were fetched
    # during a deployment (a notifier may want to take a different action
    # in this case)
    @classmethod
    def commits_fetched(klass, environment_id, local_repo_path, git_server, repository, deploy_branch, deployment_id=None):
        return klass('commits.fetched', {
            'environment_id': environment_id,
            'local_repo_path': local_repo_path,
            'deployment_id': deployment_id,
            'repository': repository,
            'git_server': git_server,
            'deploy_branch': deploy_branch
        })


class NotifierCollection(object):

    def __init__(self, *notifiers):
        self.notifiers = notifiers

    def dispatch(self, event):
        for n in self.notifiers:
            try:
                n.dispatch(event)
            except Exception:
                logger.exception("Error when dispatching event: {}".format(event.evt_type))


class RemoteDeployerNotifier(object):

    # Take care of not passing the current deployer URL
    def __init__(self, urls, deployer_username, deployer_token):
        self.urls = urls
        self.session_token = None
        self.deployer_username = deployer_username
        self.deployer_token = deployer_token

    def get_session_token(self, url):
        with database.session_scope() as session:
            deployer_user = session.query(m.User).filter(m.User.username == self.deployer_username).one_or_none()
            if deployer_user is None:
                raise ValueError('No user found with username {}, '
                                 'can not forward the websocket event to other deployer instances. '
                                 'Check the cluster->this_deployer_username setting.'.format(self.deployer_username)
                                 )
            r = requests.post(urlparse.urljoin(url, '/api/auth/token'),
                              json={'username': deployer_user.username, 'auth_token': self.deployer_token})
        r.raise_for_status()
        self.session_token = r.json()['token']

    def dispatch(self, event):
        if event.evt_type not in WebSocketNotifier.FORWARDED_EVENTS_TYPES:
            return
        for url in self.urls:
            if self.session_token is None:
                self.get_session_token(url)
            kwargs = {'json': {'event': WebSocketNotifier.event_to_websocket(event).to_dict()}, 'headers': {'Content-Type': 'application/json', 'X-Session-Token': self.session_token}}
            args = [urlparse.urljoin(url, '/api/notification/websocketevent')]
            r = requests.post(*args, **kwargs)
            if r.status_code == 403:
                self.get_session_token(url)
                kwargs['headers']['X-Session-Token'] = self.session_token
                r = requests.post(*args, **kwargs)
            r.raise_for_status()


class GraphiteNotifier(object):

    VALID_CHARACTERS = string.ascii_letters + string.digits + '-_'

    def __init__(self, carbon_host, carbon_port):
        self.carbon_host = carbon_host
        self.carbon_port = carbon_port

    def dispatch(self, event):
        if self.carbon_host is None:
            return
        if event.evt_type != "deployment.end":
            return
        deployment = event.payload["deployment"]
        if deployment.status != m.DeploymentStatus.COMPLETE.to_db_format():
            return
        metric_name = "{}.deploy.{}".format(
            GraphiteNotifier.sanitize_for_graphite(deployment.environment.name),
            GraphiteNotifier.sanitize_for_graphite(deployment.environment.repository.name)
        )
        metric_val = 1
        message = '{} {} {}\n'.format(metric_name, metric_val, int(time.time()))
        sock = socket.socket()
        sock.connect((self.carbon_host, self.carbon_port))
        sock.sendall(message)
        sock.close()

    @classmethod
    def sanitize_for_graphite(kls, name):
        return ''.join('-' if c not in kls.VALID_CHARACTERS else c for c in name)


class MailNotifier(object):

    # always_notify: array of email adresses that receive all notifications
    def __init__(self, sender, always_notify):
        self.sender = sender
        self.always_notify  = always_notify

    def dispatch(self, event):
        if event.evt_type != "deployment.end":
            return
        deployment = event.payload["deployment"]
        screenshot_files = event.payload["screenshot_files"]
        self.send_deployment_mail(deployment, screenshot_files)

    def send_deployment_mail(self, deployment, screenshot_files):
        receivers = set(deployment.environment.repository.notify_owners_mails + self.always_notify)
        message, subject = self._message_with_configuration(deployment)
        mail.send_mail(self.sender, receivers, subject, message, screenshot_files)

    def _message_with_configuration(self, deployment):
        template = """
== Deployment summary (id: {deploy_id}) ==

= General info =
Status: {status}

Repository: {repository}
Branch: {branch}
Commit: {commit}

Started: {date_start}
Completed: {date_end}

= Clusters =

{clusters_description}

= Log =

{log}
        """
        clusters_description = []
        for cluster in deployment.target_clusters:
            server_names = ", ".join([s.server_def.name for s in cluster.servers])
            clusters_description.append("{}: {}".format(cluster.name, server_names))
        was_successful = deployment.status == m.DeploymentStatus.COMPLETE.to_db_format()
        status = "was successful" if was_successful else "failed"
        short_status = "success" if was_successful else "failure"
        msg = template.format(status=short_status,
                              repository=deployment.environment.repository.name,
                              branch=deployment.branch,
                              commit=deployment.commit,
                              date_start=deployment.date_start_deploy,
                              date_end=deployment.date_end_deploy,
                              clusters_description="\n".join(clusters_description),
                              log="\n".join(s.format() for s in deployment.log_entries),
                              deploy_id=deployment.id
                              )
        subject = '{}/{} (branch {}): deployment {}'.format(
            deployment.repository_name,
            deployment.environment_name,
            deployment.environment.deploy_branch,
            status
        )
        return msg, subject


class WebSocketNotifier(object):

    FORWARDED_EVENTS_TYPES = ["deployment.queued", "deployment.configuration_loaded", "deployment.end", "deployment.step_start", "deployment.step.release", "commits.fetched"]


    # Push events to a queue
    # Also set up the given worker to answer to log requests
    def __init__(self, ws_worker):
        self.ws_worker = ws_worker
        self.ws_worker.listen('subscribe', self._handle_log_request)
        self.ws_worker.listen('unsubscribe', self._handle_log_request)
        self.ws_worker.listen('websocket.ping', self._handle_ping)
        self._deploy_schema = m.DeploymentView.__marshmallow__()

    @classmethod
    def event_to_websocket(self, event):
        self._deploy_schema = m.DeploymentView.__marshmallow__()
        if event.evt_type not in self.FORWARDED_EVENTS_TYPES:
            raise ValueError("Can not format this event: {}. Supported: {}".format(event.evt_type, self.FORWARDED_EVENTS_TYPES))


        if event.evt_type == "commits.fetched":
            payload = {
                'environment_id': event.payload['environment_id']
            }
            evt = websocket.WebSocketEvent("commits.fetched", payload)
            return evt

        if event.evt_type == "deployment.step.release":
            server_schema = m.Server.__marshmallow__()
            payload = {
                'environment_id': event.payload['deployment'].environment.id,
                "deployment": self._deploy_schema.dump(event.payload['deployment']).data,
                "release_info": dict(event.payload['release_info']),
                "server": server_schema.dump(event.payload['server']).data
            }
            payload['release_info']['release_date'] = payload['release_info']['release_date'].isoformat()
            evt = websocket.WebSocketEvent("deployment.step.release", payload)
            return evt

        if event.evt_type == "deployment.queued":
            payload = {
                'environment_id': event.payload['environment_id'],
                'deployment': {
                    'id': event.payload['deploy_id'],
                    'user_id': event.payload['user_id'],
                    'status': 'QUEUED',
                    'environment_id': event.payload['environment_id'],
                    'environment_name': event.payload['environment_name'],
                    'repository_name': event.payload['repository_name'],
                    'branch': event.payload['branch'],
                    'commit': event.payload['commit']
                }
            }
        else:
            deployment = event.payload["deployment"]
            payload = {
                "environment_id": deployment.environment.id,
                "deployment": self._deploy_schema.dump(deployment).data
            }
        return websocket.WebSocketEvent("deployment.deployment_status", payload)

    def dispatch(self, event):
        if event.evt_type not in self.FORWARDED_EVENTS_TYPES:
            return

        evt = self.__class__.event_to_websocket(event)
        self.publish(evt)

    def publish(self, websocket_event):
        self.ws_worker.publish(websocket_event)

    def _handle_log_request(self, message, ws, server):
        payload = message['payload']
        if message['type'] == 'subscribe':
            ws.forward_events_matching(payload['environment_id'])
            with database.session_scope() as session:
                deploys = session.query(m.DeploymentView).\
                    filter(m.DeploymentView.status != 'FAILED').\
                    filter(m.DeploymentView.status != 'COMPLETE').\
                    filter(m.DeploymentView.environment_id == payload['environment_id']).\
                    all()
                for d in deploys:
                    event = websocket.WebSocketEvent('deployment.deployment_status', {
                        'environment_id': payload['environment_id'],
                        'deployment': self._deploy_schema.dump(d).data
                    })
                    ws.notify(event)
        elif message['type'] == 'unsubscribe':
            ws.stop_forwarding_events_matching(payload['environment_id'])

    def _handle_ping(self, message, ws, server):
        assert message['type'] == "websocket.ping"
        event = websocket.WebSocketEvent('websocket.pong', {})
        ws.notify(event)
