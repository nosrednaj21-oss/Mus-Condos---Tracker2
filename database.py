import pandas as pd
from sqlalchemy import create_engine

# ⚠️ AQUÍ ESTÁ LA LÍNEA NUEVA: Pon tu enlace real de Supabase con tu contraseña real
DATABASE_URL = postgresql+psycopg2://postgres:SeQpUKFDP7zdoN01@db.fmhnlfvonbewihkbgoer.supabase.co:5432/postgres

def get_connection():
    """Crea y retorna el motor de conexión a Supabase."""
    engine = create_engine(DATABASE_URL)
    return engine

def add_project(state, county, city=None):
    """Inserta un nuevo proyecto en la nube y retorna el ID generado."""
    engine = get_connection()
    query = """
        INSERT INTO projects (state, county, city)
        VALUES (%(state)s, %(county)s, %(city)s)
        RETURNING id;
    """
    with engine.begin() as conn:
        result = conn.execute(pd.io.sql.SQLTextClauseRow(query), {"state": state, "county": county, "city": city})
        new_id = result.fetchone()[0]
    return new_id

def add_building(project_id, name, building_type="condo", assigned=0, mapped=0, unmapped=0, not_live=0):
    """Agrega un edificio amarrado a un proyecto en Supabase."""
    engine = get_connection()
    query = """
        INSERT INTO buildings (project_id, name, type, assigned, mapped, unmapped, not_live)
        VALUES (%(project_id)s, %(name)s, %(type)s, %(assigned)s, %(mapped)s, %(unmapped)s, %(not_live)s);
    """
    with engine.begin() as conn:
        conn.execute(pd.io.sql.SQLTextClauseRow(query), {
            "project_id": project_id, "name": name, "type": building_type,
            "assigned": assigned, "mapped": mapped, "unmapped": unmapped, "not_live": not_live
        })

def update_building(building_id, name, building_type, assigned, mapped, unmapped, not_live):
    """Actualiza los conteos de un edificio y actualiza su estampa de tiempo."""
    engine = get_connection()
    query = """
        UPDATE buildings
        SET name = %(name)s, type = %(type)s, assigned = %(assigned)s, 
            mapped = %(mapped)s, unmapped = %(unmapped)s, not_live = %(not_live)s, 
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %(id)s;
    """
    with engine.begin() as conn:
        conn.execute(pd.io.sql.SQLTextClauseRow(query), {
            "name": name, "type": building_type, "assigned": assigned,
            "mapped": mapped, "unmapped": unmapped, "not_live": not_live, "id": building_id
        })

def get_all_projects():
    """Descarga todos los proyectos y genera las etiquetas para los dropdowns."""
    engine = get_connection()
    df = pd.read_sql_query("""
        SELECT p.id, p.state, p.county, p.city, COUNT(b.id) AS total_buildings
        FROM projects p
        LEFT JOIN buildings b ON b.project_id = p.id
        GROUP BY p.id, p.state, p.county, p.city
        ORDER BY p.state, p.county, p.city
    """, engine)
    
    if df.empty:
        return df

    def make_label(row):
        label = f"{row['state']} — {row['county']}"
        if row['city']: 
            label += f" — {row['city']}"
        return label

    df["label"] = df.apply(make_label, axis=1)
    return df

def get_buildings_by_project(project_id):
    """Obtiene los edificios filtrados por proyecto calculando el residuo matemáticamente."""
    engine = get_connection()
    df = pd.read_sql_query("""
        SELECT id, name, type, assigned, mapped, unmapped, not_live, 
               (assigned - mapped - unmapped - not_live) AS left_to_review, 
               updated_at
        FROM buildings
        WHERE project_id = %(project_id)s
        ORDER BY type, name
    """, engine, params={"project_id": project_id})
    return df

def get_full_summary():
    """Consulta global uniendo tablas para las métricas e informes del Dashboard."""
    engine = get_connection()
    df = pd.read_sql_query("""
        SELECT p.state, p.county, p.city, b.id AS building_id, b.name AS building_name,
               b.type, b.assigned, b.mapped, b.unmapped, b.not_live,
               (b.assigned - b.mapped - b.unmapped - b.not_live) AS left_to_review, 
               b.updated_at
        FROM buildings b
        JOIN projects p ON p.id = b.project_id
        ORDER BY p.state, p.county, p.city, b.type, b.name
    """, engine)

    if df.empty:
        df["project_label"] = pd.Series(dtype='object')
        return df

    def make_label(row):
        label = f"{row['state']} — {row['county']}"
        if row['city']: 
            label += f" — {row['city']}"
        return label

    df["project_label"] = df.apply(make_label, axis=1)
    return df

def delete_building(building_id):
    """Elimina un edificio individual de la nube."""
    engine = get_connection()
    with engine.begin() as conn:
        conn.execute(pd.io.sql.SQLTextClauseRow("DELETE FROM buildings WHERE id = %(id)s;"), {"id": building_id})

def delete_project(project_id):
    """Elimina un proyecto completo (la restricción ON DELETE CASCADE borrará sus edificios automáticamente)."""
    engine = get_connection()
    with engine.begin() as conn:
        conn.execute(pd.io.sql.SQLTextClauseRow("DELETE FROM projects WHERE id = %(id)s;"), {"id": project_id})
