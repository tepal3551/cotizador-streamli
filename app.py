import streamlit as st
import pandas as pd
from datetime import datetime
from fpdf import FPDF
from urllib.parse import quote_plus 
import re 

# ==============================================================================
# SECCIÓN 1: CONFIGURACIÓN Y CLASE PDF
# ==============================================================================

class PDF(FPDF):
    def header(self):
        try:
            # Usamos logos por URL para evitar el MediaFileStorageError
            self.image("https://i.postimg.cc/HL8bS9xY/logo-empresa.jpg", 10, 8, 33)
            self.image("https://i.postimg.cc/c4DY0bt1/logo-marca.jpg", self.w - 43, 8, 33)
        except:
            pass
        self.set_font('Arial', 'B', 15)
        self.cell(0, 10, 'Cotizacion de Pedidos', 0, 1, 'C')
        self.ln(20)

def limpiar_para_pdf(texto):
    """Limpia acentos y símbolos que rompen el PDF (Error de la imagen 2)."""
    if not texto: return ""
    remplazos = {
        "á": "a", "é": "e", "í": "i", "ó": "o", "ú": "u",
        "Á": "A", "É": "E", "Í": "I", "Ó": "O", "Ú": "U",
        "ñ": "n", "Ñ": "N", "°": " grados", '"': " pulg", "'": ""
    }
    t = str(texto)
    for original, nuevo in remplazos.items():
        t = t.replace(original, nuevo)
    return t.encode('latin-1', 'replace').decode('latin-1')

# ==============================================================================
# SECCIÓN 2: PROCESAMIENTO DE DATOS
# ==============================================================================

