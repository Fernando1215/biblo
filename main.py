# main.py
from fastapi import FastAPI, HTTPException, status, Depends
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Dict, Any
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import secrets
import hashlib
import os

# ---------------------------
# Configuración básica
# ---------------------------
security = HTTPBearer()
app = FastAPI(title="Sistema Biblioteca - API RESTful")
class BookCreate(BaseModel):
    titulo: str = Field(..., min_length=1)
    autor: str = Field(..., min_length=1)
    categoria: str = Field(..., min_length=1)
    contenido: str = Field(..., min_length=10)

class BookUpdate(BaseModel):
    titulo: Optional[str] = None
    autor: Optional[str] = None
    categoria: Optional[str] = None
    contenido: Optional[str] = None

class BookOut(BaseModel):
    id: int
    titulo: str
    autor: str
    categoria: str
    contenido: str

class UserCreate(BaseModel):
    nombre: str = Field(..., min_length=1)
    email: EmailStr
    clave: str = Field(..., min_length=6)
    rol: str = "usuario"

class UserOut(BaseModel):
    id: int
    nombre: str
    email: str
    rol: str

class LoginInput(BaseModel):
    email: EmailStr
    clave: str = Field(..., min_length=1)

class ReviewCreate(BaseModel):
    texto: str = Field(..., min_length=1)
    cal: int = Field(..., ge=1, le=5)

class ReviewOut(BaseModel):
    usuario_id: int
    texto: str
    cal: int

# ---------------------------
# 3. Variables Globales y Funciones de ID
# ---------------------------

# IDs autonuméricos
_next_book_id = 6 
_next_user_id = 1 
_next_review_id = 1

def next_book_id() -> int:
    global _next_book_id
    val = _next_book_id
    _next_book_id += 1
    return val

def next_user_id() -> int:
    global _next_user_id
    val = _next_user_id
    _next_user_id += 1
    return val

# Almacenamiento principal de la aplicación
STORES: Dict[str, Any] = {
    "books": [],
    "users": [],
    "reviews": {},  # key: book_id (str o int) -> list of reviews
    "tokens": {},   # token (str) -> user_id (int)
}

# Datos iniciales para cargar la lista de libros
initial_books = [
    {"titulo": "Cien Años de Soledad", "autor": "Gabriel García Márquez", "categoria": "Novela", "contenido": "Muchos años después, frente al pelotón de fusilamiento, el coronel Aureliano Buendía había de recordar aquella tarde remota en que su padre lo llevó a conocer el hielo. Macondo era entonces una aldea de veinte casas de barro y cañabrava construidas a la orilla de un río de aguas diáfanas que se precipitaban por un lecho de piedras pulidas, blancas y enormes como huevos prehistóricos."},
    {"titulo": "El libro troll", "autor": "el rubius", "categoria": "Historico", "contenido": "En un mundo de luz y caos, la historia comenzó con un simple '¡Hola!' y una explosión de creatividad descontrolada. Este libro es un viaje a través de los memes y las aventuras más épicas de la vida virtual."},
    {"titulo": "1984", "autor": "George Orwell", "categoria": "Distopía", "contenido": "Era un día frío y luminoso de abril, y los relojes daban las trece. Winston Smith, con la barbilla metida en el pecho para escapar al viento desagradable, se deslizó rápidamente por las puertas de cristal de la Mansión de la Victoria, aunque no lo suficientemente rápido para evitar que una bocanada de polvo arenoso entrara con él."},
    {"titulo": "Don Quijote de la Mancha", "autor": "Miguel de Cervantes", "categoria": "Clásico", "contenido": "En un lugar de la Mancha, de cuyo nombre no quiero acordarme, no ha mucho tiempo que vivía un hidalgo de los de lanza en astillero, adarga antigua, rocín flaco y galgo corredor. Una olla de algo más vaca que carnero, salpicón las más noches, duelos y quebrantos los sábados, lantejas los viernes, algún palomino de añadidura los domingos, consumían las tres partes de su hacienda."},
    {"titulo": "La Odisea", "autor": "Homero", "categoria": "Épica", "contenido": "Háblame, Musa, de aquel varón de multiformes ingenios que, tras destruir la sagrada ciudad de Troya, anduvo peregrinando larguísimo tiempo. Vio las ciudades y conoció el espíritu de muchos hombres y padeció en el mar muchísimas fatigas en su ánimo, por asegurar su vida y la vuelta de sus compañeros."},
]

