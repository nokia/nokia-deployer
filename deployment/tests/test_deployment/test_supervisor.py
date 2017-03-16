# Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).
from unittest import TestCase

from deployment.supervisor import _import_class
import logging


class TestSupervisor(TestCase):

	def test_import_class(self):
		logger_class = _import_class('logging.Logger')
		self.assertEqual(logger_class, logging.Logger)
