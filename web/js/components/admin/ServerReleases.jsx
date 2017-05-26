//Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).
import React from 'react';
import { connect } from 'react-redux';
import { Map, fromJS  } from 'immutable';
import * as Actions from '../../Actions.js';
import { Link } from 'react-router';

const ServerReleasesHandler = React.createClass({
    componentWillMount() {
        this.props.dispatch(Actions.loadAllReleasesForServer(this.props.serverId));
    },
    componentWillReceiveProps(nextProps) {
        if(nextProps.serverId != this.props.serverId) {
            this.props.dispatch(Actions.loadAllReleasesForServer(this.props.serverId));
        }
    },
    render() {
        return <ServerReleasesList 
            allServers={this.props.allServers}
            server={this.props.server}
            environmentsById={this.props.environmentsById}
        />;
    }
});

export const ServerReleases = connect(
    (state, ownProps) => {
        const serverId = parseInt(ownProps.params.id, 10);
        return {
            allServers: state.get('serversById'),
            server: state.get('serversById').get(serverId),
            environmentsById: state.get('environmentsById'),
            serverId: serverId
        };
    }
)(ServerReleasesHandler);

export default ServerReleases;

const mapEnvironmentsAndServers = (environmentIds, servers, environmentsById) => {
    let serverEnvironmentMapping = Map();
    environmentIds.map(environmentId => {
        const environment = environmentsById.get(environmentId);
        if(!environment) {
            return;
        }
        const serversInEnv = servers.filter(server => server.get('detailsByEnv').get(environmentId));
        serverEnvironmentMapping = serverEnvironmentMapping.set(environmentId,
            fromJS({
                environment: environment,
                servers: serversInEnv
            }));
    });
    return serverEnvironmentMapping;
};

const ServerReleasesList = ({server, allServers, environmentsById}) => {
    if(!server) { return <h2>Loading...</h2>; }
    const environmentIds = server.get('detailsByEnv').keySeq().toList();
    const serverEnvironmentMapping = mapEnvironmentsAndServers(environmentIds, allServers, environmentsById);
    return <div>
        <h2>Environments for {server.get('name')}</h2>
        <table className="table">
            <thead>
                <tr>
                    <th>Repository</th>
                    <th>Environment</th>
                    <th>Discrepancies</th>
                </tr>
            </thead>
            <tbody>
                {serverEnvironmentMapping.map(mapping => 
                <tr key={mapping.get('environment').get('id')}>
                    <td><Link to={`/repositories/${mapping.get('environment').get('repositoryId')}`}>{ mapping.get('environment').get('repositoryName') }</Link></td>
                    <td>{ mapping.get('environment').get('name') }</td>
                    <td> <Discrepancies servers={mapping.get('servers')} environment={mapping.get('environment')} /></td>
                </tr>
                ).toList()}
            </tbody>
        </table>
    </div>;
};


const Discrepancies = ({servers, environment}) => {
    const environmentId = environment.get('id');
    const serversByCommit = servers.groupBy(server => server.get('detailsByEnv').get(environmentId).get('commit'));
    if(serversByCommit.count() == 1) {
        const commit = serversByCommit.keySeq().first();
        if(commit) {
            return <span className="text-success">None ({commit.substring(0, 8)} deployed)</span>;
        } else {
            return <span>Could not get release information for any server</span>;
        }
    }
    return <ul className="list-unstyled">
        {serversByCommit.map((servers, commit) => {
            const serverList = servers.map(server => server.get('name')).toList().toJS().join(', ');
            if(commit) {
                return <li key={commit}>Commit {commit.substring(0, 8)} deployed on {serverList}</li>;
            } else {
                return <li key={commit}>No release information for {serverList}</li>;
            }
        }).toList()}
    </ul>;
};
