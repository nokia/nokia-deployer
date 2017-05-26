//Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).
import React from 'react';
import { bindActionCreators } from 'redux';
import { connect } from 'react-redux';
import { contains } from 'react-immutable-proptypes';
import { Map } from 'immutable';
import * as Actions from '../Actions';


const Login = ({user, askLogin, useGuestUser}) => (
    <div>
        <div className="container-fluid">
            <div className="col-md-12">
                <h2>デプロイ (also known as the deployer) says hi!</h2>
                { user.get('status') == "NONE" ?
                <div>
                    <p>Do you have a deployer account?</p>
                    <div className="btn-group">
                        <button onClick={askLogin} className="btn btn-primary">Log in</button>
                        <button className="btn btn-default" onClick={useGuestUser}>Continue as guest</button>
                    </div>
                </div>
                : user.get('status') == "REQUEST" ?
                <p>Hold tight, I am logging you in...</p>
                : user.get('status') == "ERROR" ?
                <p>I could not log you in, but you can still access the deployer as guest.</p> :
                <p>Good news: your login was successful. Bad news: if you are seeing this, this is a bug (you should have been redirected).</p>
                }
            </div>
        </div>
        <div className="navbar navbar-fixed-bottom">
            <div className="container-fluid">
                <div className="col-md-12">
                    { process.env.REFERENCE_MAIL ?
                        <p>Need insider access? Want to report a bug or ask for a feature? Questions? Remarks? Complaints? <a href={`mailto:${process.env.REFERENCE_MAIL}`}>{process.env.REFERENCE_MAIL}</a>.</p>
                        : null
                    }
                </div>
            </div>
        </div>
    </div>
);


Login.defaultProps = {
    user: Map({
        id: null,
        status: "NONE"
    })
};

Login.propTypes = {
    user: contains({
        id: React.PropTypes.number,
        status: React.PropTypes.oneOf(["NONE", "REQUEST", "SUCCESS", "ERROR"])
    })
};


export const LoginHandler = connect(
    state => ({user: state.get('user')}),
    dispatch => ({
        askLogin: bindActionCreators(Actions.askLogin, dispatch),
        useGuestUser: bindActionCreators(Actions.useGuestUser, dispatch)
    })
)(Login);

export default LoginHandler;
