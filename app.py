import streamlit as st
import pandas as pd
from datetime import datetime
from fpdf import FPDF
from urllib.parse import quote_plus 
import re # ¡Ahora solo una vez y al inicio!

# ==============================================================================
# SECCIÓN 1: DEFINICIÓN DE TODAS LAS FUNCIONES Y CLASES
# ==============================================================================

@st.cache_data
def cargar_catalogo(nombre_archivo_catalogo, nombre_archivo_actualizaciones):
    """
    Carga el catálogo de productos y luego aplica las actualizaciones de precios
    y descripción, o agrega nuevos productos desde un archivo separado.
    """
    catalogo = []
    try:
        # Paso 1: Cargar el catálogo completo
        with open(nombre_archivo_catalogo, 'r', encoding='utf-8') as f:
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
        st.error(f"Error: No se encontró el archivo de catálogo '{nombre_archivo_catalogo}'.")
        return pd.DataFrame()

    df = pd.DataFrame(catalogo)
    if df.empty:
        df = pd.DataFrame(columns=['codigo', 'descripcion', 'precio'])

    df = df.set_index('codigo')

    # Paso 2: Cargar y aplicar actualizaciones o AGREGAR nuevos productos
    try:
        with open(nombre_archivo_actualizaciones, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    partes = line.strip().split(',')
                    if len(partes) < 3: continue 

                    codigo = partes[0].strip()
                    nuevo_precio = float(partes[-1].strip())
                    nueva_descripcion = ','.join(partes[1:-1]).strip()
                    
                    if codigo in df.index:
                        df.at[codigo, 'precio'] = nuevo_precio
                        df.at[codigo, 'descripcion'] = nueva_descripcion
                    else:
                        df.loc[codigo] = {
                            'descripcion': nueva_descripcion, 
                            'precio': nuevo_precio
                        }
                except (ValueError, IndexError):
                    continue
    except FileNotFoundError:
        pass

    df = df.reset_index()
    if not df.empty:
        df['display'] = df['codigo'] + " - " + df['descripcion']
    return df

# --- FUNCIÓN DE ANALISIS DE PEDIDO (VERSION FLEXIBLE) ---
# --- REEMPLAZAR LA FUNCIÓN ANALIZAR_Y_CARGAR_PEDIDO CON ESTA VERSIÓN FLEXIBLE ---

import re # Asegúrate de que 'import re' esté al inicio del script

# --- REEMPLAZAR LA FUNCIÓN ANALIZAR_Y_CARGAR_PEDIDO COMPLETA CON ESTA VERSIÓN ---

import re # Asegúrate de que 'import re' esté al inicio del script

def analizar_y_cargar_pedido(texto_pedido, df_catalogo):
    """
    Analiza un bloque de texto buscando el patrón numérico CÓDIGO y CANTIDAD 
    siendo totalmente tolerante a viñetas, asteriscos y espacios intermedios.
    """
    lineas = [line.strip() for line in texto_pedido.split('\n') if line.strip()]
    nuevos_productos = []
    diagnostico_fallos = [] 
    
    catalogo_map = df_catalogo.set_index('codigo').to_dict('index') 
    productos_en_sesion = {p['codigo'] for p in st.session_state.cotizacion}

    # Patrón RegEx: Busca al inicio de la línea:
    # 1. Caracteres no numéricos opcionales (viñeta, *)
    # 2. El CÓDIGO (un grupo de 4 a 6 dígitos consecutivos) -> Grupo 1
    # 3. Caracteres no numéricos opcionales (espacio, *)
    # 4. La CANTIDAD (un grupo de 1 a 3 dígitos consecutivos) -> Grupo 2
    PATRON_PEDIDO = re.compile(r'^[^\d]*(\d{4,6})[^\d]*(\d{1,3})')

    for linea in lineas:
        
        # Ignoramos líneas que son encabezados o texto largo sin patrón numérico al inicio
        if 'DETALLE DEL PEDIDO' in linea.upper() or len(linea.split()) < 2:
            continue
            
        codigo_posible = None
        cantidad_posible = 0

        # Buscamos el patrón en la línea
        match = PATRON_PEDIDO.match(linea)

        if match:
            try:
                # El grupo 1 es el CÓDIGO, el grupo 2 es la CANTIDAD
                codigo_posible = match.group(1).strip()
                cantidad_posible = int(match.group(2))
                
                if cantidad_posible <= 0:
                    cantidad_posible = 1
            except Exception:
                # Si falla la conversión a entero, seguimos.
                pass 

        # 2. Verificación de Catálogo
        if codigo_posible and codigo_posible in catalogo_map:
            if codigo_posible in productos_en_sesion:
                continue

            info = catalogo_map[codigo_posible]
            
            nuevos_productos.append({
                'codigo': codigo_posible,
                'descripcion': info['descripcion'],
                'cantidad': cantidad_posible,
                'precio_unitario': info['precio']
            })
            
        else:
            # DIAGNÓSTICO: Si se extrajo un código pero no está en el catálogo, lo guardamos.
            if codigo_posible and cantidad_posible > 0:
                diagnostico_fallos.append(f"Cód. no enc.: '{codigo_posible}' (Cant: {cantidad_posible}) Línea: {linea.strip()}")


    # 3. Presentación de Resultados y Fallos
    if nuevos_productos:
        st.session_state.cotizacion.extend(nuevos_productos)
        st.success(f"Se agregaron **{len(nuevos_productos)}** productos a la cotización.")
    else:
        # Solo mostramos la advertencia general si no hay códigos que coincidan con el patrón
        if not diagnostico_fallos:
             st.warning("No se encontraron productos válidos. Verifique el formato CÓDIGO CANTIDAD.")
        
    if diagnostico_fallos:
        st.error("❌ Fallos de Coincidencia de Catálogo (Verifique si estos códigos existen en su archivo):")
        st.code('\n'.join(diagnostico_fallos))

# --- FIN DE LA FUNCIÓN DE ANALISIS DE PEDIDO ---
def agregar_producto_y_limpiar():
    producto_display = st.session_state.get("producto_selector")
    cantidad_seleccionada = st.session_state.get("cantidad_input", 1)
    if producto_display:
        producto_info = st.session_state.catalogo_df[st.session_state.catalogo_df['display'] == producto_display].iloc[0]
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

def limpiar_area_texto():
    """Limpia el contenido del área de texto del pedido."""
    st.session_state.pedido_texto = "" # Implementación correcta


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


# ==============================================================================
# SECCIÓN 2: LÓGICA PRINCIPAL DE LA APLICACIÓN
# ==============================================================================

# --- CONFIGURACIÓN E INICIALIZACIÓN ---
st.set_page_config(page_title="Cotizador de Pedidos Truper", page_icon="🔩", layout="wide")
NOMBRE_ARCHIVO_CATALOGO = "CATALAGO 25 TRUP PRUEBA COTIZADOR.txt"
NOMBRE_ARCHIVO_ACTUALIZACIONES = "precios_actualizados.txt"

# ESTA ES LA LÍNEA 218 DONDE OCURRÍA EL ERROR. Ahora que cargar_catalogo está definida, funcionará.
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
    st.markdown("Pega aquí el texto del pedido. **Formato esperado: `[Viñeta/Espacio] CÓDIGO CANTIDAD DESCRIPCIÓN`**")
    st.code("* 44282 5 CADENA DE PASEO...\n- 49212 1 TERMOPAR...") 
    
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