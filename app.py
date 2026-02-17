import streamlit as st
import pandas as pd
from datetime import datetime
from fpdf import FPDF
from urllib.parse import quote_plus 
import re 

# ==============================================================================
# SECCIÓN 1: DEFINICIÓN DE CLASE PDF (BASADA EN TU CÓDIGO ORIGINAL)
# ==============================================================================

class PDF(FPDF):
    def header(self):
        try:
            # Logos desde las URLs de tu primer código
            self.image("https://i.postimg.cc/HL8bS9xY/logo-empresa.jpg", 10, 8, 33)
            self.image("https://i.postimg.cc/c4DY0bt1/logo-marca.jpg", self.w - 43, 8, 33)
        except Exception:
            pass
        self.set_font('Arial', 'B', 15)
        self.cell(0, 10, 'Cotizacion de Pedidos', 0, 1, 'C') # Sin acento para evitar error
        self.ln(20)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Pagina {self.page_no()}', 0, 0, 'C')

def limpiar_texto(texto):
    """Limpia caracteres especiales para que FPDF no marque error."""
    if not texto: return ""
    # Reemplazos comunes que causan error en FPDF Arial
    remplazos = {
        "á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u",
        "Á": "A", "É": "E", "Í": "I", "Ó": "O", "Ú": "U",
        "ñ": "n", "Ñ": "N", "´": "", "’": "'", "“": '"', "”": '"', "—": "-"
    }
    t = str(texto)
    for original, reemplazo in remplazos.items():
        t = t.replace(original, reemplazo)
    # Elimina cualquier otro caracter no compatible con latin-1
    return t.encode('latin-1', 'replace').decode('latin-1')

# ==============================================================================
# SECCIÓN 2: FUNCIONES DE LOGICA
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

# ==============================================================================
# SECCIÓN 3: INTERFAZ STREAMLIT
# ==============================================================================

st.set_page_config(page_title="Cotizador Truper", layout="wide")

if 'cotizacion' not in st.session_state: st.session_state.cotizacion = []
if 'tipo_lista' not in st.session_state: st.session_state.tipo_lista = "Distribuidor"

# Encabezado Visual
c1, c2, c3 = st.columns([1,3,1])
with c1: st.image("https://i.postimg.cc/HL8bS9xY/logo-empresa.jpg", width=100)
with c2: st.markdown("<h1 style='text-align: center;'>Cotizador Truper</h1>", unsafe_allow_html=True)
with c3: st.image("https://i.postimg.cc/c4DY0bt1/logo-marca.jpg", width=100)

catalogo_df = cargar_catalogo("CATALAGO 25 TRUP PRUEBA COTIZADOR.txt", "precios_actualizados.txt")
st.session_state.catalogo_df = catalogo_df

# Inputs
col_a, col_b = st.columns(2)
with col_a:
    cliente = st.text_input("Cliente:").upper()
    tipo_doc = st.text_input("Documento:", value="Remision")
with col_b:
    st.session_state.tipo_lista = st.radio("Lista:", ["Distribuidor", "Dimefet"], horizontal=True)

with st.expander("🔍 Busqueda Manual"):
    f1, f2, f3 = st.columns([4,1,1])
    prod = f1.selectbox("Producto:", catalogo_df['display'] if not catalogo_df.empty else [])
    cant = f2.number_input("Cant:", min_value=1, value=1)
    if f3.button("Añadir"):
        info = catalogo_df[catalogo_df['display'] == prod].iloc[0]
        p_base = float(info['precio'])
        st.session_state.cotizacion.append({
            'codigo': info['codigo'], 'descripcion': info['descripcion'],
            'cantidad': cant, 'precio_unitario': p_base if st.session_state.tipo_lista == "Distribuidor" else p_base / 0.90
        })

if st.session_state.cotizacion:
    df_cot = pd.DataFrame(st.session_state.cotizacion)
    df_cot['Subtotal'] = df_cot['cantidad'] * df_cot['precio_unitario']
    st.table(df_cot.style.format({'precio_unitario': '${:,.2f}', 'Subtotal': '${:,.2f}'}))
    
    total = df_cot['Subtotal'].sum()
    st.subheader(f"Total: ${total:,.2f}")

    # Acciones
    btn1, btn2, btn3 = st.columns(3)
    
    # 1. WhatsApp
    mensaje = f"Nuevo Pedido\n\nCliente: {cliente}\nTipo de Documento: {tipo_doc}\n\nDetalle del Pedido:\n\n"
    for _, fila in df_cot.iterrows():
        mensaje += f"* {fila['codigo']} {int(fila['cantidad'])} {fila['descripcion']}\n"
    btn1.link_button("📲 WhatsApp", f"https://wa.me/?text={quote_plus(mensaje)}", use_container_width=True)

    # 2. PDF (Logica original mejorada)
    try:
        pdf = PDF()
        pdf.add_page()
        pdf.set_font("Arial", size=11)
        pdf.cell(0, 10, f"Cliente: {limpiar_texto(cliente)}", ln=True)
        pdf.cell(0, 10, f"Fecha: {datetime.now().strftime('%d/%m/%Y')}", ln=True)
        pdf.ln(5)
        
        # Tabla PDF
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(25, 10, "Codigo", 1); pdf.cell(90, 10, "Descripcion", 1); pdf.cell(20, 10, "Cant", 1); pdf.cell(30, 10, "Subtotal", 1); pdf.ln()
        pdf.set_font("Arial", size=9)
        for _, r in df_cot.iterrows():
            pdf.cell(25, 8, limpiar_texto(r['codigo']), 1)
            pdf.cell(90, 8, limpiar_texto(r['descripcion'])[:45], 1)
            pdf.cell(20, 8, str(int(r['cantidad'])), 1)
            pdf.cell(30, 8, f"${r['Subtotal']:,.2f}", 1)
            pdf.ln()
        
        pdf.ln(5); pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 10, f"TOTAL: ${total:,.2f}", ln=True, align='R')
        
        pdf_out = pdf.output(dest='S').encode('latin-1')
        btn2.download_button("📥 Descargar PDF", pdf_out, f"Pedido_{cliente}.pdf", "application/pdf", use_container_width=True)
    except Exception as e:
        btn2.error("Error al crear PDF")

    if btn3.button("🗑️ Limpiar", use_container_width=True):
        st.session_state.cotizacion = []
        st.rerun()