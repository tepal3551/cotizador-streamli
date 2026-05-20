import streamlit as st
import pandas as pd
from datetime import datetime
from fpdf import FPDF
from urllib.parse import quote_plus 
import re
import json
import os
import requests 
from io import BytesIO

# ==============================================================================
# SECCIÓN 1: DEFINICIÓN DE FUNCIONES Y CARGA DE CATÁLOGOS
# ==============================================================================

@st.cache_data
def cargar_catalogo(nombre_archivo_catalogo, nombre_archivo_actualizaciones):
    """Carga el catálogo de productos desde archivos .txt locales."""
    catalogo = []
    try:
        with open(nombre_archivo_catalogo, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    partes = line.strip().split(',')
                    if len(partes) < 3: continue
                    codigo = partes[0].strip()
                    precio = float(partes[-1].strip())
                    descripcion = ','.join(partes[1:-1]).strip()
                    catalogo.append({'codigo': codigo, 'descripcion': descripcion, 'precio': precio})
                except (ValueError, IndexError): continue
    except FileNotFoundError:
        return pd.DataFrame(columns=['codigo', 'descripcion', 'precio'])

    df = pd.DataFrame(catalogo)
    if df.empty: return pd.DataFrame(columns=['codigo', 'descripcion', 'precio'])
    df = df.set_index('codigo')

    try:
        with open(nombre_archivo_actualizaciones, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    partes = line.strip().split(',')
                    if len(partes) < 3: continue 
                    codigo = partes[0].strip()
                    nuevo_precio = float(partes[-1].strip())
                    nueva_descripcion = ','.join(partes[1:-1]).strip()
                    df.loc[codigo] = {'descripcion': nueva_descripcion, 'precio': nuevo_precio}
                except: continue
    except FileNotFoundError: pass

    df = df.reset_index()
    df['display'] = df['codigo'] + " - " + df['descripcion']
    return df

@st.cache_data(ttl=600) # Se refresca cada 10 minutos para traer nuevos clientes
def cargar_clientes_desde_sheets():
    """Descarga la lista de clientes dinámicamente desde Google Sheets."""
    sheet_id = '1QzmVhpIiwWN2Scz8J9_jn2GeLI2jIz2Mv5I6HDiKQVs'
    nombre_pestana = 'Clientes' # <-- Cambia esto si tu pestaña se llama diferente
    url_clientes = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={nombre_pestana}"
    
    try:
        df = pd.read_csv(url_clientes)
        # Asumimos que la Columna A es la Clave y la Columna B es el Nombre
        df_clientes = pd.DataFrame()
        df_clientes['clave'] = df.iloc[:, 0].astype(str).str.strip()
        df_clientes['nombre'] = df.iloc[:, 1].astype(str).str.strip().str.upper()
        return df_clientes
    except Exception as e:
        st.warning("⚠️ No se pudo conectar a Google Sheets para los clientes. Usando respaldo local.")
        return pd.DataFrame([
            {"clave": "CTE001", "nombre": "TOME GARCIA MARIA MAGDALENA"},
            {"clave": "CTE000", "nombre": "CLIENTE PUBLICO GENERAL"}
        ])

def analizar_y_cargar_pedido(texto_pedido, df_catalogo):
    """Analiza líneas de texto identificando código y cantidad de forma ultra flexible."""
    lineas = [line.strip() for line in texto_pedido.split('\n') if line.strip()]
    nuevos_productos = []
    diagnostico_fallos = []
    
    catalogo_map = df_catalogo.set_index('codigo').to_dict('index') 
    productos_en_sesion = {p['codigo'] for p in st.session_state.cotizacion}

    PATRON_PEDIDO = re.compile(r'^[^\d]*(\d{4,6})[^\d]*(\d{1,3})')

    for linea in lineas:
        if 'DETALLE' in linea.upper() or 'CLIENTE' in linea.upper() or len(linea.split()) < 2: 
            continue
            
        codigo_posible = None
        cantidad_posible = 0

        match = PATRON_PEDIDO.match(linea)
        if match:
            try:
                codigo_posible = match.group(1).strip()
                cantidad_posible = int(match.group(2))
                if cantidad_posible <= 0: cantidad_posible = 1
            except Exception: pass 

        if codigo_posible and codigo_posible in catalogo_map:
            if codigo_posible in productos_en_sesion: continue
            
            p_base = float(catalogo_map[codigo_posible]['precio'])
            precio_final = p_base if st.session_state.tipo_lista == "Distribuidor" else p_base / 0.90
            
            nuevos_productos.append({
                'codigo': codigo_posible,
                'descripcion': catalogo_map[codigo_posible]['descripcion'],
                'cantidad': cantidad_posible,
                'precio_unitario': precio_final
            })
        else:
            if codigo_posible and cantidad_posible > 0:
                diagnostico_fallos.append(f"Cód. no enc.: '{codigo_posible}' Línea: {linea.strip()}")
            
    if nuevos_productos:
        st.session_state.cotizacion.extend(nuevos_productos)
        st.success(f"Se cargaron {len(nuevos_productos)} productos a la cotización.")
    else:
        if not diagnostico_fallos:
            st.warning("No se encontraron productos válidos en el formato.")
            
    if diagnostico_fallos:
        st.error("❌ Fallos de Coincidencia (Verifica catálogo):")
        st.code('\n'.join(diagnostico_fallos))

def guardar_cotizacion_pausa(nombre_cliente, tipo_lista, partidas):
    """Guarda localmente una cotización para recuperar/editar después."""
    archivo_registro = "cotizaciones_pausa.json"
    registro = {}
    if os.path.exists(archivo_registro):
        with open(archivo_registro, "r", encoding="utf-8") as f:
            try: registro = json.load(f)
            except: pass
            
    registro[nombre_cliente] = {
        "fecha": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "tipo_lista": tipo_lista,
        "partidas": partidas
    }
    with open(archivo_registro, "w", encoding="utf-8") as f:
        json.dump(registro, f, ensure_ascii=False, indent=4)
    st.success(f"💾 Cotización de '{nombre_cliente}' guardada en pausa.")

# ==============================================================================
# SECCIÓN 2: INTERFAZ Y LÓGICA DE CONTROL DE STREAMLIT
# ==============================================================================

st.set_page_config(page_title="Cotizador Corporativo", layout="wide")

if 'cotizacion' not in st.session_state: st.session_state.cotizacion = []
if 'tipo_lista' not in st.session_state: st.session_state.tipo_lista = "Distribuidor"

# Carga de catálogos (Mixto: TXT local + Google Sheets)
catalogo_df = cargar_catalogo("CATALAGO 25 TRUP PRUEBA COTIZADOR.txt", "precios_actualizados.txt")
st.session_state.catalogo_df = catalogo_df
df_clientes = cargar_clientes_desde_sheets()

st.title("🔩 Cotizador de Pedidos Inteligente")
st.markdown("---")

# --- BLOQUE 1: RECUPERAR COTIZACIÓN EN PAUSA ---
archivo_registro = "cotizaciones_pausa.json"
if os.path.exists(archivo_registro):
    with open(archivo_registro, "r", encoding="utf-8") as f:
        try: cotizaciones_guardadas = json.load(f)
        except: cotizaciones_guardadas = {}
    
    if cotizaciones_guardadas:
        with st.sidebar.expander("📂 Recuperar Cotización en Pausa"):
            cot_seleccionada = st.selectbox("Selecciona un cliente para editar:", options=list(cotizaciones_guardadas.keys()))
            if st.button("Cargar y Editar"):
                datos_recuperados = cotizaciones_guardadas[cot_seleccionada]
                st.session_state.cotizacion = datos_recuperados["partidas"]
                st.session_state.tipo_lista = datos_recuperados["tipo_lista"]
                st.sidebar.success(f"Cargadas {len(st.session_state.cotizacion)} partidas de {cot_seleccionada}")
                st.rerun()

# --- BLOQUE 2: CONFIGURACIÓN GENERAL DEL PEDIDO ---
col_gen1, col_gen2, col_gen3 = st.columns(3)
with col_gen1:
    cliente_sel = st.selectbox("🏢 Selecciona el Cliente:", options=df_clientes['nombre'].tolist())
    cve_cliente_actual = df_clientes[df_clientes['nombre'] == cliente_sel]['clave'].values[0]
    st.caption(f"Clave de Cliente ERP: **{cve_cliente_actual}**")
with col_gen2:
    tipo_doc = st.selectbox("📄 Tipo de Documento:", ["Remision", "Factura"])
with col_gen3:
    st.session_state.tipo_lista = st.radio("💰 Lista de Precios comercial:", ["Distribuidor", "Dimefet"], horizontal=True)

# --- BLOQUE 3: AGREGAR ARTÍCULOS ---
tab_manual, tab_rapida = st.tabs(["🔍 Búsqueda Individual", "🚀 Carga Rápida por Texto"])

with tab_manual:
    col_m1, col_m2, col_m3 = st.columns([4,1,1])
    prod_sel = col_m1.selectbox("Buscar Producto:", options=catalogo_df['display'].tolist(), index=None, placeholder="Escribe código o nombre...")
    cant_sel = col_m2.number_input("Cantidad:", min_value=1, value=1, step=1)
    if col_m3.button("➕ Agregar Artículo", use_container_width=True):
        if prod_sel:
            info = catalogo_df[catalogo_df['display'] == prod_sel].iloc[0]
            p_base = float(info['precio'])
            precio_final = p_base if st.session_state.tipo_lista == "Distribuidor" else p_base / 0.90
            
            if not any(p['codigo'] == info['codigo'] for p in st.session_state.cotizacion):
                st.session_state.cotizacion.append({
                    'codigo': info['codigo'], 'descripcion': info['descripcion'],
                    'cantidad': cant_sel, 'precio_unitario': precio_final
                })
                st.success("Producto añadido.")
                st.rerun()

with tab_rapida:
    texto_rapido = st.text_area("Pega aquí el listado enviado por el cliente:", height=120, placeholder="• 44282 *2* CADENA DE PASEO...")
    if st.button("🚀 Procesar y Cargar Listado", type="primary"):
        analizar_y_cargar_pedido(texto_rapido, catalogo_df)
        st.rerun()

# --- BLOQUE 4: TABLA DE TRABAJO ACTUAL ---
st.markdown("---")
st.subheader("📋 Detalle de la Cotización Actual")

if st.session_state.cotizacion:
    df_cot = pd.DataFrame(st.session_state.cotizacion)
    df_cot['Importe'] = df_cot['cantidad'] * df_cot['precio_unitario']
    
    st.table(df_cot.style.format({'precio_unitario': '${:,.2f}', 'Importe': '${:,.2f}'}))
    total_cotizacion = df_cot['Importe'].sum()
    st.markdown(f"### **Total Global ({st.session_state.tipo_lista}): ${total_cotizacion:,.2f}**")
    
    c_btn1, c_btn2, c_btn3 = st.columns(3)
    with c_btn1:
        if st.button("💾 Guardar en Pausa", use_container_width=True):
            guardar_cotizacion_pausa(cliente_sel, st.session_state.tipo_lista, st.session_state.cotizacion)
    with c_btn2:
        mensaje_wa = f"*Nuevo Pedido*\n\n*Cliente:* {cliente_sel}\n*Tipo de Documento:* {tipo_doc}\n\n*Detalle del Pedido:*\n\n"
        for _, fila in df_cot.iterrows():
            mensaje_wa += f"* {fila['codigo']} {fila['cantidad']} {fila['descripcion']}\n"
        url_wa = f"https://wa.me/?text={quote_plus(mensaje_wa)}"
        st.link_button("📲 Compartir por WhatsApp", url_wa, use_container_width=True)
    with c_btn3:
        if st.button("🗑️ Limpiar Pantalla", use_container_width=True):
            st.session_state.cotizacion = []
            st.rerun()

    # --- SECCIÓN 3: CONEXIÓN DE FOLIO CENTRAL Y EXPORTACIÓN AL ERP ---
    st.markdown("---")
    st.header("⚙️ Finalizar y Exportar para Carga en ERP")
    
    # PEGA AQUÍ LA URL DE TU APPS SCRIPT
    URL_API_FOLIOS = "TU_URL_DE_GOOGLE_APPS_SCRIPT_AQUI" 
    
    if st.button("🚀 OBTENER FOLIO Y GENERAR EXCEL", type="primary", use_container_width=True):
        folio_asignado = "COT-MANUAL-1" 
        
        if URL_API_FOLIOS != "TU_URL_DE_GOOGLE_APPS_SCRIPT_AQUI":
            try:
                respuesta = requests.get(URL_API_FOLIOS, timeout=5)
                if respuesta.status_code == 200:
                    datos_central = respuesta.json()
                    folio_asignado = str(datos_central.get("siguienteFolio", folio_asignado))
            except:
                st.warning("⚠️ No se conectó a la API. Usando folio de respaldo.")

        filas_erp = []
        fecha_alta = datetime.now().strftime("%d/%m/%Y")
        
        for item in st.session_state.cotizacion:
            filas_erp.append({
                "no_ped": folio_asignado,
                "f_alta": fecha_alta,
                "cve_cte": cve_cliente_actual,
                "cve_age": "AGE01",
                "cve_prod": item['codigo'],
                "cant_prod": item['cantidad'],
                "cve_suc": "1",
                "cve_mon": "P",
                "lugar": "A2"
            })
            
        df_final_erp = pd.DataFrame(filas_erp)
        
        output_buffer = BytesIO()
        with pd.ExcelWriter(output_buffer, engine='openpyxl') as writer:
            df_final_erp.to_excel(writer, index=False, sheet_name='Pedido')
        
        st.success(f"🎉 ¡Éxito! Folio oficial asignado: **{folio_asignado}**")
        
        st.download_button(
            label="📥 Descargar Archivo Excel Estructurado para ERP",
            data=output_buffer.getvalue(),
            file_name=f"{folio_asignado}_Pedido_ERP.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )
else:
    st.info("La cotización está vacía. Añade productos de forma manual o mediante la carga rápida.")