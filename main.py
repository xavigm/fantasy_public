from flask import Flask, render_template, request, redirect, url_for, flash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from datetime import datetime
import mysql.connector
from mysql.connector import Error
from passlib.hash import sha512_crypt
from functools import wraps

app = Flask(__name__, static_url_path='/static')
app.secret_key = 'your_secret_key_here'

# Inicializa la conexión a la base de datos
db = None
cursor = None

def connect_db():
    global db, cursor
    if db is None or not db.is_connected():
        db = mysql.connector.connect(
            host="MYSQL_HOST",
            port="MYSQL_PORT",
            user="MYSQL_USER",
            password="MYSQL_PASS",
            database="MYSQL_DB"
        )
        cursor = db.cursor()

def reconnect_on_failure(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            connect_db()
            return func(*args, **kwargs)
        except mysql.connector.Error as e:
            print(f"Error: {e}, trying to reconnect...")
            connect_db()  # Intentar reconectar
            return func(*args, **kwargs)
    return wrapper

login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.init_app(app)

class User(UserMixin):
    def __init__(self, id, admin):
        self.id = id
        self.admin = admin

    def get_id(self):
        return str(self.id)

@login_manager.user_loader
@reconnect_on_failure
def load_user(user_id):
    cursor.execute("SELECT id, nombre, password, admin FROM usuarios WHERE id = %s", (user_id,))
    user_data = cursor.fetchone()
    if user_data:
        return User(user_data[0], user_data[3])
    return None

def unauthorized_callback():
    return redirect(url_for('login'))

@reconnect_on_failure
def authenticate_user(username, password):
    cursor.execute("SELECT id, nombre, password, admin FROM usuarios WHERE nombre = %s", (username,))
    user_data = cursor.fetchone()
    if user_data and sha512_crypt.verify(password, user_data[2]):
        return User(user_data[0], user_data[3])
    return None

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.admin:
            return redirect(url_for('pagina_principal'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
@login_required
@reconnect_on_failure
def pagina_principal():
    fechahoy = datetime.now().date()
    cursor.execute("SELECT id, fecha, rival FROM jornadas WHERE fecha > %s ORDER BY fecha ASC LIMIT 1", (fechahoy,))
    jornada_actual_row = cursor.fetchone()

    if jornada_actual_row:
        jornada_actual, fecha_jornada, rival = jornada_actual_row
        fecha_jornada_datetime = datetime.strptime(str(fecha_jornada), '%Y-%m-%d')
        tiempo_restante = fecha_jornada_datetime - datetime.now()
        dias, segundos = tiempo_restante.days, tiempo_restante.seconds
        horas = segundos // 3600
        minutos = (segundos % 3600) // 60
        segundos = segundos % 60
    else:
        jornada_actual, fecha_jornada = None, None
        dias, horas, minutos, segundos = None, None, None, None

    if jornada_actual:
        cursor.execute("""
            SELECT jugadores.nombre, jugadores.imagen
            FROM seleccion
            JOIN jugadores ON seleccion.jugador_id = jugadores.id
            WHERE seleccion.usuario_id = %s AND seleccion.jornada_id = %s
        """, (current_user.id, jornada_actual))
        jugadores_seleccionados = cursor.fetchall()
        mensaje = "Te falta seleccionar {} jugadores para completar la jornada.".format(6 - len(jugadores_seleccionados)) if len(jugadores_seleccionados) < 6 else None
    else:
        jugadores_seleccionados = []
        mensaje = "No se encontró una jornada futura para agregar la selección."

    return render_template('pagina_principal.html', jugadores_seleccionados=jugadores_seleccionados, mensaje=mensaje, rival=rival, jornada_actual=jornada_actual, fecha_jornada=fecha_jornada, dias=dias, horas=horas, minutos=minutos, segundos=segundos)

@app.route('/elegir_jugadores')
@login_required
@reconnect_on_failure
def elegir_jugadores():
    cursor.execute("SELECT nombre, imagen, id FROM jugadores")
    jugadores = cursor.fetchall()
    return render_template('elegir_jugadores.html', jugadores=jugadores)

@app.route('/procesar_seleccion', methods=['POST'])
@login_required
@reconnect_on_failure
def procesar_seleccion():
    if request.method == 'POST':
        jugadores_seleccionados = request.form.getlist('jugadores')

        fechahoy = datetime.now().date()
        cursor.execute("SELECT id FROM jornadas WHERE fecha > %s ORDER BY fecha ASC LIMIT 1", (fechahoy,))
        jornada_actual_row = cursor.fetchone()
        jornada_actual = jornada_actual_row[0] if jornada_actual_row is not None else None

        if jornada_actual:
            cursor.execute("DELETE FROM seleccion WHERE usuario_id = %s AND jornada_id = %s", (current_user.id, jornada_actual))

            for jugador_id in jugadores_seleccionados:
                cursor.execute("INSERT INTO seleccion (usuario_id, jugador_id, jornada_id) VALUES (%s, %s, %s)",
                               (current_user.id, jugador_id, jornada_actual))
            db.commit()
            return redirect(url_for('pagina_principal'))
        else:
            return "No se encontró una jornada futura para agregar la selección."

@app.route('/clasificacion')
@login_required
@reconnect_on_failure
def clasificacion():
    fechahoy = datetime.now().date()
    cursor.execute("SELECT id, fecha FROM jornadas WHERE fecha <= %s", (fechahoy,))
    jornadas_anteriores_rows = cursor.fetchall()
    jornadas_anteriores = [row[0] for row in jornadas_anteriores_rows]
    
    # Obtenemos la clasificación total
    if jornadas_anteriores:
        jornadas_placeholder = ','.join(['%s'] * len(jornadas_anteriores))
        query_total = f"""
            SELECT u.nombre, SUM(p.puntuacion) AS puntuacion_total
            FROM usuarios u
            JOIN seleccion s ON u.id = s.usuario_id
            JOIN puntuaciones p ON s.jugador_id = p.jugador_id AND s.jornada_id = p.jornada_id
            WHERE p.jornada_id IN ({jornadas_placeholder})
            GROUP BY u.id, u.nombre
            ORDER BY puntuacion_total DESC;
        """
        cursor.execute(query_total, tuple(jornadas_anteriores))
        usuarios = cursor.fetchall()
    else:
        usuarios = []

    # Obtenemos las puntuaciones parciales para cada jornada
    parciales = {}
    for jornada_id in jornadas_anteriores:
        query_parcial = """
            SELECT u.nombre, SUM(p.puntuacion) AS puntuacion_jornada
            FROM usuarios u
            JOIN seleccion s ON u.id = s.usuario_id
            JOIN puntuaciones p ON s.jugador_id = p.jugador_id AND s.jornada_id = p.jornada_id
            WHERE p.jornada_id = %s
            GROUP BY u.id, u.nombre
            ORDER BY puntuacion_jornada DESC;
        """
        cursor.execute(query_parcial, (jornada_id,))
        parciales[jornada_id] = cursor.fetchall()

    # Obtenemos las fechas de las jornadas para el selector en el HTML
    jornadas_info = {row[0]: row[1] for row in jornadas_anteriores_rows}

    return render_template('clasificacion.html', usuarios=usuarios, parciales=parciales, jornadas_info=jornadas_info)

@app.route('/historico')
@login_required
@reconnect_on_failure
def historico():
    cursor.execute("SELECT DISTINCT jornada_id FROM puntuaciones")
    jornadas = [row[0] for row in cursor.fetchall()]

    cursor.execute("""
        SELECT j.nombre AS nombre_jugador, j.imagen AS imagen_jugador, p.jornada_id, p.puntuacion, p.mvp,
               CASE WHEN s.usuario_id IS NOT NULL THEN 'seleccionado' ELSE 'todos' END AS seleccion
        FROM puntuaciones p
        JOIN jugadores j ON p.jugador_id = j.id
        LEFT JOIN seleccion s ON p.jugador_id = s.jugador_id AND p.jornada_id = s.jornada_id AND s.usuario_id = %s
    """, (current_user.id,))
    puntuaciones = cursor.fetchall()
    
    return render_template('historico.html', puntuaciones=puntuaciones, jornadas=jornadas)



@app.route('/login', methods=['GET', 'POST'])
@reconnect_on_failure
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = authenticate_user(username, password)
        if user:
            login_user(user)
            return redirect(url_for('pagina_principal'))
        else:
            flash('Credenciales incorrectas. Por favor, inténtelo de nuevo.', 'error')
            return redirect(url_for('login'))
    else:
        return render_template('login.html')


@app.route('/register', methods=['POST'])
@reconnect_on_failure
def register():
    nombre = request.form['nombre']
    password = request.form['password']
    validation_code = request.form['validation_code']

    if validation_code != "FANTASYVILA25":
        flash("Código de validación incorrecto.", "error")
        return redirect(url_for('login'))

    hashed_password = sha512_crypt.hash(password)
    try:
        cursor.execute("INSERT INTO usuarios (nombre, password) VALUES (%s, %s)", (nombre, hashed_password))
        db.commit()
        flash("Usuario registrado con éxito.", "success")
    except pymysql.MySQLError as e:
        flash(f"Error al registrar el usuario: {e}", "error")
        db.rollback()
    
    return redirect(url_for('login'))



@app.route('/admin', methods=['GET', 'POST'])
@login_required
@admin_required
@reconnect_on_failure
def admin():
    if request.method == 'POST':
        if 'jugador_id' in request.form:
            jugador_id = request.form['jugador_id']    
            if jugador_id == "nuevo":
                nombre = request.form['nombre']
                imagen = request.form['imagen']
                cursor.execute("INSERT INTO jugadores (nombre, imagen) VALUES (%s, %s)", (nombre, imagen))
            else:
                jugador_id = request.form['jugador_id']
                nombre = request.form['nombre']
                imagen = request.form['imagen']
                cursor.execute("UPDATE jugadores SET nombre = %s, imagen = %s WHERE id = %s", (nombre, imagen, jugador_id))
        elif 'puntuacion_jornada_id' in request.form:
            jornada_id = request.form['puntuacion_jornada_id']
            mvp_id = request.form.get('mvp')  # Obtener el MVP seleccionado
            for jugador_id in request.form:
                if jugador_id.startswith('puntuacion_') and jugador_id != 'puntuacion_jornada_id':
                    puntuacion = request.form[jugador_id]
                    jugador_id = jugador_id.replace('puntuacion_', '')
                    if jugador_id == mvp_id:
                        cursor.execute("INSERT INTO puntuaciones (jugador_id, jornada_id, puntuacion, mvp) VALUES (%s, %s, %s, %s)", (jugador_id, jornada_id, puntuacion, True))
                    else:
                        cursor.execute("INSERT INTO puntuaciones (jugador_id, jornada_id, puntuacion) VALUES (%s, %s, %s)", (jugador_id, jornada_id, puntuacion))
        elif 'nuevo_usuario' in request.form:
            nombre = request.form['nombre']
            password = sha512_crypt.hash(request.form['password'])
            cursor.execute("INSERT INTO usuarios (nombre, password) VALUES (%s, %s)", (nombre, password))
        elif 'jornada_id' in request.form:
            jornada_id = request.form['jornada_id']
            fecha = request.form['fecha']
            cursor.execute("UPDATE jornadas SET fecha = %s WHERE id = %s", (fecha, jornada_id))
        elif 'nueva_fecha' in request.form:
            fecha = request.form['nueva_fecha']
            cursor.execute("INSERT INTO jornadas (fecha) VALUES (%s)", (fecha,))
        db.commit()
        return redirect(url_for('admin'))

    cursor.execute("SELECT id, nombre, imagen FROM jugadores")
    jugadores = cursor.fetchall()

    cursor.execute("SELECT id, fecha FROM jornadas")
    jornadas = cursor.fetchall()

    return render_template('admin.html', jugadores=jugadores, jornadas=jornadas)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
