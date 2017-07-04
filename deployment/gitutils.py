# Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).
import contextlib
import os
import re
import string
import errno
import datetime

from deployment.filelock import FileLock

import git


def mkdir_p(path):
    try:
        os.makedirs(path)
    except OSError as exc:  # Python >2.5
        if exc.errno == errno.EEXIST and os.path.isdir(path):
            pass
        else:
            raise


LOCKS_FOLDER = '/tmp/deployerlocks'


def _path_to_filename(path):
    VALID_CHARS = "-_()%s%s" % (string.ascii_letters, string.digits)
    return "".join([c if c in VALID_CHARS else "_" for c in path])


#### Controlling concurrent access to Git repositories
# Git needs minimal locking, since most of its internal structures are immutable. Git is mostly "append-only", except when it performs a repack.
# However, as we are not using bare repos, we need to be careful with operations that affects the working directory.
#
# In the context of the deployer, we need only two locks:
# * if two fetches are done concurrently, one of them may return an error when trying to update a ref (.git/refs/remotes/<origin>/<branch>). Plus we would
#   be downloading twice the missing objects anyway. Solution: per-repo "fetch lock". If it is already acquired, just skip the fetch.
# * when a deployment is in progress, we checkout the commit to deploy. The working directory must not be modified during this time, so we use another lock type: "write lock".
#   This lock is not mutually exclusive with a "fetch lock".
#
# When a clone is in progress, we need to acquire both locks, because we're not certain of the state of the directory.

@contextlib.contextmanager
def acquire_repo_lock(lock_type, repo_path, block=True):
    lock_file_name = {
        'write': "{}_write",
        'fetch': "{}_fetch"
    }
    if lock_type not in lock_file_name:
        raise ValueError("Invalid lock type: {} (expected one of {})".format(lock_type, lock_file_name.keys()))
    mkdir_p(LOCKS_FOLDER)
    filename = os.path.join(LOCKS_FOLDER,
                            lock_file_name[lock_type].format(_path_to_filename(repo_path)))
    with FileLock(filename, block):
        yield

@contextlib.contextmanager
def lock_repository_fetch(repo_path, block=True):
    with acquire_repo_lock("fetch", repo_path, block):
        repo = _CanFetchLocalRepository(repo_path)
        try:
            yield repo
        finally:
            repo.invalidate()


@contextlib.contextmanager
def lock_repository_write(repo_path):
    with acquire_repo_lock("write", repo_path):
        repo = _WritableLocalRepository(repo_path)
        try:
            yield repo
        finally:
            repo.invalidate()


def build_repo_url(repo_name, git_server):
    if re.match("ssh:\/\/.*@.*:\d+", git_server):
        if not git_server.endswith("/"):
            git_server += '/'
        git_server_url = "%s%s" % (git_server, repo_name)
    else:
        git_server_url = "git@%s:%s" % (git_server, repo_name)
    return git_server_url


@contextlib.contextmanager
def lock_repository_clone(remote_url, local_path):
    with acquire_repo_lock("fetch", local_path), acquire_repo_lock("write", local_path):
        yield _RepositoryClonator(remote_url, local_path)


class _RepositoryClonator(object):

    def __init__(self, remote_url, local_path):
        self.remote_url = remote_url
        self.local_path = local_path

    def clone(self, raise_for_error=True):
        try:
            git.Repo.clone_from(self.remote_url, self.local_path)
            return True
        except git.GitCommandError as e:
            if e.status == 128 and not raise_for_error:
                return False
            raise


