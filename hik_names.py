"""
=============================================================================
HIK_NAMES — Validador de nombres (filtros locales + Google Gemini)
=============================================================================

Responsabilidad única:
  Determinar si un nombre es de una persona real o de una empresa/bot.

Flujo:
  1. Filtros locales rápidos: vacío, nombre == empresa, prefijo "Ing.",
     dígitos, puntos/comas, keywords corporativos
  2. Los que pasan filtros locales → se envían en lote a Gemini
  3. Si Gemini falla → manual review por precaución

Requiere en .env:
  GEMINI_API_KEY → API key de Google AI Studio

=============================================================================
"""

import json
import os
import re
import logging
import unicodedata
from google import genai
from dotenv import load_dotenv

load_dotenv()

log = logging.getLogger("HikBot")

SUFIJOS_CORPORATIVOS = frozenset({
    "sa", "sas", "srl", "ltda", "ltd", "llc", "corp", "inc",
    "ca", "cia", "gmbh", "plc", "ag", "nv", "bv",
    "corporation", "incorporated", "company",
})

KEYWORDS_CORPORATIVOS = frozenset({
    # Inglés
    "security", "systems", "system", "technology", "technologies",
    "solutions", "services", "consulting", "consultants",
    "group", "international", "global", "enterprise", "enterprises",
    "industries", "industrial", "engineering", "electronics",
    "communications", "networks", "networking", "integration", "integrations",
    "distributor", "distribution", "distributors", "wholesale",
    "construction", "trading", "import", "export",
    "association", "foundation", "institute", "university",
    "surveillance",
    # Español
    "seguridad", "sistemas", "tecnologia", "tecnologias",
    "soluciones", "servicios", "consultoria", "consultores",
    "grupo", "internacional", "comercial", "comercializadora",
    "ingenieria", "electronica",
    "comunicaciones", "redes", "integraciones", "integracion",
    "distribuidora", "construccion", "constructora",
    "instalaciones", "instaladora",
    "importadora", "exportadora",
    "asociacion", "fundacion", "instituto", "universidad",
    "vigilancia", "videovigilancia",
    "telecom", "telecomunicaciones", "telecomunicacion",
    "alarma", "alarmas", "monitoreo", "automatizacion",
    "corporativo", "empresa", "compania", "corporacion",
    # Industria CCTV
    "cctv", "hikvision", "dahua",
})


class HikNames:

    """
    Valida si un nombre corresponde a una persona real.
    Uso:
        validator = HikNames()
        es_persona = validator.es_persona("Edith Ramirez", "Accesschile")
        resultados = validator.validar_lote(["Edith Ramirez", "ABC Security"])
    """

    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            log.warning("  [Names] GEMINI_API_KEY no definida — solo se usarán filtros locales")
            self.client = None
        else:
            self.client = genai.Client(api_key=api_key)

    def es_persona(self, nombre: str, empresa: str) -> bool:
        nombre  = nombre.strip()
        empresa = empresa.strip()

        if not nombre:
            log.info("  [Names] Sin nombre → rechazar")
            return False

        if nombre.lower() == empresa.lower():
            log.info(f"  [Names] Nombre == Empresa '{nombre}' → manual review")
            return False

        nombre_lower = nombre.lower()

        if nombre_lower.startswith("ing.") or nombre_lower.startswith("ing "):
            log.warning(f"  [Names] '{nombre}' empieza con 'Ing.' — manual review")
            return False

        if any(c.isdigit() for c in nombre):
            log.warning(f"  [Names] '{nombre}' contiene números — manual review")
            return False

        if any(c in nombre for c in ['.', ',']):
            log.warning(f"  [Names] '{nombre}' contiene puntos o comas — manual review")
            return False

        if self._es_nombre_corporativo(nombre):
            log.warning(f"  [Names] '{nombre}' contiene keywords corporativos — manual review")
            return False

        return True

    def validar_lote(self, nombres: list[str]) -> dict[str, bool]:
        if not nombres:
            return {}

        if not self.client:
            log.info(f"  [Names] Sin Gemini — aprobando {len(nombres)} nombres por filtros locales")
            return {n: True for n in nombres}

        prompt = (
            "You are validating names for a certification system.\n"
            "For each name, determine if it is a real human person's name or a company/organization.\n\n"
            "Names:\n"
            + "\n".join(f'- "{n}"' for n in nombres) +
            "\n\nRules:\n"
            "- Answer YES if it looks like a real human name (from any country or culture)\n"
            "- Answer NO if it looks like a company, brand, organization, or is clearly not a human name\n"
            '- Respond ONLY with a JSON array, example: [{"name": "Juan", "is_person": true}, {"name": "Corp X", "is_person": false}]\n'
            "- No extra text, no markdown, no code fences, ONLY the JSON array"
        )

        try:
            response = self.client.models.generate_content(
                model="gemini-3.6-flash",
                contents=prompt,
            )
            texto = response.text.strip()
            if texto.startswith("```"):
                texto = texto.split("\n", 1)[1].rsplit("```", 1)[0].strip()

            resultados_lista = json.loads(texto)
            resultados = {}
            for item in resultados_lista:
                nombre = item.get("name", "")
                es_persona = item.get("is_person", False)
                resultados[nombre] = es_persona
                log.info(f"  [Names] Gemini: '{nombre}' → {'persona ✓' if es_persona else 'no persona ✗'}")

            for n in nombres:
                if n not in resultados:
                    log.warning(f"  [Names] Gemini no respondió para '{n}' — manual review")
                    resultados[n] = False

            return resultados

        except Exception as e:
            log.warning(f"  [Names] Error Gemini en lote: {type(e).__name__} — todos a manual review")
            return {n: False for n in nombres}

    def _es_nombre_corporativo(self, nombre: str) -> bool:
        nombre_norm = self._normalizar(nombre.lower())
        nombre_sin_puntos = nombre_norm.replace(".", "").replace(",", "")

        for sufijo in SUFIJOS_CORPORATIVOS:
            if nombre_sin_puntos.endswith(sufijo):
                return True

        palabras = set(re.split(r'\s+', nombre_norm))
        if palabras & KEYWORDS_CORPORATIVOS:
            return True

        return False

    def _normalizar(self, texto: str) -> str:
        nfkd = unicodedata.normalize('NFKD', texto)
        return ''.join(c for c in nfkd if not unicodedata.combining(c))
