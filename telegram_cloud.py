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

# Configuración de la página
st.set_page_config(
    page_title="Telegram Cloud Storage",
    page_icon="☁️",
    layout="wide",
    initial_sidebar_state="expanded"
)

class TelegramCloudStorage:
    def __init__(self, bot_token, chat_id, data_directory=None):
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
        
        if data_directory:
            self.data_dir = Path(data_directory)
        else:
            self.data_dir = get_default_data_directory()
        
        self.data_dir.mkdir(exist_ok=True, parents=True)
        self.index_file = self.data_dir / "telegram_cloud_index.json"
        self.load_index()
    
    def load_index(self):
        """Carga el índice de archivos almacenados"""
        try:
            with open(self.index_file, 'r') as f:
                self.index = json.load(f)
        except FileNotFoundError:
            self.index = {}
    
    def save_index(self):
        """Guarda el índice de archivos"""
        with open(self.index_file, 'w') as f:
            json.dump(self.index, f, indent=2)
    
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
                    
                    return True, f"Archivo subido exitosamente: {remote_name}"
                else:
                    return False, f"Error de API: {result.get('description', 'Error desconocido')}"
            else:
                return False, f"Error HTTP: {response.status_code}"
                
        except Exception as e:
            return False, f"Error al subir archivo: {str(e)}"
    
    def download_file(self, remote_name):
        """Descarga un archivo de Telegram"""
        if remote_name not in self.index:
            return None, f"Archivo '{remote_name}' no encontrado"
        
        file_info = self.index[remote_name]
        file_id = file_info['file_id']
        
        try:
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
                        return file_response.content, f"Archivo descargado exitosamente"
                    else:
                        return None, f"Error al descargar: {file_response.status_code}"
                else:
                    return None, f"Error de API: {result.get('description', 'Error desconocido')}"
            else:
                return None, f"Error HTTP: {response.status_code}"
                
        except Exception as e:
            return None, f"Error al descargar archivo: {str(e)}"
    
    def delete_file(self, remote_name):
        """Elimina un archivo del índice"""
        if remote_name not in self.index:
            return False, f"Archivo '{remote_name}' no encontrado"
        
        del self.index[remote_name]
        self.save_index()
        return True, f"Archivo '{remote_name}' eliminado del índice"

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

def get_default_data_directory():
    """Obtiene el directorio de datos por defecto (seguro, local)"""
    # Directorio por defecto en la carpeta del usuario
    if os.name == 'nt':  # Windows
        base_dir = Path.home() / "Documents" / "TelegramCloudStorage"
    else:  # Linux/macOS
        base_dir = Path.home() / ".telegram_cloud_storage"
    
    return base_dir

def get_config_file():
    """Obtiene la ubicación del archivo de configuración"""
    config_dir = get_default_data_directory()
    config_dir.mkdir(exist_ok=True, parents=True)
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
    
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2)

