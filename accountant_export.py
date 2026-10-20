"""Paquete contable local: datos, trazabilidad y faltantes, sin asientos inferidos."""
import csv, datetime, hashlib, io, json, tempfile, zipfile
from collections import defaultdict
from contextlib import closing
from decimal import Decimal
from pathlib import Path
from analysis_local import metrics, cost_parts, is_release_copy, FIELDS
from amazon_local import MARKET_IDS
from treasury_local import cash_summary
from product_sales import product_sales


def money(value):
    return None if value is None else Decimal(value) / 100


def cell(value):
    if value is None:
        return ''
    if isinstance(value, Decimal):
        return format(value, '.2f').replace('.', ',')
    if isinstance(value, (int, float)):
        return value
    text = str(value)
    if text.lstrip().startswith(('=', '+', '-', '@')) or text.startswith(('\t', '\r', '\n')):
        text = "'" + text
    return text


def build(connection, data, start, end, markets, include_unassigned=True):
    first, last = datetime.date.fromisoformat(start), datetime.date.fromisoformat(end)
    if last < first:
        raise ValueError('La fecha final debe ser igual o posterior a la inicial')
    allowed = set(MARKET_IDS) | {'OTHER'}
    if not isinstance(markets, list) or not markets or not set(markets) <= allowed:
        raise ValueError('Selecciona uno o varios mercados admitidos')
    chosen = set(markets)
    data = Path(data).resolve()
    # One consistent local snapshot; close before compressing the archive.
    with closing(connection()) as c:
        c.execute('BEGIN')
        records = [json.loads(p) for p, in c.execute('SELECT payload FROM records')]
        documents = [dict(json.loads(r[3]), id=r[0], hash=r[1], name=r[2])
                     for r in c.execute('SELECT id,hash,name,payload FROM documents')]
        states = {k: json.loads(v) for k, v in c.execute('SELECT id,payload FROM integration_state')}
        jobs = [json.loads(p) for p, in c.execute('SELECT payload FROM amazon_reports')]
        tables = {r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        payment_originals = dict(c.execute('SELECT id,payload FROM payment_source_documents')) if 'payment_source_documents' in tables else {}
    in_period = lambda date: bool(date) and start <= date[:10] <= end
    scope = lambda market: market in chosen
    unknown = lambda market: market in ('', None, 'OTHER', 'SIN_ASIGNAR')
    selected = [r for r in records if scope(r['market']) and in_period(r['date'])]
    canonical = [r for r in selected if not is_release_copy(r)]
    manifest = dict(format='AFOS paquete contable v1', generatedAt=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    fromDate=start, toDate=end, markets=sorted(chosen), includeUnassigned=include_unassigned,
                    files=[], counts={}, warnings=[], reportTasks=[], financialRecovery={}, productCoverage={})
    warnings = manifest['warnings']
    warnings.append('Paquete de apoyo contable con datos descargados; no es un balance certificado, una declaración fiscal ni una exportación de todas las facturas de Amazon.')
    warnings.append('No se mezclan divisas. CSV en UTF-8 con BOM, separador punto y coma, decimales con coma e importes monetarios en unidades, no céntimos.')
    output = tempfile.TemporaryFile()
    try:
        with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=5) as z:
            def csv_file(name, headers, rows):
                with z.open(name, 'w', force_zip64=True) as stream:
                    text = io.TextIOWrapper(stream, encoding='utf-8-sig', newline='')
                    writer = csv.writer(text, delimiter=';')
                    writer.writerow(headers)
                    count = 0
                    for row in rows:
                        writer.writerow([cell(x) for x in row]); count += 1
                    text.flush(); text.detach()
                manifest['counts'][name] = count

            def attachment(path, folder, name):
                path = path.resolve()
                root = (data / folder).resolve()
                if not path.is_relative_to(root) or not path.is_file():
                    return None
                digest = hashlib.sha256()
                with path.open('rb') as stream:
                    for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                        digest.update(chunk)
                z.write(path, name)
                manifest['files'].append(dict(path=name, sha256=digest.hexdigest(), size=path.stat().st_size))
                return name

            summary = defaultdict(lambda: dict.fromkeys(FIELDS, 0))
            costs = []
            fields = ['sales', 'refunds', 'fees', 'salesTax', 'refundTax', 'feeTax', 'identifiedResult', 'otherMovements', 'net']
            def movement_rows():
                for r in canonical:
                    values = metrics(r)
                    key = (r['date'][:7], r['market'], r['currency'])
                    for k, v in values.items(): summary[key][k] += v
                    raw = r.get('raw') or {}
                    refs = {x.get('relatedIdentifierName'): x.get('relatedIdentifierValue') for x in raw.get('relatedIdentifiers') or []}
                    for key2, label, gross, tax, base, source in cost_parts(r):
                        costs.append([r['date'], r['market'], r['currency'], r['id'], label, source, money(base), money(tax), money(gross)])
                    yield [r['id'], r['date'], r['market'], r['currency'], raw.get('transactionType', r.get('category')), r.get('status'),
                           r.get('order'), r.get('sku'), refs.get('FINANCIAL_EVENT_GROUP_ID'), refs.get('SETTLEMENT_ID'), r.get('description'),
                           money(r['amount']), *[money(values[k]) for k in fields]]
            csv_file('01_movimientos_financieros.csv', ['id', 'fecha_registro', 'mercado', 'moneda', 'tipo', 'estado', 'pedido', 'sku',
                     'grupo_financiero', 'liquidacion', 'descripcion', 'importe_original', *fields], movement_rows())
            summary_fields = [k for k in FIELDS if k not in ('payouts', 'fundsToAmazon', 'netPayouts')]
            csv_file('02_resumen_mensual.csv', ['mes', 'mercado', 'moneda', *summary_fields],
                     ([*key, *[v[k] if k == 'unresolvedTax' else money(v[k]) for k in summary_fields]] for key, v in sorted(summary.items())))
            csv_file('03_desglose_costes.csv', ['fecha_registro', 'mercado', 'moneda', 'id_movimiento', 'concepto', 'tipo_amazon', 'base_con_signo', 'impuestos_con_signo', 'total_con_signo'], costs)
            with z.open('originales/movimientos_amazon.ndjson', 'w', force_zip64=True) as stream:
                for r in selected:
                    if r.get('raw'): stream.write((json.dumps(r['raw'], ensure_ascii=False) + '\n').encode('utf-8'))
            manifest['counts']['liberaciones_excluidas_del_resumen'] = len(selected) - len(canonical)

            snapshot = states.get('confirmed_payment_groups')
            details = {k.split(':', 1)[1]: v for k, v in states.items() if k.startswith('payment_detail:')}
            payment_rows, status_rows, pending_payments = [], [], []
            group_by_id = {g['FinancialEventGroupId']: g for g in (snapshot or {}).get('groups', [])}
            for currency in sorted({(g.get('OriginalTotal') or {}).get('CurrencyCode') for g in group_by_id.values()} - {None}):
                cash = cash_summary(records, None, 'ALL', currency, start, end, snapshot, details)
                for p in cash['payments']:
                    group = group_by_id[p['reference']]
                    date = p['date']
                    if not in_period(date or group.get('FinancialEventGroupStart', '')): continue
                    assigned = scope(p['market'])
                    if not assigned and not (include_unassigned and unknown(p['market'])): continue
                    detail = details.get(p['reference']) or {}
                    values = detail.get('metrics') if detail.get('complete') else None
                    line = [date, p['market'], currency, p['reference'], p['status'], money(p['amount']),
                            group.get('FinancialEventGroupStart'), group.get('FinancialEventGroupEnd'),
                            *[money(values[k]) if values else None for k in fields], money(p['amount'] - values['net']) if values else None,
                            'COMPLETO' if values else 'PENDIENTE', 'SELECCIONADO' if assigned else 'SIN_ASIGNAR']
                    status_rows.append(line)
                    if p['confirmed'] and p['amount'] > 0:
                        (payment_rows if assigned else pending_payments).append(line)
                        if not values: warnings.append('Pago sin detalle descargado: ' + p['reference'])
                        if p['reference'] in payment_originals:
                            name = hashlib.sha256(p['reference'].encode()).hexdigest()[:24]
                            z.writestr('originales/pagos/' + name + '.json', payment_originals[p['reference']])
                            manifest.setdefault('paymentSources', []).append(dict(groupId=p['reference'],path='originales/pagos/'+name+'.json'))
            headers = ['fecha_transferencia', 'mercado', 'moneda', 'grupo_financiero', 'estado_transferencia', 'importe_liquidacion',
                       'inicio_actividad_liquidada', 'fin_actividad_liquidada', *fields, 'diferencia_pendiente', 'detalle', 'asignacion']
            csv_file('04_pagos_confirmados.csv', headers, payment_rows)
            csv_file('05_estados_liquidaciones.csv', headers, status_rows)
            csv_file('pendientes/pagos_sin_mercado.csv', headers, pending_payments)
            if not snapshot: warnings.append('No se ha descargado la consulta oficial de pagos.')
            elif snapshot.get('errors'): warnings.append('La consulta oficial de pagos tiene tramos no disponibles; revisar manifiesto.')
            manifest['paymentCoverage'] = {k: (snapshot or {}).get(k) for k in ('checked', 'since', 'complete', 'coverage', 'errors')}

            document_rows, pending_docs = [], []
            for d in documents:
                assigned = scope(d.get('market')) and in_period(d.get('date'))
                unassigned = (not d.get('date') or unknown(d.get('market'))) and (not d.get('date') or in_period(d['date']))
                if not assigned and not (include_unassigned and unassigned): continue
                prefix = 'facturas' if assigned else 'pendientes/facturas_sin_asignar'
                ident = str(d['id'])
                filename = prefix + '/' + hashlib.sha256(ident.encode()).hexdigest()[:24] + '.pdf'
                included = attachment(data / 'documents' / (ident + '.pdf'), 'documents', filename)
                row = [ident, d.get('date'), d.get('market'), d.get('currency'), d.get('type'), d.get('number'), d.get('issuer'),
                       money(d.get('base')), money(d.get('tax')), money(d.get('total')), d.get('status'), d.get('reference'),
                       ','.join(d.get('matched') or []), d.get('name'), included, 'SELECCIONADO' if assigned else 'REVISAR_FECHA_O_MERCADO']
                (document_rows if assigned else pending_docs).append(row)
                if not included: warnings.append('Falta el PDF local del documento ' + ident)
            headers = ['id_documento', 'fecha_documento', 'mercado', 'moneda', 'tipo', 'numero', 'emisor', 'base', 'impuestos', 'total', 'estado_revision', 'referencia', 'movimientos_conciliados', 'nombre_original', 'pdf_en_paquete', 'asignacion']
            csv_file('06_facturas_documentos.csv', headers, document_rows)
            csv_file('pendientes/documentos_sin_asignar.csv', headers, pending_docs)
            if not document_rows: warnings.append('No hay facturas o documentos registrados con fecha y mercado de la selección. Esto no significa que Amazon no haya emitido facturas.')

            ids = {v: k for k, v in MARKET_IDS.items()}
            for job in jobs:
                if job.get('toDate') and job['toDate'] < start or job.get('fromDate') and job['fromDate'] > end: continue
                path = (data / 'reports' / job.get('filename', '')).resolve()
                codes = set(job.get('markets') or [job.get('market')])
                if job.get('kind') == 'sales' and job.get('status') == 'READY' and path.is_relative_to(data / 'reports') and path.is_file():
                    try:
                        report = json.loads(path.read_bytes())
                        codes = {ids.get(x, 'OTHER') for x in (report.get('reportSpecification') or {}).get('marketplaceIds', [])} or codes
                    except (ValueError, OSError): pass
                if not codes & chosen and not (include_unassigned and any(unknown(x) for x in codes)): continue
                manifest['reportTasks'].append({k: job.get(k) for k in ('id', 'reportId', 'kind', 'market', 'fromDate', 'toDate', 'status', 'error')})
                if job.get('status') != 'READY': continue
                ident = hashlib.sha256(str(job['id']).encode()).hexdigest()[:24]
                attachment(path, 'reports', 'informes_amazon/' + ident + path.suffix)
            # Product aggregates never prorate a report that extends beyond the requested period.
            product_rows = []
            if (last-first).days <= 730:
                product = product_sales(data, jobs, start, end)
                manifest['productCoverage'] = {k: v for k, v in product['coverage'].items() if k in chosen}
                product_rows = [r for r in product['rows'] if r['market'] in chosen]
            else:
                warnings.append('El agregado comercial por producto no se calcula para rangos de más de dos años; los informes originales disponibles se adjuntan completos.')
            csv_file('07_ventas_por_producto.csv', ['mercado', 'ASIN', 'ASIN_padre', 'unidades_pedidas', 'unidades_enviadas', 'unidades_devueltas', 'ventas_pedidas', 'moneda'],
                     ([r['market'], r['asin'], r['parentAsin'], r['unitsOrdered'], r['unitsShipped'], r['unitsRefunded'], money(r['sales']), r['currency']] for r in product_rows))
            if any(manifest['productCoverage'].get(m, 0) < (last-first).days + 1 for m in chosen):
                warnings.append('El informe comercial por producto tiene días o mercados sin cobertura: no interpretar los huecos como cero ventas.')
            recovery = states.get('historical_recovery') or {}
            manifest['financialRecovery'] = {k: recovery.get(k) for k in ('since', 'status', 'phase', 'completed', 'unavailable', 'error', 'updated')}
            if recovery.get('unavailable') or recovery.get('status') == 'STOPPED': warnings.append('La recuperación financiera tiene huecos o interrupciones; revisar cobertura antes de cerrar el balance.')
            warnings.append('Las facturas documentan movimientos: no volver a sumarlas a ventas/gastos. Los pagos liquidan actividad que puede pertenecer a otros periodos.')
            warnings.append('Los archivos originales de informes y pagos se adjuntan completos: pueden contener actividad fuera de las fechas seleccionadas. No sumarlos entre sí ni al CSV financiero.')
            warnings.append('Impuestos identificados no equivale a impuestos pendientes de pago ni a deducibilidad verificada. No incluye costes externos, coste de producto ni impuesto sobre beneficios.')
            csv_file('08_faltantes_y_advertencias.csv', ['advertencia'], ([w] for w in dict.fromkeys(warnings)))
            z.writestr('LEEME_CONTABLE.txt', 'AMAZON FINANCE OPEN SOURCE - PAQUETE PARA CONTABILIDAD\nPeriodo: ' + start + ' a ' + end + '\nMercados: ' + ', '.join(sorted(chosen)) + '\n\n'
                       '01 movimientos: actividad financiera por postedDate, sin duplicar liberaciones. Incluye importes con signo y columnas de desglose.\n'
                       '02 resumen: por mes, mercado y moneda; no suma divisas. Importes de impuestos y gastos conservan el signo original.\n'
                       '03 costes: detalle de tarifas, publicidad, almacenamiento y otros cargos; base + impuestos = total.\n'
                       '04 pagos: solo grupos Closed/Succeeded positivos por FundTransferDate; puede liquidar ventas de otras fechas.\n'
                       '05 estados: incluye cargos y liquidaciones fallidas/pendientes para revisión, no volver a sumar a 04.\n'
                       '06 documentos: índice de facturas y PDF locales, con estado de revisión. No presupone disponibilidad de todas las facturas de Amazon.\n'
                       '07 productos: fuente comercial, unidades pedidas/enviadas/devueltas separadas; no sumar otra vez a 01.\n'
                       'pendientes/: elementos sin mercado/fecha no asignados a los totales seleccionados.\n'
                       'originales/: datos Amazon conservados, incluidas liberaciones duplicadas económicamente; no usar suma directa.\n'
                       'informes_amazon/: archivos completos disponibles. manifest.json indica filtros, cobertura, faltantes y hashes de adjuntos.\n\n'
                       'Formato CSV: UTF-8 con BOM, delimitador ; y decimal coma. Fórmulas de texto neutralizadas.\n'
                       'Este paquete es soporte para preparar el balance fuera de la aplicación, no un balance cerrado ni declaración fiscal.\n')
            z.writestr('manifest.json', json.dumps(manifest, ensure_ascii=False, indent=2))
        output.seek(0)
        return output, manifest
    except BaseException:
        output.close()
        raise
