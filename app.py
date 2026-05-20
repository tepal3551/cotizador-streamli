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
def generar_pdf(cliente, vendedor, tipo_doc, tipo_lista, df_cot, total):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, "Cotizacion de Pedido", ln=True, align='C')
    pdf.set_font("Arial", '', 11)
    pdf.cell(0, 8, f"Cliente: {cliente}", ln=True)
    pdf.cell(0, 8, f"Vendedor: {vendedor}", ln=True)
    pdf.cell(0, 8, f"Fecha: {datetime.now().strftime('%d/%m/%Y')}", ln=True)
    pdf.ln(5)
    
    # Tabla
    pdf.set_font("Arial", 'B', 9)
    pdf.cell(25, 8, "Codigo", 1)
    pdf.cell(105, 8, "Descripcion", 1)
    pdf.cell(20, 8, "Cant.", 1, 0, 'C')
    pdf.cell(40, 8, "Importe", 1, 1, 'C')
    
    pdf.set_font("Arial", '', 8)
    for _, row in df_cot.iterrows():
        pdf.cell(25, 8, str(row['codigo']), 1)
        pdf.cell(105, 8, str(row['descripcion'])[:55], 1)
        pdf.cell(20, 8, str(row['cantidad']), 1, 0, 'C')
        pdf.cell(40, 8, f"${row['Importe']:,.2f}", 1, 1, 'R')
        
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, f"Total Global: ${total:,.2f}", ln=True, align='R')
    
    # RETORNO LIMPIO DE BYTES
    return pdf.output(dest='S').encode('latin-1')

# ==========================================
# 2. INTERFAZ
# ==========================================
st.set_page_config(layout="wide")

if 'cotizacion' not in st.session_state: st.session_state.cotizacion = []

# (Aquí va tu carga de catalogo_df y df_clientes...)
# ... mantén tu lógica de carga tal cual la tenías ...

st.title("🔩 Cotizador de Pedidos")

# Lógica del botón Agregar (Colócalo justo después de definir el selectbox y number_input)
prod_sel = st.selectbox("Buscar Producto:", options=st.session_state.catalogo_df['display'].tolist(), index=None)
cant_sel = st.number_input("Cantidad:", min_value=1, value=1)

if st.button("➕ Agregar Artículo"):
    if prod_sel:
        info = st.session_state.catalogo_df[st.session_state.catalogo_df['display'] == prod_sel].iloc[0]
        st.session_state.cotizacion.append({
            'codigo': info['codigo'], 
            'descripcion': info['descripcion'],
            'cantidad': cant_sel, 
            'precio_unitario': float(info['precio'])
        })
        st.rerun()

# Tabla y Botones Finales
if st.session_state.cotizacion:
    df_cot = pd.DataFrame(st.session_state.cotizacion)
    df_cot['Importe'] = df_cot['cantidad'] * df_cot['precio_unitario']
    st.table(df_cot)
    
    # BOTONES FINALES
    col1, col2 = st.columns(2)
    with col1:
        pdf_bytes = generar_pdf("CLIENTE", "VENDEDOR", "Remision", "Distribuidor", df_cot, df_cot['Importe'].sum())
        st.download_button("📥 Descargar PDF", data=pdf_bytes, file_name="pedido.pdf", mime="application/pdf", key="pdf_final")
    with col2:
        if st.button("🗑️ Limpiar"):
            st.session_state.cotizacion = []
            st.rerun()