# ☁️ Telegram Cloud Storage

Un sistema de almacenamiento en la nube que utiliza Telegram como backend con sincronización automática de metadatos. Cada usuario tiene su propio espacio de almacenamiento aislado con interfaz web intuitiva construida con Streamlit.

## 🌟 Características

- **💾 Almacenamiento gratuito**: Utiliza Telegram como backend de almacenamiento (hasta 2GB por archivo)
- **🔄 Sincronización automática**: Los metadatos se sincronizan automáticamente entre dispositivos
- **👥 Multiusuario**: Cada token de bot crea un espacio de almacenamiento único y aislado
- **📌 Índice remoto**: El índice de archivos se almacena como mensaje fijado en Telegram
- **🌐 Interfaz web**: Aplicación web intuitiva construida con Streamlit
- **📱 Multiplataforma**: Funciona en cualquier dispositivo con navegador web
- **🔐 Seguro**: Tus archivos se almacenan en los servidores seguros de Telegram
- **📊 Gestión completa**: Subir, descargar, eliminar y organizar archivos
- **🔍 Búsqueda y filtrado**: Encuentra tus archivos rápidamente
- **📈 Estadísticas**: Visualiza el uso de tu almacenamiento
- **📂 Subida de carpetas**: Comprime y sube carpetas completas como ZIP

## 📋 Requisitos

- Python 3.7 o superior
- Una cuenta de Telegram
- Bot de Telegram (gratuito) con permisos de administrador

## 🚀 Instalación

1. **Clona el repositorio**:
   ```bash
   git clone https://github.com/tu-usuario/telegram-cloud-storage.git
   cd telegram-cloud-storage
   ```

2. **Instala las dependencias**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Ejecuta la aplicación**:
   ```bash
   streamlit run telegram_cloud.py
   ```

4. **Abre tu navegador** en `http://localhost:8501`

## ⚙️ Configuración

### 1. Crear un Bot de Telegram

1. Abre Telegram y busca `@BotFather`
2. Envía el comando `/newbot`
3. Sigue las instrucciones para crear tu bot
4. Copia el **Token del Bot** que te proporciona BotFather
5. **🔑 IMPORTANTE**: Haz que tu bot sea **Administrador** del chat/grupo/canal donde lo uses
6. **📌 CRÍTICO**: Asegúrate de que el bot tenga el permiso para **"Fijar Mensajes"**

### 2. Configuración del Chat

Para usar el bot, necesitas darle permisos de administrador:

**Para chat privado:**
- Simplemente envía un mensaje a tu bot

**Para grupo o canal:**
1. Añade el bot al grupo/canal
2. Promociona el bot a **Administrador**
3. Asegúrate de que tenga el permiso para **"Fijar Mensajes"**
4. Envía cualquier mensaje en el grupo/canal

### 3. Configuración en la aplicación

1. Abre la aplicación web
2. En el panel lateral:
   - Ingresa tu **Token del Bot**
   - La aplicación detectará automáticamente los chats disponibles
   - Selecciona el chat donde quieres almacenar tus archivos
   - Presiona "Guardar Configuración"
3. ¡Listo! La aplicación sincronizará automáticamente tu índice de archivos

## 📖 Uso

### 📤 Subir archivos

1. Ve a la pestaña "Subir"
2. **Archivos individuales**:
   - Selecciona uno o varios archivos (máximo 2GB cada uno)
   - Opcionalmente, cambia el nombre remoto del archivo
   - Presiona "Subir"
3. **Carpetas completas**:
   - Ingresa la ruta local de la carpeta
   - La aplicación creará un archivo ZIP automáticamente
   - Personaliza el nombre del ZIP si lo deseas
   - Presiona "Subir Carpeta"

### 📁 Gestionar archivos

1. Ve a la pestaña "Archivos"
2. **🔄 Sincronización**: Usa el botón "Sincronizar Ahora" para actualizar el índice
3. **🔍 Búsqueda**: Busca archivos usando el campo de búsqueda
4. **📊 Ordenación**: Ordena por fecha, tamaño o nombre
5. **📥 Descarga**: 
   - Presiona "Preparar Descarga" para descargar el archivo de Telegram
   - Luego presiona "¡Guardar Ahora!" para guardarlo en tu dispositivo
6. **🗑️ Eliminación**: Elimina archivos del índice (permanecen en Telegram)

### 📊 Ver estadísticas

1. Ve a la pestaña "Estadísticas"
2. Visualiza:
   - Total de archivos almacenados
   - Espacio utilizado
   - Promedio de tamaño por archivo
   - Los 5 archivos más grandes
   - Los 5 archivos más recientes

## 🔄 Sincronización

### Cómo funciona

- **Índice remoto**: El índice de archivos se guarda como un archivo JSON fijado en tu chat de Telegram
- **Sincronización automática**: Cada vez que subes o eliminas un archivo, el índice se actualiza automáticamente
- **Acceso desde múltiples dispositivos**: Puedes acceder a tus archivos desde cualquier dispositivo usando el mismo token
- **Consistencia**: Si falla la actualización del índice, la operación se revierte para mantener la consistencia

### Sincronización manual

Si necesitas sincronizar manualmente (por ejemplo, si alguien más modificó el chat):
1. Ve a la pestaña "Archivos"
2. Presiona el botón "🔄 Sincronizar Ahora"

