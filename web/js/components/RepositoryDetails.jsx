//Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).
import React from 'react';
import ImmutablePropTypes from 'react-immutable-proptypes';
import { connect } from 'react-redux';
import CommitSelector from './CommitSelector.jsx';
import * as Actions from '../Actions';
import {EnvironmentDescriptionHandler} from './EnvironmentDescription.jsx';
import PureRenderMixin from 'react-addons-pure-render-mixin';
import {Link} from 'react-router';

const RepositoryDetails = React.createClass({
    mixins: [PureRenderMixin],
    contextTypes: {
        user: ImmutablePropTypes.contains({
            isSuperAdmin: React.PropTypes.bool.isRequired
        })
    },
    propTypes: {
        dispatch: React.PropTypes.func.isRequired,
        environmentsById: ImmutablePropTypes.mapOf(
            ImmutablePropTypes.contains({
                id: React.PropTypes.number.isRequired,
                name: React.PropTypes.string.isRequired,
                repositoryId: React.PropTypes.number.isRequired,
                autoDeploy: React.PropTypes.bool.isRequired,
                deployBranch: React.PropTypes.string.isRequired,
                envOrder: React.PropTypes.number.isRequired,
                syncOptions: React.PropTypes.string.isRequired,
                remoteUser: React.PropTypes.string.isRequired,
                failDeployOnFailedTests: React.PropTypes.bool.isRequired
            }).isRequired
        ).isRequired,
        repositoriesById: ImmutablePropTypes.mapOf(
            ImmutablePropTypes.contains({
                id: React.PropTypes.number.isRequired,
                name: React.PropTypes.string.isRequired,
                deployMethod: React.PropTypes.string.isRequired,
                notifyOwnersMails: ImmutablePropTypes.listOf(React.PropTypes.string),
                environmentsId: ImmutablePropTypes.listOf(React.PropTypes.number).isRequired
            }).isRequired
        ).isRequired,
        clustersById: ImmutablePropTypes.mapOf(
            ImmutablePropTypes.contains({
                id: React.PropTypes.number.isRequired,
                name: React.PropTypes.string.isRequired,
                haproxyHost: React.PropTypes.string,
                servers: ImmutablePropTypes.listOf(
                    ImmutablePropTypes.contains({
                        haproxyKey: React.PropTypes.string,
                        serverId: React.PropTypes.number.isRequired
                    })
                ).isRequired
            })
        ).isRequired,
        serversById: ImmutablePropTypes.mapOf(
            ImmutablePropTypes.contains({
                id: React.PropTypes.number.isRequired,
                name: React.PropTypes.string.isRequired
            })
        ).isRequired,
        deploymentsById: ImmutablePropTypes.mapOf(
            ImmutablePropTypes.contains({
                id: React.PropTypes.number.isRequired,
                status: React.PropTypes.oneOf(['QUEUED', 'INIT', 'PRE_DEPLOY', 'DEPLOY', 'POST_DEPLOY', 'COMPLETE', 'FAILED']),
                log_entries: ImmutablePropTypes.listOf(
                    ImmutablePropTypes.contains({
                        severity: React.PropTypes.oneOf(['info', 'warn', 'error']),
                        message: React.PropTypes.string
                    }).isRequired
                ),
                environment_id: React.PropTypes.number,
                date_start_deploy: React.PropTypes.object
            })
        ).isRequired
    },
    updateDetails(repositoryId, repository) {
        const that = this;
        if(repository == null) {
            repository = this.props.repositoriesById.get(repositoryId);
        }
        if(repository == null) {
            return;
        }
        that.props.dispatch(Actions.loadEnvironments(repository.get('id')));
    },
    componentDidMount() {
        this.updateDetails(parseInt(this.props.params.id, 10));
    },
    componentWillReceiveProps(newProps, nextContext) {
        // test if we are displaying a new repo
        const newRepoId = parseInt(newProps.params.id, 10);
        if(newProps.params.id != this.props.params.id) {
            this.updateDetails(newRepoId);
            return;
        }
        // test if the repo we are displaying has changed (beware of infinite update loops!)
        const oldRepo = this.props.repositoriesById.get(newRepoId);
        const newRepo = newProps.repositoriesById.get(newRepoId);
        if(oldRepo == null && newRepo != null) {
            this.updateDetails(newRepoId, newRepo);
            return;
        }
        if(nextContext.user !== this.context.user) {
            this.updateDetails(newRepoId);
            return;
        }
    },
    render() {
        const that = this;
        const id = parseInt(this.props.params.id, 10);
        const repository = this.props.repositoriesById.get(id);
        if(repository == null) {
            return <h3>This repository does not exist</h3>;
        }
        // TODO: remove that, use a separate RepositoryDetailsHandler component instead
        const environmentIds = repository.get('environmentsId');
        const environments = environmentIds.map(environmentId => that.props.environmentsById.get(environmentId)).
            filter(environment => environment).
            sort((e1, e2) => {
                return e1.get('envOrder') - e2.get('envOrder');
            });

        return (
            <div>
                <h2>{repository.get('name')}</h2>
                <div className="row">
                    <div className="col-md-4">
                        <DetailsBlock
                            repositoryId={repository.get('id')}
                            deployMethod={repository.get('deployMethod')}
                            gitServer={repository.get('gitServer')}
                            notifyOwnersMails={repository.get('notifyOwnersMails')}
                            isSuperAdmin={this.context.user && this.context.user.get('isSuperAdmin')} />
                    </div>
                    <div className="col-md-8">
                        <BranchesBlock
                            environments={environments.filter(env => env).
                                groupBy(environment => environment.get('deployBranch')).
                                map(environments => environments.first())}
                            onFetchClicked={this.onFetchClicked} />
                    </div>
                </div>
                { environments == null || environments.size == 0 ?
                    (
                    <div className="row">
                        <div className="col-md-12">
                            <h2>Environments</h2>
                            <p>No environment is defined yet for this repository.</p>
                        </div>
                    </div>
                    )
                :
                    (
                    <div className="row">
                        <div className="col-md-12">
                            <h2>Environments</h2>
                                {environments.map((environment, index) =>
                                    <EnvironmentDescriptionHandler key={environment.get('id')} environmentId={environment.get('id')}/>)
                                }

                        </div>
                    </div>
                    )
                }
            </div>
        );
    },
    onFetchClicked() {
        const id = parseInt(this.props.params.id, 10);
        const repository = this.props.repositoriesById.get(id);
        if(repository == null) {
            return;
        }
        const that = this;
        const environments = repository.get('environmentsId').map(envId => that.props.environmentsById.get(envId)).filter(env => env);
        environments.groupBy(environment => environment.get('deployBranch')).map((environments, branch) => {
            that.props.dispatch(Actions.updateCommits(repository.get('name'), branch));
        });
        this.props.dispatch(Actions.addAlert('SUCCESS', "Request sent. The commit list will be updated in a short moment."));
    }
});


