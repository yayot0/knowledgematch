"""
KnowledgeMatch - Carga y limpieza de datos
------------------------------------------
Lee los archivos CSV de data/raw, aplica limpieza y validaciones,
y guarda la información en la base de datos SQLite data/knowledgematch.db.

Uso (desde la carpeta del proyecto, con el entorno virtual activado):
    python src/cargar_datos.py
"""

import sqlite3
import unicodedata
from pathlib import Path

import pandas as pd

# --- Rutas del proyecto ---------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "data" / "raw"
DB_PATH = BASE_DIR / "data" / "knowledgematch.db"

# Regla R1: solo existen tres niveles. Se guardan como número para compararlos.
NIVELES = {"basico": 1, "intermedio": 2, "avanzado": 3}

# Registro de lo que se limpia, para mostrarlo al final
reporte = []


def log(mensaje):
    print(f"  · {mensaje}")
    reporte.append(mensaje)


# --- Funciones de limpieza ------------------------------------------------
def quitar_acentos(texto):
    texto = unicodedata.normalize("NFD", texto)
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")


def leer_csv(nombre):
    """Lee un CSV y elimina espacios sobrantes al inicio y final de cada texto."""
    df = pd.read_csv(RAW_DIR / f"{nombre}.csv", dtype=str)
    for col in df.columns:
        antes = df[col].copy()
        df[col] = df[col].str.strip()
        cambios = (antes != df[col]).sum()
        if cambios:
            log(f"{nombre}: {cambios} valor(es) con espacios sobrantes en '{col}'")
    return df


def normalizar_nivel(df, columna, tabla):
    """Convierte 'Básico', 'basico ', 'Intermedio'... en 1, 2 o 3 (regla R1)."""
    originales = df[columna].copy()
    limpio = df[columna].str.lower().map(quitar_acentos)
    df[columna] = limpio.map(NIVELES)

    escritura_correcta = originales.isin(["básico", "intermedio", "avanzado"])
    corregidos = ~escritura_correcta & df[columna].notna()
    if corregidos.sum():
        log(f"{tabla}: {corregidos.sum()} nivel(es) con mayúsculas o sin acento normalizados")

    invalidos = df[columna].isna()
    if invalidos.sum():
        log(f"{tabla}: {invalidos.sum()} fila(s) eliminadas por nivel no válido")
        df = df[~invalidos]
    df[columna] = df[columna].astype(int)
    return df


def quitar_duplicados(df, llaves, tabla):
    duplicados = df.duplicated(subset=llaves).sum()
    if duplicados:
        log(f"{tabla}: {duplicados} fila(s) duplicada(s) eliminada(s)")
    return df.drop_duplicates(subset=llaves)


def validar_referencia(df, columna, ids_validos, tabla):
    """Elimina filas que apuntan a un registro que no existe."""
    invalidas = ~df[columna].isin(ids_validos)
    if invalidas.sum():
        ids = ", ".join(df.loc[invalidas, columna].unique())
        log(f"{tabla}: {invalidas.sum()} fila(s) eliminadas, '{columna}' inexistente ({ids})")
    return df[~invalidas]


