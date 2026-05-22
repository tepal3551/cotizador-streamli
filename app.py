import streamlit as st
import pandas as pd
from datetime import datetime
import requests
from io import BytesIO

# ==========================================
# 1. FUNCIÓN SEGURA DE RECARGA
# ==========================================
def safe_rerun():
    """Ejecuta la recarga de página de forma compatible con cualquier versión de Streamlit"""
    try:
        st.rerun()
    except AttributeError:
        st.experimental_rerun()

# ==========================================
# 2. INICIALIZACIÓN DE ESTADOS DE SESIÓN
# ==========================================
if 'cotizaciones_guardadas' not in st.session_state:
    st.session_state.cotizaciones_guardadas = {}
if 'productos_actuales' not in st.session_state:
    st.session_state.productos_actuales = []
if 'id_cotizacion_editar' not in st.session_state:
    st.session_state.id_cotizacion_editar = None

# ==========================================
# 3. FUNCIONES AUXILIARES Y CONEXIÓN ERP
# ==========================================

@st.cache_data(ttl=300)
def cargar_clientes_sheets():
    sheet_id = '1QzmVhpIiwWN2Scz8J9_jn2GeLI2jIz2Mv5I6HDiKQVs'
    # URL para descargar específicamente la pestaña "clientes" en formato CSV
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet=clientes"
    df = pd.read_csv(url)
    # Limpieza estricta de espacios en los nombres de las columnas
    df.columns = df.columns.astype(str).str.strip()
    return df

def obtener_siguiente_folio():
    try:
        response = requests.get("https://servidor-pedidos.onrender.com")
        return response.text.strip()
    except:
        return "0000"  # Fallback si el servidor no responde

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
            "lugar": "A2"  # Ubicación de almacén requerida
        })
    
    df_final = pd.DataFrame(filas)
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df_final.to_excel(writer, index=False)
    return buffer.getvalue()

# Colocar aquí tu función real para obtener descripciones y precios del catálogo
def cargar_catalogo():
    return pd.DataFrame(columns=['codigo', 'descripcion', 'precio'])

# ==========================================
# 4. INTERFAZ DE USUARIO (SIEMPRE VISIBLE)
# ==========================================

st.title("🔩 Cotizador de Pedidos")

# Intentar cargar datos de Google Sheets de forma segura
df_clientes = None
vendedores_disponibles = []
error_carga = None

try:
    df_raw = cargar_clientes_sheets()
    
    # Identificación dinámica de columnas por palabras clave
    col_vendedor = next((c for c in df_raw.columns if 'vend' in c.lower() or 'age' in c.lower()), None)
    col_cliente = next((c for c in df_raw.columns if ('nom' in c.lower() or 'cli' in c.lower() or 'cte' in c.lower()) and 'cve' not in c.lower() and 'clav' not in c.lower()), None)
    col_clave = next((c for c in df_raw.columns if 'clav' in c.lower() or 'cve' in c.lower() or 'cod' in c.lower()), None)

    if col_vendedor and col_cliente and col_clave:
        df_clientes = df_raw.rename(columns={
            col_vendedor: 'vendedor',
            col_cliente: 'nombre',
            col_clave: 'clave'
        })
        vendedores_disponibles = sorted(df_clientes['vendedor'].dropna().unique())
    else:
        error_carga = f"Columnas faltantes. Detectadas en tu hoja: {list(df_raw.columns)}"
except Exception as e:
    error_carga = str(e)

# Estructura principal de pestañas
tab_crear, tab_bandeja = st.tabs(["📝 Crear / Editar Cotización", "🗂️ Bandeja de Cotizaciones"])

