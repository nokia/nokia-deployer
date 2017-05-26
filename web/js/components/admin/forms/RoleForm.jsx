//Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).
import React from 'react';
import ImmutablePropTypes from 'react-immutable-proptypes';
import PureRenderMixin from 'react-addons-pure-render-mixin';
import LinkedStateMixin from 'react-addons-linked-state-mixin';
import FuzzyListForm from '../../lib/FuzzyListForm.jsx';
import update from 'react-addons-update';


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
    getInitialState() {
        let roleName = "";
        let permissions = {};
        if(this.props.role) {
            roleName = this.props.role.get('name');
            // permissions
            permissions = this.props.role.get('permissions');
        }
        const isAdmin = permissions.admin === true;
        const isDeployer = permissions.deployer === true;
        const canImpersonate = permissions.impersonate === true;
        return {
            roleName,
            permissions,
            isAdmin,
            canImpersonate,
            isDeployer
        };
    },
    renderEnv(env) {
        return `${env.get('repositoryName')} / ${env.get('name')}`;
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
                    {[['read', 'Read'], ['deploy_business_hours', 'Deploy (business hours only)'], ['deploy', 'Deploy']].map(permissionDef => {
                        const permissionType = permissionDef[0];
                        const humanName = permissionDef[1];
                        const initialEnvs = that.props.environmentsById.filter((env, envId) => that.state.permissions[permissionType] != null && that.state.permissions[permissionType].indexOf(envId) != -1).toList();
                        return <div key={permissionType} className="form-group">
                            <label className="col-sm-2 control-label">{humanName}</label>
                            <div className="col-sm-5">
                                <FuzzyListForm  ref="readPermissionsSelector"
                                    onChange={that.onPermissionsChanged(permissionType)}
                                    elements={that.props.environmentsById.toList()}
                                    initialElements={initialEnvs}
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
            const command = {};
            command[permissionType] = {$set: environments.map(env => env.get('id'))};
            const permissions = update(that.state.permissions, command);
            that.setState({permissions});
        };
    },
    onSubmit() {
        let permissions = {};
        if(this.state.isAdmin) {
            permissions = {admin: true};
        } else {
            permissions = this.state.permissions;
            if(this.state.canImpersonate) {
                permissions.impersonate = true;
            }
            if(this.state.isDeployer) {
                permissions.deployer = true;
            }
        }
        this.props.onSubmit(this.state.roleName, permissions);
    },
    reset() {
        this.setState(this.getInitialState());
    }
});

export default RoleForm;
