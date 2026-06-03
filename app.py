# ============================================================
# app.py  —  v3
# Para correr: streamlit run app.py
# ============================================================

import base64
import streamlit as st
import pandas as pd
import plotly.express as px
from database import (
    add_project,
    add_building,
    update_building,
    get_all_projects,
    get_buildings_by_project,
    get_full_summary,
    delete_building,
    delete_project,
)

# ------------------------------------------------------------
# Configuración de página — siempre debe ir primero
# ------------------------------------------------------------
st.set_page_config(
    page_title="Mus-Condos Tracker",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded",
)

with open("background.webp", "rb") as f:
    bg_data = base64.b64encode(f.read()).decode()

st.markdown(f"""
    <style>
        [data-testid="stMetric"] {{
            background-color: #f0f4f8;
            border-radius: 10px;
            padding: 14px;
        }}

        .stApp {{
            background-image: url("data:image/webp;base64,{bg_data}");
            background-size: cover;
            background-position: center;
            background-attachment: fixed;
        }}
    </style>
""", unsafe_allow_html=True)

# Colores consistentes para los 4 estados
STATUS_COLORS = {
    "assigned": "#2ecc71",
    "mapped":   "#04D9FF",
    "unmapped": "#e67e22",
    "not_live": "#ffd343",

}

@st.cache_resource(show_spinner=False)
 def setup():
    init_db()

setup()


# ============================================================
# SIDEBAR
# ============================================================
with st.sidebar:
    st.title("🏢 Mus&Condos")
    st.markdown("---")

    page = st.radio(
        "Ir a:",
        [
            "📊 Dashboard",
            "🏗️ Edificios por Proyecto",
            "✏️ Actualizar Edificio",
            "➕ Nuevo Proyecto",
            "➕ Nuevo Edificio",
            "🗑️ Eliminar",
        ],
        label_visibility="collapsed",
    )


# ============================================================
# PÁGINA 1: DASHBOARD
# Métricas globales y gráfica agrupada por proyecto.
# ============================================================
if page == "📊 Dashboard":
    st.title("📊 Dashboard")

    df = get_full_summary()

    if df.empty:
        st.info("No hay datos aún. Ve a **➕ Nuevo Proyecto** para empezar.")
        st.stop()
        
    if "left_to_review" not in df.columns:
        df["left_to_review"] = df["assigned"] - df["mapped"] - df["unmapped"] - df["not_live"]

    # ----------------------------------------------------------
    # MÉTRICAS GLOBALES — suma de todos los edificios
    # ----------------------------------------------------------
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total Assigned",   int(df["assigned"].sum()))
    c2.metric("Total Mapped",     int(df["mapped"].sum()))
    c3.metric("Total Unmapped",   int(df["unmapped"].sum()))
    c4.metric("Total Not Live",   int(df["not_live"].sum()))
    c5.metric("Left to review",   int(df["left_to_review"].sum()))

    st.markdown("---")

    # ----------------------------------------------------------
    # FILTROS
    # ----------------------------------------------------------
    col1, col2, col3 = st.columns(3)
    with col1:
        sel_states = st.multiselect("State",  options=sorted(df["state"].unique()))
    with col2:
        sel_types  = st.multiselect("Type",    options=["Condo", "MUS"])
    with col3:
        sel_counties = st.multiselect("County", options=sorted(df["county"].unique()))

    filtered = df.copy()
    if sel_states:
        filtered = filtered[filtered["state"].isin(sel_states)]
    if sel_types:
        filtered = filtered[filtered["type"].isin(sel_types)]
    if sel_counties:
        filtered = filtered[filtered["county"].isin(sel_counties)]

    # ----------------------------------------------------------
    # GRÁFICA — un punto por edificio, agrupados por proyecto
    # ----------------------------------------------------------
    chart_df = filtered.melt(
        id_vars=["building_name", "project_label", "type"],
        value_vars=["assigned", "mapped", "unmapped", "not_live"],
        var_name="Status",
        value_name="Cantidad",
    )

    fig = px.bar(
        chart_df,
        x="building_name",
        y="Cantidad",
        color="Status",
        barmode="group",
        color_discrete_map=STATUS_COLORS,
        facet_col="project_label",      # Separa la gráfica en paneles por proyecto
        facet_col_wrap=2,               # Máximo 2 proyectos por fila
        labels={"building_name": "Edificio"},
        title="Listings por Edificio",
        hover_data=["project_label", "type"],
    )
    fig.update_layout(height=500)
    fig.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))  # Limpia etiquetas de paneles
    st.plotly_chart(fig, use_container_width=True)

    # ----------------------------------------------------------
    # TABLA COMPLETA
    # ----------------------------------------------------------
    st.subheader("Todos los edificios")
    st.dataframe(
        filtered[[
            "project_label", "building_name", "type",
            "assigned", "mapped", "unmapped", "not_live", "updated_at"
        ]].rename(columns={
            "project_label":  "Proyecto",
            "building_name":  "Edificio",
            "type":           "Tipo",
            "assigned":       "Assigned",
            "mapped":         "Mapped",
            "unmapped":       "Unmapped",
            "not_live":       "Not Live",
            "left_to_review": "Left to review",
            "updated_at":     "Actualizado",
        }),
        use_container_width=True,
        hide_index=True,
    )


