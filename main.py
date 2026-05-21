import streamlit as st
import pandas as pd
import io
import requests

# URL del archivo en formato Raw para poder leerlo directamente
GITHUB_RAW_URL = "https://raw.githubusercontent.com/JulianTorrest/Linaje/main/Columnas%20Oracle.txt"

def parse_oracle_metadata(file_content):
    """
    Parsea el contenido del archivo de texto para extraer Tablas, Columnas y Tipos.
    """
    data = []
    lines = [line.strip() for line in file_content.splitlines() if line.strip()]
    
    current_table = None
    # Variables para almacenar metadatos de nivel de tabla
    current_esquema = "Bronce"
    current_tipo = "Tabla"
    current_estado = "Activo"

    # Definimos un set más amplio de tipos de datos de Oracle para robustecer el parser
    oracle_types = {'VARCHAR2', 'NUMBER', 'DATE', 'CLOB', 'TIMESTAMP', 'VARCHAR', 'CHAR', 'BLOB', 'RAW', 'FLOAT', 'LONG', 'NVARCHAR2'}
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # 1. Identificar el nombre de la tabla
        if line.startswith('TBL_'):
            current_table = line
            # Valores por defecto para la nueva tabla detectada
            current_esquema = "Bronce"
            current_tipo = "Tabla"
            current_estado = "No encontrado"
            
            # Intentar detectar línea de metadatos (ej: Tabla	BRONCE	Activo)
            if i + 1 < len(lines) and any(x in lines[i+1].upper() for x in ["BRONCE", "PLATA", "ORO"]):
                meta_line = lines[i+1]
                # Dividir por tabulaciones o múltiples espacios
                parts = [p.strip() for p in meta_line.replace('\t', '  ').split('  ') if p.strip()]
                if len(parts) >= 3:
                    current_tipo = parts[0]
                    current_esquema = parts[1].capitalize()
                    current_estado = parts[2]
                    i += 2 # Saltamos el nombre de tabla y su línea de metadatos
                    continue

            i += 1
            continue
            
        # 2. Identificar pares de Columna y Tipo
        # El patrón es: Nombre_Columna seguido por el Tipo de Dato.
        # Se extrae el tipo base (ej. VARCHAR2) ignorando precisiones (ej. VARCHAR2(100))
        if i + 1 < len(lines):
            type_candidate = lines[i+1].split('(')[0].strip().upper()
            if type_candidate in oracle_types:
                col_name = line
                col_type = lines[i+1]
                
                data.append({
                    "Tabla": current_table,
                    "Esquema": current_esquema,
                    "Tipo": current_tipo,
                    "Estado": current_estado,
                    "Campo": col_name,
                    "Tipo de Dato": col_type
                })
                # Avanzamos 2 líneas (nombre y tipo)
                i += 2
                continue
        
        i += 1
        
    return pd.DataFrame(data)

