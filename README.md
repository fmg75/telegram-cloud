# ☁️ Telegram Cloud Storage

Un sistema simple y gratuito de almacenamiento en la nube que utiliza Telegram como backend de almacenamiento con una interfaz web intuitiva construida con Streamlit.

## 🌟 Características

- **💾 Almacenamiento gratuito**: Utiliza Telegram como backend de almacenamiento (hasta 2GB por archivo)
- **🌐 Interfaz web**: Aplicación web intuitiva construida con Streamlit
- **📱 Multiplataforma**: Funciona en cualquier dispositivo con navegador web
- **🔐 Seguro**: Tus archivos se almacenan en los servidores seguros de Telegram
- **📊 Gestión completa**: Subir, descargar, eliminar y organizar archivos
- **🔍 Búsqueda y filtrado**: Encuentra tus archivos rápidamente
- **📈 Estadísticas**: Visualiza el uso de tu almacenamiento
- **🏠 Configuración flexible**: Elige dónde guardar los datos localmente

## 📋 Requisitos

- Python 3.7 o superior
- Una cuenta de Telegram
- Bot de Telegram (gratuito)

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
   streamlit run telegram_cloud_.py
   ```
   > 📁 La aplicación creará automáticamente la carpeta `data/` para guardar las credenciales y el índice de archivos.

4. **Abre tu navegador** en `http://localhost:8501`

## ⚙️ Configuración

### 1. Crear un Bot de Telegram

1. Abre Telegram y busca `@BotFather`
2. Envía el comando `/newbot`
3. Sigue las instrucciones para crear tu bot
4. Copia el **Token del Bot** que te proporciona BotFather
5. Guarda este token, lo necesitarás en la aplicación

### 2. Obtener tu Chat ID

La aplicación puede obtener automáticamente tu Chat ID:

1. **Método automático** (recomendado):
   - Busca tu bot en Telegram
   - Envía cualquier mensaje al bot
   - En la aplicación web, usa la función "Obtener Chat ID automáticamente"

2. **Método manual**:
   - Puedes ingresar manualmente tu Chat ID si lo conoces

### 3. Configuración en la aplicación

1. Abre la aplicación web
2. En la configuración inicial:
   - Ingresa tu **Token del Bot**
   - Configura tu **Chat ID** (automático o manual)
3. ¡Listo! Ya puedes empezar a usar tu almacenamiento en la nube

## 📖 Uso

### 📤 Subir archivos

1. Ve a la pestaña "Subir Archivos"
2. Selecciona uno o varios archivos (máximo 2GB cada uno)
3. Opcionalmente, cambia el nombre del archivo
4. Presiona "Subir"

### 📁 Gestionar archivos

1. Ve a la pestaña "Mis Archivos"
2. Busca archivos usando el campo de búsqueda
3. Ordena por fecha, tamaño o nombre
4. Descarga o elimina archivos según necesites

### 📊 Ver estadísticas

1. Ve a la pestaña "Estadísticas"
2. Visualiza:
   - Total de archivos almacenados
   - Espacio utilizado
   - Archivos más grandes
   - Actividad reciente

## 🗂️ Estructura del proyecto

```
telegram-cloud-storage/
├── telegram_cloud_.py      # Aplicación principal
├── requirements.txt        # Dependencias de Python
├── README.md              # Este archivo
├── .gitignore             # Archivos a ignorar en Git
└── data/                  # Directorio de datos (se crea automáticamente)
    ├── credentials.json   # Credenciales guardadas (NO se sube a Git)
    └── telegram_cloud_index.json  # Índice de archivos (NO se sube a Git)
```

> ⚠️ **Importante**: La carpeta `data/` y todos los archivos `.json` están incluidos en `.gitignore` por seguridad, ya que contienen información sensible como tokens y credenciales.

## 🔧 Configuración avanzada

### Cambiar directorio de datos

La aplicación permite configurar dónde se guardan los datos locales:

- **🏠 Directorio del usuario**: `~/.telegram_cloud/`
- **📁 Directorio del proyecto**: `./data/`
- **🎯 Personalizado**: Cualquier ruta que especifiques

### Variables de entorno

El proyecto detecta automáticamente si se ejecuta en servicios de hosting como Heroku o Streamlit Cloud y ajusta la configuración de directorios accordingly.

## 🛡️ Seguridad y privacidad

- **Datos locales**: Solo se guardan las credenciales y un índice de archivos localmente
- **Archivos**: Se almacenan directamente en Telegram, no en servidores terceros
- **Token del bot**: Se guarda de forma segura en tu sistema local
- **Sin rastreo**: La aplicación no envía datos a terceros
- **⚠️ Git**: Los archivos de configuración y credenciales están excluidos del control de versiones por seguridad

### 🔐 Archivos sensibles

Los siguientes archivos **NO se suben a Git** por seguridad:
- `data/credentials.json` - Contiene tu token de bot y Chat ID
- `data/telegram_cloud_index.json` - Índice de tus archivos
- Cualquier archivo `.json` en el proyecto

## ⚠️ Limitaciones

- **Tamaño máximo por archivo**: 2GB (limitación de Telegram)
- **Tipos de archivo**: Todos los tipos son compatibles
- **Velocidad**: Depende de tu conexión a internet y los servidores de Telegram
- **Eliminación**: Los archivos eliminados del índice permanecen en Telegram

## 🤝 Contribuir

¡Las contribuciones son bienvenidas! Si tienes ideas para mejoras:

1. Fork el proyecto
2. Crea una rama para tu feature (`git checkout -b feature/AmazingFeature`)
3. Commit tus cambios (`git commit -m 'Add some AmazingFeature'`)
4. Push a la rama (`git push origin feature/AmazingFeature`)
5. Abre un Pull Request

## 📝 Ideas para futuras mejoras

- [ ] Organización por carpetas
- [ ] Compartir archivos con otros usuarios
- [ ] Cifrado de archivos antes de subir
- [ ] Sincronización automática de carpetas
- [ ] API REST para integración con otras aplicaciones
- [ ] Aplicación de escritorio
- [ ] Vista previa de archivos (imágenes, PDFs, etc.)

## 🐛 Reportar problemas

Si encuentras algún problema:

1. Revisa si ya existe un issue similar
2. Crea un nuevo issue con:
   - Descripción detallada del problema
   - Pasos para reproducirlo
   - Versión de Python y sistema operativo
   - Logs de error si los hay

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
- [Cómo crear un bot de Telegram](https://core.telegram.org/bots#3-how-do-i-create-a-bot)# telegram-cloud
