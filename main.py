# main.py
from fastapi import FastAPI, HTTPException, status, Depends, Header
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional, Dict, Any
import secrets
import hashlib
import os

app = FastAPI(title="Sistema Biblioteca - API RESTful")

#@app.get("/health")def health_check():return {"status": "ok"}

)

# ---------------------------
# == Datos iniciales / "DB" en memoria
# ---------------------------
_next_book_id = 1
next_book_id = lambda: _next_id("book")
_next_user_id = 1
next_user_id = lambda: _next_id("user")

STORES = {
    "books": [],      # lista de dicts con keys: id, titulo, autor, categoria, createdAt
    "users": [],      # lista de dicts con keys: id, nombre, email, password_hash, biblioteca (lista de book ids)
    "reviews": {},    # key: book_id -> list of reviews { user_id, texto, cal, createdAt }
    "tokens": {},     # token -> user_id (sesiones temporales)
}
INVENTARIO_LIBROS = [
    {"titulo": "Cien Años de Soledad", "autor": "Gabriel García Márquez", "categoria": "Novela"},
    {"titulo": "El libro troll", "autor": "el rubius", "categoria": "historico"},
    {"titulo": "1984", "autor": "George Orwell", "categoria": "Distopía"},
    {"titulo": "Don Quijote de la Mancha", "autor": "Miguel de Cervantes", "categoria": "Clásico"},
    {"titulo": "La Odisea", "autor": "Homero", "categoria": "Épica"},
]

def _next_id(kind: str) -> int:
    global _next_book_id, _next_user_id
    if kind == "book":
        val = _next_book_id
        _next_book_id += 1
        return val
    if kind == "user":
        val = _next_user_id
        _next_user_id += 1
        return val
    raise RuntimeError("unknown id kind")

# Poblado inicial (tomado de tu HTML original)
initial_books = [
    {"titulo": "Cien Años de Soledad", "autor": "Gabriel García Márquez", "categoria": "Novela"},
    {"titulo": "El libro troll", "autor": "el rubius", "categoria": "Historico"},
    {"titulo": "1984", "autor": "George Orwell", "categoria": "Distopía"},
    {"titulo": "Don Quijote de la Mancha", "autor": "Miguel de Cervantes", "categoria": "Clásico"},
    {"titulo": "La Odisea", "autor": "Homero", "categoria": "Épica"},
]

for b in initial_books:
    book = {
        "id": next_book_id(),
        "titulo": b["titulo"],
        "autor": b["autor"],
        "categoria": b["categoria"],
    }
    STORES["books"].append(book)

# ---------------------------
# == Schemas (Pydantic)
# ---------------------------
class BookCreate(BaseModel):
    titulo: str = Field(..., min_length=1)
    autor: str = Field(..., min_length=1)
    categoria: str = Field(..., min_length=1)

class BookUpdate(BaseModel):
    titulo: Optional[str]
    autor: Optional[str]
    categoria: Optional[str]

class BookOut(BaseModel):
    id: int
    titulo: str
    autor: str
    categoria: str

class UserCreate(BaseModel):
    nombre: str = Field(..., min_length=1)
    email: EmailStr
    clave: str = Field(..., min_length=6)

class UserOut(BaseModel):
    id: int
    nombre: str
    email: EmailStr

class TokenOut(BaseModel):
    token: str

class ReviewCreate(BaseModel):
    texto: str = Field(..., min_length=1)
    cal: int = Field(..., ge=1, le=5)

class ReviewOut(BaseModel):
    usuario_id: int
    texto: str
    cal: int

# ---------------------------
# == Utilidades (hash, auth)
# ---------------------------
def _hash_password(clave: str) -> str:
    return hashlib.sha256(clave.encode("utf-8")).hexdigest()

def _get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    for u in STORES["users"]:
        if u["email"].lower() == email.lower():
            return u
    return None

