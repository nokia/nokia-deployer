//Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).
import React from 'react';
import ImmutablePropTypes from 'react-immutable-proptypes';
import PureRenderMixin from 'react-addons-pure-render-mixin';
import { connect } from 'react-redux';
import * as Actions from '../../Actions';
import {Link} from 'react-router';
import UserForm from './forms/UserForm.jsx';
import ConfirmationDialog from '../lib/ConfirmationDialog.jsx';

const UserList = React.createClass({
    mixins: [PureRenderMixin],
    contextTypes: {
        user: React.PropTypes.object
    },
    propTypes: {
        usersById: ImmutablePropTypes.mapOf(
            ImmutablePropTypes.contains({
                id: React.PropTypes.number.isRequired,
                username: React.PropTypes.string.isRequired,
                email: React.PropTypes.string.isRequired,
                accountid: React.PropTypes.number.isRequired,
                rolesId: ImmutablePropTypes.listOf(React.PropTypes.number.isRequired)
            })
        ),
        rolesById: ImmutablePropTypes.mapOf(
            ImmutablePropTypes.contains({
                id: React.PropTypes.number.isRequired,
                name: React.PropTypes.string.isRequired
            })
        ),
        dispatch: React.PropTypes.func.isRequired
    },
    fetchData() {
        this.props.dispatch(Actions.loadUsers());
        this.props.dispatch(Actions.loadRoles());
    },
    componentWillMount() {
        this.fetchData();
    },
    componentWillReceiveProps(nextProps, nextContext) {
	// FIXME
        // if(!nextContext.user || !this.context.user || nextContext.user.get('id') != this.context.user.get('id')) {
        //     this.fetchData();
        // }
    },
    render() {
        const that = this;
        if(this.props.children) {
            const userId = parseInt(this.props.params.id, 10);
            const user = this.props.usersById.get(userId);
            if(!user) {
                return <h2>This user does not exist.</h2>;
            }
            return React.cloneElement(this.props.children, {user, dispatch: this.props.dispatch, rolesById: this.props.rolesById});
        }
        return <div>
            <h2>Users</h2>
            <h3>New User</h3>
            <UserForm onSubmit={this.addUser} rolesById={this.props.rolesById} />
            <h3>User List</h3>
            <table className="table table-striped">
                <thead>
                    <tr>
                        <td>ID</td>
                        <td>Username</td>
                        <td>Email</td>
                        <td title="As defined in the backend.">Account ID</td>
                        <td>Roles</td>
                        <td>Actions</td>
                    </tr>
                </thead>
                <tbody>
                    { this.props.usersById.sort((u1, u2) => u1.get('username').localeCompare(u2.get('username'))).map(user => <tr key={user.get('id')}>
                        <td>{user.get('id')}</td>
                        <td>{user.get('username')}</td>
                        <td>{user.get('email')}</td>
                        <td>{user.get('accountid')}</td>
                        <td>{that.formatRoles(user.get('rolesId'))}</td>
                        <td>
                                <Link className="btn btn-default btn-sm" to={`/admin/users/${user.get('id')}/edit`}>Edit</Link>
                                <button className="btn btn-sm btn-danger" type="button" onClick={that.deleteUser(user)}>Delete</button>
                        </td>
                    </tr>).toList()}
                </tbody>
            </table>
            <ConfirmationDialog ref="confirmationDialog" />
        </div>;
    },
    formatRoles(rolesId) {
        const that = this;
        return rolesId.map(roleId => {
            const role = that.props.rolesById.get(roleId);
            if(!role) {
                return <Link key={roleId} to={`/admin/roles/${roleId}`}>...</Link>;
            }
            return <Link key={roleId} to={`/admin/roles/${roleId}/edit`}>{role.get('name')} </Link>;
        }).toJS();
    },
    deleteUser(user) {
        const that = this;
        return () => {
            that.refs.confirmationDialog.show(
                <span>Delete the user <strong>{user.get("username")}</strong>? This action can not be undone.</span>,
                () => {
                    that.props.dispatch(Actions.deleteUser(user.get("id")));
                }
            );
        };
    },
    addUser(username, email, accountid, rolesId, authTokenAllowed, authToken) {
        if(!authTokenAllowed) {
            authToken = null;
        }
        this.props.dispatch(Actions.addUser({username, email, accountid, roles: rolesId, authToken}));
    }
});

const ReduxUserList = connect(state => ({
    usersById: state.get('usersById'),
    rolesById: state.get('rolesById')
}))(UserList);

export default ReduxUserList;
