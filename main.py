import os
from fastapi import FastAPI, HTTPException, Request, Header, Depends
from fastapi.middleware.cors import CORSMiddleware
from google import genai
from google.genai import types
import firebase_admin
from firebase_admin import auth as firebase_auth

# 1. Configuración de FastAPI y CORS
app = FastAPI(title="SIGEL Copiloto API")

origins = os.environ.get("CORS_ORIGINS", "*").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. Inicializar Firebase Admin (Detecta las credenciales automáticamente en Cloud Run)
try:
    if not firebase_admin._apps:
        firebase_admin.initialize_app()
except Exception as e:
    print(f"Error inicializando Firebase Admin: {e}")

# 3. Inicializar el cliente de Vertex AI
try:
    client = genai.Client(
        vertexai=True,
        project=os.environ.get("PROJECT_ID"),
        location=os.environ.get("LOCATION", "us-central1")
    )
except Exception as e:
    print(f"Error inicializando Vertex AI: {e}")
    client = None

# =======================================================
# 🔒 GUARDIA DE SEGURIDAD JWT
# =======================================================
def verificar_token(authorization: str = Header(None)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Falta el token de autorización o el formato es incorrecto.")
    
    token = authorization.split("Bearer ")[1]
    
    try:
        # Verifica la firma criptográfica con Google
        decoded_token = firebase_auth.verify_id_token(token)
        email = decoded_token.get("email", "")
        
        # Validación extra de seguridad de dominio
        if not email.endswith("@iiresodh.org"):
            raise HTTPException(status_code=403, detail="Dominio institucional no autorizado.")
            
        return decoded_token
    except Exception as e:
        print(f"Intento de acceso bloqueado (Token inválido): {e}")
        raise HTTPException(status_code=401, detail="Token inválido o sesión expirada.")

@app.get("/")
def read_root():
    return {"status": "Copiloto SIGEL Operativo y Seguro"}

# 4. Endpoint protegido (Requiere pasar por el guardia: Depends(verificar_token))
@app.post("/api/copiloto/analizar")
async def analizar_contexto(request: Request, user_token: dict = Depends(verificar_token)):
    if not client:
        raise HTTPException(status_code=500, detail="El cliente de Vertex AI no está inicializado.")

    try:
        payload = await request.json()
    except Exception:
        payload = {}

    # Extraemos los datos y forzamos el conteo matemático
    rol = str(payload.get("rol", "usuario"))
    nombre = str(payload.get("nombre_profesional", "Profesional"))
    total = int(payload.get("total_victimas") or 0)
    pendientes = int(payload.get("pendientes_acreditacion") or 0)
    
    eventos_crudos = payload.get("eventos_semana")
    if isinstance(eventos_crudos, list):
        eventos_semana = [str(e) for e in eventos_crudos if e is not None]
    else:
        eventos_semana = []
        
    # Variables estrictas para la IA
    cantidad_eventos = len(eventos_semana)
    eventos_texto = ', '.join(eventos_semana) if cantidad_eventos > 0 else '0 eventos'

    # 4. Prompt de PIDA con reglas antidistracción
    prompt = f"""
    Tu nombre es PIDA, el asistente de Inteligencia Artificial del sistema SIGEL (IIRESODH).
    Tu objetivo es dar un resumen ejecutivo, profesional y directo (máximo 4 líneas) a un {rol} que acaba de iniciar sesión.
    
    Contexto ESTRICTO de {nombre} (REGLA DE ORO: NO inventes números, usa SOLO la siguiente información):
    - Total de víctimas bajo su representación: {total}
    - Víctimas pendientes de acreditación JEP: {pendientes}
    - Eventos/Audiencias esta semana: {cantidad_eventos} ({eventos_texto})
    
    Instrucciones:
    1. Preséntate brevemente como PIDA y saluda formalmente.
    2. Si tiene 0 eventos, di explícitamente que no tiene audiencias programadas. JAMÁS inventes eventos.
    3. Si tiene 0 víctimas, dale la bienvenida e indícale que estás a la espera de nuevas asignaciones.
    4. Si tiene casos o audiencias, haz un análisis rápido sugiriendo prioridades.
    5. Mantén un tono de asistente legal eficiente y empático.
    6. NO uses formato markdown (asteriscos, negritas).
    """

    try:
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.3, 
            )
        )
        return {"sugerencia": response.text.strip()}
    
    except Exception as e:
        print(f"ERROR Vertex AI: {str(e)}")
        raise HTTPException(status_code=500, detail="Error interno de IA.")
