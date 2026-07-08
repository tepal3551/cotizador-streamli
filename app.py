import streamlit as st
import pandas as pd
from datetime import datetime
from urllib.parse import quote_plus 
import re
import json
import os
import requests 
from io import BytesIO, StringIO

# ==============================================================================
# SECCIÓN 1: CARGA DE CATÁLOGOS Y CONEXIÓN A GOOGLE SHEETS BLINDEADA
# ==============================================================================

@st.cache_data(show_spinner=False)
def cargar_catalogo(nombre_archivo_catalogo, nombre_archivo_actualizaciones):
    """Carga el catálogo localmente con máxima velocidad usando el motor en C."""
    try:
        df = pd.read_csv(
            nombre_archivo_catalogo, 
            header=None, 
            names=['codigo', 'descripcion', 'precio'],
            usecols=[0, 1, 2],
            on_bad_lines='skip',
            engine='c'
        )
        df['codigo'] = df['codigo'].astype(str).str.strip()
        df['precio'] = pd.to_numeric(df['precio'], errors='coerce').fillna(0.0)
    except Exception:
        return pd.DataFrame(columns=['codigo', 'descripcion', 'precio', 'display'])

    df = df.set_index('codigo')

    try:
        df_act = pd.read_csv(
            nombre_archivo_actualizaciones, 
            header=None, 
            names=['codigo', 'descripcion', 'precio'],
            on_bad_lines='skip',
            engine='c'
        )
        for _, fila in df_act.iterrows():
            cod = str(fila['codigo']).strip()
            if cod in df.index:
                df.loc[cod, 'precio'] = float(fila['precio'])
    except Exception:
        pass

    df = df.reset_index()
    df['display'] = df['codigo'] + " - " + df['descripcion']
    return df

@st.cache_data(ttl=600, show_spinner=False)
def cargar_clientes_desde_sheets():
    """Descarga clientes desde Google Sheets con diagnóstico inteligente de errores."""
    sheet_id = '1QzmVhpIiwWN2Scz8J9_jn2GeLI2jIz2Mv5I6HDiKQVs'
    nombre_pestana = 'Clientes' 
    url_clientes = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={nombre_pestana}"
    
    try:
        # Aumentamos a 7 segundos el tiempo límite de espera para dar margen a Google
        respuesta = requests.get(url_clientes, timeout=7)
        
        # Detector de archivo privado o restringido por Google
        if "accounts.google.com" in respuesta.text or "<html" in respuesta.text.lower():
            st.error("🔒 **Error de Lectura:** El archivo de Google Sheets está privado o restringido. Ve a Google Sheets -> Compartir -> 'Cualquier persona con el enlace puede ver'.")
            raise Exception("Hoja de Google privada.")
            
        if respuesta.status_code == 200:
            df = pd.read_csv(StringIO(respuesta.text), engine='c')
            df_clientes = pd.DataFrame()
            df_clientes['clave'] = df.iloc[:, 0].astype(str).str.strip()
            df_clientes['nombre'] = df.iloc[:, 1].astype(str).str.strip().str.upper()
            return df_clientes
            
    except Exception as e:
        if "Hoja de Google privada" not in str(e):
            st.warning(f"⚠️ No se pudo cargar Google Sheets ({str(e)}). Usando lista de respaldo temporal.")
    
    # Respaldo inmediato si la nube falla
    return pd.DataFrame([
        {"clave": "CTE001", "nombre": "TOME GARCIA MARIA MAGDALENA"},
        {"clave": "CTE000", "nombre": "CLIENTE PUBLICO GENERAL"}
    ])

