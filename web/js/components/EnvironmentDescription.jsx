//Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).
import React from 'react';
import { connect } from 'react-redux';
import PureRenderMixin from 'react-addons-pure-render-mixin';
import ImmutablePropTypes from 'react-immutable-proptypes';
import { ServerActionsHandler } from './ServerActions.jsx';
import CommitSelector from './CommitSelector.jsx';
import DeployLogs from './DeployLogs.jsx';
import * as Actions from '../Actions';
import WebSockGateway from '../WebSockGateway';
import debounce from 'debounce';
import SetIntervalMixin from '../mixins/SetIntervalMixin';
import { Map, List } from 'immutable';


const DeploymentDate = React.createClass({
    mixins: [SetIntervalMixin],
    propTypes: {
        deploymentDate: React.PropTypes.object
    },
    tick() {
        this.forceUpdate();
    },
    componentDidMount() {
        this.setInterval(this.tick, 5000);
    },
    render() {
        if(!this.props.deploymentDate) {
            return <span>Unknown</span>;
        }
        const elapsed = this.props.deploymentDate.fromNow();
        const formatted = this.props.deploymentDate.local().format('YYYY-MM-DD HH:mm');
        return <span>{formatted}<br />({elapsed})</span>;
    }
});


export const EnvironmentDescriptionWrapper = React.createClass({
    mixins: [PureRenderMixin],
    fetchData() {
        this.props.dispatch(Actions.loadServersStatus(this.props.environmentId));
        this.props.dispatch(Actions.loadEnvironmentCommits(this.props.environmentId));
    },
    unsubscribeWebsocket(environment_id) {
        WebSockGateway.send({
            'type': 'unsubscribe',
            'payload': {
                'environment_id': environment_id
            }
        });
    },
    subscribeToWebsocket(environment_id) {
        function sendSubscriptionMessage() {
            WebSockGateway.send({
                'type': 'subscribe',
                'payload': {
                    'environment_id': environment_id
                }
            });
        }
        sendSubscriptionMessage();
        WebSockGateway.listen('local.websocket.connected', sendSubscriptionMessage);
    },
    componentWillMount() {
        this.fetchData();
        this.subscribeToWebsocket(this.props.environment.get('id'));
    },
    componentWillUnmount() {
        this.unsubscribeWebsocket(this.props.environment.get('id'));
    },
    componentWillReceiveProps(newProps) {
        if(newProps.environmentId != this.props.environmentId) {
            this.fetchData();
            if(this.props.environment) {
                this.unsubscribeWebsocket(this.props.environment.get('repositoryName'), this.props.environment.get('name'));
                this.subscribeToWebsocket(this.props.environment.get('repositoryName'), newProps.environment.get('name'));
            }
        }
    },
    render() {
        return <EnvironmentDescription
            environment={this.props.environment}
            clusters={this.props.clusters}
            servers={this.props.servers}
            deploymentAlreadyInProgress={this.props.deploymentAlreadyInProgress}
            repositoryId={this.props.repositoryId}
            dispatch={this.props.dispatch}
            deploymentsInEnv={this.props.deploymentsInEnv}
            onMultiDeployClicked={this.startMultiDeploy}
        />
    },
    startMultiDeploy(clusterId, commit) {
        if(this.props.deploymentAlreadyInProgress) {
            return;
        }
        this.props.dispatch(Actions.deploy(
            this.props.environmentId,
            commit,
            this.props.environment.get('deployBranch'),
            clusterId,
            null
        ));
    }
});


export const EnvironmentDescriptionHandler = connect(
    (state, {environmentId}) => {
        const environment = state.getIn(['environmentsById', environmentId]);
        const clusters = state.get('clustersById', Map()).
                filter(cluster => environment.get('clustersId').includes(cluster.get('id'))).
                toList();
        const serverIds = clusters.map(cluster =>
            cluster.get('servers').map(server => server.get('serverId'))
        ).flatten();
        const servers = state.get('serversById', Map()).
            filter(server => serverIds.includes(server.get('id')))
            .toList();
        const deploymentAlreadyInProgress = !!state.get('deploymentsById', Map()).
            find(
                deployment => (
                    deployment.get('environment_id') == environmentId && !(['COMPLETE', 'FAILED'].includes(deployment.get('status')))
                ),
                null,
                false);
        const repositoryId = environment.get('repositoryId');
        // TODO: also filter old deployments
        const deploymentsInEnv = state.get('deploymentsById').
            filter(deployment => deployment.get('environment_id') == environmentId).
            toList();
        return {
            environment,
            clusters,
            servers,
            deploymentAlreadyInProgress,
            repositoryId,
            deploymentsInEnv
        };
    }
)(EnvironmentDescriptionWrapper);


