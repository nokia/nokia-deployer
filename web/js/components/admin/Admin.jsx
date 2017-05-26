//Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).
import React from 'react';
import {Link} from 'react-router';

const Admin = React.createClass({
    render() {
        if(this.props.children) {
            return this.props.children
        }
        return (
            <div>
                <h2>Administration</h2>
                <p>Use the menu on the left</p>
            </div>
        )
    }
});

export default Admin;
