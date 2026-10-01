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
st.markdown("Sube múltiples archivos `.txt`. Los puntos de control (BM, TBM, PKND) se renderizarán automáticamente como **triángulos**.")

opciones_epsg = {
    "Florida East - NAD83(2011) (Recomendado)": 6438,
    "Florida East - NAD83 Original": 2236,
    "Florida West - NAD83(2011)": 6443,
    "Florida West - NAD83 Original (EPSG: 2237)": 2237,
    "Florida North - NAD83(2011)": 6441,
    "Florida North - NAD83 Original": 2238,
}

# Paleta expandida a 20 colores vibrantes de alto contraste
PALETA_COLORES = [
    "#00FFFF", "#FF0000", "#FFFF00", "#00FF00", "#FF00FF", "#FFA500", "#FFFFFF",
    "#1E90FF", "#FF1493", "#32CD32", "#8A2BE2", "#FF4500", "#00CED1", "#FFD700",
    "#ADFF2F", "#FF69B4", "#00FA9A", "#DC143C", "#7B68EE", "#00BFFF"
]

with st.sidebar:
    st.header("Configuración de Proyecto")
    
    sistema_coords = st.selectbox("1. Zona y Datum:", list(opciones_epsg.keys()))
    epsg_elegido = opciones_epsg[sistema_coords]
    
    formato_columnas = st.radio("2. Orden de los TXT:", ("PNEZD (Norte, Este)", "PENZD (Este, Norte)"))
    separador_datos = st.text_input("3. Separador", value=",")
    
    archivos_subidos = st.file_uploader(
        "4. Cargar archivos TXT", 
        type=['txt', 'csv'], 
        accept_multiple_files=True
    )

