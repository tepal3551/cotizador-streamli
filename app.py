import streamlit as st
import pandas as pd
from datetime import datetime
from fpdf import FPDF
from urllib.parse import quote_plus
import re
import os
import json
import requests

# ==============================================================================
# SECCIÓN 1: DEFINICIÓN DE FUNCIONES
# ==============================================================================

def limpiar_nombre_archivo(nombre):
    """Convierte el nombre del cliente en un nombre de archivo seguro."""
    reemplazos = {
        'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u',
        'Á': 'A', 'É': 'E', 'Í': 'I', 'Ó': 'O', 'Ú': 'U',
        'ñ': 'n', 'Ñ': 'N', 'ü': 'u', 'Ü': 'U'
    }
    for k, v in reemplazos.items():
        nombre = nombre.replace(k, v)

    nombre = re.sub(r'[<>:"/\\|?*,\.]', '', nombre)
    nombre = '_'.join(nombre.split())

    return nombre[:50] if nombre else "MOSTRADOR"


@st.cache_data
def cargar_catalogo(nombre_archivo_catalogo, nombre_archivo_actualizaciones):
    catalogo = []
    try:
        with open(nombre_archivo_catalogo, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    partes = line.strip().split(',')
                    if len(partes) < 3:
                        continue
                    codigo = partes[0].strip()
                    precio = float(partes[-1].strip())
                    descripcion = ','.join(partes[1:-1]).strip()
                    catalogo.append({'codigo': codigo, 'descripcion': descripcion, 'precio': precio})
                except (ValueError, IndexError):
                    continue
    except FileNotFoundError:
        return pd.DataFrame()

    df = pd.DataFrame(catalogo)
    if df.empty:
        return pd.DataFrame(columns=['codigo', 'descripcion', 'precio'])
    df = df.set_index('codigo')

    try:
        with open(nombre_archivo_actualizaciones, 'r', encoding='utf-8') as f:
            for line in f:
                try:
                    partes = line.strip().split(',')
                    if len(partes) < 3:
                        continue
                    codigo = partes[0].strip()
                    nuevo_precio = float(partes[-1].strip())
                    nueva_descripcion = ','.join(partes[1:-1]).strip()
                    df.loc[codigo] = {'descripcion': nueva_descripcion, 'precio': nuevo_precio}
                except Exception:
                    continue
    except FileNotFoundError:
        pass

    df = df.reset_index()
    df['display'] = df['codigo'] + " - " + df['descripcion']
    return df


URL_CLIENTES_SHEET = "https://docs.google.com/spreadsheets/d/e/2PACX-1vTxPh4_poWxwC63UWWeczmFn-iAItg6UYnrZjtzBHcz-7SRs550_0pqwRHS8LCvu3PYe7oLgmn1IKoz/pub?gid=0&single=true&output=csv"


@st.cache_data(ttl=600)
def cargar_clientes(nombre_archivo_clientes):
    # 1) Intenta leer desde Google Sheets
    try:
        df = pd.read_csv(URL_CLIENTES_SHEET, dtype=str).fillna("")
        # Limpia encabezados: quita espacios sobrantes y pasa a minúsculas
        df.columns = [str(c).strip().lower() for c in df.columns]
        df = df.rename(columns={
            'id vendedor': 'cve_age',
            'nombre vendedor': 'nombre_vend',
            'id cliente': 'cve',
            'nombre cliente': 'nombre'
        })
        if 'nombre_vend' not in df.columns:
            df['nombre_vend'] = ""
        df = df[df['cve'].str.strip() != ""]
        df['cve'] = df['cve'].str.strip()
        df['cve_age'] = df['cve_age'].str.strip()
        df['nombre'] = df['nombre'].str.strip()
        df['nombre_vend'] = df['nombre_vend'].str.strip()
        df['display'] = df['cve'] + " - " + df['nombre'] + " (Vend: " + df['cve_age'] + ")"
        return df[['cve', 'cve_age', 'nombre', 'nombre_vend', 'display']]
    except Exception as e:
        st.error(f"Error leyendo Sheet: {e}")

    # 2) Respaldo: archivo local si el Sheet falla
    clientes = []
    try:
        with open(nombre_archivo_clientes, 'r', encoding='utf-8') as f:
            for line in f:
                partes = line.strip().split(',', 2)
                if len(partes) >= 3:
                    cve = partes[0].strip()
                    cve_age = partes[1].strip()
                    nombre = partes[2].strip()
                    display = f"{cve} - {nombre} (Vend: {cve_age})"
                    clientes.append({'cve': cve, 'cve_age': cve_age, 'nombre': nombre,
                                     'nombre_vend': '', 'display': display})
    except FileNotFoundError:
        return pd.DataFrame()
    return pd.DataFrame(clientes)


def crear_pedido_render(nombre_cliente, id_vendedor, id_cliente, cotizacion):
    url = "https://servidor-pedidos.onrender.com/api/crear-pedido"

    # 1. Traducimos los datos de Python al formato exacto que pide Node.js
    productos_formateados = []
    for item in cotizacion:
        productos_formateados.append({
            "key": item["codigo"],         # server.js busca 'key'
            "quantity": item["cantidad"],  # server.js busca 'quantity'
            "cve_suc": "PED",
            "cve_mon": 1,
            "lugar": "A2"                  # Forzando almacén A2 por defecto
        })

    # 2. Armamos el paquete de envío
    payload = {
        "clientName": nombre_cliente,
        "agentId": id_vendedor,
        "clientId": id_cliente,
        "products": productos_formateados
    }

    # 3. Enviamos la orden de crear pedido al servidor
    try:
        respuesta = requests.post(url, json=payload, timeout=30)

        if respuesta.status_code == 201:
            datos = respuesta.json()
            return datos["folio"]
        else:
            st.error(f"⚠️ El servidor rechazó el pedido: {respuesta.text}")
            return None

    except Exception as e:
        st.error(f"🔍 Problema de comunicación con Render: {e}")
        return None


def generar_pdf(df, cliente, tipo_doc, lista, total):
    pdf = FPDF()
    pdf.add_page()

    if os.path.exists("logo_tepalcates.png"):
        pdf.image("logo_tepalcates.png", x=10, y=8, w=35)

    if os.path.exists("logo_truper_completo.png"):
        pdf.image("logo_truper_completo.png", x=165, y=8, w=35)

    pdf.set_font("Arial", 'B', 16)
    pdf.cell(200, 10, txt="Cotización", ln=True, align='C')

    pdf.ln(15)

    pdf.set_font("Arial", size=12)
    pdf.cell(200, 8, txt=f"Cliente: {cliente}", ln=True)
    pdf.cell(200, 8, txt=f"Tipo: {tipo_doc}", ln=True)
    pdf.cell(200, 8, txt=f"Lista: {lista}", ln=True)
    pdf.cell(200, 8, txt=f"Fecha: {datetime.now().strftime('%d/%m/%Y')}", ln=True)
    pdf.ln(10)

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

    pdf.ln(10)
    pdf.set_font("Arial", 'I', 10)
    pdf.cell(200, 10, txt="Válida únicamente durante el mes de emisión de este documento.", ln=True, align='C')

    try:
        return bytes(pdf.output())
    except TypeError:
        return pdf.output(dest='S').encode('latin-1')
    except AttributeError:
        return pdf.output()


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
                nuevos_productos.append({
                    'codigo': cod,
                    'descripcion': catalogo_map[cod]['descripcion'],
                    'cantidad': cant,
                    'precio_base': p_base
                })
    if nuevos_productos:
        st.session_state.cotizacion.extend(nuevos_productos)
        if 'folio_generado' in st.session_state:
            del st.session_state.folio_generado


def agregar_producto_manual():
    if st.session_state.prod_sel:
        info = st.session_state.catalogo_df[st.session_state.catalogo_df['display'] == st.session_state.prod_sel].iloc[0]
        p_base = float(info['precio'])
        st.session_state.cotizacion.append({
            'codigo': info['codigo'],
            'descripcion': info['descripcion'],
            'cantidad': st.session_state.cant_sel,
            'precio_base': p_base
        })
        st.session_state.prod_sel = None
        st.session_state.cant_sel = 1
        if 'folio_generado' in st.session_state:
            del st.session_state.folio_generado


ARCHIVO_HISTORIAL = "historial_cotizaciones.json"


def leer_historial():
    if os.path.exists(ARCHIVO_HISTORIAL):
        with open(ARCHIVO_HISTORIAL, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {}
    return {}


def guardar_cotizacion(cliente_display, tipo_doc, tipo_lista, total):
    historial = leer_historial()

    if st.session_state.editando_id:
        cot_id = st.session_state.editando_id
        fecha_registro = historial[cot_id]['fecha']
    else:
        cot_id = datetime.now().strftime("%Y%m%d%H%M%S")
        fecha_registro = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    historial[cot_id] = {
        "id": cot_id,
        "fecha": fecha_registro,
        "cliente": cliente_display if cliente_display else "MOSTRADOR",
        "tipo_doc": tipo_doc,
        "lista_precios": tipo_lista,
        "total": round(total, 2),
        "productos": st.session_state.cotizacion
    }

    with open(ARCHIVO_HISTORIAL, 'w', encoding='utf-8') as f:
        json.dump(historial, f, indent=4)

    st.session_state.editando_id = None
    st.session_state.cotizacion = []
    st.session_state.cliente_seleccionado = None
    st.session_state.vendedor_input = ""
    st.session_state.tipo_doc_input = "Remisión"
    if 'folio_generado' in st.session_state:
        del st.session_state.folio_generado


# ==============================================================================
# SECCIÓN 2: INTERFAZ
# ==============================================================================

st.set_page_config(page_title="Cotizador Truper", layout="wide")

# --- CSS PARA MARCA DE AGUA ---
page_bg_img = """
<style>
[data-testid="stAppViewContainer"] {
    background-image: url("https://raw.githubusercontent.com/tu-usuario/tu-repositorio/main/logo_truper_fondo.png");
    background-size: contain;
    background-position: center;
    background-repeat: no-repeat;
    background-attachment: fixed;
    background-blend-mode: lighten;
    background-color: rgba(255, 255, 255, 0.95);
}
</style>
"""
st.markdown(page_bg_img, unsafe_allow_html=True)

if 'cotizacion' not in st.session_state:
    st.session_state.cotizacion = []
if 'tipo_lista' not in st.session_state:
    st.session_state.tipo_lista = "Distribuidor"
if 'editando_id' not in st.session_state:
    st.session_state.editando_id = None
if 'cliente_seleccionado' not in st.session_state:
    st.session_state.cliente_seleccionado = None
if 'vendedor_input' not in st.session_state:
    st.session_state.vendedor_input = ""
if 'tipo_doc_input' not in st.session_state:
    st.session_state.tipo_doc_input = "Remisión"

# --- LOGOS EN LA PANTALLA PRINCIPAL ---
col_logo1, col_titulo, col_logo2 = st.columns([1, 4, 1.5])

with col_logo1:
    if os.path.exists("logo_tepalcates.png"):
        st.image("logo_tepalcates.png", use_container_width=True)

with col_titulo:
    titulo_texto = "Cotizador Truper"
    if st.session_state.editando_id:
        titulo_texto += " ✏️ (Modo Edición)"
    st.markdown(f"<h1 style='text-align: center;'>{titulo_texto}</h1>", unsafe_allow_html=True)

with col_logo2:
    if os.path.exists("logo_truper_completo.png"):
        st.image("logo_truper_completo.png", use_container_width=True)

catalogo_df = cargar_catalogo("CATALAGO 25 TRUP PRUEBA COTIZADOR.txt", "precios_actualizados.txt")
st.session_state.catalogo_df = catalogo_df

clientes_df = cargar_clientes("clientes.txt")
st.session_state.clientes_df = clientes_df

st.write("### Datos Generales")
c_cfg1, c_cfg2, c_cfg3 = st.columns(3)

with c_cfg1:
    vendedor = st.text_input("Clave Vendedor (Sirve de Filtro):", value=st.session_state.vendedor_input)
    st.session_state.vendedor_input = vendedor

    opciones_clientes = []
    if not clientes_df.empty:
        if vendedor:
            df_filtrado = clientes_df[clientes_df['cve_age'] == str(vendedor).strip()]
            opciones_clientes = df_filtrado['display'].tolist()
        else:
            opciones_clientes = clientes_df['display'].tolist()

    index_cliente = None
    if st.session_state.cliente_seleccionado in opciones_clientes:
        index_cliente = opciones_clientes.index(st.session_state.cliente_seleccionado)

    cliente_seleccionado = st.selectbox(
        "Seleccione Cliente:",
        options=opciones_clientes,
        index=index_cliente,
        placeholder="Teclee nombre o clave..."
    )
    st.session_state.cliente_seleccionado = cliente_seleccionado

with c_cfg2:
    tipo_doc = st.text_input("Tipo de Documento:", value=st.session_state.tipo_doc_input)
    st.session_state.tipo_doc_input = tipo_doc

    no_ped_manual = st.text_input("No. Pedido (Dejar vacío para autogenerar):", value="")

    observaciones = st.text_input("Observaciones:", value="")

with c_cfg3:
    opciones_lista = ["Distribuidor", "Dimefet"]
    idx_lista = opciones_lista.index(st.session_state.tipo_lista) if st.session_state.tipo_lista in opciones_lista else 0
    st.session_state.tipo_lista = st.radio("Lista de Precios:", opciones_lista, index=idx_lista, horizontal=True)

cve_cliente_real = ""
cve_vendedor_real = vendedor
nombre_cliente_limpio = "MOSTRADOR"
nombre_vendedor_real = ""

if cliente_seleccionado and not clientes_df.empty:
    info_cliente = clientes_df[clientes_df['display'] == cliente_seleccionado].iloc[0]
    cve_cliente_real = info_cliente['cve']
    nombre_cliente_limpio = info_cliente['nombre']
    nombre_vendedor_real = info_cliente.get('nombre_vend', '')

    if not cve_vendedor_real and info_cliente['cve_age']:
        cve_vendedor_real = info_cliente['cve_age']

with st.expander("🔍 Búsqueda de Productos"):
    c1, c2, c3 = st.columns([4, 1, 1])
    c1.selectbox(
        "Producto:", catalogo_df['display'], index=None,
        placeholder="Escriba o seleccione un producto...", key="prod_sel"
    )
    c2.number_input("Cant:", min_value=1, value=1, key="cant_sel")
    c3.button("➕ Añadir", on_click=agregar_producto_manual)

with st.expander("🚀 Carga Rápida"):
    texto = st.text_area("Pega aquí (Código Cantidad)")
    if st.button("Procesar"):
        analizar_y_cargar_pedido(texto, catalogo_df)
        st.rerun()

if st.session_state.cotizacion:
    df_cot = pd.DataFrame(st.session_state.cotizacion)

    # --- PRECIOS SEGÚN LA LISTA SELECCIONADA ---
    # Productos de cotizaciones viejas pueden no traer precio_base:
    # se reconstruye a partir del precio_unitario que tenían guardado.
    if 'precio_base' not in df_cot.columns:
        df_cot['precio_base'] = float('nan')
    faltan = df_cot['precio_base'].isna()
    if faltan.any() and 'precio_unitario' in df_cot.columns:
        if st.session_state.tipo_lista == "Dimefet":
            df_cot.loc[faltan, 'precio_base'] = df_cot.loc[faltan, 'precio_unitario'] * 0.90
        else:
            df_cot.loc[faltan, 'precio_base'] = df_cot.loc[faltan, 'precio_unitario']
    df_cot['precio_base'] = df_cot['precio_base'].fillna(0)

    if st.session_state.tipo_lista == "Distribuidor":
        df_cot['precio_unitario'] = df_cot['precio_base']
    else:
        df_cot['precio_unitario'] = df_cot['precio_base'] / 0.90

    df_cot['Subtotal'] = df_cot['cantidad'] * df_cot['precio_unitario']

    st.write("### Detalle Actual")
    for i, row in df_cot.iterrows():
        col_item1, col_item2, col_item3 = st.columns([6, 2, 1])
        col_item1.write(f"**{row['codigo']}** - {row['descripcion']}")
        col_item2.write(f"{row['cantidad']} x ${row['precio_unitario']:,.2f} = **${row['Subtotal']:,.2f}**")
        if col_item3.button("❌", key=f"del_{i}"):
            st.session_state.cotizacion.pop(i)
            if 'folio_generado' in st.session_state:
                del st.session_state.folio_generado
            st.rerun()

    total = df_cot['Subtotal'].sum()
    st.subheader(f"Total ({st.session_state.tipo_lista}): ${total:,.2f}")

    # --- BOTONES DE SALIDA PARA COTIZACIÓN (Sin Folio) ---
    mensaje_cot = f"Cotización\n\nCliente: {nombre_cliente_limpio}\nDocumento: {tipo_doc}\n\nDetalle:\n\n"
    for _, fila in df_cot.iterrows():
        mensaje_cot += f"· {fila['codigo']} {int(fila['cantidad'])} {fila['descripcion']}\n"
    wa_url_cot = f"https://wa.me/?text={quote_plus(mensaje_cot)}"

    col_acc1, col_acc2, col_acc3, col_acc4 = st.columns(4)
    with col_acc1:
        st.link_button("📲 Enviar Cotización (WhatsApp)", wa_url_cot, use_container_width=True)
    with col_acc2:
        pdf_bytes = generar_pdf(df_cot, nombre_cliente_limpio, tipo_doc, st.session_state.tipo_lista, total)
        nombre_archivo = limpiar_nombre_archivo(nombre_cliente_limpio)
        fecha_archivo = datetime.now().strftime("%d-%m-%Y")
        st.download_button(
            "📥 Descargar PDF",
            data=pdf_bytes,
            file_name=f"Cotizacion_{nombre_archivo}_{fecha_archivo}.pdf",
            mime="application/pdf",
            use_container_width=True
        )
    with col_acc3:
        texto_btn_guardar = "💾 Actualizar Cotización" if st.session_state.editando_id else "💾 Guardar Cotización"
        if st.button(texto_btn_guardar, use_container_width=True):
            guardar_cotizacion(cliente_seleccionado, tipo_doc, st.session_state.tipo_lista, total)
            st.success("¡Guardado exitosamente!")
            st.rerun()
    with col_acc4:
        if st.button("🗑️ Limpiar / Cancelar", use_container_width=True):
            st.session_state.cotizacion = []
            st.session_state.editando_id = None
            st.session_state.cliente_seleccionado = None
            st.session_state.vendedor_input = ""
            st.session_state.tipo_doc_input = "Remisión"
            if 'folio_generado' in st.session_state:
                del st.session_state.folio_generado
            st.rerun()

    # --- CONVERSIÓN A PEDIDO ---
    st.write("---")
    st.write("### 🚀 Levantar Pedido")

    if cve_vendedor_real and cve_cliente_real:
        col_erp1, col_erp2 = st.columns(2)

        with col_erp1:
            if st.button("🔄 Convertir a Pedido", use_container_width=True):
                if no_ped_manual:
                    st.session_state.folio_generado = no_ped_manual
                    st.warning("⚠️ Folio manual. El pedido NO se registró en el servidor.")
                else:
                    with st.spinner("Creando pedido en el servidor..."):
                        folio_nuevo = crear_pedido_render(nombre_cliente_limpio, cve_vendedor_real, cve_cliente_real, st.session_state.cotizacion)

                        if folio_nuevo:
                            st.session_state.folio_generado = folio_nuevo
                            st.success(f"✅ Pedido registrado con folio {folio_nuevo}")

        with col_erp2:
            if 'folio_generado' in st.session_state:
                # Mensaje de WhatsApp con el mismo formato que la app de pedidos
                vendedor_mostrar = nombre_vendedor_real if nombre_vendedor_real else vendedor
                mensaje_pedido = "*Pedido Registrado*\n"
                mensaje_pedido += f"*Vendedor:* {vendedor_mostrar}\n"
                mensaje_pedido += f"*Cliente:* {cve_cliente_real} - {nombre_cliente_limpio}\n"
                mensaje_pedido += f"*Documento:* {tipo_doc}\n"
                mensaje_pedido += f"*Folio:* {st.session_state.folio_generado}\n"
                if observaciones.strip():
                    mensaje_pedido += f"*Observaciones:* {observaciones.strip()}\n"
                mensaje_pedido += "\n*Detalle del Pedido:*\n\n"

                for _, fila in df_cot.iterrows():
                    mensaje_pedido += f"· {fila['codigo']} *{int(fila['cantidad'])}* {str(fila['descripcion']).upper()}\n"

                wa_url_pedido = f"https://wa.me/?text={quote_plus(mensaje_pedido)}"
                st.link_button(f"📲 Enviar por WhatsApp (Folio: {st.session_state.folio_generado})", wa_url_pedido, use_container_width=True)
    else:
        st.warning("⚠️ Selecciona un Cliente del catálogo para habilitar la conversión a pedido.")

else:
    st.info("Agregue productos para iniciar la cotización.")

st.divider()
with st.expander("📂 Historial de Cotizaciones Guardadas (Cargar y Editar)"):
    historial = leer_historial()

    if not historial:
        st.write("No hay cotizaciones guardadas.")
    else:
        lista_historial = []
        for cot_id, datos in historial.items():
            lista_historial.append({
                "ID": datos['id'],
                "Fecha": datos['fecha'],
                "Cliente": datos['cliente'],
                "Total": f"${datos['total']:,.2f}"
            })

        df_hist = pd.DataFrame(lista_historial).sort_values(by="Fecha", ascending=False)
        st.dataframe(df_hist, use_container_width=True, hide_index=True)

        st.write("---")
        st.write("**Selecciona una cotización para cargarla y editarla:**")

        opciones_select = [f"{datos['cliente']} | {datos['fecha']} | {cot_id}" for cot_id, datos in historial.items()]
        cot_seleccionada = st.selectbox("Cotizaciones Guardadas:", opciones_select, index=None, placeholder="Elige una por nombre de cliente...")

        if cot_seleccionada:
            id_a_cargar = cot_seleccionada.split(" | ")[2]
            if st.button("✏️ Cargar al Editor"):
                datos_cot = historial[id_a_cargar]
                st.session_state.cotizacion = datos_cot['productos']
                st.session_state.cliente_seleccionado = datos_cot['cliente']
                st.session_state.tipo_doc_input = datos_cot['tipo_doc']
                st.session_state.tipo_lista = datos_cot['lista_precios']
                st.session_state.editando_id = datos_cot['id']
                if 'folio_generado' in st.session_state:
                    del st.session_state.folio_generado
                st.rerun()
