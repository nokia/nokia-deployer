//Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).
import React from 'react';
import ImmutablePropTypes from 'react-immutable-proptypes';
import { connect } from 'react-redux';
import * as Actions from '../../Actions';
import {Link} from 'react-router';
import PureRenderMixin from 'react-addons-pure-render-mixin';
import ServerForm from './forms/ServerForm.jsx';
import ConfirmationDialog from '../lib/ConfirmationDialog.jsx';

const ServerList = React.createClass({
    mixins: [PureRenderMixin],
    contextTypes: {
        user: React.PropTypes.object
    },
    propTypes: {
        serversById: ImmutablePropTypes.mapOf(
            ImmutablePropTypes.contains({
                id: React.PropTypes.number.isRequired,
                inventoryKey: React.PropTypes.string,
                name: React.PropTypes.string.isRequired
            })
        ),
        dispatch: React.PropTypes.func.isRequired
    },
    fetchServers() {
        this.props.dispatch(Actions.loadServerList());
    },
    componentWillReceiveProps(nextProps, nextContext) {
        if(nextContext.user !== this.context.user) {
            this.fetchServers();
        }
    },
    componentWillMount() {
        this.fetchServers();
    },
    render() {
        const that = this;
        const serverId = parseInt(this.props.params.id, 10);
        const server = this.props.serversById.get(serverId);
        if(this.props.children) {
            if(!server) {
                return <h2>This server does not exist.</h2>;
            }
            return React.cloneElement(this.props.children, {server, dispatch: this.props.dispatch});
        }
        return (
            <div>
                <h2>Servers</h2>
                <h3>New Server</h3>
                <ServerForm onSubmit={this.addServer} />
                <h3>Server list</h3>
                <table className="table table-condensed table-striped">
                    <thead>
                        <tr>
                            <td>Hostname</td>
                            <td>SSH Port</td>
                            <td>ID</td>
                            <td>Actions</td>
                        </tr>
                    </thead>
                    <tbody>
                        {this.props.serversById.sort((s1, s2) => s1.get('name').localeCompare(s2.get('name'))).map(server => <tr key={server.get('id')}>
                            <td>{server.get('name')}</td>
                            <td>{server.get('port')}</td>
                            <td>{server.get('id')}</td>
                            <td>
                                <div className="btn-group">
                                    <Link className="btn btn-default btn-sm" to={`/admin/servers/${server.get('id')}/edit`} disabled={this.isInventoryServer(server)}>Edit</Link>
                                    <Link className="btn btn-default btn-sm" to={`/admin/servers/${server.get('id')}/releases`}>View releases</Link>
                                    {server.get("activated") ?
                                        <button onClick={that.toggleServerActivation(server)} className="btn btn-warning btn-sm" type="button" disabled={this.isInventoryServer(server)}>Deactivate</button>
                                        :
                                        <button onClick={that.toggleServerActivation(server)} className="btn btn-default btn-sm" type="button" disabled={this.isInventoryServer(server)}>Activate</button>
                                    }
                                    <button onClick={that.deleteServer(server)} className="btn btn-danger btn-sm" type="button" disabled={this.isInventoryServer(server)}>Delete</button>
                                </div>
                            </td>
                        </tr>).toList()
                        }
                    </tbody>
                </table>
                <ConfirmationDialog ref="confirmationDialog" />
            </div>
        );
    },
    isInventoryServer(server) {
      return server.get('inventoryKey') != null;
    },
    deleteServer(server) {
        const that = this;
        return () => {
            that.refs.confirmationDialog.show(
                <span>Delete the server <strong>{server.get("name")}</strong>? This action can not be undone.</span>,
                () => {
                    that.props.dispatch(Actions.deleteServer(server.get("id")));
                }
            );
        };
    },
    addServer(name, port) {
        this.props.dispatch(Actions.addServer({name, port}));
    },
    toggleServerActivation(server) {
        const that = this;
        return () => {
            const activated = ! server.get('activated');
            that.props.dispatch(Actions.updateServer(server.get('id'), server.get('name'), server.get('port'), activated));
        };
    }
});

const ReduxServerList = connect(state => ({
    serversById: state.get('serversById')
}))(ServerList);

export default ReduxServerList;
