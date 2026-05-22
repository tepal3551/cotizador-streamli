import streamlit as st

import pandas as pd

from datetime import datetime

from fpdf import FPDF

from urllib.parse import quote_plus

import re

import requests

from io import BytesIO



# ==========================================

# 1. FUNCIONES AUXILIARES Y ERP

# ==========================================



@st.cache_data(ttl=300)

def cargar_clientes_sheets():

    # URL de tu Google Sheet (Asegúrate de que sea "Publicar en la web" como CSV)

    sheet_id = '1QzmVhpIiwWN2Scz8J9_jn2GeLI2jIz2Mv5I6HDiKQVs'

    return pd.read_csv(url)



def obtener_siguiente_folio():

    # Simulación de la llamada a tu API de Render para el consecutivo

    try:

        response = requests.get("https://servidor-pedidos.onrender.com")

        return response.text.strip()

    except:

        return "0000" # Fallback



def generar_excel_erp(df_cot, folio, cve_cte, cve_age):

    # Formato solicitado basado en archivo 1253

    filas = []

    for _, row in df_cot.iterrows():

        filas.append({

            "no_ped": folio,

            "cve_prod": row['codigo'],

            "cant_prod": row['cantidad'],

            "cve_cte": cve_cte,

            "cve_age": cve_age,

            "cve_suc": "1",

            "cve_mon": "P",

            "lugar": "A2"

        })

    df_final = pd.DataFrame(filas)

    buffer = BytesIO()

    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:

        df_final.to_excel(writer, index=False)

    return buffer.getvalue()



# ==========================================

# 2. INTERFAZ PRINCIPAL

# ==========================================



# ... (Mantén tus funciones de cargar_catalogo y generar_pdf aquí) ...



st.title("🔩 Cotizador de Pedidos")



# Selector de Vendedor y Cliente cargado de Sheets

df_clientes = cargar_clientes_desde_sheets()

vendedor = st.selectbox("Vendedor", df_clientes['vendedor'].unique())

cliente_info = st.selectbox("Cliente", df_clientes[df_clientes['vendedor'] == vendedor]['nombre'])

cve_cte = df_clientes[df_clientes['nombre'] == cliente_info]['clave'].iloc[0]



# ... (Tu lógica de agregar productos) ...



if st.session_state.cotizacion:

    # ... (Tabla actual) ...

   

    st.subheader("🚀 Finalizar Pedido")

    if st.button("Generar Pedido para ERP (Excel)"):

        folio = obtener_siguiente_folio()

        excel_data = generar_excel_erp(df_cot, folio, cve_cte, "AGE01")

        st.download_button("Descargar Excel ERP", data=excel_data, file_name=f"Pedido_{folio}.xlsx")

        st.success(f"Folio generado: {folio}")



    # Tu botón de PDF y WhatsApp original

    # 