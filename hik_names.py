"""
=============================================================================
HIK_NAMES — Validador de nombres (local, sin dependencias externas)
=============================================================================

Responsabilidad única:
  Determinar si un nombre es de una persona real o de una empresa/bot
  usando filtros locales basados en keywords.

Flujo:
  1. Filtros rápidos: vacío, nombre == empresa, prefijo "Ing.", dígitos, puntos/comas
  2. Detección de keywords corporativos (español e inglés)
  3. Si pasa todos los filtros → es persona (aprobar)

=============================================================================
"""

import re
import logging
import unicodedata

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
    """

    def __init__(self):
        pass

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

        log.info(f"  [Names] '{nombre}' → persona ✓")
        return True

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
