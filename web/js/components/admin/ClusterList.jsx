//Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).
import React from 'react';
import { connect } from 'react-redux';
import ImmutablePropTypes from 'react-immutable-proptypes';
import PureRenderMixin from 'react-addons-pure-render-mixin';
import * as Actions from '../../Actions';
import ClusterForm from './forms/ClusterForm.jsx';
import {Link} from 'react-router';
import Immutable from 'immutable';
import ConfirmationDialog from '../lib/ConfirmationDialog.jsx';

const ClusterList = React.createClass({
    mixins: [PureRenderMixin],
    contextTypes: {
        user: React.PropTypes.object
    },
    propTypes: {
        serversById: ImmutablePropTypes.mapOf(
            ImmutablePropTypes.contains({
                id: React.PropTypes.number.isRequired,
                name: React.PropTypes.string.isRequired
            })
        ),
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
        ),
        dispatch: React.PropTypes.func.isRequired
    },
    fetchData() {
        this.props.dispatch(Actions.loadClusterList());
        // Some servers may not belong to any cluster, so we need a separate request
        this.props.dispatch(Actions.loadServerList());
    },
    getDefaultProps() {
        return {
            serversById: Immutable.Map()
        };
    },
    componentWillMount() {
        this.fetchData();
    },
    componentWillReceiveProps(nextProps, nextContext) {
        if(nextContext.user !== this.context.user) {
            this.fetchData();
        }
    },
    render() {
        const that = this;
        if(this.props.children) {
            if(!this.props.serversById) {
                return <h2>Loading servers...</h2>;
            }
            const clusterId = parseInt(this.props.params.id, 10);
            const cluster = this.props.clustersById.get(clusterId);
            if(!cluster) {
                return <h2>This cluster does not exist.</h2>;
            }
            return React.cloneElement(this.props.children, {cluster, dispatch: this.props.dispatch, serversById: this.props.serversById});
        }
        return (
            <div>
                <h2>Clusters</h2>
                <h3>New Cluster</h3>
                <ClusterForm serversById={that.props.serversById} onSubmit={that.addCluster} />
                <h3>Cluster List</h3>
                <table className="table table-condensed table-striped">
                    <thead>
                        <tr>
                            <td>ID</td>
                            <td>Name</td>
                            <td>Servers</td>
                            <td>HAProxy Host</td>
                            <td>Actions</td>
                        </tr>
                    </thead>
                    <tbody>
                        {this.props.clustersById.sort((c1, c2) => c1.get('id') - c2.get('id')).map(cluster => <tr key={cluster.get('id')}>
                            <td>{cluster.get('id')}</td>
                            <td>{cluster.get('name')}</td>
                            <td>
                                <ul className="list-unstyled">
                                {cluster.get('servers').map(serverInfo => {
                                    const haproxyKey = serverInfo.get('haproxyKey') ? `(HAProxy: ${serverInfo.get('haproxyKey')})` : "";
                                    const server = that.props.serversById.get(serverInfo.get('serverId'));
                                    if(!server) {
                                        return [<li key={serverInfo.get('serverId')}>loading...</li>, "zzz"];
                                    }
                                    const name = server.get('name');
                                    return [<li key={server.get('id')}>{name} {haproxyKey}</li>, name];
                                }).sort((s1, s2) => s1[1].localeCompare(s2[1])).map(s => s[0])}
                                </ul>
                            </td>
                            <td>{cluster.get('haproxyHost') ? cluster.get('haproxyHost') : "none"}</td>
                            <td>
                                <div className="btn-group">
                                    <Link type="button" className="btn btn-sm btn-default" to={`/admin/clusters/${cluster.get('id')}/edit`}>Edit</Link>
                                    <button type="button" className="btn btn-sm btn-danger" onClick={that.deleteCluster(cluster)}>Delete</button>
                                </div>
                            </td>
                        </tr>).toList()}
                    </tbody>
                </table>
                <ConfirmationDialog ref="confirmationDialog" />
            </div>
        );
    },
    addCluster(name, haproxyHost, haproxy_server) {
        this.props.dispatch(Actions.addCluster({name, haproxyHost, servers: haproxy_server}));
    },
    deleteCluster(cluster) {
        const that = this;
        return () => {
            that.refs.confirmationDialog.show(
                <span>Delete the cluster <strong>{cluster.get("name")}</strong>? This action can not be undone.</span>,
                () => {
                    that.props.dispatch(Actions.deleteCluster(cluster.get("id")));
                }
            );
        };
    }
});

const ReduxClusterList = connect(state => ({
    clustersById: state.get('clustersById'),
    serversById: state.get('serversById')
}))(ClusterList);

export default ReduxClusterList;
