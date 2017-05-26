//Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).
import React from 'react';
import PureRenderMixin from 'react-addons-pure-render-mixin';
import {Link} from 'react-router';
import ImmutablePropTypes from 'react-immutable-proptypes';
import * as Actions from '../Actions.js';
import Auth from '../Auth.js';
import moment from 'frozen-moment';
import SetIntervalMixin from '../mixins/SetIntervalMixin';

const HeaderBar = React.createClass({
    mixins: [PureRenderMixin, SetIntervalMixin],
    contextTypes: {
        user: ImmutablePropTypes.contains({
            username: React.PropTypes.string.isRequired
        }),
        router: React.PropTypes.object.isRequired
    },
    propTypes: {
        user: ImmutablePropTypes.contains({
            loggedIn: React.PropTypes.bool.isRequired
        }).isRequired,
        dispatch: React.PropTypes.func.isRequired,
        websocketState: ImmutablePropTypes.contains({
            lastPing: React.PropTypes.object
        }).isRequired
    },
    componentDidMount() {
        this.setInterval(this.tick, 10000);
    },
    tick() {
        this.forceUpdate();
    },
    checkLastPing() {
        return moment().diff(this.props.websocketState.get('lastPing'), 'seconds') < 50;
    },
    render() {
        return (
            <nav className="navbar navbar-default navbar-inverse">
                <div className="container-fluid">
                    <div className="col-sm-12">
                        <div className="navbar-header">
                            <span className="navbar-brand navbar-link"><Link to='/' className='navbar-link'>デプロイ</Link></span>
                        </div>
                        <div className="nav navbar-nav navbar-right">
                            { process.env.NODE_ENV === "development" ? <li><p className="navbar-text"><span className="text-warning">THIS IS A DEVELOPMENT VERSION!</span></p></li> : null } 
                            { this.checkLastPing() ? null : <li><p className="navbar-text"><span className="text-warning">Server connectivity lost, please refresh the page.</span></p></li>}
                                <li>{this.userInfo()}</li>
                                <li>{this.logLink()}</li>
                        </div>
                    </div>
                </div>
            </nav>
        );
    },
    login(evt) {
        evt.preventDefault();
        this.props.dispatch(Actions.askLogin());
    },
    logout(evt) {
        evt.preventDefault();
        this.props.dispatch(Actions.askLogout());
    },
    userInfo() {
        if(this.props.user.get('loggedIn') && this.context.user) {
            return <p className="navbar-text">Logged as {this.context.user.get('username')}</p>;
        }
        return <p className="navbar-text text-warning">Not logged in. Most features will be disabled.</p>;
    },
    logLink() {
        if(this.props.user.get('loggedIn')) {
            return <a onClick={this.logout} href="#"><span className="glyphicon glyphicon-log-out"></span> Log out</a>;
        }
        return this.props.user.get('status') == 'REQUEST' ?  <p className="navbar-text">Logging in...</p> : <a onClick={this.login} href="#" className="active"><span className="glyphicon glyphicon-log-in"></span> Log in</a>;
    }
});

export default HeaderBar;
