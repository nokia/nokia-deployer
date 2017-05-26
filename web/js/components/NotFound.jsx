//Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).
import React from 'react';
import PureRenderMixin from 'react-addons-pure-render-mixin';
import {Link} from 'react-router';

const NotFound = React.createClass({
    mixins: [PureRenderMixin],
    render() {
        return <div>
            <h2>Nothing here.</h2>
            <p>Use the menu to get back on track, or go to the <Link to="/">homepage</Link>.</p>
        </div>;
    }
});

export default NotFound;
