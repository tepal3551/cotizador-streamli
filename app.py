import streamlit as st
import pandas as pd
from datetime import datetime
import requests
from io import BytesIO

# ==========================================
# 1. INICIALIZACIÓN DE ESTADOS DE SESIÓN
# ==========================================
if 'cotizaciones_guardadas' not in st.session_state:
    st.session_state.cotizaciones_guardadas = {}  # Almacena el histórico en memoria
if 'productos_actuales' not in st.session_state:
    st.session_state.productos_actuales = []      # Productos de la sesión activa
if 'id_cotizacion_editar' not in st.session_state:
    st.session_state.id_cotizacion_editar = None   # ID de la cotización que se está modificando

# ==========================================
# 2. FUNCIONES AUXILIARES Y CONEXIÓN ERP
# ==========================================

@st.cache_data(ttl=300)
def cargar_clientes_sheets():
    # URL estructurada para leer la pestaña 'clientes' de tu Google Sheet
    sheet_id = '1QzmVhpIiwWN2Scz8J9_jn2GeLI2jIz2Mv5I6HDiKQVs'
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet=clientes"
    df = pd.read_csv(url)
    # Limpieza inicial de espacios en blanco en los nombres de las columnas
    df.columns = df.columns.astype(str).str.strip()
    return df

def obtener_siguiente_folio():
    try:
        response = requests.get("https://servidor-pedidos.onrender.com")
        return response.text.strip()
    except:
        return "0000"  # Fallback si el servidor de Render no responde

def generar_excel_erp(df_cot, folio, cve_cte, cve_age):
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
            "lugar": "A2"  # Ubicación fija configurada para el almacén
        })
    
    df_final = pd.DataFrame(filas)
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df_final.to_excel(writer, index=False)
    return buffer.getvalue()

# Placeholder para tu función de catálogo existente
def cargar_catalogo():
    return pd.DataFrame(columns=['codigo', 'descripcion', 'precio'])

# ==========================================
# 3. INTERFAZ DE USUARIO PRINCIPAL
# ==========================================

st.title("🔩 Cotizador de Pedidos")

try:
    df_raw = cargar_clientes_sheets()
    
    # MAPEO INTELIGENTE: Detecta las columnas dinámicamente según su contenido para evitar KeyError
    col_vendedor = next((c for c in df_raw.columns if 'vend' in c.lower() or 'age' in c.lower()), None)
    col_cliente = next((c for c in df_raw.columns if ('nom' in c.lower() or 'cli' in c.lower() or 'cte' in c.lower()) and 'cve' not in c.lower() and 'clav' not in c.lower()), None)
    col_clave = next((c for c in df_raw.columns if 'clav' in c.lower() or 'cve' in c.lower() or 'cod' in c.lower()), None)

    # Validación de mapeo exitoso
    if not col_vendedor or not col_cliente or not col_clave:
        st.error("🚨 No se pudieron identificar las columnas obligatorias en el archivo de Google Sheets.")
        st.warning(f"Columnas detectadas en tu hoja: {list(df_raw.columns)}")
        st.info("Asegúrate de tener columnas que contengan las palabras clave: 'Vendedor', 'Nombre' (o Cliente) y 'Clave'.")
        st.stop()

    # Renombrado seguro para el resto del script
    df_clientes = df_raw.rename(columns={
        col_vendedor: 'vendedor',
        col_cliente: 'nombre',
        col_clave: 'clave'
    })
    
    # Extraer vendedores únicos omitiendo valores vacíos
    vendedores_disponibles = df_clientes['vendedor'].dropna().unique()

except Exception as e:
    st.error(f"Error al conectar con la base de datos de Google Sheets: {e}")
    st.stop()

# Estructura de pestañas de la aplicación
tab_crear, tab_bandeja = st.tabs(["📝 Crear / Editar Cotización", "🗂️ Bandeja de Cotizaciones"])

