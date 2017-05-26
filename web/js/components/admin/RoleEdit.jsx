//Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).
import React from 'react';
import RoleForm from './forms/RoleForm.jsx';
import PureRenderMixin from 'react-addons-pure-render-mixin';
import ImmutablePropTypes from 'react-immutable-proptypes';
import * as Actions from '../../Actions';
import {Link} from 'react-router';

const RoleEdit = React.createClass({
    contextTypes: {
        router: React.PropTypes.object.isRequired
    },
    mixins: [PureRenderMixin],
    propTypes: {
        role: ImmutablePropTypes.contains({
            id: React.PropTypes.number.isRequired,
            name: React.PropTypes.string.isRequired
        }).isRequired,
        environmentsById: ImmutablePropTypes.mapOf(
            ImmutablePropTypes.contains({
                id: React.PropTypes.number.isRequired,
                name: React.PropTypes.string.isRequired,
                repositoryName: React.PropTypes.string.isRequired
            })
        ),
        dispatch: React.PropTypes.func.isRequired
    },
    resetForm() {
        this.refs.form.reset();
    },
    render() {
        return (<div>
            <h2>Edit Role</h2>
            <p><Link to={"/admin/roles/"}>back to list</Link></p>
            <h3>Role Details</h3>
            <RoleForm onSubmit={this.editRole} role={this.props.role} environmentsById={this.props.environmentsById} ref="form"/>
            <div className="row">
                <div className="col-sm-5 col-sm-offset-2">
                    <button className="btn btn-sm btn-warning" onClick={this.resetForm}>Reset</button>
                </div>
            </div>
        </div>);
    },
    editRole(roleName, permissions) {
        this.props.dispatch(Actions.updateRole(this.props.role.get('id'), roleName, permissions));
        this.context.router.push('/admin/roles');
    }
});

export default RoleEdit;
