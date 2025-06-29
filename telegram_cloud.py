#!/usr/bin/env python3
"""
Telegram Cloud Storage - Multiusuario
Sistema de almacenamiento en la nube usando Telegram con soporte multiusuario
"""

import os
import json
import hashlib
import streamlit as st
import requests
from datetime import datetime
from pathlib import Path
import tempfile
import zipfile
import io
import logging
import uuid

# Configuración
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="Telegram Cloud Storage",
    page_icon="☁️",
    layout="wide"
)

class TelegramCloudStorage:
    def __init__(self, bot_token):
        self.bot_token = bot_token
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
        self.user_hash = hashlib.md5(bot_token.encode()).hexdigest()[:16]
        
        # Directorio único por usuario
        self.user_dir = Path(tempfile.gettempdir()) / "telegram_cloud" / self.user_hash
        self.user_dir.mkdir(parents=True, exist_ok=True)
        
        self.config_file = self.user_dir / "config.json"
        self.index_file = self.user_dir / "index.json"
        
        self.config = self.load_config()
        self.index = self.load_index()
    
    def load_config(self):
        """Carga configuración del usuario"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                logger.info(f"Configuración cargada para usuario {self.user_hash}")
                return config
        except Exception as e:
            logger.error(f"Error cargando configuración: {e}")
        return {}
    
    def save_config(self, chat_id):
        """Guarda configuración del usuario"""
        try:
            config = {
                'bot_token': self.bot_token,
                'chat_id': chat_id,
                'user_hash': self.user_hash,
                'created_date': datetime.now().isoformat()
            }
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2)
            self.config = config
            logger.info(f"Configuración guardada para usuario {self.user_hash}")
            return True
        except Exception as e:
            logger.error(f"Error guardando configuración: {e}")
            return False
    
    def load_index(self):
        """Carga índice de archivos"""
        try:
            if self.index_file.exists():
                with open(self.index_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Error cargando índice: {e}")
        return {}
    
    def save_index(self):
        """Guarda índice de archivos"""
        try:
            with open(self.index_file, 'w') as f:
                json.dump(self.index, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Error guardando índice: {e}")
            return False
    
    def test_bot_token(self):
        """Verifica si el token es válido"""
        try:
            response = requests.get(f"{self.base_url}/getMe", timeout=10)
            if response.status_code == 200:
                result = response.json()
                return result.get('ok', False), result.get('result', {})
            return False, {}
        except Exception as e:
            logger.error(f"Error verificando token: {e}")
            return False, {}
    
    def get_chat_ids(self):
        """Obtiene Chat IDs disponibles"""
        try:
            response = requests.get(f"{self.base_url}/getUpdates", timeout=10)
            if response.status_code == 200:
                data = response.json()
                if data['ok'] and data['result']:
                    chats = {}
                    for update in data['result']:
                        if 'message' in update:
                            chat = update['message']['chat']
                            chat_id = chat['id']
                            chat_type = chat['type']
                            
                            if chat_type == 'private':
                                name = chat.get('first_name', 'Usuario')
                                username = chat.get('username', '')
                                display = f"👤 {name}" + (f" (@{username})" if username else "")
                            elif chat_type == 'group':
                                display = f"👥 {chat.get('title', 'Grupo')}"
                            elif chat_type == 'channel':
                                display = f"📢 {chat.get('title', 'Canal')}"
                            else:
                                continue
                            
                            chats[chat_id] = display
                    
                    return list(chats.items())
            return []
        except Exception as e:
            logger.error(f"Error obteniendo chats: {e}")
            return []
    
    def file_exists(self, remote_name):
        """Verifica si existe un archivo con el mismo nombre"""
        return remote_name in self.index
    
    def upload_file(self, file_bytes, filename, remote_name=None):
        """Sube archivo a Telegram"""
        if len(file_bytes) > 2 * 1024 * 1024 * 1024:  # 2GB
            return False, "Archivo demasiado grande (máximo 2GB)"
        
        if not self.config.get('chat_id'):
            return False, "Chat ID no configurado"
        
        remote_name = remote_name or filename
        file_hash = hashlib.md5(file_bytes).hexdigest()
        
        # Verificar duplicado
        if remote_name in self.index and self.index[remote_name]['hash'] == file_hash:
            return True, f"Archivo '{remote_name}' ya existe (contenido idéntico)"
        
        try:
            files = {'document': (filename, file_bytes)}
            data = {
                'chat_id': self.config['chat_id'],
                'caption': f"☁️ {remote_name}\n🕒 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            }
            
            response = requests.post(f"{self.base_url}/sendDocument", 
                                   files=files, data=data, timeout=60)
            
            if response.status_code == 200:
                result = response.json()
                if result['ok']:
                    file_id = result['result']['document']['file_id']
                    
                    self.index[remote_name] = {
                        'file_id': file_id,
                        'hash': file_hash,
                        'size': len(file_bytes),
                        'upload_date': datetime.now().isoformat(),
                        'original_filename': filename
                    }
                    self.save_index()
                    
                    return True, f"Archivo '{remote_name}' subido exitosamente"
                else:
                    return False, f"Error API: {result.get('description', 'Error desconocido')}"
            else:
                return False, f"Error HTTP: {response.status_code}"
                
        except Exception as e:
            return False, f"Error: {str(e)}"
    
    def download_file(self, remote_name):
        """Descarga archivo de Telegram"""
        if remote_name not in self.index:
            return None, f"Archivo '{remote_name}' no encontrado"
        
        file_id = self.index[remote_name]['file_id']
        
        try:
            # Obtener info del archivo
            response = requests.get(f"{self.base_url}/getFile?file_id={file_id}")
            if response.status_code == 200:
                result = response.json()
                if result['ok']:
                    file_path = result['result']['file_path']
                    file_url = f"https://api.telegram.org/file/bot{self.bot_token}/{file_path}"
                    
                    # Descargar archivo
                    file_response = requests.get(file_url)
                    if file_response.status_code == 200:
                        return file_response.content, "Descarga exitosa"
                    else:
                        return None, f"Error descarga: {file_response.status_code}"
                else:
                    return None, f"Error API: {result.get('description')}"
            else:
                return None, f"Error HTTP: {response.status_code}"
                
        except Exception as e:
            return None, f"Error: {str(e)}"
    
    def delete_file(self, remote_name):
        """Elimina archivo del índice"""
        if remote_name not in self.index:
            return False, f"Archivo '{remote_name}' no encontrado"
        
        try:
            del self.index[remote_name]
            self.save_index()
            return True, f"Archivo '{remote_name}' eliminado"
        except Exception as e:
            return False, f"Error: {str(e)}"

def format_size(bytes_size):
    """Formatea tamaño de archivo"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_size < 1024:
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024
    return f"{bytes_size:.1f} TB"

