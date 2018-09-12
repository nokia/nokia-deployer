//Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).
import React from 'react';
import ReactDOM from 'react-dom';
import ImmutablePropTypes from 'react-immutable-proptypes';
import PureRenderMixin from 'react-addons-pure-render-mixin';
import FuzzyInput from './FuzzyInput.jsx';
import Immutable from 'immutable';

const FuzzyListSelector = React.createClass({
    propTypes: {
        elements: React.PropTypes.instanceOf(Immutable.List).isRequired,
        renderElement: React.PropTypes.func.isRequired,
        compareWith: React.PropTypes.func.isRequired,
        renderElementView: React.PropTypes.func,
        placeholder: React.PropTypes.string.isRequired,
        onChange: React.PropTypes.func,
        selectedElement: React.PropTypes.object,
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
                  [<div className="row">
                    <div className="col-sm-8 form-align">
                    <h5>{that.props.selectedElement.get('name')} <button type="button" className="btn btn-sm btn-default" onClick={() => that.removeElement()}>Remove</button></h5>
                     </div>
                  </div>,
                  <div>
                      {that.props.renderElementView ? that.props.renderElementView(that.props.selectedElement) : null}
                  </div>]
                }
            </div>
        );
    },
    selectElement(el) {
        this.props.onChange(el);
    },
    removeElement() {
        this.props.onChange(null);
    }
});

export default FuzzyListSelector;
