//Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).
import React from 'react';
import ReactDOM from 'react-dom';
import ImmutablePropTypes from 'react-immutable-proptypes';
import PureRenderMixin from 'react-addons-pure-render-mixin';
import FuzzyInput from './FuzzyInput.jsx';
import Immutable from 'immutable';

const FuzzyListForm = React.createClass({
    propTypes: {
        elements: React.PropTypes.instanceOf(Immutable.List).isRequired,
        renderElement: React.PropTypes.func.isRequired,
        compareWith: React.PropTypes.func.isRequired,
        renderElementForm: React.PropTypes.func,
        placeholder: React.PropTypes.string.isRequired,
        // called when an element is added or removed, get the currently selected elements as a parameter
        onChange: React.PropTypes.func,
        // must be a subset of elements
        initialElements: React.PropTypes.instanceOf(Immutable.List).isRequired
    },
    getDefaultProps() {
        return {
            onChange() {}
        };
    },
    getInitialState() {
        return {
            selectedElements: this.props.initialElements.toArray()
        };
    },
    getSelectedElements() {
        return this.state.selectedElements;
    },
    reset() {
        this.setState(this.getInitialState());
    },
    render() {
        const that = this;
        return (
            <div>
                <FuzzyInput
                    elements={that.props.elements}
                    renderElement={that.props.renderElement}
                    compareWith={that.props.compareWith}
                    placeholder={that.props.placeholder}
                    onElementSelected={that.addElement} />
                {that.state.selectedElements.map((el, index) => <div key={index} className="row">
                    <div className="col-sm-5 form-align"> {that.props.renderElement(el)} </div>
                    <div className="col-sm-4">
                        {that.props.renderElementForm ? that.props.renderElementForm(el) : null}
                    </div>
                    <div className="col-sm-3">
                        <button type="button" className="btn btn-sm btn-default" onClick={that.removeElement(el)}>Remove</button>
                    </div>
                </div>)}
            </div>
        );
    },
    addElement(el) {
        const index = this.state.selectedElements.indexOf(el);
        if (index != -1) {
            return;
        }
        const selectedElements = this.state.selectedElements.concat(el);
        this.setState({selectedElements});
        this.props.onChange(selectedElements);
    },
    removeElement(el) {
        const that = this;
        return () => {
            const index = that.state.selectedElements.indexOf(el);
            if (index > -1) {
                const selectedElements = that.state.selectedElements.slice(0, index).concat(that.state.selectedElements.slice(index + 1));
                that.setState({selectedElements});
                that.props.onChange(selectedElements);
            }
        };
    }
});

export default FuzzyListForm;
