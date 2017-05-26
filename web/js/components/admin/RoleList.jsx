//Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).
import React from 'react';
import Immutable from 'immutable';
import ImmutablePropTypes from 'react-immutable-proptypes';
import PureRenderMixin from 'react-addons-pure-render-mixin';
import * as Actions from '../../Actions';
import { connect } from 'react-redux';
import {Link} from 'react-router';
import RoleForm from './forms/RoleForm.jsx';
import ConfirmationDialog from '../lib/ConfirmationDialog.jsx';

const RoleList = React.createClass({
    contextTypes: {
        router: React.PropTypes.object.isRequired,
        user: React.PropTypes.object.isRequired
    },
    mixins: [PureRenderMixin],
    propTypes: {
        rolesById: ImmutablePropTypes.mapOf(
            ImmutablePropTypes.contains({
                id: React.PropTypes.number.isRequired,
                name: React.PropTypes.string.isRequired,
                permissions: React.PropTypes.object.isRequired
            })
        ),
        environmentsById: ImmutablePropTypes.mapOf(
            ImmutablePropTypes.contains({
                name: React.PropTypes.string.isRequired,
                repositoryName: React.PropTypes.string.isRequired
            })
        ),
        dispatch: React.PropTypes.func.isRequired
    },
    getDefaultProps() {
        return {
            rolesById: Immutable.Map()
        };
    },
    fetchData() {
        this.props.dispatch(Actions.loadRoles());
        this.props.dispatch(Actions.loadEnvironments());
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
        if(that.props.children) {
            const roleId = parseInt(this.props.params.id, 10);
            const role = this.props.rolesById.get(roleId);
            if(!role) {
                return <h2>This role does not exist.</h2>;
            }
            return React.cloneElement(this.props.children, {role, dispatch: this.props.dispatch, environmentsById: this.props.environmentsById});
        }
        return <div>
            <h2>Roles</h2>
            <h3>New Role</h3>
            <RoleForm environmentsById={that.props.environmentsById} onSubmit={that.onSubmitNewRoleClicked}/>
            <h3>Role List</h3>
            <table className="table table-striped">
                <thead>
                    <tr>
                        <th>ID</th>
                        <th>Name</th>
                        <th>Permissions</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    { that.props.rolesById.map(role => <tr key={role.get('id')}>
                        <td>{role.get('id')}</td>
                        <td>{role.get('name')}</td>
                        <td>{that.renderPermissions(role.get('permissions'))}</td>
                        <td>
                            <div className="btn-group">
                                <button className="btn btn-sm btn-default" type="button" onClick={that.editRole(role)}>Edit</button>
                                <button className="btn btn-sm btn-danger" type="button" onClick={that.deleteRole(role)}>Delete</button>
                            </div>
                        </td>
                    </tr>).toList()}
                </tbody>
            </table>
            <ConfirmationDialog ref="confirmationDialog" />
        </div>;
    },
    renderPermissions(permissions) {
        const that = this;
        if(permissions.admin) {
            return <h6>Admin</h6>;
        }
        const out = [];
        if(permissions.impersonate) {
            out.push(<h6 title='Deploy using the permissions of another user (including admin users), and read all environments.'>Impersonate</h6>);
        }
        if(permissions.deployer) {
            out.push(<h6 title='Used by instances of the deployer service'>Deployer</h6>);
        }
        const toCheck = ['deploy_business_hours', 'deploy', 'read'];
        const humanNames = ['Deploy (business hours only)', 'Deploy', 'Read-only'];
        for(let j = 0, len = toCheck.length; j < len; j++) {
            const envDescriptions = {};
            const envs = permissions[toCheck[j]];
            if(!envs || envs.length == 0) {
                continue;
            }
            for(let i = 0, lenn = envs.length; i < lenn; i++) {
                const env = that.props.environmentsById.get(envs[i]);
                if(!env) {
                    continue;
                }
                if(!envDescriptions[env.get('repositoryId')]) {
                    envDescriptions[env.get('repositoryId')] = [];
                }
                envDescriptions[env.get('repositoryId')].push(env);
            }
            const component = <div key={toCheck[j]}>
                <h6>{humanNames[j]}</h6>
                <ul>
                    {Object.keys(envDescriptions).map(repositoryId => {
                        const envs = envDescriptions[repositoryId];
                        // FIXME repositoryName no longer in environment
                        const repositoryName = envs[0].get('repositoryName');
                        return <li key={repositoryId}>
                            <Link to={`/repositories/${repositoryId}`}>{repositoryName}</Link> ( {envs.map(env => `${env.get('name')} `)})
                        </li>;
                    })}
                </ul>
            </div>;
            out.push(component);
        }
        return out;
    },
    onSubmitNewRoleClicked(roleName, permissions) {
        this.props.dispatch(Actions.addRole(roleName, permissions));
    },
    editRole(role) {
        const that = this;
        return () => {
            that.context.router.push(`/admin/roles/${role.get('id')}/edit`);
        };
    },
    deleteRole(role) {
        const that = this;
        return () => {
            that.refs.confirmationDialog.show(
                <span>Delete the role <strong>{role.get("name")}</strong>? This action can not be undone.</span>,
                () => {
                    that.props.dispatch(Actions.deleteRole(role.get("id")));
                }
            );
        };
    }
});

const ReduxRoleList = connect(state => ({
    rolesById: state.get('rolesById'),
    environmentsById: state.get('environmentsById')
}))(RoleList);

export default ReduxRoleList;
