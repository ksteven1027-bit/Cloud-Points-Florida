import streamlit as st
import pandas as pd
from streamlit_folium import st_folium
from pyproj import Transformer
import folium

# --- MOTOR DE CÁLCULO ---
class MotorTopografiaFlorida:
    def __init__(self, epsg_origen=6438):
        self.epsg_origen = epsg_origen
        self.transformer = Transformer.from_crs(
            f"epsg:{self.epsg_origen}", 
            "epsg:4326", 
            always_xy=True
        )

    def procesar_y_transformar(self, df):
        df = df.copy()
        cols_numericas = ['Y_Northing', 'X_Easting', 'Z_Elev']
        
        for col in cols_numericas:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        df = df.dropna(subset=cols_numericas)
        
        if df.empty:
            return None

        lon, lat = self.transformer.transform(
            df['X_Easting'].values, 
            df['Y_Northing'].values
        )
        df['Longitud'] = lon
        df['Latitud'] = lat
        
        return df

# --- INTERFAZ STREAMLIT ---
st.set_page_config(page_title="Visor Topográfico Avanzado", layout="wide")
st.title("📍 Visor de Nubes de Puntos - Florida")
st.markdown("Pasa el mouse sobre el ícono de capas 🥞 arriba a la derecha del mapa para cambiar el mapa base o encender/apagar archivos.")

opciones_epsg = {
    "Florida East - NAD83(2011) (Recomendado)": 6438,
    "Florida East - NAD83 Original": 2236,
    "Florida West - NAD83(2011)": 6443,
    "Florida West - NAD83 Original (EPSG: 2237)": 2237,
    "Florida North - NAD83(2011)": 6441,
    "Florida North - NAD83 Original": 2238,
}

PALETA_COLORES = [
    "#00FFFF", "#FF0000", "#FFFF00", "#00FF00", "#FF00FF", "#FFA500", "#FFFFFF",
    "#1E90FF", "#FF1493", "#32CD32", "#8A2BE2", "#FF4500", "#00CED1", "#FFD700",
    "#ADFF2F", "#FF69B4", "#00FA9A", "#DC143C", "#7B68EE", "#00BFFF"
]

# --- BARRA LATERAL: MODOS DE TRABAJO ---
with st.sidebar:
    st.header("1. Modo de Trabajo")
    modo_trabajo = st.radio("Selecciona una opción:", ("✨ Nuevo Proyecto", "📂 Restaurar Proyecto"))
    
    df_global = pd.DataFrame()
    procesar_mapa = False

    if modo_trabajo == "✨ Nuevo Proyecto":
        st.header("2. Configuración (Archivos TXT)")
        sistema_coords = st.selectbox("Zona y Datum:", list(opciones_epsg.keys()))
        epsg_elegido = opciones_epsg[sistema_coords]
        
        formato_columnas = st.radio("Orden de los TXT:", ("PNEZD (Norte, Este)", "PENZD (Este, Norte)"))
        separador_datos = st.text_input("Separador del TXT", value=",")
        
        archivos_subidos = st.file_uploader(
            "Cargar múltiples archivos TXT", 
            type=['txt', 'csv'], 
            accept_multiple_files=True
        )
        
        if archivos_subidos:
            motor = MotorTopografiaFlorida(epsg_origen=epsg_elegido)
            if formato_columnas.startswith("PNEZD"):
                nombres_columnas = ['ID', 'Y_Northing', 'X_Easting', 'Z_Elev', 'Descripcion']
            else:
                nombres_columnas = ['ID', 'X_Easting', 'Y_Northing', 'Z_Elev', 'Descripcion']

            lista_dataframes = []
            with st.spinner('Procesando nubes y transformando coordenadas...'):
                for archivo in archivos_subidos:
                    try:
                        df_crudo = pd.read_csv(archivo, sep=separador_datos, names=nombres_columnas, header=None, engine='python')
                        df_calculado = motor.procesar_y_transformar(df_crudo)
                        if df_calculado is not None and not df_calculado.empty:
                            df_calculado['Archivo_Origen'] = archivo.name
                            lista_dataframes.append(df_calculado)
                    except Exception as e:
                        st.error(f"Error procesando {archivo.name}: {e}")
                
                if lista_dataframes:
                    df_global = pd.concat(lista_dataframes, ignore_index=True)
                    procesar_mapa = True

    elif modo_trabajo == "📂 Restaurar Proyecto":
        st.header("2. Cargar Archivo Maestro")
        st.info("Sube el archivo `.csv` generado previamente con el botón 'Guardar Proyecto Streamlit'.")
        archivo_proyecto = st.file_uploader("Cargar Proyecto (.csv)", type=['csv'])
        
        # Opciones para exportar la nube final desde un proyecto restaurado
        formato_columnas = st.radio("Formato para exportar Nube Unificada:", ("PNEZD (Norte, Este)", "PENZD (Este, Norte)"))
        separador_datos = ","
        
        if archivo_proyecto:
            with st.spinner('Restaurando sesión y reconstruyendo capas...'):
                try:
                    df_global = pd.read_csv(archivo_proyecto)
                    if 'Archivo_Origen' in df_global.columns and 'Latitud' in df_global.columns:
                        procesar_mapa = True
                    else:
                        st.error("❌ El archivo subido no es un Proyecto de Streamlit válido.")
                except Exception as e:
                    st.error(f"Error al leer el proyecto: {e}")

