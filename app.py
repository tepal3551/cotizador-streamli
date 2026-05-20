import streamlit as st
import pandas as pd
from datetime import datetime
from fpdf import FPDF
from urllib.parse import quote_plus 
import re
import json
import os
from io import BytesIO

# ==============================================================================
# CONFIGURACIÓN E INICIALIZACIÓN
# ==============================================================================
st.set_page_config(page_title="Cotizador de Pedidos", layout="wide")

if 'cotizacion' not in st.session_state: st.session_state.cotizacion = []
if 'tipo_lista' not in st.session_state: st.session_state.tipo_lista = "Distribuidor"

# ==============================================================================
# FUNCIONES
# ==============================================================================

@st.cache_data
def cargar_catalogo(nombre_archivo_catalogo, nombre_archivo_actualizaciones):
    catalogo = []
    # (Tu lógica original de carga se mantiene igual)
    if not os.path.exists(nombre_archivo_catalogo):
        return pd.DataFrame(columns=['codigo', 'descripcion', 'precio', 'display'])
        
    with open(nombre_archivo_catalogo, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                partes = line.strip().split(',')
                if len(partes) < 3: continue
                codigo = partes[0].strip()
                precio = float(partes[-1].strip())
                descripcion = ','.join(partes[1:-1]).strip()
                catalogo.append({'codigo': codigo, 'descripcion': descripcion, 'precio': precio})
            except: continue
            
    df = pd.DataFrame(catalogo).set_index('codigo')
    
    # Actualizaciones
    if os.path.exists(nombre_archivo_actualizaciones):
        with open(nombre_archivo_actualizaciones, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    partes = line.strip().split(',')
                    codigo = partes[0].strip()
                    df.loc[codigo, ['descripcion', 'precio']] = [','.join(partes[1:-1]).strip(), float(partes[-1].strip())]
                except: continue
                
    df = df.reset_index()
    df['display'] = df['codigo'] + " - " + df['descripcion']
    return df

@st.cache_data(ttl=600) 
def cargar_clientes_desde_sheets():
    sheet_id = '1QzmVhpIiwWN2Scz8J9_jn2GeLI2jIz2Mv5I6HDiKQVs'
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&sheet=Clientes"
    try: return pd.read_csv(url)
    except: return pd.DataFrame()

def analizar_y_cargar_pedido(texto_pedido, df_catalogo):
    lineas = [l.strip() for l in texto_pedido.split('\n') if l.strip()]
    catalogo_map = df_catalogo.set_index('codigo').to_dict('index')
    productos_en_sesion = {p['codigo'] for p in st.session_state.cotizacion}
    PATRON = re.compile(r'^[^\d]*(\d{4,6})[^\d]*(\d{1,3})')
    
    nuevos = []
    for linea in lineas:
        match = PATRON.match(linea)
        if match:
            cod, cant = match.group(1), int(match.group(2))
            if cod in catalogo_map and cod not in productos_en_sesion:
                p_base = float(catalogo_map[cod]['precio'])
                precio = p_base if st.session_state.tipo_lista == "Distribuidor" else p_base / 0.90
                nuevos.append({'codigo': cod, 'descripcion': catalogo_map[cod]['descripcion'], 'cantidad': cant, 'precio_unitario': precio})
    
    if nuevos:
        st.session_state.cotizacion.extend(nuevos)
        st.success(f"Se cargaron {len(nuevos)} productos.")

def generar_pdf(cliente, vendedor, tipo_doc, tipo_lista, df_cot, total):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, "Cotizacion de Pedido", ln=True, align='C')
    pdf.set_font("Arial", '', 11)
    pdf.cell(0, 8, f"Cliente: {cliente} | Vendedor: {vendedor}", ln=True)
    pdf.cell(0, 8, f"Documento: {tipo_doc} | Lista: {tipo_lista}", ln=True)
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 9)
    pdf.cell(25, 8, "Codigo", 1); pdf.cell(105, 8, "Descripcion", 1); pdf.cell(20, 8, "Cant.", 1, 0, 'C'); pdf.cell(40, 8, "Importe", 1, 1, 'C')
    pdf.set_font("Arial", '', 8)
    for _, row in df_cot.iterrows():
        pdf.cell(25, 8, str(row['codigo']), 1)
        pdf.cell(105, 8, str(row['descripcion'])[:55], 1)
        pdf.cell(20, 8, str(row['cantidad']), 1, 0, 'C')
        pdf.cell(40, 8, f"${row['Importe']:,.2f}", 1, 1, 'R')
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, f"Total: ${total:,.2f}", ln=True, align='R')
    return pdf.output(dest='S').encode('latin-1')

# ==============================================================================
# INTERFAZ PRINCIPAL
# ==============================================================================
catalogo_df = cargar_catalogo("CATALAGO 25 TRUP PRUEBA COTIZADOR.txt", "precios_actualizados.txt")
df_clientes = cargar_clientes_desde_sheets()

st.title("🔩 Cotizador de Pedidos")

# Lógica de Vendedores y Clientes
col1, col2 = st.columns(2)
vendedor_sel = col1.selectbox("👤 ¿Qué vendedor eres?", options=[f"{str(r.iloc[0])} - {str(r.iloc[1])}" for _, r in df_clientes.iloc[:, [0, 1]].drop_duplicates().iterrows()] if not df_clientes.empty else [], index=None)

if vendedor_sel:
    id_vendedor = vendedor_sel.split(" - ")[0]
    cliente_sel = col1.selectbox("🏢 Cliente:", options=[f"{str(r.iloc[2])} - {str(r.iloc[3])}" for _, r in df_clientes[df_clientes.iloc[:, 0].astype(str) == id_vendedor].iterrows()], index=None)
    with col2:
        tipo_doc = st.selectbox("📄 Documento:", ["Remision", "Factura"])
        st.session_state.tipo_lista = st.radio("💰 Lista:", ["Distribuidor", "Dimefet"], horizontal=True)

    # Tabs de carga
    tab1, tab2 = st.tabs(["Búsqueda Individual", "Carga Rápida"])
    with tab1:
        prod = st.selectbox("Producto:", options=catalogo_df['display'].tolist(), index=None)
        cant = st.number_input("Cantidad:", 1, step=1)
        if st.button("➕ Agregar"):
            # Lógica de agregado manual aquí...
            st.rerun()
    with tab2:
        texto = st.text_area("Pega listado:")
        if st.button("🚀 Procesar"):
            analizar_y_cargar_pedido(texto, catalogo_df)
            st.rerun()

    # Tabla y Acciones (Solo si hay cotización)
    if st.session_state.cotizacion:
        df_cot = pd.DataFrame(st.session_state.cotizacion)
        df_cot['Importe'] = df_cot['cantidad'] * df_cot['precio_unitario']
        st.table(df_cot)
        
        if st.button("🗑️ Limpiar Todo"):
            st.session_state.cotizacion = []
            st.rerun()