//Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).
import React from 'react';
import ReactDOM from 'react-dom';
import ImmutablePropTypes from 'react-immutable-proptypes';
import fuzzy from 'fuzzy';
import PureRenderMixin from 'react-addons-pure-render-mixin';
import Immutable from 'immutable';

// renders an input (styled according to Bootstrap markup) that allows the user to select a value among
// several elements. Elements are ordered according to fuzzy matching with the current input.
const FuzzyInput = React.createClass({
    propTypes: {
        // a list of things
        elements: React.PropTypes.instanceOf(Immutable.List).isRequired,
        // will be passed the selected element when the user selects an element
        onElementSelected: React.PropTypes.func.isRequired,
        // a function taking an element and returning a string or a React Component
        renderElement: React.PropTypes.func.isRequired,
        // a function taking an element and returning a string representing this element, used for fuzzy
        // matching
        compareWith: React.PropTypes.func.isRequired,
        placeholder: React.PropTypes.string.isRequired
    },
    mixins: [
        require('react-onclickoutside'),
        PureRenderMixin
    ],
    getInitialState() {
        return {input: "", expanded: false, selectedIndex: 0};
    },
    registerInput(input) {
        this.input = ReactDOM.findDOMNode(input);
    },
    handleChange() {
        this.setState({input: this.input.value, expanded: true, selectedIndex: 0});
    },
    sort() {
        const input = this.state.input;
        const that = this;
        const options =  {
            extract(el) { return that.props.compareWith(el); }
        };
        const results = fuzzy.filter(input, this.props.elements, options);
        return results.sort((r1, r2) => {
            if(r1.score != r2.score) {
                return r2.score - r1.score;
            } else {
                return r1.string.localeCompare(r2.string);
            }
        });
    },
    renderResult(result, index) {
        const className = index === this.state.selectedIndex ? "active" : "";
        return <li key={result.index} className={className}><a href="#" onClick={this.onItemClicked(result)}>{this.props.renderElement(result.original)}</a></li>
    },
    handleKeyPress(evt) {
        if(evt.key === 'ArrowDown') {
            var sorted = this.sort();
            var newIndex = Math.max(0, Math.min(this.state.selectedIndex + 1, sorted.length - 1));
            this.setState({selectedIndex: newIndex});
        } else if(evt.key === 'ArrowUp') {
            var sorted = this.sort();
            var newIndex = Math.min(sorted.length, Math.max(0, this.state.selectedIndex - 1));
            this.setState({selectedIndex: newIndex});
        } else if(evt.key === 'Enter') {
            evt.preventDefault();
            var sorted = this.sort();
            if(this.state.selectedIndex < sorted.length) {
                this.setState({input: sorted[this.state.selectedIndex].string, expanded: false});
            }
            this.trySelectElement();
        }
    },
    render() {
        let formClass = "";
        if(this.state.expanded) {
            formClass += "open";
        }
        const sorted = this.sort();
        return (
            <div className="dropdown">
                <div className={formClass} >
                    <input value={this.state.input} className="form-control" type="text" placeholder={this.props.placeholder} ref={this.registerInput} onChange={this.handleChange} onFocus={this.onInputFocus} onKeyDown={this.handleKeyPress}/>
                    <ul className="dropdown-menu" id="dropdown">
                        {sorted.length > 0 ? sorted.map(this.renderResult) : <li>No matches.</li>}
                    </ul>
                </div>
            </div>
        )
    },
    onItemClicked(result) {
        const that = this;
        return evt => {
            evt.preventDefault();
            that.setState({input: that.props.compareWith(result.original), expanded: false}, () => {
                that.trySelectElement();
            });
        }
    },
    onInputFocus(evt) {
        this.setState({expanded: true});
        evt.target.select();
    },
    handleClickOutside(evt) {
        this.setState({expanded: false});
    },
    trySelectElement() {
        const that = this;
        const selected = this.props.elements.find(el => that.state.input === that.props.compareWith(el));
        if(selected != null) {
            that.props.onElementSelected(selected);
        }
    }
});

export default FuzzyInput;
