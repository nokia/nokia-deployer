//Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).
import RepositoryForm from './forms/RepositoryForm.jsx';
import PureRenderMixin from 'react-addons-pure-render-mixin';
import ImmutablePropTypes from 'react-immutable-proptypes';
import Immutable from 'immutable';
import React from 'react';
import * as Actions from '../../Actions';
import {Link} from 'react-router';
import EnvironmentForm from './forms/EnvironmentForm.jsx';
import ConfirmationDialog from '../lib/ConfirmationDialog.jsx';

const RepositoryEdit = React.createClass({
    mixins: [PureRenderMixin],
    contextTypes: {
        user: React.PropTypes.object.isRequired
    },
    propTypes: {
        repository: ImmutablePropTypes.contains({
            id: React.PropTypes.number.isRequired,
            environmentsId: ImmutablePropTypes.listOf(React.PropTypes.number.isRequired).isRequired,
        }).isRequired,
        // will take care of fetching environments itself
        environmentsById: ImmutablePropTypes.mapOf(
            ImmutablePropTypes.contains({
                id: React.PropTypes.number.isRequired,
                name: React.PropTypes.string.isRequired,
                // more in EnvironmentForm
            })
        ),
        clustersById: ImmutablePropTypes.mapOf(
            ImmutablePropTypes.contains({
                id: React.PropTypes.number.isRequired,
                name: React.PropTypes.string.isRequired,
                servers: React.PropTypes.instanceOf(Immutable.List)
            })
        ),
        dispatch: React.PropTypes.func.isRequired
    },
    componentWillMount() {
        this.fetchData();
    },
    fetchData(repositoryId) {
        if(!repositoryId) {
            repositoryId = this.props.repository.get('id');
        }
        this.props.dispatch(Actions.loadEnvironments(repositoryId));
    },
    componentWillReceiveProps(nextProps, nextContext) {
        if(this.props.repository.get('id') != nextProps.repository.get('id') || nextContext.user !== this.context.user) {
            this.fetchData(nextProps.repository.get('id'));
        }
    },
    resetRepoForm() {
        this.refs.repositoryForm.reset();
    },
    resetEnvironmentForm(environmentId) {
        const that = this;
        return () => {
            that.refs[`environmentForm${environmentId}`].reset();
        };
    },
    render() {
        const that = this;
        const environments = this.props.repository.get('environmentsId').map(environmentId => that.props.environmentsById.get(environmentId)).sort((e1, e2) => {
            if(e1 == null) {
                return 1;
            }
            if(e2 == null) {
                return -1;
            }
            return e1.get('envOrder') - e2.get('envOrder');
        });
        return (<div>
            <h2>Edit Repository</h2>
            <h3>Repository Details</h3>
            <RepositoryForm onSubmit={this.editRepository} repository={this.props.repository} ref="repositoryForm"/>
            <div className="row">
                <div className="col-sm-5 col-sm-offset-2">
                    <button className="btn btn-sm btn-warning" onClick={this.resetRepoForm}>Reset</button>
                </div>
            </div>
            <p>
                <Link to={`/repositories/${this.props.repository.get('id')}`}>back to detailed view</Link>
            </p>
            <h3>Environments</h3>
            <p> <Link to={`/admin/repositories/${that.props.repository.get('id')}/environments/new`} className="btn btn-default">Add New Environment</Link></p>
            {
                environments.map((environment, index) => {
                    if(environment == null) {
                        return <h5 key={`loading${index}`}>Loading environment....</h5>;
                    }
                    return (
                        <div key={environment.get('id')} className="panel panel-default">
                            <div className="panel-heading"><h5 className="panel-title">{environment.get('name')}</h5></div>
                            <div className="panel-body">
                                <EnvironmentForm
				    environment={environment}
				    clustersById={that.props.clustersById}
				    ref={`environmentForm${environment.get('id')}`}
				    onSubmit={that.editEnvironment(environment)}
				    repositoryName={that.props.repository.get('name')} />
                                <div className="row">
                                    <div className="col-sm-offset-2 col-sm-5 btn-group">
                                        <button className="btn btn-danger" onClick={that.deleteEnvironment(environment)}>Delete</button>
                                        <button className="btn btn-warning" onClick={that.resetEnvironmentForm(environment.get('id'))}>Reset</button>
                                    </div>
                                </div>
                            </div>
                        </div>
                    );
                })
            }
            <ConfirmationDialog ref="confirmationDialog" />
        </div>);
    },
    editRepository(repositoryName, gitServer, deployMethod, notifyOwnersMails) {
        this.props.dispatch(Actions.editRepository(this.props.repository.get('id'), {repositoryName, gitServer, deployMethod, notifyOwnersMails, environmentId: this.props.repository.get('environmentsId').toArray()}));
    },
    editEnvironment(environment) {
        const that = this;
        return (
            environmentName,
            autoDeploy,
            deployBranch,
            envOrder,
            targetPath,
            remoteUser,
            syncOptions,
            clustersId,
            failDeployOnFailedTests) => {
            that.props.dispatch(Actions.editEnvironment(environment.get('id'), {environmentName, autoDeploy, deployBranch, envOrder, targetPath, remoteUser, syncOptions, clustersId, failDeployOnFailedTests}));
        };
    },
    deleteEnvironment(environment) {
        const that = this;
        return () => {
            that.refs.confirmationDialog.show(
                <span>Do you want to delete the environment <strong>{environment.get("name")}</strong>? This action can not be undone.</span>,
                () => {
                    that.props.dispatch(Actions.deleteEnvironment(environment.get("id")));
                }
            );
        };
    }
});

export default RepositoryEdit;
