from flask import Flask, render_template, request, redirect, url_for, session, jsonify
import mysql.connector
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = "clave_secreta_agenda_isaac_2026"
app.static_folder = 'static'
app.permanent_session_lifetime = timedelta(minutes=30)

# ===== CONFIGURACIÓN =====
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "root",
    "database": "agenda_isaac"
}

# ===== CONEXIÓN =====
def get_db():
    try:
        return mysql.connector.connect(**DB_CONFIG)
    except mysql.connector.Error as error:
        print(f"❌ Error de conexión: {error}")
        return None

# ===== INICIO DE SESIÓN =====
@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'usuario' in session:
        return redirect(url_for('inicio'))
    
    mensaje = ""
    if request.method == 'POST':
        usuario = request.form.get('usuario', '').strip()
        contrasena = request.form.get('contrasena', '').strip()
        
        db = get_db()
        if db:
            try:
                cursor = db.cursor(dictionary=True)
                cursor.execute(
                    "SELECT * FROM usuarios WHERE usuario = %s AND contrasena = %s",
                    (usuario, contrasena)
                )
                usuario_encontrado = cursor.fetchone()
                
                if usuario_encontrado:
                    session.permanent = True
                    session['usuario'] = usuario_encontrado['usuario']
                    session['nombre'] = usuario_encontrado.get('nombre_completo', usuario_encontrado['usuario'])
                    return redirect(url_for('inicio'))
                else:
                    mensaje = "⚠️ Usuario o contraseña incorrectos"
            finally:
                db.close()
        else:
            mensaje = "❌ No se pudo conectar a la base de datos"
    
    return render_template('login.html', mensaje=mensaje)

# ===== TABLERO / INICIO =====
@app.route('/inicio')
def inicio():
    if 'usuario' not in session:
        return redirect(url_for('login'))
    
    db = get_db()
    if not db:
        return "Error de conexión a la base de datos"
    
    cursor = db.cursor(dictionary=True)
    
    cursor.execute("SELECT COUNT(*) AS total FROM contactos WHERE estado = 1")
    total_contactos = cursor.fetchone()['total']
    
    cursor.execute("SELECT COUNT(*) AS total FROM recordatorios WHERE estado = 'Pendiente'")
    total_recordatorios = cursor.fetchone()['total']
    
    cursor.execute("SELECT * FROM recordatorios WHERE estado = 'Pendiente' ORDER BY fecha ASC LIMIT 3")
    proximos = cursor.fetchall()
    
    cursor.close()
    db.close()
    
    return render_template('inicio.html',
        total_contactos=total_contactos,
        total_recordatorios=total_recordatorios,
        proximos=proximos
    )

# ===== LISTA DE CONTACTOS =====
@app.route('/contactos')
def contactos():
    if 'usuario' not in session:
        return redirect(url_for('login'))
    
    db = get_db()
    if not db:
        return "Error de conexión"
    
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT * FROM contactos WHERE estado = 1 ORDER BY nombre ASC")
    lista = cursor.fetchall()
    cursor.close()
    db.close()
    
    return render_template('contactos.html', contactos=lista, usuario=session['usuario'])

# ===== BUSCAR CONTACTOS =====
@app.route('/buscar', methods=['POST'])
def buscar():
    if 'usuario' not in session:
        return redirect(url_for('login'))
    
    texto = request.form.get('buscar', '').strip()
    db = get_db()
    if not db:
        return "Error de conexión"
    
    cursor = db.cursor(dictionary=True)
    busqueda = f"%{texto}%"
    cursor.execute("""
        SELECT * FROM contactos 
        WHERE estado = 1
          AND (nombre LIKE %s OR telefono LIKE %s OR correo LIKE %s)
        ORDER BY nombre ASC
    """, (busqueda, busqueda, busqueda))
    
    lista = cursor.fetchall()
    cursor.close()
    db.close()
    
    return render_template('contactos.html', contactos=lista, usuario=session['usuario'])

