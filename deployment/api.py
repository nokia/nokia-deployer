# Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).
# -*- coding: utf-8 -*-

import re
import json
from logging import getLogger
import datetime
import os.path
from itertools import repeat
from wsgiref.simple_server import make_server, WSGIServer, WSGIRequestHandler
from SocketServer import ThreadingMixIn

import beanstalkc
import bottle
from bottle import route, hook, request, abort, error, \
    post, delete, get, put, default_app, static_file
from bottle.ext import sqlalchemy as sabottle
from . import execution, worker, authorization,\
    gitutils, websocket, executils, database
from . import samodels as m, schemas
from .auth import issue_token, InvalidSession, NoMatchingUser, hash_token

from sqlalchemy import orm

logger = getLogger(__name__)

# FIXME: abstract away the "return json..." with a helper


def enforce(permission):
    if request.account is None or not request.account.has_permission(permission):
        abort(403)


@bottle.error(405)
def method_not_allowed(res):
    if request.method == 'OPTIONS':
        new_res = bottle.HTTPResponse()
        new_res.set_header('Access-Control-Allow-Origin', '*')
        new_res.set_header('Access-Control-Allow-Methods', 'GET, POST, DELETE, PUT')
        new_res.set_header('Access-Control-Allow-Headers', 'X-Session-Token, X-Impersonate-Username, Content-Type')
        return new_res
    res.headers['Allow'] += ', OPTIONS'
    return request.app.default_error_handler(res)


@error(500)
def handle_500_error(http_error):
    if http_error.exception is not None:
        logger.error(http_error.exception)
    if http_error.traceback is not None:
        logger.error(http_error.traceback)
    if http_error.body is not None and len(http_error.body) > 0:
        logger.error(http_error.body)
    return json.dumps(
        {
            'status': 1,
            'error': "The server encountered an internal error (see server logs for details)",
            "details": http_error.body
        }
    )


def use_default_user():
    with database.session_scope() as session:
        request.account = session.query(m.User).\
            filter(m.User.username == 'default').\
            options(orm.subqueryload(m.User.roles)).\
            one_or_none()
        if request.account is not None:
            _expunge_user(request.account, session)


def _expunge_user(user, session):
    for role in user.roles + user.default_roles:
        session.expunge(role)
    session.expunge(user)


@hook('before_request')
def check_auth():
    request.account = None
    # Allow preflight requests
    if request.method == 'OPTIONS':
        return

    # FIXME: this is legacy authentification, remove this
    token_protected_prefix = default_app().config.get("general", "token_protected_paths") or []
    if 'X-Auth-Token' in request.headers and \
            any(request.path.startswith(prefix) for prefix in token_protected_prefix):
        auth_token = request.headers['X-Auth-Token']

        expected_token = default_app().config.get("general", "auth_token")
        if auth_token != expected_token:
            logger.error("Invalid Token:[%s]" % (auth_token,))
            abort(401, "Invalid Token.")
        return

    # Get session token from request headers or cookies
    token = None
    if 'X-Session-Token' in request.headers:
        token = request.headers['X-Session-Token']

    if token is None:
        # Allow unprotected routes if no token is provided
        return use_default_user()

    # If a token is provided, check it
    with database.session_scope() as session:
        user = session.query(m.User).filter(m.User.session_token == token).one_or_none()
        if user is None:
            logger.info("Unauthorized access attempt with token: {}".format(token))
            abort(403)
        if user.token_issued_at + datetime.timedelta(minutes=30) < datetime.datetime.utcnow():
            logger.info("Token expired: {}".format(token))
            abort(403)

        request.account = user
        # Load roles, then remove them from the session so we can use them anywhere
        _expunge_user(request.account, session)


def requires_admin(decorated):
    def out(*args, **kwargs):
        enforce(authorization.SuperAdmin())
        return decorated(*args, **kwargs)
    return out


def requires_logged(decorated):
    def out(*args, **kwargs):
        enforce(authorization.Default())
        return decorated(*args, **kwargs)
    return out


