//Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).
import React from 'react';
import { connect } from 'react-redux';
import ImmutablePropTypes from 'react-immutable-proptypes';
import PureRenderMixin from 'react-addons-pure-render-mixin';
import DeploymentList from './DeploymentList.jsx';
import * as Actions from '../Actions';
import Immutable from 'immutable';

const RecentDeployments = React.createClass({
    mixins: [PureRenderMixin],
    propTypes: {
        deploymentsById: ImmutablePropTypes.mapOf(
            ImmutablePropTypes.contains({
                status: React.PropTypes.oneOf(["QUEUED", "INIT", "PRE_DEPLOY", "DEPLOY", "POST_DEPLOY", "COMPLETE", "FAILED"])
            })
        ),
        dispatch: React.PropTypes.func.isRequired
    },
    getDefaultProps() {
        return {
            deploymentsById: Immutable.Map()
        };
    },
    componentWillMount() {
        this.props.dispatch(Actions.loadRecentDeployments());
    },
    render() {
        const sorted = this.props.deploymentsById.sort((d1, d2) => d2.get('date_start_deploy') - d1.get('date_start_deploy')).toList();
        const pending = sorted.filter(deployment => deployment.get('status') != "FAILED" && deployment.get('status') != "COMPLETE").take(20);
        const failed = sorted.filter(deployment => deployment.get('status') == "FAILED").take(5);
        return <div>
            <h2>Recent deployment activity</h2>
            <h3>Pending deployments</h3>
            {pending.size > 0 ? <DeploymentList deployments={pending} displayRepositoryName={true} /> : <p>No deployment currently in progress.</p>}
            <h3>Last failed deployments</h3>
            <DeploymentList deployments={failed} displayRepositoryName={true} />
            <h3>Recent activity</h3>
            <DeploymentList deployments={sorted} displayRepositoryName={true} />
        </div>;
    }
});

const ReduxRecentDeployments = connect(state => ({
    deploymentsById: state.get('deploymentsById')
}))(RecentDeployments);

export default ReduxRecentDeployments;
