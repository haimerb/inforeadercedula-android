"""
Inforeader Cédula - Versión Android con Kivy
Adaptación de la aplicación de escritorio para dispositivos Android
"""

import os
import sqlite3
import hashlib
import csv
import json
from datetime import datetime
from functools import partial

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.uix.popup import Popup
from kivy.uix.scrollview import ScrollView
from kivy.uix.screenmanager import ScreenManager, Screen
from kivy.uix.spinner import Spinner
from kivy.clock import Clock
from kivy.properties import StringProperty, ObjectProperty
from kivy.metrics import dp

# Importaciones para cámara y códigos de barras
try:
    from android.permissions import request_permissions, Permission
    ANDROID = True
    request_permissions([
        Permission.CAMERA,
        Permission.WRITE_EXTERNAL_STORAGE,
        Permission.READ_EXTERNAL_STORAGE,
        Permission.INTERNET
    ])
except ImportError:
    ANDROID = False

# Nota: pyzbar y opencv removidos para reducir tamaño del APK
# La app usará solo el parser manual de códigos PDF417
pyzbar_decode = None
cv2 = None

import requests

# ============================================
# FUNCIONES DE BASE DE DATOS (reutilizadas)
# ============================================

def get_app_dir():
    """Directorio de la aplicación en Android o Desktop"""
    if ANDROID:
        from android.storage import app_storage_path
        return app_storage_path()
    return os.path.dirname(os.path.abspath(__file__))

def get_db_path():
    return os.path.join(get_app_dir(), "cedulas.db")

def get_config_path():
    return os.path.join(get_app_dir(), "config.json")

def init_db():
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ciudadanos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        numero TEXT,
        nombres TEXT,
        apellidos TEXT,
        fecha_nacimiento TEXT,
        sexo TEXT,
        lugar_expedicion TEXT
    )
    """)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS usuarios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        rol TEXT
    )
    """)
    password_hash = hashlib.sha256("1234".encode()).hexdigest()
    cursor.execute("INSERT OR IGNORE INTO usuarios (username, password, rol) VALUES (?, ?, ?)", 
                   ("admin", password_hash, "admin"))
    lector_hash = hashlib.sha256("lector".encode()).hexdigest()
    cursor.execute("INSERT OR IGNORE INTO usuarios (username, password, rol) VALUES (?, ?, ?)", 
                   ("lector", lector_hash, "lector"))
    conn.commit()
    conn.close()

def validar_usuario(username, password):
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    cursor.execute("SELECT rol FROM usuarios WHERE username=? AND password=?", (username, password_hash))
    usuario = cursor.fetchone()
    conn.close()
    return usuario[0] if usuario else None

def guardar_en_db(datos):
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()
    cursor.execute("""
    INSERT INTO ciudadanos (numero, nombres, apellidos, fecha_nacimiento, sexo, lugar_expedicion)
    VALUES (?, ?, ?, ?, ?, ?)
    """, (datos["numero"], datos["nombres"], datos["apellidos"],
          datos["fecha_nacimiento"], datos["sexo"], datos["lugar_expedicion"]))
    conn.commit()
    conn.close()

def obtener_registros(filtro=None):
    conn = sqlite3.connect(get_db_path())
    cursor = conn.cursor()
    if filtro:
        cursor.execute("""
        SELECT numero, nombres, apellidos, fecha_nacimiento, sexo, lugar_expedicion
        FROM ciudadanos
        WHERE numero LIKE ? OR nombres LIKE ? OR apellidos LIKE ?
        """, (f"%{filtro}%", f"%{filtro}%", f"%{filtro}%"))
    else:
        cursor.execute("SELECT numero, nombres, apellidos, fecha_nacimiento, sexo, lugar_expedicion FROM ciudadanos")
    registros = cursor.fetchall()
    conn.close()
    return registros

def cargar_config():
    ruta = get_config_path()
    if os.path.exists(ruta):
        try:
            with open(ruta, 'r') as f:
                return json.load(f)
        except Exception:
            pass
    return {"servidor": "", "puerto": 5000, "habilitado": False}

