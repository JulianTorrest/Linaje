import streamlit as st
import pandas as pd
import io
import requests
import graphviz
import re
from datetime import datetime
import json
from fuzzywuzzy import fuzz

# URL del archivo en formato Raw para poder leerlo directamente
GITHUB_RAW_URL = "https://raw.githubusercontent.com/JulianTorrest/Linaje/main/Columnas%20Oracle.txt"

# Base de datos de glosario de negocios
BUSINESS_GLOSSARY = {
    "CLIENTE": "Persona natural o jurídica que utiliza los servicios de la Defensoría",
    "EXPEDIENTE": "Conjunto de documentos y actuaciones que conforman un caso",
    "SENTENCIA": "Decisión judicial que resuelve un caso",
    "ABOGADO": "Profesional del derecho que representa a las partes",
    "DEPENDENCIA": "Unidad administrativa con funciones específicas",
    "MUNICIPIO": "División geográfica administrativa básica",
    "DEPARTAMENTO": "División geográfica administrativa superior",
    "PETICION": "Solicitud formal realizada por un ciudadano",
    "RADICADO": "Número único que identifica una comunicación oficial"
}

# Taxonomías de clasificación
DATA_TAXONOMY = {
    "Dominio": ["Jurídico", "Administrativo", "Geográfico", "Demográfico", "Financiero"],
    "Criticialidad": ["Alta", "Media", "Baja"],
    "Confidencialidad": ["Público", "Interno", "Confidencial", "Secreto"],
    "Actualización": ["Diaria", "Semanal", "Mensual", "Trimestral", "Anual"]
}