# ### Authentification methods ###
# wssession: provide a session ID, to be validated against an external backend - for human users
# token: provide a token - for bots and services without a session id
# In both cases, the response is the same and will contain a session token along with info about
# when it will expire


@post('/api/auth/wssession')
def auth_session(db):
    if 'sessionid' not in request.json:
        abort(400)
    sessionid = request.json['sessionid']
    if sessionid is None:
        abort(400)
    # Check that this session is valid
    try:
        user = default_app().config["deployer.authentificator"].get_user_by_sessionid(sessionid, db)
    except InvalidSession:
        abort(400)
    except NoMatchingUser:
        abort(403)
    return issue_token(user, db)


@post('/api/auth/token')
def auth_token(db):
    if 'auth_token' not in request.json or request.json['auth_token'] is None:
        abort(400)
    username = request.json['username']
    token = request.json['auth_token']
    try:
        user = default_app().config["deployer.authentificator"].get_user_by_token(username, token, db)
    except NoMatchingUser:
        abort(403)
    return issue_token(user, db)


# FIXME: default repo should be configurable (git@git is Withings-specific)
# Notify from external provider (such as Github)
@route('/notify/<provider>', method='POST')
def notify(provider, db):
    logger.info("Received notification from provider '{}': '{}' ".format(provider, request.json))

    repo = request.json['repository']
    if 'full_name' not in repo:
        pattern = 'git@([a-zA-Z0-9\.]+):([a-zA-Z0-9\.\/]+)\.git'  # git@gitlab.corp.withings.com:platform/wcs.git
        matches = re.match(pattern, repo['git_ssh_url'])
        if matches:
            logger.info("notify match:[%s]" % str(json.dumps(matches.groups())))
            repo_name = matches.groups()[1]
        else:
            repo_name = repo['name']
    else:
        repo_name = repo['full_name']

    newrev = request.json['after']
    ref = request.json['ref']
    # ref looks like refs/heads/master
    branch = ref.split("/")[2]

    auto_deploy_account = db.query(m.User).filter(m.User.username == "auto").one()
    beanstalk = default_app().config['deployer.beanstalk']
    notifier = default_app().config['deployer.notifier']
    deployers_urls = [s.strip() for s in default_app().config['cluster.deployers_urls'].split(',')]
    worker.handle_autodeploy_notification(
        repo_name, branch, newrev, beanstalk, notifier, auto_deploy_account, deployers_urls
    )

    return json.dumps({"status": 0})


@post('/api/notification/updatedrepo')
def notification_updatedrepo(db):
    repository_name = request.json['repository']
    branch = request.json['branch']
    commit = None
    if 'commit' in request.json:
        commit = request.json['commit']

    deployers_urls = [s.strip() for s in default_app().config['cluster.deployers_urls'].split(',')]
    auto_deploy_account = db.query(m.User).filter(m.User.username == "auto").one()
    beanstalk = default_app().config['deployer.beanstalk']
    notifier = default_app().config['deployer.notifier']
    worker.handle_autodeploy_notification(repository_name, branch, commit, beanstalk, notifier, auto_deploy_account, deployers_urls)
    return json.dumps({'status': 0, 'message': 'notification processed'})


@post('/api/notification/websocketevent')
@requires_logged
def notification_websocketevent(db):
    enforce(authorization.Deployer())
    event = websocket.WebSocketEvent.from_dict(request.json['event'])
    websocket_notifier = default_app().config["deployer.websocket_notifier"]
    websocket_notifier.publish(event)


@get('/api/repositories/<repository_id:int>/diff')
@requires_logged
def repositories_diff(repository_id, db):
    from_commit = request.query['from']
    to_commit = request.query['to']
    envs = db.query(m.Environment).join(m.Repository).filter(m.Repository.id == repository_id).all()
    if len(envs) == 0:
        abort(404)
    if not any(request.account.has_permission(authorization.DeployBusinessHours(env.id)) for env in envs):
        abort(403)
    env = envs[0]
    path = os.path.join(default_app().config['general.local_repo_path'], env.local_repo_directory_name)
    diff = gitutils.LocalRepository(path).diff(from_commit, to_commit)
    return json.dumps({'diff': {'from': from_commit, 'to': to_commit, 'diff': diff}})


