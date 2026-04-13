from hik_names import HikNames

validator = HikNames()

casos = [
    ("Edith Ramirez",        "assvirt"),
    ("Videovigilancia SYA",  "Videovigilancia SYA"),
    ("Robinson Ravelo",      "videovigilancia SYA"),
    ("Jesus Muñoz",          "GCC"),
    ("GCC",                  "GCC"),
    ("Accesschile",          "Accesschile"),
    ("Kevin Seguel",         "Accesschile"),
    ("Lahijanny Ruby",       "B2B"),
    ("Isaac Quiroz",         "Insignal México"),
]

print("\n" + "="*55)
for nombre, empresa in casos:
    resultado = validator.es_persona(nombre, empresa)
    estado = "✓ APROBAR" if resultado else "✗ RECHAZAR"
    print(f"  {estado} — {nombre} / {empresa}")
print("="*55 + "\n")