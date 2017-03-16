# Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).
# -*- encoding: utf-8 -*

import unittest
from deployment import notification


class TestNotifierCollection(unittest.TestCase):

	def test_notifier_collection(self):

		class DummyNotifier(object):

			def __init__(self):
				self.called = False

			def dispatch(self, event):
				self.called = True

		n1 = DummyNotifier()
		n2 = DummyNotifier()
		n = notification.NotifierCollection(n1, n2)
		n.dispatch(None)
		self.assertEqual(n1.called, True)
		self.assertEqual(n2.called, True)

	def test_graphite_sanitize(self):
		sanitized = notification.GraphiteNotifier.sanitize_for_graphite("ùgly/name~for+graphite")
		self.assertEqual("--gly-name-for-graphite", sanitized)
