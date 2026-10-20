# Instalación de AMAZON FINANCE OPEN SOURCE

## 1. Instalar

Windows 10/11 x64. Ejecuta `AMAZON-FINANCE-OPEN-SOURCE-Setup-1.0.0.exe`, selecciona idioma y carpeta y termina el asistente. No necesitas Python, Node, Docker ni una cuenta de desarrollador de GitHub.

El programa no está firmado con un certificado comercial de editor; Windows puede mostrar editor desconocido. Usa exclusivamente un paquete del origen que hayas verificado y compara su SHA-256 con `SHA256SUMS.txt`.

## 2. Abrir y crear acceso

Abre el acceso directo **AMAZON FINANCE OPEN SOURCE**. Se muestra una ventana de control y el navegador abre `https://127.0.0.1:18766/`. La ventana debe permanecer abierta mientras usas la aplicación; al cerrarla se detiene el servidor.

En el primer inicio se genera un certificado HTTPS único para este usuario y se incorpora al almacén de confianza del usuario de Windows, exclusivamente para la conexión local. Si Windows solicita confirmar esa operación, comprueba que corresponde al programa. Nunca se distribuye una clave o certificado común entre instalaciones.

Crea tu contraseña y vincula un autenticador TOTP compatible siguiendo la pantalla. Guarda tu configuración de recuperación de forma privada. **No existe usuario ni contraseña predeterminados.** La base de datos inicial está vacía; no hay cifras de muestra precargadas.

## 3. Conectar tu cuenta Amazon

1. Registra tu propio perfil de desarrollador y aplicación privada SP-API en https://solutionproviderportal.amazon.com/sellingpartner/developerconsole . Consulta la documentación oficial https://developer-docs.amazon/sp-api/docs/registering-your-application .
2. Solicita exclusivamente los roles necesarios para los informes que utilizarás. La aprobación depende de Amazon. Los informes fiscales restringidos pueden necesitar aprobación adicional.
3. Autoautoriza la aplicación para tu cuenta vendedora. Obtén Client ID, Client Secret de LWA y Refresh Token.
4. En **Conexión Amazon**, selecciona EU, NA o FE, pega tus propios valores y pulsa guardar. Comprueba conexión y mercados. Cada región requiere la autorización que corresponda; no todos los mercados están necesariamente habilitados en tu cuenta.
5. Solicita el periodo y los informes deseados. Descargar grandes históricos puede tardar por los límites de Amazon. Comprueba la cobertura y los errores antes de usar los totales.

Las credenciales se cifran mediante Windows DPAPI para tu usuario. No se envían a GitHub ni a un servidor del proyecto. No pegues claves en incidencias, capturas o chats.

## 4. Usar y exportar

El resumen abre desde el día 1 del mes actual hasta hoy, según la fecha del PC. Cambia fechas, mercado y moneda cuando necesites otro periodo. Arriba puedes cambiar Español / English.

**Exportación contable** prepara un ZIP para el periodo y mercados seleccionados: movimientos, resúmenes, pagos, documentos disponibles y advertencias. Los documentos originales conservan su contenido. Revisa los pendientes con tu contable; la aplicación no certifica una declaración fiscal.

## 5. Dónde se guarda todo

- Programa por defecto: `%LOCALAPPDATA%\Programs\AmazonFinanceOpenSource`.
- Datos privados: `%LOCALAPPDATA%\AmazonFinanceOpenSource\data`.
- Dirección local: `https://127.0.0.1:18766/`.

Haz copias de la carpeta de datos con la aplicación cerrada, en un destino privado. DPAPI vincula los secretos al perfil de Windows: una copia de archivos no garantiza recuperar las credenciales en otro PC. En otro equipo, vuelve a conectar Amazon y crea un acceso propio. No subas la carpeta de datos al repositorio.

## 6. Actualizar o desinstalar

Cierra la ventana de control antes de instalar una nueva versión. El instalador actualiza archivos del programa y conserva la carpeta de datos.

Desinstala desde Configuración de Windows → Aplicaciones. Los datos privados se conservan para evitar pérdidas. Si quieres borrarlos, hazlo manualmente tras verificar tu copia. El certificado local permanece en el almacén del usuario; puedes identificarlo por **AMAZON FINANCE OPEN SOURCE local** y retirarlo desde `certmgr.msc` cuando ya no utilices la aplicación.

## Problemas habituales

- Puerto ocupado: cierra una instancia anterior; la aplicación no sustituye procesos ajenos.
- Aviso de certificado persistente: cierra y abre de nuevo el navegador tras el primer inicio; comprueba que usas la dirección exacta.
- Sin datos: configurar credenciales no descarga automáticamente toda la cuenta. Solicita informes o movimientos y comprueba el estado.
- Error de permisos de Amazon: revisa los roles aprobados y la región, sin compartir las credenciales.

Herramienta independiente; el nombre Amazon identifica la plataforma con la que conecta y no implica afiliación ni aprobación de Amazon.
