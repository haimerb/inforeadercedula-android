[app]

# Nombre de la aplicación
title = Inforeader Cedula

# Nombre del paquete (dominio inverso)
package.name = inforeadercedula

# Dominio del paquete
package.domain = com.inforeader

# Código fuente (archivo principal)
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json,db

# Archivo principal de entrada
source.main = cedulas_app_android.py

# Versión de la aplicación
version = 1.0.0

# Requisitos (dependencias Python)
# Nota: opencv-python y pyzbar son muy pesados y difíciles de compilar
# Usamos solo las dependencias básicas + parseo manual del código
requirements = python3,kivy==2.3.0,pillow,requests,android

# Iconos y splash (opcional, puedes agregar luego)
#icon.filename = %(source.dir)s/icon.png
#presplash.filename = %(source.dir)s/presplash.png

# Permisos de Android necesarios
android.permissions = CAMERA,WRITE_EXTERNAL_STORAGE,READ_EXTERNAL_STORAGE,INTERNET,ACCESS_NETWORK_STATE

# Características de hardware requeridas
android.features = android.hardware.camera

# Arquitecturas soportadas
android.archs = arm64-v8a,armeabi-v7a

# API mínima de Android (Android 5.0)
android.api = 31
android.minapi = 21

# NDK versión
android.ndk = 25b

# Orientación (portrait, landscape o all)
orientation = portrait

# Habilitar AndroidX
android.enable_androidx = True

# Servicios en background (opcional)
# android.services = MyService:service.py

# Bootstrap de Python para Android
p4a.bootstrap = sdl2

# Receta de pyzbar para P4A (puede necesitar configuración adicional)
# p4a.local_recipes = ./p4a-recipes

# Configuración de logging
log_level = 2
warn_on_root = 1

# Full screen
fullscreen = 0

# Color de fondo
# android.presplash_color = #FFFFFF

[buildozer]

# Log level (0 = error, 1 = info, 2 = debug)
log_level = 2

# Mostrar advertencias
warn_on_root = 1

# Directorio de build (no versionar esto)
# build_dir = ./.buildozer

# Directorio de distribución del APK final
# bin_dir = ./bin
