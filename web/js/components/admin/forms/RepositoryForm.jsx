//Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).
import React from 'react';
import ImmutablePropTypes from 'react-immutable-proptypes';
import LinkedStateMixin from 'react-addons-linked-state-mixin';
import PureRenderMixin from 'react-addons-pure-render-mixin';

// does not include environments, since it is expected that EnvironmentForm components will be displayed on
// the same page
const RepositoryForm = React.createClass({
    mixins: [PureRenderMixin, LinkedStateMixin],
    propTypes: {
        repository: ImmutablePropTypes.contains({
            id: React.PropTypes.number.isRequired,
            name: React.PropTypes.string.isRequired,
            gitServer: React.PropTypes.string.isRequired,
            deployMethod: React.PropTypes.oneOf(['symlink', 'inplace']),
            notifyOwnersMails: ImmutablePropTypes.listOf(React.PropTypes.string).isRequired,
        }),
        // accepts: repositoryName (string), gitServer (string), deployMethod (string)
        onSubmit: React.PropTypes.func.isRequired
    },
    getInitialState() {
        return {
            repositoryName: this.props.repository ? this.props.repository.get('name') : "",
            gitServer: this.props.repository ? this.props.repository.get('gitServer') : "",
            deployMethod: this.props.repository ? this.props.repository.get('deployMethod') : "inplace",
            notifyOwnersMails: this.props.repository ? this.props.repository.get('notifyOwnersMails').join(', ') : ""
        };
    },
    render() {
        return (
            <form className="form-horizontal">
                <div className="form-group">
                    <label className="col-sm-2 control-label" >Name</label>
                    <div className="col-sm-5">
                        <input className="form-control" type="text" placeholder="my_project" valueLink={this.linkState('repositoryName')} />
                    </div>
                </div>
                <div className="form-group">
                    <label className="col-sm-2 control-label" >Git Server</label>
                    <div className="col-sm-5">
                        <input className="form-control" type="text" placeholder="git.example.com" valueLink={this.linkState('gitServer')} />
                    </div>
                </div>
                <div className="form-group">
                    <label className="col-sm-2 control-label" >Deploy Method</label>
                    <div className="col-sm-5">
                        <select className="form-control" type="text" valueLink={this.linkState('deployMethod')}>
                            <option value="inplace">inplace</option>
                            <option value="symlink">symlink</option>
                        </select>
                    </div>
                </div>
                <div className="form-group">
                    <label className="col-sm-2 control-label" >Notify mails</label>
                    <div className="col-sm-5">
                        <input className="form-control" type="text" placeholder="gitpush@example.com" valueLink={this.linkState('notifyOwnersMails')} />
                    </div>
                </div>
                <div className="form-group">
                    <div className="col-sm-5 col-sm-offset-2">
                        <button type="button" onClick={this.onSubmit} className="btn btn-default">Submit</button>
                    </div>
                </div>
            </form>
        );
    },
    reset() {
        this.setState(this.getInitialState());
    },
    onSubmit() {
        const notifyOwnersMails = this.state.notifyOwnersMails.split(',').map(str => str.trim());
        this.props.onSubmit(this.state.repositoryName, this.state.gitServer, this.state.deployMethod, notifyOwnersMails);
    }
});

export default RepositoryForm;
