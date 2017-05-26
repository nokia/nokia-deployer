//Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).
import React from 'react';
import { connect } from 'react-redux';
import {Link} from 'react-router';
import RepositoryForm from './forms/RepositoryForm.jsx';
import PureRenderMixin from 'react-addons-pure-render-mixin';
import ImmutablePropTypes from 'react-immutable-proptypes';
import Immutable from 'immutable';
import * as Actions from '../../Actions';
import EnvironmentForm from './forms/EnvironmentForm.jsx';

const EnvironmentAdd = React.createClass({
    contextTypes: {
        router: React.PropTypes.object.isRequired
    },
    propTypes: {
        repositoryId: React.PropTypes.number.isRequired,
        repository: ImmutablePropTypes.contains({
            'id': React.PropTypes.number.isRequired,
            'name': React.PropTypes.string.isRequired,
            'environmentsId': ImmutablePropTypes.listOf(React.PropTypes.number)
        }).isRequired,
        environmentsById: ImmutablePropTypes.mapOf(
            ImmutablePropTypes.contains({
                'name': React.PropTypes.string.isRequired
            })
        ).isRequired,
        clustersById: ImmutablePropTypes.mapOf(
            ImmutablePropTypes.contains({
                'id': React.PropTypes.number.isRequired,
                'name': React.PropTypes.string.isRequired
            })
        ).isRequired,
        dispatch: React.PropTypes.func.isRequired
    },
    getDefaultProps() {
        return {
            environmentsById: Immutable.Map()
        };
    },
    componentWillMount() {
        this.fetchData(this.props.repositoryId);
    },
    componentWillReceiveProps(newProps, nextContext) {
        if(this.props.repositoryId != newProps.repositoryId || nextContext.user !== this.context.user) {
            this.fetchData(newProps.repositoryId);
        }
    },
    fetchData(repositoryId) {
        this.props.dispatch(Actions.loadEnvironments(repositoryId));
    },
    render() {
	if(!this.props.repository) {
	    return <div>Loading...</div>;
	}
        const that = this;
        return (<div>
            <h2>Repository {this.props.repository.get('name')}: new environment</h2>
            { this.props.repository.get('environmentsId').size > 0 ?
                <p>
                    Environments currently defined in this repository: { this.props.repository.get('environmentsId').map(environmentId => {
                        const env = that.props.environmentsById.get(environmentId);
                        if(env) {
                            return env.get('name');
                        }
                        return "loading";
                    }).join(', ')}
                </p>
                :
                    <p>No environments are defined yet for this repository.</p>
            }
            <p>
                <Link to={`/admin/repositories/${this.props.repository.get('id')}/edit`}>back to repository</Link>
            </p>
            <EnvironmentForm onSubmit={this.onSubmit} clustersById={this.props.clustersById} repositoryName={this.props.repository.get('name')}/>
        </div>);
    },
    onSubmit(
        environmentName,
        autoDeploy,
        deployBranch,
        envOrder,
        targetPath,
        remoteUser,
        syncOptions,
        clustersId,
        failDeployOnFailedTests) {
        this.props.dispatch(Actions.addEnvironment(this.props.repository.get('id'), {environmentName, autoDeploy, deployBranch, envOrder, targetPath, remoteUser, syncOptions, clustersId, failDeployOnFailedTests}));
        this.context.router.push(`/admin/repositories/${this.props.repository.get('id')}/edit`);
    }
});

const EnvironmentAddHandler = connect(
    (state, props) => {
	const repositoryId = parseInt(props.params.id, 10);
	return {
	    repositoryId: repositoryId,
	    repository: state.getIn(['repositoriesById', repositoryId]),
	    environmentsById: state.get('environmentsById'),
	    clustersById: state.get('clustersById')
	}
})(EnvironmentAdd);

export default EnvironmentAddHandler;
