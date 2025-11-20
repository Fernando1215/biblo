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
security = HTTPBearer()
app = FastAPI(title="Sistema Biblioteca - API RESTful")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------
# Contadores e "BD" en memoria
_next_book_id = 6  # Empieza en 6 porque ya hay 5 libros iniciales en tu diseño original
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

STORES = {
    "books": [],
    "users": [],
    "reviews": {},   # key: book_id (str) -> list of reviews
    "tokens": {},    # token -> user_id
}

# Libros iniciales con contenido simulado
initial_books = [
    {
        "titulo": "Cien Años de Soledad",
        "autor": "Gabriel García Márquez",
        "categoria": "Novela",
        "contenido": (
            "Capítulo 1: Mucho antes de que naciera Aureliano Buendía, la aldea de Macondo "
            "se había fundado cerca de un río. Aquí comienzan las historias y los mitos..."
        )
    },
    {
        "titulo": "El libro troll",
        "autor": "el rubius",
        "categoria": "Histórico",
        "contenido": (
            "Capítulo 1: Un narrador inesperado cuenta las peripecias de un personaje que "
            "se mete en problemas aunque no lo busca..."
        )
    },
    {
        "titulo": "1984",
        "autor": "George Orwell",
        "categoria": "Distopía",
        "contenido": (
            "Capítulo 1: Winston trabaja vigilando hechos históricos. El gobierno controla "
            "hasta el lenguaje. Aquí comienza su despertar..."
        )
    },
    {
        "titulo": "Don Quijote de la Mancha",
        "autor": "Miguel de Cervantes",
        "categoria": "Clásico",
        "contenido": (
            "Capítulo 1: Alonso Quijano pierde el juicio por leer demasiados libros de caballería "
            "y decide convertirse en caballero andante..."
        )
    },
    {
        "titulo": "La Odisea",
        "autor": "Homero",
        "categoria": "Épica",
        "contenido": (
            "Canto 1: Odiseo trata de regresar a Ítaca. Encuentros con dioses, monstruos y pruebas "
            "marcan su camino..."
        )
    },
]

# Insertar los libros en la BD en memoria
for i, b in enumerate(initial_books, start=1):
    STORES["books"].append({
        "id": i,
        "titulo": b["titulo"],
        "autor": b["autor"],
        "categoria": b["categoria"],
        "contenido": b.get("contenido", "")
    })

# Ajustar el contador de libros 
if len(STORES["books"]) >= _next_book_id:
    _next_book_id = len(STORES["books"]) + 1

# ---------------------------
# Schemas (Pydantic)
class BookCreate(BaseModel):
    titulo: str = Field(..., min_length=1)
    autor: str = Field(..., min_length=1)
    categoria: str = Field(..., min_length=1)
    contenido: Optional[str] = ""  # opcional, puede enviarse al crear

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
    contenido: Optional[str] = ""  # retorno con contenido para detalle/lista

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
# Observer (Subject / Observers)
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
        # Simulación de envío de correo (o push). En prod, aquí llamas a un servicio real.
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
    def add_book(self, titulo: str, autor: str, categoria: str, contenido: str = "") -> Dict[str, Any]:
        book = {
            "id": next_book_id(),
            "titulo": titulo,
            "autor": autor,
            "categoria": categoria,
            "contenido": contenido or ""
        }
        self.store["books"].append(book)
        # Notificar evento
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
                # contenido también puede actualizarse
                if changes.get("contenido") is not None:
                    b["contenido"] = changes["contenido"]
                self.events.notify("LIBRO_ACTUALIZADO", b)
                return b
        return None

    def delete_book(self, libro_id: int) -> bool:
        for i, b in enumerate(self.store["books"]):
            if b["id"] == libro_id:
                removed = self.store["books"].pop(i)
                # eliminar reseñas asociadas
                self.store["reviews"].pop(str(libro_id), None)
                self.events.notify("LIBRO_ELIMINADO", removed)
                return True
        return False

    def get_book(self, libro_id: int) -> Optional[Dict[str, Any]]:
        return next((b for b in self.store["books"] if b["id"] == libro_id), None)

    def list_books(self, categoria: Optional[str] = None, search: Optional[str] = None) -> List[Dict[str, Any]]:
        items = [b.copy() for b in self.store["books"]]
        if categoria:
            items = [b for b in items if b["categoria"].lower() == categoria.lower()]
        if search:
            q = search.lower()
            items = [b for b in items if q in (b.get("titulo","").lower()) or q in (b.get("autor","").lower())]
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
        if user.get("password_hash") != _hash_password(clave_plain):
            return None
        return user

