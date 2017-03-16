# Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).
# vim: set noexpandtab


import collections

from unittest import TestCase

from deployment.websocket import WebSocketEvent


class TestLogEvent(TestCase):

	def assertDictEqual(self, d1, d2, msg=None):
		"""
		Override assertDictEqual so that it uses assertEqual to compare dict values.
		See http://stackoverflow.com/a/18469095/4781931
		"""
		for k,v1 in d1.iteritems():
			self.assertIn(k, d2, msg)
			v2 = d2[k]
			if(isinstance(v1, collections.Iterable) and not isinstance(v1, basestring)):
				self.assertItemsEqual(v1, v2, msg)
			else:
				self.assertEqual(v1, v2, msg)
		return True

	def test_to_dict(self):
		log_event = WebSocketEvent("event.type", {"data": "this is an important message"})
		self.assertEqual({
			'type': 'event.type',
			'payload': {
				'data': 'this is an important message'
			}
		}, log_event.to_dict())