const DetailsBlock = ({repositoryId, deployMethod, gitServer, notifyOwnersMails, isSuperAdmin}) =>
    <div>
        <h2>Details</h2>
        <table className="table table-condensed">
            <tbody>
                <tr>
                    <th><span className="glyphicon glyphicon-tasks"></span> Deployment method</th>
                    <td>{deployMethod}</td>
                </tr>
                <tr>
                    <th><span className="glyphicon glyphicon-hdd"></span> Git server</th>
                    <td>{gitServer}</td>
                </tr>
                <tr>
                    <th><span className="glyphicon glyphicon-inbox"></span> Send mails to</th>
                    <td>{notifyOwnersMails.join(', ')}</td>
                </tr>
            </tbody>
        </table>
        <Link activeClassName="active" to={`/repositories/${repositoryId}/deployments`}>deployment history</Link>
        {isSuperAdmin ? <span> - <Link to={`/admin/repositories/${repositoryId}/edit`}>edit</Link> </span> : null}
    </div>


const BranchesBlock = ({environments, onFetchClicked}) =>
    <div>
        <h2>Branches</h2>
        <div className="row">
            {environments.map(environment => 
                <div key={environment.get('deployBranch')}>
                    <div className="col-md-2">
                        <b>{environment.get('deployBranch')}</b>
                    </div>
                    <div className="col-md-10">
                        { 
                            environment.get('commits') && environment.get('commits').get('status') == 'SUCCESS' ?
                                <CommitSelector commits={environment.get('commits').get('list')} />
                                :
                                <p>Loading...</p>
                        }
                    </div>
                </div>
            ).toList()}
        </div>
        <button className="btn btn-default btn-sm" onClick={onFetchClicked}>Force update</button>
    </div>


const ReduxRepositoryDetails = connect()(RepositoryDetails);

export default ReduxRepositoryDetails;
