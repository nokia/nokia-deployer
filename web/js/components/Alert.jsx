//Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).
import React from 'react';
import ImmutablePropTypes from 'react-immutable-proptypes';
import * as Actions from '../Actions';
import PureRenderMixin from 'react-addons-pure-render-mixin';

const Alert = React.createClass({
	mixins: [PureRenderMixin],
	propTypes: {
		alert: ImmutablePropTypes.contains({
			id: React.PropTypes.string.isRequired,
			type: React.PropTypes.oneOf(['DANGER', 'WARNING', 'SUCCESS', 'INFO']).isRequired,
			message: React.PropTypes.string.isRequired
		}),
		dispatch: React.PropTypes.func.isRequired
	},
	render() {
		let alertClass = "alert alert-dismissible ";
		switch(this.props.alert.get('type')) {
		case 'DANGER':
			alertClass += "alert-danger";
			break;
		case 'WARNING':
			alertClass += "alert-warning";
			break;
		case 'INFO':
			alertClass += "alert-info";
			break;
		case 'SUCCESS':
			alertClass += "alert-success";
			break;
		default:
			alertClass += "alert-info";
			break;
		}
		return (
			<div className={alertClass} role="alert">
				{this.props.alert.get('message')}
				<button type="button" className="close" onClick={this.dismiss}><span>&times;</span></button>
			</div>
		)
	},
	dismiss() {
		this.props.dispatch(Actions.dismissAlert(this.props.alert.get('id')));
	}
});

export default Alert;
