//Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).
import React from 'react';
import LinkedStateMixin from 'react-addons-linked-state-mixin';
import PureRenderMixin from 'react-addons-pure-render-mixin';
import ImmutablePropTypes from 'react-immutable-proptypes';

const ServerForm = React.createClass({
    mixins: [PureRenderMixin, LinkedStateMixin],
    propTypes: {
        server: ImmutablePropTypes.contains({
            name: React.PropTypes.string.isRequired,
            port: React.PropTypes.number.isRequired
        }),
        // will be passed one parameter: serverName
        onSubmit: React.PropTypes.func.isRequired
    },
    getInitialState() {
        let serverName = "";
        let serverPort = 22;
        if(this.props.server) {
            serverName = this.props.server.get('name');
            serverPort = this.props.server.get('port');
        }
        return {
            serverName,
            serverPort
        };
    },
    onSubmit() {
        this.props.onSubmit(this.state.serverName, this.state.serverPort);
    },
    reset() {
        this.setState(this.getInitialState());
    },
    render() {
        return <form className="form-horizontal">
            <div className="form-group">
                <label className="col-sm-1 control-label">Hostname</label>
                <div className="col-sm-5">
                    <input name="serverName" valueLink={this.linkState('serverName')} type="text" placeholder="server.example.com" className="form-control col-sm-6"/>
                </div>
            </div>
            <div className="form-group">
                <label className="col-sm-1 control-label">SSH port</label>
                <div className="col-sm-5">
                    <input name="serverName" valueLink={this.linkState('serverPort')} type="number" placeholder="22" className="form-control col-sm-6"/>
                </div>
            </div>
            <div className="form-group">
                <div className="col-sm-5 col-sm-offset-1">
                    <button type="button" onClick={this.onSubmit} className="btn btn-default">Submit</button>
                </div>
            </div>
        </form>;
    }
});

export default ServerForm;
