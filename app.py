import streamlit as st
import pandas as pd
from datetime import datetime
from fpdf import FPDF
from urllib.parse import quote_plus 
import re
import json
import os
import requests 
from io import BytesIO

# ==============================================================================
# SECCIÓN 1: DEFINICIÓN DE FUNCIONES Y CARGA DE CATÁLOGOS
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
        return pd.DataFrame(columns=['codigo', 'descripcion', 'precio'])

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

@st.cache_data(ttl=600) 
def cargar_clientes_desde_sheets():
    sheet_id = '1QzmVhpIiwWN2Scz8J9_jn2GeLI2jIz2Mv5I6HDiKQVs'
    url_clientes = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&sheet=Clientes"
    
    try:
        df = pd.read_csv(url_clientes)
        return df
    except Exception as e:
        st.error(f"🚨 Error técnico de Google Sheets: {e}")
        return pd.DataFrame()

def analizar_y_cargar_pedido(texto_pedido, df_catalogo):
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
                diagnostico_fallos.append(f"Cód. no enc.: '{codigo_posible}' Línea: {linea.strip()}")
            
    if nuevos_productos:
        st.session_state.cotizacion.extend(nuevos_productos)
        st.success(f"Se cargaron {len(nuevos_productos)} productos a la cotización.")
    else:
        if not diagnostico_fallos:
            st.warning("No se encontraron productos válidos en el formato.")
            
    if diagnostico_fallos:
        st.error("❌ Fallos de Coincidencia (Verifica catálogo):")
        st.code('\n'.join(diagnostico_fallos))

def guardar_cotizacion_pausa(nombre_cliente, tipo_lista, partidas):
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

import tempfile # Asegúrate de que este import esté arriba con los demás

def generar_pdf(cliente, vendedor, tipo_doc, tipo_lista, df_cot, total):
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", 'B', 16)
    pdf.cell(0, 10, "Cotizacion de Pedido", ln=True, align='C')
    pdf.set_font("Arial", '', 11)
    pdf.cell(0, 8, f"Cliente: {cliente}", ln=True)
    pdf.cell(0, 8, f"Vendedor: {vendedor}", ln=True)
    pdf.cell(0, 8, f"Documento: {tipo_doc} | Lista: {tipo_lista}", ln=True)
    pdf.cell(0, 8, f"Fecha: {datetime.now().strftime('%d/%m/%Y')}", ln=True)
    pdf.ln(5)
    
    pdf.set_font("Arial", 'B', 9)
    pdf.cell(25, 8, "Codigo", 1)
    pdf.cell(105, 8, "Descripcion", 1)
    pdf.cell(20, 8, "Cant.", 1, 0, 'C')
    pdf.cell(40, 8, "Importe", 1, 1, 'C')
    
    pdf.set_font("Arial", '', 8)
    for _, row in df_cot.iterrows():
        pdf.cell(25, 8, str(row['codigo']), 1)
        desc = str(row['descripcion'])[:55]
        pdf.cell(105, 8, desc, 1)
        pdf.cell(20, 8, str(row['cantidad']), 1, 0, 'C')
        pdf.cell(40, 8, f"${row['Importe']:,.2f}", 1, 1, 'R')
        
    pdf.ln(5)
    pdf.set_font("Arial", 'B', 12)
    pdf.cell(0, 10, f"Total Global: ${total:,.2f}", ln=True, align='R')
    
    # Creamos un archivo temporal para que FPDF guarde ahí
    tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
    pdf.output(tmp_file.name)
    return tmp_file.name # Devolvemos la ruta del archivo# SECCIÓN 2: INTERFAZ Y LÓGICA DE CONTROL DE STREAMLIT
# ==============================================================================

st.set_page_config(page_title="Cotizador de Pedidos", layout="wide")

if 'cotizacion' not in st.session_state: st.session_state.cotizacion = []
if 'tipo_lista' not in st.session_state: st.session_state.tipo_lista = "Distribuidor"

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
        with st.sidebar.expander("📂 Recuperar Cotización en Pausa"):
            cot_seleccionada = st.sidebar.selectbox("Selecciona un cliente para editar:", options=list(cotizaciones_guardadas.keys()))
            if st.sidebar.button("Cargar y Editar"):
                datos_recuperados = cotizaciones_guardadas[cot_seleccionada]
                st.session_state.cotizacion = datos_recuperados["partidas"]
                st.session_state.tipo_lista = datos_recuperados["tipo_lista"]
                st.sidebar.success(f"Cargadas {len(st.session_state.cotizacion)} partidas de {cot_seleccionada}")
                st.rerun()