# ------------------------------------------
# PESTAÑA 1: CREAR / EDITAR COTIZACIÓN
# ------------------------------------------
with tab_crear:
    # Si hubo un error con el archivo, se despliega el panel de asistencia sin romper la app
    if error_carga:
        st.error("⚠️ No se pudo procesar la información de clientes desde Google Sheets.")
        st.info(f"**Detalle del problema:** {error_carga}")
        st.markdown("""
        **Pasos para solucionarlo:**
        1. Confirma que la pestaña abajo en tu Google Sheets se llame exactamente **`clientes`** (en minúsculas).
        2. Asegúrate de que el archivo esté compartido como **'Cualquier persona con el enlace puede ver'**.
        3. Verifica que la primera fila contenga los títulos de las columnas (ej: *Vendedor*, *Nombre*, *Clave*).
        """)
    
    elif len(vendedores_disponibles) == 0:
        st.warning("No se encontraron registros de vendedores en el archivo cargado.")
        
    else:
        # Modo edición visual
        if st.session_state.id_cotizacion_editar:
            st.warning(f"🔄 Editando la Cotización ID: {st.session_state.id_cotizacion_editar}")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Selector de Vendedor: Inicia vacío y filtra dinámicamente al escribir
            vendedor = st.selectbox(
                "Vendedor", 
                options=vendedores_disponibles,
                index=None,
                placeholder="Escribe para buscar vendedor..."
            )
            
        with col2:
            # Selector de Cliente: Permanece oculto/vacío hasta que se elija un vendedor
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

        # La sección de productos y guardado solo aparece si ambos campos están llenos
        if vendedor and cliente_info:
            fila_cliente = df_clientes[df_clientes['nombre'] == cliente_info].iloc[0]
            cve_cte = fila_cliente['clave']
            
            st.write("---")
            st.subheader(f"🛒 Productos para: {cliente_info} ({cve_cte})")
            
            col_prod, col_cant, col_btn = st.columns([3, 1, 1])
            with col_prod:
                cod_prod = st.text_input("Código de Producto")
            with col_cant:
                cant_prod = st.number_input("Cantidad", min_value=1, value=1)
            with col_btn:
                st.write("") 
                if st.button("Añadir"):
                    if cod_prod:
                        st.session_state.productos_actuales.append({
                            'codigo': cod_prod,
                            'cantidad': cant_prod
                        })
                        safe_rerun()

            if st.session_state.productos_actuales:
                df_tabla_actual = pd.DataFrame(st.session_state.productos_actuales)
                st.dataframe(df_tabla_actual, use_container_width=True)
                
                col_acciones = st.columns(2)
                with col_acciones[0]:
                    if st.button("💾 Guardar como Pendiente"):
                        if st.session_state.id_cotizacion_editar:
                            id_cot = st.session_state.id_cotizacion_editar
                            st.session_state.cotizaciones_guardadas[id_cot].update({
                                "productos": st.session_state.productos_actuales,
                                "vendedor": vendedor,
                                "cliente": cliente_info,
                                "cve_cte": cve_cte,
                                "fecha": datetime.now().strftime("%d/%m/%Y %H:%M")
                            })
                            st.success(f"Cotización {id_cot} actualizada.")
                        else:
                            id_cot = f"COT-{int(datetime.now().timestamp())}"
                            st.session_state.cotizaciones_guardadas[id_cot] = {
                                "vendedor": vendedor,
                                "cliente": cliente_info,
                                "cve_cte": cve_cte,
                                "productos": st.session_state.productos_actuales,
                                "estado": "Pendiente",
                                "fecha": datetime.now().strftime("%d/%m/%Y %H:%M")
                            }
                            st.success(f"Cotización guardada como pendiente (ID: {id_cot}).")
                        
                        st.session_state.productos_actuales = []
                        st.session_state.id_cotizacion_editar = None
                        safe_rerun()
                        
                with col_acciones[1]:
                    if st.button("❌ Cancelar / Limpiar"):
                        st.session_state.productos_actuales = []
                        st.session_state.id_cotizacion_editar = None
                        safe_rerun()
        else:
            st.write("---")
            if not vendedor:
                st.info("💡 Por favor, escribe o selecciona un Vendedor para desplegar sus clientes.")
            elif not cliente_info:
                st.info("💡 Ahora selecciona el Nombre del Cliente para habilitar el ingreso de artículos.")

# ------------------------------------------
# PESTAÑA 2: BANDEJA DE COTIZACIONES
# ------------------------------------------
with tab_bandeja:
    st.subheader("🗂️ Historial y Control de Estatus")
    
    if not st.session_state.cotizaciones_guardadas:
        st.info("No hay cotizaciones activas registradas en la bandeja.")
    else:
        for cot_id, datos in list(st.session_state.cotizaciones_guardadas.items()):
            marcador = "🟢" if datos['estado'] == "Autorizada" else "🟡"
            titulo = f"{marcador} {cot_id} | {datos['cliente']} | {datos['estado']} ({datos['fecha']})"
            
            with st.expander(titulo):
                df_items = pd.DataFrame(datos['productos'])
                st.dataframe(df_items, use_container_width=True)
                
                if datos['estado'] == "Pendiente":
                    col_b1, col_b2 = st.columns(2)
                    with col_b1:
                        if st.button("✏️ Modificar Cotización", key=f"mod_{cot_id}"):
                            st.session_state.productos_actuales = datos['productos']
                            st.session_state.id_cotizacion_editar = cot_id
                            st.info("Cargada. Pasa a la primera pestaña para editar los artículos.")
                            safe_rerun()
                    with col_b2:
                        if st.button("✅ Autorizar y Enviar a Pedido", key=f"aut_{cot_id}"):
                            folio_generado = obtener_siguiente_folio()
                            datos['estado'] = "Autorizada"
                            datos['folio_erp'] = folio_generado
                            st.success(f"¡Autorizada! Folio ERP: {folio_generado}")
                            safe_rerun()
                            
                elif datos['estado'] == "Autorizada":
                    st.success(f"Convertida en Pedido con Folio ERP: {datos['folio_erp']}")
                    excel_data = generar_excel_erp(df_items, datos['folio_erp'], datos['cve_cte'], "AGE01")
                    st.download_button(
                        label="📥 Descargar Layout de Pedido (Excel)",
                        data=excel_data,
                        file_name=f"Pedido_{datos['folio_erp']}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key=f"down_{cot_id}"
                    )