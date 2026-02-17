import streamlit as st
import pandas as pd
from datetime import datetime
from fpdf import FPDF
from urllib.parse import quote_plus 
import re 

# ==============================================================================
# SECCIÓN 1: CLASE PDF (USANDO TUS LOGOS ORIGINALES)
# ==============================================================================

class PDF(FPDF):
    def header(self):
        try:
            # Logos desde las URLs de tu primer código para evitar errores de archivo
            self.image("https://i.postimg.cc/HL8bS9xY/logo-empresa.jpg", 10, 8, 33)
            self.image("https://i.postimg.cc/c4DY0bt1/logo-marca.jpg", self.w - 43, 8, 33)
        except:
            pass
        self.set_font('Arial', 'B', 15)
        self.cell(0, 10, 'Cotizacion de Pedidos', 0, 1, 'C')
        self.ln(20)

def fpdf_safe(texto):
    """Limpia el texto para que FPDF no falle con acentos o símbolos de Truper."""
    if not texto: return ""
    replacements = {
        "á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u",
        "Á": "A", "É": "E", "Í": "I", "Ó": "O", "Ú": "U",
        "ñ": "n", "Ñ": "N", "’": "'", "“": '"', "”": '"', "—": "-",
        "°": " o.", "²": "2", "³": "3", "¼": "1/4", "½": "1/2", "¾": "3/4"
    }
    t = str(texto)
    for key, val in replacements.items():
        t = t.replace(key, val)
    return t.encode('latin-1', 'replace').decode('latin-1')

# ==============================================================================
# SECCIÓN 2: LÓGICA DE DATOS
# ==============================================================================

@st.cache_data
def cargar_catalogo(nombre_archivo_catalogo, nombre_archivo_actualizaciones):
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
                except: continue
    except FileNotFoundError: return pd.DataFrame()

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

def analizar_y_cargar_pedido(texto_pedido, df_catalogo):
    lineas = [line.strip() for line in texto_pedido.split('\n') if line.strip()]
    nuevos_productos = []
    catalogo_map = df_catalogo.set_index('codigo').to_dict('index') 
    PATRON = re.compile(r'^[^\d]*(\d{4,6})[^\d]+(\d{1,3})')

    for linea in lineas:
        match = PATRON.search(linea)
        if match:
            cod = match.group(1)
            cant = int(match.group(2))
            if cod in catalogo_map:
                p_base = float(catalogo_map[cod]['precio'])
                # Lógica Dimefet: Precio / 0.90 para que al descontar 10% regrese al base
                precio_final = p_base if st.session_state.tipo_lista == "Distribuidor" else p_base / 0.90
                nuevos_productos.append({
                    'codigo': cod, 'descripcion': catalogo_map[cod]['descripcion'],
                    'cantidad': cant, 'precio_unitario': precio_final
                })
    if nuevos_productos:
        st.session_state.cotizacion.extend(nuevos_productos)

# ==============================================================================
# SECCIÓN 3: INTERFAZ
# ==============================================================================

st.set_page_config(page_title="Cotizador Truper", layout="wide")

if 'cotizacion' not in st.session_state: st.session_state.cotizacion = []
if 'tipo_lista' not in st.session_state: st.session_state.tipo_lista = "Distribuidor"

# Logos e Interfaz (Cargados por URL)
c1, c2, c3 = st.columns([1,3,1])
with c1: st.image("https://i.postimg.cc/HL8bS9xY/logo-empresa.jpg", width=120)
with c2: st.markdown("<h1 style='text-align: center;'>Cotizador Truper</h1>", unsafe_allow_html=True)
with c3: st.image("https://i.postimg.cc/c4DY0bt1/logo-marca.jpg", width=120)

catalogo_df = cargar_catalogo("CATALAGO 25 TRUP PRUEBA COTIZADOR.txt", "precios_actualizaciones.txt")
st.session_state.catalogo_df = catalogo_df

# Configuración
col_info1, col_info2 = st.columns(2)
with col_info1:
    cliente = st.text_input("Cliente:", placeholder="Ej: TOME GARCIA MARIA MAGDALENA").upper()
    tipo_doc = st.text_input("Tipo de Documento:", value="Remision")
with col_info2:
    st.session_state.tipo_lista = st.radio("Lista de Precios:", ["Distribuidor", "Dimefet"], horizontal=True)

# Carga Rápida
with st.expander("🚀 Carga Rapida (Pegar pedido de WhatsApp)"):
    texto_pegar = st.text_area("Pega aquí (Ej: 2424 4)")
    if st.button("Procesar Pedido"):
        analizar_y_cargar_pedido(texto_pegar, catalogo_df)
        st.rerun()

# Tabla de resultados
if st.session_state.cotizacion:
    df_cot = pd.DataFrame(st.session_state.cotizacion)
    df_cot['Subtotal'] = df_cot['cantidad'] * df_cot['precio_unitario']
    st.table(df_cot.style.format({'precio_unitario': '${:,.2f}', 'Subtotal': '${:,.2f}'}))
    
    total_gral = df_cot['Subtotal'].sum()
    st.subheader(f"Total Cotizado: ${total_gral:,.2f}")

    # WhatsApp (Texto Simple)
    mensaje_wa = f"Nuevo Pedido\n\nCliente: {cliente}\nTipo de Documento: {tipo_doc}\n\nDetalle del Pedido:\n\n"
    for _, r in df_cot.iterrows():
        mensaje_wa += f"* {r['codigo']} {int(r['cantidad'])} {r['descripcion']}\n"
    
    col_btn1, col_btn2, col_btn3 = st.columns(3)
    col_btn1.link_button("📲 WhatsApp", f"https://wa.me/?text={quote_plus(mensaje_wa)}", use_container_width=True)

    # Generación de PDF (Lógica de tu primer código)
    try:
        pdf = PDF()
        pdf.add_page()
        pdf.set_font("Arial", size=11)
        pdf.cell(0, 10, f"Cliente: {fpdf_safe(cliente)}", ln=True)
        pdf.cell(0, 10, f"Tipo: {fpdf_safe(tipo_doc)}", ln=True)
        pdf.cell(0, 10, f"Fecha: {datetime.now().strftime('%d/%m/%Y')}", ln=True)
        pdf.ln(5)
        
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(25, 10, "Codigo", 1); pdf.cell(95, 10, "Descripcion", 1); pdf.cell(20, 10, "Cant", 1); pdf.cell(30, 10, "Subtotal", 1); pdf.ln()
        
        pdf.set_font("Arial", size=9)
        for _, fila in df_cot.iterrows():
            pdf.cell(25, 8, fpdf_safe(fila['codigo']), 1)
            pdf.cell(95, 8, fpdf_safe(fila['descripcion'])[:50], 1)
            pdf.cell(20, 8, str(int(fila['cantidad'])), 1, 0, 'C')
            pdf.cell(30, 8, f"${fila['Subtotal']:,.2f}", 1, 0, 'R')
            pdf.ln()
            
        pdf.ln(5); pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 10, f"TOTAL: ${total_gral:,.2f}", ln=True, align='R')
        
        pdf_bytes = pdf.output(dest='S').encode('latin-1')
        col_btn2.download_button("📥 PDF", pdf_bytes, f"Pedido_{cliente}.pdf", "application/pdf", use_container_width=True)
    except:
        col_btn2.error("Error PDF")

    if col_btn3.button("🗑️ Limpiar"):
        st.session_state.cotizacion = []
        st.rerun()