# --- BLOQUE 2: CONFIGURACIÓN GENERAL DEL PEDIDO (DATOS MAESTROS) ---
col_gen1, col_gen2 = st.columns(2)

with col_gen1:
    cve_agente_actual = "AGE00"
    cve_cliente_actual = "CTE000"
    cliente_sel = None
    
    if not df_clientes.empty and len(df_clientes.columns) >= 4:
        vendedores_df = df_clientes.iloc[:, [0, 1]].drop_duplicates().dropna()
        opciones_vendedores = [f"{str(row.iloc[0]).strip()} - {str(row.iloc[1]).strip()}" for _, row in vendedores_df.iterrows()]
        
        # BUSCADOR EN BLANCO: index=None obliga a que no haya nadie seleccionado por defecto
        vendedor_sel = st.selectbox(
            "👤 ¿Qué vendedor eres?", 
            options=opciones_vendedores,
            index=None,
            placeholder="Comienza a escribir tu número o nombre..."
        )
        
        if vendedor_sel:
            id_vendedor_actual = vendedor_sel.split(" - ")[0]
            if id_vendedor_actual.isdigit():
                cve_agente_actual = f"AGE{int(id_vendedor_actual):02d}"
            else:
                cve_agente_actual = id_vendedor_actual
                
            st.caption(f"Clave Agente ERP: **{cve_agente_actual}**")
            clientes_filtrados = df_clientes[df_clientes.iloc[:, 0].astype(str).str.strip() == id_vendedor_actual]
            opciones_clientes = [f"{str(row.iloc[2]).strip()} - {str(row.iloc[3]).strip().upper()}" for _, row in clientes_filtrados.iterrows()]
            
            cliente_sel = st.selectbox(
                "🏢 Escribe y selecciona el Cliente:", 
                options=opciones_clientes,
                index=None,
                placeholder="Comienza a escribir el nombre del cliente..."
            )
            
            if cliente_sel:
                cve_cliente_actual = cliente_sel.split(" - ")[0]
                st.caption(f"Clave de Cliente ERP: **{cve_cliente_actual}**")
        else:
            st.info("👆 Por favor, busca y selecciona tu nombre de vendedor arriba para continuar.")
    else:
        st.error("No se pudo cargar la base de datos de vendedores/clientes. Verifica la conexión.")

with col_gen2:
    if vendedor_sel:
        tipo_doc = st.selectbox("📄 Tipo de Documento:", ["Remision", "Factura"])
        st.session_state.tipo_lista = st.radio("💰 Lista de Precios comercial:", ["Distribuidor", "Dimefet"], horizontal=True)