# --- Esquema de la base de datos -----------------------------------------
ESQUEMA = """
CREATE TABLE habilidades (
    id_habilidad TEXT PRIMARY KEY,
    nombre       TEXT NOT NULL,
    categoria    TEXT
);
CREATE TABLE objetivos (
    id_objetivo TEXT PRIMARY KEY,
    nombre      TEXT NOT NULL,
    descripcion TEXT
);
CREATE TABLE proyectos (
    id_proyecto TEXT PRIMARY KEY,
    nombre      TEXT NOT NULL,
    estado      TEXT
);
CREATE TABLE empleados (
    id_empleado TEXT PRIMARY KEY,
    nombre      TEXT NOT NULL,
    puesto      TEXT,
    intereses   TEXT,
    id_objetivo TEXT REFERENCES objetivos(id_objetivo),
    id_proyecto TEXT REFERENCES proyectos(id_proyecto)
);
CREATE TABLE recursos (
    id_recurso     TEXT PRIMARY KEY,
    titulo         TEXT NOT NULL,
    tipo           TEXT,
    descripcion    TEXT,
    duracion_horas INTEGER,
    nivel          INTEGER CHECK (nivel IN (1, 2, 3)),
    recomendable   INTEGER DEFAULT 1   -- 0 si no tiene habilidad asociada (regla R2)
);
CREATE TABLE empleado_habilidad (           -- relación "conoce"
    id_empleado  TEXT REFERENCES empleados(id_empleado),
    id_habilidad TEXT REFERENCES habilidades(id_habilidad),
    nivel        INTEGER CHECK (nivel IN (1, 2, 3)),
    PRIMARY KEY (id_empleado, id_habilidad)
);
CREATE TABLE objetivo_habilidad (           -- relación "prioriza"
    id_objetivo     TEXT REFERENCES objetivos(id_objetivo),
    id_habilidad    TEXT REFERENCES habilidades(id_habilidad),
    nivel_requerido INTEGER CHECK (nivel_requerido IN (1, 2, 3)),
    PRIMARY KEY (id_objetivo, id_habilidad)
);
CREATE TABLE proyecto_habilidad (           -- relación "requiere"
    id_proyecto     TEXT REFERENCES proyectos(id_proyecto),
    id_habilidad    TEXT REFERENCES habilidades(id_habilidad),
    nivel_requerido INTEGER CHECK (nivel_requerido IN (1, 2, 3)),
    PRIMARY KEY (id_proyecto, id_habilidad)
);
CREATE TABLE recurso_habilidad (            -- relación "desarrolla"
    id_recurso           TEXT REFERENCES recursos(id_recurso),
    id_habilidad         TEXT REFERENCES habilidades(id_habilidad),
    nivel_que_desarrolla INTEGER CHECK (nivel_que_desarrolla IN (1, 2, 3)),
    PRIMARY KEY (id_recurso, id_habilidad)
);
CREATE TABLE recurso_prerrequisito (        -- relación "prerrequisito"
    id_recurso   TEXT REFERENCES recursos(id_recurso),
    id_habilidad TEXT REFERENCES habilidades(id_habilidad),
    nivel_minimo INTEGER CHECK (nivel_minimo IN (1, 2, 3)),
    PRIMARY KEY (id_recurso, id_habilidad)
);
CREATE TABLE evaluaciones (                 -- relaciones "completó" y "valora"
    id_evaluacion TEXT PRIMARY KEY,
    id_empleado   TEXT REFERENCES empleados(id_empleado),
    id_recurso    TEXT REFERENCES recursos(id_recurso),
    calificacion  INTEGER CHECK (calificacion BETWEEN 1 AND 5),
    comentario    TEXT,
    fecha         TEXT
);
"""


