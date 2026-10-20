# Preparar la publicación

El repositorio local contiene exclusivamente código, documentación y pruebas sintéticas. No se ha creado ni publicado un repositorio remoto.

Antes de publicar, ejecuta `python scripts/audit-release.py` y revisa `git status --short`. No añadas bases de datos, documentos, archivos DPAPI, claves privadas, certificados, capturas de cuentas, `.env` ni copias de seguridad. No uses `git add -f` para saltarte `.gitignore`.

Cuando se haya decidido propietario, nombre y visibilidad del remoto:

```powershell
git add .
git commit -m "Initial clean local Windows application"
git branch -M main
git remote add origin https://github.com/OWNER/amazon-finance-open-source.git
git push -u origin main
```

OWNER es un marcador: reemplázalo por el propietario elegido. Publicar el código y autorizar una aplicación privada en Amazon son acciones distintas. Cada usuario deberá crear su propia autorización; no se comparte ninguna aplicación, token ni dato vendedor del autor.

Para distribuir el instalador, adjunta el `.exe`, su SHA-256, la guía y las notas de versión a una Release. Antes de difusión general conviene probar instalación, actualización y desinstalación en otra máquina Windows limpia y obtener una firma de editor si se requiere reconocimiento de Windows.
