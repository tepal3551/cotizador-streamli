import streamlit as st
import pandas as pd
from datetime import datetime
import requests
from io import BytesIO
import os

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
# 3. FUNCIONES DE CARGA DE ARCHIVOS Y ERP
# ==========================================

@st.cache_data(ttl=300)
def cargar_clientes_sheets():
    sheet_id = '1QzmVhpIiwWN2Scz8J9_jn2GeLI2jIz2Mv5I6HDiKQVs'
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet=Clientes"
    df = pd.read_csv(url, dtype=str)
    df.columns = df.columns.astype(str).str.strip()
    df = df.fillna("")
    return df

@st.cache_data(ttl=300)
def cargar_catalogo():
    productos = {}
    
    # Función interna inteligente para leer los TXT saltándose el problema de las comas múltiples
    def procesar_archivo(ruta_archivo):
        if not os.path.exists(ruta_archivo):
            st.warning(f"⚠️ Archivo no encontrado: {ruta_archivo}")
            return
            
        # Intentamos leer en UTF-8 y si falla (común en Windows), usamos Latin-1
        try:
            with open(ruta_archivo, 'r', encoding='utf-8') as f:
                lineas = f.readlines()
        except UnicodeDecodeError:
            with open(ruta_archivo, 'r', encoding='latin-1') as f:
                lineas = f.readlines()
                
        for linea in lineas:
            linea = linea.strip()
            if not linea: 
                continue
            
            # Separamos por coma
            partes = linea.split(',')
            
            # Reconstruimos correctamente aunque la descripción tenga comas
            if len(partes) >= 3:
                codigo = partes[0].strip()
                precio = partes[-1].strip()
                descripcion = ",".join(partes[1:-1]).strip()
                
                # Si el código ya existía (ej. viene del archivo de actualizaciones), se sobrescribe su precio
                productos[codigo] = {
                    'codigo': codigo,
                    'descripcion': descripcion,
                    'precio': precio
                }

    # 1. Cargar catálogo principal
    procesar_archivo("CATALAGO 25 TRUP PRUEBA COTIZADOR.txt")
    
    # 2. Cargar actualización (reemplazará los precios de los códigos que coincidan)
    procesar_archivo("precios_actualizados.txt")
    
    if productos:
        return pd.DataFrame(list(productos.values()))
    else:
        return pd.DataFrame(columns=['codigo', 'descripcion', 'precio'])

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
# 4. INTERFAZ DE USUARIO PRINCIPAL
# ==========================================

st.title("🔩 Cotizador de Pedidos")

try:
    df_clientes = cargar_clientes_sheets()
    df_catalogo = cargar_catalogo()
    
    vendedores_disponibles = sorted([v for v in df_clientes['Nombre Vendedor'].unique() if str(v).strip() != ""])
    
    # Combinar variables para mostrar una lista atractiva en el buscador
    if not df_catalogo.empty:
        df_catalogo['mostrar_desplegable'] = df_catalogo['codigo'].astype(str) + " | " + df_catalogo['descripcion'].astype(str) + " | $" + df_catalogo['precio'].astype(str)
        opciones_productos = sorted(df_catalogo['mostrar_desplegable'].dropna().unique())
    else:
        opciones_productos = []

except Exception as e:
    st.error("Error al inicializar las bases de datos.")
    st.info(f"Detalle técnico: {e}")
    st.stop()

tab_crear, tab_bandeja = st.tabs(["📝 Crear / Editar Cotización", "🗂️ Bandeja de Cotizaciones"])

# ------------------------------------------
# PESTAÑA 1: CREAR / EDITAR COTIZACIÓN
# ------------------------------------------
with tab_crear:
    if len(vendedores_disponibles) == 0:
        st.warning("No se encontraron registros de vendedores.")
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
                lista_clientes = sorted([c for c in clientes_filtrados['Nombre Cliente'].unique() if str(c).strip() != ""])
                
                cliente_nombre = st.selectbox(
                    "Cliente", 
                    options=lista_clientes,
                    index=None,
                    placeholder="Escribe para buscar cliente..."
                )
            else:
                cliente_nombre = None

        if vendedor_nombre and cliente_nombre:
            fila_cliente = clientes_filtrados[clientes_filtrados['Nombre Cliente'] == cliente_nombre].iloc[0]
            id_cliente = str(fila_cliente['ID Cliente']).strip()
            id_vendedor = str(fila_cliente['ID Vendedor']).strip()
            
            st.write("---")
            st.subheader(f"🛒 Captura de Productos para: {cliente_nombre}")
            
            if len(opciones_productos) == 0:
                st.error("No se pudieron cargar los productos del catálogo. Verifica tus archivos TXT.")
            else:
                col_prod, col_cant, col_btn = st.columns([3, 1, 1])
                with col_prod:
                    prod_elegido = st.selectbox(
                        "Buscar Artículo (Código o Descripción)",
                        options=opciones_productos,
                        index=None,
                        placeholder="Escribe el código o nombre del producto..."
                    )
                with col_cant:
                    cant_prod = st.number_input("Cantidad", min_value=1, value=1)
                with col_btn:
                    st.write("") 
                    if st.button("Añadir"):
                        if prod_elegido:
                            fila_prod = df_catalogo[df_catalogo['mostrar_desplegable'] == prod_elegido].iloc[0]
                            st.session_state.productos_actuales.append({
                                'codigo': str(fila_prod['codigo']).strip(),
                                'descripcion': str(fila_prod['descripcion']).strip(),
                                'precio': str(fila_prod['precio']).strip(),
                                'cantidad': cant_prod
                            })
                            safe_rerun()

            if st.session_state.productos_actuales:
                df_tabla_actual = pd.DataFrame(st.session_state.productos_actuales)
                st.dataframe(df_tabla_actual[['codigo', 'descripcion', 'precio', 'cantidad']], use_container_width=True)
                
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
                st.info("💡 Selecciona un Vendedor de la lista para comenzar.")
            elif not cliente_nombre:
                st.info("💡 Selecciona el Cliente para habilitar el buscador desplegable de productos.")

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
                st.dataframe(df_items[['codigo', 'descripcion', 'precio', 'cantidad']], use_container_width=True)
                
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