# ===== BUSCAR EN VIVO =====
@app.route('/buscar_en_vivo', methods=['POST'])
def buscar_en_vivo():
    if 'usuario' not in session:
        return ""
    
    texto = request.form.get('buscar', '').strip()
    db = get_db()
    if not db:
        return "<p class='vacio'>Error de conexión</p>"
    
    cursor = db.cursor(dictionary=True)
    busqueda = f"%{texto}%"
    cursor.execute("""
        SELECT * FROM contactos 
        WHERE estado = 1
          AND (nombre LIKE %s OR telefono LIKE %s OR correo LIKE %s)
        ORDER BY nombre ASC
    """, (busqueda, busqueda, busqueda))
    
    lista = cursor.fetchall()
    cursor.close()
    db.close()
    
    if lista:
        html = ""
        for c in lista:
            fecha_alta = c['fecha_alta'].strftime('%d/%m/%Y %H:%M') if c['fecha_alta'] else '—'
            fecha_mod = c['fecha_modificacion'].strftime('%d/%m/%Y %H:%M') if c['fecha_modificacion'] else '—'
            html += f'''
            <div class="contacto">
                <div class="contacto-izquierda">
                    <div class="contacto-nombre">{c['nombre']}</div>
                    <div class="contacto-datos">
                        📞 {c['telefono']}
                        {f" | ✉️ {c['correo']}" if c['correo'] else ""}
                        <br><small style="color:#94a3b8; font-size:0.85rem;">
                            📅 Alta: {fecha_alta} · Últ. modif: {fecha_mod}
                        </small>
                    </div>
                </div>
                <div class="contacto-acciones">
                    <button class="btn-editar" 
                            onclick="abrirModalEditar({c['id']}, 
                                '{c['nombre']}', 
                                '{c['telefono']}', 
                                '{c['correo'] or ''}')">✏️ Editar</button>
                    <a href="/eliminar/{c['id']}" onclick="return confirm('¿Eliminar? Se marcará como inactivo ✅')">
                        <button class="btn-borrar">🗑️ Eliminar</button>
                    </a>
                </div>
            </div>
            '''
        return html
    else:
        return "<p class='vacio'>No se encontraron contactos</p>"

# ===== AGREGAR CONTACTO =====
@app.route('/agregar', methods=['POST'])
def agregar():
    if 'usuario' not in session:
        return redirect(url_for('login'))
    
    nombre = request.form.get('nombre', '')
    telefono = request.form.get('telefono', '')
    correo = request.form.get('correo', '')
    
    db = get_db()
    if not db:
        return "Error de conexión"
    
    cursor = db.cursor()
    cursor.execute(
        "INSERT INTO contactos (nombre, telefono, correo, estado) VALUES (%s, %s, %s, 1)",
        (nombre, telefono, correo)
    )
    db.commit()
    cursor.close()
    db.close()
    
    return redirect(url_for('contactos'))

# ===== EDITAR CONTACTO =====
@app.route('/editar/<int:id>', methods=['POST'])
def editar(id):
    if 'usuario' not in session:
        return redirect(url_for('login'))
    
    nombre = request.form.get('nombre', '')
    telefono = request.form.get('telefono', '')
    correo = request.form.get('correo', '')
    
    db = get_db()
    if not db:
        return "Error de conexión"
    
    cursor = db.cursor()
    cursor.execute(
        "UPDATE contactos SET nombre=%s, telefono=%s, correo=%s WHERE id=%s",
        (nombre, telefono, correo, id)
    )
    db.commit()
    cursor.close()
    db.close()
    
    return redirect(url_for('contactos'))

# ===== ELIMINAR = MARCAR COMO INACTIVO =====
@app.route('/eliminar/<int:id>')
def eliminar(id):
    if 'usuario' not in session:
        return redirect(url_for('login'))
    
    db = get_db()
    if not db:
        return "Error de conexión"
    
    cursor = db.cursor()
    cursor.execute("UPDATE contactos SET estado = 0 WHERE id = %s", (id,))
    db.commit()
    cursor.close()
    db.close()
    
    return redirect(url_for('contactos'))

# ===== CERRAR SESIÓN =====
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
def raiz():
    return redirect(url_for('login'))