const EnvironmentDescription = ({environment, clusters, servers, deploymentAlreadyInProgress, repositoryId, dispatch, deploymentsInEnv, onMultiDeployClicked}) => {
    const deployableCommits = environment.getIn(['commits', 'list'], List()).filter(commit => commit.get('deployable'));
    return <div>
        <h3>{environment.get('name')}</h3>
        <div className="row">
            <div className="col-md-6">
                <ConfigurationBlock
                    deployBranch={environment.get('deployBranch')}
                    autoDeploy={environment.get('autoDeploy')}
                    remoteUser={environment.get('remoteUser')}
                    syncOptions={environment.get('syncOptions')}
                    targetPath={environment.get('targetPath')} />
            </div>
            <div className="col-md-6">
                {
                    environment.get('deployAuthorized') ?
                        <MultiDeployBlock
                            clusters={clusters}
                            commits={deployableCommits}
                            onMultiDeployClicked={onMultiDeployClicked}
                            deploymentAlreadyInProgress={deploymentAlreadyInProgress}
                        />
                                :
                    <p>You are not allowed to deploy in this environment.</p>
                }
            </div>
        </div>
        <ServerTable
            servers={servers}
            clusters={clusters}
            deploymentAlreadyInProgress={deploymentAlreadyInProgress}
            deployableCommits={deployableCommits}
            environmentId={environment.get('id')}
            repositoryId={repositoryId}
        />
        { <DeployLogs deployments={deploymentsInEnv}/> }
    </div>
}


const makeClusterRows = (clusterName, servers, deployableCommits, stripped, clusterSize, environmentId, repositoryId) => {
    let tdClassName = "td-small";
    if(stripped) {
        tdClassName += " td-striped";
    }
    return servers.map((server, index) => {
        const details = server.get('detailsByEnv', Map()).get(environmentId, Map());
        const serverLoaded = details.get('status') === 'SUCCESS';
        return (
            <tr key={clusterName + "-" + server.get('id')}>
                {index == 0 ?
                    <td className={tdClassName} rowSpan={clusterSize}>
                        <span className="vertical-text"><span className="vertical-text__inner">{clusterName}</span></span>
                    </td>
                    : null
                }
                <td title={server.get('name')} className="text-nowrap">
                    {server.get("activated") ? null : <span><span className="glyphicon glyphicon-ban-circle" title="deactivated"></span> </span>}{formatServerName(server)}
                </td>
                <td>
                    {serverLoaded ? formatCommit(details) : "Loading..."}
                </td>
                <td className="text-nowrap">
                    {serverLoaded ? <DeploymentDate deploymentDate={details.get('deploymentDate')}/> : "Loading..."}
                </td>
                <td>
                    <ServerActionsHandler
                        environmentId={environmentId}
                        serverId={server.get('id')}
                        repositoryId={repositoryId}
                        server={server} />
                </td>
            </tr>
        );
    });
}

// TODO: better schema for props (the current one mirrors the Redux state, but is a pain to work with at this
// level)
const ServerTable = ({servers, clusters, deployableCommits, deploymentAlreadyInProgress, environmentId, repositoryId}) => {
    const rows = clusters.sort((c1, c2) => c1.get('name').localeCompare(c2.get('name'))).
        map((cluster, clusterIndex) => {
            const serverIdsInCluster = cluster.get('servers').
                map(serverDef => serverDef.get('serverId'));
            const serversInCluster = servers.filter(server => serverIdsInCluster.includes(server.get('id'))).
                sortBy(server => server.get('name'));
            return makeClusterRows(
                cluster.get('name'),
                serversInCluster,
                deployableCommits,
                clusterIndex % 2 == 0,
                cluster.get('servers').size,
                environmentId,
                repositoryId
            );
        }).flatten();
    return <table className="table">
        <thead>
            <tr>
                <th>{/* Cluster */}</th>
                <th>Server</th>
                <th>Currently deployed</th>
                <th>Deployment date</th>
                <th>Available commits</th>
            </tr>
        </thead>
        <tbody>
            { rows }
        </tbody>
    </table>
}