# Dueños de datos por área
DATA_OWNERS = {
    "Jurídico": "Dirección Jurídica",
    "Administrativo": "Secretaría General", 
    "Geográfico": "Oficina de Estadística",
    "Demográfico": "Dirección de Población",
    "Financiero": "Dirección Financiera"
}

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

    # Diccionario de normalización de tipos
    tipo_norm = {
        "FCT": "Hechos", "FACT": "Hechos",
        "DIM": "Dimensión", "DIMENSION": "Dimensión", "DIMENSIÓN": "Dimensión",
        "AGG": "Agregado", "AGREGADO": "Agregado",
        "VST": "Vista", "VISTA": "Vista",
        "TBL": "Tabla", "TABLA": "Tabla"
    }

    # Tipos de datos de Oracle
    oracle_types = {'VARCHAR2', 'NUMBER', 'DATE', 'CLOB', 'TIMESTAMP', 'VARCHAR', 
                    'CHAR', 'BLOB', 'RAW', 'FLOAT', 'LONG', 'NVARCHAR2', 'INTEGER'}
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # 1. Identificar el nombre de la entidad (Tabla, Vista, Agregado, Dimensión, Fact)
        # Ahora soporta TBL_, VST_, AGG_, DIM_ y FCT_
        if any(line.startswith(prefix) for prefix in ['TBL_', 'VST_', 'AGG_', 'DIM_', 'FCT_']):
            current_table = line
            
            # Inferencia de tipo por prefijo del nombre
            if line.startswith('DIM_'): inferred_tipo = tipo_norm["DIM"]
            elif line.startswith('FCT_'): inferred_tipo = tipo_norm["FCT"]
            elif line.startswith('VST_'): inferred_tipo = tipo_norm["VST"]
            elif line.startswith('AGG_'): inferred_tipo = tipo_norm["AGG"]
            else: inferred_tipo = "Tabla"

            # Inferencia de esquema por tipo (Regla de negocio: AGG, DIM, VST, FCT -> Oro)
            if inferred_tipo in [tipo_norm["FCT"], tipo_norm["DIM"], tipo_norm["AGG"], tipo_norm["VST"]]:
                current_esquema = "Oro"
            else:
                # TBL_ por defecto es Bronce, a menos que se detecte Plata abajo
                current_esquema = "Bronce"

            current_tipo = inferred_tipo
            current_estado = "No Encontrado"
            
            # Intentar detectar línea de metadatos en las siguientes 2 líneas
            # Esto permite saltar líneas intermedias como 'SQL'
            found_header = False
            for offset in [1, 2]:
                if i + offset < len(lines):
                    meta_line = lines[i+offset]
                    parts = meta_line.split()
                    
                    # Buscamos la posición del esquema (Bronce, Plata, Oro)
                    schema_idx = -1
                    for idx, p in enumerate(parts):
                        if p.upper() in ["BRONCE", "PLATA", "ORO"]:
                            schema_idx = idx
                            break
                    
                    if schema_idx != -1:
                        # Extraer Tipo de la línea de metadatos (solo si no es genérico 'Tabla')
                        raw_extracted_tipo = " ".join(parts[:schema_idx]).upper()
                        
                        # Attempt to normalize the extracted type from the metadata line
                        normalized_from_metadata = tipo_norm.get(raw_extracted_tipo, None)
                        
                        if normalized_from_metadata:
                            # If metadata explicitly states a type (e.g., "VISTA", "AGREGADO", "HECHOS", "DIMENSION", "TABLA")
                            # We use it, unless it's "Tabla" and our inferred_tipo is more specific (Hechos, Dimensión, etc.)
                            if normalized_from_metadata == "Tabla" and inferred_tipo != "Tabla":
                                # Metadata says "Tabla", but prefix says something more specific (FCT_, DIM_, AGG_, VST_).
                                # Keep the more specific inferred_tipo.
                                current_tipo = inferred_tipo
                            else:
                                # Metadata says something specific (Vista, Hechos, Dimensión, Agregado)
                                # OR metadata says "Tabla" and inferred_tipo is also "Tabla".
                                current_tipo = normalized_from_metadata

                        current_esquema = parts[schema_idx].capitalize()
                        
                        # El Estado es todo lo que sigue al esquema
                        if schema_idx + 1 < len(parts):
                            st_raw = " ".join(parts[schema_idx+1:]).upper()
                            if "MODIFICADO" in st_raw:
                                current_estado = "Modificado"
                            elif "NO" in st_raw:
                                current_estado = "No Encontrado"
                            elif "ACTIV" in st_raw:
                                current_estado = "Activo"
                            else:
                                current_estado = "No Encontrado"
                        
                        i += offset + 1 # Saltamos el nombre y las líneas de metadatos/SQL
                        found_header = True
                        break
            else:
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
                    "Campo": col_name, # Mantener el orden para facilitar la lectura
                    "Tipo de Dato": col_type,
                    "Clave Primaria": "No", # Valor por defecto
                    "Origen del Dato": "No especificado",
                    "Lógica de Transformación": "No aplica (dato original)",
                    "Sensibilidad del Dato": "Público"
                })
                # Avanzamos 2 líneas (nombre y tipo)
                i += 2
                continue
        
        i += 1
        
    df_result = pd.DataFrame(data)
    if not df_result.empty:
        # Normalización final de seguridad para la columna Tipo
        df_result['Tipo'] = df_result['Tipo'].apply(
            lambda x: tipo_norm.get(str(x).upper(), x)
        )
    return df_result

