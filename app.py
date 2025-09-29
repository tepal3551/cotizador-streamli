import streamlit as st
import pandas as pd
from datetime import datetime
from fpdf import FPDF

# ==============================================================================
# SECCIÓN 1: DEFINICIÓN DE TODAS LAS FUNCIONES Y CLASES
# (Todo alineado a la izquierda)
# ==============================================================================

@st.cache_data
def cargar_catalogo(nombre_archivo):
    catalogo = []
    try:
        with open(nombre_archivo, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    partes = line.strip().split(',')
                    if len(partes) < 3: continue
                    codigo = partes[0].strip()
                    precio = float(partes[-1].strip())
                    descripcion = ','.join(partes[1:-1]).strip()
                    catalogo.append({'codigo': codigo, 'descripcion': descripcion, 'precio': precio})
                except (ValueError, IndexError):
                    continue
    except FileNotFoundError:
        st.error(f"Error: No se encontró el archivo '{nombre_archivo}'.")
        return pd.DataFrame()
    df = pd.DataFrame(catalogo)
    if not df.empty:
        df['display'] = df['codigo'] + " - " + df['descripcion']
    return df

def agregar_producto_y_limpiar():
    producto_display = st.session_state.get("producto_selector")
    cantidad_seleccionada = st.session_state.get("cantidad_input", 1)
    if producto_display:
        producto_info = catalogo_df[catalogo_df['display'] == producto_display].iloc[0]
        if any(p['codigo'] == producto_info['codigo'] for p in st.session_state.cotizacion):
            st.warning("Este producto ya está en la cotización.")
        else:
            st.session_state.cotizacion.append({
                'codigo': producto_info['codigo'],
                'descripcion': producto_info['descripcion'],
                'cantidad': cantidad_seleccionada,
                'precio_unitario': producto_info['precio']
            })
            st.session_state.producto_selector = None
            st.session_state.cantidad_input = 1
    else:
        st.warning("Por favor, selecciona un producto.")

def actualizar_cantidad(index):
    nueva_cantidad = st.session_state[f"qty_{index}"]
    st.session_state.cotizacion[index]['cantidad'] = nueva_cantidad

        # --- REEMPLAZA TU CLASE PDF COMPLETA CON ESTA ---

# --- REEMPLAZA TU CLASE PDF COMPLETA CON ESTA ---

class PDF(FPDF):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.agente = ""

    def header(self):
        try:
            self.image("https://i.postimg.cc/HL8bS9xY/logo-empresa.jpg", 10, 8, 33)
            self.image("https://i.postimg.cc/c4DY0bt1/logo-marca.jpg", self.w - 43, 8, 33)
        except Exception:
            pass
        self.set_font('Arial', 'B', 15)
        self.cell(0, 10, 'Cotización de Pedidos', 0, 1, 'C')
        self.ln(20)

    def footer(self):
        self.set_y(-25)

        # 1. Establecemos la fuente a Negrita ('B') para el texto principal
        self.set_font('Arial', 'B', 8)

        # 2. Escribimos ambas líneas en negritas
        self.cell(0, 4, f"Atendido por: {self.agente}", align='L', ln=1)
        self.cell(0, 4, "La presente cotización es válida únicamente durante el mes y año de su emisión.", align='L', ln=1)

        # 3. Cambiamos la fuente a Itálica ('I') solo para el número de página
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Página {self.page_no()}', 0, 0, 'C')
def crear_pdf(cotizacion_df, cliente, agente): # <-- Se quita "vigencia" de aquí
    pdf = PDF(orientation='L')
    pdf.agente = agente # <-- Se pasa solo el agente
    pdf.add_page()
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 8, f'Cliente: {cliente}', 0, 1)
    pdf.cell(0, 8, f'Fecha: {datetime.now().strftime("%d/%m/%Y")}', 0, 1)
    # Ya no se escribe el agente ni la vigencia aquí
    pdf.ln(5)

    # ... (El resto del código para crear la tabla sigue exactamente igual) ...
    col_widths = {'codigo': 30, 'descripcion': 155, 'cantidad': 20, 'precio_unitario': 30, 'importe': 30}

    pdf.set_font('Arial', 'B', 10)
    pdf.set_fill_color(230, 230, 230)
    for col_name, width in col_widths.items():
        pdf.cell(width, 10, col_name.replace('_', ' ').title(), 1, 0, 'C', fill=True)
    pdf.ln()

    pdf.set_font('Arial', '', 9)
    row_height = 8 

    for _, row in cotizacion_df.iterrows():
        descripcion = row['descripcion']
        if len(descripcion) > 90:
            descripcion = descripcion[:87] + "..."

        pdf.cell(col_widths['codigo'], row_height, str(row['codigo']), 1, 0, 'C')
        pdf.cell(col_widths['descripcion'], row_height, descripcion, 1, 0, 'L')
        pdf.cell(col_widths['cantidad'], row_height, str(row['cantidad']), 1, 0, 'C')
        pdf.cell(col_widths['precio_unitario'], row_height, f"${row['precio_unitario']:,.2f}", 1, 0, 'R')
        pdf.cell(col_widths['importe'], row_height, f"${row['importe']:,.2f}", 1, 1, 'R')

    ancho_total_tabla = sum(col_widths.values())
    total = cotizacion_df['importe'].sum()
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(ancho_total_tabla - col_widths['importe'], 10, 'Total', 1, 0, 'R')
    pdf.cell(col_widths['importe'], 10, f"${total:,.2f}", 1, 1, 'R')

    return bytes(pdf.output())