# --- LÓGICA DE RENDERIZADO Y EXPORTACIÓN ---
if procesar_mapa and not df_global.empty:
    mapa = folium.Map(location=[27.6648, -81.5158], zoom_start=7)
    
    # Mapas base
    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='Esri', name='🗺️ Satélite Esri', overlay=False, control=True
    ).add_to(mapa)
    folium.TileLayer('cartodbpositron', name='🗺️ Mapa Claro', overlay=False, control=True).add_to(mapa)
    folium.TileLayer('cartodbdark_matter', name='🗺️ Mapa Oscuro', overlay=False, control=True).add_to(mapa)
    folium.TileLayer('openstreetmap', name='🗺️ OpenStreetMap', overlay=False, control=True).add_to(mapa)

    archivos_unicos = df_global['Archivo_Origen'].unique()
    todas_latitudes = df_global['Latitud'].tolist()
    todas_longitudes = df_global['Longitud'].tolist()

    # Reconstruir las capas agrupando por el nombre del archivo original
    for i, nombre_archivo in enumerate(archivos_unicos):
        df_filtrado = df_global[df_global['Archivo_Origen'] == nombre_archivo]
        
        color_puntos = PALETA_COLORES[i % len(PALETA_COLORES)]
        simbolo_color = f"<span style='color:{color_puntos}; text-shadow: 0 0 1px black; font-size: 14px;'>⬤</span>"
        nombre_capa = f"{simbolo_color} 📄 {nombre_archivo}"
        
        capa_archivo = folium.FeatureGroup(name=nombre_capa)
        
        for _, fila in df_filtrado.iterrows():
            desc_raw = str(fila.get('Descripcion', 'N/A'))
            desc = desc_raw if desc_raw.lower() != 'nan' else "N/A"
            desc_upper = desc.upper()
            pto_id = str(fila['ID'])
            elev = round(fila['Z_Elev'], 2)
            
            es_control = any(kw in desc_upper.split() or desc_upper.startswith(kw) for kw in ['TBM', 'BM', 'PKND'])

            if es_control:
                folium.RegularPolygonMarker(
                    location=[fila['Latitud'], fila['Longitud']],
                    number_of_sides=3, radius=8, color="#000000", weight=2,
                    fill=True, fill_color=color_puntos, fill_opacity=1.0,
                    tooltip=f"🔺 PUNTO DE CONTROL<br>Archivo: {nombre_archivo}<br>Punto: {pto_id}<br>Elevación: {elev} ft<br>Desc: {desc}"
                ).add_to(capa_archivo)
            else:
                folium.CircleMarker(
                    location=[fila['Latitud'], fila['Longitud']],
                    radius=3, color=color_puntos, fill=True, fill_color=color_puntos, fill_opacity=0.9,
                    tooltip=f"Archivo: {nombre_archivo}<br>Punto: {pto_id}<br>Elevación: {elev} ft<br>Desc: {desc}"
                ).add_to(capa_archivo)
            
        capa_archivo.add_to(mapa)

    # --- ANÁLISIS DE DUPLICADOS ---
    df_global['Norte_R'] = df_global['Y_Northing'].round(3)
    df_global['Este_R'] = df_global['X_Easting'].round(3)
    df_global['Elev_R'] = df_global['Z_Elev'].round(3)

    duplicados = df_global[df_global.duplicated(subset=['Norte_R', 'Este_R', 'Elev_R'], keep=False)]
    
    if not duplicados.empty:
        archivos_involucrados = duplicados['Archivo_Origen'].unique()
        if len(archivos_involucrados) > 1:
            st.warning(f"⚠️ **Alerta de Topografía:** Puntos idénticos cruzados entre: **{', '.join(archivos_involucrados)}**.")
        else:
            st.warning(f"⚠️ El archivo **{archivos_involucrados[0]}** tiene puntos duplicados internamente.")
        
        resumen_duplicados = duplicados.groupby(['Norte_R', 'Este_R', 'Elev_R']).agg(
            Archivos=('Archivo_Origen', lambda x: ' | '.join(x.unique())),
            ID_Originales=('ID', lambda x: ', '.join(x.astype(str)))
        ).reset_index()
        
        resumen_duplicados.rename(columns={'Norte_R': 'Norte', 'Este_R': 'Este', 'Elev_R': 'Elevación'}, inplace=True)
        with st.expander(f"🔍 Ver detalles de los {len(resumen_duplicados)} puntos con solapamiento"):
            st.dataframe(resumen_duplicados, use_container_width=True)

    # --- PREPARACIÓN DE ARCHIVOS PARA EXPORTAR ---
    df_unificado = df_global.drop_duplicates(subset=['Norte_R', 'Este_R', 'Elev_R'], keep='first').copy()
    df_unificado['ID'] = range(1, len(df_unificado) + 1)
    
    columnas_finales = ['ID', 'Y_Northing', 'X_Easting', 'Z_Elev', 'Descripcion'] if formato_columnas.startswith("PNEZD") else ['ID', 'X_Easting', 'Y_Northing', 'Z_Elev', 'Descripcion']
    csv_unificado = df_unificado.to_csv(columns=columnas_finales, index=False, header=False, sep=separador_datos)
    csv_proyecto = df_global.to_csv(index=False) # Exporta todo el dataframe incluyendo Lat/Lon y Archivo_Origen

    # Renderizar mapa
    mapa.fit_bounds([[min(todas_latitudes), min(todas_longitudes)], [max(todas_latitudes), max(todas_longitudes)]])
    folium.LayerControl(collapsed=True).add_to(mapa)
    
    st_folium(mapa, width="100%", height=700, returned_objects=[])
    
    # --- BOTONES DE DESCARGA ---
    st.markdown("---")
    st.markdown("### 💾 Guardar / Exportar Datos")
    
    col_metric1, col_metric2, col_btn1, col_btn2 = st.columns([1, 1, 2, 2])
    
    with col_metric1:
        st.metric("Puntos Totales", len(df_global))
    with col_metric2:
        st.metric("Puntos Únicos", len(df_unificado))
        
    with col_btn1:
        st.download_button(
            label="📥 Descargar Nube Unificada (TXT)",
            data=csv_unificado,
            file_name="Nube_Unificada_Florida.txt",
            mime="text/plain",
            help="Crea un TXT limpio sin duplicados y con IDs reiniciados. Ideal para Civil 3D."
        )
    with col_btn2:
        st.download_button(
            label="📂 Guardar Proyecto Streamlit (CSV)",
            data=csv_proyecto,
            file_name="Proyecto_Topografia.csv",
            mime="text/csv",
            help="Descarga un archivo maestro. Súbelo en 'Restaurar Proyecto' para cargar tus capas sin reprocesar."
        )