def classify_data_automatically(df):
    """
    Clasifica automáticamente los datos según taxonomías predefinidas
    """
    def get_classification(row):
        tabla = str(row['Tabla']).upper()
        campo = str(row['Campo']).upper()
        
        # Clasificación por dominio
        dominio = "Administrativo"  # Default
        if any(x in tabla for x in ['SENTENCIAS', 'JURIDICO', 'PROCESO']):
            dominio = "Jurídico"
        elif any(x in tabla for x in ['MUNICIPIO', 'DEPARTAMENTO', 'DIVIPOLA']):
            dominio = "Geográfico"
        elif any(x in tabla for x in ['PERSONA', 'CLIENTE', 'EDAD', 'SEXO']):
            dominio = "Demográfico"
        elif any(x in tabla for x in ['PRESUPUESTO', 'FINANCIERO', 'PAGO']):
            dominio = "Financiero"
            
        # Clasificación por criticidad
        criticidad = "Media"  # Default
        if any(x in campo for x in ['ID', 'PK', 'CLAVE', 'RADICADO']):
            criticidad = "Alta"
        elif any(x in campo for x in ['OBSERVACION', 'NOTA', 'COMENTARIO']):
            criticidad = "Baja"
            
        # Clasificación por confidencialidad
        confidencialidad = "Público"  # Default
        if any(x in campo for x in ['NOMBRE', 'IDENTIFICACION', 'TELEFONO', 'EMAIL']):
            confidencialidad = "Confidencial"
        elif any(x in campo for x in ['SALARIO', 'INGRESO', 'PENSION']):
            confidencialidad = "Secreto"
        elif 'INTERNO' in campo or 'SISTEMA' in campo:
            confidencialidad = "Interno"
            
        # Frecuencia de actualización
        actualizacion = "Mensual"  # Default
        if 'DIARIO' in tabla or 'DAILY' in tabla:
            actualizacion = "Diaria"
        elif 'SEMANAL' in tabla or 'WEEKLY' in tabla:
            actualizacion = "Semanal"
        elif 'ANUAL' in tabla or 'YEAR' in tabla:
            actualizacion = "Anual"
            
        return pd.Series([dominio, criticidad, confidencialidad, actualizacion])
    
    df[['Dominio', 'Criticidad', 'Confidencialidad', 'Frecuencia_Actualizacion']] = df.apply(get_classification, axis=1)
    return df

def calculate_dataset_statistics(df):
    """
    Calcula estadísticas por dataset (tabla)
    """
    stats = []
    for tabla in df['Tabla'].unique():
        tabla_data = df[df['Tabla'] == tabla]
        
        # Estadísticas básicas
        total_campos = len(tabla_data)
        campos_pk = len(tabla_data[tabla_data['Clave Primaria'] == 'Sí'])
        tipos_datos = tabla_data['Tipo de Dato'].nunique()
        
        # Métricas de calidad
        calidad_general = 0
        if campos_pk > 0:
            calidad_general += 25  # Tiene PK
        if total_campos > 5:
            calidad_general += 25  # Buena cantidad de campos
        if tabla_data['Descripción funcional'].notna().sum() > total_campos * 0.8:
            calidad_general += 25  # Buena documentación
        if tabla_data['Sensibilidad del Dato'].nunique() > 1:
            calidad_general += 25  # Clasificación de sensibilidad
            
        # Última actualización (simulada)
        ultima_actualizacion = datetime.now().strftime('%Y-%m-%d')
        
        stats.append({
            'Tabla': tabla,
            'Total_Campos': total_campos,
            'Campos_PK': campos_pk,
            'Tipos_Datos': tipos_datos,
            'Calidad_General': calidad_general,
            'Ultima_Actualizacion': ultima_actualizacion,
            'Esquema': tabla_data['Esquema'].iloc[0],
            'Tipo_Entidad': tabla_data['Tipo'].iloc[0]
        })
    
    return pd.DataFrame(stats)

def advanced_search(df, query, filters=None):
    """
    Búsqueda avanzada con fuzzy matching y filtros múltiples
    """
    if filters is None:
        filters = {}
    
    # Búsqueda por texto (fuzzy matching)
    if query:
        df['search_score'] = df.apply(lambda row: max(
            fuzz.partial_ratio(query.upper(), str(row['Tabla']).upper()),
            fuzz.partial_ratio(query.upper(), str(row['Campo']).upper()),
            fuzz.partial_ratio(query.upper(), str(row['Descripción funcional']).upper())
        ), axis=1)
        df = df[df['search_score'] >= 30]  # Umbral de similitud
        df = df.sort_values('search_score', ascending=False)
    
    # Aplicar filtros
    for field, values in filters.items():
        if field in df.columns and values:
            df = df[df[field].isin(values)]
    
    return df

def get_business_definition(term):
    """
    Obtiene definición del glosario de negocios
    """
    return BUSINESS_GLOSSARY.get(term.upper(), f"Término '{term}' no encontrado en glosario")

def get_data_owner(dominio):
    """
    Obtiene el dueño del dato según dominio
    """
    return DATA_OWNERS.get(dominio, "Sin dueño asignado")