def zip_folder(folder_path):
    """Comprime carpeta en ZIP"""
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, folder_path)
                zipf.write(file_path, arcname)
    zip_buffer.seek(0)
    return zip_buffer

def main():
    st.title("☁️ Telegram Cloud Storage")
    st.markdown("*Sistema multiusuario de almacenamiento en la nube*")
    
    # Inicialización de session state
    if 'client' not in st.session_state:
        st.session_state.client = None
    
    # Sidebar - Configuración
    with st.sidebar:
        st.header("⚙️ Configuración")
        
        # Input del token
        bot_token = st.text_input(
            "🔑 Token del Bot:",
            type="password",
            help="Obtén tu token de @BotFather en Telegram"
        )
        
        if bot_token:
            # Crear cliente
            if not st.session_state.client or st.session_state.client.bot_token != bot_token:
                st.session_state.client = TelegramCloudStorage(bot_token)
            
            client = st.session_state.client
            
            # Verificar token
            is_valid, bot_info = client.test_bot_token()
            
            if is_valid:
                st.success(f"✅ Bot: {bot_info.get('first_name', 'Bot')}")
                
                # Mostrar usuario actual
                if client.config:
                    st.info(f"👤 Usuario: {client.user_hash}")
                
                # Configurar Chat ID si no está configurado
                if not client.config.get('chat_id'):
                    st.warning("⚠️ Configura tu Chat ID")
                    
                    # Opciones para obtener Chat ID
                    option = st.radio(
                        "Obtener Chat ID:",
                        ["🔍 Automático", "✏️ Manual"],
                        horizontal=True
                    )
                    
                    if option == "🔍 Automático":
                        st.markdown("1. Envía un mensaje a tu bot\n2. Presiona el botón")
                        
                        if st.button("🔍 Buscar Chat ID"):
                            chats = client.get_chat_ids()
                            if chats:
                                st.session_state.available_chats = chats
                            else:
                                st.error("❌ No se encontraron chats. Envía un mensaje al bot primero.")
                        
                        if 'available_chats' in st.session_state:
                            chat_options = {display: chat_id for chat_id, display in st.session_state.available_chats}
                            selected_display = st.selectbox("Selecciona tu chat:", list(chat_options.keys()))
                            
                            if st.button("💾 Guardar Chat ID"):
                                selected_chat_id = chat_options[selected_display]
                                if client.save_config(selected_chat_id):
                                    st.success("✅ Configuración guardada")
                                    del st.session_state.available_chats
                                    st.rerun()
                                else:
                                    st.error("❌ Error al guardar")
                    
                    else:  # Manual
                        chat_id_input = st.text_input("📱 Chat ID:", placeholder="Ej: 123456789")
                        if chat_id_input:
                            try:
                                chat_id = int(chat_id_input)
                                if st.button("💾 Guardar Chat ID"):
                                    if client.save_config(chat_id):
                                        st.success("✅ Configuración guardada")
                                        st.rerun()
                                    else:
                                        st.error("❌ Error al guardar")
                            except ValueError:
                                st.error("❌ Debe ser un número")
                
                else:
                    st.success(f"✅ Chat configurado: {client.config['chat_id']}")
                    
                    # Botón para reconfigurar
                    if st.button("🔄 Reconfigurar Chat"):
                        client.config = {}
                        client.save_config(None)
                        st.rerun()
            
            else:
                st.error("❌ Token inválido")
        
        else:
            st.info("👆 Ingresa tu token para comenzar")
    
    # Contenido principal
    if not bot_token:
        st.info("🚀 **Comenzar:**\n1. Crea un bot con @BotFather en Telegram\n2. Ingresa el token en el panel lateral\n3. Configura tu Chat ID\n4. ¡Comienza a subir archivos!")
        return
    
    if not st.session_state.client or not st.session_state.client.config.get('chat_id'):
        st.warning("⚠️ Completa la configuración en el panel lateral")
        return
    
    client = st.session_state.client
    
    # Tabs principales
    tab1, tab2, tab3 = st.tabs(["📤 Subir", "📁 Archivos", "📊 Estadísticas"])
    
    with tab1:
        st.header("📤 Subir Archivos")
        
        # Subir archivos individuales
        uploaded_files = st.file_uploader(
            "Selecciona archivos:",
            accept_multiple_files=True,
            help="Máximo 2GB por archivo"
        )
        
        if uploaded_files:
            for idx, uploaded_file in enumerate(uploaded_files):
                # Generar un ID único para cada archivo
                unique_id = str(uuid.uuid4())[:8]
                
                col1, col2, col3 = st.columns([2, 2, 1])
                
                with col1:
                    st.write(f"📄 **{uploaded_file.name}**")
                    st.write(f"📊 {format_size(uploaded_file.size)}")
                    
                    # Verificar si ya existe
                    if client.file_exists(uploaded_file.name):
                        st.warning(f"⚠️ Ya existe un archivo con el nombre '{uploaded_file.name}'")
                
                with col2:
                    custom_name = st.text_input(
                        "Nombre personalizado:",
                        value=uploaded_file.name,
                        key=f"name_{idx}_{unique_id}"
                    )
                    
                    # Mostrar si el nombre personalizado ya existe
                    if custom_name != uploaded_file.name and client.file_exists(custom_name):
                        st.warning(f"⚠️ Ya existe un archivo con el nombre '{custom_name}'")
                
                with col3:
                    if st.button("📤", key=f"upload_{idx}_{unique_id}"):
                        # Confirmar sobrescritura si es necesario
                        if client.file_exists(custom_name):
                            # Usar session state para la confirmación
                            confirm_key = f"confirm_{idx}_{unique_id}"
                            
                            if confirm_key not in st.session_state:
                                st.session_state[confirm_key] = False
                            
                            if not st.session_state[confirm_key]:
                                st.warning("⚠️ El archivo ya existe. ¿Sobrescribir?")
                                col_yes, col_no = st.columns(2)
                                with col_yes:
                                    if st.button("✅ Sí", key=f"yes_{idx}_{unique_id}"):
                                        st.session_state[confirm_key] = True
                                        st.rerun()
                                with col_no:
                                    if st.button("❌ No", key=f"no_{idx}_{unique_id}"):
                                        st.info("❌ Subida cancelada")
                            else:
                                # Proceder con la subida
                                with st.spinner("Subiendo..."):
                                    file_bytes = uploaded_file.read()
                                    success, message = client.upload_file(file_bytes, uploaded_file.name, custom_name)
                                
                                if success:
                                    st.success(message)
                                    # Limpiar confirmación
                                    del st.session_state[confirm_key]
                                else:
                                    st.error(message)
                        else:
                            # Subir directamente
                            with st.spinner("Subiendo..."):
                                file_bytes = uploaded_file.read()
                                success, message = client.upload_file(file_bytes, uploaded_file.name, custom_name)
                            
                            if success:
                                st.success(message)
                            else:
                                st.error(message)
        
        # Subir carpeta
        st.markdown("---")
        st.subheader("📂 Subir Carpeta (como ZIP)")
        
        folder_path = st.text_input("Ruta de la carpeta:", placeholder="C:/ruta/a/carpeta")
        
        if folder_path and os.path.isdir(folder_path):
            folder_name = os.path.basename(folder_path)
            zip_name = f"{folder_name}.zip"
            
            col1, col2 = st.columns([3, 1])
            with col1:
                custom_zip_name = st.text_input("Nombre del ZIP:", value=zip_name)
                
                # Mostrar advertencia si existe
                if client.file_exists(custom_zip_name):
                    st.warning(f"⚠️ Ya existe un archivo con el nombre '{custom_zip_name}'")
                    
            with col2:
                if st.button("📤 Subir Carpeta"):
                    # Confirmar sobrescritura si es necesario
                    if client.file_exists(custom_zip_name):
                        if st.button("⚠️ Confirmar sobrescritura"):
                            with st.spinner("Comprimiendo y subiendo..."):
                                try:
                                    zip_buffer = zip_folder(folder_path)
                                    zip_bytes = zip_buffer.getvalue()
                                    success, message = client.upload_file(zip_bytes, zip_name, custom_zip_name)
                                    
                                    if success:
                                        st.success(message)
                                    else:
                                        st.error(message)
                                except Exception as e:
                                    st.error(f"Error: {str(e)}")
                    else:
                        with st.spinner("Comprimiendo y subiendo..."):
                            try:
                                zip_buffer = zip_folder(folder_path)
                                zip_bytes = zip_buffer.getvalue()
                                success, message = client.upload_file(zip_bytes, zip_name, custom_zip_name)
                                
                                if success:
                                    st.success(message)
                                else:
                                    st.error(message)
                            except Exception as e:
                                st.error(f"Error: {str(e)}")
    
    with tab2:
        st.header("📁 Mis Archivos")
        
        if not client.index:
            st.info("📭 No tienes archivos almacenados")
        else:
            # Búsqueda y filtros
            col1, col2 = st.columns([2, 1])
            with col1:
                search = st.text_input("🔍 Buscar:", key="search")
            with col2:
                sort_by = st.selectbox("📊 Ordenar:", 
                    ["Fecha ↓", "Fecha ↑", "Tamaño ↓", "Tamaño ↑", "Nombre A-Z", "Nombre Z-A"])
            
            # Filtrar archivos
            filtered = {}
            for name, info in client.index.items():
                if not search or search.lower() in name.lower():
                    filtered[name] = info
            
            # Ordenar
            if sort_by == "Fecha ↓":
                sorted_files = sorted(filtered.items(), key=lambda x: x[1]['upload_date'], reverse=True)
            elif sort_by == "Fecha ↑":
                sorted_files = sorted(filtered.items(), key=lambda x: x[1]['upload_date'])
            elif sort_by == "Tamaño ↓":
                sorted_files = sorted(filtered.items(), key=lambda x: x[1]['size'], reverse=True)
            elif sort_by == "Tamaño ↑":
                sorted_files = sorted(filtered.items(), key=lambda x: x[1]['size'])
            elif sort_by == "Nombre A-Z":
                sorted_files = sorted(filtered.items())
            else:  # Z-A
                sorted_files = sorted(filtered.items(), reverse=True)
            
            st.info(f"📋 {len(sorted_files)} de {len(client.index)} archivos")
            
            # Mostrar archivos
            for name, info in sorted_files:
                # Generar ID único para cada archivo en la lista
                file_unique_id = hashlib.md5(name.encode()).hexdigest()[:8]
                
                with st.expander(f"📄 {name} ({format_size(info['size'])})"):
                    col1, col2, col3 = st.columns([2, 1, 1])
                    
                    with col1:
                        upload_date = datetime.fromisoformat(info['upload_date'])
                        st.write(f"📅 {upload_date.strftime('%d/%m/%Y %H:%M')}")
                        st.write(f"📊 {format_size(info['size'])}")
                        st.write(f"🔒 {info['hash'][:16]}...")
                    
                    with col2:
                        if st.button("📥", key=f"download_{file_unique_id}"):
                            with st.spinner("Descargando..."):
                                content, message = client.download_file(name)
                            
                            if content:
                                st.download_button(
                                    label="💾 Guardar",
                                    data=content,
                                    file_name=name,
                                    key=f"save_{file_unique_id}"
                                )
                                st.success(message)
                            else:
                                st.error(message)
                    
                    with col3:
                        if st.button("🗑️", key=f"delete_{file_unique_id}"):
                            success, message = client.delete_file(name)
                            if success:
                                st.success(message)
                                st.rerun()
                            else:
                                st.error(message)
    
    with tab3:
        st.header("📊 Estadísticas")
        
        if not client.index:
            st.info("📭 No hay datos disponibles")
        else:
            # Métricas
            total_files = len(client.index)
            total_size = sum(info['size'] for info in client.index.values())
            avg_size = total_size / total_files if total_files > 0 else 0
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("📁 Archivos", total_files)
            with col2:
                st.metric("💾 Espacio", format_size(total_size))
            with col3:
                st.metric("📊 Promedio", format_size(avg_size))
            
            # Top archivos
            st.subheader("🔝 Archivos más grandes")
            largest = sorted(client.index.items(), key=lambda x: x[1]['size'], reverse=True)[:5]
            for i, (name, info) in enumerate(largest, 1):
                st.write(f"{i}. **{name}** - {format_size(info['size'])}")
            
            # Actividad reciente
            st.subheader("⏰ Actividad reciente")
            recent = sorted(client.index.items(), key=lambda x: x[1]['upload_date'], reverse=True)[:5]
            for name, info in recent:
                date = datetime.fromisoformat(info['upload_date'])
                st.write(f"📄 **{name}** - {date.strftime('%d/%m/%Y %H:%M')}")

if __name__ == "__main__":
    main()