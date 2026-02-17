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

class PDF(FPDF):
    def header(self):
        try:
            # Usamos las URLs directas que proporcionaste antes
            self.image("https://i.postimg.cc/HL8bS9xY/logo-empresa.jpg", 10, 8, 33)
            self.image("https://i.postimg.cc/c4DY0bt1/logo-marca.jpg", 165, 8, 33)
        except:
            pass
        self.set_font('Arial', 'B', 15)
        self.ln(10)
        self.cell(0, 10, 'Cotización de Pedidos', 0, 1, 'C')
        self.ln(10)

def generar_pdf(df, cliente, tipo_doc, lista, total):
    pdf = PDF()
    pdf.add_page()
    
    # Función para limpiar texto y evitar errores de codificación en el PDF
    def limpiar(t):
        return str(t).encode('latin-1', 'replace').decode('latin-1')

    pdf.set_font("Arial", size=12)
    pdf.cell(0, 10, txt=f"Cliente: {limpiar(cliente)}", ln=True)
    pdf.cell(0, 10, txt=f"Tipo: {limpiar(tipo_doc)}", ln=True)
    pdf.cell(0, 10, txt=f"Lista: {limpiar(lista)}", ln=True)
    pdf.cell(0, 10, txt=f"Fecha: {datetime.now().strftime('%d/%m/%Y')}", ln=True)
    pdf.ln(5)
    
    # Encabezados
    pdf.set_font("Arial", 'B', 10)
    pdf.set_fill_color(240, 240, 240)
    pdf.cell(25, 10, "Codigo", 1, 0, 'C', True)
    pdf.cell(85, 10, "Descripcion", 1, 0, 'C', True)
    pdf.cell(20, 10, "Cant.", 1, 0, 'C', True)
    pdf.cell(30, 10, "P. Unit", 1, 0, 'C', True)
    pdf.cell(30, 10, "Subt.", 1, 0, 'C', True)
    pdf.ln()
    
    pdf.set_font("Arial", size=9)
    for _, row in df.iterrows():
        pdf.cell(25, 8, limpiar(row['codigo']), 1)
        pdf.cell(85, 8, limpiar(row['descripcion'])[:45], 1)
        pdf.cell(20, 8, str(int(row['cantidad'])), 1, 0, 'C')
        pdf.cell(30, 8, f"${row['precio_unitario']:,.2f}", 1, 0, 'R')
        pdf.cell(30, 8, f"${row['Subtotal']:,.2f}", 1, 0, 'R')
        pdf.ln()
        
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, txt=f"TOTAL: ${total:,.2f}  ", ln=True, align='R')
    return pdf.output(dest='S').encode('latin-1')

# ... (Funciones analizar_y_cargar_pedido y agregar_producto_manual siguen igual)

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

# Título y Logos (Cargados por URL para evitar errores de archivo)
col1, col2, col3 = st.columns([1,3,1])
with col1:
    st.image("https://i.postimg.cc/HL8bS9xY/logo-empresa.jpg", width=120)
with col2:
    st.markdown("<h1 style='text-align: center;'>Cotizador Truper</h1>", unsafe_allow_html=True)
with col3:
    st.image("https://i.postimg.cc/c4DY0bt1/logo-marca.jpg", width=120)

catalogo_df = cargar_catalogo("CATALAGO 25 TRUP PRUEBA COTIZADOR.txt", "precios_actualizados.txt")
st.session_state.catalogo_df = catalogo_df

# Interfaz de usuario
c1, c2 = st.columns(2)
with c1:
    cliente = st.text_input("Cliente:").upper()
    tipo_doc = st.text_input("Documento:", value="Remisión")
with c2:
    st.session_state.tipo_lista = st.radio("Precios:", ["Distribuidor", "Dimefet"], horizontal=True)

with st.expander("🔍 Añadir"):
    ca, cb, cc = st.columns([4,1,1])
    ca.selectbox("Producto:", catalogo_df['display'] if not catalogo_df.empty else [], key="prod_sel")
    cb.number_input("Cant:", min_value=1, key="cant_sel")
    cc.button("➕", on_click=agregar_producto_manual)

with st.expander("🚀 Carga Rápida"):
    texto = st.text_area("Pega aquí")
    if st.button("Procesar"):
        analizar_y_cargar_pedido(texto, catalogo_df)
        st.rerun()

if st.session_state.cotizacion:
    df_cot = pd.DataFrame(st.session_state.cotizacion)
    df_cot['Subtotal'] = df_cot['cantidad'] * df_cot['precio_unitario']
    st.table(df_cot.style.format({'precio_unitario': '${:,.2f}', 'Subtotal': '${:,.2f}'}))
    
    total = df_cot['Subtotal'].sum()
    st.subheader(f"Total: ${total:,.2f}")

    # WhatsApp
    mensaje = f"Nuevo Pedido\n\nCliente: {cliente}\nTipo de Documento: {tipo_doc}\n\nDetalle del Pedido:\n\n"
    for _, fila in df_cot.iterrows():
        mensaje += f"* {fila['codigo']} {int(fila['cantidad'])} {fila['descripcion']}\n"
    wa_url = f"https://wa.me/?text={quote_plus(mensaje)}"
    
    a, b, c = st.columns(3)
    a.link_button("📲 WhatsApp", wa_url, use_container_width=True)
    
    # Generar PDF con manejo de errores interno
    try:
        pdf_data = generar_pdf(df_cot, cliente, tipo_doc, st.session_state.tipo_lista, total)
        b.download_button("📥 PDF", pdf_data, f"Cotizacion_{cliente}.pdf", "application/pdf", use_container_width=True)
    except Exception as e:
        b.error("Error PDF")
        
    if c.button("🗑️ Limpiar", use_container_width=True):
        st.session_state.cotizacion = []
        st.rerun()