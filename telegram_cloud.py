#!/usr/bin/env python3
"""
Telegram Cloud Storage - Streamlit Web App
Un sistema simple de almacenamiento en la nube usando Telegram con interfaz web
"""

import os
import sys
import json
import hashlib
import streamlit as st
import requests
from datetime import datetime
from pathlib import Path
import time
import zipfile
import io
import logging

# Configuración de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuración de la página
st.set_page_config(
    page_title="Telegram Cloud Storage",
    page_icon="☁️",
    layout="wide",
    initial_sidebar_state="expanded"
)

def ensure_directory_permissions(directory):
    """Asegura que el directorio tenga los permisos correctos"""
    try:
        directory.mkdir(exist_ok=True, parents=True)
        if os.name != 'nt':  # Solo para Linux/macOS
            os.chmod(directory, 0o700)  # rwx para el usuario dueño
        logger.info(f"Directorio configurado con permisos: {directory}")
        return True
    except Exception as e:
        logger.error(f"Error configurando directorio {directory}: {str(e)}")
        st.error(f"❌ No se pudo configurar el directorio: {str(e)}")
        return False

def get_default_data_directory():
    """Obtiene el directorio de datos por defecto (seguro, local)"""
    try:
        user_home = Path.home()
        logger.info(f"Directorio home detectado: {user_home}")

        # Verificar permisos de escritura
        test_dir = user_home / ".telegram_cloud_test"
        test_dir.mkdir(exist_ok=True, parents=True)
        test_file = test_dir / "test.txt"
        test_file.write_text("test")
        test_file.unlink()
        test_dir.rmdir()

        # Definir ruta según SO
        if os.name == 'nt':  # Windows
            base_dir = user_home / "Documents" / "TelegramCloudStorage"
        else:  # Linux/macOS - usar siempre el directorio oculto en home
            base_dir = user_home / ".telegram_cloud_storage"

        logger.info(f"Usando directorio de datos: {base_dir}")
        return base_dir

    except (PermissionError, OSError) as e:
        logger.warning(f"No se pudo escribir en el directorio home: {str(e)}")
        
        # Fallback: usar directorio temporal
        import tempfile
        base_dir = Path(tempfile.gettempdir()) / "telegram_cloud_storage"
        logger.warning(f"Usando directorio temporal como fallback: {base_dir}")
        st.warning(f"⚠️ No se pudo escribir en el directorio home. Usando directorio temporal: {base_dir}")
        return base_dir

