//Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).
import React from 'react';
import { connect } from 'react-redux';
import ImmutablePropTypes from 'react-immutable-proptypes';
import * as Actions from '../Actions';
import DeployLogs from './DeployLogs.jsx';
import Immutable from 'immutable';
import PureRenderMixin from 'react-addons-pure-render-mixin';
import WebSockGateway from '../WebSockGateway';

const DeploymentDetails = React.createClass({
    mixins: [PureRenderMixin],
    contextTypes: {
        user: React.PropTypes.object
    },
    propTypes: {
        deploymentsById: ImmutablePropTypes.mapOf(
            ImmutablePropTypes.contains({
                id: React.PropTypes.number.isRequired,
                status: React.PropTypes.oneOf(['QUEUED', 'INIT', 'PRE_DEPLOY', 'DEPLOY', 'POST_DEPLOY', 'COMPLETE', 'FAILED']),
                log_entries: ImmutablePropTypes.listOf(
                    ImmutablePropTypes.contains({
                        severity: React.PropTypes.oneOf(['info', 'warn', 'error']),
                        message: React.PropTypes.string
                    })
                ),
                date_start_deploy: React.PropTypes.object,
                repository_name: React.PropTypes.string.isRequired,
                environment_name: React.PropTypes.string.isRequired
            })
        ),
        dispatch: React.PropTypes.func.isRequired
    },
    fetchDeployIfMissing(id) {
        if(id == null) {
            id = parseInt(this.props.params.id, 10);
        }
        const deployment = this.props.deploymentsById.get(id);
        if(deployment == null) {
            this.props.dispatch(Actions.loadDeployment(id));
        }
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
        this.fetchDeployIfMissing();
        const deployment = this.props.deploymentsById.get(parseInt(this.props.params.id, 10));
        if(deployment != null) {
            this.subscribeToWebsocket(deployment.get('environment_id'));
        }
    },
    componentWillUnmount() {
        const deployment = this.props.deploymentsById.get(parseInt(this.props.params.id, 10));
        if(deployment != null) {
            this.unsubscribeWebsocket(deployment.get('environment_id'));
        }
    },
    componentWillReceiveProps(newProps, newContext) {
        if(this.props.params.id != newProps.params.id || this.context.user !== newContext.user) {
            this.fetchDeployIfMissing(newProps.params.id);
            // TODO: subscribe to the correct environment (w/ websocket)
        }
    },
    render() {
        const deployment = this.props.deploymentsById.get(parseInt(this.props.params.id, 10));
        if(deployment == null) {
            return <h2>This deployment does not exist.</h2>;
        }
        let formattedStatus = null;
        switch(deployment.get('status')) {
        case "COMPLETE":
            formattedStatus = <p className="text-success">OK</p>;
            break;
        case "FAILED":
            formattedStatus = <p className="text-danger">Error</p>;
            break;
        case "QUEUED":
            formattedStatus = <p className="text-warning">Queued</p>;
            break;
        case "INIT":
        case "PRE_DEPLOY":
        case "DEPLOY":
        case "POST_DEPLOY":
            formattedStatus = <p className="text-warning">In progress</p>;
            break;
        default:
            formattedStatus = <p className="text-warning">Unknown</p>;
            break;
        }
        return (
            <div>
                <h2>Deployment {deployment.get('id')}  <small>{deployment.get('repository_name')}/{deployment.get('environment_name')}</small></h2>
                <h4>Status</h4>
                {formattedStatus}
                <p>Started at: {deployment.get('date_start_deploy').local().format('YYYY-MM-DD HH:mm:ss ZZ')}</p>
                {
                    deployment.get('date_end_deploy') ?  <div>
                        <p>Ended at: {deployment.get('date_end_deploy').local().format('YYYY-MM-DD HH:mm:ss ZZ')}</p> 
                        <p>Duration: {deployment.get('date_end_deploy').diff(deployment.get('date_start_deploy'), 'seconds')} seconds</p>
                    </div>
                    : null
                }
                <DeployLogs deployments={Immutable.List([deployment])} scrollOnUpdate={false} limitHeight={false}/>
            </div>
        );
    }
});

const ReduxDeploymentDetails = connect(state => ({
    deploymentsById: state.get('deploymentsById')
}))(DeploymentDetails);

export default ReduxDeploymentDetails;
