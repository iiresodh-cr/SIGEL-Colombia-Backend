import os
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from google import genai
from google.genai import types

# 1. Configuración de FastAPI y CORS
app = FastAPI(title="SIGEL Copiloto API")

# Obtener los orígenes permitidos desde las variables de entorno o usar '*' para desarrollo
origins = os.environ.get("CORS_ORIGINS", "*").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. Inicializar el cliente de Vertex AI
try:
    client = genai.Client(
        vertexai=True,
        project=os.environ.get("PROJECT_ID"),
        location=os.environ.get("LOCATION", "us-central1")
    )
except Exception as e:
    print(f"Error inicializando Vertex AI: {e}")
    client = None

@app.get("/")
def read_root():
    return {"status": "Copiloto SIGEL Operativo"}

# 3. Endpoint flexible (Bypass de Pydantic para evitar el Error 422)
@app.post("/api/copiloto/analizar")
async def analizar_contexto(request: Request):
    if not client:
        raise HTTPException(status_code=500, detail="El cliente de Vertex AI no está inicializado.")

    # Atrapamos el JSON crudo tal como viene de React, sin validaciones estrictas
    try:
        payload = await request.json()
    except Exception:
        payload = {}

    # Extraemos los datos de forma manual y segura
    rol = str(payload.get("rol", "usuario"))
    nombre = str(payload.get("nombre_profesional", "Profesional"))
    total = int(payload.get("total_victimas") or 0)
    pendientes = int(payload.get("pendientes_acreditacion") or 0)
    
    # Limpiar la lista para que no haya 'None' y asegurar que todo sea texto
    eventos_crudos = payload.get("eventos_semana")
    if isinstance(eventos_crudos, list):
        # Filtramos elementos nulos y convertimos todo a string
        eventos_semana = [str(e) for e in eventos_crudos if e is not None]
    else:
        eventos_semana = []

    # 4. Construcción del Prompt Inteligente
    prompt = f"""
    Eres el Copiloto Judicial Inteligente del sistema SIGEL (Sistema de Información para la Gestión Electrónica de Litigios) de la organización IIRESODH.
    Tu objetivo es dar un resumen ejecutivo, profesional y directo (máximo 4 líneas) a un {rol} que acaba de iniciar sesión.
    
    Contexto actual del profesional ({nombre}):
    - Total de víctimas bajo su representación: {total}
    - Víctimas que requieren atención urgente (pendientes de acreditación JEP): {pendientes}
    - Eventos/Audiencias programadas esta semana: {', '.join(eventos_semana) if eventos_semana else 'Ninguna'}
    
    Instrucciones:
    1. Saluda formalmente utilizando el nombre, sin prefijos como Dr. o parecidos.
    2. Si el abogado tiene 0 víctimas, dale la bienvenida e indícale que el sistema está listo para cuando la coordinación central le asigne expedientes. No menciones nada de audiencias si tiene 0 casos.
    3. Si tiene casos/audiencias, haz un análisis cruzado rápido sugiriendo prepararse para la diligencia.
    4. Mantén un tono de asistente legal eficiente, proactivo y empático.
    5. NO uses formato markdown (asteriscos, negritas) en tu respuesta, devuelve texto plano para la UI.
    """

    try:
        # 5. Llamada al modelo Gemini 2.5 Flash
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