def enrich_with_ai_descriptions(df):
    """
    Función de IA para autocompletar metadatos funcionales basados en patrones
    técnicos y de negocio detectados en los nombres de campos y tablas.
    """
    def get_ai_metadata(row):
        campo = str(row['Campo']).upper()
        tabla = str(row['Tabla']).upper()
        tipo = str(row['Tipo de Dato']).upper()
        is_pk = "No" # Inicializar para la inferencia de PK
        
        # Valores por defecto
        desc = "Atributo técnico de la entidad."
        uso = "Almacenamiento de información operativa."
        obs = "Sin observaciones técnicas registradas."
        origen = "Sistema fuente no identificado"
        logica_transf = "Dato original (sin transformación)"
        sensibilidad = "Público"
        
        # Lógica de inferencia por patrones de nombre de campo
        if any(x in campo for x in ['FECHA', 'ANIO', 'ANO', 'FCONCLUSION']):
            desc = "Marca temporal o periodo de referencia del registro."
            uso = "Permite realizar análisis de series de tiempo, tendencias y cumplimiento de términos."
            obs = "Se recomienda validar el formato de fecha (DD/MM/YYYY) en el origen."
        elif any(x in campo for x in ['MUNICIPIO', 'DEPTO', 'DEPARTAMENTO', 'PAIS', 'DIVIPOLA', 'LUGAR', 'LATITUD', 'LONGITUD']):
            desc = "Atributo de ubicación geográfica o administrativa."
            uso = "Fundamental para la territorialización de la información y creación de mapas de calor."
            obs = "Cruzar con codificación DIVIPOLA del DANE para garantizar integridad referencial."
            origen = "DANE - Geografía"
        elif any(x in campo for x in ['SEXO', 'GENERO', 'ORIENTACION', 'EDAD', 'DISCAPACIDAD', 'ETNICO', 'INDIGENA', 'RANGO_EDAD']):
            desc = "Variable sociodemográfica de caracterización poblacional."
            uso = "Utilizado para aplicar enfoques diferenciales y analizar el impacto en grupos vulnerables."
            obs = "Dato sensible: Su tratamiento debe cumplir con la Ley de Protección de Datos Personales."
            sensibilidad = "PII - Sensible"
            origen = "Sistema de Registro Poblacional"
        elif any(x in campo for x in ['PETICION', 'RADICADO', 'SOLICITUD', 'RUP', 'NUMERO', 'ID', 'EXPEDIENTE']):
            desc = "Identificador único o número de radicado del trámite o proceso o registro."
            uso = "Garantiza la trazabilidad del registro y permite realizar uniones (joins) con otros módulos."
            obs = "Actúa generalmente como llave primaria (PK) o foránea (FK)."
            is_pk = "Sí" # Inferencia de Clave Primaria
            origen = "Sistema de Gestión de Casos/Peticiones"
        elif campo.startswith('COD_'):
            desc = "Código identificador único para una entidad (ej. código de departamento, municipio)."
            uso = "Permite la identificación unívoca y la integración con catálogos de referencia."
            obs = "Frecuentemente utilizado como llave primaria o parte de una llave compuesta."
            is_pk = "Sí" # Inferencia de Clave Primaria
            origen = "Catálogo de Referencia (ej. DANE)"
        elif any(x in campo for x in ['DEPENDENCIA', 'FUENTE', 'GESTIONADA_POR', 'USER_FUN']):
            desc = "Referencia a la unidad administrativa o usuario responsable de la gestión."
            uso = "Permite auditar el flujo de trabajo y medir la carga operativa por dependencias."
            obs = "Relacionado con la estructura organizacional interna."
            origen = "Sistema de Gestión Interna"
            
        elif any(x in campo for x in ['TITULO', 'TEXTO', 'TITULAR', 'HECHOS', 'SOLICITUD', 'CLOB']):
            desc = "Contenido narrativo, descriptivo o cuerpo del documento."
            uso = "Almacena el detalle cualitativo de la información para análisis de texto o consulta directa."
            obs = "Al ser un campo de texto largo (CLOB), puede impactar el rendimiento en consultas masivas."
            sensibilidad = "Confidencial (si contiene detalles de casos)"
            origen = "Sistema de Documentación/Noticias"

        # Lógica de transformación basada en el esquema
        if row['Esquema'] == 'Plata':
            logica_transf = "Limpieza y estandarización de datos"
        elif row['Esquema'] == 'Oro':
            logica_transf = "Agregación y transformación para análisis de negocio"
        
        # Refinamiento por contexto de tabla
        if 'SENTENCIAS' in tabla:
            desc += " (Contexto Jurídico/Sentencias)."
        elif 'NOTICIAS' in tabla:
            desc += " (Monitoreo de Medios)."
            
        return pd.Series([desc, uso, obs, is_pk, origen, logica_transf, sensibilidad])

    df[['Descripción funcional', 'Para qué sirve el campo', 'Observaciones', 'Clave Primaria', 'Origen del Dato', 'Lógica de Transformación', 'Sensibilidad del Dato']] = df.apply(get_ai_metadata, axis=1)
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