@get('/api/environments/<environment_id:int>/servers')
@requires_logged
def environments_servers(environment_id, db):
    enforce(authorization.Read(environment_id))
    env = db.query(m.Environment).get(environment_id)
    if env is None:
        abort(404)
    hosts = [executils.Host.from_server(s, env.remote_user) for s in env.servers]

    releases = execution.concurrent_get_release_status(
        zip(hosts, repeat(env.target_path))
    )

    servers_status = {}
    for server, release in zip(env.servers, releases):
        servers_status[server.id] = {}
        servers_status[server.id]['release_status'] = release.to_dict(env.id, server.id)
        servers_status[server.id]['server'] = m.Server.__marshmallow__().dump(server).data

    return json.dumps({'servers_status': servers_status})


@post('/api/environments/<environment_id:int>/fetch')
@requires_logged
def environments_fetch(environment_id, db):
    env = db.query(m.Environment).get(environment_id)
    if env is None:
        abort(404)
    worker.AsyncFetchWorker.enqueue_job(env)
    return {'message': 'fetch job queued'}


@get('/api/environments/<environment_id:int>/commits')
@requires_logged
def get_commits_by_env(environment_id, db):
    enforce(authorization.Read(environment_id))
    env = db.query(m.Environment).get(environment_id)
    if env is None:
        abort(404)
    path = os.path.join(default_app().config['general.local_repo_path'], env.local_repo_directory_name)
    if not os.path.exists(path):
        return json.dumps({'commits': [], "info": "Git repository not cloned on the server"})
    commits = gitutils.LocalRepository(path).list_commits(env.deploy_branch, count=150)
    hexshas = [c.hexsha for c in commits]
    parent_environments = db.query(m.Environment).filter(m.Environment.repository_id == env.repository_id).\
        filter(m.Environment.env_order == env.env_order - 1).\
        filter(m.Environment.deploy_branch == env.deploy_branch).\
        all()
    if len(parent_environments) > 0:
        parent_ids = [p.id for p in parent_environments]
        deployable = [c[0] for c in db.query(m.DeploymentView.commit).
                      filter(m.DeploymentView.commit.in_(hexshas)).
                      filter(m.DeploymentView.status == 'COMPLETE').
                      filter(m.DeploymentView.environment_id.in_(parent_ids)).
                      distinct().
                      all()]
        for c in commits:
            if c.hexsha not in deployable:
                c.deployable = False
    return json.dumps({'commits': [c.to_dict() for c in commits]})


@route('/api/status')
def status():
    health = default_app().config['health'].get_status()
    if health.degraded:
        # using a non 200 code makes monitoring easier, no need to parse the response body
        abort(500, "this deployer instance is not healthy: {}".format(health.reason))
    return json.dumps({'message': 'Deployer API is up and running'})


@route('/api/repositories/', method=['GET'])
@requires_logged
def repositories_list(db):
    q = db.query(m.Repository)
    if not request.account.has_permission(authorization.ReadAllEnvironments()):
        q = q.join(m.Repository.environments).\
            filter(m.Environment.id.in_(request.account.readable_environments()))
    repos = q.all()
    schema = m.Repository.__marshmallow__(many=True)
    schema.context = {'account': request.account}
    return json.dumps({'repositories': schema.dump(repos).data})


@get('/api/repositories/byname/<repo_name:re:.+>')
@requires_logged
def repository_get_by_name(repo_name, db):
    # TODO: remove copy-paste
    q = db.query(m.Repository).filter(m.Repository.name == repo_name)
    if not request.account.has_permission(authorization.ReadAllEnvironments()):
        q = q.join(m.Repository.environments).\
            filter(m.Environment.id.in_(request.account.readable_environments()))
    repo = q.one_or_none()
    if repo is None:
        abort(404, "Repository not found")
    schema = m.Repository.__marshmallow__()
    schema.context = {'account': request.account}
    return json.dumps({'repository': schema.dump(repo).data})


