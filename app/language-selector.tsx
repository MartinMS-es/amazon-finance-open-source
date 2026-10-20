import {useState} from 'react';
import {getLanguage,setLanguage} from '../lib/i18n.mjs';
export default function LanguageSelector(){const [language,setValue]=useState(getLanguage());return <label style={{display:'inline-flex',gap:8,alignItems:'center'}}>Idioma / Language<select aria-label="Idioma / Language" value={language} onChange={e=>{setValue(e.target.value);setLanguage(e.target.value);}}><option value="es">Español</option><option value="en">English</option></select></label>;}
