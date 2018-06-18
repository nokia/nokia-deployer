# Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).
import string
import json
import datetime
import os
import enum
import textwrap

import sqlalchemy as sa
from sqlalchemy import orm
from sqlalchemy.ext.declarative import declarative_base

from . import authorization


Base = declarative_base()


users_roles = sa.Table('users_roles', Base.metadata,
                       sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id'), primary_key=True, nullable=False),
                       sa.Column('role_id', sa.Integer(), sa.ForeignKey('roles.id'), primary_key=True, nullable=False)
                       )


class Role(Base):
    __tablename__ = 'roles'

    id = sa.Column(sa.Integer(), nullable=False, primary_key=True, autoincrement=True)
    name = sa.Column(sa.String(50), nullable=False, unique=True)
    # stored as JSON. Simple and dirty.
    permissions = sa.Column(sa.String(1000), nullable=False)

    users = orm.relationship("User", secondary=users_roles, back_populates="roles")

    def permissions_parsed(self):
        # TODO: memoize that somewhat ?
        return authorization.permissions_from_dict(json.loads(self.permissions))

    def allow(self, permission):
        return any(p.implies(permission) for p in self.permissions_parsed())

    def readable_environments(self):
        out = set()
        for p in self.permissions_parsed():
            out.update(p.readable_environments())
        return out


class User(Base):
    __tablename__ = "users"

    id = sa.Column(sa.Integer(), nullable=False, primary_key=True, autoincrement=True)
    username = sa.Column(sa.String(255), nullable=False, unique=True)
    email = sa.Column(sa.String(255), nullable=False)
    session_token = sa.Column(sa.String(255))
    token_issued_at = sa.Column(sa.DateTime())
    auth_token = sa.Column(sa.String(255))
    accountid = sa.Column(sa.Integer(), nullable=False, default=0)

    roles = orm.relationship("Role", secondary=users_roles, back_populates="users")

    _default_roles_cache = None

    @property
    def default_roles(self):
        if self.username == 'default':
            return []
        if self._default_roles_cache is not None:
            return self._default_roles_cache
        self._default_roles_cache = orm.object_session(self).\
            query(Role).join(User, Role.users).\
            filter(User.username == 'default').\
            all()
        return self._default_roles_cache

    def is_superadmin(self):
        return self.has_permission(authorization.SuperAdmin())

    def has_permission(self, permission):
        return any(role.allow(permission) for role in self.roles + self.default_roles)

    def readable_environments(self):
        out = set()
        for role in self.roles + self.default_roles:
            out.update(role.readable_environments())
        return out


# For those not familiar with SQLAlchemy,
# see http://docs.sqlalchemy.org/en/latest/orm/basic_relationships.html#association-pattern
class ClusterServerAssociation(Base):
    __tablename__ = 'clusters_servers'

    server_id = sa.Column(sa.Integer(), sa.ForeignKey('servers.id'), primary_key=True, nullable=False)
    cluster_id = sa.Column(sa.Integer(), sa.ForeignKey('clusters.id'), primary_key=True, nullable=False)
    haproxy_key = sa.Column(sa.String())

    cluster_def = orm.relationship("Cluster", back_populates="servers")
    server_def = orm.relationship("Server", back_populates="clusters")


class Server(Base):
    __tablename__ = "servers"

    id = sa.Column(sa.Integer(), nullable=False, primary_key=True, autoincrement=True)
    name = sa.Column(sa.String(255), nullable=False, unique=True)
    port = sa.Column(sa.Integer(), nullable=False, default=22)
    activated = sa.Column(sa.Boolean(), nullable=False, default=True)
    inventory_key = sa.Column(sa.String(255), nullable=True, unique=True) #mySQL allows multiple NUll values with a UNIQUE constraint

    clusters = orm.relationship("ClusterServerAssociation", back_populates="server_def")


