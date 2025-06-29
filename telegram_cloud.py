#!/usr/bin/env python3
"""
Telegram Cloud Storage - Multiusuario (Versión Sincronizada)
Sistema de almacenamiento en la nube usando Telegram con sincronización de metadatos.
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

# Configuración
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="Telegram Cloud Storage",
    page_icon="☁️",
    layout="wide"
)

# NUEVO: Constante para el nombre del archivo de índice
INDEX_FILENAME = "_telegram_cloud_storage_index.v1.json"

class TelegramCloudStorage:
    def __init__(self, bot_token):
        self.bot_token = bot_token
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
        self.user_hash = hashlib.md5(bot_token.encode()).hexdigest()[:16]

        # MODIFICADO: El directorio local ahora solo sirve para configuraciones temporales
        self.user_dir = Path(tempfile.gettempdir()) / "telegram_cloud" / self.user_hash
        self.user_dir.mkdir(parents=True, exist_ok=True)
        self.config_file = self.user_dir / "config.json"

        self.config = self.load_config()
        
        # MODIFICADO: El índice ya no se carga desde un archivo local al inicio
        self.index = {}
        self.index_message_id = None # NUEVO: Para saber qué mensaje de índice desanclar

        # Si ya hay config, cargamos el índice desde Telegram
        if self.config.get('chat_id'):
            self.load_index_from_telegram()

    def load_config(self):
        """Carga configuración del usuario (solo chat_id)"""
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
        """Guarda configuración del usuario (solo chat_id)"""
        try:
            config = {
                'bot_token': self.bot_token,
                'chat_id': chat_id,
                'user_hash': self.user_hash
            }
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=2)
            self.config = config
            logger.info(f"Configuración guardada para usuario {self.user_hash}")
            return True
        except Exception as e:
            logger.error(f"Error guardando configuración: {e}")
            return False

    # MODIFICADO: La función save_index ahora orquesta el guardado en Telegram
    def save_index(self):
        """Orquesta el guardado del índice en Telegram."""
        return self.save_index_to_telegram()

    # NUEVO: Lógica para cargar el índice desde un mensaje fijado en Telegram
    def load_index_from_telegram(self):
        """Carga el índice de archivos desde el mensaje fijado en Telegram."""
        if not self.config.get('chat_id'):
            return

        st.info("🔄 Sincronizando índice de archivos...")
        logger.info("Intentando cargar el índice desde Telegram...")
        try:
            # 1. Obtener información del chat para encontrar el mensaje fijado
            response = requests.get(f"{self.base_url}/getChat", params={'chat_id': self.config['chat_id']})
            if response.status_code != 200:
                logger.error(f"Error obteniendo info del chat: {response.text}")
                st.error("Error al sincronizar: No se pudo obtener información del chat.")
                return

            chat_info = response.json()
            if not chat_info.get('ok') or 'result' not in chat_info or 'pinned_message' not in chat_info['result']:
                logger.warning("No se encontró un mensaje fijado. Se asume un índice vacío.")
                st.warning("No se encontró un índice remoto. Si es la primera vez, es normal.")
                self.index = {}
                return

            pinned_message = chat_info['result']['pinned_message']
            self.index_message_id = pinned_message.get('message_id')

            # 2. Verificar que el mensaje fijado sea nuestro archivo de índice
            if 'document' in pinned_message and pinned_message['document']['file_name'] == INDEX_FILENAME:
                file_id = pinned_message['document']['file_id']
                
                # 3. Descargar el archivo de índice
                content, msg = self.download_file_by_id(file_id)
                if content:
                    self.index = json.loads(content)
                    logger.info(f"Índice cargado y sincronizado desde Telegram. {len(self.index)} archivos.")
                    st.success("✅ Índice de archivos sincronizado.")
                else:
                    logger.error(f"No se pudo descargar el archivo de índice: {msg}")
                    st.error("Error al sincronizar: No se pudo descargar el índice.")
                    self.index = {}
            else:
                logger.warning("El mensaje fijado no es un archivo de índice válido.")
                self.index = {}

        except Exception as e:
            logger.error(f"Excepción al cargar el índice desde Telegram: {e}")
            st.error(f"Error fatal durante la sincronización: {e}")
            self.index = {}

    # NUEVO: Lógica para guardar el índice como un archivo en Telegram y fijarlo
    def save_index_to_telegram(self):
        """Sube el índice como un archivo JSON a Telegram, lo fija y desancla el anterior."""
        if not self.config.get('chat_id'):
            return False
        
        logger.info("Guardando índice en Telegram...")
        try:
            # 1. Convertir el diccionario de índice a bytes
            index_bytes = json.dumps(self.index, indent=2).encode('utf-8')

            # 2. Subir el archivo de índice
            files = {'document': (INDEX_FILENAME, index_bytes)}
            data = {'chat_id': self.config['chat_id'], 'disable_notification': True}
            
            response = requests.post(f"{self.base_url}/sendDocument", files=files, data=data, timeout=60)
            if response.status_code != 200:
                logger.error(f"Error subiendo índice: {response.text}")
                return False

            result = response.json()
            if not result['ok']:
                logger.error(f"Error API subiendo índice: {result.get('description')}")
                return False

            new_message_id = result['result']['message_id']

            # 3. Desanclar el mensaje de índice antiguo si existe
            if self.index_message_id:
                requests.post(f"{self.base_url}/unpinChatMessage", data={'chat_id': self.config['chat_id'], 'message_id': self.index_message_id})
                logger.info(f"Mensaje de índice antiguo ({self.index_message_id}) desanclado.")

            # 4. Fijar el nuevo mensaje de índice
            pin_response = requests.post(f"{self.base_url}/pinChatMessage", data={'chat_id': self.config['chat_id'], 'message_id': new_message_id, 'disable_notification': True})
            if not pin_response.json().get('ok'):
                logger.error(f"¡Error Crítico! No se pudo fijar el nuevo índice: {pin_response.text}. El bot necesita ser admin con permiso para fijar mensajes.")
                st.error("⚠️ ¡Error! No se pudo fijar el nuevo índice. Asegúrate de que el bot sea administrador con permiso para 'Fijar Mensajes'.")
                return False

            self.index_message_id = new_message_id
            logger.info(f"Índice guardado y fijado en Telegram (Mensaje ID: {new_message_id}).")
            return True

        except Exception as e:
            logger.error(f"Excepción al guardar el índice en Telegram: {e}")
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
        # ... (sin cambios en esta función)
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

    def file_exists(self, remote_name):
        """Verifica si existe un archivo con el mismo nombre"""
        return remote_name in self.index
    
    def upload_file(self, file_bytes, filename, remote_name=None):
        """Sube archivo a Telegram"""
        # ... (sin cambios internos, pero ahora save_index() es más potente)
        if len(file_bytes) > 2 * 1024 * 1024 * 1024:  # 2GB
            return False, "Archivo demasiado grande (máximo 2GB)"
        
        if not self.config.get('chat_id'):
            return False, "Chat ID no configurado"
        
        remote_name = remote_name or filename
        file_hash = hashlib.md5(file_bytes).hexdigest()
        
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
                    if not self.save_index():
                        # Si falla el guardado del índice, se revierte la operación para mantener la consistencia
                        del self.index[remote_name]
                        return False, "Error: El archivo se subió, pero no se pudo actualizar el índice remoto."

                    return True, f"Archivo '{remote_name}' subido y sincronizado"
                else:
                    return False, f"Error API: {result.get('description', 'Error desconocido')}"
            else:
                return False, f"Error HTTP: {response.status_code}"
                
        except Exception as e:
            return False, f"Error: {str(e)}"

    # MODIFICADO: Renombrada para mayor claridad y reutilización
    def download_file_by_id(self, file_id):
        """Descarga un archivo directamente usando su file_id."""
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
        """Descarga archivo de Telegram usando el nombre del índice."""
        if remote_name not in self.index:
            return None, f"Archivo '{remote_name}' no encontrado en el índice"
        
        file_id = self.index[remote_name]['file_id']
        return self.download_file_by_id(file_id)

    def delete_file(self, remote_name):
        """Elimina archivo del índice y guarda el nuevo índice en Telegram."""
        if remote_name not in self.index:
            return False, f"Archivo '{remote_name}' no encontrado"
        
        try:
            del self.index[remote_name]
            if self.save_index():
                return True, f"Archivo '{remote_name}' eliminado del índice"
            else:
                # La reversión es más compleja aquí, pero por ahora notificamos el fallo.
                return False, "Error: No se pudo actualizar el índice remoto tras la eliminación."
        except Exception as e:
            return False, f"Error: {str(e)}"

# ... (El resto del código, `format_size`, `zip_folder` y `main`, no necesita cambios)
def format_size(bytes_size):
    """Formatea tamaño de archivo"""
    if not isinstance(bytes_size, (int, float)): return "0 B"
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
    st.markdown("*Sistema de almacenamiento en la nube*")
    
    with st.expander("📌 Cómo empezar (Haz clic para ver)"):
        st.markdown("""
        1. **Obtén tu token**:
           - Busca **@BotFather** en Telegram, envia /newbot, sigue las instrucciones.
           - Copia el token que te proporcionará.
           - **¡MUY IMPORTANTE!** Promociona tu bot a **Administrador** y asegúrate de que tiene el permiso para **Fijar Mensajes**.
        
        3. **Configuración en la App**:
           - Ingresa el token en el panel lateral.
           - Envía un mensaje cualquiera al bot. "Hola"
           - La aplicación detectará automáticamente tu Chat ID y se configurará.
        
        4. **¡Listo!** 
        """)
    
    if 'client' not in st.session_state:
        st.session_state.client = None
    
    with st.sidebar:
        st.header("⚙️ Configuración")
        
        bot_token = st.text_input(
            "🔑 Token del Bot:",
            type="password",
            help="Obtén tu token de @BotFather en Telegram"
        )
        
        if bot_token:
            if not st.session_state.client or st.session_state.client.bot_token != bot_token:
                st.session_state.client = TelegramCloudStorage(bot_token)
            
            client = st.session_state.client
            is_valid, bot_info = client.test_bot_token()
            
            if is_valid:
                st.success(f"✅ Bot: {bot_info.get('first_name', 'Bot')}")
                
                if not client.config.get('chat_id'):
                    with st.spinner("Buscando Chat ID... Envía un mensaje a tu bot/grupo/canal."):
                        chats = client.get_chat_ids()
                        if chats:
                            chat_options = {name: id for id, name in chats}
                            selected_chat_name = st.selectbox("Selecciona el Chat/Canal de destino:", options=chat_options.keys())
                            if st.button("Guardar Configuración"):
                                chat_id = chat_options[selected_chat_name]
                                if client.save_config(chat_id):
                                    st.success("✅ Configuración guardada. Recargando...")
                                    st.rerun()
                                else:
                                    st.error("Error al guardar configuración")
                        else:
                            st.error("❌ No se encontraron chats. Envía un mensaje a tu bot/grupo/canal primero.")
                else:
                    st.success("✅ Configuración lista y sincronizada.")
                    if st.button("🔄 Reiniciar configuración"):
                        if client.config_file.exists():
                           os.remove(client.config_file)
                        st.session_state.client = None
                        st.rerun()
            else:
                st.error("❌ Token inválido")
        else:
            st.info("👆 Ingresa tu token para comenzar")
    
    if not st.session_state.get('client') or not st.session_state.client.config.get('chat_id'):
        st.warning("⚠️ Completa la configuración en el panel lateral para continuar.")
        return
    
    client = st.session_state.client
    
    tab1, tab2, tab3 = st.tabs(["📤 Subir", "📁 Archivos", "📊 Estadísticas"])
    
    with tab1:
        # ... (código de la tab1 sin cambios) ...
        st.header("📤 Subir Archivos")
        uploaded_files = st.file_uploader(
            "Selecciona archivos:",
            accept_multiple_files=True,
            help="Máximo 2GB por archivo"
        )
        if uploaded_files:
            for idx, uploaded_file in enumerate(uploaded_files):
                unique_id = f"file_{idx}_{uploaded_file.name}"
                col1, col2, col3 = st.columns([2, 2, 1])
                with col1:
                    st.write(f"📄 **{uploaded_file.name}** ({format_size(uploaded_file.size)})")
                    if client.file_exists(uploaded_file.name):
                        st.warning(f"'{uploaded_file.name}' ya existe. Subir lo sobrescribirá.")
                with col2:
                    custom_name = st.text_input("Nombre remoto:", value=uploaded_file.name, key=f"name_{unique_id}")
                    if custom_name != uploaded_file.name and client.file_exists(custom_name):
                        st.warning(f"'{custom_name}' ya existe. Subir lo sobrescribirá.")
                with col3:
                    if st.button("📤 Subir", key=f"upload_{unique_id}"):
                        with st.spinner(f"Subiendo {custom_name}..."):
                            file_bytes = uploaded_file.read()
                            success, message = client.upload_file(file_bytes, uploaded_file.name, custom_name)
                        if success:
                            st.success(message)
                        else:
                            st.error(message)

        st.markdown("---")
        st.subheader("📂 Subir Carpeta (como ZIP)")
        folder_path_input = st.text_input("Ruta local de la carpeta:", placeholder="Ej: C:/Users/TuUsuario/Documents/Proyecto", key="folder_path")
        if folder_path_input and os.path.isdir(folder_path_input):
            folder_name = os.path.basename(folder_path_input)
            zip_name = f"{folder_name}.zip"
            col1, col2 = st.columns([3, 1])
            with col1:
                custom_zip_name = st.text_input("Nombre del archivo ZIP:", value=zip_name, key="zip_name")
                if client.file_exists(custom_zip_name):
                    st.warning(f"'{custom_zip_name}' ya existe. Subir lo sobrescribirá.")
            with col2:
                st.write(" ") 
                if st.button("📤 Subir Carpeta", key="upload_folder"):
                    with st.spinner(f"Comprimiendo y subiendo {custom_zip_name}..."):
                        try:
                            zip_buffer = zip_folder(folder_path_input)
                            zip_bytes = zip_buffer.getvalue()
                            success, message = client.upload_file(zip_bytes, zip_name, custom_zip_name)
                            if success:
                                st.success(message)
                            else:
                                st.error(message)
                        except Exception as e:
                            st.error(f"Error al comprimir: {str(e)}")
        elif folder_path_input:
            st.error("La ruta ingresada no es un directorio válido.")

    with tab2:
        # MODIFICADO: Añadimos una columna para el botón de sincronización
        col_header, col_button = st.columns([3, 1])
        with col_header:
            st.header("📁 Mis Archivos")
        
        # NUEVO: Botón de Sincronización Manual
        with col_button:
            st.write("") # Espaciador para alinear verticalmente
            if st.button("🔄 Sincronizar Ahora"):
                client.load_index_from_telegram()
                st.rerun()

        if not client.index:
            st.info("📭 No tienes archivos almacenados")
        else:
            col1, col2 = st.columns([2, 1])
            with col1:
                search = st.text_input("🔍 Buscar:", key="search")
            with col2:
                sort_by = st.selectbox("📊 Ordenar:", ["Fecha ↓", "Fecha ↑", "Tamaño ↓", "Tamaño ↑", "Nombre A-Z", "Nombre Z-A"])
            
            filtered = {name: info for name, info in client.index.items() if not search or search.lower() in name.lower()}
            
            sort_key_map = {
                "Fecha ↓": (lambda x: x[1]['upload_date'], True),
                "Fecha ↑": (lambda x: x[1]['upload_date'], False),
                "Tamaño ↓": (lambda x: x[1]['size'], True),
                "Tamaño ↑": (lambda x: x[1]['size'], False),
                "Nombre A-Z": (lambda x: x[0], False),
                "Nombre Z-A": (lambda x: x[0], True)
            }
            sort_func, reverse = sort_key_map[sort_by]
            sorted_files = sorted(filtered.items(), key=sort_func, reverse=reverse)

            st.info(f"📋 Mostrando {len(sorted_files)} de {len(client.index)} archivos totales.")
            
            for name, info in sorted_files:
                file_unique_id = hashlib.md5(name.encode()).hexdigest()[:8]
                with st.expander(f"📄 {name} ({format_size(info['size'])})"):
                    # (El resto del código para mostrar los archivos no cambia)
                    col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
                    with col1:
                        upload_date = datetime.fromisoformat(info['upload_date'])
                        st.write(f"📅 {upload_date.strftime('%d/%m/%Y %H:%M')}")
                        st.caption(f"Nombre original: {info.get('original_filename', name)}")
                        st.caption(f"Hash: {info['hash'][:16]}...")
                    with col2:
                        st.download_button(
                            label="📥 Descargar",
                            data=b'',
                            file_name=name,
                            key=f"dl_btn_{file_unique_id}",
                            disabled=True
                        )
                    with col3:
                        if st.button("🗑️ Eliminar", key=f"delete_{file_unique_id}"):
                            success, message = client.delete_file(name)
                            if success:
                                st.success(message)
                                st.rerun()
                            else:
                                st.error(message)
                    
                    with col2:
                        if st.button("Preparar Descarga", key=f"prep_dl_{file_unique_id}"):
                             with st.spinner("Descargando..."):
                                content, message = client.download_file(name)
                                if content:
                                    st.session_state[f'dl_data_{file_unique_id}'] = (content, name)
                                else:
                                    st.error(message)

                    if f'dl_data_{file_unique_id}' in st.session_state:
                         content, file_name = st.session_state[f'dl_data_{file_unique_id}']
                         st.download_button(
                            label="✅ ¡Guardar Ahora!",
                            data=content,
                            file_name=file_name,
                            mime='application/octet-stream',
                            key=f"save_{file_unique_id}"
                         )
                         del st.session_state[f'dl_data_{file_unique_id}']


    with tab3:
        # ... (código de la tab3 sin cambios) ...
        st.header("📊 Estadísticas")
        if not client.index:
            st.info("📭 No hay datos disponibles")
        else:
            total_files = len(client.index)
            total_size = sum(info.get('size', 0) for info in client.index.values())
            avg_size = total_size / total_files if total_files > 0 else 0
            
            col1, col2, col3 = st.columns(3)
            with col1: st.metric("📁 Archivos Totales", total_files)
            with col2: st.metric("💾 Espacio Utilizado", format_size(total_size))
            with col3: st.metric("📊 Tamaño Promedio", format_size(avg_size))
            
            st.subheader("🔝 5 Archivos más grandes")
            largest = sorted(client.index.items(), key=lambda x: x[1].get('size', 0), reverse=True)[:5]
            for i, (name, info) in enumerate(largest, 1):
                st.write(f"{i}. **{name}** - {format_size(info.get('size', 0))}")
            
            st.subheader("⏰ 5 Archivos más recientes")
            recent = sorted(client.index.items(), key=lambda x: x[1]['upload_date'], reverse=True)[:5]
            for name, info in recent:
                date = datetime.fromisoformat(info['upload_date'])
                st.write(f"📄 **{name}** - subido el {date.strftime('%d/%m/%Y a las %H:%M')}")


if __name__ == "__main__":
    main()