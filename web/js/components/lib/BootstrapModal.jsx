//Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).
import React from 'react';
import ReactPortal from 'react-portal';
import PureRenderMixin from 'react-addons-pure-render-mixin';

const BootstrapModal = React.createClass({
    mixins: [PureRenderMixin],
    propTypes: {
        visible: React.PropTypes.bool,
        onModalHidden: React.PropTypes.func
    },
    componentWillMount() {
        this.isOpened = this.props.visible;
    },
    componentWillUnmount() {
        if(this.contents)  {
            this.contents.closeModal();
        }
    },
    render() {
        return (
            <ReactPortal isOpened={this.isOpened}>
                <ModalContents ref={this.registerContents} onModalHidden={this.props.onModalHidden} visible={this.props.visible}>
                    {this.props.children}
                </ModalContents>
            </ReactPortal>
        )
    },
    registerContents(el) {
        this.contents = el;
    },
    componentWillReceiveProps(nextProps) {
        if(this.props.visible && !nextProps.visible) {
            this.contents.closeModal();
            this.isOpened = false;
        }
        if(!this.props.visible && nextProps.visible) {
            this.isOpened = true;
        }
    }
});

const ModalContents = React.createClass({
    propTypes: {
        onModalHidden: React.PropTypes.func,
        visible: React.PropTypes.bool
    },
    showModal(el) {
        this.modal = el;
        if(el) {
            jQuery(el).modal();
        }
        const that = this;
        jQuery(el).on('hidden.bs.modal', () => {
            if(that.props.onModalHidden) {
                that.props.onModalHidden();
            }
        });
    },
    render() {
        return (
            <div className="modal fade diff-modal" ref={this.showModal}>
                <div className="modal-dialog">
                    <div className="modal-content">
                        {this.props.children}
                    </div>
                </div>
            </div>
        )
    },
    closeModal() {
        if(this.modal) {
            jQuery(this.modal).modal('hide');
        }
    }
});

export default BootstrapModal;
