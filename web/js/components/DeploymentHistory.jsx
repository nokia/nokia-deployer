//Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).
import React from 'react';
import { connect } from 'react-redux';
import ImmutablePropTypes from 'react-immutable-proptypes';
import {Link} from 'react-router';
import PureRenderMixin from 'react-addons-pure-render-mixin';
import DeploymentList from './DeploymentList.jsx';
import * as Actions from '../Actions.js';

const DeploymentHistory = React.createClass({
    mixins: [PureRenderMixin],
    fetchData(repositoryId, repositoryName) {
        this.props.dispatch(Actions.loadRepository(repositoryId));
        this.props.dispatch(Actions.loadEnvironments(repositoryId));
        if(repositoryName) {
            this.props.dispatch(Actions.loadDeploymentHistory(repositoryName));
        }
    },
    componentWillMount() {
        this.fetchData(this.props.repositoryId, this.props.repositoryName);
    },
    componentWillReceiveProps(newProps) {
        if(this.props.repositoryId != newProps.repositoryId || this.props.repositoryName != newProps.repositoryName) {
            this.fetchData(newProps.repositoryId, newProps.repositoryName);
        }
    },
    render() {
        return (
            <div>
                <h3>Deployment history for {this.props.repositoryName}</h3>
                <p><Link to={`/repositories/${this.props.repositoryId}`} activeClassName="active">Repository details</Link></p>
                <DeploymentList deployments={this.props.deployments} />
            </div>
        );
    }
});

export const DeploymentHistoryHandler = connect(
    (state, {params}) => {
        const repositoryId = parseInt(params.id, 10);
        const repositoryName = state.getIn(['repositoriesById', repositoryId, 'name']);
        const environmentsId = state.get('environmentsById').
            filter(env => env.get('repositoryId') == repositoryId).
            toList().
            map(env => env.get('id'));
        const deployments = state.get('deploymentsById').
            filter(deployment => environmentsId.includes(deployment.get('environment_id')))
            .toList();
        return {
            deployments,
            repositoryName,
            repositoryId
        }
    }
)(DeploymentHistory);
