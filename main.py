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
    "Criticidad": ["Alta", "Media", "Baja"],
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

# Catálogo de productos de datos
DATA_PRODUCTS = {
    "TBL": {
        "nombre": "Tablero",
        "descripcion": "Tablero de visualización interactivo (Power BI u otra herramienta)",
        "tipo": "Visualización",
        "frecuencia": "Diaria",
        "formato": "Interactivo",
        "tecnologia": "Power BI/Tableau/Looker"
    },
    "INF": {
        "nombre": "Informe",
        "descripcion": "Documento de informe técnico o de gestión",
        "tipo": "Documento",
        "frecuencia": "Mensual/Trimestral",
        "formato": "PDF/Word",
        "tecnologia": "Office/LaTeX"
    },
    "BLT": {
        "nombre": "Boletín",
        "descripcion": "Boletín estadístico o de divulgación",
        "tipo": "Publicación",
        "frecuencia": "Semanal/Mensual",
        "formato": "PDF/HTML",
        "tecnologia": "InDesign/HTML"
    },
    "MAP": {
        "nombre": "Mapa",
        "descripcion": "Producto cartográfico o de georreferenciación",
        "tipo": "Geovisualización",
        "frecuencia": "Variable",
        "formato": "Interactive/Static",
        "tecnologia": "ArcGIS/QGIS/Leaflet"
    },
    "MOD": {
        "nombre": "Modelo",
        "descripcion": "Modelo estadístico o matemático",
        "tipo": "Analítico",
        "frecuencia": "Periódica",
        "formato": "Python/R/Excel",
        "tecnologia": "Python/R/SAS"
    },
    "LPG": {
        "nombre": "Landing Page",
        "descripcion": "Página web de presentación de resultados o información",
        "tipo": "Web",
        "frecuencia": "Continua",
        "formato": "HTML/CSS/JS",
        "tecnologia": "React/Angular/Vue"
    },
    "API": {
        "nombre": "API",
        "descripcion": "Interfaz de programación para consumo de datos",
        "tipo": "Servicio",
        "frecuencia": "24/7",
        "formato": "JSON/XML",
        "tecnologia": "REST/GraphQL"
    }
}

# Relación entre tablas y productos (ejemplo)
TABLE_PRODUCT_MAPPING = {
    # Tablas de hechos -> Productos comunes
    "FCT_": ["TBL", "INF", "API"],
    "PCT_": ["TBL", "INF", "API"],  # Nuevo: Tabla de Hechos
    "DIM_": ["TBL", "MAP", "API"],
    "AGG_": ["INF", "BLT", "MOD"],
    "VST_": ["API", "LPG"],
    "TBL_": ["API"],
    "TMP_": ["API"],  # Nuevo: Tabla Temporal
    "TRV_": ["API", "INF"]  # Nuevo: Transversal
}

# Catálogo de tipos de objetos de base de datos
OBJECT_TYPES = {
    "TBL": {
        "nombre": "Tabla",
        "descripcion": "Estructura principal de almacenamiento de datos",
        "capas": ["Bronce", "Plata", "Oro"],
        "estructura": "Relacional",
        "ejemplo": "TBL_CLIENTES_V1",
        "observaciones": "Objeto principal para almacenamiento persistente"
    },
    "TMP": {
        "nombre": "Tabla Temporal",
        "descripcion": "Almacenamiento temporal de datos durante procesos",
        "capas": ["Bronce", "Plata"],
        "estructura": "Relacional",
        "ejemplo": "TMP_CARGA_20231201",
        "observaciones": "Datos temporales, normalmente con ciclo de vida corto"
    },
    "IND": {
        "nombre": "Índice",
        "descripcion": "Estructura de optimización para consultas",
        "capas": ["Bronce", "Plata", "Oro"],
        "estructura": "Árbol B+",
        "ejemplo": "IND_TBL_CLIENTES_PK",
        "observaciones": "Mejora rendimiento de consultas específicas"
    },
    "PRC": {
        "nombre": "Procedimiento Almacenado",
        "descripcion": "Lógica de negocio ejecutable en base de datos",
        "capas": ["Plata", "Oro"],
        "estructura": "Procedimental",
        "ejemplo": "PRC_CALCULAR_INDICADORES",
        "observaciones": "Contiene lógica de transformación compleja"
    },
    "PKG": {
        "nombre": "Paquete",
        "descripcion": "Colección de procedimientos y funciones relacionados",
        "capas": ["Plata", "Oro"],
        "estructura": "Modular",
        "ejemplo": "PKG_TRANSFORMACIONES",
        "observaciones": "Organiza código lógico por funcionalidad"
    },
    "DIM": {
        "nombre": "Dimensión",
        "descripcion": "Tabla de características descriptivas para análisis",
        "capas": ["Oro"],
        "estructura": "Estrella",
        "ejemplo": "DIM_TIEMPO_V1",
        "observaciones": "Componente clave del modelo dimensional"
    },
    "PCT": {
        "nombre": "Tabla de Hechos",
        "descripcion": "Tabla con métricas y medidas numéricas",
        "capas": ["Oro"],
        "estructura": "Hechos",
        "ejemplo": "PCT_VENTAS_DIARIAS",
        "observaciones": "Contiene datos cuantitativos para análisis"
    },
    "AGG": {
        "nombre": "Tabla Agregada",
        "descripcion": "Datos pre-agregados para mejorar rendimiento",
        "capas": ["Oro"],
        "estructura": "Agregada",
        "ejemplo": "AGG_VENTAS_MENSUALES",
        "observaciones": "Optimiza consultas de análisis agregado"
    },
    "VST": {
        "nombre": "Vista",
        "descripcion": "Consulta virtualizada sobre tablas base",
        "capas": ["Plata", "Oro"],
        "estructura": "Virtual",
        "ejemplo": "VST_CLIENTES_ACTIVOS",
        "observaciones": "Simplifica acceso y oculta complejidad"
    },
    "FNC": {
        "nombre": "Función",
        "descripcion": "Lógica reutilizable que retorna valores",
        "capas": ["Plata", "Oro"],
        "estructura": "Funcional",
        "ejemplo": "FNC_CALCULAR_EDAD",
        "observaciones": "Encapsula lógica de cálculo reusable"
    },
    "LOG": {
        "nombre": "LOG",
        "descripcion": "Registro de eventos y auditoría",
        "capas": ["Bronce", "Plata"],
        "estructura": "Secuencial",
        "ejemplo": "LOG_ERRORES_ETL",
        "observaciones": "Trazabilidad de procesos y errores"
    },
    "TRV": {
        "nombre": "Transversal",
        "descripcion": "Objeto compartido entre múltiples dominios",
        "capas": ["Bronce", "Plata", "Oro"],
        "estructura": "Compartida",
        "ejemplo": "TRV_PARAMETROS_GLOBALES",
        "observaciones": "Datos comunes a múltiples procesos"
    }
}