## 🗂️ Estructura del proyecto

```
telegram-cloud-storage/
├── telegram_cloud.py          # Aplicación principal
├── requirements.txt           # Dependencias de Python
├── README.md                 # Este archivo
└── .gitignore               # Archivos a ignorar en Git
```

## 🔧 Arquitectura técnica

### Gestión de usuarios
- **Hash único**: Cada usuario se identifica por un hash MD5 de su token de bot
- **Aislamiento**: Los datos de cada usuario están completamente aislados
- **Configuración temporal**: Solo se guarda la configuración básica localmente

### Almacenamiento del índice
- **Archivo remoto**: `_telegram_cloud_storage_index.v1.json`
- **Mensaje fijado**: El índice siempre está fijado en el chat para fácil acceso
- **Versionado**: Los índices antiguos se desanclan automáticamente
- **Formato**: JSON con metadatos completos de cada archivo

### Gestión de archivos
- **Hash de contenido**: Cada archivo tiene un hash MD5 para detectar duplicados
- **Metadatos completos**: Fecha de subida, tamaño, nombre original, file_id de Telegram
- **Consistencia**: Las operaciones se revierten si falla la actualización del índice

## 🛡️ Seguridad y privacidad

- **Datos locales mínimos**: Solo se guarda configuración básica temporalmente
- **Archivos en Telegram**: Se almacenan directamente en los servidores seguros de Telegram
- **Token del bot**: Se guarda temporalmente solo durante la sesión
- **Sin rastreo**: La aplicación no envía datos a terceros
- **Aislamiento por usuario**: Cada token crea un espacio completamente independiente

## ⚠️ Limitaciones importantes

- **Tamaño máximo por archivo**: 2GB (limitación de Telegram)
- **Permisos requeridos**: El bot DEBE ser administrador con permiso para "Fijar Mensajes"
- **Eliminación**: Los archivos eliminados del índice permanecen en Telegram
- **Dependencia de Telegram**: Si Telegram está caído, el servicio no funciona
- **Velocidad**: Depende de tu conexión y los servidores de Telegram

## 🚨 Troubleshooting

### Error: "No se pudo fijar el nuevo índice"
**Causa**: El bot no tiene permisos de administrador o no puede fijar mensajes.
**Solución**: 
1. Ve a la configuración del grupo/canal
2. Promociona el bot a administrador
3. Asegúrate de que tenga el permiso "Fijar Mensajes" habilitado

### Error: "No se encontró un índice remoto"
**Causa**: Es normal en el primer uso o si se eliminó el mensaje fijado.
**Solución**: Simplemente sube un archivo y se creará automáticamente el índice.

### Error: "Chat ID no configurado"
**Causa**: La configuración no se completó correctamente.
**Solución**: 
1. Ve al panel lateral
2. Presiona "🔄 Reiniciar configuración"
3. Vuelve a configurar desde cero

### La aplicación no detecta chats
**Causa**: No se han enviado mensajes al bot recientemente.
**Solución**: Envía un mensaje a tu bot y recarga la página.

## 🤝 Contribuir

¡Las contribuciones son bienvenidas! Si tienes ideas para mejoras:

1. Fork el proyecto
2. Crea una rama para tu feature (`git checkout -b feature/AmazingFeature`)
3. Commit tus cambios (`git commit -m 'Add some AmazingFeature'`)
4. Push a la rama (`git push origin feature/AmazingFeature`)
5. Abre un Pull Request

## 📝 Ideas para futuras mejoras

- [ ] Cifrado de archivos antes de subir
- [ ] Organización por carpetas virtuales
- [ ] Compartir archivos con otros usuarios
- [ ] Sincronización automática de carpetas locales
- [ ] API REST para integración con otras aplicaciones
- [ ] Aplicación de escritorio nativa
- [ ] Vista previa de archivos (imágenes, PDFs, etc.)
- [ ] Papelera de reciclaje para archivos eliminados
- [ ] Estadísticas de uso más detalladas
- [ ] Notificaciones push para cambios

## 🐛 Reportar problemas

Si encuentras algún problema:

1. Revisa la sección de **Troubleshooting** primero
2. Verifica que el bot tenga los permisos correctos
3. Crea un issue con:
   - Descripción detallada del problema
   - Pasos para reproducirlo
   - Logs de error si los hay
   - Configuración de permisos del bot

## 📄 Licencia

Este proyecto está bajo la Licencia MIT. Consulta el archivo `LICENSE` para más detalles.

## 🙏 Agradecimientos

- [Streamlit](https://streamlit.io/) - Por el excelente framework de aplicaciones web
- [Telegram](https://telegram.org/) - Por proporcionar una API robusta y gratuita
- La comunidad de Python por las librerías utilizadas

---

**⭐ Si te gusta este proyecto, dale una estrella en GitHub!**

**🔗 Enlaces útiles:**
- [Documentación de Telegram Bot API](https://core.telegram.org/bots/api)
- [Documentación de Streamlit](https://docs.streamlit.io/)
- [Cómo crear un bot de Telegram](https://core.telegram.org/bots#3-how-do-i-create-a-bot)
- [Gestión de permisos en grupos de Telegram](https://telegram.org/tour/groups)