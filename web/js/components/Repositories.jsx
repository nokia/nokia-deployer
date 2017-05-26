//Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).
import React from 'react';
import RepositorySelector from './RepositorySelector.jsx';
import ImmutablePropTypes from 'react-immutable-proptypes';
import { connect } from 'react-redux';
import PureRenderMixin from 'react-addons-pure-render-mixin';
import SimpleRepositoryList from './SimpleRepositoryList.jsx';

const Repositories = React.createClass({
    contextTypes: {
        router: React.PropTypes.object.isRequired
    },
    mixins: [PureRenderMixin],
    propTypes: { // incomplete
        repositoriesById: ImmutablePropTypes.mapOf(
            ImmutablePropTypes.contains({
                id: React.PropTypes.number.isRequired,
                name: React.PropTypes.string.isRequired,
                deployMethod: React.PropTypes.string.isRequired,
                gitServer: React.PropTypes.string.isRequired,
                notifyOwnersMails: ImmutablePropTypes.listOf(React.PropTypes.string)
            }).isRequired
        ).isRequired,
        clustersById: React.PropTypes.object.isRequired,
        serversById: React.PropTypes.object.isRequired
    },
    render() {
        if (this.props.children == null) {
            return (
                <div>
                    <RepositorySelector repositories={this.props.repositoriesById.toList()} onRepositorySelected={this.onRepositorySelected}/>
                    <h4>Available repos</h4>
                    <SimpleRepositoryList repositoriesById={this.props.repositoriesById} />
                </div>
            );
        }
        const that = this;
        // TODO: remove that
        const childrenWithProps = React.Children.map(this.props.children, child => React.cloneElement(child, { repositoriesById: that.props.repositoriesById, environmentsById: that.props.environmentsById, clustersById: that.props.clustersById, serversById: that.props.serversById, deploymentsById: that.props.deploymentsById, account: that.props.account}));
        return (
            <div>
                <RepositorySelector repositories={this.props.repositoriesById.toList()} onRepositorySelected={this.onRepositorySelected}/>
                {childrenWithProps}
            </div>
        );
    },
    onRepositorySelected(repository) {
        this.context.router.push(`/repositories/${repository.get('id')}`);
    }
});

const ReduxRepositories = connect(state => ({
    repositoriesById: state.get('repositoriesById'),
    environmentsById: state.get('environmentsById'),
    clustersById: state.get('clustersById'),
    serversById: state.get('serversById'),
    deploymentsById: state.get('deploymentsById'),
    account: state.get('account')
}))(Repositories);

export default ReduxRepositories;
