//Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).
import React from 'react';
import RepositoryForm from './forms/RepositoryForm.jsx';
import PureRenderMixin from 'react-addons-pure-render-mixin';
import * as Actions from '../../Actions';
import {Link} from 'react-router';

const RepositoryAdd = React.createClass({
    mixins: [PureRenderMixin],
    propTypes: {
        dispatch: React.PropTypes.func.isRequired
    },
    render() {
        return (<div>
            <h2>Add Repository</h2>
            <p> <Link to={"/admin/repositories/"}>back to list</Link> </p>
            <p>You will be able to add environments to this repository once it is created.</p>
            <h3>Repository Details</h3>
            <RepositoryForm onSubmit={this.addRepository} ref="repositoryForm" />
        </div>);
    },
    addRepository(repositoryName, gitServer, deployMethod, notifyOwnersMails) {
        this.props.dispatch(Actions.addRepository({repositoryName, gitServer, deployMethod, notifyOwnersMails}));
    }
});

export default RepositoryAdd;