# Inicializar los libros
for i, b in enumerate(initial_books, start=1):
    STORES["books"].append({
        "id": i,
        "titulo": b["titulo"],
        "autor": b["autor"],
        "categoria": b["categoria"],
        "contenido": b["contenido"],
    })

# Asegurar que el next_book_id esté actualizado después de la carga inicial
if len(STORES["books"]) >= _next_book_id:
    _next_book_id = len(STORES["books"]) + 1

# ---------------------------
# 4. Clases del Patrón Observer y Fachada (Facade)
# ---------------------------

class EventSubject:
    def __init__(self):
        self._observers: List[Any] = []

    def subscribe(self, observer: Any):
        self._observers.append(observer)

    def notify(self, event: str, data: Dict[str, Any]):
        for obs in self._observers:
            try:
                obs.update(event, data)
            except Exception as e:
                print(f"[EventSubject] Error notificando observer: {e}")

class ObserverBase:
    def update(self, event: str, data: Dict[str, Any]):
        raise NotImplementedError

class LogObserver(ObserverBase):
    def update(self, event: str, data: Dict[str, Any]):
        print(f"[LOG] Evento: {event} -> {data}")

class EmailObserver(ObserverBase):
    def update(self, event: str, data: Dict[str, Any]):
        print(f"[EMAIL] Notificación ({event}) enviada con payload: {data}")

# Instancia global de eventos y observers
event_subject = EventSubject()
event_subject.subscribe(LogObserver())
event_subject.subscribe(EmailObserver())

# Facade: simplifica operaciones sobre la "BD"
class LibraryFacade:
    def __init__(self, store: Dict[str, Any], events: EventSubject):
        self.store = store
        self.events = events

    # Libros
    def add_book(self, titulo: str, autor: str, categoria: str, contenido: str) -> Dict[str, Any]:
        book = {
            "id": next_book_id(),
            "titulo": titulo,
            "autor": autor,
            "categoria": categoria,
            "contenido": contenido
        }
        self.store["books"].append(book)
        self.events.notify("LIBRO_CREADO", book)
        return book

    def update_book(self, libro_id: int, changes: Dict[str, Optional[str]]) -> Optional[Dict[str, Any]]:
        for b in self.store["books"]:
            if b["id"] == libro_id:
                if changes.get("titulo") is not None:
                    b["titulo"] = changes["titulo"]
                if changes.get("autor") is not None:
                    b["autor"] = changes["autor"]
                if changes.get("categoria") is not None:
                    b["categoria"] = changes["categoria"]
                if changes.get("contenido") is not None:
                    b["contenido"] = changes["contenido"]
                self.events.notify("LIBRO_ACTUALIZADO", b)
                return b
        return None

    def delete_book(self, libro_id: int) -> bool:
        for i, b in enumerate(self.store["books"]):
            if b["id"] == libro_id:
                removed = self.store["books"].pop(i)
                self.store["reviews"].pop(str(libro_id), None)
                self.events.notify("LIBRO_ELIMINADO", removed)
                return True
        return False

    def get_book(self, libro_id: int) -> Optional[Dict[str, Any]]:
        return next((b for b in self.store["books"] if b["id"] == libro_id), None)

    def list_books(self, categoria: Optional[str] = None, search: Optional[str] = None) -> List[Dict[str, Any]]:
        items = self.store["books"].copy()
        if categoria:
            items = [b for b in items if b["categoria"].lower() == categoria.lower()]
        if search:
            q = search.lower()
            items = [b for b in items if q in b["titulo"].lower() or q in b["autor"].lower()]
        return items

    # Reseñas
    def add_review(self, libro_id: int, usuario_id: int, texto: str, cal: int) -> Dict[str, Any]:
        key = str(libro_id)
        rec = {"usuario_id": usuario_id, "texto": texto, "cal": cal}
        self.store["reviews"].setdefault(key, []).append(rec)
        self.events.notify("RESEÑA_AGREGADA", {"libro_id": libro_id, **rec})
        return rec

    # Usuarios
    def register_user(self, nombre: str, email: str, password_hash: str, rol: str = "usuario") -> Dict[str, Any]:
        user = {
            "id": next_user_id(),
            "nombre": nombre,
            "email": email,
            "password_hash": password_hash,
            "rol": rol,
            "biblioteca": []
        }
        self.store["users"].append(user)
        self.events.notify("USUARIO_REGISTRADO", {"id": user["id"], "email": user["email"], "rol": user["rol"]})
        return user

    def authenticate(self, email: str, clave_plain: str) -> Optional[Dict[str, Any]]:
        user = next((u for u in self.store["users"] if u["email"].lower() == email.lower()), None)
        if not user:
            return None
        # Comprobar la contraseña usando la función de hash
        if user.get("password_hash") != _hash_password(clave_plain):
            return None
        return user