@st.cache_data
def cargar_catalogo(archivo_cat, archivo_act):
    catalogo = []
    try:
        with open(archivo_cat, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    partes = line.strip().split(',')
                    if len(partes) < 3: continue
                    catalogo.append({
                        'codigo': partes[0].strip(),
                        'descripcion': ','.join(partes[1:-1]).strip(),
                        'precio': float(partes[-1].strip())
                    })
                except: continue
    except FileNotFoundError: return pd.DataFrame()

    df = pd.DataFrame(catalogo).set_index('codigo')
    try:
        with open(archivo_act, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    p = line.strip().split(',')
                    if len(p) < 3: continue
                    df.loc[p[0].strip()] = {'descripcion': ','.join(p[1:-1]).strip(), 'precio': float(p[-1].strip())}
                except: continue
    except: pass
    
    df = df.reset_index()
    df['display'] = df['codigo'] + " - " + df['descripcion']
    return df

def analizar_y_cargar_pedido(texto, df_cat):
    lineas = [l.strip() for l in texto.split('\n') if l.strip()]
    catalogo_map = df_cat.set_index('codigo').to_dict('index') 
    PATRON = re.compile(r'^[^\d]*(\d{4,6})[^\d]+(\d{1,3})')
    
    nuevos = []
    for linea in lineas:
        match = PATRON.search(linea)
        if match:
            cod, cant = match.group(1), int(match.group(2))
            if cod in catalogo_map:
                p_base = float(catalogo_map[cod]['precio'])
                p_final = p_base if st.session_state.tipo_lista == "Distribuidor" else p_base / 0.90
                nuevos.append({'codigo': cod, 'descripcion': catalogo_map[cod]['descripcion'], 'cantidad': cant, 'precio_unitario': p_final})
    if nuevos: st.session_state.cotizacion.extend(nuevos)

# ==============================================================================
# SECCIÓN 3: INTERFAZ DE USUARIO (RESTAURADA)
# ==============================================================================

st.set_page_config(page_title="Cotizador Truper", layout="wide")

if 'cotizacion' not in st.session_state: st.session_state.cotizacion = []
if 'tipo_lista' not in st.session_state: st.session_state.tipo_lista = "Distribuidor"

# Encabezado con logos
c1, c2, c3 = st.columns([1,3,1])
with c1: st.image("https://i.postimg.cc/HL8bS9xY/logo-empresa.jpg", width=120)
with c2: st.markdown("<h1 style='text-align: center;'>Cotizador Truper</h1>", unsafe_allow_html=True)
with c3: st.image("https://i.postimg.cc/c4DY0bt1/logo-marca.jpg", width=120)

catalogo_df = cargar_catalogo("CATALAGO 25 TRUP PRUEBA COTIZADOR.txt", "precios_actualizados.txt")
st.session_state.catalogo_df = catalogo_df

# Ajustes de cliente
col_c1, col_c2 = st.columns(2)
with col_c1:
    cliente = st.text_input("Cliente:").upper()
    tipo_doc = st.text_input("Documento:", value="Remision")
with col_c2:
    st.session_state.tipo_lista = st.radio("Lista de Precios:", ["Distribuidor", "Dimefet"], horizontal=True)

# --- CARGA MANUAL (SELECTOR) ---
with st.expander("🔍 Añadir Producto Individual", expanded=True):
    m1, m2, m3 = st.columns([4,1,1])
    opciones = catalogo_df['display'].tolist() if not catalogo_df.empty else []
    p_sel = m1.selectbox("Producto:", opciones)
    c_sel = m2.number_input("Cant:", min_value=1, value=1)
    if m3.button("➕ Añadir"):
        info = catalogo_df[catalogo_df['display'] == p_sel].iloc[0]
        p_base = float(info['precio'])
        p_f = p_base if st.session_state.tipo_lista == "Distribuidor" else p_base / 0.90
        st.session_state.cotizacion.append({'codigo': info['codigo'], 'descripcion': info['descripcion'], 'cantidad': c_sel, 'precio_unitario': p_f})
        st.rerun()

# --- CARGA RÁPIDA (PEGAR TEXTO) ---
with st.expander("🚀 Carga Rápida (Pegar pedido)"):
    texto_p = st.text_area("Pega aquí (Ej: 2424 4)")
    if st.button("Procesar Lista"):
        analizar_y_cargar_pedido(texto_p, catalogo_df)
        st.rerun()

# --- TABLA Y ACCIONES FINAL ---
if st.session_state.cotizacion:
    df_cot = pd.DataFrame(st.session_state.cotizacion)
    df_cot['Subtotal'] = df_cot['cantidad'] * df_cot['precio_unitario']
    st.table(df_cot.style.format({'precio_unitario': '${:,.2f}', 'Subtotal': '${:,.2f}'}))
    
    total = df_cot['Subtotal'].sum()
    st.subheader(f"Total: ${total:,.2f}")

    # Mensaje de WhatsApp
    msj = f"Nuevo Pedido\n\nCliente: {cliente}\nTipo de Documento: {tipo_doc}\n\nDetalle del Pedido:\n\n"
    for _, r in df_cot.iterrows():
        msj += f"* {r['codigo']} {int(r['cantidad'])} {r['descripcion']}\n"
    
    wa, pdf_btn, clear = st.columns(3)
    wa.link_button("📲 WhatsApp", f"https://wa.me/?text={quote_plus(msj)}", use_container_width=True)

    # Generación de PDF Protegida
    try:
        pdf = PDF()
        pdf.add_page()
        pdf.set_font("Arial", size=11)
        pdf.cell(0, 10, f"Cliente: {limpiar_para_pdf(cliente)}", ln=True)
        pdf.cell(0, 10, f"Fecha: {datetime.now().strftime('%d/%m/%Y')}", ln=True)
        pdf.ln(5)
        
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(25, 10, "Codigo", 1); pdf.cell(95, 10, "Descripcion", 1); pdf.cell(20, 10, "Cant", 1); pdf.cell(30, 10, "Subtotal", 1); pdf.ln()
        
        pdf.set_font("Arial", size=9)
        for _, fila in df_cot.iterrows():
            pdf.cell(25, 8, limpiar_para_pdf(fila['codigo']), 1)
            pdf.cell(95, 8, limpiar_para_pdf(fila['descripcion'])[:50], 1)
            pdf.cell(20, 8, str(int(fila['cantidad'])), 1, 0, 'C')
            pdf.cell(30, 8, f"${fila['Subtotal']:,.2f}", 1, 0, 'R')
            pdf.ln()
            
        pdf.ln(5); pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 10, f"TOTAL: ${total:,.2f}  ", ln=True, align='R')
        
        pdf_out = pdf.output(dest='S').encode('latin-1')
        pdf_btn.download_button("📥 PDF", pdf_out, f"Pedido_{cliente}.pdf", "application/pdf", use_container_width=True)
    except:
        pdf_btn.error("Error al generar PDF")

    if clear.button("🗑️ Limpiar Todo", use_container_width=True):
        st.session_state.cotizacion = []
        st.rerun()
else:
    st.info("La cotización está vacía.")