environments_clusters = sa.Table('environments_clusters', Base.metadata,
                                 sa.Column('environment_id', sa.Integer(), sa.ForeignKey('environments.id'), nullable=False, primary_key=True),
                                 sa.Column('cluster_id', sa.Integer(), sa.ForeignKey('clusters.id'), nullable=False, primary_key=True)
                                 )


class Cluster(Base):
    __tablename__ = "clusters"

    id = sa.Column(sa.Integer(), nullable=False, primary_key=True, autoincrement=True)
    name = sa.Column(sa.String(), nullable=False, unique=True)
    haproxy_host = sa.Column(sa.String())
    inventory_key = sa.Column(sa.String(255), nullable=True, unique=True) #mySQL allows multiple NUll values with a UNIQUE constraint

    servers = orm.relationship("ClusterServerAssociation", back_populates="cluster_def")
    environments = orm.relationship("Environment", secondary="environments_clusters", back_populates="clusters")

    @property
    def activated_servers(self):
        return [s.server_def for s in self.servers if s.server_def.activated]


class FakeClusterAssociation(object):

    def __init__(self, server, cluster):
        self.server_def = server
        self.cluster_def = cluster
        self.haproxy_key = None


class OneServerCluster(object):

    def __init__(self, name, server):
        self.name = name
        self.haproxy_host = None
        self.servers = [FakeClusterAssociation(server, self)]

    @property
    def activated_servers(self):
        return [s.server_def for s in self.servers if s.server_def.activated]



class Repository(Base):
    __tablename__ = "repositories"

    id = sa.Column(sa.Integer(), nullable=False, primary_key=True, autoincrement=True)
    name = sa.Column(sa.String(255), nullable=False, unique=True)
    # TODO: use an enum
    deploy_method = sa.Column(sa.String(255), nullable=False, default='inplace')
    git_server = sa.Column(sa.String(255), nullable=False)
    _notify_owners_mails = sa.Column("notify_owners_mails", sa.String(255), nullable=False, default='')

    environments = orm.relationship("Environment", back_populates="repository")

    @property
    def notify_owners_mails(self):
        if self._notify_owners_mails is None:
            return []
        return [s.strip() for s in self._notify_owners_mails.split(',')]

    @notify_owners_mails.setter
    def notify_owners_mails(self, mails):
        self._notify_owners_mails = ','.join(mails)


class Environment(Base):
    __tablename__ = "environments"
    _table_args__ = (sa.Index('unique_environment_repository', "repository_id", "name", unique=True), )

    id = sa.Column(sa.Integer(), nullable=False, primary_key=True, autoincrement=True)
    name = sa.Column(sa.String(255), nullable=False)
    target_path = sa.Column(sa.String(255), nullable=False)
    auto_deploy = sa.Column(sa.Boolean(), nullable=False, default=False)
    remote_user = sa.Column(sa.String(255), nullable=False, default='scaleweb')
    sync_options = sa.Column(sa.String(255), nullable=False, default='')
    env_order = sa.Column(sa.Integer(), nullable=False, default=0)
    deploy_branch = sa.Column(sa.String(255), nullable=False, default='')
    fail_deploy_on_failed_tests = sa.Column(sa.Boolean, nullable=False, default=True)

    repository_id = sa.Column(sa.Integer, sa.ForeignKey("repositories.id"), nullable=False)

    repository = orm.relationship("Repository", back_populates="environments")
    clusters = orm.relationship("Cluster", secondary="environments_clusters", back_populates="environments")
    deployments = orm.relationship("DeploymentView", back_populates="environment")

    @property
    def servers(self):
        return [server.server_def for cluster in self.clusters for server in cluster.servers]

    @property
    def local_repo_directory_name(self):
        valid_chars = "-_()%s%s" % (string.ascii_letters, string.digits)
        return "".join([c if c in valid_chars else "_" for c in "{}_{}".format(self.repository.name, self.name)])

    def release_path(self, branch, commit):
        """Return the path to the folder containing the code. It may then be symlinked to the 'production folder' (symlink deployment method) or be used as the production folder (inplace deployment method).

        In other words, this is where the code to be deployed is copied on the remote server.
        """
        if self.repository.deploy_method == 'inplace':
            return self.target_path
        else:
            short_commit = commit[0:8]
            release_date = datetime.datetime.utcnow().strftime("%Y%m%d")
            releases_folder = "{}_releases".format(self.repository.name)
            return os.path.join(
                self.remote_repo_path(),
                "{}/{}_{}_{}".format(releases_folder, release_date, branch, short_commit)
            )

    def remote_repo_path(self):
        return os.path.dirname(os.path.normpath(self.target_path))

    def production_folder(self):
        return os.path.basename(os.path.normpath(self.target_path))


