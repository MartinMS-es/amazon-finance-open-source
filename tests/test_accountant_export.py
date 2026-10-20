import csv, hashlib, io, json, sqlite3, sys, tempfile, unittest, zipfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from accountant_export import build


class AccountantTests(unittest.TestCase):
    def test_multimarket_complete_export_and_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            data = Path(folder)
            (data / 'documents').mkdir(); (data / 'reports').mkdir()
            def connection(): return sqlite3.connect(data / 'test.sqlite')
            c = connection()
            c.executescript('CREATE TABLE records(id TEXT,payload TEXT); CREATE TABLE documents(id TEXT,hash TEXT,name TEXT,payload TEXT); CREATE TABLE integration_state(id TEXT,payload TEXT); CREATE TABLE amazon_reports(payload TEXT); CREATE TABLE payment_source_documents(id TEXT,payload TEXT);')
            raw = dict(transactionId='original', transactionType='Shipment', transactionStatus='RELEASED',
                       totalAmount=dict(currencyCode='EUR', currencyAmount=1),
                       breakdowns=[dict(breakdownType='Sales', breakdownAmount=dict(currencyCode='EUR', currencyAmount=1))])
            row = dict(id='original', date='2026-09-01', market='ES', currency='EUR', amount=100, category='Sin clasificar', status='RELEASED', raw=raw)
            c.executemany('INSERT INTO records VALUES(?,?)', ((str(i), json.dumps(dict(row, id=str(i)))) for i in range(20001)))
            release = dict(row, id='release', raw=dict(raw, relatedIdentifiers=[dict(relatedIdentifierName='DEFERRED_TRANSACTION_ID', relatedIdentifierValue='original')]))
            for ident, r in [('release', release), ('fr', dict(row, id='fr', market='FR')), ('de', dict(row, id='de', market='DE'))]:
                c.execute('INSERT INTO records VALUES(?,?)', (ident, json.dumps(r)))
            transfer = dict(row, id='transfer', raw=dict(transactionType='Transfer', description='Disbursement', relatedIdentifiers=[dict(relatedIdentifierName='FINANCIAL_EVENT_GROUP_ID', relatedIdentifierValue='paid')]))
            c.execute('INSERT INTO records VALUES(?,?)', ('transfer', json.dumps(transfer)))
            groups = dict(complete=True, groups=[dict(FinancialEventGroupId='paid', ProcessingStatus='Closed', FundTransferStatus='Succeeded', FundTransferDate='2026-09-10', OriginalTotal=dict(CurrencyCode='EUR', CurrencyAmount=1)), dict(FinancialEventGroupId='failed', ProcessingStatus='Closed', FundTransferStatus='Failed', FundTransferDate='2026-09-11', OriginalTotal=dict(CurrencyCode='EUR', CurrencyAmount=2))])
            c.execute('INSERT INTO integration_state VALUES(?,?)', ('confirmed_payment_groups', json.dumps(groups)))
            c.execute('INSERT INTO payment_source_documents VALUES(?,?)', ('paid', json.dumps(dict(transactions=[raw]))))
            document = dict(date='2026-09-02', market='ES', currency='EUR', type='Recibida', number='=BAD()', issuer='Amazon', base=100, tax=21, total=121, status='Pendiente')
            pdf = b'%PDF-1.4 synthetic test document'
            (data / 'documents' / 'doc.pdf').write_bytes(pdf)
            c.execute('INSERT INTO documents VALUES(?,?,?,?)', ('doc', hashlib.sha256(pdf).hexdigest(), 'invoice.pdf', json.dumps(document)))
            c.execute('INSERT INTO documents VALUES(?,?,?,?)', ('undated', '', 'missing.pdf', json.dumps(dict(document, date='', market='OTHER'))))
            original_report = b'date;value\n2026-09-01;1\n'
            (data / 'reports' / 'report.tsv').write_bytes(original_report)
            c.execute('INSERT INTO amazon_reports VALUES(?)', (json.dumps(dict(id='report', kind='settlement', status='READY', market='ES', fromDate='2026-09-01', toDate='2026-09-30', filename='report.tsv')),))
            (data / 'amazon-credentials.dpapi').write_bytes(b'SECRET_SENTINEL_DO_NOT_EXPORT')
            c.commit(); c.close()
            stream, manifest = build(connection, data, '2026-09-01', '2026-09-30', ['ES', 'FR'])
            with stream, zipfile.ZipFile(stream) as archive:
                def read_csv(name): return list(csv.DictReader(io.StringIO(archive.read(name).decode('utf-8-sig')), delimiter=';'))
                movements = read_csv('01_movimientos_financieros.csv')
                self.assertEqual(len(movements), 20003)
                self.assertEqual({r['mercado'] for r in movements}, {'ES', 'FR'})
                self.assertNotIn('release', {r['id'] for r in movements})
                self.assertEqual(movements[0]['importe_original'], '1,00')
                summary = read_csv('02_resumen_mensual.csv')
                self.assertNotIn('payouts', summary[0])
                self.assertEqual(sum(int(r['sales'].split(',')[0]) for r in summary), 20002)
                self.assertEqual(len(read_csv('04_pagos_confirmados.csv')), 1)
                self.assertEqual(len(read_csv('05_estados_liquidaciones.csv')), 2)
                invoices = read_csv('06_facturas_documentos.csv')
                self.assertEqual(invoices[0]['numero'], "'=BAD()")
                self.assertEqual(archive.read(invoices[0]['pdf_en_paquete']), pdf)
                self.assertEqual(len(read_csv('pendientes/documentos_sin_asignar.csv')), 1)
                self.assertEqual(manifest['counts']['liberaciones_excluidas_del_resumen'], 1)
                self.assertTrue(any('Falta el PDF' in w for w in manifest['warnings']))
                for name in archive.namelist():
                    self.assertNotIn('..', name)
                    self.assertNotIn(b'SECRET_SENTINEL_DO_NOT_EXPORT', archive.read(name))
                for item in manifest['files']:
                    self.assertEqual(hashlib.sha256(archive.read(item['path'])).hexdigest(), item['sha256'])
    def test_validation(self):
        for start, end, markets in [('2026-09-30', '2026-09-01', ['ES']), ('2026-09-01', '2026-09-30', []), ('2026-09-01', '2026-09-30', ['INVALID'])]:
            with self.assertRaises(ValueError): build(lambda: None, Path('.'), start, end, markets)


if __name__ == '__main__': unittest.main()