def analizar_y_cargar_pedido(texto_pedido, df_catalogo):
    """Analiza líneas de texto identificando código y cantidad de forma ultra rápida."""
    lineas = [line.strip() for line in texto_pedido.split('\n') if line.strip()]
    nuevos_productos = []
    diagnostico_fallos = []
    
    catalogo_map = df_catalogo.set_index('codigo').to_dict('index') 
    productos_en_sesion = {p['codigo'] for p in st.session_state.cotizacion}
    PATRON_PEDIDO = re.compile(r'^[^\d]*(\d{4,6})[^\d]*(\d{1,3})')

    for linea in lineas:
        if 'DETALLE' in linea.upper() or 'CLIENTE' in linea.upper() or len(linea.split()) < 2: 
            continue
            
        codigo_posible = None
        cantidad_posible = 0

        match = PATRON_PEDIDO.match(linea)
        if match:
            try:
                codigo_posible = match.group(1).strip()
                cantidad_posible = int(match.group(2))
                if cantidad_posible <= 0: cantidad_posible = 1
            except Exception: pass 

        if codigo_posible and codigo_posible in catalogo_map:
            if codigo_posible in productos_en_sesion: continue
            
            p_base = float(catalogo_map[codigo_posible]['precio'])
            precio_final = p_base if st.session_state.tipo_lista == "Distribuidor" else p_base / 0.90
            
            nuevos_productos.append({
                'codigo': codigo_posible,
                'descripcion': catalogo_map[codigo_posible]['descripcion'],
                'cantidad': cantidad_posible,
                'precio_unitario': precio_final
            })
        else:
            if codigo_posible and cantidad_posible > 0:
                diagnostico_fallos.append(f"Cód. no enc.: '{codigo_posible}' en: {linea.strip()}")
            
    if nuevos_productos:
        st.session_state.cotizacion.extend(nuevos_productos)
        st.success(f"Se cargaron {len(nuevos_productos)} productos a la cotización.")
    else:
        if not diagnostico_fallos:
            st.warning("No se encontraron productos válidos.")
            
    if diagnostico_fallos:
        st.error("❌ Fallos de Coincidencia:")
        st.code('\n'.join(diagnostico_fallos))

def guardar_cotizacion_pausa(nombre_cliente, tipo_lista, partidas):
    """Guarda localmente una cotización para recuperar/editar después."""
    archivo_registro = "cotizaciones_pausa.json"
    registro = {}
    if os.path.exists(archivo_registro):
        with open(archivo_registro, "r", encoding="utf-8") as f:
            try: registro = json.load(f)
            except: pass
            
    registro[nombre_cliente] = {
        "fecha": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "tipo_lista": tipo_lista,
        "partidas": partidas
    }
    with open(archivo_registro, "w", encoding="utf-8") as f:
        json.dump(registro, f, ensure_ascii=False, indent=4)
    st.success(f"💾 Cotización de '{nombre_cliente}' guardada en pausa.")

# ==============================================================================
# SECCIÓN 2: INTERFAZ Y LÓGICA DE CONTROL DE STREAMLIT
# ==============================================================================

st.set_page_config(page_title="Cotizador de Pedidos", layout="wide")

if 'cotizacion' not in st.session_state: st.session_state.cotizacion = []
if 'tipo_lista' not in st.session_state: st.session_state.tipo_lista = "Distribuidor"

# Diccionario con los 13 vendedores integrados de nuevo
diccionario_vendedores = {
    "VENDEDOR 1": "AGE01", "VENDEDOR 2": "AGE02", "VENDEDOR 3": "AGE03",
    "VENDEDOR 4": "AGE04", "VENDEDOR 5": "AGE05", "VENDEDOR 6": "AGE06",
    "VENDEDOR 7": "AGE07", "VENDEDOR 8": "AGE08", "VENDEDOR 9": "AGE09",
    "VENDEDOR 10": "AGE10", "VENDEDOR 11": "AGE11", "VENDEDOR 12": "AGE12",
    "VENDEDOR 13": "AGE13",
}

# Carga de catálogos y clientes en memoria
catalogo_df = cargar_catalogo("CATALAGO 25 TRUP PRUEBA COTIZADOR.txt", "precios_actualizados.txt")
st.session_state.catalogo_df = catalogo_df
df_clientes = cargar_clientes_desde_sheets()

st.title("🔩 Cotizador de Pedidos")
st.markdown("---")

