# AMAZON FINANCE OPEN SOURCE

**Español** · [English](README.en.md)

Editor: [MartinMS-es](https://github.com/MartinMS-es).

Aplicación local para Windows 10/11 de 64 bits. Consulta cuentas de vendedor Amazon mediante SP-API, archiva datos originales y prepara resúmenes financieros y exportaciones para contabilidad. Español e inglés; 23 marketplaces repartidos en EU, NA y FE.

**Instalación vacía:** no incluye empresas, vendedores, movimientos, documentos, usuarios ni credenciales. Cada usuario crea su acceso y registra/autoriza su propia aplicación privada en Amazon. No es un producto oficial de Amazon.

Para usuarios: [Guía de instalación](GUIA-INSTALACION.md) · [English guide](INSTALLATION-GUIDE-EN.md).

## Desarrollo local

Requisitos: Windows x64, Python 3.12, Node.js 22 y npm.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
npm ci
npm run typecheck
npm run build
python desktop_app.py
```

El lanzador prepara HTTPS y abre `https://127.0.0.1:18766/`. La ventana de control detiene el servidor al cerrarse. No abre puertos en el router ni publica servicios en Internet. El acceso a Amazon sí requiere conexión a Internet.

## Generar el instalador

Instala Inno Setup 6.7.3 desde https://jrsoftware.org/isdl.php y ejecuta:

```powershell
.\scripts\build-windows.ps1 -InnoCompiler 'C:\Program Files (x86)\Inno Setup 6\ISCC.exe'
```

PyInstaller incluye Python, cifrado, QR y los recursos web. El resultado aparece en `..\Instalador\AMAZON-FINANCE-OPEN-SOURCE-Setup-1.0.0.exe`. El usuario final no necesita instalar Python ni Node.

## Pruebas

```powershell
npm run typecheck
npm run build
npm run test:i18n
python tests/test_global_markets.py
python tests/test_local_security.py
python tests/test_amazon_connector.py
python tests/test_analysis.py
python tests/test_treasury.py
python tests/test_payment_reconciliation.py
python tests/test_product_sales.py
python tests/test_accountant_export.py
```

Las pruebas usan datos sintéticos locales. No necesitan una cuenta Amazon.

## Datos y límites

Los importes de monedas distintas no se suman. Las transferencias son movimientos de tesorería, no beneficio adicional. Los impuestos identificados no equivalen al impuesto pendiente de ingresar y su deducibilidad requiere revisión. El resultado excluye costes de producto, costes externos e impuesto sobre beneficios.

La disponibilidad histórica, los tipos de informe y las facturas dependen de los permisos y la retención de Amazon; no se garantiza todo el histórico. Las listas pueden ser parciales; el paquete contable utiliza todos los registros guardados del periodo elegido. No inventa facturas ni valores faltantes.

## GitHub

Repositorio oficial: [MartinMS-es/amazon-finance-open-source](https://github.com/MartinMS-es/amazon-finance-open-source). Consulta las [versiones descargables](https://github.com/MartinMS-es/amazon-finance-open-source/releases) y las instrucciones de [publicación](PUBLICAR-GITHUB.md).

## Licencia y atribución

El código propio de la versión actual del repositorio se distribuye bajo la **[Free Use and Attribution License](LICENSE)**, una licencia propia de uso gratuito con restricciones de distribución y acceso de pago.

- Cualquier persona o empresa puede usarlo gratuitamente, incluido el uso interno para gestionar sus propias cuentas de Amazon.
- Se permite estudiar, copiar, modificar y compartir gratuitamente el programa, respetando la licencia.
- Debe conservarse el aviso de autoría y mostrarse de forma visible **«Original project by MartinMS-es»**, con enlace a [github.com/MartinMS-es](https://github.com/MartinMS-es), en el pie o apartado de información de la aplicación.
- Sin autorización previa y por escrito del titular, no se permite venderlo, alquilarlo, cobrar por descargarlo, acceder o utilizarlo, ofrecerlo como servicio de pago ni incluirlo en un producto o servicio de pago. Estas condiciones también se aplican a versiones modificadas.
- Las versiones modificadas deben identificar sus cambios, conservar las mismas condiciones y no sugerir el respaldo del autor original.

El nombre del proyecto se mantiene, pero esta licencia **no es MIT ni una licencia open source conforme a la definición de la Open Source Initiative**: el código está disponible con las restricciones indicadas. El texto completo de `LICENSE` prevalece sobre este resumen.

**Versiones anteriores:** la Release **v1.0.0**, su instalador y las copias previamente distribuidas bajo MIT conservan los permisos que esa licencia concedió. El cambio de licencia del repositorio no modifica retroactivamente esos archivos.

Las dependencias conservan sus respectivas licencias; consulta [THIRD-PARTY-NOTICES.txt](THIRD-PARTY-NOTICES.txt). El programa se entrega sin garantías, en los términos y límites establecidos en `LICENSE`.
