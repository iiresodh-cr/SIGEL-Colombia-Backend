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

    # Extraemos los datos
    rol = str(payload.get("rol", "usuario"))
    nombre = str(payload.get("nombre_profesional", "Profesional"))
    total = int(payload.get("total_victimas") or 0)
    pendientes = int(payload.get("pendientes_acreditacion") or 0)
    
    eventos_crudos = payload.get("eventos_semana")
    if isinstance(eventos_crudos, list):
        eventos_semana = [str(e) for e in eventos_crudos if e is not None]
    else:
        eventos_semana = []

    cantidad_eventos_total = len(eventos_semana)

    # Lógica inteligente: Si es admin, habla de la institución. Si es abogado, habla de sus casos.
    es_admin = rol.lower() in ["administrador", "admin", "superadmin"]
    texto_victimas = "Total de víctimas en el sistema" if es_admin else "Total de víctimas exclusivas bajo su representación"
    texto_pendientes = "Víctimas del sistema pendientes de acreditación" if es_admin else "Sus víctimas que requieren atención urgente"

    prompt = f"""
    Eres PIDA, el asistente de IA del SIGEL.
    
    Contexto ESTRICTO:
    - Usuario: {nombre}
    - Rol en el sistema: {rol}
    - {texto_victimas}: {total}
    - {texto_pendientes}: {pendientes}
    - Eventos FUTUROS programados: {cantidad_eventos_total}
    
    INSTRUCCIONES CRÍTICAS:
    1. NO TE PRESENTES. No digas "Soy PIDA". Inicia directamente: "Bienvenido/a {nombre}." NUNCA uses títulos como Dr., Lic.
    2. Si {total} es 0, indica que la base de datos está vacía.
    3. Si {cantidad_eventos_total} es 0, confirma explícitamente que no hay audiencias ni eventos futuros programados. JAMÁS inventes eventos.
    4. Usa un tono analítico, directo y corporativo.
    5. No uses formato markdown.
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