# --- BLOQUE 1: RECUPERAR COTIZACIÓN EN PAUSA ---
archivo_registro = "cotizaciones_pausa.json"
if os.path.exists(archivo_registro):
    with open(archivo_registro, "r", encoding="utf-8") as f:
        try: cotizaciones_guardadas = json.load(f)
        except: cotizaciones_guardadas = {}
    
    if cotizaciones_guardadas:
        with st.sidebar.expander("📂 Historial de Cotizaciones Guardadas (Cargar y Editar)"):
            cot_seleccionada = st.selectbox("Selecciona un cliente para editar:", options=list(cotizaciones_guardadas.keys()))
            if st.button("Cargar y Editar", width="stretch"):
                datos_recuperados = cotizaciones_guardadas[cot_seleccionada]
                st.session_state.cotizacion = datos_recuperados["partidas"]
                st.session_state.tipo_lista = datos_recuperados["tipo_lista"]
                st.success(f"Cargadas {len(st.session_state.cotizacion)} partidas de {cot_seleccionada}")
                st.rerun()

# --- BLOQUE 2: CONFIGURACIÓN GENERAL DEL PEDIDO (VENDEDORES Y CLIENTES) ---
col_gen1, col_gen2 = st.columns(2)

with col_gen1:
    # MENÚ DE VENDEDORES
    vendedor_sel = st.selectbox("👤 ¿Qué vendedor eres?", options=list(diccionario_vendedores.keys()))
    cve_agente_actual = diccionario_vendedores[vendedor_sel]
    
    # BUSCADOR PREDICTIVO DE CLIENTES
    cliente_sel = st.selectbox(
        "🏢 Escribe y selecciona el Cliente:", 
        options=df_clientes['nombre'].tolist(),
        index=None,
        placeholder="Comienza a escribir el nombre del cliente..."
    )
    
    if cliente_sel:
        cve_cliente_actual = df_clientes[df_clientes['nombre'] == cliente_sel]['clave'].values[0]
        st.caption(f"Clave de Cliente ERP: **{cve_cliente_actual}** | Agente: **{cve_agente_actual}**")
    else:
        cve_cliente_actual = "CTE000"

with col_gen2:
    tipo_doc = st.selectbox("📄 Tipo de Documento:", ["Remision", "Factura"])
    st.session_state.tipo_lista = st.radio("💰 Lista de Precios comercial:", ["Distribuidor", "Dimefet"], horizontal=True)

# --- BLOQUE 3: AGREGAR ARTÍCULOS ---
st.markdown("---")
tab_manual, tab_rapida = st.tabs(["🔍 Búsqueda Individual de Productos", "🚀 Carga Rápida por Texto"])

with tab_manual:
    col_m1, col_m2, col_m3 = st.columns([4,1,1])
    prod_sel = col_m1.selectbox("Buscar Producto:", options=catalogo_df['display'].tolist(), index=None, placeholder="Escriba o seleccione un producto...")
    cant_sel = col_m2.number_input("Cantidad:", min_value=1, value=1, step=1)
    if col_m3.button("➕ Añadir", width="stretch"):
        if prod_sel:
            info = catalogo_df[catalogo_df['display'] == prod_sel].iloc[0]
            p_base = float(info['precio'])
            precio_final = p_base if st.session_state.tipo_lista == "Distribuidor" else p_base / 0.90
            
            if not any(p['codigo'] == info['codigo'] for p in st.session_state.cotizacion):
                st.session_state.cotizacion.append({
                    'codigo': info['codigo'], 'descripcion': info['descripcion'],
                    'cantidad': cant_sel, 'precio_unitario': precio_final
                })
                st.success("Producto añadido.")
                st.rerun()

with tab_rapida:
    texto_rapido = st.text_area("Pega aquí el listado enviado por el cliente:", height=120, placeholder="• 44282 *2* CADENA DE PASEO...")
    if st.button("🚀 Procesar y Cargar Listado", type="primary"):
        analizar_y_cargar_pedido(texto_rapido, catalogo_df)
        st.rerun()

# --- BLOQUE 4: TABLA DE TRABAJO ACTUAL ---
st.markdown("---")
st.subheader("📋 Detalle de la Cotización Actual")