@get('/api/repositories/<repository_id:int>')
@requires_logged
def repository_get_by_id(repository_id, db):
    # TODO: remove copy-paste
    q = db.query(m.Repository).filter(m.Repository.id == repository_id)
    if not request.account.has_permission(authorization.ReadAllEnvironments()):
        q = q.join(m.Repository.environments).\
            filter(m.Environment.id.in_(request.account.readable_environments()))
    repo = q.one_or_none()
    if repo is None:
        abort(404)
    schema = m.Repository.__marshmallow__()
    schema.context = {'account': request.account}
    return json.dumps({'repository': schema.dump(repo).data})


@route('/api/repositories/<repository_id:int>/environments/', method=['GET'])
@requires_logged
def repository_environments(repository_id, db):
    q = db.query(m.Environment).join(m.Repository).filter(m.Repository.id == repository_id)
    if not request.account.has_permission(authorization.ReadAllEnvironments()):
        q = q.filter(m.Environment.id.in_(request.account.readable_environments()))
    envs = q.all()
    schema = m.Environment.__marshmallow__(many=True)
    schema.context = {'account': request.account}
    return json.dumps({'environments': schema.dump(envs).data})


@route('/api/deployments/byrepo/<repository_name>', method=['GET'])
@requires_logged
def deployments_list(repository_name, db):
    repository_name = repository_name.replace("~", "/")
    q = db.query(m.DeploymentView).\
        filter(m.DeploymentView.repository_name == repository_name).\
        order_by(m.DeploymentView.date_start_deploy.desc())
    if not request.account.has_permission(authorization.ReadAllEnvironments()):
        q = q.join(m.Environment).\
            filter(m.Environment.id.in_(request.account.readable_environments()))
    deploys = q.limit(50).all()
    for deploy in deploys:
        if deploy.user is not None:
            deploy.username = deploy.user.username
    schema = m.DeploymentView.__marshmallow__(many=True)
    return json.dumps({'deployments': schema.dump(deploys).data})


@route('/api/deployments/<deploy_id:int>')
@requires_logged
def deployment_get(deploy_id, db):
    deploy = db.query(m.DeploymentView).get(deploy_id)
    if deploy is None:
        abort(404)
    if not request.account.has_permission(authorization.ReadAllEnvironments):
        if deploy.environment_id not in request.account.readable_environments():
            abort(403)
    schema = m.DeploymentView.__marshmallow__()
    return json.dumps({'deployment': schema.dump(deploy).data})


@get('/api/servers/')
@requires_admin
def servers_get(db):
    servers = db.query(m.Server).all()
    schema = m.Server.__marshmallow__(many=True)
    return json.dumps({'servers': schema.dump(servers).data})


# TODO: requires_logged could be enough,
# but then we sould need to filter according to
# what envs the user can actually see
@get('/api/servers/<server_id:int>/releases')
@requires_admin
def servers_get_environments(server_id, db):
    server = db.query(m.Server).get(server_id)
    if server is None:
        abort(404)
    environments = db.query(m.Environment).\
        join(m.Environment.clusters).\
        join(m.Cluster.servers).\
        join(m.ClusterServerAssociation.server_def).\
        filter(m.Server.id == server_id).\
        all()
    to_inspect = []
    # TODO: this will result in a LOT of SQL queries, fix that
    for env in environments:
        to_inspect += zip(
            [executils.Host.from_server(s, env.remote_user) for s in env.servers],
            repeat(env.target_path)
        )
    releases = execution.concurrent_get_release_status(
        to_inspect,
        timeout=5
    )
    # Build response
    out = {"releases": []}
    env_schema = m.Environment.__marshmallow__()
    server_schema = m.Server.__marshmallow__()
    for env in environments:
        data = {
            'environment': env_schema.dump(env).data,
            'servers': []
        }
        for server in env.servers:
            data['servers'].append({
                'server': server_schema.dump(server).data,
                'release_status': releases.pop(0).to_dict(env.id, server.id)
            })
        out['releases'].append(data)
    return json.dumps(out)