def guardar_config(config):
    ruta = get_config_path()
    try:
        with open(ruta, 'w') as f:
            json.dump(config, f, indent=2)
        return True
    except Exception:
        return False

def exportar_a_csv(filtro=None):
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        archivo = os.path.join(get_app_dir(), f"cedulas_export_{timestamp}.csv")
        
        registros = obtener_registros(filtro)
        if not registros:
            return None, "No hay registros para exportar"
        
        with open(archivo, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f, delimiter=',')
            writer.writerow(["Número", "Nombres", "Apellidos", "Nacimiento", "Sexo", "Lugar Expedición"])
            for registro in registros:
                writer.writerow(registro)
        
        return archivo, f"Exportado {len(registros)} registros"
    except Exception as e:
        return None, f"Error exportando: {str(e)}"

def sincronizar_con_servidor():
    config = cargar_config()
    if not config.get("habilitado"):
        return False, "Sincronización deshabilitada"
    
    servidor = config.get("servidor", "").strip()
    puerto = config.get("puerto", 5000)
    if not servidor:
        return False, "Servidor no configurado"
    
    try:
        registros = obtener_registros()
        if not registros:
            return False, "No hay registros para sincronizar"
        
        datos = {
            "dispositivo": "Android" if ANDROID else "Desktop",
            "timestamp": datetime.now().isoformat(),
            "registros": [
                {
                    "numero": r[0], "nombres": r[1], "apellidos": r[2],
                    "fecha_nacimiento": r[3], "sexo": r[4], "lugar_expedicion": r[5]
                }
                for r in registros
            ]
        }
        
        url = f"http://{servidor}:{puerto}/api/sincronizar"
        resp = requests.post(url, json=datos, timeout=10)
        
        if resp.status_code == 200:
            return True, f"Sincronizados {len(registros)} registros"
        else:
            return False, f"Error servidor: {resp.status_code}"
    except Exception as e:
        return False, f"Error: {str(e)}"

# ============================================
# FUNCIONES PDF417 (reutilizadas)
# ============================================

def leer_pdf417_desde_imagen(imagen_path):
    """
    Lee código PDF417 desde archivo de imagen
    Nota: En Android, opencv y pyzbar no están disponibles por tamaño.
    Esta función retorna None y se debe usar entrada manual del código.
    Para implementar lectura de imágenes, considera usar:
    - ZXing nativo de Android (vía Pyjnius)
    - Servicio web de decodificación
    """
    # Temporalmente deshabilitado para reducir tamaño de APK
    # En producción, implementar con ZXing nativo o servicio web
    return None