# ===== CALENDARIO — Navegable =====
@app.route('/calendario')
def calendario():
    if 'usuario' not in session:
        return redirect(url_for('login'))
    
    hoy = datetime.now()
    anio = request.args.get('anio', hoy.year, type=int)
    mes = request.args.get('mes', hoy.month, type=int)
    
    nombres_mes = [
        'Enero', 'Febrero', 'Marzo', 'Abril', 'Mayo', 'Junio',
        'Julio', 'Agosto', 'Septiembre', 'Octubre', 'Noviembre', 'Diciembre'
    ]
    
    # Mes anterior y siguiente
    if mes == 1:
        mes_anterior, anio_anterior = 12, anio - 1
    else:
        mes_anterior, anio_anterior = mes - 1, anio
    
    if mes == 12:
        mes_siguiente, anio_siguiente = 1, anio + 1
    else:
        mes_siguiente, anio_siguiente = mes + 1, anio
    
    # Calcular primer y último día del mes — MÉTODO SEGURO ✅
    primer_dia = datetime(anio, mes, 1)
    if mes == 12:
        primer_dia_siguiente = datetime(anio + 1, 1, 1)
    else:
        primer_dia_siguiente = datetime(anio, mes + 1, 1)
    
    ultimo_dia = primer_dia_siguiente - timedelta(days=1)
    
    # Día de inicio de la semana (0=Domingo)
    dia_inicio = primer_dia.weekday()
    dia_inicio = (dia_inicio + 1) % 7
    total_dias = ultimo_dia.day
    
    # Contar eventos por día
    db = get_db()
    conteo = {}
    if db:
        cursor = db.cursor(dictionary=True)
        cursor.execute("""
            SELECT fecha, COUNT(*) AS total 
            FROM eventos 
            WHERE YEAR(fecha)=%s AND MONTH(fecha)=%s AND estado=1
            GROUP BY fecha
        """, (anio, mes))
        for fila in cursor:
            conteo[str(fila['fecha'])] = fila['total']
        cursor.close()
        db.close()
    
    # Armar casillas — Formateo de fecha corregido ✅
    casillas = []
    for _ in range(dia_inicio):
        casillas.append({'vacio': True})
    
    for d in range(1, total_dias + 1):
        mes_str = f"{mes:02d}"
        dia_str = f"{d:02d}"
        fecha_str = f"{anio}-{mes_str}-{dia_str}"
        es_hoy = (hoy.year == anio and hoy.month == mes and hoy.day == d)
        
        casillas.append({
            'vacio': False,
            'dia': d,
            'fecha': fecha_str,
            'cantidad': conteo.get(fecha_str, 0),
            'es_hoy': es_hoy
        })
    
    return render_template('calendario.html',
        anio=anio, mes=mes,
        nombres_mes=nombres_mes,
        mes_anterior=mes_anterior, anio_anterior=anio_anterior,
        mes_siguiente=mes_siguiente, anio_siguiente=anio_siguiente,
        casillas=casillas,
        usuario=session['usuario']
    )

# ===== Obtener eventos de un mes =====
@app.route('/eventos_mes/<int:anio>/<int:mes>')
def eventos_mes(anio, mes):
    if 'usuario' not in session:
        return jsonify({})
    
    db = get_db()
    if not db:
        return jsonify({})
    
    cursor = db.cursor(dictionary=True)
    cursor.execute("""
        SELECT fecha, COUNT(*) AS total 
        FROM eventos 
        WHERE YEAR(fecha) = %s AND MONTH(fecha) = %s AND estado = 1
        GROUP BY fecha
    """, (anio, mes))
    
    conteo = {}
    for fila in cursor.fetchall():
        conteo[str(fila['fecha'])] = fila['total']
    
    cursor.close()
    db.close()
    
    return jsonify(conteo)

# ===== Ver eventos de un día =====
@app.route('/eventos_dia/<fecha>')
def eventos_dia(fecha):
    if 'usuario' not in session:
        return redirect(url_for('login'))
    
    db = get_db()
    if not db:
        return "Error de conexión"
    
    cursor = db.cursor(dictionary=True)
    cursor.execute("""
        SELECT * FROM eventos 
        WHERE fecha = %s AND estado = 1
        ORDER BY hora ASC
    """, (fecha,))
    
    lista = cursor.fetchall()
    cursor.close()
    db.close()
    
    return render_template('eventos_dia.html', eventos=lista, fecha=fecha)

# ===== Agregar evento =====
@app.route('/agregar_evento', methods=['POST'])
def agregar_evento():
    if 'usuario' not in session:
        return redirect(url_for('login'))
    
    titulo = request.form.get('titulo', '')
    descripcion = request.form.get('descripcion', '')
    fecha = request.form.get('fecha', '')
    hora = request.form.get('hora', '')
    
    db = get_db()
    if not db:
        return "Error de conexión"
    
    cursor = db.cursor()
    cursor.execute(
        "INSERT INTO eventos (titulo, descripcion, fecha, hora, estado) VALUES (%s, %s, %s, %s, 1)",
        (titulo, descripcion, fecha, hora)
    )
    db.commit()
    cursor.close()
    db.close()
    
    return redirect(url_for('calendario'))

# ===== Eliminar evento (lógico) =====
@app.route('/eliminar_evento/<int:id>')
def eliminar_evento(id):
    if 'usuario' not in session:
        return redirect(url_for('login'))
    
    db = get_db()
    if not db:
        return "Error de conexión"
    
    cursor = db.cursor()
    cursor.execute("UPDATE eventos SET estado = 0 WHERE id = %s", (id,))
    db.commit()
    cursor.close()
    db.close()
    
    return redirect(url_for('calendario'))

if __name__ == '__main__':
    app.run(debug=True, port=5000)