# Dominios organizacionales de la Defensoría del Pueblo
ORGANIZATIONAL_DOMAINS = {
    # Despachos y Centros de Analítica
    "DVDP": {"nombre": "Despacho del Vice Defensor del Pueblo", "tipo": "Despacho", "nivel": "Alto"},
    "CADDDH": {"nombre": "Centro de Analítica de Datos de Derechos Humanos", "tipo": "Centro Analítica", "nivel": "Alto"},
    
    # Direcciones Nacionales
    "DN-ATQ": {"nombre": "Dirección Nacional de Atención y Trámite de Quejas", "tipo": "Dirección Nacional", "nivel": "Alto"},
    "DN-DPU": {"nombre": "Dirección Nacional de Defensoría Pública", "tipo": "Dirección Nacional", "nivel": "Alto"},
    "DN-PYD": {"nombre": "Dirección Nacional de Promoción y Divulgación de Derechos Humanos", "tipo": "Dirección Nacional", "nivel": "Alto"},
    "DN-RAJ": {"nombre": "Dirección Nacional de Recursos y Acciones Judiciales", "tipo": "Dirección Nacional", "nivel": "Alto"},
    
    # Defensorías Delegadas (Subdominio DD-)
    "DD-AAT": {"nombre": "Defensoría Delegada para Asuntos Agrarios y Tierras", "tipo": "Defensoría Delegada", "nivel": "Medio"},
    "DD-ACL": {"nombre": "Defensoría Delegada para Asuntos Constitucionales y Legales", "tipo": "Defensoría Delegada", "nivel": "Medio"},
    "DD-SSS": {"nombre": "Defensoría Delegada para el Derecho a la Salud y Seguridad Social", "tipo": "Defensoría Delegada", "nivel": "Medio"},
    "DD-DCA": {"nombre": "Defensoría Delegada para los Derechos Colectivos y del Ambiente", "tipo": "Defensoría Delegada", "nivel": "Medio"},
    "DD-PMH": {"nombre": "Defensoría Delegada para los Derechos de la Población en Movilidad Humana", "tipo": "Defensoría Delegada", "nivel": "Medio"},
    "DD-MAG": {"nombre": "Defensoría Delegada para los Derechos de las Mujeres y Asuntos de Género", "tipo": "Defensoría Delegada", "nivel": "Medio"},
    "DD-ESC": {"nombre": "Defensoría Delegada para los Derechos Económicos, Sociales y Culturales", "tipo": "Defensoría Delegada", "nivel": "Medio"},
    "DD-GE": {"nombre": "Defensoría Delegada para los Grupos Étnicos", "tipo": "Defensoría Delegada", "nivel": "Medio"},
    "DD-IV": {"nombre": "Defensoría Delegada para La Infancia y la Vejez", "tipo": "Defensoría Delegada", "nivel": "Medio"},
    "DD-JTDP": {"nombre": "Defensoría Delegada para la Justicia Transicional y el Derecho a la Paz", "tipo": "Defensoría Delegada", "nivel": "Medio"},
    "DD-VCAI": {"nombre": "Defensoría Delegada para la Orientación y Asesoría de las Víctimas del Conflicto Armado", "tipo": "Defensoría Delegada", "nivel": "Medio"},
    "DD-PCP": {"nombre": "Defensoría Delegada para la Política Criminal y Penitenciaria", "tipo": "Defensoría Delegada", "nivel": "Medio"},
    "DD-SAT": {"nombre": "Defensoría Delegada para la Prevención de Riesgos y Sistema de Alertas Tempranas", "tipo": "Defensoría Delegada", "nivel": "Medio"},
    "DD-PTCS": {"nombre": "Defensoría Delegada para la Prevención y la Transformación de la Conflictividad Social", "tipo": "Defensoría Delegada", "nivel": "Medio"},
    "DD-ADLE": {"nombre": "Defensoría Delegada para la Protección de Derechos en Ambientes Digitales y Libertad de Expresión", "tipo": "Defensoría Delegada", "nivel": "Medio"},
    "DD-PAD": {"nombre": "Defensoría Delegada para la Protección del Derecho a la Prevención y Atención de Desastres", "tipo": "Defensoría Delegada", "nivel": "Medio"},
    "DD-BJPDD": {"nombre": "Defensoría Delegada para el Buen Futuro de las Juventudes y la Protección del Derecho al Deporte", "tipo": "Defensoría Delegada", "nivel": "Medio"},
    "DD-RAT": {"nombre": "Defensoría Delegada para las Regiones y la Articulación Territorial en materia de DDHH y DIH", "tipo": "Defensoría Delegada", "nivel": "Medio"},
    "OAI": {"nombre": "Oficina de Asuntos de Internacionales", "tipo": "Oficina", "nivel": "Medio"},
    
    # Defensorías Regionales (Subdominio DR-)
    "DR-AMA": {"nombre": "Defensoría Regional Amazonas", "tipo": "Defensoría Regional", "nivel": "Bajo"},
    "DR-ANT": {"nombre": "Defensoría Regional Antioquia", "tipo": "Defensoría Regional", "nivel": "Bajo"},
    "DR-ARA": {"nombre": "Defensoría Regional Arauca", "tipo": "Defensoría Regional", "nivel": "Bajo"},
    "DR-ATL": {"nombre": "Defensoría Regional Atlántico", "tipo": "Defensoría Regional", "nivel": "Bajo"},
    "DR-BCA": {"nombre": "Defensoría Regional Bajo Cauca Antioqueño", "tipo": "Defensoría Regional", "nivel": "Bajo"},
    "DR-BOG": {"nombre": "Defensoría Regional Bogotá", "tipo": "Defensoría Regional", "nivel": "Bajo"},
    "DR-BOL": {"nombre": "Defensoría Regional Bolívar", "tipo": "Defensoría Regional", "nivel": "Bajo"},
    "DR-BOY": {"nombre": "Defensoría Regional Boyacá", "tipo": "Defensoría Regional", "nivel": "Bajo"},
    "DR-CAL": {"nombre": "Defensoría Regional Caldas", "tipo": "Defensoría Regional", "nivel": "Bajo"},
    "DR-CAQ": {"nombre": "Defensoría Regional Caquetá", "tipo": "Defensoría Regional", "nivel": "Bajo"},
    "DR-CAS": {"nombre": "Defensoría Regional Casanare", "tipo": "Defensoría Regional", "nivel": "Bajo"},
    "DR-CAU": {"nombre": "Defensoría Regional Cauca", "tipo": "Defensoría Regional", "nivel": "Bajo"},
    "DR-CES": {"nombre": "Defensoría Regional Cesar", "tipo": "Defensoría Regional", "nivel": "Bajo"},
    "DR-CHO": {"nombre": "Defensoría Regional Chocó", "tipo": "Defensoría Regional", "nivel": "Bajo"},
    "DR-COR": {"nombre": "Defensoría Regional Córdoba", "tipo": "Defensoría Regional", "nivel": "Bajo"},
    "DR-CUN": {"nombre": "Defensoría Regional Cundinamarca", "tipo": "Defensoría Regional", "nivel": "Bajo"},
    "DR-GUA": {"nombre": "Defensoría Regional Guainía", "tipo": "Defensoría Regional", "nivel": "Bajo"},
    "DR-GUV": {"nombre": "Defensoría Regional Guaviare", "tipo": "Defensoría Regional", "nivel": "Bajo"},
    "DR-HUI": {"nombre": "Defensoría Regional Huila", "tipo": "Defensoría Regional", "nivel": "Bajo"},
    "DR-LGU": {"nombre": "Defensoría Regional La Guajira", "tipo": "Defensoría Regional", "nivel": "Bajo"},
    "DR-MAG": {"nombre": "Defensoría Regional Magdalena", "tipo": "Defensoría Regional", "nivel": "Bajo"},
    "DR-MAGM": {"nombre": "Defensoría Regional Magdalena Medio", "tipo": "Defensoría Regional", "nivel": "Bajo"},
    "DR-MET": {"nombre": "Defensoría Regional Meta", "tipo": "Defensoría Regional", "nivel": "Bajo"},
    "DR-NAR": {"nombre": "Defensoría Regional Nariño", "tipo": "Defensoría Regional", "nivel": "Bajo"},
    "DR-NSAN": {"nombre": "Defensoría Regional Norte de Santander", "tipo": "Defensoría Regional", "nivel": "Bajo"},
    "DR-OCA": {"nombre": "Defensoría Regional Ocaña", "tipo": "Defensoría Regional", "nivel": "Bajo"},
    "DR-PAC": {"nombre": "Defensoría Regional Pacífico", "tipo": "Defensoría Regional", "nivel": "Bajo"},
    "DR-PUT": {"nombre": "Defensoría Regional Putumayo", "tipo": "Defensoría Regional", "nivel": "Bajo"},
    "DR-QUI": {"nombre": "Defensoría Regional Quindío", "tipo": "Defensoría Regional", "nivel": "Bajo"},
    "DR-RIS": {"nombre": "Defensoría Regional Risaralda", "tipo": "Defensoría Regional", "nivel": "Bajo"},
    "DR-SAP": {"nombre": "Defensoría Regional San Andrés y Providencia", "tipo": "Defensoría Regional", "nivel": "Bajo"},
    "DR-SAN": {"nombre": "Defensoría Regional Santander", "tipo": "Defensoría Regional", "nivel": "Bajo"},
    "DR-SOA": {"nombre": "Defensoría Regional Soacha", "tipo": "Defensoría Regional", "nivel": "Bajo"},
    "DR-SUC": {"nombre": "Defensoría Regional Sucre", "tipo": "Defensoría Regional", "nivel": "Bajo"},
    "DR-SBOL": {"nombre": "Defensoría Regional Sur de Bolívar", "tipo": "Defensoría Regional", "nivel": "Bajo"},
    "DR-SCOR": {"nombre": "Defensoría Regional Sur de Córdoba", "tipo": "Defensoría Regional", "nivel": "Bajo"},
    "DR-TOL": {"nombre": "Defensoría Regional Tolima", "tipo": "Defensoría Regional", "nivel": "Bajo"},
    "DR-TUM": {"nombre": "Defensoría Regional Tumaco", "tipo": "Defensoría Regional", "nivel": "Bajo"},
    "DR-URDA": {"nombre": "Defensoría Regional Urabá – Darién", "tipo": "Defensoría Regional", "nivel": "Bajo"},
    "DR-VCAU": {"nombre": "Defensoría Regional Valle del Cauca", "tipo": "Defensoría Regional", "nivel": "Bajo"},
    "DR-VAU": {"nombre": "Defensoría Regional Vaupés", "tipo": "Defensoría Regional", "nivel": "Bajo"},
    "DR-VIC": {"nombre": "Defensoría Regional Vichada", "tipo": "Defensoría Regional", "nivel": "Bajo"}
}

# Mapeo de prefijos/palabras clave de tablas a dominios organizacionales de la Defensoría
# Esto ayuda a clasificar tablas de fuentes externas o temas específicos bajo una unidad interna.
TABLE_PREFIX_TO_ORG_DOMAIN_MAPPING = {
    "DANE": "CADDDH",      # Datos del DANE, usados para análisis por CADDDH
    "FGN": "DD-VCAI",      # Datos de Fiscalía General de la Nación, relacionados con víctimas
    "MDL": "CADDDH",       # Modelos/Módulos analíticos, gestionados por CADDDH
    "UARIV": "DD-VCAI",    # Datos de la Unidad para las Víctimas, gestionados por DD-VCAI
    "DPCFIO": "CADDDH",    # Proyectos específicos de casos FIO, analizados por CADDDH
    "NOTICIAS": "DN-PYD",  # Monitoreo de medios, para Promoción y Divulgación
    "FAUNA": "DD-DCA",     # Fauna Silvestre, para Derechos Colectivos y del Ambiente
    "SENTENCIAS": "DN-RAJ" # Sentencias Judiciales, para Recursos y Acciones Judiciales
}


# Reglas generales de nombramiento para gobierno de datos
NAMING_RULES = {
    "RULE_1": {
        "nombre": "Sin números al inicio",
        "descripcion": "No comenzar el nombre con dígitos",
        "ejemplo_correcto": "TBLPYDVICTIMA",
        "ejemplo_incorrecto": "1TBLPYDVICTIMA"
    },
    "RULE_2": {
        "nombre": "Sin caracteres especiales",
        "descripcion": "Solo se permite guion bajo (_) como separador entre componentes",
        "ejemplo_correcto": "TBL_PYD_VICTIMA",
        "ejemplo_incorrecto": "TBL-PYD-VICTIMA"
    },
    "RULE_3": {
        "nombre": "Nombre en singular y sin artículos ni preposiciones",
        "descripcion": "Usar nombres simples y directos",
        "ejemplo_correcto": "ATENCIONVICTIMA",
        "ejemplo_incorrecto": "ATENCION_DE_VICTIMAS"
    },
    "RULE_4": {
        "nombre": "Máximo 40 caracteres para el Nombre del Objeto",
        "descripcion": "Aplica al componente 'Nombre' sin contar el prefijo ni el dominio",
        "ejemplo_correcto": "TBL_PYD_ATENCIONCIUDADANA",
        "ejemplo_incorrecto": "TBL_PYD_ATENCIONCIUDADANAMUYLARGO"
    },
    "RULE_5": {
        "nombre": "IND, PRC y PKG toman el nombre de la tabla a la que pertenecen",
        "descripcion": "Estos objetos deben referenciar su tabla principal",
        "ejemplo_correcto": "IND_PYD_ATENCIONVICTIMA",
        "ejemplo_incorrecto": "IND_PYD_OTRATABLA"
    },
    "RULE_6": {
        "nombre": "Patrón con {FUENTE}_Prefijo_DOMINIO_FUENTE_NOMBRE",
        "descripcion": "Solo aplica cuando DOMINIO es TRANSVERSAL",
        "ejemplo_correcto": "FCT_TRV_SPDA_CONSOLIDADOVICTIMA",
        "ejemplo_incorrecto": "FCT_SPDA_CONSOLIDADOVICTIMA"
    }
}

# Palabras prohibidas en nombres (artículos y preposiciones)
FORBIDDEN_WORDS = {
    'DE', 'DEL', 'LA', 'EL', 'LOS', 'LAS', 'UN', 'UNA', 'UNOS', 'UNAS',
    'EN', 'CON', 'POR', 'PARA', 'A', 'ANTE', 'BAJO', 'CABE', 'CONTRA',
    'DE', 'DESDE', 'DURANTE', 'ENTRE', 'HACIA', 'HASTA', 'MEDIANTE',
    'PARA', 'POR', 'SEGUN', 'SIN', 'SOBRE', 'TRAS', 'DURANTE', 'MEDIANTE'
}