@post('/api/servers/')
@requires_admin
def servers_post(db):
    schema = m.Server.__marshmallow__()
    server = schema.load(request.json, session=db).data
    db.add(server)
    db.commit()
    return json.dumps({'server': schema.dump(server).data})


@delete('/api/servers/<server_id:int>')
@requires_admin
def servers_delete(server_id, db):
    server = db.query(m.Server).get(server_id)
    if server is None:
        abort(404)
    # This refers to ClusterServerAssociation, not the actual cluster
    for asso in server.clusters:
        db.delete(asso)
    db.delete(server)
    schema = m.Server.__marshmallow__()
    return json.dumps({'server': schema.dump(server).data})


@put('/api/servers/<server_id:int>')
@requires_admin
def server_put(server_id, db):
    existing = db.query(m.Server).filter(m.Server.id == server_id).one_or_none()
    if existing is None:
        abort(404)
    schema = m.Server.__marshmallow__()
    server = schema.load(request.json, instance=existing, session=db).data
    return json.dumps({'server': schema.dump(server).data})


# Get account data for the current user
@get('/api/account')
@requires_logged
def account_get(db):
    return json.dumps({'user': m.User.__marshmallow__().dump(request.account).data})


# TODO: protect this route?
@get('/api/clusters')
@requires_logged
def clusters_get(db):
    clusters = db.query(m.Cluster).all()
    schema = m.Cluster.__marshmallow__(many=True)
    return json.dumps({'clusters': schema.dump(clusters).data})


@post('/api/clusters')
@requires_admin
def clusters_post(db):
    schema = schemas.ClusterPostSchema()
    cluster_def = schema.load(request.json).data
    if cluster_def['haproxy_host'] == '':
        cluster_def['haproxy_host'] = None
    cluster = m.Cluster(name=cluster_def['name'], haproxy_host=cluster_def['haproxy_host'])
    servers = []
    for server in cluster_def['servers']:
        s = db.query(m.Server).get(server['server_id'])
        if s is None:
            abort(400)
        if server['haproxy_key'] == '':
            server['haproxy_key'] = None
        servers.append(m.ClusterServerAssociation(
            haproxy_key=server['haproxy_key'],
            server_def=s,
            cluster_def=cluster)
                       )
    cluster.servers = servers
    db.add(cluster)
    db.commit()
    return json.dumps({'cluster': m.Cluster.__marshmallow__().dump(cluster).data})


@delete('/api/clusters/<cluster_id:int>')
@requires_admin
def clusters_delete(cluster_id, db):
    cluster = db.query(m.Cluster).get(cluster_id)
    if cluster is None:
        abort(404)
    for server_asso in cluster.servers:
        db.delete(server_asso)
    db.delete(cluster)
    return json.dumps({'cluster': m.Cluster.__marshmallow__().dump(cluster).data})


@put('/api/clusters/<cluster_id:int>')
@requires_admin
def cluster_put(cluster_id, db):
    cluster = db.query(m.Cluster).get(cluster_id)
    if cluster is None:
        abort(404)
    cluster_def = schemas.ClusterPostSchema().load(request.json).data
    cluster.name = cluster_def['name']
    cluster.haproxy_host = cluster_def['haproxy_host']
    if cluster.haproxy_host == '':
        cluster.haproxy_host = None
    for server_asso in cluster.servers:
        db.delete(server_asso)
    cluster.servers = []
    for server_def in cluster_def['servers']:
        server = db.query(m.Server).get(server_def["server_id"])
        if server is None:
            abort(404, "The server {} does not exist.".format(server_def['server_id']))
        if server_def['haproxy_key'] == '':
            server_def['haproxy_key'] = None
        cluster.servers.append(m.ClusterServerAssociation(
            haproxy_key=server_def['haproxy_key'],
            server_def=server,
            cluster_def=cluster
        ))
    db.commit()
    return json.dumps({'cluster': m.Cluster.__marshmallow__().dump(cluster).data})


