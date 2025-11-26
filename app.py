import streamlit as st
import pandas as pd
from datetime import datetime
from fpdf import FPDF
from urllib.parse import quote_plus 
import re # <-- ¡Añade esta línea si no la tienes!

# ==============================================================================
# SECCIÓN 1: DEFINICIÓN DE TODAS LAS FUNCIONES Y CLASES
# ==============================================================================

import re # ¡Asegúrate de importar la librería 're' (Regular Expressions) al inicio del script!

def analizar_y_cargar_pedido(texto_pedido, df_catalogo):
    """
    Analiza un bloque de texto (pedido) que contenga CÓDIGO y CANTIDAD 
    al inicio de cada línea, ignorando viñetas o asteriscos iniciales.
    
    Formato esperado: [Viñeta] CÓDIGO CANTIDAD DESCRIPCIÓN...
    """
    lineas = [line.strip() for line in texto_pedido.split('\n') if line.strip()]
    nuevos_productos = []
    
    catalogo_map = df_catalogo.set_index('codigo').to_dict('index') 
    productos_en_sesion = {p['codigo'] for p in st.session_state.cotizacion}

    for linea in lineas:
        # 1. Limpiamos viñetas iniciales y espacios
        # Esto elimina * , -, •, o cualquier viñeta unicode al inicio de la línea.
        linea_limpia = re.sub(r'^[*-•–\s]+', '', linea).strip()
        
        if not linea_limpia:
            continue
            
        partes = linea_limpia.split(maxsplit=2) # Separamos máximo 3 partes: [CÓDIGO], [CANTIDAD], [RESTO]
        
        # Debe tener al menos 2 partes para tener código y cantidad
        if len(partes) < 2:
            continue

        try:
            codigo_posible = partes[0]
            cantidad_posible = int(partes[1])
            
            if cantidad_posible <= 0:
                cantidad_posible = 1 
                
        except ValueError:
            # Si la segunda parte no es un número entero (la cantidad), pasamos
            continue
            
        # 2. Lógica de verificación y adición
        if codigo_posible in catalogo_map:
            if codigo_posible in productos_en_sesion:
                continue

            info = catalogo_map[codigo_posible]
            
            nuevos_productos.append({
                'codigo': codigo_posible,
                'descripcion': info['descripcion'],
                'cantidad': cantidad_posible,
                'precio_unitario': info['precio']
            })

    if nuevos_productos:
        st.session_state.cotizacion.extend(nuevos_productos)
        st.success(f"Se agregaron **{len(nuevos_productos)}** productos a la cotización.")
    else:
        st.warning("No se encontraron códigos válidos o no se pudo identificar el patrón `CÓDIGO CANTIDAD` al inicio de las líneas.")
def actualizar_cantidad(index):
    nueva_cantidad = st.session_state[f"qty_{index}"]
    st.session_state.cotizacion[index]['cantidad'] = nueva_cantidad

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
        self.set_font('Arial', 'B', 8)
        self.cell(0, 4, f"Atendido por: {self.agente}", align='L', ln=1)
        self.cell(0, 4, "La presente cotización es válida únicamente durante el mes y año de su emisión.", align='L', ln=1)
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Página {self.page_no()}', 0, 0, 'C')

def crear_pdf(cotizacion_df, cliente, agente): 
    pdf = PDF(orientation='L')
    pdf.agente = agente 
    pdf.add_page()
    pdf.set_font('Arial', 'B', 12)
    pdf.cell(0, 8, f'Cliente: {cliente}', 0, 1)
    pdf.cell(0, 8, f'Fecha: {datetime.now().strftime("%d/%m/%Y")}', 0, 1)
    pdf.ln(5)

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


def analizar_y_cargar_pedido(texto_pedido, df_catalogo):
    """
    Analiza un bloque de texto (pedido) adaptado al nuevo formato 
    '* CÓDIGO *CANTIDAD* DESCRIPCIÓN'.
    """
    lineas = [line.strip() for line in texto_pedido.split('\n') if line.strip()]
    nuevos_productos = []
    
    # Crea un mapeo rápido de código a información del producto (precio, descripción)
    catalogo_map = df_catalogo.set_index('codigo').to_dict('index') 
    productos_en_sesion = {p['codigo'] for p in st.session_state.cotizacion}

    for linea in lineas:
        # 1. Nos enfocamos solo en las líneas de detalle de producto
        if '* Detalle del Pedido:' in linea or '* Cliente:' in linea or not linea.startswith('*'):
            continue

        # 2. Partimos por el asterisco para obtener las partes
        partes = [p.strip() for p in linea.split('*') if p.strip()]
        
        # Debe haber al menos 3 partes relevantes: [CÓDIGO], [CANTIDAD], [DESCRIPCIÓN]
        if len(partes) < 3:
            continue

        try:
            # La primera parte DEBERÍA ser el código (ej: '44282')
            codigo_posible = partes[0]
            
            # La segunda parte DEBERÍA ser la cantidad (ej: '2')
            cantidad_posible = int(partes[1])
            
            if cantidad_posible <= 0:
                cantidad_posible = 1 
                
        except ValueError:
            continue
            
        # 3. Lógica de verificación y adición
        if codigo_posible in catalogo_map:
            if codigo_posible in productos_en_sesion:
                continue

            info = catalogo_map[codigo_posible]
            
            nuevos_productos.append({
                'codigo': codigo_posible,
                'descripcion': info['descripcion'],
                'cantidad': cantidad_posible,
                'precio_unitario': info['precio']
            })

    # Agregar los productos válidos a la sesión
    if nuevos_productos:
        st.session_state.cotizacion.extend(nuevos_productos)
        st.success(f"Se agregaron **{len(nuevos_productos)}** productos a la cotización.")
    else:
        st.warning("No se encontraron códigos de producto válidos o el formato no es el esperado en el texto proporcionado.")

