//Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).
import React from 'react';
import { connect } from 'react-redux';
import * as Actions from '../../../Actions';
import ImmutablePropTypes from 'react-immutable-proptypes';
import PureRenderMixin from 'react-addons-pure-render-mixin';
import FuzzyListForm from '../../lib/FuzzyListForm.jsx';
import FuzzyListSelector from '../../lib/FuzzyListSelector.jsx';
import LinkedStateMixin from 'react-addons-linked-state-mixin';
import { List, Map } from 'immutable';

const ClusterForm = React.createClass({
    mixins: [LinkedStateMixin],
    propTypes: {
        cluster: ImmutablePropTypes.contains({
            name: React.PropTypes.string.isRequired,
            haproxyHost: React.PropTypes.string,
            haproxyBackend: React.PropTypes.number,
            inventoryKey: React.PropTypes.string,
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
        backendsById: ImmutablePropTypes.mapOf(
            ImmutablePropTypes.contains({
                id: React.PropTypes.number.isRequired,
                name: React.PropTypes.string.isRequired,
                clusterKey: React.PropTypes.string.isRequired,
            })
        ).isRequired,
        onSubmit: React.PropTypes.func.isRequired
    },
    getInitialState() {
        let clusterName = "";
        let haproxyHost = "";
        let haproxyBackend = "";
        let selectedServers = List();
        let availableBackends = Map();
        const haproxyKeys = {}; // map server id to server haproxyKey
        const that = this;
        let synchronized = false;
        if(this.props.cluster) {
            clusterName = this.props.cluster.get('name');
            haproxyHost = this.props.cluster.get('haproxyHost');
            haproxyBackend = this.props.backendsById.get(this.props.cluster.get('haproxyBackend'));
            selectedServers = this.props.cluster.get('servers').map(server => that.props.serversById.get(server.get('serverId')));
            this.props.cluster.get('servers').map(server => {
                haproxyKeys[server.get('serverId')] = server.get('haproxyKey');
            });
            synchronized = this.props.cluster.get('inventoryKey') != null;
            availableBackends = this.props.backendsById.filter( backend =>
                backend.get('clusterKey') === this.props.cluster.get('inventoryKey')

            )
        }
        return {
            clusterName,
            haproxyHost,
            haproxyBackend,
            selectedServers,
            haproxyKeys,
            synchronized,
            availableBackends,
        };
    },
    onServersChanged(servers) {
        this.setState({selectedServers: servers});
    },
    onBackendChanged(backend) {
        this.setState({haproxyBackend: backend});
    },
    backendRender(backend) {
        return backend.get('name') + ' (' + backend.get('haproxyHost') + ')';
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
    renderBackendData(backend) {
        return (
            <div>
                <div className="row">
                    <label className="col-sm-3">HAProxy Host</label>
                    <div className="col-sm-8">{backend.get('haproxyHost')}</div>
                </div>
                {this.state.selectedServers.map((el, index) => <div key={index} className="row">
                    <label className="col-sm-1 control-label">server</label>
                    <div className="col-sm-5 form-align"> {el.get('name').split('.')[0].toUpperCase()} </div>
                </div>)
                }
            </div>
            )
    },
    render() {
        const that = this;
        return (
          <div>
            <div className="cluster-form-tab">
                <form className="form-horizontal">
                    <div className="form-group">
                        <label className="col-sm-2 control-label">Name</label>
                        <div className="col-sm-8">
                            {this.state.synchronized == true ?
                                <div class="col-sm-5 form-align">{this.state.clusterName}</div>
                                :
                                <input name="clusterName" type="text" placeholder="myproject_prod" className="form-control" valueLink={this.linkState('clusterName')}/>
                            }
                        </div>
                    </div>
                    {this.state.synchronized == true ?
                        <div className="form-group">
                            <label className="col-sm-2 control-label">HAProxy Backend</label>
                            <div className="col-sm-8">
                                <FuzzyListSelector
                                    onChange={this.onBackendChanged}
                                    elements={this.state.availableBackends.toList()}
                                    selectedElement={this.state.haproxyBackend}
                                    renderElement={this.backendRender}
                                    placeholder="BACKEND_TEST"
                                    renderElementView={this.renderBackendData}
                                    compareWith={this.backendRender} />
                            </div>
                        </div>
                        :
                        <div className="form-group">
                            <label className="col-sm-2 control-label">HAProxy Host</label>
                            <div className="col-sm-5">
                                <input name="haproxyHost" type="text" placeholder="http://haproxy.example.com:800" className="form-control" valueLink={this.linkState('haproxyHost')} />
                            </div>
                        </div>
                    }
                    <div className="form-group">
                        <label className="col-sm-2 control-label">Servers</label>
                        {this.state.synchronized == true ?
                            <div className="col-sm-8">
                                {this.state.selectedServers.map((el, index) => <div key={index} className="row">
                                    <div className="col-sm-5 form-align row"> {el.get('name')} </div>
                                </div>
                                )}
                            </div>
                            :
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
                        }
                    </div>
                    <div className="form-group">
                        <div className="col-sm-5 col-sm-offset-2">
                            <button type="button" onClick={this.onSubmit} className="btn btn-default">Submit</button>
                        </div>
                    </div>
                </form>
            </div>
          </div>
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
                inventoryKey: null,
                haproxyKey: (this.state.haproxyKeys[server.get('id')] || null)
            });
        });
        let haproxyBackend = 0;
        if (this.state.haproxyBackend) {
            haproxyBackend = this.state.haproxyBackend.get('id');
        }
        this.props.onSubmit(
          this.state.clusterName,
          null,
          this.state.haproxyHost,
          haproxyBackend,
          serversHaproxy);
    }
});

export default ClusterForm;
