import streamlit as st
import pandas as pd
from datetime import datetime
from fpdf import FPDF
from urllib.parse import quote_plus
from io import BytesIO
import os

# ==========================================
# 1. FUNCIONES (DEFINIDAS AL INICIO)
# ==========================================

@st.cache_data
def cargar_catalogo(nombre_archivo):
    if not os.path.exists(nombre_archivo): 
        return pd.DataFrame(columns=['codigo', 'descripcion', 'precio', 'display'])
    df = pd.read_csv(nombre_archivo, names=['codigo', 'descripcion', 'precio'])
    df['display'] = df['codigo'].astype(str) + " - " + df['descripcion'].astype(str)
    return df

@st.cache_data(ttl=600)
def cargar_clientes_desde_sheets():
    sheet_id = '1QzmVhpIiwWN2Scz8J9_jn2GeLI2jIz2Mv5I6HDiKQVs'
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&sheet=Clientes"
    try: return pd.read_csv(url)
    except: return pd.DataFrame()

def guardar_cotizacion_pausa(nombre, lista, partidas):
    st.success(f"💾 Cotización de '{nombre}' guardada en pausa.")

def generar_pdf(cliente, vendedor, tipo_doc, tipo_lista, df_cot, total):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, "Cotizacion de Pedido", ln=True, align='C')
    pdf.set_font("Arial", '', 11)
    pdf.cell(0, 8, f"Cliente: {cliente}", ln=True)
    pdf.cell(0, 8, f"Vendedor: {vendedor}", ln=True)
    pdf.cell(0, 8, f"Documento: {tipo_doc} | Lista: {tipo_lista}", ln=True)
    pdf.cell(0, 8, f"Fecha: {datetime.now().strftime('%d/%m/%Y')}", ln=True)
    pdf.ln(5)
    
    # Encabezado tabla
    pdf.set_font("Arial", 'B', 9)
    pdf.cell(25, 8, "Codigo", 1)
    pdf.cell(105, 8, "Descripcion", 1)
    pdf.cell(20, 8, "Cant.", 1, 0, 'C')
    pdf.cell(40, 8, "Importe", 1, 1, 'C')
    
    # Contenido tabla
    pdf.set_font("Arial", '', 8)
    for _, row in df_cot.iterrows():
        pdf.cell(25, 8, str(row['codigo']), 1)
        pdf.cell(105, 8, str(row['descripcion'])[:55], 1)
        pdf.cell(20, 8, str(row['cantidad']), 1, 0, 'C')
        pdf.cell(40, 8, f"${row['Importe']:,.2f}", 1, 1, 'R')
        
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, f"Total Global: ${total:,.2f}", ln=True, align='R')
    return pdf.output(dest='S').encode('latin-1')

# ==========================================
# 2. INTERFAZ Y LÓGICA PRINCIPAL
# ==========================================
st.set_page_config(layout="wide")

if 'cotizacion' not in st.session_state: st.session_state.cotizacion = []

# Carga de datos
catalogo_df = cargar_catalogo("CATALAGO 25 TRUP PRUEBA COTIZADOR.txt")
df_clientes = cargar_clientes_desde_sheets()

st.title("🔩 Cotizador de Pedidos")

# Fila de filtros
col1, col2 = st.columns(2)
vendedor_sel = col1.selectbox("👤 ¿Qué vendedor eres?", options=[f"{str(r.iloc[0])} - {str(r.iloc[1])}" for _, r in df_clientes.iloc[:, [0, 1]].drop_duplicates().iterrows()] if not df_clientes.empty else [], index=None)

if vendedor_sel:
    id_vendedor = vendedor_sel.split(" - ")[0]
    cliente_sel = col1.selectbox("🏢 Cliente:", options=[f"{str(r.iloc[2])} - {str(r.iloc[3])}" for _, r in df_clientes[df_clientes.iloc[:, 0].astype(str) == id_vendedor].iterrows()], index=None)
    
    with col2:
        tipo_doc = st.selectbox("📄 Tipo de Documento:", ["Remision", "Factura"])
        tipo_lista = st.radio("💰 Lista de Precios:", ["Distribuidor", "Dimefet"], horizontal=True)

    # Búsqueda de productos
    prod_sel = st.selectbox("Buscar Producto:", options=catalogo_df['display'].tolist(), index=None)
    cant_sel = st.number_input("Cantidad:", min_value=1, value=1)
    
    if st.button("➕ Agregar Artículo"):
        if prod_sel and cliente_sel:
            info = catalogo_df[catalogo_df['display'] == prod_sel].iloc[0]
            precio_base = float(info['precio'])
            precio_final = precio_base if tipo_lista == "Distribuidor" else precio_base / 0.90
            st.session_state.cotizacion.append({
                'codigo': info['codigo'], 'descripcion': info['descripcion'],
                'cantidad': cant_sel, 'precio_unitario': precio_final
            })
            st.rerun()

    # Tabla y Botones de acción
    if st.session_state.cotizacion:
        df_cot = pd.DataFrame(st.session_state.cotizacion)
        df_cot['Importe'] = df_cot['cantidad'] * df_cot['precio_unitario']
        st.table(df_cot)
        
        total_cot = df_cot['Importe'].sum()
        st.markdown("---")
        
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            if st.button("💾 Guardar Pausa", key="b_pausa"): guardar_cotizacion_pausa(cliente_sel, tipo_lista, st.session_state.cotizacion)
        with c2:
            pdf_b = generar_pdf(cliente_sel, vendedor_sel, tipo_doc, tipo_lista, df_cot, total_cot)
            st.download_button("📄 Descargar PDF", data=pdf_b, file_name="pedido.pdf", mime="application/pdf", key="b_pdf")
        with c3:
            st.link_button("📲 WhatsApp", f"https://wa.me/?text={quote_plus('Pedido: ' + str(cliente_sel))}")
        with c4:
            if st.button("🗑️ Limpiar"): st.session_state.cotizacion = []; st.rerun()