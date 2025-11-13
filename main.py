# main.py - VERSIÓN CORREGIDA
from fastapi import FastAPI, HTTPException, status, Depends
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, EmailStr 
from typing import List, Optional, Dict, Any
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import secrets
import hashlib
import os

security = HTTPBearer()
app = FastAPI(title="Sistema Biblioteca - API RESTful")

# CORS habilitado
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Contadores globales
_next_book_id = 6  # Empieza en 6 porque ya hay 5 libros iniciales
_next_user_id = 1

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

# Base de datos en memoria
STORES = {
    "books": [],
    "users": [],
    "reviews": {},
    "tokens": {},
}

# Libros iniciales
initial_books = [
    {"titulo": "Cien Años de Soledad", "autor": "Gabriel García Márquez", "categoria": "Novela"},
    {"titulo": "El libro troll", "autor": "el rubius", "categoria": "Historico"},
    {"titulo": "1984", "autor": "George Orwell", "categoria": "Distopía"},
    {"titulo": "Don Quijote de la Mancha", "autor": "Miguel de Cervantes", "categoria": "Clásico"},
    {"titulo": "La Odisea", "autor": "Homero", "categoria": "Épica"},
]

for b in initial_books:
    book = {
        "id": next_book_id() - 5 + len(STORES["books"]),
        "titulo": b["titulo"],
        "autor": b["autor"],
        "categoria": b["categoria"],
    }
    STORES["books"].append(book)

# Schemas
class BookCreate(BaseModel):
    titulo: str = Field(..., min_length=1)
    autor: str = Field(..., min_length=1)
    categoria: str = Field(..., min_length=1)

class BookUpdate(BaseModel):
    titulo: Optional[str] = None
    autor: Optional[str] = None
    categoria: Optional[str] = None

class BookOut(BaseModel):
    id: int
    titulo: str
    autor: str
    categoria: str

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

# Utilidades
def _hash_password(clave: str) -> str:
    return hashlib.sha256(clave.encode("utf-8")).hexdigest()

def _get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    for u in STORES["users"]:
        if u["email"].lower() == email.lower():
            return u
    return None

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    user_id = STORES["tokens"].get(token)
    
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado"
        )
    
    user = next((u for u in STORES["users"] if u["id"] == user_id), None)
    if not user:
        raise HTTPException(status_code=401, detail="Usuario no encontrado")
    
    return user

def admin_required(user: dict):
    if user.get("rol") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Solo administradores pueden realizar esta acción"
        )

