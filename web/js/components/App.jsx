//Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).
import HeaderBar from './HeaderBar.jsx';
import Menu from './Menu.jsx';
import DiffModal from 'components/DiffModal.jsx';
import Alert from 'components/Alert.jsx';
import { connect } from 'react-redux';
import React from 'react';
import RepositorySelector from 'components/RepositorySelector.jsx';
import * as Actions from '../Actions';
import Cookies from 'cookies-js';
import ImmutablePropTypes from 'react-immutable-proptypes';
import SimpleRepositoryList from 'components/SimpleRepositoryList.jsx';
import Login from './Login.jsx';
import Auth from 'Auth';

const ReduxDiffModal = connect(state => ({
    diff: state.get('diff')
}))(DiffModal);

const App = React.createClass({
    contextTypes: {
        router: React.PropTypes.object.isRequired
    },
    childContextTypes: {
        user: ImmutablePropTypes.contains({
            isSuperAdmin: React.PropTypes.bool,
            username: React.PropTypes.string.isRequired
        })
    },
    getChildContext() {
        return {
            user: this.props.usersById.get(this.props.user.get('userId'))
        };
    },
    componentWillMount() {
        this.props.dispatch(Actions.loadRepositories());
    },
    componentWillReceiveProps(nextProps) {
        if(this.props.user !== nextProps.user) {
            if(nextProps.user.get('loggedIn')) {
                this.props.dispatch(Actions.loadRepositories());
            }
        }
    },
    render() {
        const that = this;
        const now = new Date();
        return (
            <div>
                <HeaderBar user={that.props.user} dispatch={that.props.dispatch} websocketState={that.props.websocketState}/>
                { this.props.user.get('status') != "SUCCESS" ? <Login /> :
                <div className="container-fluid">
                    <div className='col-md-2 sidemenu'><Menu /></div>
                    <div className='col-md-10'>
                        {
                            this.props.alertsById.toList().sortBy(alert => alert.get('addedAt')).map(alert => <Alert key={alert.get('id')} alert={alert} dispatch={that.props.dispatch}/>)
                        }
                        {
                            this.props.children ?
                                this.props.children
                        :
                            <div>
                                <h2>デプロイ (also known as the deployer) says hi!</h2>
                                <p>Use the menu to get started, or select a repository below.</p>
                                <RepositorySelector repositories={this.props.repositoriesById.toList()} onRepositorySelected={this.onRepositorySelected}/>
                                <h4>Available repositories</h4>
                                <SimpleRepositoryList repositoriesById={this.props.repositoriesById} />
                            </div>
                        }
                    </div>
                </div> }
                <ReduxDiffModal />
            </div>
        );
    },
    onRepositorySelected(repository) {
        this.context.router.push(`/repositories/${repository.get('id')}`);
    }
});

export const AppComponent = connect(
    state => ({
        repositoriesById: state.get('repositoriesById'),
        environmentsById: state.get('environmentsById'),
        deploymentsById: state.get('deploymentsById'),
        clustersById: state.get('clustersById'),
        user: state.get('user'),
        usersById: state.get('usersById'),
        routing: state.get('routing'),
        alertsById: state.get('alertsById'),
        websocketState: state.get('websocketState')
    })
)(App);

export default AppComponent;
