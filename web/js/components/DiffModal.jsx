//Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).
import React from 'react';
import * as Actions from '../Actions.js';
import BootstrapModal from './lib/BootstrapModal.jsx';
import ImmutablePropTypes from 'react-immutable-proptypes';
import PureRenderMixin from 'react-addons-pure-render-mixin';

const DiffModal = React.createClass({
    mixins: [PureRenderMixin],
    propTypes: {
        dispatch: React.PropTypes.func.isRequired,
        diff: ImmutablePropTypes.contains({
            visible: React.PropTypes.bool.isRequired,
            toSha: React.PropTypes.string,
            fromSha: React.PropTypes.string,
            message: React.PropTypes.string
        }).isRequired
    },
    render() {
        return (
            <BootstrapModal onModalHidden={this.onModalHidden} visible={this.props.diff.get('visible')}>
                <DiffContents diff={this.props.diff} dispatch={this.props.dispatch}/>
            </BootstrapModal>
        )
    },
    onModalHidden() {
        this.props.dispatch(Actions.hideDiff());
    }
});

const DiffContents = React.createClass({
    mixins: [PureRenderMixin],
    propTypes: {
        diff: ImmutablePropTypes.contains({
            visible: React.PropTypes.bool.isRequired,
            html: React.PropTypes.string
        }).isRequired
    },
    parseDiff() {
        if(this.props.diff.get('message') == null) {
            return <p>Loading...</p>;
        }
        const lines = this.props.diff.get('message').split('\n');
        const out = [];
        for(let i = 0, len = lines.length; i < len; i++) {
            const line = lines[i];
            if(line.substring(0, 10) == 'diff --git') {
                out.push(<h5 key={i}>{line}</h5>);
            } else if(line.substring(0,1) == '-') {
                out.push(<p key={i} className="text-danger">{line}</p>);
            } else if(line.substring(0,1) == '+') {
                out.push(<p key={i} className="text-success">{line}</p>);
            } else if(line.substring(0,2) == '@@') {
                out.push(<h6 key={i}>{line}</h6>);
            } else {
                out.push(<p key={i}>{line}</p>);
            }
        }
        return out;
    },
    render() {
        const diff = this.props.diff;
        return (
            <div>
                <div className="modal-header">
                    <h4 className="modal-title">Diff {diff.get('fromSha')}..{diff.get('toSha')}</h4>
                    <button type="button" className="close" onClick={this.onCloseButtonClicked}><span>&times;</span></button>
                </div>
                <div className="modal-body diff">
                    { this.parseDiff() }
                </div>
            </div>
        )
    },
    onCloseButtonClicked() {
        this.props.dispatch(Actions.hideDiff());
    }
});

export default DiffModal;
