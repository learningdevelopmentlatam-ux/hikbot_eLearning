"""
=============================================================================
HIK_NAMES — Validador de nombres con Groq AI
=============================================================================

Responsabilidad única:
  Determinar si un nombre es de una persona real o de una empresa/bot
  usando Groq (gratuito, sin tarjeta)

Flujo:
  1. Filtro rápido: nombre == empresa → False directo (sin gastar API)
  2. Si pasa → pregunta a Groq: ¿es nombre de persona?
  3. Retorna True (persona) o False (no persona)

Requiere en .env:
  GROQ_API_KEY → API key de console.groq.com

=============================================================================
"""

import os
import time
import logging
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger("HikBot")


class HikNames:

    """
    Valida si un nombre corresponde a una persona real.
    Uso:
        validator = HikNames()
        es_persona = validator.es_persona("Edith Ramirez", "Accesschile")      
    """

    def __init__(self):
        self._validar_config()
        self.client = Groq(api_key=os.getenv("GROQ_API_KEY"))
        self._cache = {}

    def es_persona(self, nombre: str, empresa: str) -> bool:
        """
        Retorna True si el nombre es de una persona real.
        Retorna False si parece empresa, bot o nombre inválido.
        """
        nombre  = nombre.strip()
        empresa = empresa.strip()

        if not nombre:
            log.info("  [Names] Sin nombre → rechazar")
            return False

        # Filtro 1 — nombre igual a empresa
        if nombre.lower() == empresa.lower():
            log.info(f"  [Names] Nombre == Empresa '{nombre}' → rechazar")
            return False

        # Filtro 2 — Groq
        return self._consultar_groq(nombre)

    def _consultar_groq(self, nombre: str) -> bool:
        """Consulta Groq si el nombre es de una persona real."""
        nombre_lower = nombre.lower()

        if nombre_lower in self._cache:
            resultado = self._cache[nombre_lower]
            log.info(f"  [Names] Cache: '{nombre}' → {'persona' if resultado else 'no persona'}")
            return resultado

        prompt = f"""You are validating names for a certification system.
    Determine if this is a real human person's name or a company/organization name.

    Name: "{nombre}"

    Rules:
    - Answer YES if it looks like a real human name (from any country or culture)
    - Answer NO if it looks like a company, brand, organization, or is clearly not a human name
    - Answer only YES or NO, nothing else"""

        try:
            response = self.client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=5,
                temperature=0,
            )
            answer    = response.choices[0].message.content.strip().upper()
            resultado = answer.startswith("YES")

            self._cache[nombre_lower] = resultado
            log.info(f"  [Names] Groq: '{nombre}' → {'persona ✓' if resultado else 'no persona ✗'} (respuesta: {answer})")
            return resultado

        except Exception as e:
            log.warning(f"  [Names] Error Groq para '{nombre}': {e} → aprobando por defecto")
            return True
        
    def _validar_config(self):
        if not os.getenv("GROQ_API_KEY"):
            raise Exception("GROQ_API_KEY no está definido en .env")