# ============================================================
# database.py  —  v3
# Dos tablas: projects (ubicación) y buildings (edificios).
# Un proyecto tiene muchos edificios.
# Los conteos viven en cada edificio individual.
# ============================================================

import sqlite3
import pandas as pd
from datetime import datetime

DB_NAME = "mus_condo.db"


# ------------------------------------------------------------
# get_connection()
# Abre la conexión al archivo de base de datos.
# row_factory permite leer columnas por nombre (row["state"]).
# ------------------------------------------------------------
def get_connection():
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn


# ------------------------------------------------------------
# init_db()
# Crea las dos tablas si no existen.
# Llámala una vez al iniciar la app.
# ------------------------------------------------------------
def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    # ----------------------------------------------------------
    # TABLA: projects
    # Solo guarda la ubicación geográfica.
    # city puede ser NULL cuando el contrato cubre todo el condado.
    # ----------------------------------------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            state      TEXT    NOT NULL,
            county     TEXT    NOT NULL,
            city       TEXT,                      -- NULL si es contrato de condado
            created_at TEXT    DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # ----------------------------------------------------------
    # TABLA: buildings
    # Cada edificio pertenece a un proyecto (project_id).
    # Guarda nombre, tipo y los 4 conteos individuales.
    # ----------------------------------------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS buildings (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER NOT NULL,           -- Liga con la tabla projects
            name       TEXT    NOT NULL,           -- Nombre del edificio (street view / public records)
            type       TEXT    NOT NULL DEFAULT 'condo',  -- "condo" o "MUS"
            assigned   INTEGER DEFAULT 0,
            mapped     INTEGER DEFAULT 0,
            unmapped   INTEGER DEFAULT 0,
            not_live   INTEGER DEFAULT 0,
            updated_at TEXT    DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (project_id) REFERENCES projects(id)
        )
    """)

    conn.commit()
    conn.close()


# ------------------------------------------------------------
# add_project(state, county, city)
# Inserta un nuevo proyecto.
# city es opcional — queda NULL si no se pasa.
# Retorna el ID del proyecto creado.
# ------------------------------------------------------------
def add_project(state, county, city=None):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO projects (state, county, city)
        VALUES (?, ?, ?)
    """, (state, county, city))

    new_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return new_id


# ------------------------------------------------------------
# add_building(project_id, name, type, assigned, mapped, unmapped, not_live)
# Agrega un edificio a un proyecto existente.
# Los conteos son opcionales — por defecto arrancan en 0.
# Retorna el ID del edificio creado.
# ------------------------------------------------------------
def add_building(project_id, name, building_type="condo",
                 assigned=0, mapped=0, unmapped=0, not_live=0):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO buildings (project_id, name, type, assigned, mapped, unmapped, not_live)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (project_id, name, building_type, assigned, mapped, unmapped, not_live))

    new_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return new_id


# ------------------------------------------------------------
# update_building(building_id, name, type, assigned, mapped, unmapped, not_live)
# Actualiza los datos y conteos de un edificio existente.
# También registra la fecha de la última actualización.
# ------------------------------------------------------------
def update_building(building_id, name, building_type, assigned, mapped, unmapped, not_live):
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        UPDATE buildings
        SET name       = ?,
            type       = ?,
            assigned   = ?,
            mapped     = ?,
            unmapped   = ?,
            not_live   = ?,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
    """, (name, building_type, assigned, mapped, unmapped, not_live, building_id))

    conn.commit()
    conn.close()


# ------------------------------------------------------------
# get_all_projects()
# Retorna todos los proyectos con una etiqueta legible.
# Ej: "Florida — Miami-Dade — Miami"
#     "Texas — Nelson County"  (sin ciudad)
# También incluye el total de edificios por proyecto.
# ------------------------------------------------------------
def get_all_projects():
    conn = get_connection()

    # Cuenta cuántos edificios tiene cada proyecto con un subquery
    df = pd.read_sql_query("""
        SELECT
            p.id,
            p.state,
            p.county,
            p.city,
            p.created_at,
            COUNT(b.id) AS total_buildings
        FROM projects p
        LEFT JOIN buildings b ON b.project_id = p.id
        GROUP BY p.id
        ORDER BY p.state, p.county, p.city
    """, conn)

    conn.close()

    # Construye etiqueta legible para dropdowns
    def make_label(row):
        label = f"{row['state']} — {row['county']}"
        if row['city']:
            label += f" — {row['city']}"
        return label

    df["label"] = df.apply(make_label, axis=1)
    return df


# ------------------------------------------------------------
# get_buildings_by_project(project_id)
# Retorna todos los edificios de un proyecto específico.
# ------------------------------------------------------------
def get_buildings_by_project(project_id):
    conn = get_connection()

    df = pd.read_sql_query("""
        SELECT id, name, type, assigned, mapped, unmapped, not_live, updated_at
        FROM buildings
        WHERE project_id = ?
        ORDER BY type, name
    """, conn, params=(project_id,))

    conn.close()
    return df


# ------------------------------------------------------------
# get_full_summary()
# Retorna todos los edificios con su proyecto incluido.
# Útil para el Dashboard general.
# ------------------------------------------------------------
def get_full_summary():
    conn = get_connection()

    df = pd.read_sql_query("""
        SELECT
            p.state,
            p.county,
            p.city,
            b.id         AS building_id,
            b.name       AS building_name,
            b.type,
            b.assigned,
            b.mapped,
            b.unmapped,
            b.not_live,
            b.updated_at
        FROM buildings b
        JOIN projects p ON p.id = b.project_id
        ORDER BY p.state, p.county, p.city, b.type, b.name
    """, conn)

    conn.close()

    # Etiqueta del proyecto para agrupar en gráficas
    def make_label(row):
        label = f"{row['state']} — {row['county']}"
        if row['city']:
            label += f" — {row['city']}"
        return label

    df["project_label"] = df.apply(make_label, axis=1)
    return df


# ------------------------------------------------------------
# delete_building(building_id)
# Elimina un edificio por su ID.
# ------------------------------------------------------------
def delete_building(building_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM buildings WHERE id = ?", (building_id,))
    conn.commit()
    conn.close()


# ------------------------------------------------------------
# delete_project(project_id)
# Elimina un proyecto y todos sus edificios.
# Primero borra los edificios (hijos) para no romper
# la integridad referencial de la base de datos.
# ------------------------------------------------------------
def delete_project(project_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM buildings WHERE project_id = ?", (project_id,))
    cursor.execute("DELETE FROM projects WHERE id = ?", (project_id,))
    conn.commit()
    conn.close()


# ------------------------------------------------------------
# Bloque de prueba — solo se ejecuta con: python database.py
# Crea la DB e inserta proyectos y edificios de ejemplo.
# ------------------------------------------------------------