# --- Proceso principal ----------------------------------------------------
def main():
    print("=" * 60)
    print(" KnowledgeMatch · Carga y limpieza de datos")
    print("=" * 60)

    # 1) Lectura y limpieza de espacios
    print("\n[1/4] Leyendo archivos CSV y limpiando espacios...")
    habilidades = leer_csv("habilidades")
    objetivos = leer_csv("objetivos")
    proyectos = leer_csv("proyectos")
    empleados = leer_csv("empleados")
    recursos = leer_csv("recursos")
    emp_hab = leer_csv("empleado_habilidad")
    obj_hab = leer_csv("objetivo_habilidad")
    pro_hab = leer_csv("proyecto_habilidad")
    rec_hab = leer_csv("recurso_habilidad")
    rec_pre = leer_csv("recurso_prerrequisito")
    evaluaciones = leer_csv("evaluaciones")

    # 2) Normalización de niveles (regla R1) y tipos de dato
    print("\n[2/4] Normalizando niveles (básico=1, intermedio=2, avanzado=3)...")
    recursos = normalizar_nivel(recursos, "nivel", "recursos")
    emp_hab = normalizar_nivel(emp_hab, "nivel", "empleado_habilidad")
    obj_hab = normalizar_nivel(obj_hab, "nivel_requerido", "objetivo_habilidad")
    pro_hab = normalizar_nivel(pro_hab, "nivel_requerido", "proyecto_habilidad")
    rec_hab = normalizar_nivel(rec_hab, "nivel_que_desarrolla", "recurso_habilidad")
    rec_pre = normalizar_nivel(rec_pre, "nivel_minimo", "recurso_prerrequisito")
    recursos["duracion_horas"] = pd.to_numeric(recursos["duracion_horas"], errors="coerce").astype("Int64")
    evaluaciones["calificacion"] = pd.to_numeric(evaluaciones["calificacion"], errors="coerce")

    # 3) Duplicados, integridad de relaciones y reglas de negocio
    print("\n[3/4] Validando duplicados, relaciones y reglas...")
    ids_hab = set(habilidades["id_habilidad"])
    ids_emp = set(empleados["id_empleado"])
    ids_rec = set(recursos["id_recurso"])

    emp_hab = quitar_duplicados(emp_hab, ["id_empleado", "id_habilidad"], "empleado_habilidad")
    obj_hab = quitar_duplicados(obj_hab, ["id_objetivo", "id_habilidad"], "objetivo_habilidad")
    pro_hab = quitar_duplicados(pro_hab, ["id_proyecto", "id_habilidad"], "proyecto_habilidad")
    rec_hab = quitar_duplicados(rec_hab, ["id_recurso", "id_habilidad"], "recurso_habilidad")
    rec_pre = quitar_duplicados(rec_pre, ["id_recurso", "id_habilidad"], "recurso_prerrequisito")

    empleados = validar_referencia(empleados, "id_objetivo", set(objetivos["id_objetivo"]), "empleados")
    empleados = validar_referencia(empleados, "id_proyecto", set(proyectos["id_proyecto"]), "empleados")
    emp_hab = validar_referencia(emp_hab, "id_empleado", ids_emp, "empleado_habilidad")
    emp_hab = validar_referencia(emp_hab, "id_habilidad", ids_hab, "empleado_habilidad")
    obj_hab = validar_referencia(obj_hab, "id_habilidad", ids_hab, "objetivo_habilidad")
    pro_hab = validar_referencia(pro_hab, "id_habilidad", ids_hab, "proyecto_habilidad")
    rec_hab = validar_referencia(rec_hab, "id_recurso", ids_rec, "recurso_habilidad")
    rec_hab = validar_referencia(rec_hab, "id_habilidad", ids_hab, "recurso_habilidad")
    rec_pre = validar_referencia(rec_pre, "id_recurso", ids_rec, "recurso_prerrequisito")
    rec_pre = validar_referencia(rec_pre, "id_habilidad", ids_hab, "recurso_prerrequisito")
    evaluaciones = validar_referencia(evaluaciones, "id_empleado", ids_emp, "evaluaciones")
    evaluaciones = validar_referencia(evaluaciones, "id_recurso", ids_rec, "evaluaciones")

    fuera_rango = ~evaluaciones["calificacion"].between(1, 5)
    if fuera_rango.sum():
        log(f"evaluaciones: {fuera_rango.sum()} fila(s) eliminadas por calificación fuera de 1-5")
        evaluaciones = evaluaciones[~fuera_rango]
    evaluaciones["calificacion"] = evaluaciones["calificacion"].astype(int)

    # Regla R2: todo recurso recomendable debe desarrollar al menos una habilidad
    sin_habilidad = ~recursos["id_recurso"].isin(rec_hab["id_recurso"])
    recursos["recomendable"] = (~sin_habilidad).astype(int)
    for _, r in recursos[sin_habilidad].iterrows():
        log(f"recursos: '{r['titulo']}' ({r['id_recurso']}) no tiene habilidad asociada "
            f"-> se marca como no recomendable (regla R2)")

    # 4) Guardado en SQLite
    print("\n[4/4] Guardando en la base de datos SQLite...")
    if DB_PATH.exists():
        DB_PATH.unlink()
    con = sqlite3.connect(DB_PATH)
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript(ESQUEMA)

    tablas = {
        "habilidades": habilidades,
        "objetivos": objetivos,
        "proyectos": proyectos,
        "empleados": empleados,
        "recursos": recursos,
        "empleado_habilidad": emp_hab,
        "objetivo_habilidad": obj_hab,
        "proyecto_habilidad": pro_hab,
        "recurso_habilidad": rec_hab,
        "recurso_prerrequisito": rec_pre,
        "evaluaciones": evaluaciones,
    }
    for nombre, df in tablas.items():
        df.to_sql(nombre, con, if_exists="append", index=False)
    con.commit()

    # Resumen
    print(f"\n  Base de datos creada: {DB_PATH.relative_to(BASE_DIR)}\n")
    print(f"  {'Tabla':<24}{'Registros':>10}")
    print(f"  {'-' * 34}")
    for nombre in tablas:
        total = con.execute(f"SELECT COUNT(*) FROM {nombre}").fetchone()[0]
        print(f"  {nombre:<24}{total:>10}")
    con.close()

    print(f"\n  Correcciones aplicadas durante la limpieza: {len(reporte)}")
    print("=" * 60)
    print(" Carga completada ✔")
    print("=" * 60)


if __name__ == "__main__":
    main()
