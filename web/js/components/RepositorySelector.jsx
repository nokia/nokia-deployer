//Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).
import React from 'react';
import ImmutablePropTypes from 'react-immutable-proptypes';
import FuzzyInput from './lib/FuzzyInput.jsx';
import PureRenderMixin from 'react-addons-pure-render-mixin';

const RepositorySelector = React.createClass({
    mixins: [PureRenderMixin],
    propTypes: {
        repositories: ImmutablePropTypes.listOf(
            ImmutablePropTypes.contains({
                name: React.PropTypes.string.isRequired
            })
        ).isRequired,
        onRepositorySelected: React.PropTypes.func.isRequired
    },
    render() {
        return (
            <form className="form-horizontal row">
                <div className="form-group>">
                    <label className="control-label col-sm-1">Repository</label>
                    <div className="col-sm-7">
                        <FuzzyInput
                            elements={this.props.repositories}
                            onElementSelected={this.props.onRepositorySelected}
                            renderElement={repo => repo.get('name')}
                            placeholder="repository name"
                            compareWith={repo => repo.get('name')} />
                    </div>
                </div>
            </form>
        )
    }
});

export default RepositorySelector;