class Severity(enum.Enum):
    INFO = 1,
    WARN = 2,
    ERROR = 3

    def format(self):
        if self.name == 'INFO':
            return "info"
        elif self.name == 'WARN':
            return "warn"
        elif self.name == 'ERROR':
            return "error"
        assert False, "Code should not reach here"

    @staticmethod
    def from_string(string):
        if string == "info":
            return Severity.INFO
        elif string == "warn":
            return Severity.WARN
        elif string == "error":
            return Severity.ERROR
        raise ValueError('Unknown severity: {}'.format(string))


class LogEntry(Base):
    __tablename__ = "log_entries"

    def __init__(self, message, severity=Severity.INFO, date=None, deploy_id=None, id=None):
        self.message = message
        self.severity = severity.format()
        if date is None:
            date = datetime.datetime.utcnow()
        self.date = date
        self.deploy_id = deploy_id
        self.id = id

    id = sa.Column(sa.Integer(), nullable=False, primary_key=True, autoincrement=True)
    deploy_id = sa.Column(
        sa.Integer(),
        sa.ForeignKey('deploys.id', onupdate="CASCADE", ondelete="CASCADE"),
        nullable=False
    )
    date = sa.Column(sa.DateTime(), nullable=False, default=datetime.datetime.utcnow)
    severity = sa.Column(sa.Enum('info', 'warn', 'error'), nullable=False, default='info')
    message = sa.Column(sa.Text(), nullable=False)

    def format(self):
        prefix = ''
        if self.severity == "warn":
            prefix = 'warning: '
        elif self.severity == "error":
            prefix = 'ERROR: '
        return "[{}] {}{}".format(self.date, prefix, self.message)


class DeploymentView(Base):
    __tablename__ = "deploys"

    id = sa.Column(sa.Integer(), nullable=False, primary_key=True, autoincrement=True)
    # Not only foreign keys for tracability reasons - the env may be modified or deleted
    # TODO: use soft env delete instead
    repository_name = sa.Column(sa.String(255), nullable=False)
    environment_name = sa.Column(sa.String(255), nullable=False)
    # Nullable because the environment might be deleted
    environment_id = sa.Column(sa.ForeignKey('environments.id'))
    # A deployment mentions either a server, a specific cluster, or all clusters for a given environment
    # (in which case both cluster_id and server_id will be None)
    cluster_id = sa.Column(sa.ForeignKey('clusters.id'))
    server_id = sa.Column(sa.ForeignKey('servers.id'))
    branch = sa.Column(sa.String(255), nullable=False)
    commit = sa.Column(sa.String(255), nullable=False)
    user_id = sa.Column(sa.Integer(), sa.ForeignKey('users.id'))
    status = sa.Column(sa.Enum("QUEUED", "INIT", "PRE_DEPLOY", "DEPLOY", "POST_DEPLOY", "FAILED", "COMPLETE"), nullable=False)
    queued_date = sa.Column(sa.DateTime(), nullable=False)
    date_start_deploy = sa.Column(sa.DateTime())
    date_end_deploy = sa.Column(sa.DateTime())

    environment = orm.relationship("Environment", back_populates="deployments")
    cluster = orm.relationship("Cluster")
    server = orm.relationship("Server")
    log_entries = orm.relationship("LogEntry")
    user = orm.relationship("User")

    @property
    def target_servers(self):
        if self.cluster_id is None and self.server_id is None:
            # FIXME: handle self.environment is None
            # TODO: prevent self.environment from being None
            return self.environment.servers
        elif self.server_id is not None:
            assert self.cluster_id is None
            return [self.server]
        elif self.cluster_id is not None:
            assert self.server_id is None
            return [s.server_def for s in self.cluster.servers]
        assert False, "Code should not reach here"

    @property
    def target_clusters(self):
        if self.cluster_id is None and self.server_id is None:
            # FIXME: handle self.environment is None
            # TODO: prevent self.environment from being None
            return self.environment.clusters
        elif self.server_id is not None:
            assert self.cluster_id is None
            return [OneServerCluster(self.server.name, self.server)]
        elif self.cluster_id is not None:
            return [self.cluster]
        assert False, "Code should not reach here"

    @property
    def deactivated_servers(self):
        return set(s for s in self.target_servers if not s.activated)

    def end(self, status, date=None):
        if date is None:
            date = datetime.datetime.utcnow()
        self.date_end_deploy = date
        self.status = status.to_db_format()


