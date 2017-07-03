//Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).
import Auth from 'Auth';
import { environment, role, repository, user, server, deployment, cluster, serverRelease, environmentRelease } from './Schemas';
import { restActions, createAction } from './actionutils';


function escapeRepository(repo) {
    return repo.replace(/\//g,"~");
}

export const addAlert = (type, message, id) => dispatch => {
    const action = createAction('ADD_ALERT', (type, message, id) => {
        return {
            'id': id,
            'type': type,
            'message': message,
            'addedAt': new Date()
        };
    });
    if(id == null) {
        id = genid();
    }
    dispatch(action(type, message, id));
    // Automatically dismiss non errors after 10 seconds
    if(type != "DANGER") {
        setTimeout(() => { dispatch(dismissAlert(id))}, 10*1000);
    }
};

export const dismissAlert = createAction('DISMISS_ALERT', alertId => ({
    'id': alertId
}));


export const loginFlowStarted = () => dispatch => {
    const action = createAction('LOGIN_FLOW_STARTED');
    dispatch(action({status: "SUCCESS"}));
};

export const askLogin = () => dispatch => {
    const action = createAction('ASK_LOGIN');
    Auth.login();
    dispatch(action({status: "SUCCESS"}));
};

export const askLogout = () => dispatch => {
    const action = createAction('ASK_LOGOUT');
    Auth.logout();
    dispatch(action({status: "SUCCESS"}));
};

export const loginFlowSuccess = createAction('LOGIN_FLOW_SUCCESS', user => ({
    user_id: user.id,
    status: "SUCCESS",
    entities: {
        users: {
            [user.id]: user
        }
    }
}));


export const useGuestUser = createAction('USE_GUEST_USER', () => ({
    status: "SUCCESS"
}));

export const loginFlowError = createAction('LOGIN_FLOW_ERROR');


const repositoryActions = restActions('repository', 'repositories', {
    baseUrl: () => '/repositories/',
    postUrl: () => '/repositories',
    schema: repository,
    alertAction: addAlert,
    makeData: ({repositoryName, gitServer, deployMethod, notifyOwnersMails, environmentsId}) => ({
        name: repositoryName,
        git_server: gitServer,
        deploy_method: deployMethod,
        environments_id: environmentsId,
        notify_owners_mails: notifyOwnersMails
    })
});
export const loadRepository = repositoryActions.get;
export const loadRepositories = repositoryActions.list;
export const editRepository = repositoryActions.edit;
export const addRepository = repositoryActions.add;
export const deleteRepository = repositoryActions.delete;

export function loadEnvironmentCommits(environmentId) {
    const action = createAction('LOAD_ENVIRONMENT_COMMITS', (status, environmentId, commits) => ({
        status,
        environmentId,
        commits
    }));
    return dispatch => {
        dispatch(action('REQUEST', environmentId));
        Auth.getJSON(`/environments/${environmentId}/commits`, json => {
            dispatch(action('SUCCESS', environmentId, json.commits));
        });
    };
}

const serverActions = restActions('server', 'servers', {
    baseUrl: () => '/servers/',
    schema: server,
    makeData: ({name, port, activated = true}) => ({name, port, activated}),
    alertAction: addAlert,
});
export const loadServerList = serverActions.list;
export const addServer = serverActions.add;
export const deleteServer = serverActions.delete;
export const updateServer = (id, name, port, activated) => serverActions.edit(id, {name, port, activated});

export const loadServersStatus = environmentId => restActions('servers_status', 'servers_status', {
    baseUrl: (environmentId) => `/environments/${environmentId}/servers`,
    schema: serverRelease
}).list(environmentId);

export const updateServerStatus = createAction('UPDATE_SERVER_STATUS', (serverId, deploymentDate, branch, commit, environmentId) => ({
    status: 'SUCCESS',
    serverId,
    statusCode: 0,
    message: undefined,
    branch,
    commit,
    deploymentDate,
    environmentId,
    in_progress: false
}));

export function loadDiff(repositoryId, fromSha, toSha) {
    return dispatch => {
        const action = createAction('LOAD_DIFF', (repositoryId, fromSha, toSha, status, message) => ({
            repositoryId,
            fromSha,
            toSha,
            status,
            message
        }));
        const partial = action.bind(null, repositoryId, fromSha, toSha);
        dispatch(partial('REQUEST', null));
        dispatch(showDiff());
        Auth.getJSON(`/repositories/${repositoryId}/diff?from=${fromSha}&to=${toSha}`, json => {
            dispatch(partial('SUCCESS', json.diff.diff));
        });
    };
}
export const showDiff = createAction('SHOW_DIFF');
export const hideDiff = createAction('HIDE_DIFF');

const genid = () => {
    const s4 = () =>
        Math.floor((1 + Math.random()) * 0x10000)
        .toString(16)
        .substring(1);
    return s4() + s4() + s4();
};

export function deploy(environmentId, commit, branch, clusterId, serverId) {
    return dispatch => {
        const action = createAction('DEPLOY', (environmentId, commit, branch, clusterId, serverId, status, deploymentId) => ({
            deployment: {
                status,
                environment_id: environmentId,
                commit,
                branch,
                cluster_id: clusterId,
                server_id: serverId,
                id: deploymentId
            }
        }));
        const data = {
            branch,
            commit,
            target: {
                cluster: clusterId,
                server: serverId
            }
        };
        const partial = action.bind(null, environmentId, commit, branch, clusterId, serverId);
        dispatch(partial('REQUEST', null));
        Auth.postJSON(`environments/${environmentId}/deployments`, data, json => {
            dispatch(partial('SUCCESS', json.deployment_id));
        }, () => {
            dispatch(partial('ERROR', null));
            dispatch(addAlert('DANGER', `Error: could not start the deployment of ${branch}/${commit}`));
        });
    };
}

export const updateDeployment = createAction('UPDATE_DEPLOYMENT', ({deployment}) => ({
    status: 'SUCCESS',
    entities: {
        deployments: { [deployment.id]: deployment }
    }
}));

// TODO: use repositoryId instead of repositoryName
const deploymentActions = restActions("deployment", "deployments", {
    baseUrl: ({ repositoryName=null, recent=false } = {}) => {
        if(repositoryName != null && recent) {
            throw Error("You can set only one of deploymentId and recent.");
        } else if(repositoryName != null) {
            return `deployments/byrepo/${escapeRepository(repositoryName)}`;
        } else if(recent) {
            return "deployments/recent";
        } else {
            return "deployments";
        }
    },
    entityUrl: id => `deployments/${id}`,
    schema: deployment
});
export const loadDeployment = deploymentActions.get;
export const loadRecentDeployments = () => deploymentActions.list({recent: true});
export const loadDeploymentHistory = (repositoryName) => deploymentActions.list({repositoryName});

const clusterActions = restActions('cluster', 'clusters', {
    baseUrl: () => '/clusters',
    schema: cluster,
    // servers: array of {'haproxyKey': ..., 'serverId': ...}
    makeData: ({name, haproxyHost, servers}) => {
        const serversData = servers.map(serverData => ({
            haproxy_key: serverData.haproxyKey,
            server_id: serverData.serverId
        }));
        return {name, haproxy_host: haproxyHost, servers: serversData};
    },
    alertAction: addAlert
});
export const loadClusterList = clusterActions.list;
export const addCluster = clusterActions.add;
export const deleteCluster = clusterActions.delete;
export const editCluster = clusterActions.edit;

const environmentActions = restActions("environment", "environments", {
    postUrl: ({repositoryId}) => `/repositories/${repositoryId}/environments`,
    baseUrl: ({repositoryId = null} = {}) => (repositoryId == null ? '/environments' : `repositories/${repositoryId}/environments/`),
    makeData: data => ({
        name: data.environmentName,
        auto_deploy: data.autoDeploy,
        deploy_branch: data.deployBranch,
        env_order: data.envOrder,
        target_path: data.targetPath,
        remote_user: data.remoteUser,
        sync_options: data.syncOptions,
        clusters_id: data.clustersId,
        fail_deploy_on_failed_tests: data.failDeployOnFailedTests,
    }),
    alertAction: addAlert,
    schema: environment
});
export const addEnvironment = (repositoryId, data) => (environmentActions.add(data, { repositoryId }));
export const editEnvironment = environmentActions.edit;
export const deleteEnvironment = environmentActions.delete;
export const loadEnvironment = environmentActions.get;
export const loadEnvironments = (repositoryId = null) => (environmentActions.list({ repositoryId }));

export function updateCommits(repositoryName, branch) {
    return dispatch => {
        const action = createAction('UPDATE_COMMITS', (repositoryName, branch, status) => ({
            repositoryName,
            branch,
            status
        }));
        dispatch(action(repositoryName, branch, 'REQUEST'));
        const data = {
            'repository': repositoryName,
            'branch': branch
        };
        Auth.postJSON('/notification/updatedrepo', data, () => {
            dispatch(action(repositoryName, branch, 'SUCCESS'));
        });
    };
}

const roleActions = restActions("role", "roles", {
    baseUrl: () => '/roles',
    makeData: ({name, permissions}) => ({
        name: name,
        permissions: permissions
    }),
    alertAction: addAlert,
    schema: role
});
export const loadRoles = roleActions.list;
export const loadRole = roleActions.get;
export const addRole = (name, permissions) => roleActions.add({name, permissions});
export const updateRole = (id, name, permissions) => roleActions.edit(id, {name, permissions});
export const deleteRole = id => roleActions.delete(id);

const userActions = restActions("user", "users", {
    baseUrl: () => '/users',
    makeData: data => {
        const out = {
            username: data.username,
            email: data.email,
            accountid: data.accountid,
            roles: data.roles
        };
        if(!data.authTokenAllowed) {
            // ignore the provided token if we want to deactivate it anyway
            out.authToken = null;
        }
        if(data.authTokenAllowed && data.authToken) {
            // if the token was changed, submit the new token to the server
            // otherwise, do not set the key (it means "no update" for the server)
            out.auth_token = data.authToken;
        }
        return out;
    },
    alertAction: addAlert,
    schema: user
});
export const loadUsers = userActions.list;
export const deleteUser = userActions.delete;
export const addUser = userActions.add;
export const editUser = userActions.edit;

export const websocketPinged = createAction('WEBSOCKET_PINGED', pingMoment => ({
    pingMoment
}));

export const loadAllReleasesForServer = serverId => restActions('release', 'releases', {
    baseUrl: (serverId) => `/servers/${serverId}/releases`,
    schema: environmentRelease
}).list(serverId);
