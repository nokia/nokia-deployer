//Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).
import React from 'react';
import {connect} from 'react-redux';
import CommitSelector from './CommitSelector.jsx';
import * as Actions from '../Actions';
import ImmutablePropTypes from 'react-immutable-proptypes';
import PureRenderMixin from 'react-addons-pure-render-mixin';
import debounce from 'debounce';
import {List, Map} from 'immutable';


const ServerActions = React.createClass({
    mixins: [PureRenderMixin],
      registerCommitSelector(el) {
        this.commitSelector = el;
    },
    contextTypes: {
        router: React.PropTypes.object.isRequired
    },
    onDeployButtonClicked() {
        if(!this.props.deploymentAlreadyInProgress) {
            const selectedCommit = this.commitSelector.getSelectedCommit();
            if(!selectedCommit) {
                return;
            }
            this.props.dispatch(
                Actions.deploy(
                    this.props.environment.get('id'),
                    selectedCommit,
                    this.props.environment.get('deployBranch'),
                    null,
                    this.props.server.get('id')
                )
            );
        }
    },
    componentWillMount() {
        this.onDeployButtonClicked = debounce(this.onDeployButtonClicked, 3000, true);
    },
    render() {
        // TODO: factorize (also done in EnvironmentDescription)
        const deployableCommits = this.props.environment.getIn(['commits', 'list'], List())
            .filter(commit => commit.get('deployable'));
        let className = "btn btn-sm btn-warning";
        let message = "Deploy";
        if(this.props.deploymentAlreadyInProgress) {
            className += " btn-disabled";
            message = "In progress...";
        }
        return (
            <form className="form-horizontal">
            { this.props.environment.get('deployAuthorized') ?
                <div className="form-group">
                    <div className="col-sm-8">
                        <CommitSelector
                            commits={deployableCommits}
                            ref={this.registerCommitSelector}
                            currentCommit={this.props.server.getIn(['detailsByEnv', this.props.environment.get('id'), 'commit'])}
                        />
                    </div>
                    <div className="col-sm-4">
			<div className="btn-group">
                            <button className="btn btn-default btn-sm" type="button" onClick={this.onDiffButtonClicked}>Diff</button>
                            <button className={className} type="button" onClick={this.onDeployButtonClicked}>{message}</button>
                        </div>
                    </div>
                </div>
                :
                <div className="form-group">
                    <div className="col-sm-12">
                        <CommitSelector
                            commits={deployableCommits}
                            ref={this.registerCommitSelector}
                            currentCommit={this.props.server.getIn(['detailsByEnv', this.props.environment.get('id'), 'commit'])}
                        />
                    </div>
                </div>
            }
            </form>
        );
    },
    onDiffButtonClicked(e) {
        e.preventDefault();
        const from =  this.props.server.getIn(['detailsByEnv', this.props.environment.get('id'), 'commit']);
        const to =  this.commitSelector.getSelectedCommit();
        const url = `/repositories/${this.props.environment.get('repositoryId')}/diff/${from}/${to}`;
        const win = window.open(url, '_blank');
        win.focus();
    }
});

// TODO: this is also done in EnvironmentDescription, factor out these selectors
// TODO: use redux bindActionCreators to reduce the state slice this component needs to be aware of
// Warning: makes no attempt to fetch data if the environment or server is not provided in the state
// Also requires a repositoryId in props
export const ServerActionsHandler = connect(
    (state, {environmentId, serverId}) => {
        const environment = state.getIn(['environmentsById', environmentId]);
        const server = state.getIn(['serversById', serverId]);
        const deploymentAlreadyInProgress = !!state.get('deploymentsById', Map()).
            find(
                deployment => (
                    deployment.get('environment_id') == environmentId && !(['COMPLETE', 'FAILED'].includes(deployment.get('status')))
                ),
                null,
                false);
        return {
            environment,
            server,
            deploymentAlreadyInProgress
        }
    }
)(ServerActions);