def enrich_with_ai_descriptions(df):
    """
    Función de IA para autocompletar metadatos funcionales basados en patrones
    técnicos y de negocio detectados en los nombres de campos y tablas.
    """
    def get_ai_metadata(row):
        campo = str(row['Campo']).upper()
        tabla = str(row['Tabla']).upper()
        tipo = str(row['Tipo de Dato']).upper()
        
        # Valores por defecto
        desc = "Atributo técnico de la entidad."
        uso = "Almacenamiento de información operativa."
        obs = "Sin observaciones técnicas registradas."
        
        # Lógica de inferencia por patrones de nombre de campo
        if any(x in campo for x in ['FECHA', 'ANIO', 'ANO', 'FCONCLUSION']):
            desc = "Marca temporal o periodo de referencia del registro."
            uso = "Permite realizar análisis de series de tiempo, tendencias y cumplimiento de términos."
            obs = "Se recomienda validar el formato de fecha (DD/MM/YYYY) en el origen."
        elif any(x in campo for x in ['MUNICIPIO', 'DEPTO', 'DEPARTAMENTO', 'PAIS', 'DIVIPOLA', 'LUGAR', 'LATITUD', 'LONGITUD']):
            desc = "Atributo de ubicación geográfica o administrativa."
            uso = "Fundamental para la territorialización de la información y creación de mapas de calor."
            obs = "Cruzar con codificación DIVIPOLA del DANE para garantizar integridad referencial."
        elif any(x in campo for x in ['SEXO', 'GENERO', 'ORIENTACION', 'EDAD', 'DISCAPACIDAD', 'ETNICO', 'INDIGENA', 'RANGO_EDAD']):
            desc = "Variable sociodemográfica de caracterización poblacional."
            uso = "Utilizado para aplicar enfoques diferenciales y analizar el impacto en grupos vulnerables."
            obs = "Dato sensible: Su tratamiento debe cumplir con la Ley de Protección de Datos Personales."
        elif any(x in campo for x in ['PETICION', 'RADICADO', 'SOLICITUD', 'RUP', 'NUMERO', 'ID', 'EXPEDIENTE']):
            desc = "Identificador único o número de radicado del trámite o proceso."
            uso = "Garantiza la trazabilidad del registro y permite realizar uniones (joins) con otros módulos."
            obs = "Actúa generalmente como llave primaria (PK) o foránea (FK)."
        elif any(x in campo for x in ['DEPENDENCIA', 'FUENTE', 'GESTIONADA_POR', 'USER_FUN']):
            desc = "Referencia a la unidad administrativa o usuario responsable de la gestión."
            uso = "Permite auditar el flujo de trabajo y medir la carga operativa por dependencias."
            obs = "Relacionado con la estructura organizacional interna."
        elif any(x in campo for x in ['TITULO', 'TEXTO', 'TITULAR', 'HECHOS', 'SOLICITUD', 'CLOB']):
            desc = "Contenido narrativo, descriptivo o cuerpo del documento."
            uso = "Almacena el detalle cualitativo de la información para análisis de texto o consulta directa."
            obs = "Al ser un campo de texto largo (CLOB), puede impactar el rendimiento en consultas masivas."
        
        # Refinamiento por contexto de tabla
        if 'SENTENCIAS' in tabla:
            desc += " (Contexto Jurídico/Sentencias)."
        elif 'NOTICIAS' in tabla:
            desc += " (Monitoreo de Medios)."
            
        return pd.Series([desc, uso, obs])

    df[['Descripción funcional', 'Para qué sirve el campo', 'Observaciones']] = df.apply(get_ai_metadata, axis=1)
    return df

@st.cache_data
def fetch_github_data(url):
    """Descarga el archivo desde GitHub."""
    try:
        response = requests.get(url)
        if response.status_code == 200:
            return response.text
        return None
    except Exception:
        return None

# --- Interfaz de Streamlit ---
st.set_page_config(page_title="Linaje de Datos - Defensoría", layout="wide")

st.title("📊 Diccionario de Datos Oracle")
st.markdown("""
Esta aplicación organiza la información de las tablas de la capa **BRONCE**.
""")

# 1. Intentar cargar desde GitHub automáticamente
content = fetch_github_data(GITHUB_RAW_URL)

# 2. Opción de carga manual (sobreescribe el de GitHub si se sube algo)
with st.expander("Opciones de carga de datos"):
    if content:
        st.success("✅ Datos cargados automáticamente desde GitHub.")
    else:
        st.warning("⚠️ No se pudo cargar automáticamente desde GitHub.")
        
    uploaded_file = st.file_uploader("Subir una versión local de 'Columnas Oracle.txt'", type=["txt"])
    if uploaded_file is not None:
        content = uploaded_file.getvalue().decode("utf-8")

if content:
    # Procesar contenido
    df = parse_oracle_metadata(content)
    
    # Enriquecer con IA
    df = enrich_with_ai_descriptions(df)
    
    if not df.empty:
        # Filtros opcionales
        st.subheader("Filtros de Metadatos")
        
        # Usamos st.columns para organizar los filtros en el centro
        col_esquema, col_tipo, col_estado = st.columns(3)
        
        with col_esquema:
            esquemas_seleccionados = st.multiselect(
                "Esquema",
                options=df["Esquema"].unique(),
                default=df["Esquema"].unique()
            )
        
        with col_tipo:
            tipos_seleccionados = st.multiselect(
                "Tipo",
                options=df["Tipo"].unique(),
                default=df["Tipo"].unique()
            )
            
        with col_estado:
            estados_seleccionados = st.multiselect(
                "Estado",
                options=df["Estado"].unique(),
                default=df["Estado"].unique()
            )
            
        # El filtro de tablas lo dejamos debajo de los otros para mayor espacio
        tablas_seleccionadas = st.multiselect(
            "Tabla", 
            options=df["Tabla"].unique(),
            default=df["Tabla"].unique()[:min(len(df["Tabla"].unique()), 5)] # Por defecto las primeras 5 tablas
        )
        
        # Aplicar todos los filtros
        df_filtered = df[
            (df["Esquema"].isin(esquemas_seleccionados)) &
            (df["Tipo"].isin(tipos_seleccionados)) &
            (df["Estado"].isin(estados_seleccionados)) &
            (df["Tabla"].isin(tablas_seleccionadas))
        ]
        
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
