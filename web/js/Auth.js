//Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).
import Cookies from 'cookies-js';


const Auth = function() {

    this.daemonUrl = `${window.location.protocol}//${window.location.hostname}`;
    this._listeners = [];
    this._pendingRequests = [];
    this._loginInProgress = false;

    this.initLogin = () => {
        if(Cookies.get('deployer-hasloggedin')) {
            this.login();
        }
    };

    // Add a X-Session-ID header to the request, add append the daemonUrl before path
    this.request = function(path, success, error = error => console.error(error), method='GET', data) {
        // if we no longer have a session and know we had one at some point, try to login before going on
        if((Cookies.get('deployer-hasloggedin') && !Cookies.get('deployer-session')) || this._loginInProgress) {
            this._pendingRequests.push({path, success, error, method, data});
            if(!this._loginInProgress) {
                const that = this;
                this.login(() => that._processPendingRequests());
            }
            return;
        }
        this._performRequest(path, success, error, method, data);
    };

    this._performRequest = function(path, success, error, method, data) {
        if(path.substring(0, 1) != '/') {
            path = `/${path}`;
        }
        if(path.substring(0, 4) != '/api') {
            path = `/api${path}`;
        }
        fetch(this.daemonUrl + path, {
            method,
            headers: this._makeHeaders(),
            body: data
        }).then(response => {
            if(!response.ok) {
                error(`Server returned status ${response.status}`);
                return;
            }
            response.json().then(data => success(data));
        });
    };

    this._processPendingRequests = () => {
        const that = this;
        this._pendingRequests.map(({path, success, error, method, data}) => {
            that.request(path, success, error, method, data);
        });
        this._pendingRequests = [];
    };

    this.getJSON = function(path, success, error) {
        this.request(path, success, error, 'GET');
    };

    // data must will be converted to JSON before being posted
    this.postJSON = function(path, data, success, error) {
        const json = JSON.stringify(data);
        this.request(path, success, error, 'POST', json);
    };

    this.deleteJSON = function(path, success, error) {
        this.request(path, success, error, 'DELETE');
    };

    this.putJSON = function(path, data, success, error) {
        const json = JSON.stringify(data);
        this.request(path, success, error, 'PUT', json);
    };

    // Inits a login flow. Events "login_failed" or "login_success" will be emitted when the flow is complete.
    // The flow ends with a call to either _emitLoggedIn, _emitLogginFailed, or a redirection to account.
    this.login = (cb = () => null) => {
        if(this._loginInProgress) {
            return;
        }
        this._emitStartLoginFlow();
        this._loginInProgress = true;
        const sessionid = Cookies.get('session-admin_key');
        if(!sessionid) {
            this._redirectToAccount();
        }
        const deployerToken = Cookies.get('deployer-session');
        if(deployerToken) {
            this._validateSession().then(
                user => {this._emitLoggedIn(deployerToken, user, false); cb();},
                () => {Cookies.expire('deployer-session'); this._createSession(cb);}
            );
            return;
        }
        this._createSession(cb);
    };

    this.logout = () => {
        Cookies.expire('deployer-hasloggedin');
        Cookies.expire('deployer-session');
    };

    this._redirectToAccount = () => {
        window.location = process.env.AUTH_PAGE.replace('{originUrl}', encodeURIComponent(window.location.href));
    };

    this._validateSession = () => {
        return new Promise((resolve, reject) => {
            this._performRequest("/account", response => {
                if(response.user.username == "default") {
                    reject();
                    return;
                }
                resolve(response.user);
            }, () => reject(), 'GET');
        });
    };

    this._createSession = (cb) => {
        const that = this;
        fetch(this.daemonUrl + '/api/auth/wssession', {
            body: JSON.stringify({sessionid: Cookies.get(process.env.SESSIONID_COOKIE)}),
            method: 'POST',
            headers: this._makeHeaders()
        }).then(response => {
            if(response.ok) {
                response.json().then(body => {
                    this._emitLoggedIn(body.token, body.user, true);
                    cb();
                });
                return;
            } else if(response.status == '403') {
                // no matching user in the deployer DB
                that._emitLoginFailed();
            } else if(response.status == '400') {
                // invalid session ID given
                that._redirectToAccount();
            }
        });
    };

    this._emitLoggedIn = (token, user, writeToken = false) => {
        this._loginInProgress = false;
        // Must expire before the session on the server (currently 30 minutes)
        if(writeToken) {
            Cookies.set('deployer-session', token, {expires: 60 * 20});
        }
        Cookies.set('deployer-hasloggedin', true, {expires: 60 * 60 * 24 * 365});
        this._emit("login_success", { user });
    };

    this._emitLoginFailed = () => {
        this._loginInProgress = false;
        Cookies.expire('deployer-hasloggedin');
        Cookies.expire('deployer-session');
        this._emit("login_failed");
    };

    this._emitStartLoginFlow = () => {
        this._loginInProgress = true;
        this._emit("login_start");
    };

    this.listen = listener => {
        this._listeners.push(listener);
    };

    this.removeListener = listener => {
        const index = this._listeners.indexOf(listener);
        if (index > -1) {
            this._listeners.splice(index, 1);
        }
    };

    this._emit = (type, payload = {}) => {
        const event = {type, payload};
        this._listeners.map(listener => listener(event));
    };

    this._makeHeaders = () => {
        const headers = new Headers({
            "Content-Type": "application/json",
        });
        const token = Cookies.get('deployer-session');
        if(token) {
            headers.append('X-Session-Token', token);
        }
        return headers;
    };

};

const appAuth = new Auth();


export default appAuth;