st.title("Diccionario de Datos Oracle")
st.markdown("""
Esta aplicación organiza la información de las tablas de la capa **BRONCE - PLATA Y ORO**.
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
    
    # Clasificar automáticamente
    df = classify_data_automatically(df)
    
    # Calcular estadísticas
    df_stats = calculate_dataset_statistics(df)
    
    if not df.empty:
        # Crear pestañas para organizar la aplicación
        tab_catalogo, tab_busqueda, tab_perfiles, tab_glosario, tab_lineage, tab_schema = st.tabs([
            "📋 Catálogo Central", "🔍 Búsqueda Avanzada", "📊 Perfiles de Datasets", 
            "📚 Glosario de Negocios", "🔗 Linaje de Datos", "📐 Modelo Dimensional"
        ])

        with tab_catalogo:
            st.subheader("Catálogo de Datos Centralizado")
            st.markdown("""
            **Bienvenido al Catálogo de Datos** - Descubra, explore y entienda sus activos de datos.
            *Navegue por las pestañas para acceder a diferentes funcionalidades del catálogo.*
            """)
            
            # Métricas generales
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("📁 Total Tablas", df["Tabla"].nunique())
            col2.metric("🔢 Total Campos", len(df))
            col3.metric("🏷️ Dominios", df["Dominio"].nunique())
            col4.metric("👥 Dueños", len(df_stats['Esquema'].unique()))
            
            # Vista previa de datasets por calidad
            st.subheader("📈 Calidad de Datasets por Esquema")
            calidad_esquema = df_stats.groupby('Esquema')['Calidad_General'].mean().reset_index()
            st.bar_chart(calidad_esquema.set_index('Esquema'))
            
            # Tabla resumen con clasificaciones
            st.subheader("📋 Clasificación Automática de Datasets")
            display_df = df[['Tabla', 'Esquema', 'Tipo', 'Dominio', 'Criticidad', 'Confidencialidad']].drop_duplicates('Tabla')
            st.dataframe(display_df, use_container_width=True)

        with tab_busqueda:
            st.subheader("🔍 Búsqueda Avanzada de Datos")
            
            # Barra de búsqueda
            col1, col2 = st.columns([3, 1])
            with col1:
                search_query = st.text_input("🔎 Buscar tablas, campos o descripciones...", placeholder="Ej: cliente, fecha, sentencia...")
            with col2:
                st.write("")
                search_button = st.button("Buscar", type="primary")
            
            # Filtros avanzados
            with st.expander("🎛️ Filtros Avanzados"):
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    dominios_sel = st.multiselect("Dominio", options=DATA_TAXONOMY["Dominio"], default=DATA_TAXONOMY["Dominio"])
                    criticidad_sel = st.multiselect("Criticidad", options=DATA_TAXONOMY["Criticialidad"], default=DATA_TAXONOMY["Criticialidad"])
                
                with col2:
                    confidencialidad_sel = st.multiselect("Confidencialidad", options=DATA_TAXONOMY["Confidencialidad"], default=DATA_TAXONOMY["Confidencialidad"])
                    esquemas_sel = st.multiselect("Esquema", options=sorted(df["Esquema"].unique()), default=sorted(df["Esquema"].unique()))
                
                with col3:
                    tipos_sel = st.multiselect("Tipo", options=sorted(df["Tipo"].unique()), default=sorted(df["Tipo"].unique()))
                    estados_sel = st.multiselect("Estado", options=sorted(df["Estado"].unique()), default=sorted(df["Estado"].unique()))
            
            # Ejecutar búsqueda
            if search_query or search_button:
                filters = {
                    'Dominio': dominios_sel,
                    'Criticidad': criticidad_sel,
                    'Confidencialidad': confidencialidad_sel,
                    'Esquema': esquemas_sel,
                    'Tipo': tipos_sel,
                    'Estado': estados_sel
                }
                
                results = advanced_search(df, search_query, filters)
                
                if not results.empty:
                    st.success(f"✅ Se encontraron {len(results)} resultados")
                    
                    # Mostrar resultados con scores
                    if 'search_score' in results.columns:
                        display_cols = ['Tabla', 'Campo', 'Descripción funcional', 'Dominio', 'search_score']
                        display_results = results[display_cols].rename(columns={'search_score': 'Score'})
                        st.dataframe(display_results, use_container_width=True)
                    else:
                        st.dataframe(results, use_container_width=True)
                else:
                    st.warning("❌ No se encontraron resultados para su búsqueda")
            else:
                st.info("💡 Ingrese un término de búsqueda o use los filtros para explorar los datos")

        with tab_perfiles:
            st.subheader("📊 Perfiles Detallados de Datasets")
            
            # Selector de dataset
            tabla_sel = st.selectbox("📋 Seleccione un dataset para ver su perfil:", options=sorted(df["Tabla"].unique()))
            
            if tabla_sel:
                tabla_data = df[df["Tabla"] == tabla_sel]
                tabla_stat = df_stats[df_stats["Tabla"] == tabla_sel].iloc[0]
                
                # Información general
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("📊 Total Campos", tabla_stat['Total_Campos'])
                with col2:
                    st.metric("🔑 Claves Primarias", tabla_stat['Campos_PK'])
                with col3:
                    st.metric("⭐ Calidad General", f"{tabla_stat['Calidad_General']}/100")
                
                # Metadatos del dataset
                st.subheader("📋 Metadatos del Dataset")
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write(f"**Esquema:** {tabla_stat['Esquema']}")
                    st.write(f"**Tipo de Entidad:** {tabla_stat['Tipo_Entidad']}")
                    st.write(f"**Última Actualización:** {tabla_stat['Ultima_Actualizacion']}")
                
                with col2:
                    # Obtener dominio y dueño
                    dominio = tabla_data['Dominio'].iloc[0]
                    dueño = get_data_owner(dominio)
                    st.write(f"**Dominio:** {dominio}")
                    st.write(f"**Dueño del Dato:** {dueño}")
                    st.write(f"**Frecuencia de Actualización:** {tabla_data['Frecuencia_Actualizacion'].iloc[0]}")
                
                # Campos detallados
                st.subheader("📝 Detalle de Campos")
                campos_display = tabla_data[['Campo', 'Tipo de Dato', 'Clave Primaria', 'Descripción funcional', 'Sensibilidad del Dato', 'Para qué sirve el campo']]
                st.dataframe(campos_display, use_container_width=True)
                
                # Estadísticas de calidad
                st.subheader("📈 Métricas de Calidad")
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    pk_ratio = (tabla_stat['Campos_PK'] / tabla_stat['Total_Campos']) * 100
                    st.metric("🔑 % con PK", f"{pk_ratio:.1f}%")
                with col2:
                    doc_ratio = (tabla_data['Descripción funcional'].notna().sum() / len(tabla_data)) * 100
                    st.metric("📄 % Documentado", f"{doc_ratio:.1f}%")
                with col3:
                    sens_types = tabla_data['Sensibilidad del Dato'].nunique()
                    st.metric("🔒 Tipos de Sensibilidad", sens_types)
                with col4:
                    data_types = tabla_stat['Tipos_Datos']
                    st.metric("💾 Tipos de Datos", data_types)

        with tab_glosario:
            st.subheader("📚 Glosario de Negocios")
            
            # Buscador de términos
            term_search = st.text_input("🔍 Buscar término en glosario:", placeholder="Ej: cliente, expediente, sentencia...")
            
            if term_search:
                definition = get_business_definition(term_search)
                if "no encontrado" not in definition:
                    st.success(f"✅ **{term_search.upper()}**: {definition}")
                else:
                    st.warning(definition)
                    
                    # Sugerir términos similares
                    st.write("**Términos disponibles en el glosario:**")
                    for term in sorted(BUSINESS_GLOSSARY.keys()):
                        if term_search.upper() in term or term_search.lower() in term.lower():
                            st.write(f"• {term}: {BUSINESS_GLOSSARY[term]}")
            else:
                st.info("💡 **Glosario de Negocios** - Definiciones estandarizadas para términos clave")
                st.write("**Términos disponibles:**")
                
                # Mostrar todos los términos
                cols = st.columns(2)
                for i, (term, definition) in enumerate(sorted(BUSINESS_GLOSSARY.items())):
                    with cols[i % 2]:
                        with st.expander(f"📖 {term}"):
                            st.write(definition)
            
            # Estadísticas del glosario
            st.subheader("📊 Estadísticas del Glosario")
            col1, col2 = st.columns(2)
            with col1:
                st.metric("📝 Total Términos", len(BUSINESS_GLOSSARY))
            with col2:
                st.metric("🏢 Dominios Cubiertos", len(DATA_OWNERS))

        with tab_lineage:
            st.subheader("Mapa de Linaje Medallion y Relacional")
            st.info("Este gráfico muestra cómo viajan los datos entre capas y cómo se relacionan los procesos.")
            
            dot = graphviz.Digraph(comment='Linaje Defensoria')
            # Optimizamos el espacio: LR (Izquierda a Derecha), aumentamos separación entre nodos y niveles
            dot.attr(rankdir='LR', nodesep='0.5', ranksep='1.5')
            
            # 1. Nodos por tabla y esquema
            for _, row in df.drop_duplicates(['Tabla', 'Esquema']).iterrows():
                label = f"{row['Tabla']}\n({row['Esquema']})"
                color = 'lightblue' if row['Esquema'] == 'Bronce' else 'lightgreen' if row['Esquema'] == 'Plata' else 'gold'
                dot.node(f"{row['Tabla']}_{row['Esquema']}", label, style='filled', color=color, shape='box')

            # 2. Aristas: Linaje Medallion (Misma tabla entre capas)
            tables = df['Tabla'].unique()
            for t in tables:
                layers = df[df['Tabla'] == t]['Esquema'].unique()
                if 'Bronce' in layers and 'Plata' in layers:
                    dot.edge(f"{t}_Bronce", f"{t}_Plata", label="ETL Plata", color='blue')
                if 'Plata' in layers and 'Oro' in layers:
                    dot.edge(f"{t}_Plata", f"{t}_Oro", label="ETL Oro", color='darkgreen')

            # 3. Aristas: Linaje Relacional (Comparten Clave Primaria)
            pk_fields = df[df['Clave Primaria'] == 'Sí'][['Tabla', 'Esquema', 'Campo']]
            for campo in pk_fields['Campo'].unique():
                relevant_tables = pk_fields[pk_fields['Campo'] == campo]
                if len(relevant_tables) > 1:
                    base_node = f"{relevant_tables.iloc[0]['Tabla']}_{relevant_tables.iloc[0]['Esquema']}"
                    for idx in range(1, len(relevant_tables)):
                        target_node = f"{relevant_tables.iloc[idx]['Tabla']}_{relevant_tables.iloc[idx]['Esquema']}"
                        if base_node != target_node:
                            dot.edge(base_node, target_node, label=f"Ref: {campo}", style='dashed', color='gray')

            st.graphviz_chart(dot, use_container_width=True)

        with tab_schema:
            st.subheader("Análisis de Esquema Estrella / Copo de Nieve")
            st.markdown("""
            Esta vista muestra la relación técnica entre entidades del esquema **Oro**. 
            Permite identificar si el modelo es tipo estrella o si existen dimensiones normalizadas (copo de nieve).
            """)
            
            # Filtrar por el esquema Oro que es donde reside el modelo dimensional
            df_oro = df[df["Esquema"] == "Oro"]
            
            if df_oro.empty:
                st.warning("No se detectaron tablas en el esquema 'Oro' para generar el modelo dimensional.")
            else:
                # --- Mejorar legibilidad mediante filtros por Hechos ---
                st.info("💡 **Consejo de Visualización**: Seleccione una o dos tablas de Hechos para que el diagrama sea legible y los cuadros se vean grandes.")
                
                lista_hechos = sorted(df_oro[df_oro["Tipo"] == "Hechos"]["Tabla"].unique())
                
                col_f1, col_f2 = st.columns([2, 1])
                with col_f1:
                    hechos_seleccionados = st.multiselect(
                        "Filtrar por Tablas de Hechos (Fact):",
                        options=lista_hechos,
                        default=lista_hechos[:1] if lista_hechos else []
                    )
                
                # Lógica para identificar qué mostrar: Hechos seleccionados + Dimensiones relacionadas
                if hechos_seleccionados:
                    # Campos (llaves) presentes en los hechos seleccionados
                    campos_en_hechos = df_oro[df_oro["Tabla"].isin(hechos_seleccionados)]["Campo"].unique()
                    # Dimensiones que tienen su PK presente en esos hechos
                    dimensiones_relacionadas = df_oro[
                        (df_oro["Tipo"] == "Dimensión") & 
                        (df_oro["Clave Primaria"] == "Sí") & 
                        (df_oro["Campo"].isin(campos_en_hechos))
                    ]["Tabla"].unique()
                    
                    entidades_visibles = list(hechos_seleccionados) + list(dimensiones_relacionadas)
                    df_display = df_oro[df_oro["Tabla"].isin(entidades_visibles)]
                else:
                    st.warning("Seleccione al menos una tabla de Hechos para visualizar el modelo.")
                    st.stop()

                # Crear grafo para el modelo de datos
                schema_dot = graphviz.Digraph(comment='Modelo Dimensional')
                # Ajustamos la orientación a LR y aumentamos significativamente el espaciado
                schema_dot.attr(rankdir='LR', nodesep='1.5', ranksep='3.0')
                # Configuramos fuentes masivas y tamaños para legibilidad en pantallas grandes
                schema_dot.attr('node', fontsize='30', fontname='Arial Bold', width='4.5', height='2')
                schema_dot.attr('edge', fontsize='20', fontname='Arial', penwidth='2.5')
                
                # 1. Crear Nodos con formas distintivas por Tipo
                unique_entities = df_display.drop_duplicates('Tabla')
                for _, row in unique_entities.iterrows():
                    t_name = row['Tabla']
                    t_tipo = row['Tipo']
                    
                    if t_tipo == "Hechos":
                        schema_dot.node(t_name, f"{t_name}\n(HECHOS)", shape='box3d', style='filled', color='#FFD700', margin='0.3')
                    elif t_tipo == "Dimensión":
                        schema_dot.node(t_name, f"{t_name}\n(DIMENSIÓN)", shape='component', style='filled', color='#E0E0E0', margin='0.3')
                    else:
                        schema_dot.node(t_name, f"{t_name}\n({t_tipo})", shape='box', style='filled', color='#F5F5F5', margin='0.3')
                
                # 2. Establecer relaciones basadas en Claves Primarias que existen en otras tablas
                # Buscamos PKs de las entidades visibles para trazar uniones
                pks_visibles = df_display[df_display["Clave Primaria"] == "Sí"]
                
                for _, pk_row in pks_visibles.iterrows():
                    # Buscar dónde se usa esta columna en otras tablas visibles
                    matches = df_display[(df_display["Campo"] == pk_row["Campo"]) & (df_display["Tabla"] != pk_row["Tabla"])]
                    for _, match in matches.iterrows():
                        schema_dot.edge(pk_row["Tabla"], match["Tabla"], label=pk_row["Campo"], color="#2E86C1", fontcolor="#1B4F72")
                
                st.graphviz_chart(schema_dot, use_container_width=True)

    else:
        st.warning("No se pudo extraer información. Verifica el formato del archivo.")
