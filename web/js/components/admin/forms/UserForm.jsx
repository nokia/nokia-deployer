//Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).
import React from 'react';
import ImmutablePropTypes from 'react-immutable-proptypes';
import PureRenderMixin from 'react-addons-pure-render-mixin';
import LinkedStateMixin from 'react-addons-linked-state-mixin';
import FuzzyListForm from '../../lib/FuzzyListForm.jsx';
import { List } from 'immutable';

const UserForm = React.createClass({
    mixins: [PureRenderMixin, LinkedStateMixin],
    propTypes: {
        user: ImmutablePropTypes.contains({
            id: React.PropTypes.number.isRequired,
            username: React.PropTypes.string.isRequired,
            accountid: React.PropTypes.number.isRequired,
            rolesId: ImmutablePropTypes.listOf(React.PropTypes.number.isRequired),
            authTokenAllowed: React.PropTypes.bool.isRequired
        }),
        rolesById: ImmutablePropTypes.mapOf(
            ImmutablePropTypes.contains({
                id: React.PropTypes.number.isRequired,
                name: React.PropTypes.string.isRequired
            })
        ),
        onSubmit: React.PropTypes.func.isRequired
    },
    getInitialState() {
        let username = "";
        let email = "";
        let accountid = 0;
        let rolesId = [];
        let authTokenAllowed = false;
        let accountAuthAllowed = true;
        let selectedRoles = List();
        if(this.props.user) {
            const that = this;
            username = this.props.user.get('username');
            email = this.props.user.get('email');
            accountid = this.props.user.get('accountid');
            rolesId = this.props.user.get('rolesId').toList();
            authTokenAllowed = this.props.user.get('authTokenAllowed');
            accountAuthAllowed = this.props.user.get('accountid') != -1;
            selectedRoles = this.props.user.get('rolesId').map(roleId => that.props.rolesById.get(roleId)).toList();
        }
        return {
            email,
            username,
            accountid,
            rolesId,
            authToken: "",
            authTokenAllowed,
            accountAuthAllowed,
            selectedRoles
        };
    },
    reset() {
        this.setState(this.getInitialState());
    },
    onRolesChanged(roles) {
        this.setState({selectedRoles: roles});
    },
    componentWillReceiveProps(nextProps) {
        if((nextProps.user != this.props.user || nextProps.rolesById != this.props.rolesById) && nextProps.user) {
            const that = this;
            this.setState({
                selectedRoles: nextProps.user.get('rolesId').map(roleId => that.props.rolesById.get(roleId)).toList()
            });
        }
    },
    render() {
        const that = this;
        return <form className="form-horizontal">
            <div className="form-group">
                <label className="col-sm-2 control-label">Name</label>
                <div className="col-sm-5">
                    <input name="username" type="text" placeholder="jdoe" className="form-control" valueLink={this.linkState('username')} />
                </div>
            </div>
            <div className="form-group">
                <label className="col-sm-2 control-label">Email</label>
                <div className="col-sm-5">
                    <input name="email" type="text" className="form-control" valueLink={this.linkState('email')} />
                </div>
            </div>
            <div className="form-group" >
                <div className="col-sm-offset-2 col-sm-5"  data-toggle="tooltip" data-placement="right" title="For human users." ref="tooltip1">
                    <div className="checkbox row">
                        <label>
                            <input type="checkbox" checkedLink={that.linkState('accountAuthAllowed')}/> Allow authentification using a session ID
                        </label>
                    </div>
                </div>
            </div>
            { that.state.accountAuthAllowed ?
                <div className="form-group">
                    <label className="col-sm-2 control-label">Account ID</label>
                    <div className="col-sm-5" data-toggle="tooltip">
                        <input name="accountid" type="number" className="form-control" valueLink={this.linkState('accountid')} />
                    </div>
                </div>
                :
                null
            }
            <div className="form-group" >
                <div className="col-sm-offset-2 col-sm-5"  data-toggle="tooltip" data-placement="right" title="For services interfacing with the deployer." ref="tooltip2">
                    <div className="checkbox row">
                        <label>
                            <input type="checkbox" checkedLink={that.linkState('authTokenAllowed')}/> Allow token authentification
                        </label>
                    </div>
                </div>
            </div>
            { that.state.authTokenAllowed ?
                <div className="form-group">
                    <label className="col-sm-2 control-label">New Authentification Token</label>
                    <div className="col-sm-5" data-toggle="tooltip" data-placement="right" title="Leave this empty to keep the existing token." ref="tooltip3">
                        <input name="accountid" type="text" className="form-control" valueLink={this.linkState('authToken')} />
                    </div>
                </div>
                :
                null
            }
            <div className="form-group">
                <label className="col-sm-2 control-label">Roles</label>
                <div className="col-sm-5">
                    <FuzzyListForm
                        onChange={this.onRolesChanged}
                        elements={this.props.rolesById.toList()}
                        selectedElements={this.state.selectedRoles}
                        renderElement={role => role.get('name')}
                        placeholder=""
                        compareWith={role => role.get('name')} />
                </div>
            </div>
            <div className="form-group">
                <div className="col-sm-5 col-sm-offset-2">
                    <button type="button" onClick={this.onSubmit} className="btn btn-default">Submit</button>
                </div>
            </div>
        </form>;
    },
    componentDidUpdate() {
        this.attachTooltip();
    },
    attachTooltip() {
        $(this.refs.tooltip1).tooltip();
        $(this.refs.tooltip2).tooltip();
        $(this.refs.tooltip3).tooltip();
    },
    onSubmit() {
        let accountid = this.state.accountid;
        if(!this.state.accountAuthAllowed) {
            accountid = -1;
        }
        this.props.onSubmit(this.state.username, this.state.email, accountid, this.state.selectedRoles.map(role => role.get('id')).toJS(), this.state.authTokenAllowed, this.state.authToken);
    }
});

export default UserForm;