@put('/api/repositories/<repository_id:int>')
@requires_admin
def repository_put(repository_id, db):
    schema = m.Repository.__marshmallow__()
    schema.context = {'account': request.account}
    existing = db.query(m.Repository).get(repository_id)
    if existing is None:
        abort(404)
    repository = schema.load(request.json, instance=existing, session=db).data
    return json.dumps({'repository': schema.dump(repository).data})


@post('/api/repositories')
@requires_admin
def repository_post(db):
    schema = m.Repository.__marshmallow__()
    schema.context = {'account': request.account}
    repository = schema.load(request.json, session=db).data
    db.add(repository)
    db.commit()
    return json.dumps({'repository': schema.dump(repository).data})


@post('/api/repositories/<repository_id:int>/environments')
@requires_admin
def repository_environments_post(repository_id, db):
    repository = db.query(m.Repository).get(repository_id)
    if repository is None:
        abort(404)
    schema = schemas.PostEnvironmentSchema()
    environment = schema.load(request.json, session=db).data
    environment.repository_id = repository_id
    db.commit()
    return json.dumps({'environment': m.Environment.__marshmallow__().dump(environment).data})


@delete('/api/repositories/<repository_id:int>')
@requires_admin
def repository_delete(repository_id, db):
    repository = db.query(m.Repository).get(repository_id)
    if repository is None:
        abort(404)
    db.delete(repository)
    db.commit()
    return json.dumps({'repository': m.Repository.__marshmallow__().dump(repository).data})


@get('/api/environments')
@requires_logged
def environments_list(db):
    if request.account.has_permission(authorization.ReadAllEnvironments()):
        envs = db.query(m.Environment).all()
    else:
        envs = db.query(m.Environment).\
            filter(m.Environment.id.in_(request.account.readable_environments())).\
            all()
    schema = m.Environment.__marshmallow__(many=True)
    schema.context = {'account': request.account}
    return json.dumps({'environments': schema.dump(envs).data})


@put('/api/environments/<environment_id:int>')
@requires_admin
def environment_put(environment_id, db):
    existing = db.query(m.Environment).get(environment_id)
    if existing is None:
        abort(404)
    schema = schemas.PostEnvironmentSchema()
    env = schema.load(request.json, instance=existing, session=db).data
    return json.dumps({'environment': m.Environment.__marshmallow__().dump(env).data})


@get('/api/environments/<environment_id:int>')
@requires_logged
def environment_get(environment_id, db):
    enforce(authorization.Read(environment_id))
    environment = db.query(m.Environment).get(environment_id)
    if environment is None:
        abort(404)
    schema = m.Environment.__marshmallow__()
    schema.context = {'account': request.account}
    return json.dumps({'environment': schema.dump(environment).data})


@delete('/api/environments/<environment_id:int>')
@requires_admin
def environment_delete(environment_id, db):
    environment = db.query(m.Environment).get(environment_id)
    if environment is None:
        abort(404)
    db.delete(environment)
    schema = m.Environment.__marshmallow__()
    schema.context = {'account': request.account}
    return json.dumps({'environment': schema.dump(environment).data})


@get('/api/deployments/recent')
@requires_logged
def deployments_recent(db):
    q = db.query(m.DeploymentView).options(orm.joinedload('log_entries'))
    if not request.account.has_permission(authorization.ReadAllEnvironments()):
        q = q.filter(m.DeploymentView.environment_id.in_(request.account.readable_environments()))
    deploys = q.order_by(m.DeploymentView.date_start_deploy.desc()).\
        limit(70).\
        all()
    for deploy in deploys:
        if deploy.user is not None:
            deploy.username = deploy.user.username
    return json.dumps({'deployments': m.DeploymentView.__marshmallow__(many=True).dump(deploys).data})