# Safe operations only, can be used without acquiring a lock first.
# Specialized subclasses with more operations defined are built by using one of the lock functions.
class LocalRepository(object):

    def __init__(self, path):
        self.path = path  # Path to the folder on disk containing the repo
        self._repo = git.Repo(self.path)
        self._invalidated = False

    def invalidate(self):
        self._invalidated = True

    def _abort_if_invalidated(self):
        if self._invalidated:
            raise ValueError('You can no longer perform this operation with this object.')

    # Converts a commit object from GitPython to a simpler structure (see gitutils.Commit),
    # so we don't expose the GitPython library to the rest of the code
    def _format_commit(self, entry):
        try:
            msg = entry.message
        except Exception:
            msg = ""
        try:
            committer = entry.committer.name
        except Exception:
            committer = entry.author.email
        return Commit(msg, committer, entry.hexsha, datetime.datetime.utcfromtimestamp(entry.authored_date - entry.author_tz_offset))

    def list_commits(self, branch, count=20):
        if not branch.startswith("origin/"):
            branch = "origin/" + branch
        commits = self._repo.iter_commits(branch, max_count=count)
        out = [self._format_commit(commit) for commit in commits]
        return out

    def get_commit(self, commit):
        return self._format_commit(self._repo.commit(commit))

    # Returns a string
    def diff(self, commit_src, commit_dest):
        return self._repo.git.diff(commit_src, commit_dest)

    def look_for_file(self, commit_src, commit_dest, filename):
        """Returns a list of Commits reachable from commit_dest but not from commit_src
        whose tree contains the given filename.
        """
        out = []
        for commit in self._repo.iter_commits("{}..{}".format(commit_src, commit_dest)):
            if filename in commit.tree:
                out.append(self._format_commit(commit))
        return out


class _CanFetchLocalRepository(LocalRepository):

    def __init__(self, *args, **kwargs):
        super(_CanFetchLocalRepository, self).__init__(*args, **kwargs)

    def fetch(self):
        self._abort_if_invalidated()
        self._repo.remotes.origin.fetch()


class _WritableLocalRepository(LocalRepository):

    def __init__(self, *args, **kwargs):
        super(_WritableLocalRepository, self).__init__(*args, **kwargs)

    def switch_to(self, commit):
        """Make sure the specified commit is checked out."""
        self._abort_if_invalidated()
        # Use twice the "-f" option to also delete repositories
        self._repo.git.clean(d=True, force=True, x=True, f=True)
        self._repo.head.reference = self._repo.commit(commit)
        self._repo.head.reset(index=True, working_tree=True)


class Commit(object):

    def __init__(self, message, committer, hexsha, authored_date, deployable=True):
        self.message = message
        self.committer = committer
        self.hexsha = hexsha
        self.authored_date = authored_date
        # This attribute could be moved elsewhere, but for now let's not create
        # another class just to add one attribute
        self.deployable = deployable

    def to_dict(self):
        return {
            'message': self.message,
            'committer': self.committer,
            'hexsha': self.hexsha,
            'authored_date': self.authored_date.isoformat(),
            'deployable': self.deployable
        }



class InvalidReleaseFile(Exception):
    pass


class Release(object):

    DATE_FORMAT = "%Y-%m-%dT%H:%M:%S.%f"

    def __init__(self, branch, commit, deployment_date, destination_path, in_progress=False):
        self.branch = branch
        self.deployment_date = deployment_date
        self.commit = commit
        self.in_progress = in_progress
        self.destination_path = destination_path

    def to_dict(self):
        return {
            'branch': self.branch,
            'deployment_date': self.deployment_date.strftime(self.DATE_FORMAT),
            'commit': self.commit,
            'in_progress': self.in_progress
        }

    @classmethod
    def from_string(klass, contents):
        outs = contents.strip().split("\n")
        if len(outs) <= 3:
            raise InvalidReleaseFile()
        if len(outs) >= 5:
            in_progress = outs[4] == "deployment in progress"
        else:
            in_progress = False
        try:
            date = datetime.datetime.strptime(outs[2], klass.DATE_FORMAT)
        except ValueError as e:
            raise InvalidReleaseFile(str(e))
        return klass(branch=outs[0], commit=outs[1], deployment_date=date,
                     destination_path=outs[3], in_progress=in_progress)

    def to_string(self):
        out = "\n".join([self.branch, self.commit,
                         self.deployment_date.strftime(self.DATE_FORMAT),
                         self.destination_path])
        if self.in_progress:
            out += "\ndeployment in progress"
        return out