const formatServerName = (server) => {
    const name = server.get('name');
    const suffixesToRemove = process.env.HIDE_HOSTNAME_SUFFIXES;
    for(let i = 0, len = suffixesToRemove.length; i < len; i++) {
        const suffix = suffixesToRemove[i];
        if(name.endsWith(suffix)) {
            return name.slice(0, -suffix.length);
        }
    }
    return name;
}

const formatCommit = (details) => {
    if(details.get('statusCode') == 0) {
        return details.get('commit').substring(0, 8);
    }
    return <span className="text-warning">Error: {details.get('message')}</span>;
}


// TODO: use syncOptions default from server
const ConfigurationBlock = ({deployBranch, autoDeploy, remoteUser, syncOptions, targetPath}) =>
    <table className="table table-condensed">
        <tbody>
            <tr>
                <th><span className="glyphicon glyphicon-random"></span> Branch</th>
                <td>{deployBranch + (autoDeploy ? " (automatically deployed)" : "")}</td>
            </tr>
            <tr>
                <th><span className="glyphicon glyphicon-floppy-save"></span> Rsync Options</th>
                <td>rsync flags: '{syncOptions ? syncOptions : "-az --delete"}'</td>
            </tr>
            <tr>
                <th><span className="glyphicon glyphicon-play"></span> Target</th>
                <td>user: '{remoteUser}' -- target path: {targetPath}</td>
            </tr>
        </tbody>
    </table>


class MultiDeployBlock extends React.Component {
    constructor(props) {
        super(props);
        this.state = {selectedCluster: "default"};
    }
    onChange(event) {
        this.setState({selectedCluster: event.target.value});
    }
    componentWillMount() {
        this.onMultiDeployClicked = debounce(this.onMultiDeployClicked, 3000, true);
    }
    onMultiDeployClicked() {
        let clusterId = null;
        if(this.state.selectedCluster != 'default') {
            clusterId = parseInt(this.state.selectedCluster.substring(2), 10);
        }
        this.props.onMultiDeployClicked(clusterId, this.clusterCommitSelector.getSelectedCommit());
    }
    render() {
        const that = this;
        let multiDeployButtonClass = "btn btn-sm btn-warning";
        let message = "Deploy on cluster";
        if(this.props.deploymentAlreadyInProgress) {
            multiDeployButtonClass += " btn-disabled";
            message = "In progress...";
        }
        return <div>
            <form className="form-horizontal">
                <div className="form-group">
                    <label className="col-sm-2 control-label">Commit</label>
                    <div className="col-sm-10">
                        { this.props.commits ?
                            <CommitSelector commits={this.props.commits} ref={(el) => this.clusterCommitSelector = el}/>
                            :
                            <p>Loading...</p>
                        }
                    </div>
                </div>
                <div className="form-group">
                    <label className="col-sm-2 control-label">Cluster</label>
                    <div className="col-sm-3">
                        <select className="input-sm form-control" value={this.state.selectedCluster} onChange={(event) => this.onChange(event)}>
                            <option key={"default"} value="default">all</option>
                            {
                                that.props.clusters.map(cluster => <option key={`c-${cluster.get('id')}`} value={`c-${cluster.get('id')}`}>{cluster.get('name')}</option>)
                            }
                        </select>
                    </div>
                    <div className="col-sm-2">
                        <button type="button" onClick={() => that.onMultiDeployClicked()} className={multiDeployButtonClass}>{message}</button>
                    </div>
                </div>
            </form>
        </div>
    }
}

// TODO: have a "models" module defining those, rather than copying them around
MultiDeployBlock.propTypes = {
    clusters: React.PropTypes.object.isRequired,
    commits: React.PropTypes.object,
    onMultiDeployClicked: React.PropTypes.func.isRequired,
    deploymentAlreadyInProgress: React.PropTypes.bool.isRequired
}
