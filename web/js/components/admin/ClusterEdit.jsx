//Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).
import React from 'react';
import ImmutablePropTypes from 'react-immutable-proptypes';
import PureRenderMixin from 'react-addons-pure-render-mixin';
import {Link} from 'react-router';
import ClusterForm from './forms/ClusterForm.jsx';
import * as Actions from '../../Actions';

const ClusterEdit = React.createClass({
    contextTypes: {
        router: React.PropTypes.object.isRequired
    },
    propTypes: {
        cluster: ImmutablePropTypes.contains({
            id: React.PropTypes.number.isRequired,
            name: React.PropTypes.string.isRequired,
            inventoryKey: React.PropTypes.string,
            haproxyHost: React.PropTypes.string,
            haproxyBackend: React.PropTypes.number,
            servers: ImmutablePropTypes.listOf(
                ImmutablePropTypes.contains({
                    haproxyKey: React.PropTypes.string,
                    serverId: React.PropTypes.number.isRequired
                })
            ).isRequired
        }),
        dispatch: React.PropTypes.func.isRequired,
        serversById: ImmutablePropTypes.mapOf(
            ImmutablePropTypes.contains({
                id: React.PropTypes.number.isRequired,
                name: React.PropTypes.string.isRequired
            })
        ).isRequired,
        backendsById: ImmutablePropTypes.mapOf(
            ImmutablePropTypes.contains({
                id: React.PropTypes.number.isRequired,
                name: React.PropTypes.string.isRequired
            })
        ).isRequired,
    },
    mixins: [PureRenderMixin],
    render() {
        return (
            <div>
                <h2>Edit Cluster</h2>
                <p><Link to={"/admin/clusters/"}>back to list</Link></p>
                <div>
                    <ClusterForm cluster={this.props.cluster}  backendsById={this.props.backendsById} ref="clusterForm" onSubmit={this.editCluster} serversById={this.props.serversById} />
                    <div className="row">
                        <div className="col-sm-offset-2 col-sm-1">
                            <button className="btn btn-sm btn-warning" onClick={this.reset}>Reset</button>
                        </div>
                    </div>
                </div>
            </div>
        );
    },
    editCluster(name, inventoryKey, haproxyHost, haproxyBackend, servers_data) {  //TODO HEEERE
        this.props.dispatch(Actions.editCluster(this.props.cluster.get('id'), {name, inventoryKey, haproxyHost, haproxyBackend, servers: servers_data, sync:false}));
        this.context.router.push('/admin/clusters');
    },
    reset() {
        this.refs.clusterForm.reset();
    }
});

export default ClusterEdit;
