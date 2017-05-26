//Copyright (C) 2016 Nokia Corporation and/or its subsidiary(-ies).
import Auth from './Auth.js';
import { normalize, arrayOf } from 'normalizr';

const identity = t => t;


export const createAction = (name, payloadFactory = identity) => (...args) => (
    {
        'type': name,
        'payload': payloadFactory(...args)
    }
);


// Helper to generate Redux actions related to a REST resource and cut boilerplate.
// See how to use it in Actions.js.
export const restActions = (resourceName, pluralName, {
        baseUrl,
        postUrl = undefined,
        entityUrl = undefined,
        alertAction = undefined,
        schema,
        makeData = identity
    }) => {
    if(postUrl === undefined) {
        postUrl = baseUrl;
    }
    if(entityUrl === undefined) {
        if(baseUrl().endsWith('/')) {
            entityUrl = id => `${baseUrl()}${id}`;
        } else {
            entityUrl = id => `${baseUrl()}/${id}`;
        }
    }
    const actions = {
        add: createAction(`ADD_${resourceName.toUpperCase()}`),
        delete: createAction(`DELETE_${resourceName.toUpperCase()}`),
        list: createAction(`LOAD_${pluralName.toUpperCase()}`),
        get: createAction(`GET_${resourceName.toUpperCase()}`),
        edit: createAction(`EDIT_${resourceName.toUpperCase()}`),
    };
    const capitalizedResourceName = resourceName[0].toUpperCase() + resourceName.slice(1);
    return {
        add: (data, urlParams = {}) => dispatch => {
            const postData = makeData(data);
            dispatch(actions.add({status: 'REQUEST'}));
            Auth.postJSON(postUrl(urlParams), postData, json => {
                const normalized = normalize(json[resourceName], schema);
                dispatch(actions.add({status: 'SUCCESS', entities: normalized.entities}));
                if(alertAction) {
                    dispatch(alertAction('SUCCESS', `${capitalizedResourceName} ${json[resourceName].id} created.`));
                }
            }, () => {
                dispatch(actions.add({status: 'ERROR'}));
                if(alertAction) {
                    dispatch(alertAction('DANGER', `Error when creating a new ${resourceName}.`));
                }
            });
        },
        edit: (id, data, urlParams = {}) => dispatch => {
            const putData = makeData(data);
            dispatch(actions.add({status: 'REQUEST'}));
            Auth.putJSON(entityUrl(id, urlParams), putData, json => {
                const normalized = normalize(json[resourceName], schema);
                dispatch(actions.edit({status: 'SUCCESS', entities: normalized.entities}));
                if(alertAction) {
                    dispatch(alertAction('SUCCESS', `${capitalizedResourceName} ${json[resourceName].id} modified.`));
                }
            }, () => {
                dispatch(actions.edit({status: 'ERROR'}));
                if(alertAction) {
                    dispatch(alertAction('DANGER', `Error when modifying ${resourceName} ${id}.`));
                }
            });
        },
        delete: (id, urlParams = {}) => dispatch => {
            dispatch(actions.delete({status: 'REQUEST'}));
            Auth.deleteJSON(entityUrl(id, urlParams), json => {
                json[resourceName].id = id;
                const normalized = normalize(json[resourceName], schema);
                dispatch(actions.delete({status: 'SUCCESS', entities: normalized.entities}));
                if(alertAction) {
                    dispatch(alertAction('SUCCESS', `${capitalizedResourceName} ${json[resourceName].id} deleted.`));
                }
            }, () => {
                dispatch(actions.delete({status: 'ERROR'}));
                if(alertAction) {
                    dispatch(alertAction('DANGER', `Error when deleting ${resourceName} ${id}.`));
                }
            });
        },
        list: (urlParams = {}) => dispatch => {
            dispatch(actions.list({status: 'REQUEST'}));
            Auth.getJSON(baseUrl(urlParams), json => {
                const normalized = normalize(json[pluralName], arrayOf(schema));
                dispatch(actions.list({status: 'SUCCESS', entities: normalized.entities}));
            }, () => {
                dispatch(actions.list({status: 'ERROR'}));
            });
        },
        get: (id, urlParams = {}) => dispatch => {
            dispatch(actions.list({status: 'REQUEST'}));
            Auth.getJSON(entityUrl(id, urlParams), json => {
                const normalized = normalize(json[resourceName], schema);
                dispatch(actions.list({status: 'SUCCESS', entities: normalized.entities}));
            }, () => {
                dispatch(actions.list({status: 'ERROR'}));
            });
        }
    };
};