# ==============================================================================
# SECCIÓN 2: LÓGICA PRINCIPAL DE LA APLICACIÓN
# ==============================================================================

# --- CONFIGURACIÓN E INICIALIZACIÓN ---
st.set_page_config(page_title="Cotizador de Pedidos Truper", page_icon="🔩", layout="wide")
NOMBRE_ARCHIVO_CATALOGO = "CATALAGO 25 TRUP PRUEBA COTIZADOR.txt"
catalogo_df = cargar_catalogo(NOMBRE_ARCHIVO_CATALOGO)

if 'cotizacion' not in st.session_state:
    st.session_state.cotizacion = []
if 'cliente' not in st.session_state:
    st.session_state.cliente = ""
if 'agente' not in st.session_state:
    st.session_state.agente = ""


# --- ENCABEZADO Y TÍTULO ---
col1, col_medio, col2 = st.columns([1, 3, 1])
with col1:
    st.image("https://i.postimg.cc/HL8bS9xY/logo-empresa.jpg", width=150)
with col2:
    st.image("https://i.postimg.cc/c4DY0bt1/logo-marca.jpg", width=150)
st.markdown("<h1 style='text-align: center;'>Cotizador de Pedidos Truper</h1>", unsafe_allow_html=True)
st.write("Crea y gestiona cotizaciones para enviar a tus clientes.")
st.markdown("---")

# --- ENTRADA DE DATOS GENERALES ---
# --- ENTRADA DE DATOS GENERALES (CORREGIDO) ---
st.session_state.cliente = st.text_input("📝 **Nombre del Cliente:**", st.session_state.cliente).upper()
st.session_state.agente = st.text_input("👤 **Atendido por (Agente):**", st.session_state.agente).upper()
st.markdown("---")

# --- AGREGAR PRODUCTOS A LA COTIZACIÓN ---
st.header("🔍 Agregar Productos a la Cotización")
if not catalogo_df.empty:
    col_prod, col_cant, col_btn = st.columns([4, 1, 1.5])
    with col_prod:
        st.selectbox('Busca y selecciona un producto:', options=catalogo_df['display'], index=None, placeholder="Escribe para buscar...", key="producto_selector")
    with col_cant:
        st.number_input('Cantidad:', min_value=1, value=1, step=1, key="cantidad_input")
    with col_btn:
        st.write("") 
        st.write("")
        st.button("➕ Agregar Producto", use_container_width=True, on_click=agregar_producto_y_limpiar)
