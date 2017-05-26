//Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).
import React from 'react';
import UserForm from './forms/UserForm.jsx';
import PureRenderMixin from 'react-addons-pure-render-mixin';
import ImmutablePropTypes from 'react-immutable-proptypes';
import * as Actions from '../../Actions';
import {Link} from 'react-router';

const UserEdit = React.createClass({
    contextTypes: {
        router: React.PropTypes.object.isRequired
    },
    mixins: [PureRenderMixin],
    propTypes: {
        user: ImmutablePropTypes.contains({
            id: React.PropTypes.number.isRequired,
            name: React.PropTypes.string.isRequired,
            email: React.PropTypes.string.isRequired,
            accountid: React.PropTypes.number.isRequired,
            rolesId: ImmutablePropTypes.listOf(React.PropTypes.number).isRequired
        }).isRequired,
        rolesById: ImmutablePropTypes.mapOf(
            ImmutablePropTypes.contains({
                id: React.PropTypes.number.isRequired,
                name: React.PropTypes.string.isRequired
            })
        ),
        dispatch: React.PropTypes.func.isRequired
    },
    resetForm() {
        this.refs.form.reset();
    },
    render() {
        return (<div>
            <h2>Edit User</h2>
            <p><Link to={"/admin/users/"}>back to list</Link></p>
            <h3>User Details</h3>
            <UserForm onSubmit={this.editUser} user={this.props.user} rolesById={this.props.rolesById} ref="form"/>
            <div className="row">
                <div className="col-sm-5 col-sm-offset-2">
                    <button className="btn btn-sm btn-warning" onClick={this.resetForm}>Reset</button>
                </div>
            </div>
        </div>);
    },
    editUser(username, email, accountid, rolesId, authTokenAllowed, authToken) {
        this.props.dispatch(Actions.editUser(this.props.user.get('id'), {username, email, accountid, roles: rolesId, authTokenAllowed, authToken}));
        this.context.router.push('/admin/users');
    }
});

export default UserEdit;