# Patrones de nomenclatura por capa
LAYER_NAMING_PATTERNS = {
    "Bronce": {
        "TBL_[SUBDOMINIO]_[NOMBRE]": {
            "descripcion": "Definiciones de tablas generales",
            "patron": r"^TBL_[A-Z]+_[A-Z_]+$",
            "ejemplos": ["TBL_AFC_SD_ENTIDAD_OBLIGADA", "TBL_PYD_IND_RESERVA"],
            "aplica_para": "Tablas"
        },
        "TBL_TRV_[SUBDOMINIO]_[NOMBRE]": {
            "descripcion": "Definiciones de tablas transversales",
            "patron": r"^TBL_TRV_[A-Z]+_[A-Z_]+$",
            "ejemplos": ["TBL_TRV_DDHH_VICTIMAS_SOCIALES", "TBL_TRV_IND_POBLACION_VICTIMA_DEL_CONFLICTO_ARMADO"],
            "aplica_para": "Tablas Transversales"
        }
    },
    "Plata": {
        "TBL_[SUBDOMINIO]_[NOMBRE]": {
            "descripcion": "Definiciones de tablas generales",
            "patron": r"^TBL_[A-Z]+_[A-Z_]+$",
            "ejemplos": ["TBL_AFC_SD_ENTIDAD_OBLIGADA", "TBL_PYD_IND_RESERVA"],
            "aplica_para": "Tablas"
        },
        "TBL_TRV_[SUBDOMINIO]_[NOMBRE]": {
            "descripcion": "Definiciones de tablas transversales",
            "patron": r"^TBL_TRV_[A-Z]+_[A-Z_]+$",
            "ejemplos": ["TBL_TRV_DDHH_VICTIMAS_SOCIALES", "TBL_TRV_IND_POBLACION_VICTIMA_DEL_CONFLICTO_ARMADO"],
            "aplica_para": "Tablas Transversales"
        },
        "PKG_[SUBDOMINIO]_[AREA ASOCIADA]": {
            "descripcion": "Definiciones para paquetes en Plata y Oro",
            "patron": r"^PKG_[A-Z]+_[A-Z_]+$",
            "ejemplos": ["PKG_DDHH_VICTIMAS_SOCIALES", "PKG_DDHH_DERECHO_HUMANOS"],
            "aplica_para": "Paquetes"
        }
    },
    "Oro": {
        "PKG_[SUBDOMINIO]_[AREA ASOCIADA]": {
            "descripcion": "Definiciones para paquetes en Plata y Oro",
            "patron": r"^PKG_[A-Z]+_[A-Z_]+$",
            "ejemplos": ["PKG_DDHH_VICTIMAS_SOCIALES", "PKG_DDHH_DERECHO_HUMANOS"],
            "aplica_para": "Paquetes"
        },
        "PRC_[SUBDOMINIO]_[AREA ASOCIADA]": {
            "descripcion": "Definiciones para procedimientos almacenados en Plata y Oro",
            "patron": r"^PRC_[A-Z]+_[A-Z_]+$",
            "ejemplos": ["PRC_DDHH_VICTIMAS_SOCIALES", "PRC_DDHH_DERECHO_HUMANOS"],
            "aplica_para": "Procedimientos"
        },
        "VST_[SUBDOMINIO]_[AREA ASOCIADA]": {
            "descripcion": "Definiciones para vistas en Plata y Oro",
            "patron": r"^VST_[A-Z]+_[A-Z_]+$",
            "ejemplos": ["VST_DDHH_VICTIMAS_SOCIALES", "VST_DDHH_DERECHO_HUMANOS"],
            "aplica_para": "Vistas"
        },
        "[PREFIJO]_[DOMINIO]_[NOMBRE]": {
            "descripcion": "Definiciones de tablas generales",
            "patron": r"^(TBL|DIM|FCT|AGG)_[A-Z]+_[A-Z_]+$",
            "ejemplos": ["DIM_RUC_DDP_DNI_CUI", "FCT_PYD_ATENCION_CIUDADANA"],
            "aplica_para": "Tablas Dimensionales/Hechos/Agregadas"
        },
        "[PREFIJO]_TRV_[PUENTE]_[NOMBRE]": {
            "descripcion": "Definiciones de tablas transversales",
            "patron": r"^(TBL|DIM|FCT|AGG)_TRV_[A-Z]+_[A-Z_]+$",
            "ejemplos": ["DIM_TRV_DDHH_VICTIMAS", "FCT_TRV_POBLACION_VICTIMA_DEL_CONFLICTO_ARMADO"],
            "aplica_para": "Tablas Transversales Dimensionales/Hechos/Agregadas"
        }
    }
}

# Mapeo de prefijos a patrones aplicables
PREFIX_PATTERN_MAPPING = {
    "TBL": ["TBL_[SUBDOMINIO]_[NOMBRE]", "TBL_TRV_[SUBDOMINIO]_[NOMBRE]", "[PREFIJO]_[DOMINIO]_[NOMBRE]", "[PREFIJO]_TRV_[PUENTE]_[NOMBRE]"],
    "DIM": ["[PREFIJO]_[DOMINIO]_[NOMBRE]", "[PREFIJO]_TRV_[PUENTE]_[NOMBRE]"],
    "FCT": ["[PREFIJO]_[DOMINIO]_[NOMBRE]", "[PREFIJO]_TRV_[PUENTE]_[NOMBRE]"],
    "AGG": ["[PREFIJO]_[DOMINIO]_[NOMBRE]", "[PREFIJO]_TRV_[PUENTE]_[NOMBRE]"],
    "TMP": ["TBL_[SUBDOMINIO]_[NOMBRE]"],
    "IND": ["TBL_[SUBDOMINIO]_[NOMBRE]"],
    "PKG": ["PKG_[SUBDOMINIO]_[AREA ASOCIADA]"],
    "PRC": ["PRC_[SUBDOMINIO]_[AREA ASOCIADA]"],
    "VST": ["VST_[SUBDOMINIO]_[AREA ASOCIADA]"]
}

# Nomenclatura y tipificación de campos gobernados
FIELD_NOMENCLATURE = {
    "ID": {
        "descripcion": "Identificador único principal de la entidad",
        "tipo_dato": "VARCHAR2",
        "patron": "ID_[ENTIDAD]",
        "ejemplo": "ID_PERSONA",
        "notas": "Primary key de la tabla. No nulo, único",
        "longitud_recomendada": 20,
        "oracle_type": "VARCHAR2(20)"
    },
    "CD": {
        "descripcion": "Código de referencia externa o catálogo",
        "tipo_dato": "VARCHAR2",
        "patron": "CD_[ENTIDAD_REFERENCIA]",
        "ejemplo": "CD_DEPARTAMENTO",
        "notas": "Código de catálogo maestro. Referencia a tablas de parámetros",
        "longitud_recomendada": 10,
        "oracle_type": "VARCHAR2(10)"
    },
    "NM": {
        "descripcion": "Nombre descriptivo de la entidad",
        "tipo_dato": "VARCHAR2",
        "patron": "NM_[ENTIDAD]",
        "ejemplo": "NM_PERSONA",
        "notas": "Nombre completo o descriptivo. Puede contener espacios",
        "longitud_recomendada": 200,
        "oracle_type": "VARCHAR2(200)"
    },
    "DS": {
        "descripcion": "Descripción detallada o texto largo",
        "tipo_dato": "CLOB",
        "patron": "DS_[DESCRIPCION]",
        "ejemplo": "DS_OBSERVACIONES",
        "notas": "Texto largo con descripciones detalladas. Permite formato libre",
        "longitud_recomendada": "CLOB",
        "oracle_type": "CLOB"
    },
    "FH": {
        "descripcion": "Fecha y hora del evento o registro",
        "tipo_dato": "TIMESTAMP",
        "patron": "FH_[EVENTO]",
        "ejemplo": "FH_CREACION",
        "notas": "Fecha y hora completa. Incluir zona horaria si es necesario",
        "longitud_recomendada": "TIMESTAMP",
        "oracle_type": "TIMESTAMP"
    },
    "VL": {
        "descripcion": "Valor numérico o métrica",
        "tipo_dato": "NUMBER",
        "patron": "VL_[MEDIDA]",
        "ejemplo": "VL_MONTO",
        "notas": "Valor numérico. Definir precisión y escala según negocio",
        "longitud_recomendada": "NUMBER(18,2)",
        "oracle_type": "NUMBER(18,2)"
    },
    "TP": {
        "descripcion": "Tipo o clasificación del dato",
        "tipo_dato": "VARCHAR2",
        "patron": "TP_[CLASIFICACION]",
        "ejemplo": "TP_DOCUMENTO",
        "notas": "Tipo o categoría. Valores controlados por catálogo",
        "longitud_recomendada": 50,
        "oracle_type": "VARCHAR2(50)"
    },
    "FL": {
        "descripcion": "Bandera o indicador booleano",
        "tipo_dato": "CHAR",
        "patron": "FL_[INDICADOR]",
        "ejemplo": "FL_ACTIVO",
        "notas": "S/N o 1/0. Indicador de estado o condición",
        "longitud_recomendada": 1,
        "oracle_type": "CHAR(1)"
    },
    "TS_CARGA": {
        "descripcion": "Timestamp de carga del dato",
        "tipo_dato": "TIMESTAMP",
        "patron": "TS_CARGA",
        "ejemplo": "TS_CARGA",
        "notas": "Fecha y hora de carga ETL. Auditoría de procesos",
        "longitud_recomendada": "TIMESTAMP",
        "oracle_type": "TIMESTAMP"
    },
    "TS_ACT": {
        "descripcion": "Timestamp de última actualización",
        "tipo_dato": "TIMESTAMP",
        "patron": "TS_ACT",
        "ejemplo": "TS_ACT",
        "notas": "Fecha y hora de última modificación. Control de cambios",
        "longitud_recomendada": "TIMESTAMP",
        "oracle_type": "TIMESTAMP"
    }
}

