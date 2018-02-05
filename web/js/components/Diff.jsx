//Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).
import React from 'react';
import { Link } from 'react-router';
import { bindActionCreators } from 'redux';
import { connect } from 'react-redux';
import { fetchDiff, loadRepository } from '../Actions.js';
import PureRenderMixin from 'react-addons-pure-render-mixin';
import SimpleRepositoryList from './SimpleRepositoryList.jsx';


const parseDiff = (message) => {
    if(message == null) {
        return;
    }
    const out = [];
    const lines = message.split('\n');
    for(let i = 0, len = lines.length; i < len; i++) {
        const line = lines[i];
        if(line.substring(0, 10) == 'diff --git') {
            out.push(<h4 key={i}>{line}</h4>);
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
}

const Diff = ({fromSha, toSha, message, repositoryName, repositoryId}) =>
    <div>
        <h3>Repository: <Link to={`/repositories/${repositoryId}`}>{ repositoryName }</Link></h3>
        <h5>Diff {fromSha}..{toSha}</h5>
        <div>
        { parseDiff(message) }
        </div>
    </div>


class DiffRenderer extends React.Component {
    render() {
        return <Diff
            toSha={this.props.toSha}
            fromSha={this.props.fromSha}
            repositoryId={this.props.repositoryId}
            repositoryName={this.props.repositoryName}
            message={this.props.message} />
    }
    componentDidMount() {
        this.props.fetchDiff(this.props.repositoryId, this.props.fromSha, this.props.toSha);
        this.props.loadRepository(this.props.repositoryId);
    }
}


export const DiffHandler = connect(
    (state, ownProps) => ({
        message: state.getIn(
            [
                'diffsByRepo', parseInt(ownProps.params.repositoryId, 10),
                ownProps.params.fromSha,
                ownProps.params.toSha,
                'message'
            ]
        ),
        repositoryId: parseInt(ownProps.params.repositoryId),
        repositoryName: state.getIn(['repositoriesById', parseInt(ownProps.params.repositoryId), 'name']),
        fromSha: ownProps.params.fromSha,
        toSha: ownProps.params.toSha
    }),
    dispatch => ({
        fetchDiff: bindActionCreators(fetchDiff, dispatch),
        loadRepository: bindActionCreators(loadRepository, dispatch)
    })
)(DiffRenderer);