class TelegramCloudStorage:
    def __init__(self, bot_token, chat_id, data_directory=None):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
        
        if data_directory:
            self.data_dir = Path(data_directory)
        else:
            self.data_dir = get_default_data_directory()
        
        if not ensure_directory_permissions(self.data_dir):
            raise RuntimeError(f"No se pudo configurar el directorio de datos: {self.data_dir}")
        
        self.index_file = self.data_dir / "telegram_cloud_index.json"
        self.load_index()
    
    def load_index(self):
        """Carga el índice de archivos almacenados"""
        try:
            with open(self.index_file, 'r') as f:
                self.index = json.load(f)
            logger.info(f"Índice cargado correctamente desde {self.index_file}")
        except FileNotFoundError:
            self.index = {}
            logger.info("No se encontró archivo de índice, creando uno nuevo")
        except json.JSONDecodeError:
            self.index = {}
            logger.error("Índice corrupto, creando uno nuevo")
    
    def save_index(self):
        """Guarda el índice de archivos"""
        try:
            with open(self.index_file, 'w') as f:
                json.dump(self.index, f, indent=2)
            logger.info(f"Índice guardado correctamente en {self.index_file}")
        except Exception as e:
            logger.error(f"Error guardando índice: {str(e)}")
            raise
    
    def get_file_hash(self, file_bytes):
        """Calcula el hash MD5 de bytes de archivo"""
        hash_md5 = hashlib.md5()
        hash_md5.update(file_bytes)
        return hash_md5.hexdigest()
    
    def upload_file(self, file_bytes, filename, remote_name=None):
        """Sube un archivo a Telegram"""
        file_size = len(file_bytes)
        if file_size > 2 * 1024 * 1024 * 1024:  # 2GB
            return False, "El archivo es demasiado grande (máximo 2GB)"
        
        remote_name = remote_name or filename
        file_hash = self.get_file_hash(file_bytes)
        
        # Verificar si ya existe
        if remote_name in self.index:
            if self.index[remote_name]['hash'] == file_hash:
                return True, f"El archivo '{remote_name}' ya existe y es idéntico"
        
        try:
            files = {'document': (filename, file_bytes)}
            data = {
                'chat_id': self.chat_id,
                'caption': f"☁️ {remote_name}\n🕒 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            }
            
            logger.info(f"Intentando subir archivo: {remote_name} ({file_size} bytes)")
            response = requests.post(f"{self.base_url}/sendDocument", 
                                   files=files, data=data, timeout=60)
            
            if response.status_code == 200:
                result = response.json()
                if result['ok']:
                    file_id = result['result']['document']['file_id']
                    
                    # Actualizar índice
                    self.index[remote_name] = {
                        'file_id': file_id,
                        'hash': file_hash,
                        'size': file_size,
                        'upload_date': datetime.now().isoformat(),
                        'original_filename': filename
                    }
                    self.save_index()
                    
                    logger.info(f"Archivo subido exitosamente: {remote_name}")
                    return True, f"Archivo subido exitosamente: {remote_name}"
                else:
                    error_msg = f"Error de API: {result.get('description', 'Error desconocido')}"
                    logger.error(error_msg)
                    return False, error_msg
            else:
                error_msg = f"Error HTTP: {response.status_code}"
                logger.error(error_msg)
                return False, error_msg
                
        except Exception as e:
            error_msg = f"Error al subir archivo: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
    
    def download_file(self, remote_name):
        """Descarga un archivo de Telegram"""
        if remote_name not in self.index:
            return None, f"Archivo '{remote_name}' no encontrado"
        
        file_info = self.index[remote_name]
        file_id = file_info['file_id']
        
        try:
            logger.info(f"Intentando descargar archivo: {remote_name}")
            # Obtener información del archivo
            response = requests.get(f"{self.base_url}/getFile?file_id={file_id}")
            
            if response.status_code == 200:
                result = response.json()
                if result['ok']:
                    file_path = result['result']['file_path']
                    file_url = f"https://api.telegram.org/file/bot{self.bot_token}/{file_path}"
                    
                    # Descargar archivo
                    file_response = requests.get(file_url)
                    if file_response.status_code == 200:
                        logger.info(f"Archivo descargado exitosamente: {remote_name}")
                        return file_response.content, f"Archivo descargado exitosamente"
                    else:
                        error_msg = f"Error al descargar: {file_response.status_code}"
                        logger.error(error_msg)
                        return None, error_msg
                else:
                    error_msg = f"Error de API: {result.get('description', 'Error desconocido')}"
                    logger.error(error_msg)
                    return None, error_msg
            else:
                error_msg = f"Error HTTP: {response.status_code}"
                logger.error(error_msg)
                return None, error_msg
                
        except Exception as e:
            error_msg = f"Error al descargar archivo: {str(e)}"
            logger.error(error_msg)
            return None, error_msg
    
    def delete_file(self, remote_name):
        """Elimina un archivo del índice"""
        if remote_name not in self.index:
            return False, f"Archivo '{remote_name}' no encontrado"
        
        try:
            del self.index[remote_name]
            self.save_index()
            logger.info(f"Archivo eliminado del índice: {remote_name}")
            return True, f"Archivo '{remote_name}' eliminado del índice"
        except Exception as e:
            error_msg = f"Error eliminando archivo del índice: {str(e)}"
            logger.error(error_msg)
            return False, error_msg

def get_chat_id(bot_token):
    """Obtiene Chat IDs del bot"""
    url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
    
    try:
        response = requests.get(url)
        
        if response.status_code == 200:
            data = response.json()
            
            if data['ok'] and data['result']:
                chats = []
                seen_chats = set()
                
                for update in data['result']:
                    if 'message' in update:
                        chat = update['message']['chat']
                        chat_id = chat['id']
                        chat_type = chat['type']
                        
                        if chat_id not in seen_chats:
                            seen_chats.add(chat_id)
                            
                            if chat_type == 'private':
                                first_name = chat.get('first_name', 'N/A')
                                username = chat.get('username', 'N/A')
                                chats.append({
                                    'id': chat_id,
                                    'type': 'Personal',
                                    'name': f"{first_name} (@{username})",
                                    'display': f"👤 {first_name} ({chat_id})"
                                })
                                
                            elif chat_type == 'group':
                                title = chat.get('title', 'N/A')
                                chats.append({
                                    'id': chat_id,
                                    'type': 'Grupo',
                                    'name': title,
                                    'display': f"👥 {title} ({chat_id})"
                                })
                                
                            elif chat_type == 'channel':
                                title = chat.get('title', 'N/A')
                                chats.append({
                                    'id': chat_id,
                                    'type': 'Canal',
                                    'name': title,
                                    'display': f"📢 {title} ({chat_id})"
                                })
                
                return chats, "Chat IDs obtenidos exitosamente"
            else:
                return [], "No se encontraron mensajes recientes"
        else:
            return [], f"Error HTTP: {response.status_code}"
            
    except Exception as e:
        return [], f"Error: {str(e)}"

def get_config_file():
    """Obtiene la ubicación del archivo de configuración"""
    config_dir = get_default_data_directory()
    if not ensure_directory_permissions(config_dir):
        raise RuntimeError(f"No se pudo configurar el directorio de configuración: {config_dir}")
    return config_dir / "config.json"

def save_config(bot_token, chat_id, data_directory=None):
    """Guarda la configuración completa"""
    config_file = get_config_file()
    config = {
        'bot_token': bot_token,
        'chat_id': chat_id,
        'data_directory': str(data_directory) if data_directory else None,
        'saved_date': datetime.now().isoformat()
    }
    
    try:
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=2)
        logger.info(f"Configuración guardada en {config_file}")
        return True
    except Exception as e:
        logger.error(f"Error guardando configuración: {str(e)}")
        return False

