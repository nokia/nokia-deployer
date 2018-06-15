//Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).
import React from 'react';
import ImmutablePropTypes from 'react-immutable-proptypes';
import PureRenderMixin from 'react-addons-pure-render-mixin';
import ServerForm from './forms/ServerForm.jsx';
import * as Actions from '../../Actions';
import {Link} from 'react-router';

const ServerEdit = React.createClass({
    contextTypes: {
        router: React.PropTypes.object.isRequired
    },
    propTypes: {
        server: ImmutablePropTypes.contains({
            name: React.PropTypes.string.isRequired,
            inventoryKey: React.PropTypes.string,
            id: React.PropTypes.number.isRequired
        }),
        dispatch: React.PropTypes.func.isRequired
    },
    mixins: [PureRenderMixin],
    render() {
        return (
            <div>
                <h2>Edit Server</h2>
                <p><Link to={"/admin/servers/"}>back to list</Link></p>
                <h3>Server Details</h3>
                {this.props.server.get('inventoryKey') == null ?
                <div>
                <ServerForm server={this.props.server} ref="serverForm" onSubmit={this.editServer}/>
                <div className="row">
                    <div className="col-sm-offset-1 col-sm-1">
                        <button className="btn btn-sm btn-warning" onClick={this.reset}>Reset</button>
                    </div>
                </div>
                </div>
                :
                <div className="row">
                    Impossible to modify a server linked to a synchronized cluster
                </div>
              }
            </div>
        );
    },
    editServer(serverName, serverPort) {
        this.props.dispatch(Actions.updateServer(this.props.server.get('id'), serverName, serverPort, this.props.server.get('activated')));
        this.context.router.push('/admin/servers');
    },
    reset() {
        this.refs.serverForm.reset();
    }
});

export default ServerEdit;