# Instancia de la fachada
facade = LibraryFacade(STORES, event_subject)

# ---------------------------
# Utilidades de seguridad / auth
def _hash_password(clave: str) -> str:
    return hashlib.sha256(clave.encode("utf-8")).hexdigest()

def _get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    return next((u for u in STORES["users"] if u["email"].lower() == email.lower()), None)

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
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
    if user.get("rol") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Solo administradores pueden realizar esta acción")
    
# Crear admin por defecto (siempre)
admin_default = {
    "id": next_user_id(),
    "nombre": "Administrador",
    "email": "admin@biblioteca.com",
    "password_hash": _hash_password("admin123"),  # contraseña por defecto
    "rol": "admin",
    "biblioteca": []
}

STORES["users"].append(admin_default)
print("🟢 Usuario administrador creado por defecto -> admin@biblioteca.com / admin123")

@app.get("/", response_class=HTMLResponse)
def home():
    return HTMLResponse(HTML_PAGE)

# ---------------------------
# Endpoints usando la Facade
@app.get("/api/v1/libros", response_model=List[BookOut])
def listar_libros(page: int = 1, limit: int = 20, categoria: Optional[str] = None, search: Optional[str] = None):
    items = facade.list_books(categoria=categoria, search=search)
    start = (page - 1) * limit
    end = start + limit
    return items[start:end]

@app.post("/api/v1/libros", response_model=BookOut, status_code=status.HTTP_201_CREATED)
def crear_libro(data: BookCreate, user=Depends(get_current_user)):
    admin_required(user)
    book = facade.add_book(data.titulo, data.autor, data.categoria, data.contenido or "")
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
    changes = {"titulo": payload.titulo, "autor": payload.autor, "categoria": payload.categoria, "contenido": payload.contenido}
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

# Endpoints específicos para contenido (GET público, PUT admin)
@app.get("/api/v1/libros/{libro_id}/contenido")
def obtener_contenido(libro_id: int):
    book = facade.get_book(libro_id)
    if not book:
        raise HTTPException(status_code=404, detail="Libro no encontrado")
    return {"id": book["id"], "contenido": book.get("contenido", "")}

class ContenidoUpdate(BaseModel):
    contenido: str = Field(..., min_length=0)

@app.put("/api/v1/libros/{libro_id}/contenido")
def actualizar_contenido(libro_id: int, data: ContenidoUpdate, user=Depends(get_current_user)):
    admin_required(user)
    updated = facade.update_book(libro_id, {"contenido": data.contenido})
    if not updated:
        raise HTTPException(status_code=404, detail="Libro no encontrado")
    return {"message": "Contenido actualizado", "libro": updated}

# Reseñas
@app.get("/api/v1/libros/{libro_id}/reseñas", response_model=List[ReviewOut])
def listar_reseñas(libro_id: int):
    return STORES["reviews"].get(str(libro_id), [])

@app.post("/api/v1/libros/{libro_id}/reseñas", response_model=ReviewOut, status_code=status.HTTP_201_CREATED)
def crear_reseña(libro_id: int, payload: ReviewCreate, user=Depends(get_current_user)):
    if not facade.get_book(libro_id):
        raise HTTPException(status_code=404, detail="Libro no encontrado")
    rec = facade.add_review(libro_id, user["id"], payload.texto, payload.cal)
    return rec

# Usuarios y Auth (usando facade donde aplica)
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

# Biblioteca personal
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

# Run
if __name__ == "__main__":
    import uvicorn
    puerto = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=puerto)