def load_config():
    """Carga la configuración guardada"""
    config_file = get_config_file()
    try:
        with open(config_file, 'r') as f:
            config = json.load(f)
        logger.info(f"Configuración cargada desde {config_file}")
        return config
    except FileNotFoundError:
        logger.info("No se encontró archivo de configuración")
        return None
    except json.JSONDecodeError:
        logger.error("Archivo de configuración corrupto")
        return None

def get_data_directory():
    """Obtiene el directorio de datos actual (configurado o por defecto)"""
    config = load_config()
    if config and config.get('data_directory'):
        data_dir = Path(config['data_directory'])
    else:
        data_dir = get_default_data_directory()
    
    if not ensure_directory_permissions(data_dir):
        raise RuntimeError(f"No se pudo configurar el directorio de datos: {data_dir}")
    
    return data_dir

def format_file_size(size_bytes):
    """Formatea el tamaño del archivo"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024**2:
        return f"{size_bytes/1024:.1f} KB"
    elif size_bytes < 1024**3:
        return f"{size_bytes/(1024**2):.1f} MB"
    else:
        return f"{size_bytes/(1024**3):.1f} GB"

def zip_folder(folder_path):
    """Comprime una carpeta en un archivo ZIP en memoria"""
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, start=folder_path)
                zipf.write(file_path, arcname)
    zip_buffer.seek(0)
    return zip_buffer

def main():
    st.title("☁️ Telegram Cloud Storage")
    st.markdown("---")
    
    # Cargar configuración guardada
    config = load_config()
    
    # Sidebar para configuración
    with st.sidebar:
        st.header("⚙️ Configuración")
        
        # Configuración del directorio de datos
        st.subheader("📂 Directorio de Datos")
        current_dir = get_data_directory()
        
        # Mostrar directorio actual
        st.info(f"📁 Actual: `{current_dir}`")
        
        # Botón para explorar directorio
        if st.button("🔍 Explorar directorio"):
            import subprocess
            import platform
            try:
                if platform.system() == "Windows":
                    subprocess.Popen(f'explorer "{current_dir}"')
                elif platform.system() == "Darwin":  # macOS
                    subprocess.Popen(["open", str(current_dir)])
                else:  # Linux
                    subprocess.Popen(["xdg-open", str(current_dir)])
                st.success("✅ Directorio abierto")
            except:
                st.info(f"📂 Ruta: {current_dir}")
        
        st.markdown("---")
        
        # Estado de configuración
        if config:
            st.success("✅ Bot configurado")
            st.info(f"🤖 Chat ID: {config['chat_id']}")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🔄 Reconfigurar"):
                    config_file = get_config_file()
                    if config_file.exists():
                        config_file.unlink()
                    st.rerun()
            
            with col2:
                if st.button("🔄 Refrescar"):
                    st.rerun()
        else:
            st.warning("⚠️ Configura tu bot primero")
    
    # Configuración inicial del bot
    if not config:
        st.header("🚀 Configuración inicial")
        
        tab1, tab2 = st.tabs(["📝 Configurar Bot Token", "📱 Configurar Chat ID"])
        
        with tab1:
            st.subheader("1️⃣ Configurar Bot Token")
            st.markdown("""
            **Instrucciones:**
            1. Abre Telegram y busca @BotFather
            2. Envía `/newbot` y sigue las instrucciones
            3. Copia el token que te proporciona
            4. Pégalo aquí abajo
            """)
            
            bot_token = st.text_input("🔑 Token del Bot:", type="password")
            
            if bot_token:
                st.session_state.bot_token = bot_token
                st.success("✅ Token guardado temporalmente")
        
        with tab2:
            st.subheader("2️⃣ Configurar Chat ID")
            
            if 'bot_token' not in st.session_state:
                st.warning("⚠️ Primero configura el Bot Token en la pestaña anterior")
            else:
                option = st.radio("Selecciona una opción:", 
                                ["🔍 Obtener Chat ID automáticamente", 
                                 "✏️ Ingresar Chat ID manualmente"])
                
                if option == "🔍 Obtener Chat ID automáticamente":
                    st.markdown("""
                    **Instrucciones:**
                    1. Busca tu bot en Telegram
                    2. Envía cualquier mensaje al bot
                    3. Presiona el botón para obtener tu Chat ID
                    """)
                    
                    if st.button("🔍 Obtener Chat ID"):
                        with st.spinner("Buscando Chat IDs..."):
                            chats, message = get_chat_id(st.session_state.bot_token)
                            
                        if chats:
                            st.success(message)
                            st.session_state.available_chats = chats
                    
                    if 'available_chats' in st.session_state and st.session_state.available_chats:
                        chat_options = [chat['display'] for chat in st.session_state.available_chats]
                        selected = st.selectbox("Selecciona tu chat:", chat_options)
                        
                        if selected:
                            selected_chat = next(chat for chat in st.session_state.available_chats if chat['display'] == selected)
                            
                            if st.button("💾 Guardar configuración"):
                                if save_config(st.session_state.bot_token, selected_chat['id']):
                                    st.success("✅ Configuración guardada exitosamente")
                                    st.balloons()
                                    # Limpiar session state
                                    for key in ['bot_token', 'available_chats']:
                                        if key in st.session_state:
                                            del st.session_state[key]
                                    time.sleep(1)
                                    st.rerun()
                                else:
                                    st.error("❌ Error al guardar la configuración")
                
                else:  # Ingresar manualmente
                    chat_id = st.text_input("📱 Chat ID:", help="Ingresa tu Chat ID (número)")
                    
                    if chat_id:
                        try:
                            chat_id = int(chat_id)
                            if st.button("💾 Guardar configuración"):
                                if save_config(st.session_state.bot_token, chat_id):
                                    st.success("✅ Configuración guardada exitosamente")
                                    st.balloons()
                                    # Limpiar session state
                                    if 'bot_token' in st.session_state:
                                        del st.session_state['bot_token']
                                    time.sleep(1)
                                    st.rerun()
                                else:
                                    st.error("❌ Error al guardar la configuración")
                        except ValueError:
                            st.error("❌ El Chat ID debe ser un número")
    
    else:
        # Interfaz principal
        bot_token = config['bot_token']
        chat_id = config['chat_id']
        
        # Inicializar cliente con directorio configurado
        try:
            data_dir = get_data_directory()
            client = TelegramCloudStorage(bot_token, chat_id, data_dir)
        except Exception as e:
            st.error(f"❌ Error al inicializar el cliente: {str(e)}")
            st.stop()
        
        # Tabs principales
        tab1, tab2, tab3 = st.tabs(["📤 Subir Archivos", "📁 Mis Archivos", "📊 Estadísticas"])
        
        with tab1:
            st.header("📤 Subir Archivos")
            
            # Opción para subir archivos o carpetas
            upload_option = st.radio(
                "Selecciona el tipo de subida:",
                ["📄 Archivos", "📂 Carpeta (se comprimirá en ZIP)"],
                horizontal=True
            )
            
            if upload_option == "📄 Archivos":
                uploaded_files = st.file_uploader(
                    "Selecciona archivos para subir:",
                    accept_multiple_files=True,
                    help="Máximo 2GB por archivo"
                )
                
                if uploaded_files:
                    st.subheader("📋 Archivos seleccionados:")
                    
                    for uploaded_file in uploaded_files:
                        with st.expander(f"📄 {uploaded_file.name} ({format_file_size(uploaded_file.size)})"):
                            col1, col2 = st.columns([3, 1])
                            
                            with col1:
                                custom_name = st.text_input(
                                    "Nombre personalizado (opcional):",
                                    value=uploaded_file.name,
                                    key=f"name_{uploaded_file.name}"
                                )
                            
                            with col2:
                                if st.button("📤 Subir", key=f"upload_{uploaded_file.name}"):
                                    with st.spinner(f"Subiendo {uploaded_file.name}..."):
                                        file_bytes = uploaded_file.read()
                                        success, message = client.upload_file(
                                            file_bytes, uploaded_file.name, custom_name
                                        )
                                    
                                    if success:
                                        st.success(f"✅ {message}")
                                    else:
                                        st.error(f"❌ {message}")
            
            else:  # Subir carpeta
                st.markdown("### 📂 Subir carpeta")
                folder_path = st.text_input(
                    "Ingresa la ruta completa de la carpeta a subir:",
                    placeholder="Ejemplo: C:/Users/MiUsuario/Documents/MiCarpeta"
                )
                
                if folder_path and os.path.isdir(folder_path):
                    folder_name = os.path.basename(folder_path)
                    zip_name = f"{folder_name}.zip"
                    
                    col1, col2 = st.columns([3, 1])
                    
                    with col1:
                        custom_name = st.text_input(
                            "Nombre personalizado para el ZIP (opcional):",
                            value=zip_name,
                            key="folder_zip_name"
                        )
                    
                    with col2:
                        if st.button("📤 Subir Carpeta"):
                            with st.spinner(f"Comprimiendo y subiendo {folder_name}..."):
                                try:
                                    # Comprimir carpeta
                                    zip_buffer = zip_folder(folder_path)
                                    zip_bytes = zip_buffer.getvalue()
                                    
                                    # Subir archivo ZIP
                                    success, message = client.upload_file(
                                        zip_bytes, zip_name, custom_name
                                    )
                                    
                                    if success:
                                        st.success(f"✅ {message}")
                                    else:
                                        st.error(f"❌ {message}")
                                except Exception as e:
                                    st.error(f"❌ Error al procesar carpeta: {str(e)}")
                elif folder_path:
                    st.error("❌ La ruta especificada no es un directorio válido")

        with tab2:
            st.header("📁 Mis Archivos")
            
            if not client.index:
                st.info("📭 No tienes archivos almacenados")
            else:
                # Filtros
                col1, col2 = st.columns([2, 1])
                with col1:
                    search_term = st.text_input("🔍 Buscar archivos:", "", key="search_term")
                with col2:
                    sort_by = st.selectbox("📊 Ordenar por:", 
                                        ["Fecha (más reciente)", "Fecha (más antiguo)", 
                                         "Tamaño (mayor)", "Tamaño (menor)", "Nombre A-Z", "Nombre Z-A"],
                                        key="sort_by")
                
                # Filtrar archivos
                filtered_files = {}
                for name, info in client.index.items():
                    # Buscar por nombre o extensión
                    if not search_term or (
                        search_term.lower() in name.lower() or 
                        (search_term.startswith('.') and name.lower().endswith(search_term.lower()))
                    ):
                        filtered_files[name] = info
                
                # Ordenar archivos
                if sort_by == "Fecha (más reciente)":
                    sorted_files = sorted(filtered_files.items(), 
                                        key=lambda x: x[1]['upload_date'], reverse=True)
                elif sort_by == "Fecha (más antiguo)":
                    sorted_files = sorted(filtered_files.items(), 
                                        key=lambda x: x[1]['upload_date'])
                elif sort_by == "Tamaño (mayor)":
                    sorted_files = sorted(filtered_files.items(), 
                                        key=lambda x: x[1]['size'], reverse=True)
                elif sort_by == "Tamaño (menor)":
                    sorted_files = sorted(filtered_files.items(), 
                                        key=lambda x: x[1]['size'])
                elif sort_by == "Nombre A-Z":
                    sorted_files = sorted(filtered_files.items())
                else:  # Nombre Z-A
                    sorted_files = sorted(filtered_files.items(), reverse=True)
                
                st.info(f"📋 Mostrando {len(sorted_files)} de {len(client.index)} archivos")
                
                # Mostrar archivos
                for name, info in sorted_files:
                    expander_title = f"📄 {name} ({format_file_size(info['size'])})"
                    
                    with st.expander(expander_title):
                        st.write(f"**Nombre:** {name}")
                        
                        col1, col2, col3 = st.columns([2, 1, 1])
                        
                        with col1:
                            upload_date = datetime.fromisoformat(info['upload_date'])
                            st.write(f"📅 **Subido:** {upload_date.strftime('%d/%m/%Y %H:%M')}")
                            st.write(f"📊 **Tamaño:** {format_file_size(info['size'])}")
                            st.write(f"🔒 **Hash:** `{info['hash'][:16]}...`")
                        
                        with col2:
                            if st.button("📥 Descargar", key=f"download_{name}"):
                                with st.spinner(f"Descargando {name}..."):
                                    file_content, message = client.download_file(name)
                                
                                if file_content:
                                    st.download_button(
                                        label="💾 Guardar archivo",
                                        data=file_content,
                                        file_name=name,
                                        mime="application/octet-stream",
                                        key=f"save_{name}"
                                    )
                                    st.success(f"✅ {message}")
                                else:
                                    st.error(f"❌ {message}")
                        
                        with col3:
                            if st.button("🗑️ Eliminar", key=f"delete_{name}"):
                                success, message = client.delete_file(name)
                                if success:
                                    st.success(f"✅ {message}")
                                    st.info("⚠️ El archivo permanece en Telegram")
                                    st.rerun()
                                else:
                                    st.error(f"❌ {message}")

        with tab3:
            st.header("📊 Estadísticas")
            
            if not client.index:
                st.info("📭 No hay estadísticas disponibles")
            else:
                # Métricas generales
                total_files = len(client.index)
                total_size = sum(info['size'] for info in client.index.values())
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("📁 Total de archivos", total_files)
                
                with col2:
                    st.metric("💾 Espacio utilizado", format_file_size(total_size))
                
                with col3:
                    avg_size = total_size / total_files if total_files > 0 else 0
                    st.metric("📊 Tamaño promedio", format_file_size(avg_size))
                
                st.markdown("---")
                
                # Archivos más grandes
                st.subheader("🔝 Archivos más grandes")
                largest_files = sorted(client.index.items(), 
                                     key=lambda x: x[1]['size'], reverse=True)[:5]
                
                for i, (name, info) in enumerate(largest_files, 1):
                    st.write(f"{i}. **{name}** - {format_file_size(info['size'])}")
                
                # Actividad reciente
                st.subheader("⏰ Actividad reciente")
                recent_files = sorted(client.index.items(), 
                                    key=lambda x: x[1]['upload_date'], reverse=True)[:5]
                
                for name, info in recent_files:
                    upload_date = datetime.fromisoformat(info['upload_date'])
                    st.write(f"📄 **{name}** - {upload_date.strftime('%d/%m/%Y %H:%M')}")

if __name__ == "__main__":
    main()