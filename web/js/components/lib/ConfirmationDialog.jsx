//Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).
import React from 'react';
import BootstrapModal from './BootstrapModal.jsx';

// Put this in a component, get a ref to it, then use ref.show() to ask the user for confirmation
const ConfirmationDialog = React.createClass({
    show(message, onAccepted, onRejected) {
        this.onAccepted = onAccepted;
        this.onRejected = onRejected;
        this.message = message;
        this.setState({visible: true});
    },
    getInitialState() {
        return {visible: false};
    },
    render() {
        let message = this.message;
        if(!message) {
            message = 'Are you sure?';
        }
        return <BootstrapModal visible={this.state.visible} onModalHidden={this.onCancelClicked}>
            <div className="modal-body">
                <span>{message}</span>
            </div>
            <div className="modal-footer">
                <button type="button" className="btn btn-default" onClick={this.onCancelClicked}>Cancel</button>
                <button type="button" className="btn btn-primary" onClick={this.onConfirmClicked}>Confirm</button>
            </div>
        </BootstrapModal>;
    },
    onCancelClicked() {
        this.setState({visible: false});
        if(this.onRejected) {
            this.onRejected();
        }
    },
    onConfirmClicked() {
        this.setState({visible: false});
        if(this.onAccepted) {
            this.onAccepted();
        }
    }
});

export default ConfirmationDialog;
