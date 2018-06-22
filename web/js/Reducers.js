//Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).
import Immutable, { Map, fromJS } from 'immutable';
import { combineReducers } from 'redux-immutablejs';
import { routeReducer } from 'react-router-redux';
import moment from 'frozen-moment';


// TODO remove the "state" argument, and use Immutable merge function
function environmentFromPayload(payload, state = Map()) {
    state = state.set('id', payload.id).
        set('repositoryId', payload.repository_id).
        set('repositoryName', payload.repository_name).
        set('name', payload.name).
        set('targetPath', payload.target_path).
        set('autoDeploy', payload.auto_deploy).
        set('deployBranch', payload.deploy_branch).
        set('syncOptions', payload.sync_options).
        set('envOrder', payload.env_order).
        set('remoteUser', payload.remote_user).
        set('deployAuthorized', payload.deploy_authorized).
        set('failDeployOnFailedTests', payload.fail_deploy_on_failed_tests).
        set('clustersId', Immutable.List(payload.clusters));
    return state;
}

const environmentsByIdReducer = (state = Map(), action) => {
    switch(action.type) {
    case 'LOAD_ENVIRONMENT':
    case 'LOAD_ENVIRONMENTS':
    case 'ADD_ENVIRONMENT':
    case 'EDIT_ENVIRONMENT':
    case 'LOAD_RELEASES':
        if(action.payload.status != 'SUCCESS') {
            break;
        }
        Object.values(action.payload.entities.environments).map(environment => {
            state = state.mergeIn([environment.id], environmentFromPayload(environment));
        });
        break;
    case 'DELETE_ENVIRONMENT':
        if(action.payload.status != 'SUCCESS') {
            break;
        }
        Object.values(action.payload.entities.environments).map(environment => {
            state = state.remove(environment.id);
        });
        break;
    case 'LOAD_ENVIRONMENT_COMMITS':
        if(action.payload.status != 'SUCCESS') {
            break;
        }
        var environment = state.get(action.payload.environmentId, Map());
        environment = environment.set('commits', Immutable.Map({
            status: 'SUCCESS',
            list: Immutable.List(action.payload.commits.map(commit => Immutable.Map({
                hexsha: commit.hexsha,
                authoredDate: moment.utc(commit.authored_date).freeze(),
                message: commit.message,
                committer: commit.committer,
                deployable: commit.deployable
            })))
        }));
        state = state.set(action.payload.environmentId, environment);
        break;
    }
    return state;
};

function serversByIdReducer(state = Map(), action) {
    switch(action.type) {
    case 'LOAD_SERVERS_STATUS':
    case 'LOAD_RELEASES':
        if(action.payload.status != 'SUCCESS') {
            break;
        }
        const releases = action.payload.entities.releaseStatus;
        Object.keys(releases).forEach(releaseId => {
            const releaseStatus = releases[releaseId];
            state = state.setIn([releaseStatus.server_id, 'detailsByEnv', releaseStatus.environment_id],
                Immutable.Map({
                    'branch': releaseStatus.release ? releaseStatus.release.branch: undefined,
                    'commit': releaseStatus.release ? releaseStatus.release.commit: undefined,
                    'inProgress': releaseStatus.release ? releaseStatus.release.in_progress : undefined,
                    'statusCode': releaseStatus.get_info_successful ? 0 : 1,
                    'status': "SUCCESS",
                    'deploymentDate': releaseStatus.release && releaseStatus.release.deployment_date ? moment.utc(releaseStatus.release.deployment_date).freeze() : null,
                    'message': releaseStatus.get_info_error,
                })
            );
        });
    // fallthrough
    case 'LOAD_ENVIRONMENTS':
    case 'LOAD_ENVIRONMENT':
    case 'LOAD_SERVERS':
    case 'EDIT_SERVER':
    case 'ADD_SERVER':
        if(action.payload.status != 'SUCCESS') {
            break;
        }
        if(!action.payload.entities.servers) {
            // TODO: the real solution would be to figure out how to force
            // normalizr to create empty arrays instead
            break;
        }
        Object.values(action.payload.entities.servers).map(server => {
            state = state.mergeDeepIn([server.id], Map({
                status: server.status,
                inventoryKey: server.inventory_key,
                name: server.name,
                port: server.port,
                id: server.id,
                activated: server.activated,
                detailsByEnv: Map()
            }));
        });
        break;
    case 'DELETE_SERVER':
        if(action.payload.status != 'SUCCESS') {
            break;
        }
        Object.values(action.payload.entities.servers).map(server => {
            state = state.remove(server.id);
        });
        break;
    default:
        if(!action.payload) { break; }
        const serverId = action.payload.serverId;
        if(serverId != null) {
            var server = state.get(serverId);
            state = state.set(serverId, serverReducer(server, action));
            break;
        }
    }
    return state;
}


