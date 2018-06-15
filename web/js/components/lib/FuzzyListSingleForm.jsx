//Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).
import React from 'react';
import ReactDOM from 'react-dom';
import ImmutablePropTypes from 'react-immutable-proptypes';
import PureRenderMixin from 'react-addons-pure-render-mixin';
import FuzzyInput from './FuzzyInput.jsx';
import Immutable from 'immutable';

const FuzzyListSingleForm = React.createClass({
    propTypes: {
        elements: React.PropTypes.instanceOf(Immutable.List).isRequired,
        renderElement: React.PropTypes.func.isRequired,
        renderChildElement: React.PropTypes.func.isRequired,
        compareWith: React.PropTypes.func.isRequired,
        renderElementForm: React.PropTypes.func,
        renderChildForm: React.PropTypes.func,
        placeholder: React.PropTypes.string.isRequired,
        // called when an element is added or removed, get the currently selected elements as a parameter
        onChange: React.PropTypes.func,
        // must be a subset of elements
        selectedElement: React.PropTypes.object,
        selectedChildren: React.PropTypes.instanceOf(Immutable.List).isRequired,
        childElement: React.PropTypes.string.isRequired
    },
    getDefaultProps() {
        return {
            onChange() {}
        };
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
                    onElementSelected={that.selectElement} />
                {that.props.selectedElement &&
                  <div className="row">
                      <div className="col-sm-5 form-align"> {that.props.selectedElement.get('name')} </div>
                      <div className="col-sm-4">
                          {that.props.renderElementForm ? that.props.renderElementForm(that.props.selectedElement) : null}
                      </div>
                      <div className="col-sm-3">
                          <button type="button" className="btn btn-sm btn-default" onClick={() => that.removeElement()}>Remove</button>
                      </div>
                  </div>
                }
                {that.props.selectedChildren.map((el, index) => <div key={index} className="row">
                    <div className="col-sm-5 form-align"> {that.props.renderChildElement(el)} </div>
                    <div className="col-sm-4">
                        {that.props.renderChildForm ? that.props.renderChildForm(el) : null}
                    </div>
                </div>)}
            </div>
        );
    },
    selectElement(el) {
        this.props.onChange(this.props.selectedElement = el);
        // this.props.onChange(this.props.selectedChildren = el.get(this.props.childElement).toList())
    },
    removeElement() {
        this.props.onChange(this.props.selectedElement = null);
        // this.props.onChange(this.props.selectedChildren = List())

    }
});

export default FuzzyListSingleForm;