def _get_user_by_id(uid: int) -> Optional[Dict[str, Any]]:
    for u in STORES["users"]:
        if u["id"] == uid:
            return u
    return None

def authenticate_user(email: str, clave: str) -> Optional[Dict[str, Any]]:
    user = _get_user_by_email(email)
    if not user:
        return None
    if user["password_hash"] != _hash_password(clave):
        return None
    return user

def create_token_for_user(user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    STORES["tokens"][token] = user_id
    return token

def get_current_user(authorization: Optional[str] = Header(None)) -> Dict[str, Any]:
    """
    Dependency to get current user from header Authorization: Bearer <token>
    Raises HTTPException 401 if invalid/missing.
    """
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authorization header required")
    parts = authorization.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid authorization header")
    token = parts[1]
    user_id = STORES["tokens"].get(token)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    user = _get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user

# ---------------------------
# == HTML frontend (mantengo tu página)
# ---------------------------
HTML_PAGE = f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Biblioteca Personal</title>
  <style>
    /* Fondo estilo papel antiguo */
    body {{
      font-family: 'Arial', sans-serif;
      background-color: #f5f1e9;
      background-image:
        radial-gradient(circle at 50% 50%, #f7f3eb 5%, transparent 25%),
        radial-gradient(circle at 25% 25%, #f1e8dc 5%, transparent 20%);
      background-repeat: repeat;
      margin: 0;
      padding: 0;
      display: flex;
      justify-content: center;
      min-height: 100vh;
      align-items: flex-start;
      padding-top: 30px;
    }}

    .container {{
      background: #fffdfa;
      max-width: 700px;
      width: 90%;
      padding: 25px 35px;
      border-radius: 12px;
      box-shadow: 0 8px 15px rgba(0,0,0,0.1);
      box-sizing: border-box;
      text-align: center;
    }}

    h1, h2, h3, h4 {{
      color: #3a4d24;
      margin-bottom: 20px;
      font-weight: 700;
      font-family: 'Georgia', serif;
    }}

    input, textarea, select, button {{
      width: 100%;
      padding: 12px 15px;
      margin: 10px 0;
      border-radius: 8px;
      border: 1.8px solid #9caf88;
      font-size: 16px;
      font-family: 'Arial', sans-serif;
      box-sizing: border-box;
      transition: border-color 0.3s ease;
    }}

    input:focus, textarea:focus, select:focus {{
      outline: none;
      border-color: #5a7d30;
      background-color: #f7f9f3;
    }}

    button {{
      background-color: #4caf50;
      color: white;
      border: none;
      cursor: pointer;
      font-weight: 700;
      letter-spacing: 0.05em;
      box-shadow: 0 4px 8px rgba(76, 175, 80, 0.3);
      transition: background-color 0.3s ease;
      max-width: 250px;
      margin-left: auto;
      margin-right: auto;
      display: block;
    }}

    button:hover {{
      background-color: #388e3c;
    }}

    #panelUsuario, #detalleLibro, #registro {{
      display: none;
      margin-top: 30px;
      text-align: left;
    }}

    #catalogoGlobal div, #miBiblioteca div {{
      padding: 15px;
      margin: 8px 0;
      background-color: #e7ebd1;
      border: 1.6px solid #b6c78a;
      border-radius: 8px;
      font-family: 'Georgia', serif;
      color: #3a4d24;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }}

    #catalogoGlobal div:hover, #miBiblioteca div:hover {{
      background-color: #d4dbb4;
    }}

    .detalle {{
      background-color: #fff8dc;
      border: 1.8px solid #f0e68c;
      padding: 20px;
      margin-top: 20px;
      border-radius: 8px;
      color: #6b5e00;
      font-family: 'Georgia', serif;
    }}

    /* Botones en los listados */
    #catalogoGlobal button, #miBiblioteca button {{
      width: auto;
      padding: 7px 12px;
      margin-left: 10px;
      border-radius: 6px;
      font-size: 14px;
      background-color: #6aaa4f;
      box-shadow: 0 3px 6px rgba(106, 170, 79, 0.4);
    }}

    #catalogoGlobal button:hover, #miBiblioteca button:hover {{
      background-color: #488235;
    }}

    /* Botón cerrar sesión */
    #cerrarSecion {{
      margin-top: 20px;
      max-width: 150px;
      background-color: #a44c4c;
      box-shadow: 0 4px 8px rgba(164, 76, 76, 0.4);
    }}

    #cerrarSecion:hover {{
      background-color: #7a3939;
    }}
  </style>
