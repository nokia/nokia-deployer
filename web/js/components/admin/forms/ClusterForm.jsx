//Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).
import React from 'react';
import ImmutablePropTypes from 'react-immutable-proptypes';
import PureRenderMixin from 'react-addons-pure-render-mixin';
import FuzzyListForm from '../../lib/FuzzyListForm.jsx';
import LinkedStateMixin from 'react-addons-linked-state-mixin';
import { List } from 'immutable';

const ClusterForm = React.createClass({
    mixins: [LinkedStateMixin],
    propTypes: {
        cluster: ImmutablePropTypes.contains({
            name: React.PropTypes.string.isRequired,
            haproxyHost: React.PropTypes.string,
            servers: ImmutablePropTypes.listOf(
                ImmutablePropTypes.contains({
                    haproxyKey: React.PropTypes.string,
                    serverId: React.PropTypes.number.isRequired
                })
            ).isRequired
        }),
        serversById: ImmutablePropTypes.mapOf(
            ImmutablePropTypes.contains({
                id: React.PropTypes.number.isRequired,
                name: React.PropTypes.string.isRequired
            })
        ).isRequired,
        onSubmit: React.PropTypes.func.isRequired
    },
    getInitialState() {
        let clusterName = "";
        let haproxyHost = "";
        let selectedServers = List();
        const haproxyKeys = {}; // map server id to server haproxyKey
        const that = this;
        if(this.props.cluster) {
            clusterName = this.props.cluster.get('name');
            haproxyHost = this.props.cluster.get('haproxyHost');
            selectedServers = this.props.cluster.get('servers').map(server => that.props.serversById.get(server.get('serverId')));
            this.props.cluster.get('servers').map(server => {
                haproxyKeys[server.get('serverId')] = server.get('haproxyKey');
            });
        }
        return {
            clusterName,
            haproxyHost,
            selectedServers,
            haproxyKeys
        };
    },
    onServersChanged(servers) {
        this.setState({selectedServers: servers});
    },
    componentWillReceiveProps(nextProps) {
        if(nextProps.cluster && (nextProps.cluster != this.props.cluster || nextProps.serversById != this.props.serversById)) {
            this.setState({
                selectedServers: nextProps.cluster.get('servers').map(server => nextProps.serversById.get(server.get('serverId')))
            });
        }
    },
    renderHaproxyKeyInput(server) {
        return <input className="form-control input-sm"
            placeholder="HAProxy key" name={`haproxy-host-${server.get('name')}`}
            value={this.state.haproxyKeys[server.get('id')] || ""}
            onChange={this.onHaproxyKeyChanged(server)} />
    },
    onHaproxyKeyChanged(server) {
        const that = this;
        return evt => {
            const haproxyKey = evt.target.value;
            const newHaproxyKeys = that.state.haproxyKeys;
            newHaproxyKeys[server.get('id')] = haproxyKey;
            that.setState({haproxyKeys: newHaproxyKeys});
        }
    },
    render() {
        const that = this;
        return (
            <form className="form-horizontal">
                <div className="form-group">
                    <label className="col-sm-2 control-label">Name</label>
                    <div className="col-sm-5">
                        <input name="clusterName" type="text" placeholder="myproject_prod" className="form-control" valueLink={this.linkState('clusterName')} />
                    </div>
                </div>
                <div className="form-group">
                    <label className="col-sm-2 control-label">HAProxy Host</label>
                    <div className="col-sm-5">
                        <input name="haproxyHost" type="text" placeholder="http://haproxy.example.com:800" className="form-control" valueLink={this.linkState('haproxyHost')} />
                    </div>
                </div>
                <div className="form-group">
                    <label className="col-sm-2 control-label">Servers</label>
                    <div className="col-sm-8">
                        <FuzzyListForm
                            onChange={this.onServersChanged}
                            elements={this.props.serversById.toList()}
                            selectedElements={this.state.selectedServers}
                            renderElement={server => server.get('name')}
                            placeholder="server.example.com"
                            renderElementForm={this.renderHaproxyKeyInput}
                            compareWith={server => server.get('name')} />
                    </div>
                </div>
                <div className="form-group">
                    <div className="col-sm-5 col-sm-offset-2">
                        <button type="button" onClick={this.onSubmit} className="btn btn-default">Submit</button>
                    </div>
                </div>
            </form>
        );
    },
    reset() {
        this.setState(this.getInitialState());
    },
    onSubmit() {
        const serversHaproxy = [];
        this.state.selectedServers.forEach(server => {
            serversHaproxy.push({
                serverId: server.get('id'),
                haproxyKey: (this.state.haproxyKeys[server.get('id')] || null)
            });
        });
        this.props.onSubmit(this.state.clusterName, this.state.haproxyHost, serversHaproxy);
    }
});

export default ClusterForm;