# ============================================================
# PÁGINA 2: EDIFICIOS POR PROYECTO
# Seleccionas un proyecto y ves todos sus edificios con totales.
# ============================================================
elif page == "🏗️ Edificios por Proyecto":
    st.title("🏗️ Edificios por Proyecto")

    df_projects = get_all_projects()

    if df_projects.empty:
        st.info("No hay proyectos aún.")
        st.stop()

    selected_label = st.selectbox("Selecciona un proyecto:", df_projects["label"].tolist())
    row_proj = df_projects[df_projects["label"] == selected_label].iloc[0]
    project_id = int(row_proj["id"])

    df_buildings = get_buildings_by_project(project_id)

    if df_buildings.empty:
        st.info("Este proyecto no tiene edificios. Ve a **➕ Nuevo Edificio** para agregar uno.")
        st.stop()
    if "left_to_review" not in df_buildings.columns:
        df_buildings["left_to_review"] = df_buildings["assigned"] - df_buildings["mapped"] - df_buildings["unmapped"] - df_buildings["not_live"]

    # Totales del proyecto (suma de todos sus edificios)
    st.subheader(f"Totales — {selected_label}")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Assigned", int(df_buildings["assigned"].sum()))
    c2.metric("Mapped",   int(df_buildings["mapped"].sum()))
    c3.metric("Unmapped", int(df_buildings["unmapped"].sum()))
    c4.metric("Not Live", int(df_buildings["not_live"].sum()))
    c5.metric("Left to review", int(df_buildings["left_to_review"].sum()))

    st.markdown("---")

    # Tabla de edificios del proyecto
    st.subheader("Edificios")
    st.dataframe(
        df_buildings[["name", "type", "assigned", "mapped", "unmapped", "not_live", "left_to_review", "updated_at"]].rename(columns={
            "name":           "Edificio",
            "type":           "Tipo",
            "assigned":       "Assigned",
            "mapped":         "Mapped",
            "unmapped":       "Unmapped",
            "not_live":       "Not Live",
            "left_to_review": "Left to review",
            "updated_at":     "Actualizado",
        }),
        use_container_width=True,
        hide_index=True,
    )
    
    #Reporte en texto code
    st.markdown("---")
    st.subheader("📋 Herramientas de Reporte Semanal")
    
    tab_texto, tab_archivo = st.tabs(["✉️ Reporte en Texto para Jira", "💾 Descargar Archivo (Excel/CSV)"])
    
    with tab_texto:
        total_assigned = int(df_buildings["assigned"].sum())
        total_mapped = int(df_buildings["mapped"].sum())
        total_unmapped = int(df_buildings["unmapped"].sum())
        total_not_live = int(df_buildings["not_live"].sum())
        total_left = int(df_buildings["left_to_review"].sum())
        
        percentage_advance = round((total_mapped / total_assigned * 100), 1) if total_assigned > 0 else 0
        
        texto_informe = f"""### 📊 INFORME SEMANAL DE PROYECTO
**Proyecto:** {selected_label}
**Estado de Avance General:** {percentage_advance}%

#### 📈 RESUMEN DE METRICAS GLOBALES
* **Total Listings Asignados:** {total_assigned}
* **Total Mapeados:** {total_mapped}
* **Total No Mapeados:** {total_unmapped}
* **Total Not Live:** {total_not_live}
* **Total Left to Map (Sin Revisar):** {total_left}

#### 🏢 DETALLE POR CONDO / MUS
| Condo / MU | Tipo | Asignados | Mapeados | No Mapeados | Not Live | Left to Map |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
"""

        for _, row in df_buildings.iterrows():
            texto_informe += f"| {row['name']} | {row['type']} | {int(row['assigned'])} | {int(row['mapped'])} | {int(row['unmapped'])} | {int(row['not_live'])} | **{int(row['left_to_review'])}** |\n"
        
        texto_informe += "\n*Informe generado automáticamente por Mor.*"
        
        st.text_area(
            label="Selecciona el texto y pégalo mor:",
            value=texto_informe,
            height=300
        )
    
    with tab_archivo:
        st.write("Genera un archivo compatible con Excel con toda la información del proyecto actual:")
        
        reporte_df = df_buildings[[
            "name", "type", "assigned", "mapped", "unmapped", "not_live", "left_to_review"
        ]].rename(columns={
            "name":           "Condo / MU",
            "type":           "Tipo",
            "assigned":       "Listings Asignados",
            "mapped":         "Mapeados",
            "unmapped":       "No Mapeados",
            "not_live":       "Not Live",
            "left_to_review": "Left to Map (Sin Revisar)"
        })
        
        csv_data = reporte_df.to_csv(index=False, sep=";", encoding="utf-8-sig")

        st.download_button(
            label="📥 Descargar Reporte Semanal (.csv)",
            data=csv_data,
            file_name=f"Reporte_Semanal_{selected_label.replace(' — ', '_')}.csv",
            mime="text/csv",
            use_container_width=True
        )

    # Gráfica solo de este proyecto
    chart_df = df_buildings.melt(
        id_vars=["name"],
        value_vars=["assigned", "mapped", "unmapped", "not_live"],
        var_name="Status",
        value_name="Cantidad",
    )
    fig = px.bar(
        chart_df,
        x="name",
        y="Cantidad",
        color="Status",
        barmode="group",
        color_discrete_map=STATUS_COLORS,
        labels={"name": "Edificio"},
    )
    fig.update_layout(xaxis_tickangle=-20, height=380)
    st.plotly_chart(fig, use_container_width=True)


