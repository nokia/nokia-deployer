//Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).
import { Schema, arrayOf } from 'normalizr';

export const repository = new Schema('repositories');
export const environment = new Schema('environments');
export const serverAssociation = new Schema('serverAssociations');
export const server = new Schema('servers');
export const cluster = new Schema('clusters');
export const inventory_cluster = new Schema('inventory_cluster');
export const role = new Schema('roles');
export const user = new Schema('users');
export const deployment = new Schema('deployments');
export const environmentRelease = new Schema('environmentRelease', {
    idAttribute: entity => entity.environment.id
});
export const serverRelease = new Schema('serverRelease', {
    idAttribute: entity => entity.release_status.id
});
export const releaseStatus = new Schema('releaseStatus');


repository.define({
    environments: arrayOf(environment)
});

environment.define({
    clusters: arrayOf(cluster)
});

cluster.define({
    servers: arrayOf(serverAssociation)
});

inventory_cluster.define({
    servers: arrayOf(server)
});

serverAssociation.define({
    server: server
});

user.define({
    roles: arrayOf(role)
});

environmentRelease.define({
    environment,
    servers: arrayOf(serverRelease)
});

serverRelease.define({
    release_status: releaseStatus,
    server
});
