# Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).
# vim: set noexpandtab:
from unittest import TestCase

from Queue import Queue

from deployment import executils


class Testexecutils(TestCase):

	def test_exec_cmd_with_timeout(self):
		status, stdout, stderr = executils.exec_cmd("sleep 1", timeout=0.1, current_working_directory='/tmp')
		self.assertEqual(1, status)

	def test_exec_without_timeout(self):
		status, stdout, stderr = executils.exec_cmd("echo 'hey'", current_working_directory='/tmp', timeout=1)
		self.assertEqual('hey\n', stdout)
		self.assertEqual('', stderr)

	# This test can result in a LOT of logging
	# If an assertion fails, then nosetests tries to display the capture logging,
	# which may take a lot of time (and display a lot of y's)
	def test_exec_partial_stdout(self):
		status, stdout, stderr = executils.exec_cmd("yes", timeout=0.1)
		self.assertTrue(len(stdout) > 5)
		self.assertTrue(stdout.startswith('y'))
		self.assertTrue(stderr.startswith('Timeout'))

	def test_exec_partial_stderr(self):
		status, stdout, stderr = executils.exec_cmd("yes 1>&2", timeout=0.1, current_working_directory='/tmp')
		self.assertTrue(len(stdout) == 0)
		self.assertTrue(len(stderr) > 5)
		self.assertTrue(stderr.startswith('Timeout'))

	def test_exec_without_timeout_stderr(self):
		status, stdout, stderr = executils.exec_cmd("echo 'hey' 1>&2", timeout=0.1, current_working_directory='/tmp')
		self.assertEqual('hey\n', stderr)
		self.assertEqual('', stdout)
