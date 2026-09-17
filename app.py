from flask import Flask, render_template, request, redirect, url_for, session
import mysql.connector
from datetime import timedelta

app = Flask(__name__)
app.secret_key = "clave_secreta_agenda_isaac_2026"  # Necesaria para las sesiones
app.static_folder = 'static'
app.permanent_session_lifetime = timedelta(minutes=30)  # Sesión activa 30 min

# ===== CONFIGURACIÓN =====
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "root",  # ⚠️ Pon tu contraseña de MySQL
    "database": "agenda_isaac"
}

# ===== CONEXIÓN =====
def conectar():
    try:
        return mysql.connector.connect(**DB_CONFIG)
    except mysql.connector.Error as error:
        print(f"❌ Error de conexión: {error}")
        return None

# ===== CARGAR CONTACTOS =====
def cargar_contactos():
    conexion = conectar()
    if not conexion:
        return []
    try:
        cursor = conexion.cursor(dictionary=True)
        cursor.execute("SELECT * FROM contactos ORDER BY nombre ASC")
        return list(enumerate(cursor.fetchall()))
    except mysql.connector.Error:
        return []
    finally:
        conexion.close()

# ===== RUTA DE INICIO DE SESIÓN =====
@app.route('/login', methods=['GET', 'POST'])
def login():
    # Si ya inició sesión, ir directo a la agenda
    if 'usuario' in session:
        return redirect(url_for('inicio'))
    
    mensaje = ""
    if request.method == 'POST':
        usuario = request.form.get('usuario', '').strip()
        contrasena = request.form.get('contrasena', '').strip()
        
        conexion = conectar()
        if conexion:
            try:
                cursor = conexion.cursor(dictionary=True)
                cursor.execute(
                    "SELECT * FROM usuarios WHERE usuario = %s AND contrasena = %s",
                    (usuario, contrasena)
                )
                usuario_encontrado = cursor.fetchone()
                
                if usuario_encontrado:
                    session.permanent = True
                    session['usuario'] = usuario_encontrado['usuario']
                    session['nombre'] = usuario_encontrado['nombre_completo']
                    return redirect(url_for('inicio'))
                else:
                    mensaje = "⚠️ Usuario o contraseña incorrectos"
            finally:
                conexion.close()
        else:
            mensaje = "❌ No se pudo conectar a la base de datos"
    
    return render_template('login.html', mensaje=mensaje)

# ===== CERRAR SESIÓN =====
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ===== PÁGINA PRINCIPAL (PROTEGIDA) =====
@app.route('/')
def inicio():
    if 'usuario' not in session:
        return redirect(url_for('login'))
    contactos = cargar_contactos()
    return render_template('inicio.html', contactos=contactos, usuario=session.get('nombre', session['usuario']))

# ===== AGREGAR =====
@app.route('/agregar', methods=['POST'])
def agregar():
    if 'usuario' not in session:
        return redirect(url_for('login'))
    
    nombre = request.form.get('nombre', '').strip()
    telefono = request.form.get('telefono', '').strip()
    correo = request.form.get('correo', '').strip()

    if nombre and telefono:
        conexion = conectar()
        if conexion:
            try:
                cursor = conexion.cursor()
                cursor.execute(
                    "INSERT INTO contactos (nombre, telefono, correo) VALUES (%s, %s, %s)",
                    (nombre, telefono, correo)
                )
                conexion.commit()
            finally:
                conexion.close()
    return redirect(url_for('inicio'))

# ===== ELIMINAR =====
@app.route('/eliminar/<int:indice>')
def eliminar(indice):
    if 'usuario' not in session:
        return redirect(url_for('login'))
    
    contactos = cargar_contactos()
    if 0 <= indice < len(contactos):
        contacto_id = contactos[indice][1]['id']
        conexion = conectar()
        if conexion:
            try:
                cursor = conexion.cursor()
                cursor.execute("DELETE FROM contactos WHERE id = %s", (contacto_id,))
                conexion.commit()
            finally:
                conexion.close()
    return redirect(url_for('inicio'))

# ===== EDITAR =====
@app.route('/editar/<int:indice>', methods=['POST'])
def editar(indice):
    if 'usuario' not in session:
        return redirect(url_for('login'))
    
    contactos = cargar_contactos()
    if 0 <= indice < len(contactos):
        contacto_id = contactos[indice][1]['id']
        nombre = request.form.get('nombre', '').strip()
        telefono = request.form.get('telefono', '').strip()
        correo = request.form.get('correo', '').strip()
        
        if nombre and telefono:
            conexion = conectar()
            if conexion:
                try:
                    cursor = conexion.cursor()
                    cursor.execute(
                        "UPDATE contactos SET nombre = %s, telefono = %s, correo = %s WHERE id = %s",
                        (nombre, telefono, correo, contacto_id)
                    )
                    conexion.commit()
                finally:
                    conexion.close()
    return redirect(url_for('inicio'))

# ===== BUSCAR =====
@app.route('/buscar', methods=['POST'])
def buscar():
    if 'usuario' not in session:
        return redirect(url_for('login'))
    
    texto = request.form.get('buscar', '').strip()
    conexion = conectar()
    if not conexion:
        return render_template('resultados.html', contactos=[], busqueda=texto)
    
    try:
        cursor = conexion.cursor(dictionary=True)
        if texto:
            cursor.execute(
                """SELECT * FROM contactos 
                   WHERE nombre LIKE %s OR telefono LIKE %s OR correo LIKE %s
                   ORDER BY nombre ASC""",
                (f"%{texto}%", f"%{texto}%", f"%{texto}%")
            )
        else:
            cursor.execute("SELECT * FROM contactos ORDER BY nombre ASC")
        
        resultados = list(enumerate(cursor.fetchall()))
        return render_template('resultados.html', contactos=resultados, busqueda=texto)
    finally:
        conexion.close()

if __name__ == '__main__':
    app.run(debug=True, port=5000)