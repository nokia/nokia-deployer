//Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).
import React from 'react';
import ImmutablePropTypes from 'react-immutable-proptypes';
import Immutable from 'immutable';
import * as Actions from '../../Actions';
import { connect } from 'react-redux';
import {Link} from 'react-router';
import PureRenderMixin from 'react-addons-pure-render-mixin';

const RepositoryList = React.createClass({
    mixins: [PureRenderMixin],
    propTypes: {
        repositoriesById: ImmutablePropTypes.mapOf(
            ImmutablePropTypes.contains({
                id: React.PropTypes.number.isRequired,
                name: React.PropTypes.string.isRequired,
                environmentsId: ImmutablePropTypes.listOf(React.PropTypes.number).isRequired
            })
        ).isRequired,
        clustersById: ImmutablePropTypes.mapOf(
            ImmutablePropTypes.contains({
                id: React.PropTypes.number.isRequired,
                name: React.PropTypes.string.isRequired,
                servers: React.PropTypes.instanceOf(Immutable.List)
            })
        ),
        dispatch: React.PropTypes.func.isRequired
    },
    getDefaultProps() {
        return {
            repositoriesById: Immutable.Map(),
            environmentsById: Immutable.Map(),
            clustersById: Immutable.Map()
        };
    },
    fetchData() {
        this.props.dispatch(Actions.loadRepositories());
        this.props.dispatch(Actions.loadClusterList());
    },
    componentWillMount() {
        this.fetchData();
    },
    render() {
        const that = this;
        if(that.props.children) {
            if(!this.props.params.id) {
                // just render children
                return React.cloneElement(that.props.children, {dispatch: this.props.dispatch});
            }
            // otherwise, our children need a repository
            const id = parseInt(this.props.params.id, 10);
            const repository = that.props.repositoriesById.get(id);
            if(!repository) {
                return <h2>Loading repository...</h2>;
            }
            return React.cloneElement(that.props.children, {repository, dispatch: this.props.dispatch, environmentsById: this.props.environmentsById, clustersById: this.props.clustersById});
        }
        return (<div>
            <h2>Repositories</h2>
            <p>
                <Link className="btn btn-default" to="/admin/repositories/new">New Repository</Link>
            </p>
            <table className="table table-condensed table-striped">
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Name</th>
                        <th>Git server</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    { that.props.repositoriesById.sort((r1, r2) => r1.get('name').localeCompare(r2.get('name'))).map(repository => <tr key={repository.get('id')}>
                        <td>{repository.get('id')}</td>
                        <td>{repository.get('name')}</td>
                        <td>{repository.get('gitServer')}</td>
                        <td>
                            <div className="btn-group">
                                <Link className="btn btn-sm btn-default" to={`/repositories/${repository.get('id')}`}>View</Link>
                                <Link className="btn btn-sm btn-default" to={`/admin/repositories/${repository.get('id')}/edit`}>Edit</Link>
                                <button className="btn btn-sm btn-danger">Delete</button>
                            </div>
                        </td>
                    </tr>).toList()}
                </tbody>
            </table>
        </div>);
    }
});

const ReduxRepositoryList = connect(state => ({
    repositoriesById: state.get('repositoriesById'),
    environmentsById: state.get('environmentsById'),
    clustersById: state.get('clustersById')
}))(RepositoryList);

export default ReduxRepositoryList;