# ============================================================
# PÁGINA 3: ACTUALIZAR EDIFICIO
# La página que más vas a usar en tu flujo semanal.
# Seleccionas proyecto → edificio → actualizas los 4 conteos.
# ============================================================
elif page == "✏️ Actualizar Edificio":
    st.title("✏️ Update Building")

    df_projects = get_all_projects()

    if df_projects.empty:
        st.info("No hay proyectos aún.")
        st.stop()

    # Paso 1: elegir proyecto
    selected_label = st.selectbox("Project:", df_projects["label"].tolist())
    row_proj = df_projects[df_projects["label"] == selected_label].iloc[0]
    project_id = int(row_proj["id"])

    df_buildings = get_buildings_by_project(project_id)
    
    if "left_to_review" not in df_buildings.columns:
        df_buildings["left_to_review"] = df_buildings["assigned"] - df_buildings["mapped"] - df_buildings["unmapped"] - df_buildings["not_live"]

    if df_buildings.empty:
        st.info("Este proyecto no tiene edificios aún.")
        st.stop()

    # Paso 2: elegir edificio dentro del proyecto
    # El diccionario mapea "Nombre (tipo)" → id del edificio
    building_options = {
        f"{r['name']} ({r['type']})": int(r["id"])
        for _, r in df_buildings.iterrows()
    }
    selected_building = st.selectbox("Building:", list(building_options.keys()))
    building_id = building_options[selected_building]

    # Obtener la fila completa del edificio seleccionado
    row_b = df_buildings[df_buildings["id"] == building_id].iloc[0]

    st.markdown("---")

    # Muestra los conteos actuales como referencia
    st.subheader("Conteos actuales")
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Assigned", int(row_b["assigned"]))
    m2.metric("Mapped",   int(row_b["mapped"]))
    m3.metric("Unmapped", int(row_b["unmapped"]))
    m4.metric("Not Live", int(row_b["not_live"]))
    
    not_review_yet = int(row_b["left_to_review"])
    m5.metric("Left to review", not_review_yet, delta=-not_review_yet if not_review_yet > 0 else None, delta_color="inverse")

    st.markdown("---")
    st.subheader("Nuevos valores")

    with st.form("update_building_form"):
        # También permite corregir nombre y tipo si hubo un error
        col_a, col_b = st.columns(2)
        with col_a:
            new_name = st.text_input("Building name", value=row_b["name"])
        with col_b:
            new_type = st.selectbox(
                "Type Structure",
                ["Condo", "MUS"],
                index=0 if row_b["type"] == "condo" else 1
            )

        col1, col2 = st.columns(2)
        with col1:
            new_assigned = st.number_input("Assigned", min_value=0, value=int(row_b["assigned"]))
            new_mapped   = st.number_input("Mapped",   min_value=0, value=int(row_b["mapped"]))
        with col2:
            new_unmapped = st.number_input("Unmapped", min_value=0, value=int(row_b["unmapped"]))
            new_not_live = st.number_input("Not Live", min_value=0, value=int(row_b["not_live"]))

        saved = st.form_submit_button("💾 Save Changes", use_container_width=True)

    if saved:
        update_building(
            building_id=building_id,
            name=new_name,
            building_type=new_type,
            assigned=new_assigned,
            mapped=new_mapped,
            unmapped=new_unmapped,
            not_live=new_not_live,
        )
        st.success(f"✅ '{new_name}' actualizado.")
        st.rerun()


