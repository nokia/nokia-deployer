//Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).
import React from 'react';
import ImmutablePropTypes from 'react-immutable-proptypes';
import PureRenderMixin from 'react-addons-pure-render-mixin';
import {Link} from 'react-router';
import moment from 'moment';

const DeploymentList = React.createClass({
    mixins: [PureRenderMixin],
    propTypes: {
        displayRepositoryName: React.PropTypes.bool,
        deployments: ImmutablePropTypes.listOf(
            ImmutablePropTypes.contains({
                id: React.PropTypes.number.isRequired,
                status: React.PropTypes.oneOf(['QUEUED', 'INIT', 'PRE_DEPLOY', 'DEPLOY', 'POST_DEPLOY', 'FAILED', 'COMPLETE']),
                log_entries: ImmutablePropTypes.listOf(
                    ImmutablePropTypes.contains({
                        severity: React.PropTypes.oneOf(['info', 'warn', 'error']),
                        message: React.PropTypes.string
                    })
                ),
                date_start_deploy: React.PropTypes.object,
                commit: React.PropTypes.string,
                branch: React.PropTypes.string
            })
        ).isRequired
    },
    getDefaultProps() {
        return {
            displayRepositoryName: false
        };
    },
    render() {
        const that = this;
        if(that.props.deployments.size == 0) {
            return <p>Nothing to show here yet.</p>;
        }
        return (
            <table className="table table-condensed">
                <thead>
                    <tr>
                        <th>ID</th>
                        {that.props.displayRepositoryName ? <th>Repository</th> : null}
                        <th>Environment</th>
                        <th>Branch</th>
                        <th>Commit</th>
                        <th>Status</th>
                        <th>Started at</th>
                        <th>Logs</th>
                    </tr>
                </thead>
                <tbody>
                    { that.props.deployments.sort((d1, d2) => d2.get('date_start_deploy') - d1.get('date_start_deploy')).map(deployment => {
                        let formattedStatus = null;
                        switch(deployment.get('status')) {
                        case "COMPLETE":
                            formattedStatus = <td><span className="text-success">OK</span></td>;
                            break;
                        case "FAILED":
                            formattedStatus = <td><span className="text-danger">Error</span></td>;
                            break;
                        case "QUEUED":
                            formattedStatus = <td><span className="text-warning">Queued</span></td>;
                            break;
                        case "INIT":
                        case "DEPLOY":
                        case "PRE_DEPLOY":
                        case "POST_DEPLOY":
                            formattedStatus = <td><span className="text-warning">In progress</span></td>;
                            break;
                        default:
                            formattedStatus = <td><span className="text-warning">Unknown</span></td>;
                            break;
                        }
                        return (
                            <tr key={deployment.get('id')}>
                                <td>{deployment.get('id')}</td>
                                {that.props.displayRepositoryName ? <td>{deployment.get('repository_name')}</td> : null}
                                <td>{deployment.get('environment_name')}</td>
                                <td>{deployment.get('branch')}</td>
                                <td>{that.formatCommit(deployment.get('commit'))}</td>
				{ formattedStatus }
				<td>{ deployment.get('date_start_deploy').local().format('YYYY-MM-DD HH:mm ZZ') }</td>
                                <td><Link to={`/deployments/${deployment.get('id')}`} activeClassName="active">details</Link></td>
                            </tr>
                            );
                    })}
                </tbody>
            </table>
        );
    },
    formatCommit(hexsha) {
        return hexsha.substring(0, 8);
    }
});

export default DeploymentList;