@post('/api/environments/<environment_id:int>/deployments')
@requires_logged
def environments_start_deployment(environment_id, db):
    # DeployBusinessHours is the minimal required permission to perform a deployment
    # Additional permissions check will be done during the deployment proper
    if 'X-Impersonate-Username' in request.headers:
        enforce(authorization.Impersonate())
        impersonated = db.query(m.User).\
            filter(m.User.username == request.headers['X-Impersonate-Username']).\
            one_or_none()
        if impersonated is None:
            abort(403)
        if not impersonated.has_permission(authorization.DeployBusinessHours(environment_id)):
            abort(403)
        user_id = impersonated.id
        logger.info("User {} impersonated user {} in order to deploy in the environment {}".format(request.account.username, impersonated.username, environment_id))
        # TODO: add better traceability (in DB)
    else:
        enforce(authorization.DeployBusinessHours(environment_id))
        user_id = request.account.id

    # If we are impersonating an user, check this user permission instead
    environment = db.query(m.Environment).get(environment_id)
    if environment is None:
        abort(404)
    # Poor man validation (proper API validation is a TODO)
    if request.json['branch'] is None or request.json['commit'] is None or len(request.json['commit']) < 3 or len(request.json['branch']) == 0:
        abort(400)
    target = request.json['target']
    server_id = None
    if 'server' in target:
        server_id = target['server']
    cluster_id = None
    if 'cluster' in target:
        cluster_id = target['cluster']
    deploy_id = worker.create_deployment_job(
        default_app().config['deployer.beanstalk'],
        default_app().config['deployer.notifier'],
        environment.repository.name,
        environment.name,
        environment.id,
        cluster_id,
        server_id,
        request.json['branch'],
        request.json['commit'],
        user_id,
    )
    return json.dumps({"deployment_id": deploy_id, "status": "QUEUED"})


@get('/api/users')
@requires_admin
def users_list(db):
    users = db.query(m.User).all()
    return json.dumps({'users': m.User.__marshmallow__(many=True).dump(users).data})


# FIXME: use a marshmallow schema for serialization
@post('/api/users')
@requires_admin
def users_post(db):
    roles = []
    for role_id in request.json['roles']:
        role = db.query(m.Role).get(role_id)
        if role is None:
            abort(404)
        roles.append(role)
    auth_token = None
    if 'auth_token' in request.json:
        auth_token = hash_token(request.json['auth_token'], default_app().config['deployer.bcrypt_log_rounds'])
    user = m.User(
        username=request.json['username'],
        email=request.json['email'],
        accountid=request.json['accountid'],
        roles=roles,
        auth_token=auth_token)
    db.add(user)
    db.commit()
    return json.dumps({'user': m.User.__marshmallow__().dump(user).data})


@get('/api/users/<user_id:int>')
@requires_admin
def users_get(user_id, db):
    user = db.query(m.User).get(user_id)
    if user is None:
        abort(404)
    return json.dumps({'user': m.User.__marshmallow__().dump(user).data})


# FIXME: use a marshmallow schema for serialization
@put('/api/users/<user_id:int>')
@requires_admin
def users_put(user_id, db):
    user = db.query(m.User).get(user_id)
    if user is None:
        abort(404)
    roles = []
    for role_id in request.json['roles']:
        role = db.query(m.Role).get(role_id)
        if role is None:
            abort(404)
        roles.append(role)
    user.roles = roles
    user.username = request.json['username']
    user.email = request.json['email']
    user.accountid = request.json['accountid']
    if 'auth_token' in request.json:
        if request.json['auth_token'] is None:
            user.auth_token = None
        else:
            user.auth_token = hash_token(request.json['auth_token'], default_app().config['deployer.bcrypt_log_rounds'])
    db.commit()
    return json.dumps({'user': m.User.__marshmallow__().dump(user).data})


@delete('/api/users/<user_id:int>')
@requires_admin
def users_delete(user_id, db):
    user = db.query(m.User).get(user_id)
    if user is None:
        abort(404)
    db.delete(user)
    return json.dumps({'user': m.User.__marshmallow__().dump(user).data})


@get('/api/roles')
@requires_admin
def roles_list(db):
    roles = db.query(m.Role).all()
    return json.dumps({'roles': m.Role.__marshmallow__(many=True).dump(roles).data})