# ============================================================
# PÁGINA 4: NUEVO PROYECTO
# Solo Estado + Condado + Ciudad opcional.
# ============================================================
elif page == "➕ Nuevo Proyecto":
    st.title("➕ Nuevo Proyecto")

    with st.form("new_project_form"):
        col1, col2 = st.columns(2)
        with col1:
            state  = st.text_input("State *",  placeholder="Ej: Texas")
            county = st.text_input("County *", placeholder="Ej: Nelson County")
        with col2:
            city = st.text_input(
                "City (optional)",
                placeholder="Dejar vacío si el contrato es de condado"
            )

        submitted = st.form_submit_button("✅ Create Project", use_container_width=True)

    if submitted:
        if not state or not county:
            st.error("Estado y Condado son obligatorios.")
        else:
            city_value = city.strip() if city.strip() else None
            add_project(state.strip(), county.strip(), city_value)
            label = f"{state} — {county}" + (f" — {city}" if city_value else "")
            st.success(f"✅ Project created: {label}")
            st.info("Ahora ve a **➕ Nuevo Edificio** para agregar los condos y MUS de este proyecto.")
            st.rerun()


# ============================================================
# PÁGINA 5: NUEVO EDIFICIO
# Seleccionas el proyecto y agregas un edificio con sus conteos.
# ============================================================
elif page == "➕ Nuevo Edificio":
    st.title("➕ Nuevo Edificio")

    df_projects = get_all_projects()

    if df_projects.empty:
        st.info("Primero crea un proyecto en **➕ Nuevo Proyecto**.")
        st.stop()

    with st.form("new_building_form"):
        # Selector de proyecto al que pertenece este edificio
        selected_label = st.selectbox("Proyecto al que pertenece:", df_projects["label"].tolist())

        col1, col2 = st.columns(2)
        with col1:
            name  = st.text_input("Nombre del edificio *", placeholder="Ej: Sunrise Condominiums")
        with col2:
            btype = st.selectbox("Type Structure *", ["Condo", "MUS"])

        st.markdown("---")
        st.subheader("Conteos iniciales")

        c1, c2, c3, c4 = st.columns(4)
        init_assigned = c1.number_input("Assigned", min_value=0, value=0)
        init_mapped   = c2.number_input("Mapped",   min_value=0, value=0)
        init_unmapped = c3.number_input("Unmapped", min_value=0, value=0)
        init_not_live = c4.number_input("Not Live", min_value=0, value=0)

        submitted = st.form_submit_button("✅ Agregar Edificio", use_container_width=True)

    if submitted:
        if not name:
            st.error("El nombre del edificio es obligatorio.")
        else:
            row_proj = df_projects[df_projects["label"] == selected_label].iloc[0]
            add_building(
                project_id=int(row_proj["id"]),
                name=name.strip(),
                building_type=btype,
                assigned=init_assigned,
                mapped=init_mapped,
                unmapped=init_unmapped,
                not_live=init_not_live,
            )
            st.success(f"✅ Edificio '{name}' agregado a {selected_label}.")
            st.rerun()


