// Local renderer: translate labels, never values, identifiers, input data or raw JSON.
import * as runtime from 'react/jsx-runtime-original';
import {translate} from './i18n.mjs';
export const Fragment=runtime.Fragment;
function labels(value){return Array.isArray(value)?value.map(labels):typeof value==='string'?translate(value):value;}
function prepare(type,props){if(!props||type==='pre'||type==='code')return props;const result={...props};if('children' in result)result.children=labels(result.children);for(const key of ['title','placeholder','aria-label','alt'])if(typeof result[key]==='string')result[key]=translate(result[key]);return result;}
export function jsx(type,props,key){return runtime.jsx(type,prepare(type,props),key);}
export function jsxs(type,props,key){return runtime.jsxs(type,prepare(type,props),key);}