def load_config():
    """Carga la configuración guardada"""
    config_file = get_config_file()
    try:
        with open(config_file, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return None

def get_data_directory():
    """Obtiene el directorio de datos actual (configurado o por defecto)"""
    config = load_config()
    if config and config.get('data_directory'):
        data_dir = Path(config['data_directory'])
    else:
        data_dir = get_default_data_directory()
    
    data_dir.mkdir(exist_ok=True, parents=True)
    return data_dir

def is_safe_directory(path):
    """Verifica si un directorio es seguro (no está en ubicaciones de nube)"""
    path_str = str(path).lower()
    unsafe_patterns = [
        'dropbox', 'onedrive', 'googledrive', 'google drive', 'icloud',
        'box', 'mega', 'sync', 'cloud', 'backup'
    ]
    
    return not any(pattern in path_str for pattern in unsafe_patterns)

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
        
        # Botón para cambiar directorio
        if st.button("📁 Cambiar ubicación"):
            st.session_state.show_directory_config = True
        
        # Configuración de directorio
        if st.session_state.get('show_directory_config', False):
            st.markdown("---")
            st.subheader("🔧 Configurar Directorio")
            
            # Opciones predefinidas
            default_dir = get_default_data_directory()
            
            option = st.radio(
                "Selecciona una opción:",
                [
                    f"🏠 Usar directorio por defecto",
                    "📁 Especificar directorio personalizado"
                ]
            )
            
            if option.startswith("🏠"):
                new_dir = default_dir
                st.success(f"✅ Directorio por defecto: `{new_dir}`")
            else:
                custom_path = st.text_input(
                    "📂 Ruta personalizada:",
                    help="Ingresa la ruta completa donde quieres guardar los datos"
                )
                
                if custom_path:
                    new_dir = Path(custom_path)
                    
                    # Verificar que sea un directorio seguro
                    if not is_safe_directory(new_dir):
                        st.warning("⚠️ **Advertencia de Seguridad**: No se recomienda usar carpetas de servicios en la nube (Dropbox, OneDrive, etc.) para almacenar credenciales y datos sensibles.")
                        
                        if st.checkbox("Entiendo los riesgos y quiero continuar"):
                            pass
                        else:
                            new_dir = None
                    
                    if new_dir:
                        try:
                            new_dir.mkdir(exist_ok=True, parents=True)
                            st.success(f"✅ Directorio válido: `{new_dir}`")
                        except Exception as e:
                            st.error(f"❌ Error al crear directorio: {e}")
                            new_dir = None
                else:
                    new_dir = None
            
            # Botones de acción
            col1, col2 = st.columns(2)
            with col1:
                if st.button("💾 Aplicar", disabled=not new_dir):
                    if config:
                        save_config(config['bot_token'], config['chat_id'], new_dir)
                        st.success("✅ Directorio actualizado")
                    else:
                        st.session_state.custom_data_dir = str(new_dir)
                    st.session_state.show_directory_config = False
                    st.rerun()
            
            with col2:
                if st.button("❌ Cancelar"):
                    st.session_state.show_directory_config = False
                    st.rerun()
        
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
                                # Usar directorio personalizado si se configuró
                                data_dir = st.session_state.get('custom_data_dir', None)
                                save_config(st.session_state.bot_token, selected_chat['id'], data_dir)
                                st.success("✅ Configuración guardada exitosamente")
                                st.balloons()
                                # Limpiar session state
                                for key in ['bot_token', 'available_chats', 'custom_data_dir']:
                                    if key in st.session_state:
                                        del st.session_state[key]
                                time.sleep(1)
                                st.rerun()
                
                else:  # Ingresar manualmente
                    chat_id = st.text_input("📱 Chat ID:", help="Ingresa tu Chat ID (número)")
                    
                    if chat_id:
                        try:
                            chat_id = int(chat_id)
                            if st.button("💾 Guardar configuración"):
                                data_dir = st.session_state.get('custom_data_dir', None)
                                save_config(st.session_state.bot_token, chat_id, data_dir)
                                st.success("✅ Configuración guardada exitosamente")
                                st.balloons()
                                # Limpiar session state
                                for key in ['bot_token', 'custom_data_dir']:
                                    if key in st.session_state:
                                        del st.session_state[key]
                                time.sleep(1)
                                st.rerun()
                        except ValueError:
                            st.error("❌ El Chat ID debe ser un número")
    
    else:
        # Interfaz principal
        bot_token = config['bot_token']
        chat_id = config['chat_id']
        
        # Inicializar cliente con directorio configurado
        data_dir = get_data_directory()
        client = TelegramCloudStorage(bot_token, chat_id, data_dir)
        
        # Tabs principales
        tab1, tab2, tab3 = st.tabs(["📤 Subir Archivos", "📁 Mis Archivos", "📊 Estadísticas"])
        
        with tab1:
            st.header("📤 Subir Archivos")
            
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
        
        with tab2:
            st.header("📁 Mis Archivos")
            
            if not client.index:
                st.info("📭 No tienes archivos almacenados")
            else:
                # Filtros
                col1, col2 = st.columns([2, 1])
                with col1:
                    search_term = st.text_input("🔍 Buscar archivos:", "")
                with col2:
                    sort_by = st.selectbox("📊 Ordenar por:", 
                                          ["Fecha (más reciente)", "Fecha (más antiguo)", 
                                           "Tamaño (mayor)", "Tamaño (menor)", "Nombre A-Z", "Nombre Z-A"])
                
                # Filtrar archivos
                filtered_files = {}
                for name, info in client.index.items():
                    if search_term.lower() in name.lower():
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
                    with st.expander(f"📄 {name} ({format_file_size(info['size'])})"):
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