function clustersByIdReducer(state = Map(), action) {
    switch(action.type) {
    case 'LOAD_ENVIRONMENTS':
    case 'LOAD_CLUSTERS':
    case 'ADD_CLUSTER':
    case 'EDIT_CLUSTER':
    case 'LOAD_RELEASES':
        if(action.payload.status != 'SUCCESS') {
            break;
        }
        if(!action.payload.entities.clusters) {
            // TODO: the real solution would be to figure out how to force
            // normalizr to create empty arrays instead
            break;
        }
        Object.values(action.payload.entities.clusters).map(cluster => {
            state = state.mergeIn([cluster.id], clusterFromPayload(cluster, action.payload.entities.serverAssociations));
        });
        break;
    case 'DELETE_CLUSTER':
        if(action.payload.status != "SUCCESS") {
            break;
        }
        Object.values(action.payload.entities.clusters).map(cluster => {
            state = state.remove(cluster.id);
        });
        break;
    }
    return state;
}

function clusterFromPayload(payload, associations) {
    const state = Map({
        'id': payload.id,
        'name': payload.name,
        'inventoryKey': payload.inventory_key,
        'haproxyHost': payload.haproxy_host,
        'haproxyBackend': null,
        'servers': Immutable.List(payload.servers.map(association_id => Map({
            'serverId': associations[association_id].server,
            'haproxyKey': associations[association_id].haproxy_key
        }))
        )
    });
    return state;
}

// TODO: remove that, merge into serversByIdReducer
function serverReducer(state = fromJS({status: 'NONE', test: {code: -1}, detailsByEnv: {}}), action) {
    switch(action.type) {
    case 'UPDATE_SERVER_STATUS':
        state = state.setIn(['detailsByEnv', action.payload.environmentId, 'status'], action.payload.status);
        if(action.payload.status === 'SUCCESS') {
            state = state.mergeDeepIn(['detailsByEnv', action.payload.environmentId],
                Immutable.Map({
                    branch: action.payload.branch,
                    commit: action.payload.commit,
                    statusCode: action.payload.statusCode,
                    deploymentDate: action.payload.deploymentDate ? moment.utc(action.payload.deploymentDate).freeze() : null,
                    message: action.payload.message,
                    inProgress: action.payload.in_progress
                })
            );
        }
        break;
    }
    return state;
}

function repositoryFromPayload(payload) {
    return Map({
        'id': payload.id,
        'name': payload.name,
        'deployMethod': payload.deploy_method,
        'notifyOwnersMails': Immutable.List(payload.notify_owners_mails),
        'gitServer': payload.git_server,
        'environmentsId': Immutable.List(payload.environments)
    });
}

// FIXME: envs are not correctly added to the repo after creation, fix that
function repositoriesByIdReducer(state = Map(), action) {
    switch(action.type) {
    case 'LOAD_REPOSITORIES':
    case 'LOAD_REPOSITORY':
    case 'EDIT_REPOSITORY':
    case 'ADD_REPOSITORY':
        if(action.payload.status != "SUCCESS") {
            break;
        }
        Object.values(action.payload.entities.repositories).map(repository => {
            state = state.mergeIn([repository.id], repositoryFromPayload(repository));
        });
        break;
    case 'DELETE_ENVIRONMENT':
        if(action.payload.status != 'SUCCESS') {
            break;
        }
        Object.values(action.payload.entities.environments).map(environment => {
            state = state.updateIn([environment.repository, "environmentsId"], envs => envs.filter(id => id != environment.id));
        });
        break;
    case 'ADD_ENVIRONMENT':
    case 'LOAD_ENVIRONMENTS':
        if(action.payload.status != 'SUCCESS') {
            break;
        }
        Object.values(action.payload.entities.environments).map(environment => {
            // TODO use a Set instead
            state = state.updateIn([environment.repository_id, 'environmentsId'], envIds => envIds.concat([environment.id]).toSet().toList());
        });
        break;
    case 'DELETE_REPOSITORY':
        if(action.payload.status != 'SUCCESS') {
            break;
        }
        Object.values(action.payload.entities.repositories).map(repo => {
            state = state.remove(repo.id);
        });
        break;
    }
    return state;
}

function diffsByRepoReducer(state = Map(), action) {
    switch(action.type) {
    case 'FETCH_DIFF':
        if(action.payload.status !== 'SUCCESS') {
            break;
        }
        state = state.setIn(
            [action.payload.repositoryId, action.payload.fromSha, action.payload.toSha, 'message'],
            action.payload.message
        );
        break;
    }
    return state;
}

const parseLogEntry = entry =>
    Immutable.Map({
        date: moment.utc(entry.date).freeze(),
        id: entry.id,
        message: entry.message,
        severity: entry.severity
    });

