"""
KnowledgeMatch - Consulta de la base de conocimiento
----------------------------------------------------
Demuestra que el sistema puede consultar los datos guardados en SQLite.

Uso (desde la carpeta del proyecto, con el entorno virtual activado):
    python src/consultar_datos.py            -> consulta a Daniel (EMP-001)
    python src/consultar_datos.py EMP-004    -> consulta a otro colaborador
"""

import sqlite3
import sys
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "knowledgematch.db"
NOMBRE_NIVEL = {0: "ninguno", 1: "básico", 2: "intermedio", 3: "avanzado"}


def consultar(con, sql, params=()):
    return pd.read_sql(sql, con, params=params)


def titulo(texto):
    print(f"\n--- {texto} " + "-" * max(0, 56 - len(texto)))


def main():
    if not DB_PATH.exists():
        print("No existe la base de datos. Primero ejecuta: python src/cargar_datos.py")
        return

    id_empleado = sys.argv[1] if len(sys.argv) > 1 else "EMP-001"
    con = sqlite3.connect(DB_PATH)
    pd.set_option("display.width", 120)

    # 1) Perfil del colaborador
    perfil = consultar(con, """
        SELECT e.id_empleado, e.nombre, e.puesto, o.nombre AS objetivo, p.nombre AS proyecto
        FROM empleados e
        JOIN objetivos o ON o.id_objetivo = e.id_objetivo
        JOIN proyectos p ON p.id_proyecto = e.id_proyecto
        WHERE e.id_empleado = ?""", (id_empleado,))

    if perfil.empty:
        print(f"No se encontró al colaborador {id_empleado}.")
        con.close()
        return

    print("=" * 60)
    print(" KnowledgeMatch · Consulta de la base de conocimiento")
    print("=" * 60)
    p = perfil.iloc[0]
    print(f"\n  Colaborador: {p['nombre']} ({p['id_empleado']}) · {p['puesto']}")
    print(f"  Objetivo:    {p['objetivo']}")
    print(f"  Proyecto:    {p['proyecto']}")

    # 2) Habilidades que conoce (relación "conoce")
    titulo("Habilidades que conoce")
    conoce = consultar(con, """
        SELECT h.nombre AS habilidad, eh.nivel
        FROM empleado_habilidad eh
        JOIN habilidades h ON h.id_habilidad = eh.id_habilidad
        WHERE eh.id_empleado = ?""", (id_empleado,))
    conoce["nivel"] = conoce["nivel"].map(NOMBRE_NIVEL)
    print(conoce.to_string(index=False) if not conoce.empty else "  (sin habilidades registradas)")

    # 3) Brecha de habilidades frente a su objetivo (relación "prioriza")
    titulo("Brecha frente a su objetivo")
    brecha = consultar(con, """
        SELECT h.nombre AS habilidad,
               oh.nivel_requerido,
               COALESCE(eh.nivel, 0) AS nivel_actual
        FROM empleados e
        JOIN objetivo_habilidad oh ON oh.id_objetivo = e.id_objetivo
        JOIN habilidades h         ON h.id_habilidad = oh.id_habilidad
        LEFT JOIN empleado_habilidad eh
               ON eh.id_empleado = e.id_empleado
              AND eh.id_habilidad = oh.id_habilidad
        WHERE e.id_empleado = ?""", (id_empleado,))
    brecha["estado"] = brecha.apply(
        lambda r: "FALTA" if r["nivel_actual"] < r["nivel_requerido"] else "cubierta", axis=1)
    faltantes = brecha[brecha["estado"] == "FALTA"]
    mostrar = brecha.copy()
    mostrar["nivel_requerido"] = mostrar["nivel_requerido"].map(NOMBRE_NIVEL)
    mostrar["nivel_actual"] = mostrar["nivel_actual"].map(NOMBRE_NIVEL)
    print(mostrar.to_string(index=False))

    # 4) Recursos del catálogo que desarrollan las habilidades faltantes
    titulo("Recursos que desarrollan las habilidades faltantes")
    if faltantes.empty:
        print("  El colaborador ya cubre todas las habilidades de su objetivo.")
    else:
        marcadores = ",".join("?" * len(faltantes))
        recursos = consultar(con, f"""
            SELECT r.id_recurso, r.titulo, r.tipo, h.nombre AS desarrolla
            FROM recurso_habilidad rh
            JOIN recursos r    ON r.id_recurso = rh.id_recurso
            JOIN habilidades h ON h.id_habilidad = rh.id_habilidad
            WHERE h.nombre IN ({marcadores}) AND r.recomendable = 1
            ORDER BY r.id_recurso""", tuple(faltantes["habilidad"]))
        if recursos.empty:
            print("  No hay recursos en el catálogo para estas habilidades.")
        else:
            print(recursos.to_string(index=False))

    con.close()
    print("\n" + "=" * 60)
    print(" Consulta completada ✔  (estos datos alimentan al recomendador)")
    print("=" * 60)


if __name__ == "__main__":
    main()