# ============================================================
# PÁGINA 6: ELIMINAR
# Dos opciones: eliminar un edificio o un proyecto completo.
# ============================================================
elif page == "🗑️ Eliminar":
    st.title("🗑️ Eliminar")

    df_projects = get_all_projects()

    if df_projects.empty:
        st.info("No hay datos para eliminar.")
        st.stop()

    # Tabs para separar las dos opciones de eliminación
    tab1, tab2 = st.tabs(["Eliminar un Edificio", "Eliminar un Proyecto completo"])

    # ----------------------------------------------------------
    # TAB 1: Eliminar edificio individual
    # ----------------------------------------------------------
    with tab1:
        st.subheader("Eliminar Edificio")

        sel_proj = st.selectbox("Proyecto:", df_projects["label"].tolist(), key="del_proj")
        row_proj = df_projects[df_projects["label"] == sel_proj].iloc[0]
        df_buildings = get_buildings_by_project(int(row_proj["id"]))

        if df_buildings.empty:
            st.info("Este proyecto no tiene edificios.")
        else:
            building_options = {
                f"{r['name']} ({r['type']})": int(r["id"])
                for _, r in df_buildings.iterrows()
            }
            sel_building = st.selectbox("Edificio a eliminar:", list(building_options.keys()))
            building_id  = building_options[sel_building]

            st.warning("Esta acción no se puede deshacer.")
            if st.button("🗑️ Eliminar Edificio", type="primary"):
                delete_building(building_id)
                st.success(f"Edificio '{sel_building}' eliminado.")
                st.rerun()

    # ----------------------------------------------------------
    # TAB 2: Eliminar proyecto completo (con todos sus edificios)
    # ----------------------------------------------------------
    with tab2:
        st.subheader("Eliminar Proyecto completo")
        st.caption("Esto elimina el proyecto Y todos sus edificios.")

        sel_proj2 = st.selectbox("Proyecto a eliminar:", df_projects["label"].tolist(), key="del_proj2")
        row_proj2 = df_projects[df_projects["label"] == sel_proj2].iloc[0]

        st.warning(f"Se eliminarán el proyecto y sus **{int(row_proj2['total_buildings'])} edificios**. Esta acción no se puede deshacer.")

        if st.button("🗑️ Eliminar Proyecto completo", type="primary"):
            delete_project(int(row_proj2["id"]))
            st.success(f"Proyecto '{sel_proj2}' y todos sus edificios eliminados.")
            st.rerun()
