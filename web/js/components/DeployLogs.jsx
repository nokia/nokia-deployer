//Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).
import React from 'react';
import ReactDOM from 'react-dom';
import PureRenderMixin from 'react-addons-pure-render-mixin';
import ImmutablePropTypes from 'react-immutable-proptypes';
import Immutable from 'immutable';
import {Link} from 'react-router';

const DeployLogs = React.createClass({
    mixins: [PureRenderMixin],
    propTypes: {
        deployments: ImmutablePropTypes.listOf(
            ImmutablePropTypes.contains({
                id: React.PropTypes.number.isRequired,
                status: React.PropTypes.oneOf(['QUEUED', 'INIT', 'PRE_DEPLOY', 'DEPLOY', 'POST_DEPLOY', 'COMPLETE', 'FAILED']),
                log_entries: ImmutablePropTypes.listOf(
                    ImmutablePropTypes.contains({
                        severity: React.PropTypes.oneOf(['info', 'warn', 'error']),
                        message: React.PropTypes.string
                    })
                ),
                date_start_deploy: React.PropTypes.object
            })
        ),
        scrollOnUpdate: React.PropTypes.bool.isRequired,
        limitHeight: React.PropTypes.bool.isRequired
    },
    getDefaultProps() {
        return {
            scrollOnUpdate: true,
            limitHeight: true,
            deployments: Immutable.List()
        };
    },
    getInitialState() {
        let selectedDeploymentId = -1;
        if(this.props.deployments.size > 0) {
            selectedDeploymentId = this.sortDeploymentsByDate().first().get('id');
        }
        return {
            selectedDeploymentId
        };
    },
    sortDeploymentsByDate(deployments) {
        if(deployments == null) {
            deployments = this.props.deployments;
        }
        return deployments.sort((d1, d2) => d2.get('date_start_deploy').isAfter(d1.get('date_start_deploy')));
    },
    componentWillReceiveProps(newProps) {
        // if there is a new deployment (more recent), automatically switch to its tab
        if(this.props.deployments == newProps.deployments) {
            return;
        }
        const newMostRecent = this.sortDeploymentsByDate(newProps.deployments).first();
        if(!newMostRecent) {
            return;
        }
        if(this.props.deployments.size == 0) {
            this.setState({selectedDeploymentId: newMostRecent.get('id')});
            return;
        }
        if (this.sortDeploymentsByDate().first().get('id') != newMostRecent.get('id')) {
            this.setState({selectedDeploymentId: newMostRecent.get('id')});
        }
    },
    render() {
        const that = this;
        let deploymentsToDisplay = Immutable.List();
        if(this.props.deployments) {
            deploymentsToDisplay = this.sortDeploymentsByDate().take(5);
        }
        // remove deployments older than 1 hour in the parent component, where applicable
        if(deploymentsToDisplay.size == 0) {
            return null;
        }
        const selectedDeployment = deploymentsToDisplay.find(deployment => deployment.get('id') == that.state.selectedDeploymentId);
        let closingDiv = null;
        if(selectedDeployment) {
            if (selectedDeployment.get('status') === 'FAILED') {
                closingDiv = <p key="deploy-failed" className="text-danger"><strong>Deployment failed</strong></p>;
            } else if (selectedDeployment.get('status') === 'COMPLETE') {
                closingDiv = <p key="deploy-complete" className="text-success"><strong>Deployment complete</strong></p>;
            } else if(selectedDeployment.get('status') === 'QUEUED') {
                closingDiv = <p key="deploy-queued"><strong>Deployment queued...</strong></p>;
            } else {
                closingDiv = <p key="ellipsis" className="ellipsis"><span>.</span><span>.</span><span>.</span></p>;
            }
        }
        const tabClassName = this.props.limitHeight ? "limit-height deploy-logs" : "deploy-logs";
        return (
            <div className="row">
                <div className="col-md-12">
                    { deploymentsToDisplay.size > 1 ? 
                        <ul className="nav nav-tabs">
                            { deploymentsToDisplay.reverse().map(deployment => {
                                const inProgress = (deployment.get('status') != 'COMPLETE' && deployment.get('status') != "FAILED");
                                const className = deployment.get('id') == that.state.selectedDeploymentId ? "active" : "";
                                return <li onClick={that.onLogTabClicked(deployment.get('id'))} className={className} key={deployment.get('id')}><a href="#">
                                        <span className="glyphicon glyphicon-console"></span> {deployment.get('id')} { inProgress ? <span key="ellipsis" className="ellipsis"><span>.</span><span>.</span><span>.</span></span> : null }
                                        </a></li>;
                            })}
                        </ul>
                    : null
                    }
                    { selectedDeployment ?
                        <div className={tabClassName} ref="deployLogs">
                            <h5 key="deploy-started">Deployment started (<Link to={`/deployments/${selectedDeployment.get('id')}`}>ID {selectedDeployment.get('id')}</Link>)</h5>
                            {selectedDeployment.get('log_entries').
                                map((entry, index) => <LogEntry key={index} entry={entry}/>)
                            }
                            {closingDiv}
                        </div>
                    :
                        null
                    }
                    </div>
            </div>
        );
    },
    onLogTabClicked(deployId) {
        const that = this;
        return e => {
            e.preventDefault();
            that.setState({selectedDeploymentId: deployId});
        };
    },
    scrollToBottom() {
        const node = ReactDOM.findDOMNode(this.refs.deployLogs);
        if(!node) {
            return;
        }
        node.scrollTop = node.scrollHeight;
    },
    componentDidUpdate() {
        if(!this.props.scrollOnUpdate) {
            return;
        }
        if(this.props.deployments.size <= 1) {
            this.scrollToBottom();
            return;
        }
        if(this.sortDeploymentsByDate().first().get('id') == this.state.selectedDeploymentId) {
            this.scrollToBottom();
        }
    }
});

const formatLogEntry = entry => `[${entry.get('date').local().format('HH:mm:ss')}] ${entry.get('message')}`

const LogEntry = ({entry}) => {
    let className = null;
    switch(entry.get('severity')) {
    case "warn":
        className = "text-warning";
        break;
    case "error":
        className = "text-danger";
        break;
    case "info":  // fall-through
    default:
        className= "";
    }
    if (entry.get('message').substring(0, 6) == "Step: ") {
        return (
            <p className={className}><strong>{formatLogEntry(entry)}</strong></p>
            );
    }
    return <p className={className}>{formatLogEntry(entry)}</p>;
}

export default DeployLogs;
