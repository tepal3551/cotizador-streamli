import streamlit as st
import pandas as pd
from datetime import datetime
from fpdf import FPDF
from urllib.parse import quote_plus 
import re
import json
import os
from io import BytesIO

# ==========================================
# 1. FUNCIONES
# ==========================================

@st.cache_data
def cargar_catalogo(nombre_archivo_catalogo, nombre_archivo_actualizaciones):
    # ... (tu lógica original de carga de catálogo) ...
    catalogo = []
    if not os.path.exists(nombre_archivo_catalogo):
        return pd.DataFrame(columns=['codigo', 'descripcion', 'precio', 'display'])
    with open(nombre_archivo_catalogo, 'r', encoding='utf-8') as f:
        for line in f:
            try:
                partes = line.strip().split(',')
                codigo = partes[0].strip()
                precio = float(partes[-1].strip())
                descripcion = ','.join(partes[1:-1]).strip()
                catalogo.append({'codigo': codigo, 'descripcion': descripcion, 'precio': precio})
            except: continue
    df = pd.DataFrame(catalogo)
    df['display'] = df['codigo'] + " - " + df['descripcion']
    return df

@st.cache_data(ttl=600)
def cargar_clientes_desde_sheets():
    sheet_id = '1QzmVhpIiwWN2Scz8J9_jn2GeLI2jIz2Mv5I6HDiKQVs'
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&sheet=Clientes"
    try: return pd.read_csv(url)
    except: return pd.DataFrame()

def generar_pdf(cliente, vendedor, tipo_doc, tipo_lista, df_cot, total):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, "Cotizacion de Pedido", ln=True, align='C')
    pdf.set_font("Arial", '', 11)
    pdf.cell(0, 8, f"Cliente: {cliente} | Vendedor: {vendedor}", ln=True)
    pdf.ln(5)
    # ... (el resto de tu lógica de tabla PDF) ...
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, f"Total Global: ${total:,.2f}", ln=True, align='R')
    return pdf.output(dest='S').encode('latin-1')

# ==========================================
# 2. INTERFAZ
# ==========================================
st.set_page_config(layout="wide")

if 'cotizacion' not in st.session_state: st.session_state.cotizacion = []

# Carga de datos
catalogo_df = cargar_catalogo("CATALAGO 25 TRUP PRUEBA COTIZADOR.txt", "precios_actualizados.txt")
df_clientes = cargar_clientes_desde_sheets()

st.title("🔩 Cotizador de Pedidos")

# --- SECCIÓN VENDEDORES Y CLIENTES ---
col1, col2 = st.columns(2)
if not df_clientes.empty:
    vendedores_df = df_clientes.iloc[:, [0, 1]].drop_duplicates().dropna()
    opciones_vendedores = [f"{str(r.iloc[0])} - {str(r.iloc[1])}" for _, r in vendedores_df.iterrows()]
    
    vendedor_sel = col1.selectbox("👤 ¿Qué vendedor eres?", options=opciones_vendedores, index=None)
    
    if vendedor_sel:
        id_vendedor = vendedor_sel.split(" - ")[0]
        clientes_filtrados = df_clientes[df_clientes.iloc[:, 0].astype(str) == id_vendedor]
        cliente_sel = col1.selectbox("🏢 Cliente:", options=[f"{str(r.iloc[2])} - {str(r.iloc[3])}" for _, r in clientes_filtrados.iterrows()], index=None)
        
        # --- SECCIÓN PRODUCTOS ---
        prod_sel = st.selectbox("Buscar Producto:", options=catalogo_df['display'].tolist(), index=None)
        cant_sel = st.number_input("Cantidad:", min_value=1, value=1)
        
        if st.button("➕ Agregar"):
            if prod_sel and cliente_sel:
                info = catalogo_df[catalogo_df['display'] == prod_sel].iloc[0]
                st.session_state.cotizacion.append({'codigo': info['codigo'], 'descripcion': info['descripcion'], 'cantidad': cant_sel, 'precio_unitario': float(info['precio'])})
                st.rerun()

# --- TABLA Y BOTONES (SI HAY COTIZACIÓN) ---
if st.session_state.cotizacion:
    df_cot = pd.DataFrame(st.session_state.cotizacion)
    df_cot['Importe'] = df_cot['cantidad'] * df_cot['precio_unitario']
    st.table(df_cot)
    
    # [AQUÍ VA TU BLOQUE ÚNICO DE BOTONES QUE TE PASÉ ANTERIORMENTE]