# HTML Frontend ACTUALIZADO CON LLAMADAS A LA API
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
      <button onclick="agregarLibro()">Agregar Libro</button>
    </div>

    <div id="detalleLibro">
      <h3 id="tituloDetalle"></h3>
      <p id="autorDetalle"></p>
      <p id="categoriaDetalle"></p>
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
    let userRole = null;  // ← Guardamos el rol del usuario
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
        userRole = data.rol;  // ← Guardamos el rol
        
        document.getElementById('login').style.display = 'none';
        document.getElementById('panelUsuario').style.display = 'block';
        document.getElementById('cerrarSesion').style.display = 'block';
        
        // Mostrar u ocultar sección de agregar libros según el rol
        const agregarLibroSection = document.querySelector('#panelUsuario h2:nth-of-type(3)').parentElement.querySelectorAll('h2:nth-of-type(3), #nuevoTitulo, #nuevoAutor, #nuevaCategoria, button:last-of-type');
        if (userRole === 'admin') {
          alert('✅ Bienvenido Administrador');
        } else {
          // Ocultar formulario de agregar libros para usuarios normales
          document.querySelectorAll('#panelUsuario > h2:nth-of-type(3), #nuevoTitulo, #nuevoAutor, #nuevaCategoria, #panelUsuario > button:last-of-type').forEach(el => {
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
      userRole = null;  // ← Limpiar rol
      document.getElementById('login').style.display = 'block';
      document.getElementById('panelUsuario').style.display = 'none';
      document.getElementById('cerrarSesion').style.display = 'none';
      document.getElementById('loginEmail').value = '';
      document.getElementById('loginClave').value = '';
      
      // Mostrar de nuevo el formulario de agregar libros (para próximo login)
      document.querySelectorAll('#panelUsuario > h2:nth-of-type(3), #nuevoTitulo, #nuevoAutor, #nuevaCategoria, #panelUsuario > button:last-of-type').forEach(el => {
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
      
      if (!titulo || !autor || !categoria) {
        alert('Completa todos los campos');
        return;
      }
      
      try {
        await request(`${API}/libros`, {
          method: 'POST',
          body: JSON.stringify({titulo, autor, categoria})
        });
        
        document.getElementById('nuevoTitulo').value = '';
        document.getElementById('nuevoAutor').value = '';
        document.getElementById('nuevaCategoria').value = '';
        
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
        
        const lista = document.getElementById('listaReseñas');
        lista.innerHTML = '';
        reseñas.forEach(r => {
          const li = document.createElement('li');
          li.textContent = `Usuario ${r.usuario_id}: "${r.texto}" (⭐${r.cal})`;
          lista.appendChild(li);
        });
        
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
        
        await request(`${API}/libros/${libroId}`, {
          method: 'PUT',
          body: JSON.stringify({
            titulo: nuevoTitulo,
            autor: nuevoAutor,
            categoria: nuevaCategoria
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

# === ENDPOINTS API ===

@app.get("/api/v1/libros", response_model=List[BookOut])
def listar_libros(
    page: int = 1,
    limit: int = 20,
    categoria: Optional[str] = None,
    search: Optional[str] = None,
):
    items = STORES["books"].copy()
    
    if categoria:
        items = [b for b in items if b["categoria"].lower() == categoria.lower()]
    
    if search:
        q = search.lower()
        items = [b for b in items if q in b["titulo"].lower() or q in b["autor"].lower()]
    
    start = (page - 1) * limit
    end = start + limit
    return items[start:end]

@app.post("/api/v1/libros", response_model=BookOut, status_code=status.HTTP_201_CREATED)
def crear_libro(data: BookCreate, user=Depends(get_current_user)):
    # Solo admin puede crear libros
    admin_required(user)
    
    book = {
        "id": next_book_id(),
        "titulo": data.titulo,
        "autor": data.autor,
        "categoria": data.categoria,
    }
    STORES["books"].append(book)
    return book

@app.get("/api/v1/libros/{libro_id}", response_model=BookOut)
def obtener_libro(libro_id: int):
    for b in STORES["books"]:
        if b["id"] == libro_id:
            return b
    raise HTTPException(status_code=404, detail="Libro no encontrado")

@app.put("/api/v1/libros/{libro_id}", response_model=BookOut)
def actualizar_libro(libro_id: int, payload: BookUpdate, user=Depends(get_current_user)):
    admin_required(user)
    
    for b in STORES["books"]:
        if b["id"] == libro_id:
            if payload.titulo is not None:
                b["titulo"] = payload.titulo
            if payload.autor is not None:
                b["autor"] = payload.autor
            if payload.categoria is not None:
                b["categoria"] = payload.categoria
            return b
    raise HTTPException(status_code=404, detail="Libro no encontrado")

@app.delete("/api/v1/libros/{libro_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_libro(libro_id: int, user=Depends(get_current_user)):
    admin_required(user)
    
    for i, b in enumerate(STORES["books"]):
        if b["id"] == libro_id:
            STORES["books"].pop(i)
            STORES["reviews"].pop(str(libro_id), None)
            return
    raise HTTPException(status_code=404, detail="Libro no encontrado")

# === RESEÑAS ===

@app.get("/api/v1/libros/{libro_id}/reseñas", response_model=List[ReviewOut])
def listar_reseñas(libro_id: int):
    key = str(libro_id)
    return STORES["reviews"].get(key, [])

@app.post("/api/v1/libros/{libro_id}/reseñas", response_model=ReviewOut, status_code=status.HTTP_201_CREATED)
def crear_reseña(libro_id: int, payload: ReviewCreate, user=Depends(get_current_user)):
    if not any(b["id"] == libro_id for b in STORES["books"]):
        raise HTTPException(status_code=404, detail="Libro no encontrado")
    
    key = str(libro_id)
    rec = {"usuario_id": user["id"], "texto": payload.texto, "cal": payload.cal}
    STORES["reviews"].setdefault(key, []).append(rec)
    return rec

# === USUARIOS ===

@app.post("/api/v1/usuarios", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def registrar_usuario(payload: UserCreate):
    if _get_user_by_email(payload.email):
        raise HTTPException(status_code=409, detail="Email ya registrado")
    
    user = {
        "id": next_user_id(),
        "nombre": payload.nombre,
        "email": payload.email,
        "password_hash": _hash_password(payload.clave),
        "rol": payload.rol,
        "biblioteca": [],
    }
    STORES["users"].append(user)
    return {"id": user["id"], "nombre": user["nombre"], "email": user["email"], "rol": user["rol"]}

@app.post("/api/v1/auth/login")
def login(payload: LoginInput):
    user = _get_user_by_email(payload.email)
    if not user:
        raise HTTPException(status_code=401, detail="Credenciales inválidas")
    
    if user["password_hash"] != _hash_password(payload.clave):
        raise HTTPException(status_code=401, detail="Credenciales inválidas")
    
    token = secrets.token_urlsafe(32)
    STORES["tokens"][token] = user["id"]
    
    return {"token": token, "rol": user.get("rol", "usuario")}

# === BIBLIOTECA PERSONAL ===

@app.post("/api/v1/usuarios/me/biblioteca/{libro_id}")
def agregar_a_mi_biblioteca(libro_id: int, user=Depends(get_current_user)):
    if not any(b["id"] == libro_id for b in STORES["books"]):
        raise HTTPException(status_code=404, detail="Libro no encontrado")
    if libro_id in user["biblioteca"]:
        raise HTTPException(status_code=409, detail="Libro ya en biblioteca")
    user["biblioteca"].append(libro_id)
    return {"message": "Libro agregado a tu biblioteca"}

@app.delete("/api/v1/usuarios/me/biblioteca/{libro_id}")
def quitar_de_mi_biblioteca(libro_id: int, user=Depends(get_current_user)):
    if libro_id not in user["biblioteca"]:
        raise HTTPException(status_code=404, detail="Libro no está en tu biblioteca")
    user["biblioteca"].remove(libro_id)
    return {"message": "Libro eliminado de tu biblioteca"}

@app.get("/api/v1/usuarios/me/biblioteca", response_model=List[BookOut])
def obtener_mi_biblioteca(user=Depends(get_current_user)):
    libros = [b for b in STORES["books"] if b["id"] in user["biblioteca"]]
    return libros

if __name__ == "__main__":
    import uvicorn
    puerto = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=puerto)
