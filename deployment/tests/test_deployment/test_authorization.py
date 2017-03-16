# Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).
import unittest
from deployment import authorization


class TestPermissionsImportAndExport(unittest.TestCase):

	def test_permissions_to_dict(self):
		permissions = [authorization.SuperAdmin(),
				 authorization.DeployBusinessHours(1),
				 authorization.DeployBusinessHours(2),
				 authorization.Deploy(1),
				 authorization.Read(3)]
		expected = {
			'admin': True,
			'deploy_business_hours': [1, 2],
			'deploy': [1],
			'read': [3]
		}
		self.assertEqual(expected, authorization.permissions_to_dict(permissions))

	def test_permissions_from_dict(self):
		data = {
			'admin': True,
			'deploy_business_hours': [1, 2],
			'deploy': [1],
			'read': [3]
		}
		self.assertEqual(data, authorization.permissions_to_dict(authorization.permissions_from_dict(data)))


class TestPermissions(unittest.TestCase):

	def test_implies(self):
		self.assertTrue(authorization.Deploy(1).implies(authorization.Read(1)))
		self.assertFalse(authorization.Deploy(1).implies(authorization.Read(2)))
		self.assertFalse(authorization.Read(1).implies(authorization.ReadAllEnvironments()))
		self.assertTrue(authorization.SuperAdmin().implies(authorization.ReadAllEnvironments()))
		self.assertTrue(authorization.Impersonate().implies(authorization.ReadAllEnvironments()))
		self.assertTrue(authorization.Impersonate().implies(authorization.Read(1)))
		self.assertTrue(authorization.SuperAdmin().implies(authorization.Read(1)))
		self.assertTrue(authorization.DeployBusinessHours(1).implies(authorization.Read(1)))
		self.assertFalse(authorization.Read(1).implies(authorization.Deploy(1)))
		self.assertFalse(authorization.Read(1).implies(authorization.SuperAdmin()))
		self.assertTrue(authorization.SuperAdmin().implies(authorization.SuperAdmin()))
		self.assertFalse(authorization.Read(1).implies(authorization.Read(2)))
		self.assertTrue(authorization.Read(1).implies(authorization.Read(1)))

	def test_readable_environments(self):
		self.assertEqual([1], authorization.Deploy(1).readable_environments())
		self.assertEqual([1], authorization.DeployBusinessHours(1).readable_environments())
		self.assertEqual([1], authorization.Read(1).readable_environments())

	def test_implies_self(self):
		permissions = [authorization.Deploy(1), authorization.Read(1), authorization.DeployBusinessHours(1),
				 authorization.SuperAdmin(), authorization.Impersonate(), authorization.ReadAllEnvironments()]
		for permission in permissions:
			self.assertTrue(permission.implies(permission))