else:
    st.warning("El catálogo está vacío o no se pudo cargar.")
st.markdown("---")

# --- VISTA DE LA COTIZACIÓN ACTUAL ---
st.header("📋 Cotización Actual")
if st.session_state.cotizacion:
    st.write(f"**Cliente:** {st.session_state.cliente}")
    cotizacion_actual_df = pd.DataFrame(st.session_state.cotizacion)
    cotizacion_actual_df['importe'] = cotizacion_actual_df['cantidad'] * cotizacion_actual_df['precio_unitario']

    col_headers = st.columns((2, 6, 2, 2, 2, 1.5))
    campos = ['Código', 'Descripción', 'Cant.', 'P. Unitario', 'Importe', 'Acción']
    for col, campo in zip(col_headers, campos):
        col.markdown(f"**{campo}**")
    st.markdown("---")

    for i in range(len(st.session_state.cotizacion)):
        producto = st.session_state.cotizacion[i]
        col_data = st.columns((2, 6, 2, 2, 2, 1.5))
        col_data[0].write(producto['codigo'])
        col_data[1].write(producto['descripcion'])
        col_data[2].number_input("Cantidad", min_value=1, value=producto['cantidad'], key=f"qty_{i}", on_change=actualizar_cantidad, args=(i,), label_visibility="collapsed")
        col_data[3].write(f"${producto['precio_unitario']:,.2f}")
        importe_fila = producto['cantidad'] * producto['precio_unitario']
        col_data[4].write(f"${importe_fila:,.2f}")
        if col_data[5].button("🗑️ Eliminar", key=f"del_{i}"):
            st.session_state.cotizacion.pop(i)
            st.rerun()

    total = cotizacion_actual_df['importe'].sum()
    st.subheader(f"Total: ${total:,.2f}")
    st.markdown("---")

    col_pdf, col_clear = st.columns(2)
    with col_pdf:
        # LÍNEA CORRECTA
        pdf_bytes = crear_pdf(cotizacion_actual_df, st.session_state.cliente, st.session_state.agente)
        st.download_button("📄 Descargar Cotización en PDF", data=pdf_bytes, file_name=f"cotizacion_{st.session_state.cliente.replace(' ', '_') or 'cliente'}.pdf", mime="application/octet-stream", use_container_width=True)
    with col_clear:
        if st.button("🗑️ Limpiar Cotización Completa", use_container_width=True, type="primary"):
            st.session_state.cotizacion = []
            st.session_state.cliente = ""
            st.rerun()

        with st.expander("✅ Exportar Cotización para Cliente"):
            fecha_actual = datetime.now().strftime('%d/%m/%Y')

            texto_exportar = f"*COTIZACIÓN*\n"
            texto_exportar += "======================================\n"
            texto_exportar += f"*Cliente:* {st.session_state.cliente}\n"
            texto_exportar += f"*Atendido por:* {st.session_state.agente}\n"
            texto_exportar += f"*Fecha:* {fecha_actual}\n"
            texto_exportar += "--------------------------------------\n"
            texto_exportar += "*Productos Solicitados:*\n"

            texto_productos = ""
            for _, row in cotizacion_actual_df.iterrows():
                # --- LÍNEA MODIFICADA ---
                # Añadimos el código del producto [{row['codigo']}]
                texto_productos += f"\n- ({row['cantidad']}x) [{row['codigo']}] *{row['descripcion']}*\n"
                texto_productos += f"  Importe: ${row['importe']:,.2f}"

            texto_exportar += texto_productos
            texto_exportar += "\n--------------------------------------\n"
            texto_exportar += f"*TOTAL: ${total:,.2f}*\n"
            texto_exportar += "======================================\n"
            texto_exportar += "*La presente cotización es válida únicamente durante el mes y año de su emisión.*"

            st.code(texto_exportar)
            st.info("Copia este texto y pégalo en WhatsApp. Las partes con *asteriscos* se verán en negritas.")
else:
    st.info("La cotización está vacía. Agrega productos para empezar.")