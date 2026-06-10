# ============================================================
# database.py — version Supabase/PostgreSQL
# En lugar de un archivo .db local, los datos viven en
# Supabase y son accesibles desde cualquier computadora.
# ============================================================

import psycopg2                        # Librería para conectar Python con PostgreSQL
import psycopg2.extras                 # Permite acceder a columnas por nombre (como row_factory en SQLite)
import pandas as pd
import streamlit as st                 # Necesario para leer los Secrets de Streamlit


# ------------------------------------------------------------
# get_connection()
# Lee la URL de la base de datos desde los Secrets de Streamlit.
# Los Secrets se configuran en share.streamlit.io → Settings → Secrets
# y NUNCA se suben a GitHub — son privados y seguros.
# ------------------------------------------------------------
def get_connection():
    # st.secrets["DATABASE_URL"] lee el valor que guardaste en Streamlit Secrets
    # En local puedes crear un archivo .streamlit/secrets.toml con el mismo valor
    conn = psycopg2.connect(st.secrets["DATABASE_URL"])

    # autocommit=False significa que debes llamar conn.commit() manualmente
    # para confirmar los cambios — igual que en SQLite
    conn.autocommit = False
    return conn


# ------------------------------------------------------------
# init_db()
# Crea las tablas si no existen.
# PostgreSQL usa SERIAL en lugar de AUTOINCREMENT de SQLite.
# TEXT funciona igual en ambos.
# ------------------------------------------------------------
def init_db():
    conn = get_connection()

    # RealDictCursor permite acceder a columnas por nombre: row["state"]
    # Es el equivalente de row_factory = sqlite3.Row en SQLite
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # ----------------------------------------------------------
    # TABLA: projects
    # SERIAL = equivalente a AUTOINCREMENT en SQLite
    # ----------------------------------------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS projects (
            id         SERIAL PRIMARY KEY,
            state      TEXT   NOT NULL,
            county     TEXT   NOT NULL,
            city       TEXT,
            created_at TEXT   DEFAULT TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI:SS')
        )
    """)

    # ----------------------------------------------------------
    # TABLA: buildings
    # ----------------------------------------------------------
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS buildings (
            id         SERIAL  PRIMARY KEY,
            project_id INTEGER NOT NULL,
            name       TEXT    NOT NULL,
            type       TEXT    NOT NULL DEFAULT 'condo',
            assigned   INTEGER DEFAULT 0,
            mapped     INTEGER DEFAULT 0,
            unmapped   INTEGER DEFAULT 0,
            not_live   INTEGER DEFAULT 0,
            updated_at TEXT    DEFAULT TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI:SS'),
            FOREIGN KEY (project_id) REFERENCES projects(id)
        )
    """)

    conn.commit()
    cursor.close()
    conn.close()


# ------------------------------------------------------------
# add_project(state, county, city)
# En PostgreSQL se usa RETURNING id para obtener el ID
# del registro recién insertado — equivalente a lastrowid en SQLite.
# ------------------------------------------------------------
def add_project(state, county, city=None):
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    # RETURNING id le dice a PostgreSQL que retorne el ID del registro insertado
    # En SQLite usabas cursor.lastrowid — aquí es diferente
    cursor.execute("""
        INSERT INTO projects (state, county, city)
        VALUES (%s, %s, %s)
        RETURNING id
    """, (state, county, city))

    # fetchone() obtiene la primera (y única) fila del resultado
    new_id = cursor.fetchone()["id"]
    conn.commit()
    cursor.close()
    conn.close()
    return new_id


# ------------------------------------------------------------
# add_building()
# Igual que add_project pero para edificios.
# Nota: PostgreSQL usa %s como placeholder en lugar de ? de SQLite.
# ------------------------------------------------------------
def add_building(project_id, name, building_type="condo",
                 assigned=0, mapped=0, unmapped=0, not_live=0):
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute("""
        INSERT INTO buildings (project_id, name, type, assigned, mapped, unmapped, not_live)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING id
    """, (project_id, name, building_type, assigned, mapped, unmapped, not_live))

    new_id = cursor.fetchone()["id"]
    conn.commit()
    cursor.close()
    conn.close()
    return new_id


# ------------------------------------------------------------
# update_building()
# NOW() en PostgreSQL es equivalente a CURRENT_TIMESTAMP en SQLite.
# ------------------------------------------------------------
def update_building(building_id, name, building_type, assigned, mapped, unmapped, not_live):
    conn = get_connection()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    
    print(f"building_id: {building_id} tipo: {type(building_id)}")
    print(f"name: {name} tipo: {type(name)}")
    print(f"building_type: {building_type} tipo: {type(building_type)}")
    print(f"assigned: {assigned} tipo: {type(assigned)}")
    print(f"mapped: {mapped} tipo: {type(mapped)}")
    print(f"unmapped: {unmapped} tipo: {type(unmapped)}")
    print(f"not_live: {not_live} tipo: {type(not_live)}")

    cursor.execute("""
        UPDATE buildings
        SET name       = %s,
            type       = %s,
            assigned   = %s,
            mapped     = %s,
            unmapped   = %s,
            not_live   = %s,
            updated_at = TO_CHAR(NOW(), 'YYYY-MM-DD HH24:MI:SS')
        WHERE id = %s
    """, (name, building_type, assigned, mapped, unmapped, not_live, building_id))

    conn.commit()
    cursor.close()
    conn.close()


# ------------------------------------------------------------
# get_all_projects()
# pd.read_sql_query funciona igual con PostgreSQL que con SQLite.
# Solo cambia la conexión que se le pasa.
# ------------------------------------------------------------
def get_all_projects():
    conn = get_connection()

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

    def make_label(row):
        label = f"{row['state']} — {row['county']}"
        if row['city']:
            label += f" — {row['city']}"
        return label

    df["label"] = df.apply(make_label, axis=1)
    return df


# ------------------------------------------------------------
# get_buildings_by_project(project_id)
# ------------------------------------------------------------
def get_buildings_by_project(project_id):
    conn = get_connection()

    df = pd.read_sql_query("""
        SELECT
            id, name, type, assigned, mapped, unmapped, not_live,
            (assigned - mapped - unmapped - not_live) AS left_to_review,
            updated_at
        FROM buildings
        WHERE project_id = %s
        ORDER BY type, name
    """, conn, params=(project_id,))

    conn.close()
    return df


# ------------------------------------------------------------
# get_full_summary()
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
            (b.assigned - b.mapped - b.unmapped - b.not_live) AS left_to_review,
            b.updated_at
        FROM buildings b
        JOIN projects p ON p.id = b.project_id
        ORDER BY p.state, p.county, p.city, b.type, b.name
    """, conn)

    conn.close()

    def make_label(row):
        label = f"{row['state']} — {row['county']}"
        if row['city']:
            label += f" — {row['city']}"
        return label

    df["project_label"] = df.apply(make_label, axis=1)
    return df


# ------------------------------------------------------------
# delete_building(building_id)
# ------------------------------------------------------------
def delete_building(building_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM buildings WHERE id = %s", (building_id,))
    conn.commit()
    cursor.close()
    conn.close()


# ------------------------------------------------------------
# delete_project(project_id)
# Primero borra los edificios hijos, luego el proyecto padre.
# ------------------------------------------------------------
def delete_project(project_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM buildings WHERE project_id = %s", (project_id,))
    cursor.execute("DELETE FROM projects WHERE id = %s", (project_id,))
    conn.commit()
    cursor.close()
    conn.close()
