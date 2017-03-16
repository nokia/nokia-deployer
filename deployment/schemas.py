# Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).
import sys
import inspect
import json

from marshmallow import fields
from sqlalchemy import orm
import sqlalchemy as sa
from marshmallow_sqlalchemy import ModelSchema, ModelConversionError, field_for
from marshmallow import Schema

from . import samodels as m, authorization


class BaseSchema(ModelSchema):
	class Meta(object):
		strict = True


class RepositorySchema(BaseSchema):
	class Meta(BaseSchema.Meta):
		model = m.Repository

	environments = fields.Method("get_environments")
	_notify_owners_mails = fields.Method(
		serialize="dump_mails",
		deserialize="load_mails",
		dump_to="notify_owners_mails",
		load_from='notify_owners_mails')

	def dump_mails(self, obj):
		return obj.notify_owners_mails

	def load_mails(self, value):
		if value is None:
			return None
		out = ",".join(s.strip() for s in value)
		return out

	def get_environments(self, obj):
		ids = [env.id for env in obj.environments]
		if self.context and not self.context['account'].has_permission(authorization.ReadAllEnvironments()):
			ids = [env_id for env_id in ids if env_id in self.context['account'].readable_environments()]
		return ids


class ServerSchema(BaseSchema):
	class Meta(BaseSchema.Meta):
		model = m.Server

	clusters = fields.Function(
		lambda obj: [{"cluster_id": c.cluster_id, "haproxy_key": c.haproxy_key} for c in obj.clusters])


class ClusterSchema(BaseSchema):
	class Meta(BaseSchema.Meta):
		model = m.Cluster

	servers = fields.Method("format_servers")

	def format_servers(self, obj):
		return [{
			"haproxy_key": s.haproxy_key,
			"server": ServerSchema(exclude=("clusters",)).dump(s.server_def).data,
			"id": "_".join([str(e) for e in [s.cluster_id, s.server_id]])
		} for s in obj.servers]


class _InnerClusterPostSchema(Schema):
	class Meta(object):
		strict = True
	haproxy_key = fields.String(missing=None)
	server_id = fields.Integer()


class ClusterPostSchema(Schema):
	class Meta(object):
		strict = True
	name = fields.String()
	haproxy_host = fields.String(missing=None)
	servers = fields.List(fields.Nested(_InnerClusterPostSchema))


class EnvironmentSchema(BaseSchema):
	class Meta(BaseSchema.Meta):
		model = m.Environment
		exclude = ("deployments",)

	clusters = fields.Nested(ClusterSchema, many=True, exclude=("environments",))
	deploy_authorized = fields.Method("add_deploy_authorized")
	repository_id = fields.Function(lambda obj: obj.repository.id)
	repository_name = fields.Function(lambda obj: obj.repository_name)
	# TODO: normalize DB

	def add_deploy_authorized(self, obj):
		if self.context and 'account' in self.context:
			return self.context['account'].has_permission(authorization.DeployBusinessHours(obj.id))
		return False


class PostEnvironmentSchema(EnvironmentSchema):
	clusters = field_for(m.Environment, 'clusters', load_from='clusters_id')


class LogEntrySchema(BaseSchema):
	class Meta(BaseSchema.Meta):
		model = m.LogEntry


class DeploymentViewSchema(BaseSchema):
	class Meta(BaseSchema.Meta):
		model = m.DeploymentView
	log_entries = fields.List(fields.Nested(LogEntrySchema))


class RoleSchema(BaseSchema):
	class Meta(BaseSchema.Meta):
		model = m.Role
		exclude = ("users",)

	permissions = fields.Method("dump_permissions", "load_permissions")

	def dump_permissions(self, obj):
		return json.loads(obj.permissions)

	def load_permissions(self, value):
		return json.dumps(authorization.dict_permissions_to_string(value))


class UserSchema(BaseSchema):
	class Meta(BaseSchema.Meta):
		model = m.User
		exclude = ('session_token', 'token_issued_at', 'auth_token')

	roles = fields.List(fields.Nested(RoleSchema))
	is_superadmin = fields.Function(lambda obj: obj.has_permission(authorization.SuperAdmin()))
	auth_token_allowed = fields.Function(lambda obj: obj.auth_token is not None)


def _register_explicit_schemas():
	for name, obj in inspect.getmembers(sys.modules[__name__]):
		if hasattr(obj, '__name__') and obj.__name__.endswith('Schema') \
				and issubclass(obj, BaseSchema) and obj != BaseSchema:
			if not hasattr(obj.Meta, '__marshmallow__'):
				# FIXME
				if obj != PostEnvironmentSchema:
					obj.Meta.model.__marshmallow__ = obj


# adapted from
# http://marshmallow-sqlalchemy.readthedocs.io/en/latest/recipes.html#automatically-generating-schemas-for-sqlalchemy-models
def _register_deduced_schemas(Base):
	def setup_schema_fn():
		# Generate missing schemas
		for class_ in Base._decl_class_registry.values():
			if hasattr(class_, '__tablename__') and not hasattr(class_, '__marshmallow__'):
				if class_.__name__.endswith('Schema'):
					raise ModelConversionError(
						"For safety, setup_schema can not be used when a"
						"Model class ends with 'Schema'"
					)

				class Meta(BaseSchema.Meta):
					model = class_

				schema_class_name = '%sSchema' % class_.__name__

				schema_class = type(
					schema_class_name,
					(BaseSchema,),
					{'Meta': Meta}
				)

				setattr(class_, '__marshmallow__', schema_class)

	return setup_schema_fn


def register_schemas(Base):
	"""Sets the __marshmallow__ attribute on all model classes.

	Model classes are all the models under the provided declarative Base.
	The __marshmallow__ attribute specifies which schema to use for general serialization of this model
	(esp. in the API).

	Such a schema can be explicitely defined in this module (needs to inherit from ModelSchema and 
	have a class name ending in "Schema"). If not, it is inferred from the model.
	"""
	_register_explicit_schemas()
	_register_deduced_schemas(Base)()
	# If the mapper configuration is not complete yet, models will not be stored
	# in the declarative Base, hence this trigger:
	sa.event.listen(orm.mapper, 'after_configured', _register_deduced_schemas(Base))