def limpiar_area_texto():
    """Limpia el contenido del área de texto del pedido."""
    st.session_state.pedido_texto = "" # Implementación correcta


# ==============================================================================
# SECCIÓN 2: LÓGICA PRINCIPAL DE LA APLICACIÓN
# ==============================================================================

# --- CONFIGURACIÓN E INICIALIZACIÓN ---
st.set_page_config(page_title="Cotizador de Pedidos Truper", page_icon="🔩", layout="wide")
NOMBRE_ARCHIVO_CATALOGO = "CATALAGO 25 TRUP PRUEBA COTIZADOR.txt"
NOMBRE_ARCHIVO_ACTUALIZACIONES = "precios_actualizados.txt"
catalogo_df = cargar_catalogo(NOMBRE_ARCHIVO_CATALOGO, NOMBRE_ARCHIVO_ACTUALIZACIONES)

# Guardar el DataFrame en session_state para que 'agregar_producto_y_limpiar' lo pueda usar
st.session_state.catalogo_df = catalogo_df 

if 'cotizacion' not in st.session_state:
    st.session_state.cotizacion = []
if 'cliente' not in st.session_state:
    st.session_state.cliente = ""
if 'agente' not in st.session_state:
    st.session_state.agente = ""
if 'pedido_texto' not in st.session_state:
    st.session_state.pedido_texto = ""


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

# ==============================================================================
# 🆕 LÓGICA DE STREAMLIT PARA CARGAR PEDIDO POR TEXTO 🆕
# ==============================================================================
st.header("📝 Carga Rápida de Pedido por Texto")

with st.expander("▶️ Pegar y Cargar Pedido de Cliente"):
    st.markdown("Pega aquí el texto del pedido del cliente. **Formato esperado: `* CÓDIGO *CANTIDAD* DESCRIPCIÓN`**")
    st.code("* 44282 *5* CADENA DE PASEO...\n* 49212 *1* TERMOPAR...") # Ejemplo ilustrativo
    
    texto_pedido = st.text_area("Pega el pedido aquí:", height=150, key="pedido_texto", help="Copia el detalle del pedido directamente del formato que usas.")
    
    col_cargar, col_limpiar = st.columns([1, 1])
    con_texto = True if texto_pedido else False
    
    with col_cargar:
        if st.button("🚀 Procesar Pedido y Cargar", use_container_width=True, type="primary", disabled=not con_texto):
            if catalogo_df.empty:
                st.error("No se puede procesar: El catálogo está vacío.")
            else:
                analizar_y_cargar_pedido(texto_pedido, catalogo_df)
                st.rerun() 

    with col_limpiar:
        st.button("🧹 Limpiar Texto", use_container_width=True, on_click=limpiar_area_texto, disabled=not con_texto)

st.markdown("---")
# ==============================================================================

# --- VISTA DE LA COTIZACIÓN ACTUAL ---
st.header("📋 Cotización Actual")

if st.session_state.cotizacion:
    # --- INICIO DEL BLOQUE DONDE TODO DEBE ESTAR ---
    
    st.write(f"**Cliente:** {st.session_state.cliente}")
    
    # 1. Se crea el DataFrame
    cotizacion_actual_df = pd.DataFrame(st.session_state.cotizacion)
    cotizacion_actual_df['importe'] = cotizacion_actual_df['cantidad'] * cotizacion_actual_df['precio_unitario']

    # 2. Se muestra la tabla
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

    # 3. Se calcula y muestra el total
    total = cotizacion_actual_df['importe'].sum()
    st.subheader(f"Total: ${total:,.2f}")
    st.markdown("---")

    # 4. AHORA SE MUESTRAN LAS ACCIONES (DENTRO DEL 'IF')
    st.subheader("Acciones Finales")
    col_pdf, col_whatsapp, col_clear = st.columns(3)

    with col_pdf:
        pdf_bytes = crear_pdf(cotizacion_actual_df, st.session_state.cliente, st.session_state.agente)
        st.download_button("📄 Descargar PDF", data=pdf_bytes, file_name=f"COTIZACION_{st.session_state.cliente.replace(' ', '_') or 'cliente'}.pdf", mime="application/octet-stream", use_container_width=True)

    with col_whatsapp:
        # Generar un mensaje de WhatsApp que incluya parte del detalle (opcional)
        # Por simplicidad, se usa solo el mensaje inicial, el PDF es el importante.
        mensaje_whatsapp = quote_plus(f"Hola {st.session_state.cliente}, te comparto la cotización solicitada por un total de ${total:,.2f}.")
        whatsapp_url = f"https://wa.me/?text={mensaje_whatsapp}"
        st.link_button("📲 Compartir en WhatsApp", url=whatsapp_url, use_container_width=True)

    with col_clear:
        if st.button("🗑️ Limpiar Cotización", use_container_width=True, type="primary"):
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
            texto_productos += f"\n- ({row['cantidad']}x) [{row['codigo']}] *{row['descripcion']}*\n"
            texto_productos += f"  Importe: ${row['importe']:,.2f}"
        texto_exportar += texto_productos
        texto_exportar += "\n--------------------------------------\n"
        texto_exportar += f"*TOTAL: ${total:,.2f}*\n"
        texto_exportar += "======================================\n"
        texto_exportar += "*La presente cotización es válida únicamente durante el mes y año de su emisión.*"
        st.code(texto_exportar)
    
    # --- FIN DEL BLOQUE DONDE TODO DEBE ESTAR ---

else:
    st.info("La cotización está vacía. Agrega productos para empezar.")