//Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).
import React from 'react';
import ImmutablePropTypes from 'react-immutable-proptypes';
import PureRenderMixin from 'react-addons-pure-render-mixin';
import FuzzyListForm from '../../lib/FuzzyListForm.jsx';
import LinkedStateMixin from 'react-addons-linked-state-mixin';
import Immutable from 'immutable';

const EnvironmentForm = React.createClass({
    mixins: [PureRenderMixin, LinkedStateMixin],
    propTypes: {
        repositoryName: React.PropTypes.string.isRequired,
        environment: ImmutablePropTypes.contains({
            name: React.PropTypes.isRequired,
            autoDeploy: React.PropTypes.bool.isRequired,
            clustersId: ImmutablePropTypes.listOf(React.PropTypes.number.isRequired),
            deployBranch: React.PropTypes.string.isRequired,
            envOrder: React.PropTypes.number.isRequired,
            failDeployOnFailedTests: React.PropTypes.bool.isRequired,
            remoteUser: React.PropTypes.string.isRequired,
            targetPath: React.PropTypes.string.isRequired,
            syncOptions: React.PropTypes.string.isRequired
        }),
        clustersById: ImmutablePropTypes.mapOf(
            ImmutablePropTypes.contains({
                name: React.PropTypes.string.isRequired
            })
        ).isRequired,
        onSubmit: React.PropTypes.func.isRequired
    },
    getInitialState() {
        if(this.props.environment) {
            const env = this.props.environment;
            return {
                environmentName: env.get('name'),
                autoDeploy: env.get('autoDeploy'),
                deployBranch: env.get('deployBranch'),
                envOrder: env.get('envOrder'),
                failDeployOnFailedTests: env.get('failDeployOnFailedTests'),
                targetPath: env.get('targetPath'),
                remoteUser: env.get('remoteUser'),
                syncOptions: env.get('syncOptions'),
                clustersId: env.get('clustersId').toArray(),
            };
        }
        return {
            environmentName: "dev",
            autoDeploy: false,
            deployBranch: "master",
            envOrder: 0,
            failDeployOnFailedTests: false,
            targetPath: process.env.DEFAULT_TARGET_PATH + this.props.repositoryName,
            remoteUser: "scaleweb",
            syncOptions: "",
            clustersId: []
        };
    },
    reset() {
        this.setState(this.getInitialState());
        this.refs.clustersSelector.reset();
    },
    onClustersChanged(clusters) {
        this.setState({clustersId: clusters.map(cluster => cluster.get('id'))});
    },
    render() {
        const that = this;
        let initialClusters = Immutable.List();
        if(this.props.environment) {
            initialClusters = this.props.environment.get('clustersId').map(clusterId => that.props.clustersById.get(clusterId));
        }
	const displayTargetPathWarning = !this.state.targetPath.endsWith(this.props.repositoryName);
        return (
            <form className="form-horizontal">
                <div className="form-group">
                    <label className="col-sm-2 control-label">Name</label>
                    <div className="col-sm-5"><input className="form-control" type="text" placeholder="prod" valueLink={this.linkState('environmentName')}/></div>
                </div>
                <div className="form-group">
                    <label className="col-sm-2 control-label">Branch to deploy</label>
                    <div className="col-sm-5"><input className="form-control" type="text" placeholder="prod" valueLink={this.linkState("deployBranch")}/></div>
                </div>
                <div className="form-group">
                    <div className="col-sm-offset-2 col-sm-5">
                        <div className="checkbox row">
                            <label>
                                <input type="checkbox" checkedLink={this.linkState('autoDeploy')}/> Automatically deployed
                            </label>
                        </div>
                    </div>
                </div>
                <div className={"form-group" + (displayTargetPathWarning ? " has-warning" : "")}>
                    <label className="col-sm-2 control-label">Target path</label>
                    <div className="col-sm-5"><input className="form-control" type="text" placeholder="/home/scaleweb/websites" valueLink={this.linkState('targetPath')} /></div>
		    { displayTargetPathWarning ?
			<span className="col-sm-5 help-block">The last component of this path does not match the repository name. This is a non standard setup, double-check your path.</span>
			: null
		    }
                </div>
                <div className="form-group">
                    <label className="col-sm-2 control-label">Remote User</label>
                    <div className="col-sm-5"><input className="form-control" type="text" placeholder="scaleweb" valueLink={this.linkState('remoteUser')}/></div>
                </div>
                <div className="form-group">
                    <label className="col-sm-2 control-label">RSync Options</label>
                    <div className="col-sm-5"><input className="form-control" type="text" placeholder="-az --delete" valueLink={this.linkState('syncOptions')}/></div>
                </div>
                <div className="form-group">
                    <label className="col-sm-2 control-label">Environment Order</label>
                    <div className="col-sm-5"><input className="form-control" type="number" placeholder="0" valueLink={this.linkState('envOrder')}/></div>
                </div>
                <div className="form-group">
                    <div className="col-sm-offset-2 col-sm-5">
                        <div className="checkbox row">
                            <label>
                                <input type="checkbox" checkedLink={this.linkState('failDeployOnFailedTests')}/> Abort deployment on failed tests
                            </label>
                        </div>
                    </div>
                </div>
                <div className="form-group">
                    <label className="col-sm-2 control-label">Clusters</label>
                    <div className="col-sm-5">
                        <FuzzyListForm ref="clustersSelector"
                            onChange={this.onClustersChanged}
                            elements={this.props.clustersById.toList()}
                            initialElements={initialClusters}
                            renderElement={
                                cluster => {
                                    if(!cluster) {
                                        return <span className="text-muted">Loading...</span>;
                                    }
                                    const nbServers = cluster.get('servers').size;
                                    let ending = " servers)";
                                    if(nbServers <= 1) {
                                        ending = " server)";
                                    }
                                    return <span>{cluster.get('name')} <span className="text-muted text-nowrap">({cluster.get('servers').size}{ending}</span></span>;
                                }
                            }
                            compareWith={cluster => cluster.get('name')}
                            placeholder="webservers_prod"
                        />
                    </div>
                </div>
                <div className="form-group">
                    <div className="col-sm-5 col-sm-offset-2">
                        <button type="button" onClick={this.onSubmit} className="btn btn-default">Submit</button>
                    </div>
                </div>
            </form>
        );
    },
    onSubmit() {
        this.props.onSubmit(this.state.environmentName, this.state.autoDeploy, this.state.deployBranch, this.state.envOrder, this.state.targetPath, this.state.remoteUser, this.state.syncOptions, this.state.clustersId, this.state.failDeployOnFailedTests);
    }
});

export default EnvironmentForm;
