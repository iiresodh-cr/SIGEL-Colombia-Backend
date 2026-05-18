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

# 3. Modelos de datos a prueba de fallos (Evita el Error 422)
class ContextoCopiloto(BaseModel):
    rol: Optional[str] = "usuario"
    nombre_profesional: Optional[str] = "Profesional"
    total_victimas: Optional[int] = 0
    pendientes_acreditacion: Optional[int] = 0
    eventos_semana: Optional[List[str]] = []

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
    2. Si el abogado tiene 0 víctimas, dale la bienvenida e indícale que el sistema está listo para cuando la coordinación central le asigne nuevos expedientes.
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
        raise HTTPException(status_code=500, detail=f"Error generando sugerencia: {str(e)}")