def parsear_datos(data):
    """Parser del código PDF417 colombiano (reutilizado del código original)"""
    if not data:
        return {
            "numero": "",
            "nombres": "",
            "apellidos": "",
            "fecha_nacimiento": "",
            "sexo": "",
            "lugar_expedicion": ""
        }

    s = data if isinstance(data, str) else data.decode("utf-8", errors="ignore")
    
    if "@" in s and len(s.split("@")) >= 4:
        campos = [c.strip() for c in s.split("@")]
        return {
            "numero": campos[1] if len(campos) > 1 else "",
            "nombres": campos[2] if len(campos) > 2 else "",
            "apellidos": campos[3] if len(campos) > 3 else "",
            "fecha_nacimiento": campos[4] if len(campos) > 4 else "",
            "sexo": campos[5] if len(campos) > 5 else "",
            "lugar_expedicion": campos[6] if len(campos) > 6 else ""
        }

    import re
    patron_fecha = r'([MF])(\d{4})(\d{2})(\d{2})(\d{2})(\d{3})'
    match = re.search(patron_fecha, s)
    
    if match:
        genero = match.group(1)
        year = match.group(2)
        month = match.group(3)
        day = match.group(4)
        municipio = match.group(5)
        departamento = match.group(6)
        
        prefijo = s[:match.start()]
        numeros_candidatos = re.findall(r'\d{10,}', prefijo)
        
        documento = ""
        if numeros_candidatos:
            numeros_con_posicion = [(m.start(), m.group()) for m in re.finditer(r'\d{10,}', prefijo)]
            if len(numeros_con_posicion) > 1:
                documento = numeros_con_posicion[-1][1]
            else:
                documento = numeros_candidatos[-1]
        
        palabras_raw = re.findall(r'[A-Z]+', s)
        palabras = []
        for p in palabras_raw:
            if len(p) >= 3 and p not in ["DSK", "PUB", "PUBDSK"]:
                palabras.append(p)
        
        apellido1 = palabras[0] if len(palabras) > 0 else ""
        apellido2 = palabras[1] if len(palabras) > 1 else ""
        nombre1 = palabras[2] if len(palabras) > 2 else ""
        nombre2 = palabras[3] if len(palabras) > 3 else ""
        
        apellidos = " ".join([p for p in [apellido1, apellido2] if p])
        nombres = " ".join([p for p in [nombre1, nombre2] if p])
        
        fecha = ""
        try:
            y = int(year) if year.isdigit() else 0
            m = int(month) if month.isdigit() else 0
            d = int(day) if day.isdigit() else 0
            if 1900 <= y <= 2100 and 1 <= m <= 12 and 1 <= d <= 31:
                fecha = f"{year}-{month}-{day}"
        except Exception:
            pass
        
        return {
            "numero": documento,
            "nombres": nombres.title(),
            "apellidos": apellidos.title(),
            "fecha_nacimiento": fecha,
            "sexo": "M" if genero.upper() == "M" else "F",
            "lugar_expedicion": f"{departamento}-{municipio}".strip("-") if departamento or municipio else ""
        }
    
    return {
        "numero": "",
        "nombres": "",
        "apellidos": "",
        "fecha_nacimiento": "",
        "sexo": "",
        "lugar_expedicion": ""
    }

# ============================================
# PANTALLAS KIVY
# ============================================

class LoginScreen(Screen):
    """Pantalla de login"""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation='vertical', padding=dp(20), spacing=dp(10))
        
        layout.add_widget(Label(
            text='Inforeader Cédula',
            size_hint_y=0.2,
            font_size=dp(24),
            bold=True
        ))
        
        self.username_input = TextInput(
            hint_text='Usuario',
            multiline=False,
            size_hint_y=0.1
        )
        layout.add_widget(self.username_input)
        
        self.password_input = TextInput(
            hint_text='Contraseña',
            multiline=False,
            password=True,
            size_hint_y=0.1
        )
        layout.add_widget(self.password_input)
        
        self.status_label = Label(
            text='',
            size_hint_y=0.1,
            color=(1, 0, 0, 1)
        )
        layout.add_widget(self.status_label)
        
        btn_login = Button(
            text='Iniciar Sesión',
            size_hint_y=0.1,
            background_color=(0.2, 0.6, 1, 1)
        )
        btn_login.bind(on_press=self.do_login)
        layout.add_widget(btn_login)
        
        layout.add_widget(Label(size_hint_y=0.4))
        
        self.add_widget(layout)
    
    def do_login(self, instance):
        username = self.username_input.text.strip()
        password = self.password_input.text.strip()
        
        rol = validar_usuario(username, password)
        if rol:
            app = App.get_running_app()
            app.current_rol = rol
            app.current_username = username
            self.manager.current = 'main'
            self.status_label.text = ''
            self.password_input.text = ''
        else:
            self.status_label.text = 'Usuario o contraseña inválidos'