function deploymentsByIdReducer(state = Map(), action) {
    switch(action.type) {
    case "LOAD_DEPLOYMENTS":
    case "LOAD_DEPLOYMENT":
    case 'UPDATE_DEPLOYMENT':
    case 'DEPLOY':
        if(action.payload.status != "SUCCESS") {
            break;
        }
        Object.values(action.payload.entities.deployments).map(deployment => {
            state = state.mergeIn([deployment.id], Map({
                'status': deployment.status,
                'repository_name': deployment.repository_name,
                'environment_name': deployment.environment_name,
                'environment_id': deployment.environment,
                'commit': deployment.commit,
                'branch': deployment.branch,
                'id': deployment.id,
                'user_id': deployment.user,
                'username': deployment.username,
                'date_start_deploy': moment.utc(deployment.date_start_deploy).freeze(),
                'date_end_deploy': deployment.date_end_deploy ? moment.utc(deployment.date_end_deploy).freeze() : null,
                'log_entries': deployment.log_entries ? Immutable.List(deployment.log_entries.map(entry => parseLogEntry(entry))) : Immutable.List()
            }));
        });
        break;
    }
    return state;
}


function userReducer(state = Map({'loggedIn': false, status: "NONE"}), action) {
    switch(action.type) {
    case 'LOGIN_FLOW_STARTED':
        state = state.set("status", "REQUEST").
            set("loggedIn", false);
        break;
    case 'LOGIN_FLOW_SUCCESS':
        state = state.set("status", "SUCCESS").
            set("loggedIn", true).
            set("userId", action.payload.user_id);
        break;
    case 'LOGIN_FLOW_ERROR':
        state = state.set("status", "ERROR").
            set("loggedIn", false).
            set("userId", null);
        break;
    case 'USE_GUEST_USER':
        state = state.set("status", "SUCCESS").
            set("loggedIn", false).
            set("userId", null);
        break;
    case 'ASK_LOGOUT':
        state = state.set("status", "NONE").
            set("loggedIn", false).
            set("userId", null);
        break;
    }
    return state;
}

function alertsByIdReducer(state = Map(), action) {
    switch(action.type) {
    case "ADD_ALERT":
        state = state.set(action.payload.id, Immutable.Map({
            id: action.payload.id,
            type: action.payload.type,
            message: action.payload.message,
            addedAt: action.payload.addedAt
        }));
        break;
    case "DISMISS_ALERT":
        state = state.remove(action.payload.id);
        break;
    }
    return state;
}

function rolesByIdReducer(state = Map(), action) {
    switch(action.type) {
    case "LOAD_ROLES":
    case "LOAD_ROLE":
    case "ADD_ROLE":
    case "EDIT_ROLE":
    case "LOAD_USERS":
        if(action.payload.status != "SUCCESS") {
            break;
        }
        Object.values(action.payload.entities.roles).map(role => {
            state = state.mergeIn([role.id], Map({
                id: role.id,
                name: role.name,
                permissions: role.permissions
            })
            );
        });
        break;
    case "DELETE_ROLE":
        if(action.payload.status != "SUCCESS") {
            break;
        }
        Object.values(action.payload.entities.roles).map(role => {
            state = state.remove(role.id);
        });
        break;
    }
    return state;
}

// TODO: remove duplicated code
function usersByIdReducer(state = Map(), action) {
    switch(action.type) {
    case 'LOGIN_FLOW_SUCCESS':
    case 'EDIT_USER':
    case 'LOAD_USERS':
    case 'ADD_USER':
        if(action.payload.status != "SUCCESS") {
            break;
        }
        Object.values(action.payload.entities.users).map(user => {
            state = state.mergeIn([user.id],
                Map({
                    id: user.id,
                    username: user.username,
                    email: user.email,
                    isSuperAdmin: user.is_superadmin,
                    accountid: user.accountid,
                    rolesId: Immutable.List(user.roles),
                    authTokenAllowed: action.payload.auth_token_allowed
                })
            );
        });
        break;
    case 'DELETE_USER':
        if(action.payload.status != "SUCCESS") {
            break;
        }
        Object.values(action.payload.entities.users).map(user => {
            state = state.remove(user.id);
        });
    }
    return state;
}


// This isn't pure (initial state depends on time), but is way simpler than any alternative
function websocketStateReducer(state = Map({lastPing: moment().freeze()}), action) {
    switch(action.type) {
    case 'WEBSOCKET_PINGED':
        state = state.set('lastPing', action.payload.pingMoment);
        break;
    }
    return state;
}


const appReducer = combineReducers({
    environmentsById: environmentsByIdReducer,
    repositoriesById: repositoriesByIdReducer,
    diffsByRepo: diffsByRepoReducer,
    deploymentsById: deploymentsByIdReducer,
    user: userReducer,
    routing: routeReducer,
    clustersById: clustersByIdReducer,
    serversById: serversByIdReducer,
    alertsById: alertsByIdReducer,
    rolesById: rolesByIdReducer,
    usersById: usersByIdReducer,
    websocketState: websocketStateReducer
});

const reducers = {
    app: appReducer,
    server: serverReducer,
    environmentsById: environmentsByIdReducer,
    clustersById: clustersByIdReducer
};

export default reducers;