class TestStatus(enum.Enum):
    SUCCESS = 1,
    FAILED = 2


class TestReport(object):

    def __init__(self, repository_name, environment_name, server, branch, commit, status, stdout, stderr):
        self.environment_name = environment_name
        self.server = server
        self.branch = branch
        self.commit = commit
        self.status = status
        self.stdout = stdout
        self.stderr = stderr
        self.repository_name = repository_name

    # output = (return_code, stdout, stderr)
    # see execution.exec_cmd
    @classmethod
    def from_command_output(klass, output, repository_name, environment_name, server, branch, commit):
        (return_code, stdout, stderr) = output
        if int(return_code) != 0:
            status = TestStatus.FAILED
        else:
            status = TestStatus.SUCCESS
        return klass(
            environment_name=environment_name,
            server=server,
            branch=branch,
            commit=commit,
            status=status,
            stdout=stdout,
            stderr=stderr,
            repository_name=repository_name
        )

    @property
    def failed(self):
        return self.status != TestStatus.SUCCESS

    @property
    def message(self):
        return "stdout:\n{}\nstderr:\n{}\n".format(self.stdout, self.stderr)

    def format(self):
        template = textwrap.dedent("""\
            Tests result: {was_successful}

            Repository {repository} - environment {environment} (branch {branch})
            Commit {commit}
            {server}

            stdout:
            {stdout}

            stderr:
            {stderr}
        """)
        was_successful = "failed :(" if self.failed else "success :)"
        server = "Server {}".format(self.server) if self.server else ''
        return template.format(repository=self.repository_name,
                               environment=self.environment_name,
                               branch=self.branch,
                               commit=self.commit,
                               server=server,
                               stdout=self.stdout,
                               stderr=self.stderr,
                               was_successful=was_successful
                               )


class DeploymentStatus(enum.Enum):
    QUEUED = 1
    INIT = 2
    PRE_DEPLOY = 3
    DEPLOY = 4
    POST_DEPLOY = 5
    COMPLETE = 6
    FAILED = 7

    def to_db_format(self):
        return self.name

    @property
    def finished(self):
        return self in [DeploymentStatus.COMPLETE, DeploymentStatus.FAILED]

    @property
    def in_progress(self):
        return not self.finished and self != DeploymentStatus.QUEUED

    @classmethod
    def from_string(klass, data):
        data = data.upper()
        matching = [m for m in klass if m.name == data]
        if len(matching) == 0:
            raise ValueError("{} is not a valid DeploymentStatus, expected one of {}".format(data, [m.name for m in klass]))
        return matching[0]
