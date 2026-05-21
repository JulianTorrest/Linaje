import streamlit as st
import pandas as pd
import io

def parse_oracle_metadata(file_content):
    """
    Parsea el contenido del archivo de texto para extraer Tablas, Columnas y Tipos.
    """
    data = []
    lines = [line.strip() for line in file_content.splitlines() if line.strip()]
    
    current_table = None
    # Definimos los tipos de datos conocidos en Oracle para ayudar al parser
    oracle_types = {'VARCHAR2', 'NUMBER', 'DATE', 'CLOB'}
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # 1. Identificar el nombre de la tabla
        if line.startswith('TBL_'):
            current_table = line
            i += 1
            continue
            
        # 2. Identificar pares de Columna y Tipo
        # El patrón observado es: Nombre_Columna seguido inmediatamente por el Tipo de Dato
        if i + 1 < len(lines) and lines[i+1] in oracle_types:
            col_name = line
            col_type = lines[i+1]
            
            data.append({
                "Tabla": current_table,
                "Campo": col_name,
                "Tipo de Dato": col_type
            })
            # Avanzamos 2 líneas (nombre y tipo)
            i += 2
            continue
        
        i += 1
        
    return pd.DataFrame(data)

# --- Interfaz de Streamlit ---
st.set_page_config(page_title="Linaje de Datos - Defensoría", layout="wide")

st.title("📊 Diccionario de Datos Oracle")
st.markdown("""
Esta aplicación procesa el archivo de metadatos para organizar la información de las tablas de la capa **BRONCE**.
""")

# Opción de cargar el archivo
uploaded_file = st.file_uploader("Cargar archivo 'Columnas Oracle.txt'", type=["txt"])

if uploaded_file is not None:
    # Leer el contenido del archivo cargado
    stringio = io.StringIO(uploaded_file.getvalue().decode("utf-8"))
    content = stringio.read()
    
    # Procesar
    df = parse_oracle_metadata(content)
    
    if not df.empty:
        # Filtros opcionales
        st.sidebar.header("Filtros")
        tablas_seleccionadas = st.sidebar.multiselect(
            "Seleccionar Tablas", 
            options=df["Tabla"].unique(),
            default=df["Tabla"].unique()[:2] # Por defecto las primeras 2
        )
        
        df_filtered = df[df["Tabla"].isin(tablas_seleccionadas)]
        
        # Mostrar métricas rápidas
        col1, col2 = st.columns(2)
        col1.metric("Total Tablas", df_filtered["Tabla"].nunique())
        col2.metric("Total Campos", len(df_filtered))
        
        # Mostrar tabla principal
        st.subheader("Estructura de Metadatos")
        st.dataframe(df_filtered, use_container_width=True, height=600)
        
        # Botón para descargar como CSV
        csv = df_filtered.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="Descargar esta vista como CSV",
            data=csv,
            file_name="metadatos_oracle.csv",
            mime="text/csv",
        )
    else:
        st.warning("No se pudo extraer información. Verifica el formato del archivo.")
else:
    st.info("Por favor, sube el archivo .txt para comenzar el análisis.")

