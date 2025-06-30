#!/usr/bin/env python3
"""
Telegram Cloud Storage - Versión Simplificada
Sistema de almacenamiento en la nube usando Telegram con enlaces compartibles.
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
import base64
import urllib.parse

# Configuración
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="Telegram Cloud Storage",
    page_icon="☁️",
    layout="wide"
)

INDEX_FILENAME = "_telegram_cloud_index.json"

class TelegramCloudStorage:
    def __init__(self, bot_token):
        self.bot_token = bot_token
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
        self.user_hash = hashlib.md5(bot_token.encode()).hexdigest()[:16]
        
        # Directorio temporal para configuración
        self.user_dir = Path(tempfile.gettempdir()) / "telegram_cloud" / self.user_hash
        self.user_dir.mkdir(parents=True, exist_ok=True)
        self.config_file = self.user_dir / "config.json"
        
        self.config = self.load_config()
        self.index = {}
        self.index_message_id = None
        
        # Cargar índice si ya hay configuración
        if self.config.get('chat_id'):
            self.sync_index()

    def load_config(self):
        """Carga configuración del usuario"""
        try:
            if self.config_file.exists():
                with open(self.config_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Error cargando configuración: {e}")
        return {}

    def save_config(self, chat_id):
        """Guarda configuración del usuario"""
        try:
            config = {
                'bot_token': self.bot_token,
                'chat_id': chat_id,
                'user_hash': self.user_hash
            }
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2)
            self.config = config
            return True
        except Exception as e:
            logger.error(f"Error guardando configuración: {e}")
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
                            elif chat_type in ['group', 'supergroup']:
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

    def sync_index(self):
        """Sincroniza el índice desde Telegram"""
        if not self.config.get('chat_id'):
            return False
            
        try:
            # Obtener mensaje fijado
            response = requests.get(f"{self.base_url}/getChat", params={'chat_id': self.config['chat_id']})
            if response.status_code != 200:
                return False

            chat_info = response.json()
            if not chat_info.get('ok') or 'pinned_message' not in chat_info.get('result', {}):
                self.index = {}
                return True

            pinned_message = chat_info['result']['pinned_message']
            self.index_message_id = pinned_message.get('message_id')

            # Verificar si es nuestro archivo de índice
            if ('document' in pinned_message and 
                pinned_message['document']['file_name'] == INDEX_FILENAME):
                
                file_id = pinned_message['document']['file_id']
                content, _ = self.download_file_by_id(file_id)
                
                if content:
                    self.index = json.loads(content)
                    return True
            
            self.index = {}
            return True
            
        except Exception as e:
            logger.error(f"Error sincronizando índice: {e}")
            self.index = {}
            return False

    def save_index(self):
        """Guarda el índice en Telegram"""
        if not self.config.get('chat_id'):
            return False
        
        try:
            # Subir nuevo índice
            index_bytes = json.dumps(self.index, indent=2).encode('utf-8')
            files = {'document': (INDEX_FILENAME, index_bytes)}
            data = {'chat_id': self.config['chat_id'], 'disable_notification': True}
            
            response = requests.post(f"{self.base_url}/sendDocument", files=files, data=data, timeout=60)
            if response.status_code != 200:
                return False

            result = response.json()
            if not result['ok']:
                return False

            new_message_id = result['result']['message_id']

            # Desanclar anterior y fijar nuevo
            if self.index_message_id:
                requests.post(f"{self.base_url}/unpinChatMessage", 
                            data={'chat_id': self.config['chat_id'], 'message_id': self.index_message_id})

            pin_response = requests.post(f"{self.base_url}/pinChatMessage", 
                                       data={'chat_id': self.config['chat_id'], 'message_id': new_message_id, 'disable_notification': True})
            
            if pin_response.json().get('ok'):
                self.index_message_id = new_message_id
                return True
            else:
                st.error("⚠️ Error: El bot necesita ser administrador con permiso para fijar mensajes")
                return False

        except Exception as e:
            logger.error(f"Error guardando índice: {e}")
            return False

    def upload_file(self, file_bytes, filename, remote_name=None):
        """Sube archivo a Telegram"""
        if len(file_bytes) > 2 * 1024 * 1024 * 1024:  # 2GB
            return False, "Archivo demasiado grande (máximo 2GB)"
        
        if not self.config.get('chat_id'):
            return False, "Chat ID no configurado"
        
        remote_name = remote_name or filename
        file_hash = hashlib.md5(file_bytes).hexdigest()
        
        # Verificar si ya existe
        if remote_name in self.index and self.index[remote_name]['hash'] == file_hash:
            return True, f"Archivo '{remote_name}' ya existe (contenido idéntico)"
        
        try:
            files = {'document': (filename, file_bytes)}
            data = {
                'chat_id': self.config['chat_id'],
                'caption': f"☁️ {remote_name}\n🕒 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
            }
            
            response = requests.post(f"{self.base_url}/sendDocument", files=files, data=data, timeout=60)
            
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
                    
                    if self.save_index():
                        return True, f"Archivo '{remote_name}' subido exitosamente"
                    else:
                        del self.index[remote_name]
                        return False, "Error: No se pudo actualizar el índice"
                else:
                    return False, f"Error API: {result.get('description', 'Error desconocido')}"
            else:
                return False, f"Error HTTP: {response.status_code}"
                
        except Exception as e:
            return False, f"Error: {str(e)}"

    def download_file_by_id(self, file_id):
        """Descarga archivo por file_id"""
        try:
            response = requests.get(f"{self.base_url}/getFile", params={'file_id': file_id})
            if response.status_code == 200:
                result = response.json()
                if result.get('ok'):
                    file_path = result['result']['file_path']
                    file_url = f"https://api.telegram.org/file/bot{self.bot_token}/{file_path}"
                    
                    file_response = requests.get(file_url, stream=True)
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

    def download_file(self, remote_name):
        """Descarga archivo por nombre"""
        if remote_name not in self.index:
            return None, f"Archivo '{remote_name}' no encontrado"
        
        file_id = self.index[remote_name]['file_id']
        return self.download_file_by_id(file_id)

    def delete_file(self, remote_name):
        """Elimina archivo del índice"""
        if remote_name not in self.index:
            return False, f"Archivo '{remote_name}' no encontrado"
        
        try:
            del self.index[remote_name]
            if self.save_index():
                return True, f"Archivo '{remote_name}' eliminado"
            else:
                return False, "Error: No se pudo actualizar el índice"
        except Exception as e:
            return False, f"Error: {str(e)}"

    def generate_share_link(self, remote_name):
        """Genera enlace  compartible para descarga"""
        if remote_name not in self.index:
            return None, "Archivo no encontrado"
        
        try:
            # Crear datos del enlace
            share_data = {
                'bot_token': self.bot_token,
                'file_id': self.index[remote_name]['file_id'],
                'filename': remote_name,
                'size': self.index[remote_name]['size'],
                'upload_date': self.index[remote_name]['upload_date']
            }
            
            # Codificar en base64
            json_data = json.dumps(share_data)
            encoded_data = base64.b64encode(json_data.encode()).decode()
            
            # Crear URL
            base_url = st.secrets.get("APP_URL", "http://localhost:8501")  # Configurable
            share_url = f"{base_url}?share={urllib.parse.quote(encoded_data)}"
            
            return share_url, "Enlace generado exitosamente"
            
        except Exception as e:
            return None, f"Error generando enlace: {str(e)}"

def handle_shared_link():
    """Maneja la descarga desde enlace compartido"""
    if 'share' in st.query_params:
        try:
            encoded_data = st.query_params['share']
            decoded_data = base64.b64decode(urllib.parse.unquote(encoded_data)).decode()
            share_data = json.loads(decoded_data)
            
            st.title("📥 Descarga Compartida")
            st.markdown(f"**📄 Archivo:** {share_data['filename']}")
            st.markdown(f"**📊 Tamaño:** {format_size(share_data['size'])}")
            
            upload_date = datetime.fromisoformat(share_data['upload_date'])
            st.markdown(f"**📅 Subido:** {upload_date.strftime('%d/%m/%Y %H:%M')}")
            
            if st.button("📥 Descargar Archivo"):
                with st.spinner("Descargando..."):
                    # Crear cliente temporal
                    temp_client = TelegramCloudStorage(share_data['bot_token'])
                    content, message = temp_client.download_file_by_id(share_data['file_id'])
                    
                    if content:
                        st.download_button(
                            label="💾 Guardar Archivo",
                            data=content,
                            file_name=share_data['filename'],
                            mime='application/octet-stream'
                        )
                        st.success("✅ Archivo listo para descargar")
                    else:
                        st.error(f"Error: {message}")
            
            return True
            
        except Exception as e:
            st.error(f"Error procesando enlace: {str(e)}")
            return True
    
    return False

def format_size(bytes_size):
    """Formatea tamaño de archivo"""
    if not isinstance(bytes_size, (int, float)): 
        return "0 B"
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
    # Verificar si es un enlace compartido
    if handle_shared_link():
        return
    
    st.title("☁️ Telegram Cloud Storage")
    st.markdown("*Sistema de almacenamiento en la nube con enlaces compartibles*")
    
    # Instrucciones simplificadas
    with st.expander("📋 Instrucciones"):
        st.markdown("""
        1. **Crear Bot**: Busca @BotFather en Telegram → /newbot → Copia el token
        2. **Configurar Bot**: Hazlo administrador con permiso para "Fijar Mensajes"
        3. **Usar App**: Pega el token → Envía "Hola" al bot → Selecciona el chat
        4. **¡Listo!** Ya puedes subir archivos y generar enlaces compartibles
        """)
    
    # Inicializar cliente
    if 'client' not in st.session_state:
        st.session_state.client = None
    
    # Configuración en sidebar
    with st.sidebar:
        st.header("⚙️ Configuración")
        
        bot_token = st.text_input("🔑 Token del Bot:", type="password")
        
        if bot_token:
            if not st.session_state.client or st.session_state.client.bot_token != bot_token:
                st.session_state.client = TelegramCloudStorage(bot_token)
            
            client = st.session_state.client
            is_valid, bot_info = client.test_bot_token()
            
            if is_valid:
                st.success(f"✅ Bot: {bot_info.get('first_name', 'Bot')}")
                
                if not client.config.get('chat_id'):
                    with st.spinner("Buscando chats..."):
                        chats = client.get_chat_ids()
                        if chats:
                            chat_options = {name: id for id, name in chats}
                            selected_chat = st.selectbox("Selecciona Chat:", chat_options.keys())
                            if st.button("💾 Guardar"):
                                if client.save_config(chat_options[selected_chat]):
                                    st.success("✅ Configurado")
                                    st.rerun()
                        else:
                            st.error("❌ Envía 'Hola' a tu bot primero")
                else:
                    st.success("✅ Configurado")
                    if st.button("🔄 Reconfigurar"):
                        client.config_file.unlink(missing_ok=True)
                        st.session_state.client = None
                        st.rerun()
            else:
                st.error("❌ Token inválido")
        else:
            st.info("👆 Ingresa tu token")
    
    # Verificar configuración
    if not st.session_state.get('client') or not st.session_state.client.config.get('chat_id'):
        st.warning("⚠️ Completa la configuración para continuar")
        return
    
    client = st.session_state.client
    
    # Tabs principales
    tab1, tab2, tab3 = st.tabs(["📤 Subir", "📁 Archivos", "📊 Stats"])
    
    with tab1:
        st.header("📤 Subir Archivos")
        
        # Subir archivos individuales
        uploaded_files = st.file_uploader("Selecciona archivos:", accept_multiple_files=True)
        
        if uploaded_files:
            for uploaded_file in uploaded_files:
                col1, col2, col3 = st.columns([2, 2, 1])
                
                with col1:
                    st.write(f"📄 {uploaded_file.name} ({format_size(uploaded_file.size)})")
                
                with col2:
                    custom_name = st.text_input("Nombre:", value=uploaded_file.name, 
                                              key=f"name_{uploaded_file.name}")
                
                with col3:
                    if st.button("📤", key=f"upload_{uploaded_file.name}"):
                        with st.spinner("Subiendo..."):
                            file_bytes = uploaded_file.read()
                            success, message = client.upload_file(file_bytes, uploaded_file.name, custom_name)
                        
                        if success:
                            st.success(message)
                            st.rerun()
                        else:
                            st.error(message)
        
        # Subir carpeta como ZIP
        st.markdown("---")
        st.subheader("📂 Subir Carpeta")
        
        folder_path = st.text_input("Ruta de carpeta:", placeholder="C:/ruta/a/carpeta")
        
        if folder_path and os.path.isdir(folder_path):
            folder_name = os.path.basename(folder_path)
            zip_name = f"{folder_name}.zip"
            
            col1, col2 = st.columns([3, 1])
            with col1:
                custom_zip_name = st.text_input("Nombre ZIP:", value=zip_name)
            with col2:
                st.write("")  # Espaciador
                if st.button("📤 Subir"):
                    with st.spinner("Comprimiendo..."):
                        try:
                            zip_buffer = zip_folder(folder_path)
                            zip_bytes = zip_buffer.getvalue()
                            success, message = client.upload_file(zip_bytes, zip_name, custom_zip_name)
                            
                            if success:
                                st.success(message)
                                st.rerun()
                            else:
                                st.error(message)
                        except Exception as e:
                            st.error(f"Error: {str(e)}")

    with tab2:
        col1, col2 = st.columns([3, 1])
        with col1:
            st.header("📁 Mis Archivos")
        with col2:
            if st.button("🔄 Sincronizar"):
                client.sync_index()
                st.rerun()
        
        if not client.index:
            st.info("📭 No hay archivos")
        else:
            # Búsqueda y ordenamiento
            col1, col2 = st.columns(2)
            with col1:
                search = st.text_input("🔍 Buscar:")
            with col2:
                sort_by = st.selectbox("📊 Ordenar:", 
                                     ["Fecha ↓", "Fecha ↑", "Tamaño ↓", "Tamaño ↑", "Nombre A-Z"])
            
            # Filtrar archivos
            filtered = {name: info for name, info in client.index.items() 
                       if not search or search.lower() in name.lower()}
            
            # Ordenar archivos
            sort_funcs = {
                "Fecha ↓": lambda x: x[1]['upload_date'],
                "Fecha ↑": lambda x: x[1]['upload_date'],
                "Tamaño ↓": lambda x: x[1]['size'],
                "Tamaño ↑": lambda x: x[1]['size'],
                "Nombre A-Z": lambda x: x[0]
            }
            
            reverse = "↓" in sort_by
            sorted_files = sorted(filtered.items(), key=sort_funcs[sort_by], reverse=reverse)
            
            st.info(f"📋 {len(sorted_files)} de {len(client.index)} archivos")
            
            # Mostrar archivos
            for name, info in sorted_files:
                with st.expander(f"📄 {name} ({format_size(info['size'])})"):
                    col1, col2, col3, col4 = st.columns(4)
                    
                    with col1:
                        upload_date = datetime.fromisoformat(info['upload_date'])
                        st.write(f"📅 {upload_date.strftime('%d/%m/%Y')}")
                    
                    with col2:
                        if st.button("📥 Descargar", key=f"dl_{name}"):
                            with st.spinner("Descargando..."):
                                content, message = client.download_file(name)
                                if content:
                                    st.download_button(
                                        "💾 Guardar",
                                        data=content,
                                        file_name=name,
                                        key=f"save_{name}"
                                    )
                                else:
                                    st.error(message)
                    
                    with col3:
                        if st.button("🔗 Compartir", key=f"share_{name}"):
                            share_url, message = client.generate_share_link(name)
                            if share_url:
                                st.code(share_url, language=None)
                                st.success("✅ Enlace generado")
                            else:
                                st.error(message)
                    
                    with col4:
                        if st.button("🗑️ Eliminar", key=f"del_{name}"):
                            success, message = client.delete_file(name)
                            if success:
                                st.success(message)
                                st.rerun()
                            else:
                                st.error(message)

    with tab3:
        st.header("📊 Estadísticas")
        
        if not client.index:
            st.info("📭 No hay datos")
        else:
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
            
            # Top 5 más grandes
            st.subheader("🔝 Archivos más grandes")
            largest = sorted(client.index.items(), key=lambda x: x[1]['size'], reverse=True)[:5]
            for i, (name, info) in enumerate(largest, 1):
                st.write(f"{i}. **{name}** - {format_size(info['size'])}")
            
            # 5 más recientes
            st.subheader("⏰ Archivos recientes")
            recent = sorted(client.index.items(), key=lambda x: x[1]['upload_date'], reverse=True)[:5]
            for name, info in recent:
                date = datetime.fromisoformat(info['upload_date'])
                st.write(f"📄 **{name}** - {date.strftime('%d/%m/%Y %H:%M')}")

if __name__ == "__main__":
    main()