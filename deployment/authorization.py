# Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).
import collections


def permissions_from_dict(data):
    permissions = []
    data = collections.defaultdict(list, data)

    # The admin should be enough to do anything, so we could stop here,
    # but in order to allow serialization + unserialization we don't do anything clever here
    for name, permission in [('admin', SuperAdmin), ('impersonate', Impersonate), ('deployer', Deployer)]:
        if data[name] is True:
            permissions.append(permission())

    for name, permission in [('read', Read), ('deploy_business_hours', DeployBusinessHours), ('deploy', Deploy)]:
        for env_id in data[name]:
            permissions.append(permission(int(env_id)))

    return permissions


def permissions_to_dict(permissions):
    out = {}
    for permission in permissions:
        to_merge = permission.to_dict()
        for key, value in to_merge.iteritems():
            if key not in out:
                out[key] = value
                continue
            if not isinstance(out[key], type(value)):
                raise ValueError("Could not merge '{}' and '{}' (incompatible types)".format(out, to_merge))
            if isinstance(value, bool):
                out[key] = out[key] or value
            elif isinstance(value, list):
                out[key] += value
                out[key] = list(set(out[key]))  # remove duplicates
            else:
                raise ValueError("Could not merge '{}' and '{}' (unsupported type)".format(out, to_merge))
    return out


def dict_permissions_to_string(data):
    return permissions_to_dict(permissions_from_dict(data))


class Permission(object):

    def readable_environments(self):
        return []

    def implies(self, permission):
        return False

    def to_dict(self):
        raise NotImplemented('Subclasses must implement this method')


class Default(Permission):

    def to_dict(self):
        return {}


class Read(Permission):

    def __init__(self, environment_id):
        self.environment_id = environment_id

    def implies(self, permission):
        if isinstance(permission, Read):
            return permission.environment_id == self.environment_id
        if isinstance(permission, Default):
            return True
        return False

    def readable_environments(self):
        return [self.environment_id]

    def to_dict(self):
        return {'read': [self.environment_id]}


class DeployBusinessHours(Permission):

    def __init__(self, environment_id):
        self.environment_id = environment_id

    def implies(self, permission):
        if isinstance(permission, DeployBusinessHours):
            return permission.environment_id == self.environment_id
        return Read(self.environment_id).implies(permission)

    def readable_environments(self):
        return [self.environment_id]

    def to_dict(self):
        return {'deploy_business_hours': [self.environment_id]}


class Deploy(Permission):

    def __init__(self, environment_id):
        self.environment_id = environment_id

    def implies(self, permission):
        if isinstance(permission, Deploy):
            return permission.environment_id == self.environment_id
        return DeployBusinessHours(self.environment_id).implies(permission)

    def readable_environments(self):
        return [self.environment_id]

    def to_dict(self):
        return {'deploy': [self.environment_id]}


# Implied by nothing except SuperAdmin and Impersonate
# Test for this permission before using Permision.readable_environments()
class ReadAllEnvironments(Permission):

    def implies(self, permission):
        return any([isinstance(permission, Read),
                    isinstance(permission, Default),
                    isinstance(permission, ReadAllEnvironments)])


class SuperAdmin(Permission):

    def implies(self, permission):
        return True

    def to_dict(self):
        return {'admin': True}


class Impersonate(Permission):

    def implies(self, permission):
        return any([isinstance(permission, Impersonate),
                    ReadAllEnvironments().implies(permission)])

    def to_dict(self):
        return {'impersonate': True}


class Deployer(Permission):

    def implies(self, permission):
        return isinstance(permission, Permission) or isinstance(permission, Default)

    def to_dict(self):
        return {'deployer': True}