</head>
<body>
  <div class="container">
    <h1>Biblioteca Personal</h1>

    <div id="login">
      <h2>Ingresar usuario</h2>
      <input type="text" id="usuario" placeholder="Nombre de usuario" autocomplete="username" />
      <input type="password" id="clave" placeholder="Contraseña" autocomplete="current-password" />
      <button onclick="login()">Ingresar</button>
      <button onclick="mostrarRegistro()">Registrar usuario</button>
    </div>

    <div id="registro">
      <h2>Registrar Usuario</h2>
      <input type="text" id="nuevoNombre" placeholder="Nombre" />
      <input type="password" id="nuevaClave" placeholder="Contraseña" />
      <button onclick="agregarUsuario()">Registrar</button>
      <button onclick="volverLogin()">Volver</button>
    </div>

    <div id="panelUsuario">
      <h2>Biblioteca Global</h2>
      <div id="catalogoGlobal"></div>

      <h2>Mi Biblioteca</h2>
      <div id="miBiblioteca"></div>

      <h2>Agregar Libro Nuevo</h2>
      <input type="text" id="titulo" placeholder="Título del libro" />
      <input type="text" id="autor" placeholder="Autor" />
      <input type="text" id="categoria" placeholder="Categoría" />
      <button onclick="agregarLibroGlobal()">Agregar Libro</button>
    </div>

    <div id="detalleLibro">
      <h3 id="tituloDetalle"></h3>
      <p id="autorDetalle"></p>
      <p id="categoriaDetalle"></p>

      <textarea id="reseñaTexto" placeholder="Escribe tu reseña..."></textarea>
      <input type="number" id="calificacion" min="1" max="5" placeholder="Calificación (1 a 5)" />
      <button onclick="guardarReseña()">Guardar Reseña</button>

      <h4>Reseñas:</h4>
      <ul id="listaReseñas"></ul>
    </div>

    <button id="cerrarSecion" style="display:none;" onclick="logout()">Cerrar sesión</button>
  </div>

  <script>
    // Inventario inicial, solo si no existe ya en localStorage
    if (!localStorage.getItem("librosGlobal")) {{
      localStorage.setItem("librosGlobal", JSON.stringify({INVENTARIO_LIBROS}));
    }}

    let usuarios = JSON.parse(localStorage.getItem("usuarios")) || [];
    let usuarioActual = null;
    let librosGlobal = JSON.parse(localStorage.getItem("librosGlobal")) || [];
    let reseñas = JSON.parse(localStorage.getItem("reseñas")) || {{}};
    let libroSeleccionado = null;

    function guardarDatos() {{
      localStorage.setItem("usuarios", JSON.stringify(usuarios));
      localStorage.setItem("librosGlobal", JSON.stringify(librosGlobal));
      localStorage.setItem("reseñas", JSON.stringify(reseñas));
    }}

    function login() {{
      const nombre = document.getElementById("usuario").value.trim();
      const clave = document.getElementById("clave").value;
      const user = usuarios.find(u => u.nombre === nombre && u.clave === clave);
      if (!user) {{
        alert("Usuario o clave incorrecta");
        return;
      }}
      usuarioActual = user;
      document.getElementById("login").style.display = "none";
      document.getElementById("registro").style.display = "none";
      document.getElementById("panelUsuario").style.display = "block";
      document.getElementById("cerrarSecion").style.display = "block";
      mostrarCatalogoGlobal();
      mostrarMiBiblioteca();
    }}

    function mostrarRegistro() {{
      document.getElementById("registro").style.display = "block";
      document.getElementById("login").style.display = "none";
    }}

    function volverLogin() {{
      document.getElementById("registro").style.display = "none";
      document.getElementById("login").style.display = "block";
    }}

    function agregarUsuario() {{
      const nombre = document.getElementById("nuevoNombre").value.trim();
      const clave = document.getElementById("nuevaClave").value;
      if (!nombre || !clave) {{
        alert("Completa todos los campos");
        return;
      }}
      if (usuarios.some(u => u.nombre === nombre)) {{
        alert("Nombre ya existe");
        return;
      }}
      usuarios.push({{ nombre, clave, biblioteca: [] }});
      guardarDatos();
      alert("Registrado exitosamente");
      document.getElementById("registro").style.display = "none";
      document.getElementById("login").style.display = "block";
    }}

    function logout() {{
      usuarioActual = null;
      document.getElementById("login").style.display = "block";
      document.getElementById("registro").style.display = "none";
      document.getElementById("panelUsuario").style.display = "none";
      document.getElementById("cerrarSecion").style.display = "none";
      document.getElementById("detalleLibro").style.display = "none";
      document.getElementById("usuario").value = "";
      document.getElementById("clave").value = "";
    }}

    function agregarLibroGlobal() {{
      const titulo = document.getElementById("titulo").value.trim();
      const autor = document.getElementById("autor").value.trim();
      const categoria = document.getElementById("categoria").value.trim();
      if (!titulo || !autor || !categoria) {{
        alert("Completa todos los campos");
        return;
      }}
      librosGlobal.push({{ titulo, autor, categoria }});
      guardarDatos();
      mostrarCatalogoGlobal();
      // Limpiar inputs
      document.getElementById("titulo").value = "";
      document.getElementById("autor").value = "";
      document.getElementById("categoria").value = "";
    }}

    function mostrarCatalogoGlobal() {{
      const cont = document.getElementById("catalogoGlobal");
      cont.innerHTML = "";
      librosGlobal.forEach((libro, i) => {{
        const div = document.createElement("div");
        div.innerHTML = `<strong>${{libro.titulo}}</strong> - ${{libro.autor}} (${{libro.categoria}})
          <div>
            <button onclick="agregarAMiBiblioteca(${{i}})">Agregar a mi biblioteca</button>
            <button onclick="verDetalle(${{i}})">Ver detalle</button>
          </div>`;
        cont.appendChild(div);
      }});
    }}

    function agregarAMiBiblioteca(index) {{
      const libro = librosGlobal[index];
      if (!usuarioActual.biblioteca.some(l => l.titulo === libro.titulo && l.autor === libro.autor)) {{
        usuarioActual.biblioteca.push(libro);
        guardarDatos();
        mostrarMiBiblioteca();
      }} else {{
        alert("Este libro ya está en tu biblioteca");
      }}
    }}

    function mostrarMiBiblioteca() {{
      const cont = document.getElementById("miBiblioteca");
      cont.innerHTML = "";
      usuarioActual.biblioteca.forEach((libro, i) => {{
        const div = document.createElement("div");
        div.innerHTML = `<strong>${{libro.titulo}}</strong> - ${{libro.autor}}
          <div>
            <button onclick="verDetalleDesdeMiBiblioteca(${{i}})">Ver detalle</button>
            <button onclick="eliminarDeMiBiblioteca(${{i}})">Eliminar</button>
          </div>`;
        cont.appendChild(div);
      }});
    }}

    function eliminarDeMiBiblioteca(index) {{
      usuarioActual.biblioteca.splice(index, 1);
      guardarDatos();
      mostrarMiBiblioteca();
    }}

    function verDetalle(index) {{
      const libro = librosGlobal[index];
      mostrarDetalle(libro);
    }}

    function verDetalleDesdeMiBiblioteca(index) {{
      const libro = usuarioActual.biblioteca[index];
      mostrarDetalle(libro);
    }}

    function mostrarDetalle(libro) {{
      libroSeleccionado = libro;
      document.getElementById("tituloDetalle").textContent = libro.titulo;
      document.getElementById("autorDetalle").textContent = "Autor: " + libro.autor;
      document.getElementById("categoriaDetalle").textContent = "Categoría: " + libro.categoria;
      document.getElementById("detalleLibro").style.display = "block";
      mostrarReseñas();
      // Scroll a detalle para mejor UX
      document.getElementById("detalleLibro").scrollIntoView({{behavior: "smooth"}});
    }}

    function mostrarReseñas() {{
      const list = document.getElementById("listaReseñas");
      list.innerHTML = "";
      const key = libroSeleccionado.titulo;
      const reseñasLibro = reseñas[key] || [];
      reseñasLibro.forEach(r => {{
        const li = document.createElement("li");
        li.textContent = `${{r.usuario}}: "${{r.texto}}" (Calificación: ${{r.cal}})`;
        list.appendChild(li);
      }});
    }}

    function guardarReseña() {{
      const texto = document.getElementById("reseñaTexto").value.trim();
      const cal = parseInt(document.getElementById("calificacion").value);
      if (!texto || isNaN(cal) || cal < 1 || cal > 5) {{
        alert("Completa todos los campos correctamente (texto y calificación de 1 a 5)");
        return;
      }}
      const key = libroSeleccionado.titulo;
      if (!reseñas[key]) reseñas[key] = [];
      reseñas[key].push({{ usuario: usuarioActual.nombre, texto, cal }});
      guardarDatos();
      document.getElementById("reseñaTexto").value = "";
      document.getElementById("calificacion").value = "";
      mostrarReseñas();
      alert("Reseña guardada ✅");
    }}
  </script>