class MainScreen(Screen):
    """Pantalla principal"""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.layout = BoxLayout(orientation='vertical', padding=dp(10), spacing=dp(10))
        
        # Título con rol
        self.title_label = Label(
            text='Lectura de Cédulas',
            size_hint_y=0.08,
            font_size=dp(20),
            bold=True
        )
        self.layout.add_widget(self.title_label)
        
        # Campo de entrada para scanner
        scan_layout = BoxLayout(orientation='horizontal', size_hint_y=0.1, spacing=dp(5))
        scan_layout.add_widget(Label(text='Código:', size_hint_x=0.2))
        self.scanner_input = TextInput(
            hint_text='Escanea aquí o escribe manualmente',
            multiline=False,
            size_hint_x=0.8
        )
        self.scanner_input.bind(on_text_validate=self.procesar_codigo)
        scan_layout.add_widget(self.scanner_input)
        self.layout.add_widget(scan_layout)
        
        # Botones de acción
        btn_layout = GridLayout(cols=2, size_hint_y=0.15, spacing=dp(5))
        
        btn_camara = Button(text='📷 Cámara', background_color=(0.2, 0.7, 0.3, 1))
        btn_camara.bind(on_press=self.abrir_camara)
        btn_layout.add_widget(btn_camara)
        
        self.btn_exportar = Button(text='📊 Exportar', background_color=(0.9, 0.6, 0.2, 1))
        self.btn_exportar.bind(on_press=self.exportar_csv)
        btn_layout.add_widget(self.btn_exportar)
        
        self.btn_sync = Button(text='🔄 Sincronizar', background_color=(0.6, 0.3, 0.9, 1))
        self.btn_sync.bind(on_press=self.sincronizar)
        btn_layout.add_widget(self.btn_sync)
        
        self.btn_config = Button(text='⚙️ Config', background_color=(0.5, 0.5, 0.5, 1))
        self.btn_config.bind(on_press=self.abrir_config)
        btn_layout.add_widget(self.btn_config)
        
        self.layout.add_widget(btn_layout)
        
        # Búsqueda
        search_layout = BoxLayout(orientation='horizontal', size_hint_y=0.08, spacing=dp(5))
        self.search_input = TextInput(
            hint_text='Buscar...',
            multiline=False,
            size_hint_x=0.7
        )
        search_layout.add_widget(self.search_input)
        btn_search = Button(text='🔍', size_hint_x=0.15)
        btn_search.bind(on_press=self.buscar)
        search_layout.add_widget(btn_search)
        btn_clear = Button(text='✖', size_hint_x=0.15)
        btn_clear.bind(on_press=self.limpiar_busqueda)
        search_layout.add_widget(btn_clear)
        self.layout.add_widget(search_layout)
        
        # Tabla de registros (ScrollView)
        scroll = ScrollView(size_hint_y=0.49)
        self.registros_layout = GridLayout(cols=1, spacing=dp(2), size_hint_y=None)
        self.registros_layout.bind(minimum_height=self.registros_layout.setter('height'))
        scroll.add_widget(self.registros_layout)
        self.layout.add_widget(scroll)
        
        # Estado
        self.status_label = Label(
            text='',
            size_hint_y=0.06,
            color=(0, 0.8, 0, 1)
        )
        self.layout.add_widget(self.status_label)
        
        # Botón cerrar sesión
        btn_logout = Button(
            text='🚪 Cerrar Sesión',
            size_hint_y=0.08,
            background_color=(0.8, 0.2, 0.2, 1)
        )
        btn_logout.bind(on_press=self.logout)
        self.layout.add_widget(btn_logout)
        
        self.add_widget(self.layout)
    
    def on_enter(self):
        """Cuando se entra a esta pantalla"""
        app = App.get_running_app()
        rol = getattr(app, 'current_rol', 'lector')
        username = getattr(app, 'current_username', '')
        
        self.title_label.text = f'Cédulas - {username} ({rol})'
        
        # Deshabilitar botones según rol
        if rol != 'admin':
            self.btn_exportar.disabled = True
            self.btn_sync.disabled = True
            self.btn_config.disabled = True
        
        self.cargar_registros()
    
    def procesar_codigo(self, instance):
        """Procesar código escaneado"""
        codigo = self.scanner_input.text.strip()
        if not codigo:
            self.status_label.text = 'Código vacío'
            return
        
        datos = parsear_datos(codigo)
        self.scanner_input.text = ''
        
        if datos.get('numero'):
            self.mostrar_dialogo_datos(datos, codigo)
        else:
            self.status_label.text = '✗ No se pudo parsear el código'
    
    def mostrar_dialogo_datos(self, datos, raw_data):
        """Muestra popup con datos para confirmar"""
        content = BoxLayout(orientation='vertical', spacing=dp(10), padding=dp(10))
        
        content.add_widget(Label(text='Datos Decodificados:', size_hint_y=0.1, bold=True))
        
        campos = {}
        for key, label in [
            ('numero', 'Número:'),
            ('nombres', 'Nombres:'),
            ('apellidos', 'Apellidos:'),
            ('fecha_nacimiento', 'F. Nac.:'),
            ('sexo', 'Sexo:'),
            ('lugar_expedicion', 'Lugar:')
        ]:
            row = BoxLayout(orientation='horizontal', size_hint_y=0.1, spacing=dp(5))
            row.add_widget(Label(text=label, size_hint_x=0.3))
            input_field = TextInput(text=str(datos.get(key, '')), multiline=False, size_hint_x=0.7)
            campos[key] = input_field
            row.add_widget(input_field)
            content.add_widget(row)
        
        btn_layout = BoxLayout(orientation='horizontal', size_hint_y=0.15, spacing=dp(10))
        
        popup = Popup(title='Confirmar Datos', content=content, size_hint=(0.9, 0.8))
        
        def guardar(instance):
            datos_editados = {key: campos[key].text.strip() for key in campos}
            if not datos_editados.get('numero'):
                self.status_label.text = '✗ Número requerido'
                return
            guardar_en_db(datos_editados)
            self.status_label.text = f'✓ Guardado: {datos_editados["numero"]}'
            self.cargar_registros()
            popup.dismiss()
        
        btn_save = Button(text='💾 Guardar', background_color=(0.2, 0.8, 0.2, 1))
        btn_save.bind(on_press=guardar)
        btn_layout.add_widget(btn_save)
        
        btn_cancel = Button(text='❌ Cancelar', background_color=(0.8, 0.2, 0.2, 1))
        btn_cancel.bind(on_press=popup.dismiss)
        btn_layout.add_widget(btn_cancel)
        
        content.add_widget(btn_layout)
        popup.open()
    
    def abrir_camara(self, instance):
        """TODO: Implementar captura con cámara"""
        self.status_label.text = 'Cámara: en desarrollo'
        # Nota: Requiere plyer o android.camera
    
    def exportar_csv(self, instance):
        filtro = self.search_input.text.strip() or None
        archivo, mensaje = exportar_a_csv(filtro)
        self.status_label.text = mensaje
    
    def sincronizar(self, instance):
        exito, mensaje = sincronizar_con_servidor()
        self.status_label.text = mensaje
    
    def abrir_config(self, instance):
        """Abrir pantalla de configuración"""
        self.manager.current = 'config'
    
    def buscar(self, instance):
        self.cargar_registros()
    
    def limpiar_busqueda(self, instance):
        self.search_input.text = ''
        self.cargar_registros()
    
    def cargar_registros(self):
        """Carga registros en la lista"""
        filtro = self.search_input.text.strip() or None
        registros = obtener_registros(filtro)
        
        self.registros_layout.clear_widgets()
        
        if not registros:
            self.registros_layout.add_widget(Label(
                text='No hay registros',
                size_hint_y=None,
                height=dp(40)
            ))
            return
        
        for reg in registros:
            texto = f"{reg[0]} - {reg[1]} {reg[2]}"
            btn = Button(
                text=texto,
                size_hint_y=None,
                height=dp(40), usando ZXing o plyer"""
        self.status_label.text = 'Cámara: Usa entrada manual o scanner físico'
        # Implementación futura:
        # 1. Usar pyjnius para llamar ZXing de Android
        # 2. O usar plyer.camera para capturar y enviar a servicio web
        # 3. O implementar lector nativo con kivy-garden x
            )
            self.registros_layout.add_widget(btn)
    
    def logout(self, instance):
        self.manager.current = 'login'

class ConfigScreen(Screen):
    """Pantalla de configuración"""
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        layout = BoxLayout(orientation='vertical', padding=dp(20), spacing=dp(10))
        
        layout.add_widget(Label(
            text='Configuración Servidor',
            size_hint_y=0.1,
            font_size=dp(20),
            bold=True
        ))
        
        # Servidor
        srv_layout = BoxLayout(orientation='horizontal', size_hint_y=0.08, spacing=dp(5))
        srv_layout.add_widget(Label(text='Servidor:', size_hint_x=0.3))
        self.servidor_input = TextInput(multiline=False, size_hint_x=0.7)
        srv_layout.add_widget(self.servidor_input)
        layout.add_widget(srv_layout)
        
        # Puerto
        port_layout = BoxLayout(orientation='horizontal', size_hint_y=0.08, spacing=dp(5))
        port_layout.add_widget(Label(text='Puerto:', size_hint_x=0.3))
        self.puerto_input = TextInput(multiline=False, input_filter='int', size_hint_x=0.7)
        port_layout.add_widget(self.puerto_input)
        layout.add_widget(port_layout)
        
        # Habilitado
        hab_layout = BoxLayout(orientation='horizontal', size_hint_y=0.08, spacing=dp(5))
        hab_layout.add_widget(Label(text='Habilitar:', size_hint_x=0.3))
        self.habilitado_spinner = Spinner(
            text='No',
            values=('Sí', 'No'),
            size_hint_x=0.7
        )
        hab_layout.add_widget(self.habilitado_spinner)
        layout.add_widget(hab_layout)
        
        layout.add_widget(Label(size_hint_y=0.46))
        
        # Botones
        btn_layout = BoxLayout(orientation='horizontal', size_hint_y=0.1, spacing=dp(10))
        
        btn_save = Button(text='💾 Guardar', background_color=(0.2, 0.8, 0.2, 1))
        btn_save.bind(on_press=self.guardar)
        btn_layout.add_widget(btn_save)
        
        btn_back = Button(text='← Volver', background_color=(0.5, 0.5, 0.5, 1))
        btn_back.bind(on_press=self.volver)
        btn_layout.add_widget(btn_back)
        
        layout.add_widget(btn_layout)
        
        self.status_label = Label(text='', size_hint_y=0.08, color=(0, 0.8, 0, 1))
        layout.add_widget(self.status_label)
        
        self.add_widget(layout)
    
    def on_enter(self):
        """Cargar configuración actual"""
        config = cargar_config()
        self.servidor_input.text = config.get('servidor', '')
        self.puerto_input.text = str(config.get('puerto', 5000))
        self.habilitado_spinner.text = 'Sí' if config.get('habilitado') else 'No'
    
    def guardar(self, instance):
        config = {
            'servidor': self.servidor_input.text.strip(),
            'puerto': int(self.puerto_input.text or '5000'),
            'habilitado': self.habilitado_spinner.text == 'Sí'
        }
        if guardar_config(config):
            self.status_label.text = '✓ Guardado correctamente'
        else:
            self.status_label.text = '✗ Error al guardar'
    
    def volver(self, instance):
        self.manager.current = 'main'

# ============================================
# APLICACIÓN PRINCIPAL
# ============================================

class CedulasAndroidApp(App):
    current_rol = StringProperty('lector')
    current_username = StringProperty('')
    
    def build(self):
        # Inicializar base de datos
        init_db()
        
        # Crear screen manager
        sm = ScreenManager()
        sm.add_widget(LoginScreen(name='login'))
        sm.add_widget(MainScreen(name='main'))
        sm.add_widget(ConfigScreen(name='config'))
        
        return sm

if __name__ == '__main__':
    CedulasAndroidApp().run()
