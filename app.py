import streamlit as st
import pandas as pd
import re
from urllib.parse import quote_plus

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
        st.error(f"No se encontró el archivo: {nombre_archivo_catalogo}")
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

def analizar_y_cargar_pedido(texto_pedido, df_catalogo):
    """Lógica para detectar CÓDIGO y CANTIDAD ignorando símbolos."""
    lineas = [line.strip() for line in texto_pedido.split('\n') if line.strip()]
    nuevos_productos = []
    catalogo_map = df_catalogo.set_index('codigo').to_dict('index') 
    
    # Patrón: Busca el código (4-6 dígitos) y la cantidad
    PATRON = re.compile(r'[^\d]*(\d{4,6})[^\d]+(\d{1,3})')

    for linea in lineas:
        match = PATRON.search(linea)
        if match:
            cod = match.group(1)
            cant = int(match.group(2))
            if cod in catalogo_map:
                p_base = float(catalogo_map[cod]['precio'])
                # Lógica: Precio Dimefet es el base / 0.90
                precio_final = p_base if st.session_state.tipo_lista == "Distribuidor" else p_base / 0.90
                
                nuevos_productos.append({
                    'codigo': cod,
                    'descripcion': catalogo_map[cod]['descripcion'],
                    'cantidad': cant,
                    'precio_unitario': precio_final
                })
    
    if nuevos_productos:
        st.session_state.cotizacion.extend(nuevos_productos)
        st.success(f"Se cargaron {len(nuevos_productos)} productos.")
    else:
        st.warning("No se reconoció el formato. Asegúrate de poner: Código Cantidad")

def agregar_producto_manual():
    if st.session_state.prod_sel:
        info = st.session_state.catalogo_df[st.session_state.catalogo_df['display'] == st.session_state.prod_sel].iloc[0]
        p_base = float(info['precio'])
        precio_final = p_base if st.session_state.tipo_lista == "Distribuidor" else p_base / 0.90
        
        st.session_state.cotizacion.append({
            'codigo': info['codigo'],
            'descripcion': info['descripcion'],
            'cantidad': st.session_state.cant_sel,
            'precio_unitario': precio_final
        })

# ==============================================================================
# SECCIÓN 2: INTERFAZ DE USUARIO
# ==============================================================================

st.set_page_config(page_title="Cotizador Truper", layout="wide")

if 'cotizacion' not in st.session_state: st.session_state.cotizacion = []
if 'tipo_lista' not in st.session_state: st.session_state.tipo_lista = "Distribuidor"

catalogo_df = cargar_catalogo("CATALAGO 25 TRUP PRUEBA COTIZADOR.txt", "precios_actualizados.txt")
st.session_state.catalogo_df = catalogo_df

st.title("🔩 Cotizador de Hardware y Eléctricos")

# --- PANEL DE CONFIGURACIÓN ---
col_cfg1, col_cfg2 = st.columns(2)
with col_cfg1:
    cliente_input = st.text_input("Cliente:", placeholder="Ej: TOME GARCIA MARIA MAGDALENA").upper()
    tipo_doc = st.text_input("Tipo de Documento:", value="Remisión")
with col_cfg2:
    st.session_state.tipo_lista = st.radio("Selecciona Lista de Precios:", ["Distribuidor", "Dimefet"], horizontal=True)
    st.caption("Nota: 'Dimefet' aumenta el precio para permitir un descuento posterior del 10%.")

# --- ENTRADA DE PRODUCTOS ---
with st.expander("🔍 Búsqueda Manual"):
    c1, c2, c3 = st.columns([4,1,1])
    c1.selectbox("Producto:", catalogo_df['display'], key="prod_sel")
    c2.number_input("Cant:", min_value=1, value=1, key="cant_sel")
    c3.button("➕ Añadir", on_click=agregar_producto_manual)

with st.expander("🚀 Carga Rápida (Pegar pedido)"):
    texto = st.text_area("Pega aquí (Ej: 44282 2)", help="Formato sugerido: Código Cantidad")
    if st.button("Procesar Texto"):
        analizar_y_cargar_pedido(texto, catalogo_df)
        st.rerun()

# --- TABLA Y ENVÍO ---
if st.session_state.cotizacion:
    df_cot = pd.DataFrame(st.session_state.cotizacion)
    df_cot['Subtotal'] = df_cot['cantidad'] * df_cot['precio_unitario']
    
    st.table(df_cot.style.format({'precio_unitario': '${:,.2f}', 'Subtotal': '${:,.2f}'}))
    
    total = df_cot['Subtotal'].sum()
    st.subheader(f"Total Cotizado ({st.session_state.tipo_lista}): ${total:,.2f}")

    # --- GENERACIÓN DE MENSAJE WHATSAPP (CORREGIDO) ---
    # Usamos saltos de línea exactos para el formato solicitado
    mensaje = (
        f"Nuevo Pedido\n\n"
        f"Cliente: {cliente_input}\n"
        f"Tipo de Documento: {tipo_doc}\n\n"
        f"Detalle del Pedido:\n\n"
    )
    
    for _, fila in df_cot.iterrows():
        # Formato: * CODIGO CANTIDAD DESCRIPCION (Texto Simple)
        mensaje += f"* {fila['codigo']} {int(fila['cantidad'])} {fila['descripcion']}\n"
    
    # Codificar para URL
    wa_url = f"https://wa.me/?text={quote_plus(mensaje)}"
    
    st.link_button("📲 Enviar a WhatsApp", wa_url)
    
    c_btn1, c_btn2 = st.columns(2)
    c_btn1.link_button("📲 Enviar a WhatsApp", wa_url, use_container_width=True)
    if c_btn2.button("🗑️ Limpiar Todo", use_container_width=True):
        st.session_state.cotizacion = []
        st.rerun()
else:
    st.info("La cotización está vacía. Agregue productos para comenzar.")