</body>
</html>"""
# Para brevedad en este snippet lo oculto; en tu archivo final puedes usar el HTML que ya tenías.
# (En el ejemplo real que pegues en tu proyecto, copia la variable HTML_PAGE completa desde tu main.py original.)

@app.get("/", response_class=HTMLResponse)
def home():
    return HTMLResponse(HTML_PAGE)

# ---------------------------
# == Endpoints API v1 - Libros
# ---------------------------
@app.get("/api/v1/libros", response_model=List[BookOut])
def listar_libros(
    page: int = 1,
    limit: int = 20,
    categoria: Optional[str] = None,
    search: Optional[str] = None,
    sort: Optional[str] = None,
):
    """
    Listar libros con paginación básica, filtrado por categoría y búsqueda por título/autor.
    """
    items = STORES["books"].copy()

    # filtro
    if categoria:
        items = [b for b in items if b["categoria"].lower() == categoria.lower()]

    if search:
        q = search.lower()
        items = [b for b in items if q in b["titulo"].lower() or q in b["autor"].lower()]

    # sort: ejemplo "titulo:asc" o "id:desc"
    if sort:
        try:
            field, direction = sort.split(":")
            reverse = direction.lower() == "desc"
            items.sort(key=lambda x: x.get(field, ""), reverse=reverse)
        except Exception:
            pass

    # paginación
    start = (page - 1) * limit
    end = start + limit
    return items[start:end]

@app.post("/api/v1/libros", status_code=status.HTTP_201_CREATED, response_model=BookOut)
def crear_libro(payload: BookCreate, user=Depends(get_current_user)):
    """
    Crear un libro (requiere autenticación).
    """
    book = {
        "id": next_book_id(),
        "titulo": payload.titulo,
        "autor": payload.autor,
        "categoria": payload.categoria,
    }
    STORES["books"].append(book)
    return book

@app.get("/api/v1/libros/{libro_id}", response_model=BookOut)
def obtener_libro(libro_id: int):
    for b in STORES["books"]:
        if b["id"] == libro_id:
            return b
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Libro no encontrado")

@app.put("/api/v1/libros/{libro_id}", response_model=BookOut)
def actualizar_libro(libro_id: int, payload: BookUpdate, user=Depends(get_current_user)):
    for b in STORES["books"]:
        if b["id"] == libro_id:
            if payload.titulo is not None:
                b["titulo"] = payload.titulo
            if payload.autor is not None:
                b["autor"] = payload.autor
            if payload.categoria is not None:
                b["categoria"] = payload.categoria
            return b
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Libro no encontrado")

@app.delete("/api/v1/libros/{libro_id}", status_code=status.HTTP_204_NO_CONTENT)
def eliminar_libro(libro_id: int, user=Depends(get_current_user)):
    for i, b in enumerate(STORES["books"]):
        if b["id"] == libro_id:
            STORES["books"].pop(i)
            # eliminar reseñas asociadas
            STORES["reviews"].pop(str(libro_id), None)
            return
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Libro no encontrado")

# ---------------------------
# == Endpoints - Reseñas (anidadas)
# ---------------------------
@app.get("/api/v1/libros/{libro_id}/reseñas", response_model=List[ReviewOut])
def listar_reseñas(libro_id: int):
    key = str(libro_id)
    return STORES["reviews"].get(key, [])

@app.post("/api/v1/libros/{libro_id}/reseñas", status_code=status.HTTP_201_CREATED, response_model=ReviewOut)
def crear_reseña(libro_id: int, payload: ReviewCreate, user=Depends(get_current_user)):
    # valida existencia libro
    if not any(b["id"] == libro_id for b in STORES["books"]):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Libro no encontrado")
    key = str(libro_id)
    rec = {"usuario_id": user["id"], "texto": payload.texto, "cal": payload.cal}
    STORES["reviews"].setdefault(key, []).append(rec)
    return rec

# ---------------------------
# == Usuarios & Auth (simple)
# ---------------------------
@app.post("/api/v1/usuarios", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def registrar_usuario(payload: UserCreate):
    if _get_user_by_email(payload.email):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email ya registrado")
    user = {
        "id": next_user_id(),
        "nombre": payload.nombre,
        "email": payload.email,
        "password_hash": _hash_password(payload.clave),
        "biblioteca": [],  # lista de book ids
    }
    STORES["users"].append(user)
    return {"id": user["id"], "nombre": user["nombre"], "email": user["email"]}

@app.post("/api/v1/auth/login", response_model=TokenOut)
def login(email: EmailStr, clave: str):
    user = authenticate_user(email, clave)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Credenciales inválidas")
    token = create_token_for_user(user["id"])
    return {"token": token}

@app.get("/api/v1/auth/me", response_model=UserOut)
def who_am_i(user=Depends(get_current_user)):
    return {"id": user["id"], "nombre": user["nombre"], "email": user["email"]}

# ---------------------------
# == Operaciones de biblioteca personal (agregar/quitar libro)
# ---------------------------
@app.post("/api/v1/usuarios/me/biblioteca/{libro_id}", status_code=status.HTTP_200_OK)
def agregar_a_mi_biblioteca(libro_id: int, user=Depends(get_current_user)):
    if not any(b["id"] == libro_id for b in STORES["books"]):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Libro no encontrado")
    if libro_id in user["biblioteca"]:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Libro ya en biblioteca")
    user["biblioteca"].append(libro_id)
    return {"message": "Libro agregado"}

@app.delete("/api/v1/usuarios/me/biblioteca/{libro_id}", status_code=status.HTTP_200_OK)
def quitar_de_mi_biblioteca(libro_id: int, user=Depends(get_current_user)):
    if libro_id not in user["biblioteca"]:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Libro no está en tu biblioteca")
    user["biblioteca"].remove(libro_id)
    return {"message": "Libro eliminado"}
# ---------------------------
# == Run
# ---------------------------
if __name__ == "__main__":
    import uvicorn
    puerto = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=puerto)









