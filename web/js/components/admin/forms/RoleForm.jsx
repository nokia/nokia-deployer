//Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).
import React from 'react';
import ImmutablePropTypes from 'react-immutable-proptypes';
import PureRenderMixin from 'react-addons-pure-render-mixin';
import LinkedStateMixin from 'react-addons-linked-state-mixin';
import FuzzyListForm from '../../lib/FuzzyListForm.jsx';
import { List, Map } from 'immutable';

const PERMISSIONS = [['read', 'Read'], ['deploy_business_hours', 'Deploy (business hours only)'], ['deploy', 'Deploy']];

const RoleForm = React.createClass({
    mixins: [PureRenderMixin, LinkedStateMixin],
    propTypes: {
        onSubmit: React.PropTypes.func.isRequired,
        environmentsById: ImmutablePropTypes.mapOf(
            ImmutablePropTypes.contains({
                id: React.PropTypes.number.isRequired,
                name: React.PropTypes.string.isRequired,
                repositoryName: React.PropTypes.string.isRequired
            })
        ),
        role: ImmutablePropTypes.contains({
            name: React.PropTypes.string.isRequired,
            permissions: React.PropTypes.object.isRequired
        })
    },
    stateFromProps(props) {
        let roleName = "";
        // FIXME: do not hardcode this permission list in several places in the backend/frontend
        let selectedPermissions = Map({'read': List(), 'deploy': List(), 'deploy_business_hours': List()});
        let currentPermissions = {'admin': false, 'deployer': false, 'impersonate': false};
        if(props.role) {
            roleName = props.role.get('name');
            currentPermissions = props.role.get('permissions');
            PERMISSIONS.map(([permissionType, _]) => {
                if (currentPermissions.hasOwnProperty(permissionType)) {
                    selectedPermissions = selectedPermissions.set(
                        permissionType,
                        List(currentPermissions[permissionType].map(
                            environmentId => props.environmentsById.get(environmentId)
                        )).filter(env => env != null)
                    );
                }
            });
        }
        const isAdmin = currentPermissions.admin === true;
        const isDeployer = currentPermissions.deployer === true;
        const canImpersonate = currentPermissions.impersonate === true;
        return {
            roleName,
            selectedPermissions,
            isAdmin,
            canImpersonate,
            isDeployer
        };
    },
    getInitialState() {
        return this.stateFromProps(this.props);
    },
    renderEnv(env) {
        return `${env.get('repositoryName')} / ${env.get('name')}`;
    },
    componentWillReceiveProps(nextProps) {
        if(nextProps.role != this.props.role || this.props.environmentsById != nextProps.environmentsById) {
            this.setState(this.stateFromProps(nextProps));
        }
    },
    render() {
        const that = this;
        return <form className="form-horizontal">
            <div className="form-group">
                <label className="col-sm-2 control-label">Name</label>
                <div className="col-sm-5">
                    <input name="roleName" type="text" placeholder="role name" className="form-control" valueLink={this.linkState('roleName')} />
                </div>
            </div>
            <h4>Permissions</h4>
            { that.state.isDeployer ? null :
            <div className="form-group">
                <div className="col-sm-offset-2 col-sm-5">
                    <div className="checkbox row">
                        <label>
                            <input type="checkbox" checkedLink={that.linkState('isAdmin')}/> Admin
                            { that.state.isAdmin ? <p class="text-muted">All others permissions are implied by 'Admin'.</p>: null}
                        </label>
                    </div>
                </div>
            </div>
            }
            { that.state.isAdmin ? null :
            <div className="form-group">
                <div className="col-sm-offset-2 col-sm-5">
                    <div className="checkbox row">
                        <label>
                            <input type="checkbox" checkedLink={that.linkState('isDeployer')}/> Deployer (permission for deployer instances)
                        </label>
                    </div>
                </div>
            </div>
            }
            { that.state.isAdmin  || that.state.isDeployer ? null :
                <div>
                    {PERMISSIONS.map(([permissionType, humanName]) => {
                        return <div key={permissionType} className="form-group">
                            <label className="col-sm-2 control-label">{humanName}</label>
                            <div className="col-sm-5">
                                <FuzzyListForm
                                    onChange={that.onPermissionsChanged(permissionType)}
                                    elements={that.props.environmentsById.toList()}
                                    selectedElements={that.state.selectedPermissions.get(permissionType)}
                                    renderElement={that.renderEnv}
                                    placeholder="apiv2 / dev"
                                    compareWith={that.renderEnv} />
                            </div>
                        </div>;
                    })}
                    <div className="form-group">
                        <div className="col-sm-offset-2 col-sm-5">
                            <div className="checkbox row">
                                <label>
                                    <input type="checkbox" checkedLink={that.linkState('canImpersonate')}/> Allow impersonation (deploy using the permissions of another user, useful for bots. Implies the right to read any environment.)
                                    { that.state.canImpersonate ? <p className="text-warning">Warning: one can impersonate admin users too!</p> : null}
                                </label>
                            </div>
                        </div>
                    </div>
                                    </div>
                }
            <div className="form-group">
                <div className="col-sm-5 col-sm-offset-2">
                    <button type="button" onClick={that.onSubmit} className="btn btn-default">Submit</button>
                </div>
            </div>
            </form>;
    },
    onPermissionsChanged(permissionType) {
        const that = this;
        return environments => {
            const selectedPermissions = that.state.selectedPermissions.set(permissionType, environments);
            that.setState({selectedPermissions});
        };
    },
    onSubmit() {
        let permissions = {};
        if(this.state.isAdmin) {
            permissions = {admin: true};
        } else {
            if(this.state.canImpersonate) {
                permissions.impersonate = true;
            }
            if(this.state.isDeployer) {
                permissions.deployer = true;
            }
            PERMISSIONS.map(([permissionType, _]) => {
                permissions[permissionType] = this.state.selectedPermissions.get(permissionType).map(environment => environment.get("id")).toJS();
            });

        }
        this.props.onSubmit(this.state.roleName, permissions);
    },
    reset() {
        this.setState(this.getInitialState());
    }
});

export default RoleForm;