# --- BLOQUE 3: AGREGAR ARTÍCULOS ---
if vendedor_sel:
    st.markdown("---")
    tab_manual, tab_rapida = st.tabs(["🔍 Búsqueda Individual de Productos", "🚀 Carga Rápida por Texto"])

    with tab_manual:
        col_m1, col_m2, col_m3 = st.columns([4,1,1])
        prod_sel = col_m1.selectbox("Buscar Producto:", options=catalogo_df['display'].tolist(), index=None, placeholder="Escribe código o nombre...")
        cant_sel = col_m2.number_input("Cantidad:", min_value=1, value=1, step=1)
        if col_m3.button("➕ Agregar Artículo", use_container_width=True):
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
if vendedor_sel:
    st.markdown("---")
    st.subheader("📋 Detalle de la Cotización Actual")

    if st.session_state.cotizacion:
        df_cot = pd.DataFrame(st.session_state.cotizacion)
        df_cot['Importe'] = df_cot['cantidad'] * df_cot['precio_unitario']
        
        st.table(df_cot.style.format({'precio_unitario': '${:,.2f}', 'Importe': '${:,.2f}'}))
        total_cotizacion = df_cot['Importe'].sum()
        st.markdown(f"### **Total Global ({st.session_state.tipo_lista}): ${total_cotizacion:,.2f}**")
        
        # 4 BOTONES: Pausa, PDF, WhatsApp, Limpiar
        c_btn1, c_btn2, c_btn3, c_btn4 = st.columns(4)
        
        nombre_limpio = cliente_sel.split(" - ", 1)[1] if cliente_sel else "MOSTRADOR"
        
        with c_btn1:
            if st.button("💾 Guardar en Pausa", use_container_width=True):
                guardar_cotizacion_pausa(nombre_limpio, st.session_state.tipo_lista, st.session_state.cotizacion)
        
        with c_btn2:
            # BOTÓN NUEVO DE PDF
            pdf_bytes = generar_pdf(nombre_limpio, vendedor_sel, tipo_doc, st.session_state.tipo_lista, df_cot, total_cotizacion)
            st.download_button(
                label="📄 Descargar PDF",
                data=pdf_bytes,
                file_name=f"Cotizacion_{nombre_limpio}.pdf",
                mime="application/pdf",
                use_container_width=True
            )

        with c_btn3:
            mensaje_wa = f"*Nuevo Pedido*\n\n*Cliente:* {nombre_limpio}\n*Tipo de Documento:* {tipo_doc}\n\n*Detalle del Pedido:*\n\n"
            for _, fila in df_cot.iterrows():
                mensaje_wa += f"* {fila['codigo']} {fila['cantidad']} {fila['descripcion']}\n"
            url_wa = f"https://wa.me/?text={quote_plus(mensaje_wa)}"
            st.link_button("📲 Enviar texto por WhatsApp", url_wa, use_container_width=True)
            
        with c_btn4:
            if st.button("🗑️ Limpiar Pantalla", use_container_width=True):
                st.session_state.cotizacion = []
                st.rerun()

        # --- SECCIÓN 3: CONEXIÓN DE FOLIO CENTRAL Y EXPORTACIÓN AL ERP ---
     # --- SECCIÓN 3: CONEXIÓN DE FOLIO CENTRAL Y EXPORTACIÓN AL ERP ---
       # --- SECCIÓN 3: FINALIZAR Y EXPORTAR ---
        st.markdown("---")
        st.header("⚙️ Finalizar y Exportar")
        
        # 1. BOTÓN DE EXPORTACIÓN A EXCEL (ERP)
        if st.button("🚀 OBTENER FOLIO Y GENERAR EXCEL PARA ERP", type="primary", use_container_width=True):
            if not cliente_sel:
                st.error("❌ Selecciona un cliente primero.")
            else:
                # Folio y Lógica ERP aquí...
                folio_asignado = "1254" 
                # (Tu lógica de requests.get va aquí)
                
                filas_erp = []
                for item in st.session_state.cotizacion:
                    filas_erp.append({"no_ped": folio_asignado, "cve_prod": item['codigo'], "cant_prod": item['cantidad'], "cve_cte": cve_cliente_actual, "cve_age": cve_agente_actual, "cve_suc": "1", "cve_mon": "P", "lugar": "A2"})
                
                df_final_erp = pd.DataFrame(filas_erp)
                output_buffer = BytesIO()
                with pd.ExcelWriter(output_buffer, engine='openpyxl') as writer:
                    df_final_erp.to_excel(writer, index=False, sheet_name='Pedido')
                
                st.session_state.ultimo_folio = folio_asignado
                st.session_state.excel_data = output_buffer.getvalue()
                st.success(f"🎉 Folio: {folio_asignado}")

        # MOSTRAR BOTONES DE DESCARGA SOLO SI HAY DATOS
        col_d1, col_d2 = st.columns(2)
        
        # Botón descarga Excel (si se generó)
        if 'excel_data' in st.session_state:
            col_d1.download_button("📥 Descargar Excel ERP", data=st.session_state.excel_data, 
                                  file_name=f"Pedido_{st.session_state.ultimo_folio}.xlsx", 
                                  mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)

        # Botón descarga PDF (Siempre disponible)
     # Botón descarga PDF (Siempre disponible)
        ruta_pdf = generar_pdf(nombre_limpio, vendedor_sel, tipo_doc, st.session_state.tipo_lista, df_cot, total_cotizacion)
        with open(ruta_pdf, "rb") as f:
            pdf_data = f.read()
        
        # AGREGAMOS EL PARÁMETRO key PARA SOLUCIONAR EL ERROR DE DUPLICADOS
        col_d2.download_button(
            label="📄 Descargar PDF", 
            data=pdf_data, 
            file_name=f"Cotizacion_{nombre_limpio}.pdf", 
            mime="application/pdf", 
            use_container_width=True,
            key="pdf_unico_id" 
        )