# ------------------------------------------
# PESTAÑA 1: CREAR / EDITAR COTIZACIÓN
# ------------------------------------------
with tab_crear:
    if len(vendedores_disponibles) > 0:
        if st.session_state.id_cotizacion_editar:
            st.warning(f"⚠️ Modo edición activo para la Cotización ID: {st.session_state.id_cotizacion_editar}")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Selector de Vendedor: Empieza vacío y permite escribir para filtrar coincidencias
            vendedor = st.selectbox(
                "Vendedor", 
                options=sorted(vendedores_disponibles),
                index=None,
                placeholder="Escribe para buscar vendedor..."
            )
            
        with col2:
            # Selector de Cliente: Solo se activa y filtra cuando se elige el vendedor
            if vendedor:
                clientes_filtrados = df_clientes[df_clientes['vendedor'] == vendedor]
                cliente_info = st.selectbox(
                    "Cliente", 
                    options=sorted(clientes_filtrados['nombre'].dropna().unique()),
                    index=None,
                    placeholder="Escribe para buscar cliente..."
                )
            else:
                cliente_info = None

        # Bloque de captura de productos: Se habilita únicamente al tener vendedor y cliente seleccionados
        if vendedor and cliente_info:
            fila_cliente = df_clientes[df_clientes['nombre'] == cliente_info].iloc[0]
            cve_cte = fila_cliente['clave']
            
            st.write("---")
            st.subheader(f"🛒 Captura de Productos para: {cliente_info} (Clave: {cve_cte})")
            
            # Formulario de inserción de productos
            col_prod, col_cant, col_btn = st.columns([3, 1, 1])
            with col_prod:
                cod_prod = st.text_input("Código de Producto")
            with col_cant:
                cant_prod = st.number_input("Cantidad", min_value=1, value=1)
            with col_btn:
                st.write("")  # Alineación vertical
                if st.button("Añadir"):
                    if cod_prod:
                        st.session_state.productos_actuales.append({
                            'codigo': cod_prod,
                            'cantidad': cant_prod
                        })
                        st.experimental_rerun()

            # Visualización y almacenamiento de la tabla de cotización activa
            if st.session_state.productos_actuales:
                df_tabla_actual = pd.DataFrame(st.session_state.productos_actuales)
                st.dataframe(df_tabla_actual, use_container_width=True)
                
                col_acciones = st.columns(2)
                with col_acciones[0]:
                    if st.button("💾 Guardar como Pendiente"):
                        if st.session_state.id_cotizacion_editar:
                            # Actualizar cotización que se estaba editando
                            id_cot = st.session_state.id_cotizacion_editar
                            st.session_state.cotizaciones_guardadas[id_cot].update({
                                "productos": st.session_state.productos_actuales,
                                "vendedor": vendedor,
                                "cliente": cliente_info,
                                "cve_cte": cve_cte,
                                "fecha": datetime.now().strftime("%d/%m/%Y %H:%M")
                            })
                            st.success(f"La cotización {id_cot} ha sido modificada con éxito.")
                        else:
                            # Generar un identificador único para una nueva cotización
                            id_cot = f"COT-{int(datetime.now().timestamp())}"
                            st.session_state.cotizaciones_guardadas[id_cot] = {
                                "vendedor": vendedor,
                                "cliente": cliente_info,
                                "cve_cte": cve_cte,
                                "productos": st.session_state.productos_actuales,
                                "estado": "Pendiente",
                                "fecha": datetime.now().strftime("%d/%m/%Y %H:%M")
                            }
                            st.success(f"Cotización resguardada en la bandeja con el ID: {id_cot}")
                        
                        # Limpieza de variables de control
                        st.session_state.productos_actuales = []
                        st.session_state.id_cotizacion_editar = None
                        st.experimental_rerun()
                        
                with col_acciones[1]:
                    if st.button("❌ Cancelar / Limpiar"):
                        st.session_state.productos_actuales = []
                        st.session_state.id_cotizacion_editar = None
                        st.experimental_rerun()
        else:
            if not vendedor:
                st.info("👆 Comienza escribiendo o seleccionando un vendedor de la lista.")
            elif not cliente_info:
                st.info("👆 Selecciona el nombre del cliente para habilitar la sección de productos.")

# ------------------------------------------
# PESTAÑA 2: BANDEJA DE COTIZACIONES
# ------------------------------------------
with tab_bandeja:
    st.subheader("🗂️ Historial y Control de Estatus")
    
    if not st.session_state.cotizaciones_guardadas:
        st.info("No se encuentran cotizaciones registradas en la bandeja actualmente.")
    else:
        for cot_id, datos in list(st.session_state.cotizaciones_guardadas.items()):
            marcador_estatus = "🟢" if datos['estado'] == "Autorizada" else "🟡"
            titulo_desplegable = f"{marcador_estatus} {cot_id} | Cliente: {datos['cliente']} | Estado: {datos['estado']} ({datos['fecha']})"
            
            with st.expander(titulo_desplegable):
                df_items = pd.DataFrame(datos['productos'])
                st.dataframe(df_items, use_container_width=True)
                
                if datos['estado'] == "Pendiente":
                    col_b1, col_b2 = st.columns(2)
                    
                    with col_b1:
                        if st.button("✏️ Modificar Cotización", key=f"mod_{cot_id}"):
                            # Carga los productos y el identificador en los estados globales para edición
                            st.session_state.productos_actuales = datos['productos']
                            st.session_state.id_cotizacion_editar = cot_id
                            st.info("Datos transferidos. Dirígete a la primera pestaña para aplicar los cambios.")
                            st.experimental_rerun()
                            
                    with col_b2:
                        if st.button("✅ Autorizar y Enviar a Pedido", key=f"aut_{cot_id}"):
                            # Consume el consecutivo real desde Render al cambiar el estatus
                            folio_generado = obtener_siguiente_folio()
                            datos['estado'] = "Autorizada"
                            datos['folio_erp'] = folio_generado
                            st.success(f"Estatus actualizado. Folio ERP asignado: {folio_generado}")
                            st.experimental_rerun()
                            
                elif datos['estado'] == "Autorizada":
                    st.success(f"Esta cotización se encuentra autorizada bajo el Folio ERP: {datos['folio_erp']}")
                    
                    # Descarga del layout de Excel estructurado
                    excel_data = generar_excel_erp(df_items, datos['folio_erp'], datos['cve_cte'], "AGE01")
                    st.download_button(
                        label="📥 Descargar Layout de Pedido (Excel)",
                        data=excel_data,
                        file_name=f"Pedido_{datos['folio_erp']}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key=f"down_{cot_id}"
                    )