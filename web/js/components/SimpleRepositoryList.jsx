//Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).
import React from 'react';
import ImmutablePropTypes from 'react-immutable-proptypes';
import PureRenderMixin from 'react-addons-pure-render-mixin';
import {Link} from 'react-router';

const SimpleRepositoryList = React.createClass({
    mixins: [PureRenderMixin],
    propTypes: {
        repositoriesById: ImmutablePropTypes.mapOf(
            ImmutablePropTypes.contains({
                id: React.PropTypes.number.isRequired,
                name: React.PropTypes.string.isRequired
            })
        )
    },
    render() {
        return <ul className="list-unstyled">
            { this.props.repositoriesById.toList().sort((r1, r2) => r1.get('name').localeCompare(r2.get('name'))).map(repository => <li key={repository.get('id')}><Link to={`/repositories/${repository.get('id')}`}>{repository.get('name')}</Link></li>)}
            <li>
            </li>
        </ul>;
    }
});

export default SimpleRepositoryList;
