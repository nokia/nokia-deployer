//Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).
import React from 'react';
import {Link} from 'react-router';
import ImmutablePropTypes from 'react-immutable-proptypes';

const Menu = React.createClass({
    contextTypes: {
        user: ImmutablePropTypes.contains({
            isSuperAdmin: React.PropTypes.bool
        })
    },
    shouldComponentUpdate(nextProps, nextState, nextContext) {
        return nextContext.user !== this.context.user;
    },
    render() {
        return (
            <div>
                <h4>Deployments</h4>
                <ul className="nav nav-pills nav-stacked">
                    <li><Link activeClassName="active" to="/deployments/recent">Recent activity</Link></li>
                    <li><Link activeClassName="active" to="/repositories">Repositories</Link></li>
                </ul>
                { this.context.user && this.context.user.get('isSuperAdmin') ? 
                    <div>
                        <h4>Admin</h4>
                        <ul className="nav nav-pills nav-stacked">
                            <li><Link activeClassName="active" to="/admin/repositories">Repositories</Link></li>
                            <li><Link activeClassName="active" to="/admin/servers">Servers</Link></li>
                            <li><Link activeClassName="active" to="/admin/clusters">Clusters</Link></li>
                            <li><Link activeClassName="active" to="/admin/users">Users</Link></li>
                            <li><Link activeClassName="active" to="/admin/roles">Roles</Link></li>
                        </ul>
                    </div>
                : 
                    null
                }
            </div>
        );
    }
});


export default Menu;
