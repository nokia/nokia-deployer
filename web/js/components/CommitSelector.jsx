//Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).
import React from 'react';
import PureRenderMixin from 'react-addons-pure-render-mixin';
import ImmutablePropTypes from 'react-immutable-proptypes';

// TODO: make this a simpler controlled component
const CommitSelector = React.createClass({
    mixins: [PureRenderMixin],
    propTypes: {
        currentCommit: React.PropTypes.string,
        commits: ImmutablePropTypes.listOf(
            ImmutablePropTypes.contains({
                hexsha: React.PropTypes.string.isRequired,
                authoredDate: React.PropTypes.number.object,
                committer: React.PropTypes.string.isRequired
            })
        ),
        onChange: React.PropTypes.func,
    },
    render() {
        const that = this;
        if(!this.props.commits) {
            return <p>Loading commit data...</p>
        }
        const isCurrentCommit = this.props.currentCommit 
        return (
            <select className='form-control input-sm' onChange={this.onChange} ref={this.registerSelect}>
                {this.props.commits.map(commit => 
                    <CommitDetailsOption
                        key={commit.get('hexsha')}
                        commit={commit}
                        isCurrentCommit={commit.get('hexsha') == that.props.currentCommit} />
                )}
            </select>
        )
    },
    onChange(evt) {
        if(this.props.onChange) {
            this.props.onChange(evt.target.value);
        }
    },
    registerSelect(el) {
        this.select = el;
    },
    getSelectedCommit() {
        if(this.select) {
            return this.select.value;
        }
        return null;
    }
});

const CommitDetailsOption = ({commit, isCurrentCommit}) => 
    <option value={commit.get('hexsha')}>
        {formatCommitHash(commit.get('hexsha'), isCurrentCommit)}{' '}
        [{ commit.get('authoredDate').format('YYYY-MM-DD HH:mm') }]{' '}
        [{commit.get('committer')}]{' '}
        {formatCommitMessage(commit.get('message'))}
    </option>

const formatCommitHash = (hash, isCurrentCommit) => {
        let leader = " ";
        if(isCurrentCommit) {
            leader = "*";
        }
        return leader + hash.substring(0, 9);
}

const formatCommitMessage = (message) => {
        const MAX_LENGTH = 80;
        if(message.length > 80) {
            return `${message.substring(0, MAX_LENGTH - 3)}...`;
        }
        return message;
}

export default CommitSelector;
