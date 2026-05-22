import streamlit as st
import pandas as pd
from datetime import datetime
from fpdf import FPDF
from urllib.parse import quote_plus 
import re
import requests
from io import BytesIO

# ==========================================
# 1. INICIALIZACIÓN DE ESTADOS DE SESIÓN
# ==========================================
if 'cotizaciones_guardadas' not in st.session_state:
    st.session_state.cotizaciones_guardadas = {}  # Almacena las cotizaciones por ID
if 'productos_actuales' not in st.session_state:
    st.session_state.productos_actuales = []      # Productos de la cotización activa
if 'id_cotizacion_editar' not in st.session_state:
    st.session_state.id_cotizacion_editar = None   # Controla si se está editando una cotización existente
if 'cliente_seleccionado' not in st.session_state:
    st.session_state.cliente_seleccionado = None

# ==========================================
# 2. FUNCIONES AUXILIARES Y ERP
# ==========================================

@st.cache_data(ttl=300)
def cargar_clientes_sheets():
    # URL estructurada para descargar específicamente la pestaña "clientes" en formato CSV
    sheet_id = '1QzmVhpIiwWN2Scz8J9_jn2GeLI2jIz2Mv5I6HDiKQVs'
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet=clientes"
    return pd.read_csv(url)

def obtener_siguiente_folio():
    try:
        response = requests.get("https://servidor-pedidos.onrender.com")
        return response.text.strip()
    except:
        return "0000"  # Fallback

def generar_excel_erp(df_cot, folio, cve_cte, cve_age):
    # Formato exacto basado en la estructura de la plantilla de pedidos (1253)
    filas = []
    fecha_actual = datetime.now().strftime("%d/%m/%Y")
    
    for _, row in df_cot.iterrows():
        filas.append({
            "no_ped": folio,
            "f_alta_ped": fecha_actual,
            "cve_cte": cve_cte,
            "cve_age": cve_age,
            "cve_prod": row['codigo'],
            "cant_prod": row['cantidad'],
            "cve_suc": "PED",
            "cve_mon": "1",
            "lugar": "A2"
        })
    
    df_final = pd.DataFrame(filas)
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df_final.to_excel(writer, index=False)
    return buffer.getvalue()

# Placeholder para tus funciones existentes
def cargar_catalogo():
    # Tu lógica actual para el catálogo de productos Truper / Multimarcas
    return pd.DataFrame(columns=['codigo', 'descripcion', 'precio'])

# ==========================================
# 3. INTERFAZ PRINCIPAL Y FLUJO
# ==========================================

st.title("🔩 Cotizador de Pedidos")

# Carga de datos de clientes desde Google Sheets
try:
    df_clientes = cargar_clientes_sheets()
    vendedores_disponibles = df_clientes['vendedor'].unique()
except Exception as e:
    st.error(f"Error al conectar con Google Sheets: {e}")
    vendedores_disponibles = []

# Pestañas de navegación de la aplicación
tab_crear, tab_bandeja = st.tabs(["📝 Crear / Editar Cotización", "🗂️ Bandeja de Cotizaciones"])