# Instancia de la fachada
facade = LibraryFacade(STORES, event_subject)

# ---------------------------
# 5. Utilidades de seguridad y Auth (Las DEFINICIONES deben ir ANTES de ser usadas)
# ---------------------------

def _hash_password(clave: str) -> str:
    """Función para hashear la contraseña usando SHA256."""
    return hashlib.sha256(clave.encode("utf-8")).hexdigest()

def _get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    """Busca un usuario por email en el STORE."""
    return next((u for u in STORES["users"] if u["email"].lower() == email.lower()), None)

# ⭐️ La función que te faltaba definida ANTES de ser llamada ⭐️
def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Dependencia para obtener el usuario autenticado a partir del token Bearer."""
    if not credentials:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authorization header required")
    token = credentials.credentials
    user_id = STORES["tokens"].get(token)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido o expirado")
    user = next((u for u in STORES["users"] if u["id"] == user_id), None)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Usuario no encontrado")
    return user

def admin_required(user: dict):
    """Dependencia para verificar si el usuario es administrador."""
    if user.get("rol") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo administradores pueden realizar esta acción")
    
# Creación de usuario administrador por defecto
admin_default = {
    "id": next_user_id(),
    "nombre": "Administrador",
    "email": "admin@biblioteca.com",
    "password_hash": _hash_password("admin123"),
    "rol": "admin",
    "biblioteca": []
}

STORES["users"].append(admin_default)
print("🟢 Usuario administrador creado por defecto -> admin@biblioteca.com / admin123")
# ---------------------------
# HTML frontend (mantuve tu versión + llamadas a /api/v1 y nuevos campos)
# ---------------------------
HTML_PAGE = """<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Biblioteca Personal</title>
  <style>
    body {
      font-family: 'Arial', sans-serif;
      background-color: #f5f1e9;
      margin: 0;
      padding: 0;
      display: flex;
      justify-content: center;
      min-height: 100vh;
      padding-top: 30px;
    }
    .container {
      background: #fffdfa;
      max-width: 700px;
      width: 90%;
      padding: 25px 35px;
      border-radius: 12px;
      box-shadow: 0 8px 15px rgba(0,0,0,0.1);
    }
    h1, h2, h3 { color: #3a4d24; }
    input, textarea, button {
      width: 100%;
      padding: 12px;
      margin: 10px 0;
      border-radius: 8px;
      border: 2px solid #9caf88;
      font-size: 16px;
      box-sizing: border-box;
    }
    button {
      background-color: #4caf50;
      color: white;
      border: none;
      cursor: pointer;
      font-weight: bold;
    }
    button:hover { background-color: #388e3c; }
    #panelUsuario, #detalleLibro, #registro { display: none; margin-top: 20px; }
    .libro-item {
      padding: 15px;
      margin: 8px 0;
      background-color: #e7ebd1;
      border: 2px solid #b6c78a;
      border-radius: 8px;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .libro-item:hover { background-color: #d4dbb4; }
    .btn-small {
      width: auto;
      padding: 7px 12px;
      margin-left: 5px;
      font-size: 14px;
    }
    #cerrarSesion {
      background-color: #a44c4c;
      max-width: 150px;
      margin: 20px auto;
      display: none;
    }
  </style>
</head>
<body>
  <div class="container">
    <h1>📚 Biblioteca Personal</h1>

    <div id="login">
      <h2>Iniciar Sesión</h2>
      <input type="email" id="loginEmail" placeholder="Email" />
      <input type="password" id="loginClave" placeholder="Contraseña" />
      <button onclick="login()">Ingresar</button>
      <button onclick="mostrarRegistro()">Registrar Usuario</button>
    </div>

    <div id="registro">
      <h2>Registrar Usuario</h2>
      <input type="text" id="regNombre" placeholder="Nombre" />
      <input type="email" id="regEmail" placeholder="Email" />
      <input type="password" id="regClave" placeholder="Contraseña (mín. 6 caracteres)" />
      <button onclick="registrarUsuario()">Registrar</button>
      <button onclick="volverLogin()">Volver</button>
    </div>

    <div id="panelUsuario">
      <h2>Catálogo Global</h2>
      <div id="catalogoGlobal"></div>

      <h2>Mi Biblioteca</h2>
      <div id="miBiblioteca"></div>

      <h2>Agregar Nuevo Libro</h2>
      <input type="text" id="nuevoTitulo" placeholder="Título" />
      <input type="text" id="nuevoAutor" placeholder="Autor" />
      <input type="text" id="nuevaCategoria" placeholder="Categoría" />
            <textarea id="nuevoContenido" placeholder="Contenido del libro (mín. 10 caracteres)"></textarea>
      <button onclick="agregarLibro()">Agregar Libro</button>
    </div>

    <div id="detalleLibro">
      <h3 id="tituloDetalle"></h3>
      <p id="autorDetalle"></p>
      <p id="categoriaDetalle"></p>
      
            <h4>Contenido:</h4>
      <div id="contenidoDetalle" style="border: 1px solid #ccc; padding: 10px; margin-bottom: 20px; max-height: 200px; overflow-y: auto; background-color: #f9f9f9; white-space: pre-wrap;"></div>
      
      <textarea id="reseñaTexto" placeholder="Escribe tu reseña..."></textarea>
      <input type="number" id="calificacion" min="1" max="5" placeholder="Calificación (1-5)" />
      <button onclick="guardarReseña()">Guardar Reseña</button>
      <h4>Reseñas:</h4>
      <ul id="listaReseñas"></ul>
      <button onclick="cerrarDetalle()">Cerrar</button>
    </div>

    <button id="cerrarSesion" onclick="logout()">Cerrar Sesión</button>
  </div>

  <script>
    let token = null;
    let userRole = null;  // ← Guardamos el rol del usuario
    let libroSeleccionado = null;
    let misBibliotecaIds = [];

    const API = '/api/v1';

    async function request(url, options = {}) {
      if (token && !options.headers) {
        options.headers = {};
      }
      if (token) {
        options.headers['Authorization'] = `Bearer ${token}`;
      }
      options.headers = options.headers || {};
      options.headers['Content-Type'] = 'application/json';
      
      const res = await fetch(url, options);
      if (!res.ok) {
        const error = await res.json().catch(() => ({detail: 'Error desconocido'}));
        throw new Error(error.detail || 'Error en la petición');
      }
      return res.status === 204 ? null : res.json();
    }

    async function login() {
      const email = document.getElementById('loginEmail').value.trim();
      const clave = document.getElementById('loginClave').value;
      
      try {
        const data = await request(`${API}/auth/login`, {
          method: 'POST',
          body: JSON.stringify({email, clave})
        });
        
        token = data.token;
        userRole = data.rol;  // ← Guardamos el rol
        
        document.getElementById('login').style.display = 'none';
        document.getElementById('panelUsuario').style.display = 'block';
        document.getElementById('cerrarSesion').style.display = 'block';
        
        // Mostrar u ocultar sección de agregar libros según el rol
        // 🆕 Añadir #nuevoContenido
        const adminElements = document.querySelectorAll('#panelUsuario > h2:nth-of-type(3), #nuevoTitulo, #nuevoAutor, #nuevaCategoria, #nuevoContenido, #panelUsuario > button:last-of-type');
        if (userRole === 'admin') {
          adminElements.forEach(el => el.style.display = 'block');
          alert('✅ Bienvenido Administrador');
        } else {
          // Ocultar formulario de agregar libros para usuarios normales
          adminElements.forEach(el => {
            el.style.display = 'none';
          });
          alert('✅ Bienvenido Usuario');
        }
        
        await cargarCatalogo();
        await cargarMiBiblioteca();
      } catch (err) {
        alert('Error al iniciar sesión: ' + err.message);
      }
    }

    function mostrarRegistro() {
      document.getElementById('login').style.display = 'none';
      document.getElementById('registro').style.display = 'block';
    }

    function volverLogin() {
      document.getElementById('registro').style.display = 'none';
      document.getElementById('login').style.display = 'block';
    }

    async function registrarUsuario() {
      const nombre = document.getElementById('regNombre').value.trim();
      const email = document.getElementById('regEmail').value.trim();
      const clave = document.getElementById('regClave').value;
      
      try {
        await request(`${API}/usuarios`, {
          method: 'POST',
          body: JSON.stringify({nombre, email, clave, rol: 'usuario'})
        });
        
        alert('Usuario registrado exitosamente');
        volverLogin();
      } catch (err) {
        alert('Error al registrar: ' + err.message);
      }
    }

    function logout() {
      token = null;
      userRole = null;  // ← Limpiar rol
      document.getElementById('login').style.display = 'block';
      document.getElementById('panelUsuario').style.display = 'none';
      document.getElementById('cerrarSesion').style.display = 'none';
      document.getElementById('loginEmail').value = '';
      document.getElementById('loginClave').value = '';
      
      // Mostrar de nuevo el formulario de agregar libros (para próximo login)
      // 🆕 Añadir #nuevoContenido
      document.querySelectorAll('#panelUsuario > h2:nth-of-type(3), #nuevoTitulo, #nuevoAutor, #nuevaCategoria, #nuevoContenido, #panelUsuario > button:last-of-type').forEach(el => {
        el.style.display = 'block';
      });
    }

    async function cargarCatalogo() {
      try {
        const libros = await request(`${API}/libros`);
        const cont = document.getElementById('catalogoGlobal');
        cont.innerHTML = '';
        
        libros.forEach(libro => {
          const div = document.createElement('div');
          div.className = 'libro-item';
          
          // Botones según el rol del usuario
          let botonesHTML = `
            <button class="btn-small" onclick="agregarAMiBiblioteca(${libro.id})">Agregar</button>
            <button class="btn-small" onclick="verDetalle(${libro.id})">Ver</button>
          `;
          
          // Solo admin puede editar y eliminar
          if (userRole === 'admin') {
            botonesHTML += `
              <button class="btn-small" onclick="editarLibro(${libro.id})" style="background-color: #ff9800;">Editar</button>
              <button class="btn-small" onclick="eliminarLibro(${libro.id})" style="background-color: #f44336;">Eliminar</button>
            `;
          }
          
          div.innerHTML = `
            <div><strong>${libro.titulo}</strong> - ${libro.autor} (${libro.categoria})</div>
            <div>${botonesHTML}</div>
          `;
          cont.appendChild(div);
        });
      } catch (err) {
        alert('Error al cargar catálogo: ' + err.message);
      }
    }

    async function cargarMiBiblioteca() {
      try {
        const libros = await request(`${API}/usuarios/me/biblioteca`);
        const cont = document.getElementById('miBiblioteca');
        cont.innerHTML = '';
        
        if (libros.length === 0) {
          cont.innerHTML = '<p style="text-align: center; color: #999; padding: 20px;">📚 Tu biblioteca está vacía. Agrega libros desde el catálogo global.</p>';
          return;
        }
        
        libros.forEach(libro => {
          const div = document.createElement('div');
          div.className = 'libro-item';
          div.innerHTML = `
            <div><strong>${libro.titulo}</strong> - ${libro.autor} (${libro.categoria})</div>
            <div>
              <button class="btn-small" onclick="verDetalle(${libro.id})">Ver detalle</button>
              <button class="btn-small" onclick="quitarDeMiBiblioteca(${libro.id})" style="background-color: #f44336;">Quitar</button>
            </div>
          `;
          cont.appendChild(div);
        });
      } catch (err) {
        const cont = document.getElementById('miBiblioteca');
        cont.innerHTML = '<p style="color: #f44336;">Error al cargar tu biblioteca: ' + err.message + '</p>';
      }
    }

    async function agregarLibro() {
      const titulo = document.getElementById('nuevoTitulo').value.trim();
      const autor = document.getElementById('nuevoAutor').value.trim();
      const categoria = document.getElementById('nuevaCategoria').value.trim();
      const contenido = document.getElementById('nuevoContenido').value;  // 🆕 Obtener contenido
      
      if (!titulo || !autor || !categoria || !contenido) {  // 🆕 Validar contenido
        alert('Completa todos los campos');
        return;
      }
      
      try {
        await request(`${API}/libros`, {
          method: 'POST',
          body: JSON.stringify({titulo, autor, categoria, contenido})  // 🆕 Enviar contenido
        });
        
        document.getElementById('nuevoTitulo').value = '';
        document.getElementById('nuevoAutor').value = '';
        document.getElementById('nuevaCategoria').value = '';
        document.getElementById('nuevoContenido').value = '';  // 🆕 Limpiar contenido
        
        await cargarCatalogo();
      } catch (err) {
        if (err.message.includes('Solo administradores')) {
          alert('❌ Solo los administradores pueden crear libros');
        } else {
          alert('Error al agregar libro: ' + err.message);
        }
      }
    }

    async function agregarAMiBiblioteca(libroId) {
      try {
        await request(`${API}/usuarios/me/biblioteca/${libroId}`, {
          method: 'POST'
        });
        alert('Libro agregado a tu biblioteca');
        await cargarMiBiblioteca();
      } catch (err) {
        alert('Error: ' + err.message);
      }
    }
    async function quitarDeMiBiblioteca(libroId) {
      if (!confirm('¿Seguro que deseas quitar este libro de tu biblioteca?')) return;

    try {
      await request(`${API}/usuarios/me/biblioteca/${libroId}`, {
        method: 'DELETE'
     });

     await cargarMiBiblioteca();
    } catch (err) {
      alert('Error al eliminar libro: ' + err.message);
      }
    }

    async function verDetalle(libroId) {
      try {
        const libro = await request(`${API}/libros/${libroId}`);
        const reseñas = await request(`${API}/libros/${libroId}/reseñas`);
        
        libroSeleccionado = libro;
        document.getElementById('tituloDetalle').textContent = libro.titulo;
        document.getElementById('autorDetalle').textContent = 'Autor: ' + libro.autor;
        document.getElementById('categoriaDetalle').textContent = 'Categoría: ' + libro.categoria;
        
        // 🆕 Mostrar el contenido
        document.getElementById('contenidoDetalle').textContent = libro.contenido;

        const lista = document.getElementById('listaReseñas');
        lista.innerHTML = '';
        reseñas.forEach(r => {
          const li = document.createElement('li');
          li.textContent = `Usuario ${r.usuario_id}: "${r.texto}" (⭐${r.cal})`;
          lista.appendChild(li);
        });
        
        document.getElementById('panelUsuario').style.display = 'none';
        document.getElementById('detalleLibro').style.display = 'block';
      } catch (err) {
        alert('Error al cargar detalle: ' + err.message);
      }
    }

    async function guardarReseña() {
      const texto = document.getElementById('reseñaTexto').value.trim();
      const cal = parseInt(document.getElementById('calificacion').value);
      
      if (!texto || !cal || cal < 1 || cal > 5) {
        alert('Completa todos los campos correctamente');
        return;
      }
      
      try {
        await request(`${API}/libros/${libroSeleccionado.id}/reseñas`, {
          method: 'POST',
          body: JSON.stringify({texto, cal})
        });
        
        document.getElementById('reseñaTexto').value = '';
        document.getElementById('calificacion').value = '';
        alert('Reseña guardada ✅');
        await verDetalle(libroSeleccionado.id);
      } catch (err) {
        alert('Error al guardar reseña: ' + err.message);
      }
    }

    function cerrarDetalle() {
      document.getElementById('detalleLibro').style.display = 'none';
      document.getElementById('panelUsuario').style.display = 'block';
    }

    async function editarLibro(libroId) {
      try {
        const libro = await request(`${API}/libros/${libroId}`);
        
        const nuevoTitulo = prompt('Nuevo título:', libro.titulo);
        if (!nuevoTitulo) return;
        
        const nuevoAutor = prompt('Nuevo autor:', libro.autor);
        if (!nuevoAutor) return;
        
        const nuevaCategoria = prompt('Nueva categoría:', libro.categoria);
        if (!nuevaCategoria) return;

        const nuevoContenido = prompt('Nuevo contenido:', libro.contenido);  // 🆕 Prompt para contenido
        if (!nuevoContenido) return;
        
        await request(`${API}/libros/${libroId}`, {
          method: 'PUT',
          body: JSON.stringify({
            titulo: nuevoTitulo,
            autor: nuevoAutor,
            categoria: nuevaCategoria,
            contenido: nuevoContenido  // 🆕 Enviar contenido
          })
        });
        
        alert('✅ Libro actualizado exitosamente');
        await cargarCatalogo();
      } catch (err) {
        alert('Error al editar libro: ' + err.message);
      }
    }

    async function eliminarLibro(libroId) {
      if (!confirm('¿Estás seguro de que deseas eliminar este libro?')) {
        return;
      }
      
      try {
        await request(`${API}/libros/${libroId}`, {
          method: 'DELETE'
        });
        
        alert('✅ Libro eliminado exitosamente');
        await cargarCatalogo();
      } catch (err) {
        alert('Error al eliminar libro: ' + err.message);
      }
    }
  </script>
</body>
</html>
"""
@app.get("/", response_class=HTMLResponse)
def home():
    return HTMLResponse(HTML_PAGE)

# Endpoints de Libros
@app.get("/api/v1/libros", response_model=List[BookOut])
def listar_libros(page: int = 1, limit: int = 20, categoria: Optional[str] = None, search: Optional[str] = None):
    items = facade.list_books(categoria=categoria, search=search)
    start = (page - 1) * limit
    end = start + limit
    return items[start:end]

@app.post("/api/v1/libros", response_model=BookOut, status_code=status.HTTP_201_CREATED)
def crear_libro(data: BookCreate, user=Depends(get_current_user)):
    admin_required(user)
    book = facade.add_book(data.titulo, data.autor, data.categoria, data.contenido)
    return book

@app.get("/api/v1/libros/{libro_id}", response_model=BookOut)
def obtener_libro(libro_id: int):
    book = facade.get_book(libro_id)
    if not book:
        raise HTTPException(status_code=404, detail="Libro no encontrado")
    return book

@app.put("/api/v1/libros/{libro_id}", response_model=BookOut)
def actualizar_libro(libro_id: int, payload: BookUpdate, user=Depends(get_current_user)):
    admin_required(user)
    changes = {
        "titulo": payload.titulo,
        "autor": payload.autor,
        "categoria": payload.categoria,
        "contenido": payload.contenido
    }
    updated = facade.update_book(libro_id, changes)
    if not updated:
        raise HTTPException(status_code=404, detail="Libro no encontrado")
    return updated

@app.delete("/api/v1/libros/{libro_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_libro(libro_id: int, user=Depends(get_current_user)):
    admin_required(user)
    ok = facade.delete_book(libro_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Libro no encontrado")
    return None

# Endpoints de Reseñas
@app.get("/api/v1/libros/{libro_id}/reseñas", response_model=List[ReviewOut])
def listar_reseñas(libro_id: int):
    return STORES["reviews"].get(str(libro_id), [])

@app.post("/api/v1/libros/{libro_id}/reseñas", response_model=ReviewOut, status_code=status.HTTP_201_CREATED)
def crear_reseña(libro_id: int, payload: ReviewCreate, user=Depends(get_current_user)):
    if not facade.get_book(libro_id):
        raise HTTPException(status_code=404, detail="Libro no encontrado")
    rec = facade.add_review(libro_id, user["id"], payload.texto, payload.cal)
    return rec

# Endpoints de Usuarios y Autenticación
@app.post("/api/v1/usuarios", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def registrar_usuario(payload: UserCreate):
    if _get_user_by_email(payload.email):
        raise HTTPException(status_code=409, detail="Email ya registrado")

    user = facade.register_user(
        payload.nombre,
        payload.email.strip().lower(),
        _hash_password(payload.clave),
        payload.rol
    )

    return {
        "id": user["id"],
        "nombre": user["nombre"],
        "email": user["email"],
        "rol": user["rol"]
    }

@app.post("/api/v1/auth/login")
def login(payload: LoginInput):
    user = facade.authenticate(payload.email, payload.clave)
    if not user:
        raise HTTPException(status_code=401, detail="Credenciales inválidas")
    
    token = secrets.token_urlsafe(32)
    STORES["tokens"][token] = user["id"]
    return {"token": token, "rol": user.get("rol", "usuario")}

@app.get("/api/v1/auth/me", response_model=UserOut)
def who_am_i(user=Depends(get_current_user)):
    return {"id": user["id"], "nombre": user["nombre"], "email": user["email"], "rol": user.get("rol", "usuario")}

# Endpoints de Biblioteca Personal
@app.post("/api/v1/usuarios/me/biblioteca/{libro_id}")
def agregar_a_mi_biblioteca(libro_id: int, user=Depends(get_current_user)):
    if not facade.get_book(libro_id):
        raise HTTPException(status_code=404, detail="Libro no encontrado")
    if libro_id in user["biblioteca"]:
        raise HTTPException(status_code=409, detail="Libro ya en biblioteca")
    user["biblioteca"].append(libro_id)
    event_subject.notify("BIBLIOTECA_ACTUALIZADA", {"usuario_id": user["id"], "libro_id": libro_id, "accion": "agregar"})
    return {"message": "Libro agregado a tu biblioteca"}

@app.delete("/api/v1/usuarios/me/biblioteca/{libro_id}")
def quitar_de_mi_biblioteca(libro_id: int, user=Depends(get_current_user)):
    if libro_id not in user["biblioteca"]:
        raise HTTPException(status_code=404, detail="Libro no está en tu biblioteca")
    user["biblioteca"].remove(libro_id)
    event_subject.notify("BIBLIOTECA_ACTUALIZADA", {"usuario_id": user["id"], "libro_id": libro_id, "accion": "quitar"})
    return {"message": "Libro eliminado de tu biblioteca"}

@app.get("/api/v1/usuarios/me/biblioteca", response_model=List[BookOut])
def obtener_mi_biblioteca(user=Depends(get_current_user)):
    libros = [b for b in STORES["books"] if b["id"] in user["biblioteca"]]
    return libros

# ---------------------------
# 7. Bloque de Ejecución (RUN)
# ---------------------------
if __name__ == "__main__":
    import uvicorn
    puerto = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=puerto)