if st.session_state.cotizacion:
    df_cot = pd.DataFrame(st.session_state.cotizacion)
    df_cot['Importe'] = df_cot['cantidad'] * df_cot['precio_unitario']
    
    st.table(df_cot.style.format({'precio_unitario': '${:,.2f}', 'Importe': '${:,.2f}'}))
    total_cotizacion = df_cot['Importe'].sum()
    st.markdown(f"### **Total Global ({st.session_state.tipo_lista}): ${total_cotizacion:,.2f}**")
    
    c_btn1, c_btn2, c_btn3 = st.columns(3)
    with c_btn1:
        if st.button("💾 Guardar en Pausa", width="stretch"):
            nombre_para_guardar = cliente_sel if cliente_sel else "CLIENTE_MOSTRADOR"
            guardar_cotizacion_pausa(nombre_para_guardar, st.session_state.tipo_lista, st.session_state.cotizacion)
    with c_btn2:
        nombre_para_wa = cliente_sel if cliente_sel else "SIN NOMBRE"
        mensaje_wa = f"*Nuevo Pedido*\n\n*Cliente:* {nombre_para_wa}\n*Tipo de Documento:* {tipo_doc}\n\n*Detalle del Pedido:*\n\n"
        for _, fila in df_cot.iterrows():
            mensaje_wa += f"* {fila['codigo']} {fila['cantidad']} {fila['descripcion']}\n"
        url_wa = f"https://wa.me/?text={quote_plus(mensaje_wa)}"
        st.link_button("📲 Compartir por WhatsApp", url_wa, width="stretch")
    with c_btn3:
        if st.button("🗑️ Limpiar Pantalla", width="stretch"):
            st.session_state.cotizacion = []
            st.rerun()

    # --- SECCIÓN 3: CONEXIÓN DE FOLIO CENTRAL Y EXPORTACIÓN AL ERP ---
    st.markdown("---")
    st.header("⚙️ Finalizar y Exportar para Carga en ERP")
    
    URL_API_FOLIOS = "TU_URL_DE_GOOGLE_APPS_SCRIPT_AQUI" 
    
    if st.button("🚀 OBTENER FOLIO CONSECUTIVO Y GENERAR EXCEL", type="primary", width="stretch"):
        if not cliente_sel:
            st.error("❌ No puedes exportar al ERP sin seleccionar un cliente válido de la lista.")
        else:
            folio_asignado = "1254" 
            if URL_API_FOLIOS != "TU_URL_DE_GOOGLE_APPS_SCRIPT_AQUI":
                try:
                    respuesta = requests.get(URL_API_FOLIOS, timeout=3)
                    if respuesta.status_code == 200:
                        datos_central = respuesta.json()
                        folio_asignado = str(datos_central.get("siguienteFolio", folio_asignado))
                except:
                    st.warning("⚠️ No se conectó a la API de folios. Usando folio base.")

            filas_erp = []
            fecha_alta = datetime.now().strftime("%d/%m/%Y")
            
            for item in st.session_state.cotizacion:
                filas_erp.append({
                    "no_ped": folio_asignado,
                    "f_alta": fecha_alta,
                    "cve_cte": cve_cliente_actual,
                    "cve_age": cve_agente_actual, # Toma automáticamente al vendedor seleccionado
                    "cve_prod": item['codigo'],
                    "cant_prod": item['cantidad'],
                    "cve_suc": "1",
                    "cve_mon": "P",
                    "lugar": "A2" # Almacén fijo A2 configurado por defecto
                })
                
            df_final_erp = pd.DataFrame(filas_erp)
            output_buffer = BytesIO()
            with pd.ExcelWriter(output_buffer, engine='openpyxl') as writer:
                df_final_erp.to_excel(writer, index=False, sheet_name='Pedido')
            
            st.success(f"🎉 ¡Éxito! Folio oficial consecutivo asignado: **{folio_asignado}**")
            st.download_button(
                label="📥 Descargar Archivo Excel Estructurado para ERP",
                data=output_buffer.getvalue(),
                file_name=f"{folio_asignado}_Pedido_ERP.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                width="stretch"
            )
else:
    st.info("Agregue productos para iniciar la cotización.")
