//Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).
// required by bootstrap
global.jQuery = require('jquery');
global.$ = global.jQuery;
require('bootstrap');
import 'babel-polyfill';
import 'whatwg-fetch';

import 'highlight.js';
// import './polyfill';

import App from 'App.jsx';

const app = new App();
app.kickoff();
