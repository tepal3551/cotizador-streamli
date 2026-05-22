import streamlit as st
import pandas as pd
from datetime import datetime
import requests
from io import BytesIO

# ==========================================
# 1. FUNCIÓN SEGURA DE RECARGA
# ==========================================
def safe_rerun():
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
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet=Clientes"
    
    # 🛡️ BLINDAJE: dtype=str obliga a que TODO sea texto. fillna("") elimina los "NaN" vacíos.
    df = pd.read_csv(url, dtype=str)
    df.columns = df.columns.astype(str).str.strip()
    df = df.fillna("")
    return df

def obtener_siguiente_folio():
    try:
        response = requests.get("https://servidor-pedidos.onrender.com")
        return response.text.strip()
    except:
        return "0000"

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
            "lugar": "A2"
        })
    
    df_final = pd.DataFrame(filas)
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        df_final.to_excel(writer, index=False)
    return buffer.getvalue()

# ==========================================
# 4. INTERFAZ DE USUARIO 
# ==========================================

st.title("🔩 Cotizador de Pedidos")

try:
    df_clientes = cargar_clientes_sheets()
    # Filtramos celdas que estén realmente vacías después de la limpieza
    lista_vendedores = [v for v in df_clientes['Nombre Vendedor'].unique() if str(v).strip() != ""]
    vendedores_disponibles = sorted(lista_vendedores)
except Exception as e:
    st.error("Error al leer el archivo de Google Sheets.")
    st.info(f"Detalle técnico: {e}")
    st.stop()

tab_crear, tab_bandeja = st.tabs(["📝 Crear / Editar Cotización", "🗂️ Bandeja de Cotizaciones"])

# ------------------------------------------
# PESTAÑA 1: CREAR / EDITAR COTIZACIÓN
# ------------------------------------------
with tab_crear:
    if len(vendedores_disponibles) == 0:
        st.warning("No se encontraron registros de vendedores en el archivo.")
    else:
        if st.session_state.id_cotizacion_editar:
            st.warning(f"🔄 Editando la Cotización ID: {st.session_state.id_cotizacion_editar}")
        
        col1, col2 = st.columns(2)
        
        with col1:
            vendedor_nombre = st.selectbox(
                "Vendedor", 
                options=vendedores_disponibles,
                index=None,
                placeholder="Escribe para buscar vendedor..."
            )
            
        with col2:
            if vendedor_nombre:
                clientes_filtrados = df_clientes[df_clientes['Nombre Vendedor'] == vendedor_nombre]
                lista_clientes = [c for c in clientes_filtrados['Nombre Cliente'].unique() if str(c).strip() != ""]
                
                cliente_nombre = st.selectbox(
                    "Cliente", 
                    options=sorted(lista_clientes),
                    index=None,
                    placeholder="Escribe para buscar cliente..."
                )
            else:
                cliente_nombre = None

        if vendedor_nombre and cliente_nombre:
            fila_cliente = clientes_filtrados[clientes_filtrados['Nombre Cliente'] == cliente_nombre].iloc[0]
            # Aseguramos que los IDs se extraigan limpios
            id_cliente = str(fila_cliente['ID Cliente']).strip()
            id_vendedor = str(fila_cliente['ID Vendedor']).strip()
            
            st.write("---")
            st.subheader(f"🛒 Productos para: {cliente_nombre} (ID: {id_cliente})")
            
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
                                "vendedor_nombre": vendedor_nombre,
                                "cliente_nombre": cliente_nombre,
                                "id_cliente": id_cliente,
                                "id_vendedor": id_vendedor,
                                "fecha": datetime.now().strftime("%d/%m/%Y %H:%M")
                            })
                            st.success(f"Cotización {id_cot} actualizada.")
                        else:
                            id_cot = f"COT-{int(datetime.now().timestamp())}"
                            st.session_state.cotizaciones_guardadas[id_cot] = {
                                "vendedor_nombre": vendedor_nombre,
                                "cliente_nombre": cliente_nombre,
                                "id_cliente": id_cliente,
                                "id_vendedor": id_vendedor,
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
            if not vendedor_nombre:
                st.info("💡 Por favor, selecciona un Vendedor de la lista.")
            elif not cliente_nombre:
                st.info("💡 Ahora selecciona el Cliente para habilitar el ingreso de artículos.")

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
            titulo = f"{marcador} {cot_id} | Cliente: {datos['cliente_nombre']} | {datos['estado']} ({datos['fecha']})"
            
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
                    excel_data = generar_excel_erp(
                        df_items, 
                        datos['folio_erp'], 
                        datos['id_cliente'], 
                        datos['id_vendedor']
                    )
                    st.download_button(
                        label="📥 Descargar Layout de Pedido (Excel)",
                        data=excel_data,
                        file_name=f"Pedido_{datos['folio_erp']}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        key=f"down_{cot_id}"
                    )