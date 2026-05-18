import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
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

# 2. Inicializar el cliente del nuevo SDK unificado usando Vertex AI
try:
    client = genai.Client(
        vertexai=True,
        project=os.environ.get("PROJECT_ID"),
        location=os.environ.get("LOCATION", "us-central1")
    )
except Exception as e:
    print(f"Error inicializando Vertex AI: {e}")
    client = None

# 3. Modelos de datos esperados desde React
class ContextoCopiloto(BaseModel):
    rol: str
    nombre_profesional: str
    total_victimas: int
    pendientes_acreditacion: int
    eventos_semana: List[str]

@app.get("/")
def read_root():
    return {"status": "Copiloto SIGEL Operativo"}

@app.post("/api/copiloto/analizar")
def analizar_contexto(contexto: ContextoCopiloto):
    if not client:
        raise HTTPException(status_code=500, detail="El cliente de Vertex AI no está inicializado. Revisa las variables PROJECT_ID y LOCATION.")

    # 4. Construcción del Prompt Inteligente
    prompt = f"""
    Eres el Copiloto Judicial Inteligente del sistema SIGEL (Sistema de Información para la Gestión de Litigio) de la organización IIRESODH.
    Tu objetivo es dar un resumen ejecutivo, profesional y directo (máximo 4 líneas) a un {contexto.rol} que acaba de iniciar sesión.
    
    Contexto actual del profesional ({contexto.nombre_profesional}):
    - Total de víctimas bajo su representación: {contexto.total_victimas}
    - Víctimas que requieren atención urgente (pendientes de acreditación JEP): {contexto.pendientes_acreditacion}
    - Eventos/Audiencias programadas esta semana: {', '.join(contexto.eventos_semana) if contexto.eventos_semana else 'Ninguna'}
    
    Instrucciones:
    1. Saluda formalmente.
    2. Haz un análisis cruzado rápido: si hay audiencias y víctimas pendientes de acreditación, sugiere contactarlas como preparación para la diligencia. Si no hay audiencias, enfócate en la tarea de acreditación.
    3. Mantén un tono de asistente legal eficiente, proactivo y empático.
    4. NO uses formato markdown (asteriscos, negritas) en tu respuesta, devuelve texto plano para la UI.
    """

    try:
        # 5. Llamada al modelo Gemini 1.5 Flash (ideal por su velocidad y bajo costo para tareas de texto)
        response = client.models.generate_content(
            model='gemini-1.5-flash',
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.3, # Baja temperatura para respuestas consistentes y profesionales
            )
        )
        return {"sugerencia": response.text.strip()}
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error generando sugerencia: {str(e)}")