# Reglas de validación de campos
FIELD_VALIDATION_RULES = {
    "longitud_maxima": {
        "VARCHAR2": 4000,
        "CHAR": 2000,
        "NUMBER": 38
    },
    "patrones_obligatorios": {
        "timestamps": ["TS_CARGA", "TS_ACT"],
        "identificadores": ["ID"],
        "banderas": ["FL"]
    },
    "tipos_por_patron": {
        "^ID_.*": "VARCHAR2",
        "^CD_.*": "VARCHAR2",
        "^NM_.*": "VARCHAR2",
        "^DS_.*": "CLOB",
        "^FH_.*": "TIMESTAMP",
        "^VL_.*": "NUMBER",
        "^TP_.*": "VARCHAR2",
        "^FL_.*": "CHAR"
    }
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

def assign_data_products(df):
    """
    Asigna productos de datos potenciales a cada tabla según su tipo
    """
    def get_products_for_table(row):
        tabla = str(row['Tabla']).upper()
        
        # Buscar productos según prefijo de la tabla
        for prefix, products in TABLE_PRODUCT_MAPPING.items():
            if tabla.startswith(prefix):
                return ", ".join(products)
        
        # Si no coincide con ningún prefijo, asignar productos genéricos
        return "API"
    
    df['Productos_Potenciales'] = df.drop_duplicates('Tabla').apply(get_products_for_table, axis=1)
    return df

def get_product_details(product_code):
    """
    Obtiene detalles completos de un producto de datos
    """
    return DATA_PRODUCTS.get(product_code, {
        "nombre": "Desconocido",
        "descripcion": "Producto no identificado",
        "tipo": "Sin clasificar",
        "frecuencia": "No especificada",
        "formato": "Desconocido",
        "tecnologia": "N/A"
    })

def identify_organizational_domain(table_name):
    """
    Identifica el dominio organizacional basado en el nombre de la tabla
    usando la nomenclatura proporcionada (ej: 2026_001_HU_TBL_DVDP_V1)
    """
    # Patrón para extraer sigla de la nomenclatura
    import re
    
    # Buscar patrones comunes en nombres de tablas
    for domain_code, domain_info in ORGANIZATIONAL_DOMAINS.items():
        # Buscar la sigla en el nombre de la tabla
        if domain_code in table_name.upper():
            return domain_code, domain_info
    
    return None, None

def classify_by_organizational_domain(df):
    """
    Clasifica las tablas según dominio organizacional
    """
    def get_domain_info(row):
        tabla = str(row['Tabla'])
        domain_code, domain_info = identify_organizational_domain(tabla)
        
        if domain_code:
            return pd.Series([
                domain_code,
                domain_info['nombre'],
                domain_info['tipo'],
                domain_info['nivel']
            ])
        else:
            return pd.Series([
                'SIN_DOMINIO',
                'Sin dominio asignado',
                'No clasificado',
                'Bajo'
            ])
    
    df[['Dominio_Org', 'Nombre_Dominio', 'Tipo_Org', 'Nivel_Org']] = df.apply(get_domain_info, axis=1)
    return df

def get_organizational_stats(df):
    """
    Calcula estadísticas por dominio organizacional
    """
    if 'Dominio_Org' not in df.columns:
        return pd.DataFrame()
    
    stats = []
    for domain_code in df['Dominio_Org'].unique():
        if domain_code == 'SIN_DOMINIO':
            continue
            
        domain_data = df[df['Dominio_Org'] == domain_code]
        domain_info = ORGANIZATIONAL_DOMAINS.get(domain_code, {})
        
        stats.append({
            'Dominio': domain_code,
            'Nombre': domain_info.get('nombre', domain_code),
            'Tipo': domain_info.get('tipo', 'Desconocido'),
            'Nivel': domain_info.get('nivel', 'Bajo'),
            'Total_Tablas': domain_data['Tabla'].nunique(),
            'Total_Campos': len(domain_data),
            'Esquemas': ', '.join(sorted(domain_data['Esquema'].unique()))
        })
    
    return pd.DataFrame(stats)

def identify_object_type(table_name):
    """
    Identifica el tipo de objeto basado en el prefijo del nombre
    """
    for prefix, obj_info in OBJECT_TYPES.items():
        if table_name.upper().startswith(prefix + "_"):
            return prefix, obj_info
    
    # Si no coincide con ningún prefijo conocido
    return "TBL", OBJECT_TYPES["TBL"]  # Default a Tabla

def classify_by_object_type(df):
    """
    Clasifica las tablas según tipo de objeto de base de datos
    """
    def get_object_type_info(row):
        tabla = str(row['Tabla'])
        obj_code, obj_info = identify_object_type(tabla)
        
        return pd.Series([
            obj_code,
            obj_info['nombre'],
            obj_info['descripcion'],
            obj_info['estructura'],
            ", ".join(obj_info['capas'])
        ])
    
    df[['Tipo_Objeto', 'Nombre_Objeto', 'Desc_Objeto', 'Estructura_Objeto', 'Capas_Objeto']] = df.apply(get_object_type_info, axis=1)
    return df

def get_object_type_stats(df):
    """
    Calcula estadísticas por tipo de objeto
    """
    if 'Tipo_Objeto' not in df.columns:
        return pd.DataFrame()
    
    stats = []
    for obj_code in df['Tipo_Objeto'].unique():
        obj_data = df[df['Tipo_Objeto'] == obj_code]
        obj_info = OBJECT_TYPES.get(obj_code, {})
        
        stats.append({
            'Tipo_Objeto': obj_code,
            'Nombre': obj_info.get('nombre', obj_code),
            'Estructura': obj_info.get('estructura', 'Desconocida'),
            'Total_Tablas': obj_data['Tabla'].nunique(),
            'Total_Campos': len(obj_data),
            'Esquemas': ', '.join(sorted(obj_data['Esquema'].unique())),
            'Capas': obj_info.get('capas', [])
        })
    
    return pd.DataFrame(stats)

def check_naming_rules(table_name):
    """
    Verifica si un nombre de tabla cumple con todas las reglas de nombramiento
    """
    results = {
        'tabla': table_name,
        'reglas_cumplidas': [],
        'reglas_violadas': [],
        'puntaje_gobierno': 0,
        'recomendaciones': []
    }
    
    total_rules = len(NAMING_RULES)
    
    # Regla 1: Sin números al inicio
    if not table_name or not table_name[0].isdigit():
        results['reglas_cumplidas'].append('RULE_1')
        results['puntaje_gobierno'] += 1
    else:
        results['reglas_violadas'].append('RULE_1')
        results['recomendaciones'].append('Eliminar números al inicio del nombre')
    
    # Regla 2: Sin caracteres especiales (solo guion bajo)
    invalid_chars = re.findall(r'[^A-Z_]', table_name)
    if not invalid_chars:
        results['reglas_cumplidas'].append('RULE_2')
        results['puntaje_gobierno'] += 1
    else:
        results['reglas_violadas'].append('RULE_2')
        results['recomendaciones'].append(f'Remover caracteres especiales: {invalid_chars}')
    
    # Regla 3: Nombre en singular y sin artículos ni preposiciones
    words = re.findall(r'[A-Z]+', table_name)
    forbidden_found = [word for word in words if word in FORBIDDEN_WORDS]
    if not forbidden_found:
        results['reglas_cumplidas'].append('RULE_3')
        results['puntaje_gobierno'] += 1
    else:
        results['reglas_violadas'].append('RULE_3')
        results['recomendaciones'].append(f'Remover artículos/preposiciones: {forbidden_found}')
    
    # Regla 4: Máximo 40 caracteres para el nombre
    # Extraer el nombre (quitar prefijos y dominios)
    parts = table_name.split('_')
    if len(parts) >= 3:
        # Patrón: PREFIJO_DOMINIO_NOMBRE
        nombre_part = '_'.join(parts[2:]) if len(parts) > 2 else parts[-1]
    else:
        nombre_part = parts[-1] if parts else table_name
    
    if len(nombre_part) <= 40:
        results['reglas_cumplidas'].append('RULE_4')
        results['puntaje_gobierno'] += 1
    else:
        results['reglas_violadas'].append('RULE_4')
        results['recomendaciones'].append(f'Reducir nombre a menos de 40 caracteres (actual: {len(nombre_part)})')
    
    # Regla 5: IND, PRC y PKG toman el nombre de la tabla
    prefixes_check = ['IND', 'PRC', 'PKG']
    for prefix in prefixes_check:
        if table_name.startswith(prefix + '_'):
            # Debe contener el nombre de la tabla
            if len(parts) >= 3:
                results['reglas_cumplidas'].append('RULE_5')
                results['puntaje_gobierno'] += 1
            else:
                results['reglas_violadas'].append('RULE_5')
                results['recomendaciones'].append(f'{prefix} debe incluir nombre de tabla principal')
            break
    else:
        # No es IND/PRC/PKG, regla no aplica
        results['reglas_cumplidas'].append('RULE_5')
        results['puntaje_gobierno'] += 1
    
    # Regla 6: Patrón con TRANSVERSAL
    if 'TRV' in parts:
        # Debe tener el patrón completo
        if len(parts) >= 5 and parts[0] in ['FCT', 'DIM', 'AGG', 'TBL']:
            results['reglas_cumplidas'].append('RULE_6')
            results['puntaje_gobierno'] += 1
        else:
            results['reglas_violadas'].append('RULE_6')
            results['recomendaciones'].append('TRANSVERSAL debe seguir patrón {FUENTE}_Prefijo_DOMINIO_FUENTE_NOMBRE')
    else:
        # No es TRANSVERSAL, regla no aplica
        results['reglas_cumplidas'].append('RULE_6')
        results['puntaje_gobierno'] += 1
    
    # Calcular porcentaje de cumplimiento
    results['porcentaje_cumplimiento'] = (results['puntaje_gobierno'] / total_rules) * 100
    
    return results

def validate_naming_governance(df):
    """
    Valida el gobierno de nombramiento para todas las tablas
    """
    validation_results = []
    
    for table_name in df['Tabla'].unique():
        result = check_naming_rules(table_name)
        validation_results.append(result)
    
    return pd.DataFrame(validation_results)

def get_governance_stats(df_validation):
    """
    Calcula estadísticas de gobierno de datos
    """
    if df_validation.empty:
        return pd.DataFrame()
    
    stats = {
        'total_tablas': len(df_validation),
        'tablas_cumplen': len(df_validation[df_validation['porcentaje_cumplimiento'] == 100]),
        'tablas_parciales': len(df_validation[(df_validation['porcentaje_cumplimiento'] > 0) & (df_validation['porcentaje_cumplimiento'] < 100)]),
        'tablas_no_cumplen': len(df_validation[df_validation['porcentaje_cumplimiento'] == 0]),
        'puntaje_promedio': df_validation['puntaje_gobierno'].mean(),
        'cumplimiento_promedio': df_validation['porcentaje_cumplimiento'].mean()
    }
    
    # Estadísticas por regla
    rule_stats = {}
    for rule_code in NAMING_RULES.keys():
        cumplen = sum(df_validation['reglas_cumplidas'].apply(lambda x: rule_code in x))
        violan = sum(df_validation['reglas_violadas'].apply(lambda x: rule_code in x))
        
        rule_stats[rule_code] = {
            'nombre': NAMING_RULES[rule_code]['nombre'],
            'cumplen': cumplen,
            'violan': violan,
            'porcentaje_cumplimiento': (cumplen / len(df_validation)) * 100 if len(df_validation) > 0 else 0
        }
    
    return stats, rule_stats

def check_layer_naming_pattern(table_name, layer, object_type):
    """
    Verifica si un nombre de tabla cumple con los patrones de nomenclatura de su capa
    """
    results = {
        'tabla': table_name,
        'capa': layer,
        'tipo_objeto': object_type,
        'patron_cumplido': None,
        'patrones_aplicables': [],
        'patrones_violados': [],
        'recomendaciones_patron': [],
        'cumple_patron': False
    }
    
    # Obtener patrones para la capa
    if layer not in LAYER_NAMING_PATTERNS:
        results['recomendaciones_patron'].append(f'Capa "{layer}" no tiene patrones definidos')
        return results
    
    layer_patterns = LAYER_NAMING_PATTERNS[layer]
    
    # Obtener prefijo del nombre
    prefix = table_name.split('_')[0] if '_' in table_name else table_name
    
    # Obtener patrones aplicables para este prefijo
    applicable_patterns = PREFIX_PATTERN_MAPPING.get(prefix, [])
    
    # Filtrar patrones que existen en la capa
    valid_patterns = []
    for pattern_name in applicable_patterns:
        if pattern_name in layer_patterns:
            valid_patterns.append(pattern_name)
    
    results['patrones_aplicables'] = valid_patterns
    
    # Verificar cada patrón aplicable
    for pattern_name in valid_patterns:
        pattern_info = layer_patterns[pattern_name]
        pattern_regex = pattern_info['patron']
        
        if re.match(pattern_regex, table_name):
            results['patron_cumplido'] = pattern_name
            results['cumple_patron'] = True
            break
    
    # Si no cumple ningún patrón, generar recomendaciones
    if not results['cumple_patron'] and valid_patterns:
        results['patrones_violados'] = valid_patterns
        
        for pattern_name in valid_patterns:
            pattern_info = layer_patterns[pattern_name]
            results['recomendaciones_patron'].append(
                f"Debe seguir patrón: {pattern_name}. "
                f"Ejemplo: {pattern_info['ejemplos'][0] if pattern_info['ejemplos'] else 'N/A'}"
            )
    
    return results

def validate_layer_patterns(df):
    """
    Valida los patrones de nomenclatura por capa para todas las tablas
    """
    validation_results = []
    
    for _, row in df.iterrows():
        table_name = row['Tabla']
        layer = row['Esquema']
        object_type = row.get('Tipo_Objeto', 'TBL')
        
        result = check_layer_naming_pattern(table_name, layer, object_type)
        validation_results.append(result)
    
    return pd.DataFrame(validation_results)

def get_layer_pattern_stats(df_patterns):
    """
    Calcula estadísticas de patrones de nomenclatura por capa
    """
    if df_patterns.empty:
        return {}, {}
    
    # Estadísticas generales
    general_stats = {
        'total_objetos': len(df_patterns),
        'cumplen_patron': len(df_patterns[df_patterns['cumple_patron'] == True]),
        'no_cumplen_patron': len(df_patterns[df_patterns['cumple_patron'] == False]),
        'porcentaje_cumplimiento': (len(df_patterns[df_patterns['cumple_patron'] == True]) / len(df_patterns)) * 100
    }
    
    # Estadísticas por capa
    layer_stats = {}
    for layer in df_patterns['capa'].unique():
        layer_data = df_patterns[df_patterns['capa'] == layer]
        
        layer_stats[layer] = {
            'total_objetos': len(layer_data),
            'cumplen_patron': len(layer_data[layer_data['cumple_patron'] == True]),
            'no_cumplen_patron': len(layer_data[layer_data['cumple_patron'] == False]),
            'porcentaje_cumplimiento': (len(layer_data[layer_data['cumple_patron'] == True]) / len(layer_data)) * 100,
            'patrones_mas_usados': layer_data['patron_cumplido'].value_counts().to_dict() if not layer_data['patron_cumplido'].isna().all() else {}
        }
    
    # Estadísticas por tipo de objeto
    object_stats = {}
    for obj_type in df_patterns['tipo_objeto'].unique():
        obj_data = df_patterns[df_patterns['tipo_objeto'] == obj_type]
        
        object_stats[obj_type] = {
            'total_objetos': len(obj_data),
            'cumplen_patron': len(obj_data[obj_data['cumple_patron'] == True]),
            'no_cumplen_patron': len(obj_data[obj_data['cumple_patron'] == False]),
            'porcentaje_cumplimiento': (len(obj_data[obj_data['cumple_patron'] == True]) / len(obj_data)) * 100
        }
    
    return general_stats, layer_stats, object_stats

def identify_field_type(field_name):
    """
    Identifica el tipo de campo basado en su prefijo de nomenclatura
    """
    for prefix, field_info in FIELD_NOMENCLATURE.items():
        if field_name.upper().startswith(prefix + "_"):
            return prefix, field_info
    
    # Si no coincide con ningún prefijo conocido
    return "UNKNOWN", {
        "descripcion": "Campo sin clasificación estándar",
        "tipo_dato": "VARCHAR2",
        "patron": "SIN_PATRON",
        "ejemplo": field_name,
        "notas": "Campo sin nomenclatura definida",
        "longitud_recomendada": 100,
        "oracle_type": "VARCHAR2(100)"
    }

def validate_field_nomenclature(field_name, field_type):
    """
    Valida si un campo cumple con la nomenclatura y tipificación definida
    """
    results = {
        'campo': field_name,
        'tipo_actual': field_type,
        'tipo_campo': None,
        'cumple_nomenclatura': False,
        'cumple_tipificacion': False,
        'tipo_recomendado': None,
        'recomendaciones': []
    }
    
    # Identificar tipo de campo por nomenclatura
    field_prefix, field_info = identify_field_type(field_name, field_type)
    results['tipo_campo'] = field_prefix
    results['tipo_recomendado'] = field_info['tipo_dato']
    
    # Verificar si cumple nomenclatura
    if field_prefix in FIELD_NOMENCLATURE:
        results['cumple_nomenclatura'] = True
    else:
        results['recomendaciones'].append('Usar prefijo estándar: ID_, CD_, NM_, DS_, FH_, VL_, TP_, FL_')
    
    # Verificar si cumple tipificación
    if field_type.upper() == field_info['tipo_dato'].upper():
        results['cumple_tipificacion'] = True
    else:
        results['recomendaciones'].append(
            f"Tipo recomendado: {field_info['oracle_type']} (actual: {field_type})"
        )
    
    # Validaciones adicionales
    if field_prefix == "ID" and "PRIMARY" not in field_type.upper():
        results['recomendaciones'].append('Los campos ID deberían ser PRIMARY KEY')
    
    if field_prefix in ["TS_CARGA", "TS_ACT"] and "TIMESTAMP" not in field_type.upper():
        results['recomendaciones'].append('Los campos de timestamp deben ser TIMESTAMP')
    
    if field_prefix == "FL" and field_type.upper() not in ["CHAR", "VARCHAR2"]:
        results['recomendaciones'].append('Los campos de bandera deben ser CHAR(1) o VARCHAR2(1)')
    
    return results

def validate_all_fields(df):
    """
    Valida la nomenclatura y tipificación de todos los campos
    """
    validation_results = []
    
    for _, row in df.iterrows():
        field_name = row['Campo']
        field_type = row['Tipo de Dato']
        
        result = validate_field_nomenclature(field_name, field_type)
        validation_results.append(result)
    
    return pd.DataFrame(validation_results)

def get_field_validation_stats(df_fields):
    """
    Calcula estadísticas de validación de campos
    """
    if df_fields.empty:
        return {}, {}
    
    # Estadísticas generales
    general_stats = {
        'total_campos': len(df_fields),
        'cumplen_nomenclatura': len(df_fields[df_fields['cumple_nomenclatura'] == True]),
        'cumplen_tipificacion': len(df_fields[df_fields['cumple_tipificacion'] == True]),
        'campos_sin_clasificar': len(df_fields[df_fields['tipo_campo'] == 'UNKNOWN'])
    }
    
    # Estadísticas por tipo de campo
    type_stats = {}
    for field_type in df_fields['tipo_campo'].unique():
        if field_type == 'UNKNOWN':
            continue
            
        type_data = df_fields[df_fields['tipo_campo'] == field_type]
        field_info = FIELD_NOMENCLATURE.get(field_type, {})
        
        type_stats[field_type] = {
            'descripcion': field_info.get('descripcion', 'Sin descripción'),
            'total_campos': len(type_data),
            'cumplen_nomenclatura': len(type_data[type_data['cumple_nomenclatura'] == True]),
            'cumplen_tipificacion': len(type_data[type_data['cumple_tipificacion'] == True]),
            'tipo_recomendado': field_info.get('oracle_type', 'VARCHAR2'),
            'ejemplo': field_info.get('ejemplo', 'N/A')
        }
    
    # Estadísticas de problemas comunes
    issue_stats = {
        'campos_sin_prefijo': len(df_fields[df_fields['tipo_campo'] == 'UNKNOWN']),
        'tipificacion_incorrecta': len(df_fields[df_fields['cumple_tipificacion'] == False]),
        'problemas_criticos': len(df_fields[
            (df_fields['cumple_nomenclatura'] == False) | (df_fields['cumple_tipificacion'] == False)
        ])
    }
    
    return general_stats, type_stats, issue_stats

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
        st.success("Datos cargados automáticamente desde GitHub.")
    else:
        st.warning("No se pudo cargar automáticamente desde GitHub.")
        
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
    
    # Clasificación organizacional
    df = classify_by_organizational_domain(df)
    
    # Clasificación por tipo de objeto
    df = classify_by_object_type(df)
    
    # Calcular estadísticas
    df_stats = calculate_dataset_statistics(df)
    
    # Calcular estadísticas organizacionales
    df_org_stats = get_organizational_stats(df)
    
    # Calcular estadísticas por tipo de objeto
    df_obj_stats = get_object_type_stats(df)
    
    # Validar gobierno de nombramiento
    df_governance = validate_naming_governance(df)
    governance_stats, rule_stats = get_governance_stats(df_governance)
    
    # Validar patrones de nomenclatura por capa
    df_patterns = validate_layer_patterns(df)
    pattern_general_stats, pattern_layer_stats, pattern_object_stats = get_layer_pattern_stats(df_patterns)
    
    # Validar nomenclatura y tipificación de campos
    df_fields = validate_all_fields(df)
    field_general_stats, field_type_stats, field_issue_stats = get_field_validation_stats(df_fields)
    
    if not df.empty:
        # Crear pestañas para organizar la aplicación
        tab_catalogo, tab_busqueda, tab_perfiles, tab_productos, tab_objetos, tab_campos, tab_gobierno, tab_dominios, tab_glosario, tab_lineage, tab_schema = st.tabs([
            "Catalogo Central", "Busqueda Avanzada", "Perfiles de Datasets", 
            "Catalogo de Productos", "Tipos de Objetos", "Validacion de Campos", "Gobierno de Datos", "Dominios Org.", "Glosario de Negocios", "Linaje de Datos", "Modelo Dimensional"
        ])

        with tab_catalogo:
            st.subheader("Catalogo de Datos Centralizado")
            st.markdown("""
            **Bienvenido al Catálogo de Datos** - Descubra, explore y entienda sus activos de datos.
            *Navegue por las pestañas para acceder a diferentes funcionalidades del catálogo.*
            """)
            
            # Métricas generales
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Total Tablas", df["Tabla"].nunique())
            col2.metric("Total Campos", len(df))
            col3.metric("Dominios", df["Dominio"].nunique())
            col4.metric("Dueños", len(df_stats['Esquema'].unique()))
            
            # Vista previa de datasets por calidad
            st.subheader("Calidad de Datasets por Esquema")
            calidad_esquema = df_stats.groupby('Esquema')['Calidad_General'].mean().reset_index()
            st.bar_chart(calidad_esquema.set_index('Esquema'))
            
            # Tabla resumen con clasificaciones
            st.subheader("Clasificacion Automatica de Datasets")
            display_df = df[['Tabla', 'Esquema', 'Tipo', 'Dominio', 'Criticidad', 'Confidencialidad']].drop_duplicates('Tabla')
            st.dataframe(display_df, use_container_width=True)

        with tab_busqueda:
            st.subheader("Busqueda Avanzada de Datos")
            
            # Barra de búsqueda
            col1, col2 = st.columns([3, 1])
            with col1:
                search_query = st.text_input("Buscar tablas, campos o descripciones...", placeholder="Ej: cliente, fecha, sentencia...")
            with col2:
                st.write("")
                search_button = st.button("Buscar", type="primary")
            
            # Filtros avanzados
            with st.expander("Filtros Avanzados"):
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    dominios_sel = st.multiselect("Dominio", options=DATA_TAXONOMY["Dominio"], default=DATA_TAXONOMY["Dominio"])
                    criticidad_sel = st.multiselect("Criticidad", options=DATA_TAXONOMY["Criticidad"], default=DATA_TAXONOMY["Criticidad"])
                
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
                    st.success(f"Se encontraron {len(results)} resultados")
                    
                    # Mostrar resultados con scores
                    if 'search_score' in results.columns:
                        display_cols = ['Tabla', 'Campo', 'Descripción funcional', 'Dominio', 'search_score']
                        display_results = results[display_cols].rename(columns={'search_score': 'Score'})
                        st.dataframe(display_results, use_container_width=True)
                    else:
                        st.dataframe(results, use_container_width=True)
                else:
                    st.warning("No se encontraron resultados para su búsqueda")
            else:
                st.info("Ingrese un término de búsqueda o use los filtros para explorar los datos")

        with tab_perfiles:
            st.subheader("Perfiles Detallados de Datasets")
            
            # Selector de dataset
            tabla_sel = st.selectbox("Seleccione un dataset para ver su perfil:", options=sorted(df["Tabla"].unique()))
            
            if tabla_sel:
                tabla_data = df[df["Tabla"] == tabla_sel]
                tabla_stat = df_stats[df_stats["Tabla"] == tabla_sel].iloc[0]
                
                # Información general
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Campos", tabla_stat['Total_Campos'])
                with col2:
                    st.metric("Claves Primarias", tabla_stat['Campos_PK'])
                with col3:
                    st.metric("Calidad General", f"{tabla_stat['Calidad_General']}/100")
                
                # Metadatos del dataset
                st.subheader("Metadatos del Dataset")
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
                st.subheader("Detalle de Campos")
                campos_display = tabla_data[['Campo', 'Tipo de Dato', 'Clave Primaria', 'Descripción funcional', 'Sensibilidad del Dato', 'Para qué sirve el campo']]
                st.dataframe(campos_display, use_container_width=True)
                
                # Productos de datos potenciales
                st.subheader("Productos de Datos Potenciales")
                
                # Verificar si la columna existe antes de usarla
                if 'Productos_Potenciales' in tabla_data.columns:
                    productos_potenciales = tabla_data['Productos_Potenciales'].iloc[0]
                    productos_lista = productos_potenciales.split(", ")
                else:
                    # Si no existe la columna, asignar productos automáticamente
                    productos_potenciales = assign_data_products(pd.DataFrame({'Tabla': [tabla_sel]}))['Productos_Potenciales'].iloc[0]
                    productos_lista = productos_potenciales.split(", ")
                
                col1, col2 = st.columns(2)
                for i, producto in enumerate(productos_lista):
                    with col1 if i % 2 == 0 else col2:
                        producto_info = get_product_details(producto.strip())
                        with st.expander(f"{producto.strip()} - {producto_info['nombre']}"):
                            st.write(f"**Descripcion:** {producto_info['descripcion']}")
                            st.write(f"**Frecuencia:** {producto_info['frecuencia']}")
                            st.write(f"**Tecnologia:** {producto_info['tecnologia']}")
                
                # Estadísticas de calidad
                st.subheader("Metricas de Calidad")
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    pk_ratio = (tabla_stat['Campos_PK'] / tabla_stat['Total_Campos']) * 100
                    st.metric("% con PK", f"{pk_ratio:.1f}%")
                with col2:
                    doc_ratio = (tabla_data['Descripción funcional'].notna().sum() / len(tabla_data)) * 100
                    st.metric("% Documentado", f"{doc_ratio:.1f}%")
                with col3:
                    sens_types = tabla_data['Sensibilidad del Dato'].nunique()
                    st.metric("Tipos de Sensibilidad", sens_types)
                with col4:
                    data_types = tabla_stat['Tipos_Datos']
                    st.metric("Tipos de Datos", data_types)

        with tab_productos:
            st.subheader("Catalogo de Productos de Datos")
            st.markdown("""
            **Productos de Datos** - Transformación de datos brutos en productos de valor para el negocio.
            *Explore los diferentes tipos de productos que se pueden generar a partir de sus datasets.*
            """)
            
            # Asignar productos a las tablas
            df_with_products = assign_data_products(df)
            
            # Métricas generales de productos
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Total Productos", len(DATA_PRODUCTS))
            col2.metric("Tablas con Productos", df_with_products['Tabla'].nunique())
            col3.metric("Productos por Tabla", f"{len(DATA_PRODUCTS) / max(df_with_products['Tabla'].nunique(), 1):.1f}")
            col4.metric("Tipos de Producto", len(set(p['tipo'] for p in DATA_PRODUCTS.values())))
            
            # Catálogo de productos
            st.subheader("Catalogo Completo de Productos")
            
            for product_code, product_info in DATA_PRODUCTS.items():
                with st.expander(f"{product_code} - {product_info['nombre']}"):
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.write(f"**Descripcion:** {product_info['descripcion']}")
                        st.write(f"**Tipo:** {product_info['tipo']}")
                        st.write(f"**Frecuencia:** {product_info['frecuencia']}")
                    
                    with col2:
                        st.write(f"**Formato:** {product_info['formato']}")
                        st.write(f"**Tecnologia:** {product_info['tecnologia']}")
                        
                        # Encontrar tablas que pueden generar este producto
                        related_tables = []
                        for prefix, products in TABLE_PRODUCT_MAPPING.items():
                            if product_code in products:
                                tables_with_prefix = [t for t in df['Tabla'].unique() if t.upper().startswith(prefix)]
                                related_tables.extend(tables_with_prefix[:3])  # Limitar a 3 ejemplos
                        
                        if related_tables:
                            st.write("**Tablas relacionadas:**")
                            for table in related_tables:
                                st.write(f"• {table}")
            
            # Tabla de asignación de productos
            st.subheader("Asignacion de Productos por Tabla")
            product_assignment = df_with_products[['Tabla', 'Esquema', 'Tipo', 'Productos_Potenciales']].drop_duplicates('Tabla')
            st.dataframe(product_assignment, use_container_width=True)

        with tab_objetos:
            st.subheader("Catalogo de Tipos de Objetos")
            st.markdown("""
            **Tipos de Objetos de BD** - Clasificación técnica según estructura y función.
            *Explore los diferentes tipos de objetos y su distribución en la arquitectura.*
            """)
            
            # Métricas de objetos
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Total Tipos", len(OBJECT_TYPES))
            col2.metric("Objetos Clasificados", len(df[df['Tipo_Objeto'] != 'SIN_TIPO']))
            col3.metric("Tipos con Datos", df_obj_stats['Tipo_Objeto'].nunique() if not df_obj_stats.empty else 0)
            col4.metric("Cobertura Tecnica", f"{len(df[df['Tipo_Objeto'] != 'SIN_TIPO']) / max(len(df), 1) * 100:.1f}%")
            
            # Estadísticas por tipo de objeto
            if not df_obj_stats.empty:
                st.subheader("Estadisticas por Tipo de Objeto")
                
                # Tabla de estadísticas
                display_cols = ['Tipo_Objeto', 'Nombre', 'Estructura', 'Total_Tablas', 'Total_Campos']
                st.dataframe(df_obj_stats[display_cols], use_container_width=True)
                
                # Gráficos de distribución
                col1, col2 = st.columns(2)
                
                with col1:
                    st.subheader("Tablas por Estructura")
                    estructura_data = df_obj_stats.groupby('Estructura')['Total_Tablas'].sum()
                    st.bar_chart(estructura_data)
                
                with col2:
                    st.subheader("Tablas por Tipo")
                    tipo_data = df_obj_stats.set_index('Nombre')['Total_Tablas']
                    st.bar_chart(tipo_data)
            
            # Catálogo completo de tipos de objetos
            st.subheader("Catalogo Completo de Tipos de Objetos")
            
            # Filtros por estructura
            estructura_sel = st.selectbox(
                "Filtrar por tipo de estructura:",
                options=["Todos"] + list(set(obj['estructura'] for obj in OBJECT_TYPES.values())),
                index=0
            )
            
            # Mostrar objetos filtrados
            objetos_filtrados = {}
            for code, info in OBJECT_TYPES.items():
                if estructura_sel == "Todos" or info['estructura'] == estructura_sel:
                    objetos_filtrados[code] = info
            
            # Organizar en columnas
            cols = st.columns(3)
            for i, (code, info) in enumerate(objetos_filtrados.items()):
                with cols[i % 3]:
                    with st.expander(f"{code} - {info['nombre']}"):
                        col1, col2 = st.columns(2)
                        with col1:
                            st.write(f"**Descripcion:** {info['descripcion']}")
                            st.write(f"**Estructura:** {info['estructura']}")
                        with col2:
                            # Buscar objetos asociados
                            tablas_asociadas = df[df['Tipo_Objeto'] == code]['Tabla'].nunique()
                            campos_asociados = len(df[df['Tipo_Objeto'] == code])
                            st.write(f"**Tablas:** {tablas_asociadas}")
                            st.write(f"**Campos:** {campos_asociados}")
                        
                        st.write(f"**Capas Aplicables:** {', '.join(info['capas'])}")
                        st.write(f"**Ejemplo:** `{info['ejemplo']}`")
                        st.write(f"**Observaciones:** {info['observaciones']}")
            
            # Análisis por capas
            st.subheader("Distribucion por Capas Arquitectonicas")
            
            # Contar objetos por capa
            capa_counts = {'Bronce': 0, 'Plata': 0, 'Oro': 0}
            for obj_code, obj_info in OBJECT_TYPES.items():
                for capa in obj_info['capas']:
                    capa_counts[capa] += 1
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Objetos en Bronce", capa_counts['Bronce'])
            with col2:
                st.metric("Objetos en Plata", capa_counts['Plata'])
            with col3:
                st.metric("Objetos en Oro", capa_counts['Oro'])
            
            # Matriz de tipos vs capas
            st.subheader("Matriz de Tipos por Capa")
            
            matriz_data = []
            for obj_code, obj_info in OBJECT_TYPES.items():
                row = {'Tipo_Objeto': obj_code, 'Nombre': obj_info['nombre']}
                for capa in ['Bronce', 'Plata', 'Oro']:
                    row[capa] = 'SI' if capa in obj_info['capas'] else 'NO'
                matriz_data.append(row)
            
            matriz_df = pd.DataFrame(matriz_data)
            st.dataframe(matriz_df, use_container_width=True)
            
            # Objetos sin clasificar
            sin_clasificar_obj = df[df['Tipo_Objeto'] == 'SIN_TIPO'] if 'SIN_TIPO' in df['Tipo_Objeto'].values else pd.DataFrame()
            if not sin_clasificar_obj.empty:
                st.warning(f"**{len(sin_clasificar_obj)} objetos sin clasificacion tecnica**")
                with st.expander("Ver objetos sin tipo asignado"):
                    tablas_sin_tipo = sin_clasificar_obj['Tabla'].unique()
                    for tabla in tablas_sin_tipo[:10]:
                        st.write(f"• {tabla}")
                    if len(tablas_sin_tipo) > 10:
                        st.write(f"... y {len(tablas_sin_tipo) - 10} más")

        with tab_campos:
            st.subheader("Validacion de Nomenclatura y Tipificacion de Campos")
            st.markdown("""
            **Control de Calidad de Campos** - Validación de nomenclatura y tipos de datos.
            *Asegure que cada campo sigue los estándares definidos de nomenclatura y tipificación.*
            """)
            
            # Métricas generales de campos
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Total Campos", field_general_stats.get('total_campos', 0))
            col2.metric("Cumplen Nomenclatura", field_general_stats.get('cumplen_nomenclatura', 0))
            col3.metric("Cumplen Tipificacion", field_general_stats.get('cumplen_tipificacion', 0))
            col4.metric("Sin Clasificar", field_general_stats.get('campos_sin_clasificar', 0))
            
            # Análisis por tipo de campo
            st.subheader("Analisis por Tipo de Campo")
            
            if field_type_stats:
                type_data = []
                for field_type, stats in field_type_stats.items():
                    type_data.append({
                        'Tipo Campo': field_type,
                        'Descripción': stats['descripcion'][:50] + '...' if len(stats['descripcion']) > 50 else stats['descripcion'],
                        'Total': stats['total_campos'],
                        'Cumplen Nomenclatura': stats['cumplen_nomenclatura'],
                        'Cumplen Tipificación': stats['cumplen_tipificacion'],
                        'Tipo Recomendado': stats['tipo_recomendado'],
                        'Ejemplo': stats['ejemplo']
                    })
                
                type_df = pd.DataFrame(type_data)
                st.dataframe(type_df, use_container_width=True)
            
            # Problemas comunes
            st.subheader("Problemas Comunes Identificados")
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Campos sin Prefijo", field_issue_stats.get('campos_sin_prefijo', 0))
            with col2:
                st.metric("Tipificacion Incorrecta", field_issue_stats.get('tipificacion_incorrecta', 0))
            with col3:
                st.metric("Problemas Criticos", field_issue_stats.get('problemas_criticos', 0))
            
            # Validación detallada por campo
            st.subheader("Analisis Detallado por Campo")
            
            # Filtros
            col1, col2 = st.columns(2)
            with col1:
                filtro_nomenclatura = st.selectbox(
                    "Filtrar por nomenclatura:",
                    options=["Todos", "Cumplen Nomenclatura", "No Cumplen Nomenclatura"],
                    index=0
                )
            
            with col2:
                filtro_tipificacion = st.selectbox(
                    "Filtrar por tipificación:",
                    options=["Todos", "Cumplen Tipificación", "No Cumplen Tipificación"],
                    index=0
                )
            
            # Aplicar filtros
            df_campos_filtrado = df_fields.copy()
            
            if filtro_nomenclatura == "Cumplen Nomenclatura":
                df_campos_filtrado = df_campos_filtrado[df_campos_filtrado['cumple_nomenclatura'] == True]
            elif filtro_nomenclatura == "No Cumplen Nomenclatura":
                df_campos_filtrado = df_campos_filtrado[df_campos_filtrado['cumple_nomenclatura'] == False]
            
            if filtro_tipificacion == "Cumplen Tipificación":
                df_campos_filtrado = df_campos_filtrado[df_campos_filtrado['cumple_tipificacion'] == True]
            elif filtro_tipificacion == "No Cumplen Tipificación":
                df_campos_filtrado = df_campos_filtrado[df_campos_filtrado['cumple_tipificacion'] == False]
            
            # Mostrar resultados
            if not df_campos_filtrado.empty:
                for _, row in df_campos_filtrado.iterrows():
                    with st.expander(f"{row['campo']} - {'SI' if row['cumple_nomenclatura'] and row['cumple_tipificacion'] else 'NO'}"):
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.write(f"**Campo:** {row['campo']}")
                            st.write(f"**Tipo Actual:** {row['tipo_actual']}")
                            st.write(f"**Tipo Campo:** {row['tipo_campo']}")
                        
                        with col2:
                            st.write(f"**Nomenclatura:** {'SI' if row['cumple_nomenclatura'] else 'NO'}")
                            st.write(f"**Tipificacion:** {'SI' if row['cumple_tipificacion'] else 'NO'}")
                            st.write(f"**Tipo Recomendado:** {row['tipo_recomendado']}")
                        
                        # Recomendaciones
                        if row['recomendaciones']:
                            st.write("**Recomendaciones:**")
                            for rec in row['recomendaciones']:
                                st.write(f"• {rec}")
            else:
                st.info("No hay campos que coincidan con los filtros seleccionados")
            
            # Catálogo de tipos de campos
            st.subheader("Catalogo de Tipos de Campos Gobernados")
            
            for field_type, field_info in FIELD_NOMENCLATURE.items():
                with st.expander(f"{field_type} - {field_info['descripcion']}"):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(f"**📝 Patrón:** {field_info['patron']}")
                        st.write(f"**🔤 Tipo Dato:** {field_info['tipo_dato']}")
                        st.write(f"**📏 Longitud:** {field_info['longitud_recomendada']}")
                    with col2:
                        st.write(f"**📋 Ejemplo:** `{field_info['ejemplo']}`")
                        st.write(f"**💾 Oracle Type:** `{field_info['oracle_type']}`")
                        st.write(f"**📝 Notas:** {field_info['notas']}")
                    
                    # Estadísticas de uso
                    campos_tipo = df_fields[df_fields['tipo_campo'] == field_type]
                    st.write(f"**Uso Actual:** {len(campos_tipo)} campos")

        with tab_gobierno:
            st.subheader("Gobierno de Datos - Validacion de Nombramiento")
            st.markdown("""
            **Control de Calidad de Nomenclatura** - Verificación del cumplimiento de reglas de gobierno.
            *Asegure consistencia y estándares en el nombramiento de objetos de datos.*
            """)
            
            # Métricas generales de gobierno
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Total Tablas", governance_stats.get('total_tablas', 0))
            col2.metric("Cumplen 100%", governance_stats.get('tablas_cumplen', 0))
            col3.metric("Cumplen Parcial", governance_stats.get('tablas_parciales', 0))
            col4.metric("No Cumplen", governance_stats.get('tablas_no_cumplen', 0))
            
            # Puntaje general de gobierno
            st.subheader("Indice de Madurez de Gobierno")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                puntaje_promedio = governance_stats.get('puntaje_promedio', 0)
                st.metric("Puntaje Promedio", f"{puntaje_promedio:.1f}/6.0")
            
            with col2:
                cumplimiento_promedio = governance_stats.get('cumplimiento_promedio', 0)
                estado_texto = "Alto" if cumplimiento_promedio >= 80 else "Medio" if cumplimiento_promedio >= 60 else "Bajo"
                st.metric(f"Cumplimiento Promedio ({estado_texto})", f"{cumplimiento_promedio:.1f}%")
            
            with col3:
                calidad_general = "Excelente" if cumplimiento_promedio >= 90 else "Bueno" if cumplimiento_promedio >= 70 else "Regular" if cumplimiento_promedio >= 50 else "Requiere Mejora"
                st.metric("Calidad General", calidad_general)
            
            # Análisis por regla
            st.subheader("Cumplimiento por Regla de Nombramiento")
            
            if rule_stats:
                # Crear tabla de reglas
                rule_data = []
                for rule_code, stats in rule_stats.items():
                    rule_info = NAMING_RULES[rule_code]
                    rule_data.append({
                        'Regla': f"{rule_code}: {rule_info['nombre']}",
                        'Descripción': rule_info['descripcion'],
                        'Cumplen': stats['cumplen'],
                        'Violan': stats['violan'],
                        '% Cumplimiento': f"{stats['porcentaje_cumplimiento']:.1f}%",
                        'Estado': 'CUMPLE' if stats['porcentaje_cumplimiento'] >= 90 else 'PARCIAL' if stats['porcentaje_cumplimiento'] >= 70 else 'NO CUMPLE'
                    })
                
                rule_df = pd.DataFrame(rule_data)
                st.dataframe(rule_df, use_container_width=True)
                
                # Gráfico de cumplimiento por regla
                st.subheader("Visualizacion de Cumplimiento")
                rule_chart_data = {stats['nombre']: stats['porcentaje_cumplimiento'] for stats in rule_stats.values()}
                st.bar_chart(rule_chart_data)
            
            # Validación detallada por tabla
            st.subheader("Analisis Detallado por Tabla")
            
            # Filtros
            col1, col2 = st.columns(2)
            with col1:
                filtro_cumplimiento = st.selectbox(
                    "Filtrar por nivel de cumplimiento:",
                    options=["Todas", "Cumplen 100%", "Cumplen Parcialmente", "No Cumplen"],
                    index=0
                )
            
            with col2:
                ordenar_por = st.selectbox(
                    "Ordenar por:",
                    options=["Nombre de Tabla", "Puntaje de Gobierno", "% Cumplimiento"],
                    index=1
                )
            
            # Aplicar filtros
            df_filtrado = df_governance.copy()
            
            if filtro_cumplimiento == "Cumplen 100%":
                df_filtrado = df_filtrado[df_filtrado['porcentaje_cumplimiento'] == 100]
            elif filtro_cumplimiento == "Cumplen Parcialmente":
                df_filtrado = df_filtrado[(df_filtrado['porcentaje_cumplimiento'] > 0) & (df_filtrado['porcentaje_cumplimiento'] < 100)]
            elif filtro_cumplimiento == "No Cumplen":
                df_filtrado = df_filtrado[df_filtrado['porcentaje_cumplimiento'] == 0]
            
            # Ordenar
            if ordenar_por == "Nombre de Tabla":
                df_filtrado = df_filtrado.sort_values('tabla')
            elif ordenar_por == "Puntaje de Gobierno":
                df_filtrado = df_filtrado.sort_values('puntaje_gobierno', ascending=False)
            else:
                df_filtrado = df_filtrado.sort_values('porcentaje_cumplimiento', ascending=False)
            
            # Mostrar resultados
            if not df_filtrado.empty:
                for _, row in df_filtrado.iterrows():
                    with st.expander(f"{row['tabla']} - {row['porcentaje_cumplimiento']:.1f}%"):
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.write(f"**Puntaje:** {row['puntaje_gobierno']}/6")
                            st.write(f"**Reglas Cumplidas:** {len(row['reglas_cumplidas'])}")
                            st.write(f"**Reglas Violadas:** {len(row['reglas_violadas'])}")
                        
                        with col2:
                            # Estado visual
                            if row['porcentaje_cumplimiento'] == 100:
                                st.success("Cumple todas las reglas")
                            elif row['porcentaje_cumplimiento'] >= 70:
                                st.warning("Cumple parcialmente")
                            else:
                                st.error("Requiere correccion")
                        
                        # Detalles de reglas
                        if row['reglas_violadas']:
                            st.write("**Reglas Violadas:**")
                            for rule_code in row['reglas_violadas']:
                                rule_info = NAMING_RULES[rule_code]
                                st.write(f"• {rule_info['nombre']}: {rule_info['descripcion']}")
                        
                        if row['recomendaciones']:
                            st.write("**Recomendaciones:**")
                            for rec in row['recomendaciones']:
                                st.write(f"• {rec}")
            else:
                st.info("No hay tablas que coincidan con los filtros seleccionados")
            
            # Reglas de nombramiento
            st.subheader("Reglas de Nombramiento Definidas")
            
            for rule_code, rule_info in NAMING_RULES.items():
                with st.expander(f"{rule_code}: {rule_info['nombre']}"):
                    col1, col2 = st.columns(2)
                    with col1:
                        st.write(f"**📝 Descripción:** {rule_info['descripcion']}")
                        st.write(f"**Ejemplo Correcto:** `{rule_info['ejemplo_correcto']}`")
                    with col2:
                        st.write(f"**Ejemplo Incorrecto:** `{rule_info['ejemplo_incorrecto']}`")
                        
                        # Estadísticas de esta regla
                        if rule_code in rule_stats:
                            stats = rule_stats[rule_code]
                            st.write(f"**Estadisticas:**")
                            st.write(f"• Cumplen: {stats['cumplen']}")
                            st.write(f"• Violan: {stats['violan']}")
                            st.write(f"• % Cumplimiento: {stats['porcentaje_cumplimiento']:.1f}%")
            
            # Validación de Patrones de Nomenclatura por Capa
            st.subheader("Patrones de Nomenclatura por Capa")
            st.markdown("""
            **Validación de Patrones Arquitectónicos** - Verificación de cumplimiento de patrones por capa.
            *Asegure que cada objeto sigue la estructura definida para su capa arquitectónica.*
            """)
            
            # Métricas generales de patrones
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Total Objetos", pattern_general_stats.get('total_objetos', 0))
            col2.metric("Cumplen Patron", pattern_general_stats.get('cumplen_patron', 0))
            col3.metric("No Cumplen", pattern_general_stats.get('no_cumplen_patron', 0))
            col4.metric("% Cumplimiento", f"{pattern_general_stats.get('porcentaje_cumplimiento', 0):.1f}%")
            
            # Análisis por capa
            st.subheader("Cumplimiento por Capa Arquitectonica")
            
            if pattern_layer_stats:
                layer_data = []
                for layer, stats in pattern_layer_stats.items():
                    layer_data.append({
                        'Capa': layer,
                        'Total Objetos': stats['total_objetos'],
                        'Cumplen Patrón': stats['cumplen_patron'],
                        'No Cumplen': stats['no_cumplen_patron'],
                        '% Cumplimiento': f"{stats['porcentaje_cumplimiento']:.1f}%",
                        'Estado': 'CUMPLE' if stats['porcentaje_cumplimiento'] >= 80 else 'PARCIAL' if stats['porcentaje_cumplimiento'] >= 60 else 'NO CUMPLE'
                    })
                
                layer_df = pd.DataFrame(layer_data)
                st.dataframe(layer_df, use_container_width=True)
                
                # Gráfico de cumplimiento por capa
                st.subheader("Visualizacion por Capa")
                layer_chart_data = {layer: stats['porcentaje_cumplimiento'] for layer, stats in pattern_layer_stats.items()}
                st.bar_chart(layer_chart_data)
            
            # Análisis por tipo de objeto
            st.subheader("Cumplimiento por Tipo de Objeto")
            
            if pattern_object_stats:
                object_data = []
                for obj_type, stats in pattern_object_stats.items():
                    object_data.append({
                        'Tipo Objeto': obj_type,
                        'Total': stats['total_objetos'],
                        'Cumplen': stats['cumplen_patron'],
                        'No Cumplen': stats['no_cumplen_patron'],
                        '% Cumplimiento': f"{stats['porcentaje_cumplimiento']:.1f}%"
                    })
                
                object_df = pd.DataFrame(object_data)
                st.dataframe(object_df, use_container_width=True)
            
            # Validación detallada por objeto
            st.subheader("Analisis Detallado de Patrones")
            
            # Filtros
            col1, col2 = st.columns(2)
            with col1:
                filtro_patron = st.selectbox(
                    "Filtrar por cumplimiento de patrón:",
                    options=["Todos", "Cumplen Patrón", "No Cumplen Patrón"],
                    index=0
                )
            
            with col2:
                filtro_capa = st.selectbox(
                    "Filtrar por capa:",
                    options=["Todas"] + list(df_patterns['capa'].unique()),
                    index=0
                )
            
            # Aplicar filtros
            df_pat_filtrado = df_patterns.copy()
            
            if filtro_patron == "Cumplen Patrón":
                df_pat_filtrado = df_pat_filtrado[df_pat_filtrado['cumple_patron'] == True]
            elif filtro_patron == "No Cumplen Patrón":
                df_pat_filtrado = df_pat_filtrado[df_pat_filtrado['cumple_patron'] == False]
            
            if filtro_capa != "Todas":
                df_pat_filtrado = df_pat_filtrado[df_pat_filtrado['capa'] == filtro_capa]
            
            # Mostrar resultados
            if not df_pat_filtrado.empty:
                for _, row in df_pat_filtrado.iterrows():
                    with st.expander(f"{row['tabla']} ({row['capa']}) - {'SI' if row['cumple_patron'] else 'NO'}"):
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.write(f"**Capa:** {row['capa']}")
                            st.write(f"**Tipo Objeto:** {row['tipo_objeto']}")
                            st.write(f"**Cumple Patron:** {'SI' if row['cumple_patron'] else 'NO'}")
                        
                        with col2:
                            if row['cumple_patron']:
                                st.success(f"Patron: {row['patron_cumplido']}")
                            else:
                                st.error("No cumple ningun patron aplicable")
                        
                        # Patrones aplicables
                        if row['patrones_aplicables']:
                            st.write("**Patrones Aplicables:**")
                            for pattern in row['patrones_aplicables']:
                                pattern_info = LAYER_NAMING_PATTERNS.get(row['capa'], {}).get(pattern, {})
                                st.write(f"• {pattern}: {pattern_info.get('descripcion', 'Sin descripción')}")
                        
                        # Recomendaciones
                        if row['recomendaciones_patron']:
                            st.write("**Recomendaciones:**")
                            for rec in row['recomendaciones_patron']:
                                st.write(f"• {rec}")
            else:
                st.info("No hay objetos que coincidan con los filtros seleccionados")
            
            # Catálogo de patrones por capa
            st.subheader("Catalogo de Patrones por Capa")
            
            for layer, patterns in LAYER_NAMING_PATTERNS.items():
                with st.expander(f"{layer} - {len(patterns)} patrones definidos"):
                    for pattern_name, pattern_info in patterns.items():
                        col1, col2 = st.columns(2)
                        with col1:
                            st.write(f"**📝 Patrón:** {pattern_name}")
                            st.write(f"**📋 Descripción:** {pattern_info['descripcion']}")
                            st.write(f"**🎯 Aplica Para:** {pattern_info['aplica_para']}")
                        with col2:
                            st.write(f"**🔤 Expresión:** `{pattern_info['patron']}`")
                            st.write(f"**Ejemplos:**")
                            for ejemplo in pattern_info['ejemplos']:
                                st.write(f"• `{ejemplo}`")
                        
                        # Estadísticas de este patrón
                        pattern_usage = sum(1 for _, row in df_patterns.iterrows() 
                                          if row['patron_cumplido'] == pattern_name)
                        st.write(f"**Uso Actual:** {pattern_usage} objetos")

        with tab_dominios:
            st.subheader("Dominios Organizacionales")
            st.markdown("""
            **Dominios de la Defensoría** - Clasificación de datos según estructura organizacional.
            *Explore cómo se distribuyen los datos por despachos, direcciones y defensorías.*
            """)
            
            # Métricas organizacionales
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Total Dominios", len(ORGANIZATIONAL_DOMAINS))
            col2.metric("Tablas Clasificadas", len(df[df['Dominio_Org'] != 'SIN_DOMINIO']))
            col3.metric("Dominios con Datos", df_org_stats['Dominio'].nunique() if not df_org_stats.empty else 0)
            col4.metric("Cobertura Org.", f"{len(df[df['Dominio_Org'] != 'SIN_DOMINIO']) / max(len(df), 1) * 100:.1f}%")
            
            # Estadísticas por dominio
            if not df_org_stats.empty:
                st.subheader("Estadisticas por Dominio Organizacional")
                
                # Tabla de estadísticas
                display_cols = ['Dominio', 'Nombre', 'Tipo', 'Nivel', 'Total_Tablas', 'Total_Campos']
                st.dataframe(df_org_stats[display_cols], use_container_width=True)
                
                # Gráficos de distribución
                col1, col2 = st.columns(2)
                
                with col1:
                    st.subheader("Tablas por Tipo de Org")
                    tipo_counts = df_org_stats['Tipo'].value_counts()
                    st.bar_chart(tipo_counts)
                
                with col2:
                    st.subheader("Tablas por Nivel")
                    nivel_counts = df_org_stats['Nivel'].value_counts()
                    st.bar_chart(nivel_counts)
            
            # Catálogo completo de dominios
            st.subheader("Catalogo Completo de Dominios")
            
            # Filtros por tipo de organización
            tipo_org_sel = st.selectbox(
                "Filtrar por tipo de organización:",
                options=["Todos"] + list(set(org['tipo'] for org in ORGANIZATIONAL_DOMAINS.values())),
                index=0
            )
            
            # Mostrar dominios filtrados
            dominios_filtrados = {}
            for code, info in ORGANIZATIONAL_DOMAINS.items():
                if tipo_org_sel == "Todos" or info['tipo'] == tipo_org_sel:
                    dominios_filtrados[code] = info
            
            # Organizar en columnas
            cols = st.columns(3)
            for i, (code, info) in enumerate(dominios_filtrados.items()):
                with cols[i % 3]:
                    with st.expander(f"{code} - {info['nombre']}"):
                        col1, col2 = st.columns(2)
                        with col1:
                            st.write(f"**Tipo:** {info['tipo']}")
                            st.write(f"**Nivel:** {info['nivel']}")
                        with col2:
                            # Buscar tablas asociadas
                            tablas_asociadas = df[df['Dominio_Org'] == code]['Tabla'].nunique()
                            campos_asociados = len(df[df['Dominio_Org'] == code])
                            st.write(f"**Tablas:** {tablas_asociadas}")
                            st.write(f"**Campos:** {campos_asociados}")
            
            # Análisis de cobertura
            st.subheader("Analisis de Cobertura Organizacional")
            
            # Tablas sin clasificar
            sin_clasificar = df[df['Dominio_Org'] == 'SIN_DOMINIO']
            if not sin_clasificar.empty:
                st.warning(f"**{len(sin_clasificar)} campos sin clasificacion organizacional**")
                with st.expander("Ver tablas sin dominio asignado"):
                    tablas_sin_dom = sin_clasificar['Tabla'].unique()
                    for tabla in tablas_sin_dom[:10]:  # Limitar a 10
                        st.write(f"• {tabla}")
                    if len(tablas_sin_dom) > 10:
                        st.write(f"... y {len(tablas_sin_dom) - 10} más")
            
            # Mapa de dominios por esquema
            st.subheader("Distribucion por Esquema y Dominio")
            if not df_org_stats.empty:
                # Crear matriz de dominios vs esquemas
                pivot_data = df[df['Dominio_Org'] != 'SIN_DOMINIO'].pivot_table(
                    index='Dominio_Org', 
                    columns='Esquema', 
                    values='Tabla', 
                    aggfunc='nunique', 
                    fill_value=0
                )
                st.dataframe(pivot_data, use_container_width=True)

        with tab_glosario:
            st.subheader("Glosario de Negocios")
            
            # Buscador de términos
            term_search = st.text_input("Buscar termino en glosario:", placeholder="Ej: cliente, expediente, sentencia...")
            
            if term_search:
                definition = get_business_definition(term_search)
                if "no encontrado" not in definition:
                    st.success(f"**{term_search.upper()}**: {definition}")
                else:
                    st.warning(definition)
                    
                    # Sugerir términos similares
                    st.write("**Términos disponibles en el glosario:**")
                    for term in sorted(BUSINESS_GLOSSARY.keys()):
                        if term_search.upper() in term or term_search.lower() in term.lower():
                            st.write(f"• {term}: {BUSINESS_GLOSSARY[term]}")
            else:
                st.info("Glosario de Negocios - Definiciones estandarizadas para terminos clave")
                st.write("**Términos disponibles:**")
                
                # Mostrar todos los términos
                cols = st.columns(2)
                for i, (term, definition) in enumerate(sorted(BUSINESS_GLOSSARY.items())):
                    with cols[i % 2]:
                        with st.expander(f"{term}"):
                            st.write(definition)
            
            # Estadísticas del glosario
            st.subheader("Estadisticas del Glosario")
            col1, col2 = st.columns(2)
            with col1:
                st.metric("Total Terminos", len(BUSINESS_GLOSSARY))
            with col2:
                st.metric("Dominios Cubiertos", len(DATA_OWNERS))

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
