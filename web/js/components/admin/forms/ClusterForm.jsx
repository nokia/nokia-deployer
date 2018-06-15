//Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).
import React from 'react';
import { connect } from 'react-redux';
import * as Actions from '../../../Actions';
import ImmutablePropTypes from 'react-immutable-proptypes';
import PureRenderMixin from 'react-addons-pure-render-mixin';
import FuzzyListForm from '../../lib/FuzzyListForm.jsx';
import FuzzyListSingleForm from '../../lib/FuzzyListSingleForm.jsx';
import LinkedStateMixin from 'react-addons-linked-state-mixin';
import { List } from 'immutable';

const ClusterForm = React.createClass({
    mixins: [LinkedStateMixin],
    propTypes: {
        cluster: ImmutablePropTypes.contains({
            name: React.PropTypes.string.isRequired,
            haproxyHost: React.PropTypes.string,
            inventoryKey: React.PropTypes.string,
            haproxyBackend: React.PropTypes.string,
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
        inventoryClustersById: ImmutablePropTypes.mapOf(
            ImmutablePropTypes.contains({
                id: React.PropTypes.string.isRequired,
                inventory_key : React.PropTypes.string.isRequired,
                name: React.PropTypes.string.isRequired,
                haproxyHost: React.PropTypes.string,
                servers: ImmutablePropTypes.listOf(
                    ImmutablePropTypes.contains({
                        inventory_key: React.PropTypes.string.isRequired,
                        name: React.PropTypes.string.isRequired
                    })
                ).isRequired
            })
        ),
        onSubmit: React.PropTypes.func.isRequired
    },
    getInitialState() {
        let clusterName = "";
        let haproxyHost = "";
        let haproxyBackend = "";
        let selectedServers = List();
        let selectedInventoryCluster = null;
        let selectedChildren= List();
        let clusterType = "inventory";
        const haproxyKeys = {}; // map server id to server haproxyKey
        const inventoryHaproxyKeys = {};
        const that = this;
        if(this.props.cluster) {
            clusterName = this.props.cluster.get('name');
            haproxyHost = this.props.cluster.get('haproxyHost');
            haproxyBackend = this.props.cluster.get('haproxyBackend');
            if (this.props.cluster.get('inventoryKey') == null) {
              clusterType = 'deployer';
            } else {
              clusterType = 'inventory';
            }
            selectedServers = this.props.cluster.get('servers').map(server => that.props.serversById.get(server.get('serverId')));
            this.props.cluster.get('servers').map(server => {
                haproxyKeys[server.get('serverId')] = server.get('haproxyKey');
                inventoryHaproxyKeys[server.get('serverId')] = server.get('haproxyKey');
            });
        }
        return {
            clusterName,
            haproxyHost,
            haproxyBackend,
            selectedServers,
            selectedInventoryCluster,
            selectedChildren,
            clusterType,
            inventoryHaproxyKeys,
            haproxyKeys
        };
    },
    onServersChanged(servers) {
        this.setState({selectedServers: servers});
    },
    onClusterChanged(cluster) {
        this.setState({selectedInventoryCluster: cluster});
        if(cluster != null) {
            this.setState({selectedChildren: cluster.get('servers').toList()});
        } else {
            this.setState({selectedChildren: List()});
        }
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
    inventoryRenderHaproxyKeyInput(server) {
        return <input className="form-control input-sm"
            placeholder="HAProxy key" name={`haproxy-host-${server.get('name')}`}
            value={this.state.inventoryHaproxyKeys[server.get('inventory_key')] || ""}
            onChange={this.inventoryOnHaproxyKeyChanged(server)} />
    },
    inventoryOnHaproxyKeyChanged(server) {
        const that = this;
        return evt => {
            const haproxyKey = evt.target.value;
            const newHaproxyKeys = that.state.inventoryHaproxyKeys;
            newHaproxyKeys[server.get('inventory_key')] = haproxyKey;
            that.setState({inventoryHaproxyKeys: newHaproxyKeys});
        }
    },
    renderClusterInput(cluster) {
        return <input className="form-control input-sm"
            placeholder="HAProxy host" name={`haproxy-host-${cluster.get('name')}`}
            value={this.state.haproxyHost || ""}
            onChange={this.onHaproxyHostChanged()} />
    },
    onHaproxyHostChanged() {
        const that = this;
        return evt => {
            const haproxyHost = evt.target.value;
            that.setState({haproxyHost: haproxyHost});
        }
    },
    render() {
        const that = this;
        let multipleChoice = (this.props.cluster == null);
        return (
          <div>
          {multipleChoice &&
              <ul className="nav nav-tabs">
                  <li onClick={that.onMethodTabClicked('inventory')} className={this.state.clusterType == 'inventory' ? "active" : ""}><a href="#">
                  <span className="glyphicon glyphicon-cloud"></span> From inventory
                      </a></li>
                  <li onClick={that.onMethodTabClicked('deployer')} className={this.state.clusterType == 'deployer' ? "active" : ""}><a href="#">
                  <span className="glyphicon glyphicon-plus"></span> Local add
                      </a></li>
              </ul>
            }
            {multipleChoice &&
            <div className="cluster-form-tab" hidden={this.state.clusterType != 'inventory'}>
                <form className="form-horizontal">
                    <div className="form-group">
                        <label className="col-sm-2 control-label">Available clusters</label>
                        <div className="col-sm-8">
                            <FuzzyListSingleForm
                                onChange={this.onClusterChanged}
                                elements={this.props.inventoryClustersById.toList()}
                                selectedElement={this.state.selectedInventoryCluster}
                                selectedChildren={this.state.selectedChildren}
                                childElement="servers"
                                renderElement={cluster => cluster.get('name')}
                                renderChildElement={server => server.get('name')}
                                placeholder="hq|mycluster-dev"
                                renderElementForm={this.renderClusterInput}
                                renderChildForm={this.inventoryRenderHaproxyKeyInput}
                                compareWith={cluster => cluster.get('name')}
                            />
                        </div>
                    </div>
                    <div className="form-group">
                        <div className="col-sm-5 col-sm-offset-2">
                            <button type="button" onClick={this.onInventorySubmit} className="btn btn-default">Submit</button>
                        </div>
                    </div>
                </form>
            </div>
          }
            <div className="cluster-form-tab" hidden={this.state.clusterType != 'deployer'}>
                <form className="form-horizontal">
                    <div className="form-group">
                        <label className="col-sm-2 control-label">Name</label>
                        <div className="col-sm-8">
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
                        <label className="col-sm-2 control-label">HAProxy Backend</label>
                        <div className="col-sm-5">
                            <input name="haproxyBackend" type="text" placeholder="MY_HAPROXY_BACKEND" className="form-control" valueLink={this.linkState('haproxyBackend')} />
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
            </div>
          </div>
        );
    },
    reset() {
        this.setState(this.getInitialState());
    },
    onMethodTabClicked(value) {
      return e => {
          e.preventDefault();
          this.setState({clusterType: value});
      };
    },
    onInventorySubmit() {
        const serversHaproxy = [];
        this.state.selectedChildren.forEach(server => {
            serversHaproxy.push({
                inventoryKey: server.get('inventory_key'),
                haproxyKey: (this.state.inventoryHaproxyKeys[server.get('inventory_key')] || null),
                serverId: null
          });
      });
      this.props.onSubmit(
        this.state.selectedInventoryCluster.get('name'),
        this.state.selectedInventoryCluster.get('inventory_key'),
        this.state.haproxyHost,
        null,
        serversHaproxy
      );
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
        this.props.onSubmit(this.state.clusterName, null, this.state.haproxyHost, this.state.haproxyBackend, serversHaproxy);
    }
});

export default ClusterForm;
