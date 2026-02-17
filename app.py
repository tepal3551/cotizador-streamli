import streamlit as st
import pandas as pd
from datetime import datetime
from fpdf import FPDF
from urllib.parse import quote_plus 
import re 

# ==============================================================================
# SECCIÓN 1: DEFINICIÓN DE FUNCIONES
# ==============================================================================

@st.cache_data
def cargar_catalogo(nombre_archivo_catalogo, nombre_archivo_actualizaciones):
    """Carga el catálogo y aplica actualizaciones de precios."""
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
        return pd.DataFrame()

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

def generar_pdf(df, cliente, tipo_doc, lista, total):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(200, 10, txt="Cotización Truper", ln=True, align='C')
    
    pdf.set_font("Arial", size=12)
    pdf.ln(10)
    pdf.cell(200, 10, txt=f"Cliente: {cliente}", ln=True)
    pdf.cell(200, 10, txt=f"Tipo: {tipo_doc}", ln=True)
    pdf.cell(200, 10, txt=f"Lista: {lista}", ln=True)
    pdf.cell(200, 10, txt=f"Fecha: {datetime.now().strftime('%d/%m/%Y')}", ln=True)
    pdf.ln(10)
    
    # Encabezados de tabla
    pdf.set_font("Arial", 'B', 10)
    pdf.cell(30, 10, "Código", 1)
    pdf.cell(90, 10, "Descripción", 1)
    pdf.cell(20, 10, "Cant.", 1)
    pdf.cell(25, 10, "P. Unit", 1)
    pdf.cell(25, 10, "Subt.", 1)
    pdf.ln()
    
    pdf.set_font("Arial", size=9)
    for _, row in df.iterrows():
        pdf.cell(30, 8, str(row['codigo']), 1)
        pdf.cell(90, 8, str(row['descripcion'])[:45], 1)
        pdf.cell(20, 8, str(int(row['cantidad'])), 1)
        pdf.cell(25, 8, f"${row['precio_unitario']:,.2f}", 1)
        pdf.cell(25, 8, f"${row['Subtotal']:,.2f}", 1)
        pdf.ln()
        
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(200, 10, txt=f"TOTAL: ${total:,.2f}", ln=True, align='R')
    return pdf.output(dest='S').encode('latin-1')

def analizar_y_cargar_pedido(texto_pedido, df_catalogo):
    lineas = [line.strip() for line in texto_pedido.split('\n') if line.strip()]
    nuevos_productos = []
    catalogo_map = df_catalogo.set_index('codigo').to_dict('index') 
    PATRON = re.compile(r'^[^\d]*(\d{4,6})[^\d]*(\d{1,3})')

    for linea in lineas:
        match = PATRON.match(linea)
        if match:
            cod = match.group(1)
            cant = int(match.group(2))
            if cod in catalogo_map:
                p_base = float(catalogo_map[cod]['precio'])
                precio_final = p_base if st.session_state.tipo_lista == "Distribuidor" else p_base / 0.90
                nuevos_productos.append({
                    'codigo': cod, 'descripcion': catalogo_map[cod]['descripcion'],
                    'cantidad': cant, 'precio_unitario': precio_final
                })
    if nuevos_productos:
        st.session_state.cotizacion.extend(nuevos_productos)

def agregar_producto_manual():
    if st.session_state.prod_sel:
        info = st.session_state.catalogo_df[st.session_state.catalogo_df['display'] == st.session_state.prod_sel].iloc[0]
        p_base = float(info['precio'])
        precio_final = p_base if st.session_state.tipo_lista == "Distribuidor" else p_base / 0.90
        st.session_state.cotizacion.append({
            'codigo': info['codigo'], 'descripcion': info['descripcion'],
            'cantidad': st.session_state.cant_sel, 'precio_unitario': precio_final
        })

# ==============================================================================
# SECCIÓN 2: INTERFAZ
# ==============================================================================

st.set_page_config(page_title="Cotizador Truper", layout="wide")

if 'cotizacion' not in st.session_state: st.session_state.cotizacion = []
if 'tipo_lista' not in st.session_state: st.session_state.tipo_lista = "Distribuidor"

# --- LOGOS Y TÍTULO ---
col_logo1, col_titulo, col_logo2 = st.columns([1, 4, 1])
with col_logo1:
    st.image("logo1.png", width=100) # Asegúrate que el archivo exista
with col_titulo:
    st.title("Cotizador Truper")
with col_logo2:
    st.image("logo2.png", width=100) # Asegúrate que el archivo exista

catalogo_df = cargar_catalogo("CATALAGO 25 TRUP PRUEBA COTIZADOR.txt", "precios_actualizados.txt")
st.session_state.catalogo_df = catalogo_df

# --- CONFIGURACIÓN ---
c_cfg1, c_cfg2 = st.columns(2)
with c_cfg1:
    cliente = st.text_input("Cliente:").upper()
    tipo_doc = st.text_input("Tipo de Documento (Remisión/Factura):", value="Remisión")
with c_cfg2:
    st.session_state.tipo_lista = st.radio("Lista de Precios:", ["Distribuidor", "Dimefet"], horizontal=True)

# --- BÚSQUEDA ---
with st.expander("🔍 Búsqueda"):
    c1, c2, c3 = st.columns([4,1,1])
    c1.selectbox("Producto:", catalogo_df['display'], key="prod_sel")
    c2.number_input("Cant:", min_value=1, value=1, key="cant_sel")
    c3.button("➕ Añadir", on_click=agregar_producto_manual)

with st.expander("🚀 Carga Rápida"):
    texto = st.text_area("Pega aquí (Código Cantidad)")
    if st.button("Procesar"):
        analizar_y_cargar_pedido(texto, catalogo_df)
        st.rerun()

# --- TABLA Y ACCIONES ---
if st.session_state.cotizacion:
    df_cot = pd.DataFrame(st.session_state.cotizacion)
    df_cot['Subtotal'] = df_cot['cantidad'] * df_cot['precio_unitario']
    st.table(df_cot.style.format({'precio_unitario': '${:,.2f}', 'Subtotal': '${:,.2f}'}))
    
    total = df_cot['Subtotal'].sum()
    st.subheader(f"Total ({st.session_state.tipo_lista}): ${total:,.2f}")

    # --- FORMATO WHATSAPP (SOLO DETALLE SOLICITADO) ---
    mensaje = f"Nuevo Pedido\n\nCliente: {cliente}\nTipo de Documento: {tipo_doc}\n\nDetalle del Pedido:\n\n"
    for _, fila in df_cot.iterrows():
        # Formato: * CODIGO CANTIDAD DESCRIPCION
        mensaje += f"* {fila['codigo']} {int(fila['cantidad'])} {fila['descripcion']}\n"
    
    wa_url = f"https://wa.me/?text={quote_plus(mensaje)}"
    
    # --- BOTONES DE SALIDA ---
    col_acc1, col_acc2, col_acc3 = st.columns(3)
    with col_acc1:
        st.link_button("📲 Enviar WhatsApp", wa_url, use_container_width=True)
    with col_acc2:
        pdf_bytes = generar_pdf(df_cot, cliente, tipo_doc, st.session_state.tipo_lista, total)
        st.download_button("📥 Descargar PDF", data=pdf_bytes, file_name=f"Cotizacion_{cliente}.pdf", mime="application/pdf", use_container_width=True)
    with col_acc3:
        if st.button("🗑️ Limpiar", use_container_width=True):
            st.session_state.cotizacion = []
            st.rerun()
else:
    st.info("Agregue productos.")