@get('/api/roles/<role_id:int>')
@requires_admin
def roles_get(role_id, db):
    role = db.query(m.Role).get(role_id)
    if role is None:
        abort(404)
    return json.dumps({'role': m.Role.__marshmallow__().dump(role).data})


@post('/api/roles')
@requires_admin
def roles_post(db):
    schema = m.Role.__marshmallow__()
    role = schema.load(request.json, session=db).data
    db.add(role)
    db.commit()
    return json.dumps({'role': schema.dump(role).data})


@put('/api/roles/<role_id:int>')
@requires_admin
def roles_put(role_id, db):
    schema = m.Role.__marshmallow__()
    existing = db.query(m.Role).get(role_id)
    if existing is None:
        abort(404)
    role = schema.load(request.json, instance=existing, session=db).data
    db.commit()
    return json.dumps({'role': schema.dump(role).data})


@delete('/api/roles/<role_id:int>')
@requires_admin
def roles_delete(role_id, db):
    role = db.query(m.Role).get(role_id)
    if role is None:
        abort(404)
    db.delete(role)
    return json.dumps({'role': m.Role.__marshmallow__().dump(role).data})


@get('/static/<path:path>')
def static(path, db):
    static_root = default_app().config["general.web_path"]
    return static_file(path, static_root)


@get('/favicon.ico')
def favicon(db):
    static_root = os.path.abspath(default_app().config["general.web_path"])
    return static_file('favicon.ico', static_root)


@get('/')
def index(db):
    static_root = os.path.abspath(default_app().config["general.web_path"])
    html_root = os.path.join(static_root, 'html')
    return static_file('index.html', html_root)


@get('<path:re:^(?!.*api).*>')
def catch_all(path, db):
    static_root = os.path.abspath(default_app().config["general.web_path"])
    html_root = os.path.join(static_root, 'html')
    return static_file('index.html', html_root)


class ThreadingWSGIServer(ThreadingMixIn, WSGIServer):
    pass


class LoggingWSGIRequestHandler(WSGIRequestHandler):

    def log_message(self, format, *args):
        code = args[1]
        # Logging HTTP 200 responses is super verbose
        if code == '200':
            return
        # But any non 200 reponse is suspicious and should be logger
        logger.info(
            "%s %s\n" % (
                self.client_address[0], format % args
            )
        )

# TODO: do not spawn the API ourselves ; instead, create an application.wsgi file defining
# the WSGI app and let Apache or some other webserver serve it
# TODO: or at least, use a better webserver than the standard WSGIServer
class ApiWorker(object):

    # TODO: use our own config everywhere, do not rely on Bottle for that
    # (eg pass only the config object)
    def __init__(self, config_path, config, notifier, websocket_notifier, authentificator, health):
        app = bottle.app()
        app.config.load_config(config_path)
        engine = database.engine()
        plugin = sabottle.Plugin(
            engine,
            None,
            keyword='db',
            use_kwargs=True,
            create=False,
        )
        app.install(plugin)
        self._check_for_index_html(app)
        conn = beanstalkc.Connection(
            host=config.get("general", "beanstalk_host"),
            port=11300
        )
        conn.use('deployer-deployments')
        app.config["deployer.engine"] = engine
        app.config["deployer.beanstalk"] = conn
        app.config["deployer.notifier"] = notifier
        app.config["deployer.websocket_notifier"] = websocket_notifier
        app.config["deployer.bcrypt_log_rounds"] = 12
        app.config["deployer.authentificator"] = authentificator
        app.config["health"] = health
        self.httpd = make_server("0.0.0.0", config.getint('general', 'api_port'), app,
                                 server_class=ThreadingWSGIServer,
                                 handler_class=LoggingWSGIRequestHandler)

    def _check_for_index_html(self, app):
        index_path = os.path.abspath(os.path.join(app.config['general.web_path'], "html", "index.html"))
        if not os.path.exists(index_path):
            raise ValueError("Could not find the index.html file at {}, check your configuration."
                             .format(index_path))

    def start(self):
        self.httpd.serve_forever()

    def stop(self):
        self.httpd.shutdown()

    @property
    def name(self):
        return 'api'