# ------------------------------------------
# PESTAÑA 1: CREAR / EDITAR COTIZACIÓN
# ------------------------------------------
with tab_crear:
    if len(vendedores_disponibles) > 0:
        if st.session_state.id_cotizacion_editar:
            st.warning(f"Editando la Cotización ID: {st.session_state.id_cotizacion_editar}")
        
        col1, col2 = st.columns(2)
        with col1:
            vendedor = st.selectbox("Vendedor", vendedores_disponibles)
        with col2:
            clientes_filtrados = df_clientes[df_clientes['vendedor'] == vendedor]
            cliente_info = st.selectbox("Cliente", clientes_filtrados['nombre'].unique())
            
        cve_cte = df_clientes[df_clientes['nombre'] == cliente_info]['clave'].iloc[0]
        
        st.write("---")
        st.subheader("Agregar Productos")
        
        # Simulación de captura de productos (Integra aquí tus inputs de código/cantidad actuales)
        df_cat = cargar_catalogo()
        col_prod, col_cant, col_btn = st.columns([3, 1, 1])
        
        with col_prod:
            cod_prod = st.text_input("Código de Producto")
        with col_cant:
            cant_prod = st.number_input("Cantidad", min_value=1, value=1)
        with col_btn:
            st.write("")  # Espacio estético
            if st.button("Añadir"):
                if cod_prod:
                    st.session_state.productos_actuales.append({
                        'codigo': cod_prod,
                        'cantidad': cant_prod
                    })
                    st.rerun()

        # Mostrar tabla de productos actual si tiene elementos
        if st.session_state.productos_actuales:
            df_tabla_actual = pd.DataFrame(st.session_state.productos_actuales)
            st.dataframe(df_tabla_actual, use_container_width=True)
            
            col_acciones = st.columns(3)
            with col_acciones[0]:
                # Guardar o actualizar estado pendiente
                if st.button("💾 Guardar como Pendiente"):
                    if st.session_state.id_cotizacion_editar:
                        # Actualizar cotización existente
                        id_cot = st.session_state.id_cotizacion_editar
                        st.session_state.cotizaciones_guardadas[id_cot].update({
                            "productos": st.session_state.productos_actuales,
                            "vendedor": vendedor,
                            "cliente": cliente_info,
                            "cve_cte": cve_cte,
                            "fecha": datetime.now().strftime("%d/%m/%Y %H:%M")
                        })
                        st.success(f"Cotización {id_cot} actualizada correctamente.")
                    else:
                        # Generar nuevo ID temporal interno
                        id_cot = f"COT-{int(datetime.now().timestamp())}"
                        st.session_state.cotizaciones_guardadas[id_cot] = {
                            "vendedor": vendedor,
                            "cliente": cliente_info,
                            "cve_cte": cve_cte,
                            "productos": st.session_state.productos_actuales,
                            "estado": "Pendiente",
                            "fecha": datetime.now().strftime("%d/%m/%Y %H:%M")
                        }
                        st.success(f"Cotización guardada en la bandeja con ID: {id_cot}")
                    
                    # Limpiar espacio de trabajo actual
                    st.session_state.productos_actuales = []
                    st.session_state.id_cotizacion_editar = None
                    st.rerun()
                    
            with col_acciones[1]:
                if st.button("❌ Cancelar / Limpiar"):
                    st.session_state.productos_actuales = []
                    st.session_state.id_cotizacion_editar = None
                    st.rerun()

# ------------------------------------------
# PESTAÑA 2: BANDEJA DE COTIZACIONES
# ------------------------------------------
with tab_bandeja:
    st.subheader("Historial de Cotizaciones del Cliente")
    
    if not st.session_state.cotizaciones_guardadas:
        st.info("No hay cotizaciones registradas en la sesión por el momento.")
    else:
        for cot_id, datos in list(st.session_state.cotizaciones_guardadas.items()):
            # Crear una sección expandible para cada cotización guardada
            status_color = "🟢" if datos['estado'] == "Autorizada" else "🟡"
            label = f"{status_color} {cot_id} | Cliente: {datos['cliente']} | Estado: {datos['estado']} ({datos['fecha']})"
            
            with st.expander(label):
                df_items = pd.DataFrame(datos['productos'])
                st.dataframe(df_items, use_container_width=True)
                
                # Acciones basadas en el estado de la cotización
                if datos['estado'] == "Pendiente":
                    col_b1, col_b2 = st.columns(2)
                    
                    with col_b1:
                        if st.button("✏️ Editar Cotización", key=f"edit_{cot_id}"):
                            # Cargar datos en la sesión activa para edición
                            st.session_state.productos_actuales = datos['productos']
                            st.session_state.id_cotizacion_editar = cot_id
                            st.info("Cargado en la pestaña de edición. Cambia de pestaña para modificarla.")
                            st.rerun()
                            
                    with col_b2:
                        if st.button("✅ Autorizar y Generar Pedido", key=f"auth_{cot_id}"):
                            # Consumir el folio de Render y cambiar de estado
                            nuevo_folio = obtener_siguiente_folio()
                            datos['estado'] = "Autorizada"
                            datos['folio_erp'] = nuevo_folio
                            st.success(f"¡Cotización Autorizada! Folio ERP asignado: {nuevo_folio}")
                            st.rerun()
                            
                elif datos['estado'] == "Autorizada":
                    st.success(f"Esta cotización ya fue convertida en el Pedido Folio: {datos['folio_erp']}")
                    
                    # Generar descarga del archivo de Excel estructurado para el ERP
                    excel_data = generar_excel_erp(df_items, datos['folio_erp'], datos['cve_cte'], "AGE01")
                    st.download_button(
                        label="📥 Descargar Excel ERP",
                        data=excel_data,
                        file_name=f"Pedido_{datos['folio_erp']}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key=f"dl_{cot_id}"
                    )