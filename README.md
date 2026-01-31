# Inforeader Cédula - App de Lectura PDF417

Aplicación de escritorio para lectura y gestión de códigos de barras PDF417 en cédulas colombianas con almacenamiento local y sincronización centralizada.

---

## 🎯 Características

✅ **Lectura PDF417 crítica** - Legible usando `pyzbar` (robusta y fiable)  
✅ **Almacenamiento local** - SQLite en cada dispositivo  
✅ **Exportación CSV** - Descarga de registros en cualquier momento  
✅ **Sincronización servidor** - Envío centralizado de datos  
✅ **Autenticación** - Login con roles (admin/lector)  
✅ **Portable** - Ejecutable único (37 MB) sin instalación  

---

## 📦 Distribución

### Requisitos
- Windows 10/11 (64 bits)
- Permisos para escribir en la carpeta donde esté el `.exe`
- Cámara o scanner para códigos de barras (opcional, puedes cargar imágenes)

### Instalación rápida
1. Descarga: `dist/cedulas_app.exe`
2. Copia a cualquier carpeta (ej: `C:\Apps\cedulas_app.exe`)
3. Ejecuta el `.exe` - ¡listo!

No requiere instalación, no contamina el registro de Windows.

---

## 🔐 Credenciales por defecto

| Usuario | Contraseña | Rol | Acceso |
|---------|-----------|-----|--------|
| admin | 1234 | Admin | Todo (crear usuarios, exportar, sincronizar) |
| lector | lector | Lector | Solo consulta y lectura |

**⚠️ IMPORTANTE**: Cambiar contraseña del admin en la primera ejecución.

---

## 🚀 Uso

### Admin: Lectura de cédula
1. Click en "Cargar Imagen"
2. Selecciona foto del código PDF417
3. App extrae datos automáticamente
4. Datos se guardan en `cedulas.db` (junto al `.exe`)

### Admin: Exportar datos
1. Click en "Exportar a CSV"
2. Se descarga `cedulas_export_YYYYMMDD_HHMMSS.csv` 
3. Abre con Excel o similar

### Admin: Sincronizar servidor
1. Click en "Configurar Servidor"
2. Ingresa IP/dominio del servidor central (ej: `192.168.1.100`)
3. Puerto (default: 5000)
4. Habilita con "si"
5. Click en "Sincronizar Servidor" para enviar datos

**Formato esperado del servidor:**
```
POST http://IP:PUERTO/api/sincronizar
{
  "dispositivo": "NOMBRE_COMPUTADORA",
  "timestamp": "2026-01-29T21:00:00",
  "registros": [
    {
      "numero": "1234567890",
      "nombres": "JUAN",
      "apellidos": "PÉREZ",
      "fecha_nacimiento": "1990-01-15",
      "sexo": "M",
      "lugar_expedicion": "BOGOTÁ"
    }
  ]
}
```

### Lector: Solo consulta
- Búsqueda por número o nombre
- Ver registros guardados
- NO puede cargar nuevas cédulas ni exportar

---

## 📁 Archivos generados

Junto al `cedulas_app.exe` se crean:

| Archivo | Descripción |
|---------|-------------|
| `cedulas.db` | Base de datos SQLite (registros) |
| `config.json` | Configuración de servidor |
| `cedulas_export_*.csv` | Exportaciones (generadas al exportar) |

---

## 🛠️ Compilación (para desarrolladores)

### Requisitos desarrollo
```bash
pip install PyQt5 opencv-python pyzbar requests
pip install pyinstaller
```

### Build --onedir (pruebas)
```bash
python -m PyInstaller --onedir --windowed cedulas_app.py
```
Resultado: `dist/cedulas_app/cedulas_app.exe` (~200 MB)

### Build --onefile (producción)
```bash
python -m PyInstaller --onefile --windowed cedulas_app.py
```
Resultado: `dist/cedulas_app.exe` (~37 MB) ← **Recomendado para distribución**

---

## 🐛 Solución de problemas

### "Failed to load platform plugin 'windows'"
- **Causa**: Falta PyQt5 plugins
- **Solución**: Reinstala PyQt5 o recompila

### "No se detecta código PDF417"
- **Causa**: Imagen borrosa, mal ángulo o poca luz
- **Solución**: 
  - Toma foto con buena iluminación
  - Código debe ocupar >50% de la imagen
  - Prueba con código de prueba conocido

### "No se puede conectar al servidor"
- **Verificar**: IP, puerto, firewall
- **Debug**: Abre CMD en la carpeta del exe y ejecuta:
  ```
  ipconfig  (obtén tu IP)
  ```
  Asegúrate que el servidor escucha en esa IP:puerto

### "BaseDE de datos bloqueada"
- **Causa**: Otra instancia de la app abierta
- **Solución**: Cierra todos los `cedulas_app.exe`

---

## 📝 Notas de seguridad

⚠️ **Backup regular**: la DB `cedulas.db` contiene datos sensibles
- Haz backup periódico de `cedulas.db`
- O usa sincronización automática a servidor

⚠️ **Acceso físico**: Cualquiera con acceso a la máquina puede ver los datos
- Usa contraseña Windows si necesitas más seguridad
- Considera encriptación de disco

⚠️ **Sincronización**: El envío es en HTTP (no encriptado)
- Para producción, configura servidor con HTTPS
- Usa autenticación en servidor (tokens, API keys)

---

## 📞 Soporte

Para problemas o mejoras:
1. Revisa la carpeta `dist` y busca `warn-cedulas_app.txt` (warnings de compilación)
2. Ejecuta desde CMD para ver mensajes de error en tiempo real
3. Contacta al desarrollador con detalles del error

---

**Versión**: 1.0  
**Última actualización**: 29 de enero de 2026  
**Estado**: Listo para producción ✅
