# -*- encoding: utf8 -*
# Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).
import unittest
import tempfile
import shutil
import os

import git

from deployment import gitutils, filelock


class TestGitUtils(unittest.TestCase):

    def setUp(self):
        self.base_path = "/tmp/deployertests"
        gitutils.mkdir_p(self.base_path)
        self._create_bare_repo()

    def tearDown(self):
        shutil.rmtree(self.base_path)

    def _clone_repo(self):
        clone_path = tempfile.mkdtemp(dir=self.base_path, prefix="clone")
        gitutils.clone(self.base_repo_path, clone_path)
        return clone_path

    def _commit_and_push_to_base_repo(self):
        clone_path = self._clone_repo()
        repo = git.Repo(clone_path)
        new_file_path = os.path.join(repo.working_tree_dir, 'hi.txt')
        with open(new_file_path, 'w') as f:
            f.write("hello there")
            f.flush()
        repo.index.add([new_file_path])
        self.first_commit_sha = repo.index.commit("first commit").hexsha
        with open(new_file_path, 'w') as f:
            f.write("how do you do?")
            f.flush()
        repo.index.add([new_file_path])
        # Unicode + Python 2 = fun
        self.second_commit_sha = repo.index.commit(u"second commit œ").hexsha
        repo.remotes.origin.push('master')

    def _create_bare_repo(self):
        self.base_repo_path = tempfile.mkdtemp(dir=self.base_path, prefix="repo", suffix=".git")
        self.repo = git.Repo.init(path=self.base_repo_path, bare=True)

    def test_clone_repo(self):
        clone_path = tempfile.mkdtemp(dir=self.base_path)
        self.assertTrue(gitutils.clone(self.base_repo_path, clone_path))
        self.assertFalse(gitutils.clone(self.base_repo_path, clone_path))
        # Will raise InvalidGitRepositoryError if the clone did not succeed
        gitutils.LocalRepository(clone_path)

    def test_get_commit(self):
        self._commit_and_push_to_base_repo()
        clone_path = self._clone_repo()
        message = gitutils.LocalRepository(clone_path).get_commit(self.first_commit_sha).message
        self.assertEqual("first commit", message)

    def test_list_commits(self):
        self._commit_and_push_to_base_repo()
        clone_path = self._clone_repo()
        commits = gitutils.LocalRepository(clone_path).list_commits("master")
        self.assertEqual(2, len(commits))
        self.assertEqual(u"second commit œ", commits[0].message)

    def test_diff(self):
        self._commit_and_push_to_base_repo()
        clone_path = self._clone_repo()
        diff = gitutils.LocalRepository(clone_path).diff(self.first_commit_sha, self.second_commit_sha)
        self.assertIn("+how do you do", diff)
        self.assertIn("-hello there", diff)

    def test_fetch(self):
        clone_path = self._clone_repo()
        self._commit_and_push_to_base_repo()
        with gitutils.lock_repository_fetch(clone_path) as repo:
            repo.fetch()
        commits = gitutils.LocalRepository(clone_path).list_commits("origin/master")
        self.assertGreater(len(commits), 0)

    def test_fetch_lock(self):
        clone_path = self._clone_repo()
        with gitutils.lock_repository_fetch(clone_path):
            with self.assertRaises(filelock.AlreadyLocked):
                with gitutils.lock_repository_fetch(clone_path, block=False) as repo:
                    repo.fetch()

    def test_write_and_fetch_lock(self):
        clone_path = self._clone_repo()
        with gitutils.lock_repository_write(clone_path):
            with gitutils.lock_repository_fetch(clone_path) as repo:
                repo.fetch()

    def test_switch_to(self):
        self._commit_and_push_to_base_repo()
        clone_path = self._clone_repo()

        with gitutils.lock_repository_write(clone_path) as repo:
            with open(os.path.join(clone_path, "hi.txt"), 'w') as f:
                f.write("what if a predeploy script create a conflicting file?")
                f.flush()

            repo.switch_to(self.first_commit_sha)
            with open(os.path.join(clone_path, "hi.txt")) as f:
                self.assertEqual("hello there", f.read())

            repo.switch_to(self.second_commit_sha)
            with open(os.path.join(clone_path, "hi.txt")) as f:
                self.assertEqual("how do you do?", f.read())

            with open(os.path.join(clone_path, "do_not_keep_this.txt"), 'w') as f:
                f.write("this will be removed")
                f.flush()
            repo.switch_to(self.second_commit_sha)
            self.assertFalse(os.path.exists(os.path.join(clone_path, "do_not_keep_this.txt")))

    def test_build_repo_url(self):
        self.assertEqual("git@git:apiv2", gitutils.build_repo_url("apiv2", "git"))
        self.assertEqual("ssh://someone@gerrit:22/apiv2", gitutils.build_repo_url("apiv2", "ssh://someone@gerrit:22"))

    def test_look_for_file(self):
        self._commit_and_push_to_base_repo()
        clone_path = self._clone_repo()
        repo = gitutils.LocalRepository(clone_path)
        commits = repo.look_for_file(self.first_commit_sha, self.second_commit_sha, "hi.txt")
        self.assertEqual(1, len(commits))
        self.assertEqual(self.second_commit_sha, commits[0].hexsha)
