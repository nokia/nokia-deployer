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
# In the context of the deployer, we need only two locks:
# * if two fetches are done concurrently, one of them may return an error when trying to update a ref (.git/refs/remotes/<origin>/<branch>). Plus we would
#   be downloading twice the missing objects anyway. Solution: per-repo "fetch lock". If it is already acquired, just skip the fetch.
# * when a deployment is in progress, we checkout the commit to deploy. The working directory must not be modified during this time, so we use another lock
#   type: "write lock". This lock is not mutually exclusive with a "fetch lock".

@contextlib.contextmanager
def lock_repository_fetch(repo_path, block=True):
    mkdir_p(LOCKS_FOLDER)
    filename = os.path.join(LOCKS_FOLDER,
                            "{}_fetch".format(_path_to_filename(repo_path)))
    with FileLock(filename, block):
        repo = _CanFetchLocalRepository(repo_path)
        try:
            yield repo
        finally:
            repo.invalidate()


@contextlib.contextmanager
def lock_repository_write(repo_path):
    mkdir_p(LOCKS_FOLDER)
    filename = os.path.join(LOCKS_FOLDER,
                            "{}_write".format(_path_to_filename(repo_path)))
    with FileLock(filename):
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


def clone(remote_url, local_path, raise_for_error=False):
    """Returns True is the clone was actually done, False otherwise"""
    try:
        git.Repo.clone_from(remote_url, local_path)
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

    # Converts a coommit object from GitPython to a simpler structure (see gitutils.Commit),
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


def release_file_contents(branch, commit, date, destination_path):
    return "\n".join([branch, commit, date.isoformat(), destination_path])


class InvalidReleaseFile(Exception):
    pass


class Release(object):

    def __init__(self, branch, commit, deployment_date):
        self.branch = branch
        self.deployment_date = deployment_date
        self.commit = commit

    def to_dict(self):
        return {
            'branch': self.branch,
            'deployment_date': self.deployment_date,
            'commit': self.commit
        }


def parse_release_file_contents(contents):
    outs = contents.strip().split("\n")
    if len(outs) <= 2:
        raise InvalidReleaseFile()
    return Release(branch=outs[0], commit=outs[1], deployment_date=outs[2])
