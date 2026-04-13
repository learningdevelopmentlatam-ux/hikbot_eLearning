"""
=============================================================================
HIK_NAMES — Validador de nombres con Gemini AI
=============================================================================

Responsabilidad única:
  Determinar si un nombre es de una persona real o de una empresa/bot
  usando Google Gemini Flash (gratuito)

Flujo:
  1. Filtro rápido: nombre == empresa → False directo (sin gastar API)
  2. Si pasa → pregunta a Gemini: ¿es nombre de persona?
  3. Retorna True (persona) o False (no persona)

Requiere en .env:
  GEMINI_API_KEY → API key de Google AI Studio

=============================================================================
"""

import os
import logging
from google import genai
from dotenv import load_dotenv
import time

load_dotenv()

log = logging.getLogger("HikBot")

# Configurar Gemini
client = genai.Client(api_key=os.getenv("GEMINI_API_KEY", ""))

class HikNames:
    """
    Valida si un nombre corresponde a una persona real.

    Uso:
        validator = HikNames()
        es_persona = validator.es_persona("Edith Ramirez", "Accesschile")
    """

    def __init__(self):
        self._validar_config()
        # Cache para no repetir llamadas con el mismo nombre
        self._cache = {}

    def es_persona(self, nombre: str, empresa: str) -> bool:
        """
        Retorna True si el nombre es de una persona real.
        Retorna False si parece empresa, bot o nombre inválido.
        """
        nombre  = nombre.strip()
        empresa = empresa.strip()

        if not nombre:
            log.info(f"  [Names] Sin nombre → rechazar")
            return False

        # Filtro 1 — nombre igual a empresa (sin gastar API)
        if nombre.lower() == empresa.lower():
            log.info(f"  [Names] Nombre == Empresa '{nombre}' → rechazar")
            return False

        # Filtro 2 — Gemini
        return self._consultar_gemini(nombre)

    def _consultar_gemini(self, nombre: str) -> bool:
        """Consulta Gemini si el nombre es de una persona real."""

        # Usar cache si ya consultamos este nombre
        nombre_lower = nombre.lower()
        if nombre_lower in self._cache:
            resultado = self._cache[nombre_lower]
            log.info(f"  [Names] Cache: '{nombre}' → {'persona' if resultado else 'no persona'}")
            return resultado
        time.sleep(4)  # 4 segundos entre llamadas = máx 15/min

        prompt = f"""You are validating names for a certification system.
        
Determine if this is a real human person's name or a company/organization/bot name.

Name: "{nombre}"

Rules:
- Answer YES if it looks like a real human name (from any country or culture)
- Answer NO if it looks like a company, brand, organization, or is clearly not a human name
- Answer only YES or NO, nothing else

Answer:"""

        try:
            response = client.models.generate_content(
                model="gemini-2.0-flash-lite",
                contents=prompt
            )
            answer = response.text.strip().upper()
            resultado = answer.startswith("YES")

            self._cache[nombre_lower] = resultado
            log.info(f"  [Names] Gemini: '{nombre}' → {'persona ✓' if resultado else 'no persona ✗'} (respuesta: {answer})")
            return resultado

        except Exception as e:
            # Si falla Gemini, aprobar por defecto para no rechazar personas reales
            log.warning(f"  [Names] Error Gemini para '{nombre}': {e} → aprobando por defecto")
            return True

    def _validar_config(self):
        if not os.getenv("GEMINI_API_KEY"):
            raise Exception("GEMINI_API_KEY no está definido en .env")