# --- LÓGICA DE PROCESAMIENTO Y MAPA ---
if archivos_subidos:
    mapa = folium.Map(location=[27.6648, -81.5158], zoom_start=7)
    
    folium.TileLayer(
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='Esri', name='🗺️ Satélite Esri', overlay=False, control=True
    ).add_to(mapa)
    
    folium.TileLayer('cartodbpositron', name='🗺️ Mapa Claro', overlay=False, control=True).add_to(mapa)
    folium.TileLayer('cartodbdark_matter', name='🗺️ Mapa Oscuro', overlay=False, control=True).add_to(mapa)
    folium.TileLayer('openstreetmap', name='🗺️ OpenStreetMap', overlay=False, control=True).add_to(mapa)

    motor = MotorTopografiaFlorida(epsg_origen=epsg_elegido)
    
    if formato_columnas.startswith("PNEZD"):
        nombres_columnas = ['ID', 'Y_Northing', 'X_Easting', 'Z_Elev', 'Descripcion']
    else:
        nombres_columnas = ['ID', 'X_Easting', 'Y_Northing', 'Z_Elev', 'Descripcion']

    lista_dataframes_procesados = []
    todas_latitudes = []
    todas_longitudes = []

    with st.spinner('Procesando nubes de puntos, identificando BMs y buscando coincidencias...'):
        for i, archivo in enumerate(archivos_subidos):
            try:
                df_crudo = pd.read_csv(
                    archivo, sep=separador_datos, names=nombres_columnas, header=None, engine='python'
                )
                df_calculado = motor.procesar_y_transformar(df_crudo)
                
                if df_calculado is not None and not df_calculado.empty:
                    df_calculado['Archivo_Origen'] = archivo.name
                    lista_dataframes_procesados.append(df_calculado)

                    color_puntos = PALETA_COLORES[i % len(PALETA_COLORES)]
                    simbolo_color = f"<span style='color:{color_puntos}; text-shadow: 0 0 1px black; font-size: 14px;'>⬤</span>"
                    nombre_capa = f"{simbolo_color} 📄 {archivo.name}"
                    
                    capa_archivo = folium.FeatureGroup(name=nombre_capa)
                    
                    for _, fila in df_calculado.iterrows():
                        desc = str(fila['Descripcion']) if pd.notna(fila.get('Descripcion')) else "N/A"
                        desc_upper = desc.upper()
                        pto_id = str(fila['ID'])
                        elev = round(fila['Z_Elev'], 2)
                        
                        # Lógica para detectar puntos de control
                        # Verifica si la descripción comienza con la clave o si la contiene como palabra aislada
                        es_control = False
                        for kw in ['TBM', 'BM', 'PKND']:
                            if kw in desc_upper.split() or desc_upper.startswith(kw):
                                es_control = True
                                break

                        if es_control:
                            # Símbolo de punto de control: Triángulo (3 lados) con borde negro
                            folium.RegularPolygonMarker(
                                location=[fila['Latitud'], fila['Longitud']],
                                number_of_sides=3,
                                radius=8,
                                color="#000000",
                                weight=2,
                                fill=True,
                                fill_color=color_puntos,
                                fill_opacity=1.0,
                                tooltip=f"🔺 PUNTO DE CONTROL<br>Archivo: {archivo.name}<br>Punto: {pto_id}<br>Elevación: {elev} ft<br>Desc: {desc}"
                            ).add_to(capa_archivo)
                        else:
                            # Símbolo topográfico normal: Círculo
                            folium.CircleMarker(
                                location=[fila['Latitud'], fila['Longitud']],
                                radius=3, 
                                color=color_puntos, 
                                fill=True, 
                                fill_color=color_puntos, 
                                fill_opacity=0.9,
                                tooltip=f"Archivo: {archivo.name}<br>Punto: {pto_id}<br>Elevación: {elev} ft<br>Desc: {desc}"
                            ).add_to(capa_archivo)
                        
                        todas_latitudes.append(fila['Latitud'])
                        todas_longitudes.append(fila['Longitud'])
                    
                    capa_archivo.add_to(mapa)
                    
            except Exception as e:
                st.error(f"Error al procesar el archivo {archivo.name}: {e}")

    # --- ANÁLISIS DE DUPLICIDAD Y EXPORTACIÓN ---
    if lista_dataframes_procesados:
        df_global = pd.concat(lista_dataframes_procesados, ignore_index=True)
        
        df_global['Norte_R'] = df_global['Y_Northing'].round(3)
        df_global['Este_R'] = df_global['X_Easting'].round(3)
        df_global['Elev_R'] = df_global['Z_Elev'].round(3)

        duplicados = df_global[df_global.duplicated(subset=['Norte_R', 'Este_R', 'Elev_R'], keep=False)]
        
        if not duplicados.empty:
            archivos_involucrados = duplicados['Archivo_Origen'].unique()
            
            if len(archivos_involucrados) > 1:
                st.warning(f"⚠️ **Alerta de Topografía:** Se detectaron puntos con las mismas coordenadas repetidos entre los archivos: **{', '.join(archivos_involucrados)}**.")
            else:
                st.warning(f"⚠️ El archivo **{archivos_involucrados[0]}** tiene puntos duplicados internamente.")
            
            resumen_duplicados = duplicados.groupby(['Norte_R', 'Este_R', 'Elev_R']).agg(
                Archivos=('Archivo_Origen', lambda x: ' | '.join(x.unique())),
                ID_Originales=('ID', lambda x: ', '.join(x.astype(str)))
            ).reset_index()
            
            resumen_duplicados.rename(columns={
                'Norte_R': 'Norte', 'Este_R': 'Este', 'Elev_R': 'Elevación'
            }, inplace=True)

            with st.expander(f"🔍 Ver detalles de los {len(resumen_duplicados)} puntos con solapamiento"):
                st.dataframe(resumen_duplicados, use_container_width=True)

        df_unificado = df_global.drop_duplicates(subset=['Norte_R', 'Este_R', 'Elev_R'], keep='first').copy()
        df_unificado['ID'] = range(1, len(df_unificado) + 1)
        
        if formato_columnas.startswith("PNEZD"):
            columnas_finales = ['ID', 'Y_Northing', 'X_Easting', 'Z_Elev', 'Descripcion']
        else:
            columnas_finales = ['ID', 'X_Easting', 'Y_Northing', 'Z_Elev', 'Descripcion']
            
        csv_unificado = df_unificado.to_csv(columns=columnas_finales, index=False, header=False, sep=separador_datos)

        mapa.fit_bounds([[min(todas_latitudes), min(todas_longitudes)], [max(todas_latitudes), max(todas_longitudes)]])
        folium.LayerControl(collapsed=True).add_to(mapa)
        
        col_mapa, col_datos = st.columns([3, 1])
        with col_mapa:
            st_folium(mapa, width="100%", height=700, returned_objects=[])
        
        with col_datos:
            st.success("✅ Renderizado Completo")
            st.metric("Puntos Totales (Con repetidos)", len(df_global))
            st.metric("Puntos Únicos (Unificados)", len(df_unificado))
            
            st.markdown("### Exportar Nube")
            st.markdown("Descarga un archivo unificado. Se han eliminado los puntos solapados y se ha reiniciado la numeración (ID) de 1 en adelante.")
            st.download_button(
                label="📥 Descargar Nube Unificada",
                data=csv_unificado,
                file_name="Nube_Unificada_Florida.txt",
                mime="text/plain"
            )
    else:
        st.warning("No se encontraron coordenadas válidas en los archivos subidos.")

else:
    st.info("👈 Sube uno o más archivos TXT en la barra lateral.")