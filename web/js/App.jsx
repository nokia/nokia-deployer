//Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).
import * as Redux from 'redux';
import React from 'react';
import { connect, Provider } from 'react-redux';
import ReduxThunk from 'redux-thunk';
import ReduxLogger from 'redux-logger';
import WebSockGateway from 'WebSockGateway';
import * as Actions from 'Actions';
import AppComponent from 'components/App.jsx';
import Repositories from 'components/Repositories.jsx';
import RepositoryDetails from 'components/RepositoryDetails.jsx';
import {DeploymentHistoryHandler} from 'components/DeploymentHistory.jsx';
import DeploymentDetails from 'components/DeploymentDetails.jsx';
import RecentDeployments from 'components/RecentDeployments.jsx';
import ReactDOM from 'react-dom';
import Reducers from 'Reducers';
import { syncHistory } from 'react-router-redux';
import Admin from 'components/admin/Admin.jsx';
import ServerList from 'components/admin/ServerList.jsx';
import ServerEdit from 'components/admin/ServerEdit.jsx';
import ClusterList from 'components/admin/ClusterList.jsx';
import ClusterEdit from 'components/admin/ClusterEdit.jsx';
import RepositoryList from 'components/admin/RepositoryList.jsx';
import RepositoryEdit from 'components/admin/RepositoryEdit.jsx';
import RepositoryAdd from 'components/admin/RepositoryAdd.jsx';
import EnvironmentAdd from 'components/admin/EnvironmentAdd.jsx';
import UserList from 'components/admin/UserList.jsx';
import RoleList from 'components/admin/RoleList.jsx';
import RoleEdit from 'components/admin/RoleEdit.jsx';
import UserEdit from 'components/admin/UserEdit.jsx';
import NotFound from 'components/NotFound.jsx';
import {Router} from 'react-router';
import {Route} from 'react-router';
import {browserHistory} from 'react-router';
import moment from 'frozen-moment';
import Auth from './Auth.js';
import { ServerReleases } from 'components/admin/ServerReleases.jsx'

const logger = ReduxLogger({
    stateTransformer(state) {
        return state.toJS();
    },
    predicate(getState, action) {
        if(process.env.NODE_ENV === "development") {
            return !(action.payload && action.payload.status === 'REQUEST');
        }
        return false;
    }
});

const reduxRouterMiddleware = syncHistory(browserHistory, state => state.get('routing'));

const applyMiddleware = Redux.applyMiddleware(
    reduxRouterMiddleware,
    ReduxThunk,
    logger
);

const createMyStore = applyMiddleware;


function App() {
    this.store = createMyStore(Redux.createStore)(Reducers.app);
    const that = this;

    function connectWebsocketToRedux() {
        WebSockGateway.listen('deployment.deployment_status', data => {
            that.store.dispatch(Actions.updateDeployment(data.payload));
        });
        WebSockGateway.listen('deployment.step.release', data => {
            that.store.dispatch(Actions.updateServerStatus(
                data.payload.server.id,
                data.payload.release_info.release_date,
                data.payload.release_info.branch,
                data.payload.release_info.commit,
                data.payload.environment_id
            ));
        });
        WebSockGateway.listen('commits.fetched', data => {
            that.store.dispatch(Actions.loadEnvironmentCommits(data.payload.environment_id));
        });
        WebSockGateway.listen('websocket.pong', () => {
            that.store.dispatch(Actions.websocketPinged(moment().freeze()));
        });
    }

    const connectAuthToRedux = () => {
        Auth.listen(event => {
            if(event.type == 'login_success') {
                that.store.dispatch(Actions.loginFlowSuccess(event.payload.user));
            } else if(event.type == 'login_failed') {
                that.store.dispatch(Actions.loginFlowError(event.payload.user));
            } else if(event.type == 'login_start') {
                that.store.dispatch(Actions.loginFlowStarted());
            }
        });
    };

    this.kickoff = () => {
        connectWebsocketToRedux();
        connectAuthToRedux();
        Auth.initLogin();
        ReactDOM.render(
            <Provider store={that.store}>
                <Router history={browserHistory}>
                    <Route path="/" component={AppComponent}>
                        <Route path="repositories" component={Repositories}>
                            <Route path=":id" component={RepositoryDetails} />
                            <Route path=":id/deployments" component={DeploymentHistoryHandler} />
                        </Route>
                        <Route path="deployments/recent" component={RecentDeployments} />
                        <Route path="deployments/:id" component={DeploymentDetails} />
                        <Route path="admin" component={Admin}>
                            <Route path="servers/:id/releases" component={ServerReleases} />
                            <Route path="servers" component={ServerList} >
                                <Route path=":id/edit" component={ServerEdit} />
                            </Route>
                            <Route path="clusters" component={ClusterList} >
                                <Route path=":id/edit" component={ClusterEdit} />
                            </Route>
                            <Route path="users" component={UserList} >
                                <Route path=":id/edit" component={UserEdit} />
                            </Route>
                            <Route path="roles" component={RoleList}>
                                <Route path=":id/edit" component={RoleEdit} />
                            </Route>
                            <Route path="repositories" component={RepositoryList}>
                                <Route path="new" component={RepositoryAdd} />
                                <Route path=":id/edit" component={RepositoryEdit} />
                                <Route path=":id/environments/new" component={EnvironmentAdd} />
                            </Route>
                        </Route>
                        <Route path="*" component={NotFound} />
                    </Route>
                </Router>
            </Provider>,
            document.getElementById('app-container'));
    };
}

export default App;
