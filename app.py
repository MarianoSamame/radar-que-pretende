import streamlit as st
import requests
import google.generativeai as genai
import pandas as pd
import json
import plotly.express as px
import plotly.graph_objects as go
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- LISTA ESTÁTICA DE CATEGORÍAS (MVP REDUCIDO - SIN AEROPUERTO) ---
CATEGORIAS_GOOGLE = [
    "Agencia de viajes", "Agencia inmobiliaria", "Alquiler de coches",
    "Banco", "Bar", "Bar de cócteles", "Biblioteca", "Bufete de abogados",
    "Café internet", "Cafetería", "Cajero automático", "Camping", "Carnicería",
    "Casino", "Centro comercial", "Centro de yoga", "Cervecería", "Chocolatería",
    "Cine", "Clínica dental", "Concesionario de coches", "Discoteca", "Escuela",
    "Espacio de coworking", "Estación de servicio", "Farmacia", "Ferretería", "Floristería",
    "Gimnasio", "Hamburguesería", "Heladería", "Hospital", "Hostal", "Hotel",
    "Hotel de lujo", "Lavadero de autos", "Librería",
    "Licorería", "Motel", "Panadería", "Parrilla", "Pastelería", "Peluquería",
    "Pescadería", "Pizzería", "Restaurante", "Restaurante chino",
    "Restaurante de comida rápida", "Restaurante italiano", "Restaurante japonés",
    "Restaurante mexicano", "Restaurante vegetariano", "Salón de belleza", "Spa", "Supermercado", "Taller mecánico",
    "Tienda de comestibles", "Tienda de conveniencia", "Tienda de deportes",
    "Tienda de electrónica", "Tienda de juguetes", "Tienda de mascotas",
    "Tienda de muebles", "Tienda de regalos", "Tienda de repuestos de automóviles",
    "Tienda de ropa", "Tienda de Vinos", "Verdulería", "Veterinaria",
    "Zapatería"
]
CATEGORIAS_GOOGLE.sort()

# --- CONFIGURACIÓN DE LA PÁGINA ---
st.set_page_config(page_title="Radar CX", layout="wide")

# --- GESTIÓN DE SECRETOS ---
try:
    GOOGLE_API_KEY = st.secrets["GOOGLE_API_KEY"]
    GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
    EMAIL_SENDER = st.secrets["EMAIL_SENDER"]
    EMAIL_PASSWORD = st.secrets["EMAIL_PASSWORD"]
except Exception as e:
    st.error("⚠️ Error: No se encontraron las API Keys configuradas en los Secretos.")
    st.stop()


# --- FUNCIONES DE NOTIFICACIÓN Y ARCHIVOS ---
def enviar_notificacion(usuario_email, tipo_busqueda, detalle, radio, coordenadas):
    destinatario = "Mnsamame@gmail.com"
    asunto = f"🔔 Nuevo Lead Radar CX: {tipo_busqueda}"
    mensaje = f"""
    Hola Matías,
    Un nuevo usuario ha ejecutado una auditoría.

    👤 Email: {usuario_email}
    🔍 Tipo: {tipo_busqueda}
    🏢 Detalle: {detalle}
    📍 Ubicación: {coordenadas}
    📏 Radio: {radio} km
    """
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_SENDER
        msg['To'] = destinatario
        msg['Subject'] = asunto
        msg.attach(MIMEText(mensaje, 'plain'))
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        text = msg.as_string()
        server.sendmail(EMAIL_SENDER, destinatario, text)
        server.quit()
        return True
    except Exception as e:
        print(f"Error mail: {e}")
        return False


def cargar_reseñas_archivo(file):
    try:
        if file.name.endswith('.csv'):
            df = pd.read_csv(file)
        else:
            df = pd.read_excel(file)
        cols = [c.lower() for c in df.columns]
        target_col = None
        posibles_nombres = ['comentario', 'review', 'opinión', 'opinion', 'texto', 'feedback', 'mensaje']
        for candidato in posibles_nombres:
            matches = [c for c in cols if candidato in c]
            if matches:
                target_col = df.columns[cols.index(matches[0])]
                break
        if target_col:
            return df[target_col].dropna().astype(str).tolist()
        else:
            return []
    except:
        return []


# --- FUNCIONES API GOOGLE ---

def buscar_candidatos_negocio(query, api_key):
    """Búsqueda por nombre de negocio (Modo 1)"""
    url = "https://places.googleapis.com/v1/places:searchText"
    headers = {"Content-Type": "application/json", "X-Goog-Api-Key": api_key,
               "X-Goog-FieldMask": "places.displayName,places.formattedAddress"}
    data = {"textQuery": query, "pageSize": 5, "languageCode": "es"}
    try:
        return requests.post(url, headers=headers, json=data).json().get('places', [])
    except:
        return []


def validar_direccion(direccion_input, api_key):
    url = "https://places.googleapis.com/v1/places:searchText"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "places.formattedAddress,places.location"
    }
    data = {"textQuery": direccion_input, "pageSize": 1, "languageCode": "es"}
    try:
        resp = requests.post(url, headers=headers, json=data)
        lugares = resp.json().get('places', [])
        if lugares: return lugares[0]
        return None
    except:
        return None


def buscar_mercado_por_rubro(lat, lng, rubro, radio_km, api_key):
    """
    Trae DETALLE de los primeros 20 para análisis cualitativo.
    """
    url = "https://places.googleapis.com/v1/places:searchText"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.rating,places.userRatingCount,places.reviews,places.primaryTypeDisplayName,places.googleMapsUri,places.location,places.editorialSummary,places.priceLevel,places.websiteUri"
    }

    radio_metros = radio_km * 1000.0
    parametros = {
        "textQuery": rubro,
        "pageSize": 20,
        "languageCode": "es",
        "locationBias": {
            "circle": {
                "center": {"latitude": lat, "longitude": lng},
                "radius": radio_metros
            }
        }
    }
    try:
        resp = requests.post(url, headers=headers, json=parametros)
        return resp.json().get('places', [])
    except:
        return []


def buscar_detalle_target_y_competencia(lugar_seleccionado, radio_km, api_key):
    nombre = lugar_seleccionado['displayName']['text']
    direccion = lugar_seleccionado['formattedAddress']

    url = "https://places.googleapis.com/v1/places:searchText"
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.rating,places.userRatingCount,places.reviews,places.primaryTypeDisplayName,places.googleMapsUri,places.location,places.editorialSummary,places.priceLevel,places.websiteUri"
    }
    resp_target = requests.post(url, headers=headers,
                                json={"textQuery": f"{nombre} {direccion}", "pageSize": 1, "languageCode": "es"})

    data_target = resp_target.json().get('places', [])
    if not data_target: return None, None, None

    target_obj = data_target[0]
    rubro = target_obj.get('primaryTypeDisplayName', {}).get('text', 'Comercio')
    loc = target_obj.get('location', {})

    mercado = buscar_mercado_por_rubro(loc['latitude'], loc['longitude'], rubro, radio_km, api_key)

    return target_obj, mercado, rubro


# --- FUNCIONES IA (GEMINI) ---

def generar_resumenes_batch(lista_negocios, api_key):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.0-flash', generation_config={"response_mime_type": "application/json"})
    prompt = "Analiza opiniones y resume en 1 frase (máx 20 palabras) cada ítem.\n\n"
    mapa = {}
    for i, neg in enumerate(lista_negocios):
        nom = neg.get('displayName', {}).get('text')
        revs = " | ".join([r.get('text', {}).get('text', '') for r in neg.get('reviews', [])][:5])
        pid = f"ID_{i}"
        prompt += f"ITEM {pid} ({nom}): {revs or '(Sin datos)'}\n"
        mapa[pid] = nom
    prompt += "OUTPUT JSON: { 'ID_0': '...', ... }"
    try:
        res = json.loads(model.generate_content(prompt).text)
        if isinstance(res, list): res = {k: v for i in res for k, v in i.items()}
        return {mapa[k]: v for k, v in res.items() if k in mapa}
    except:
        return {}


def analizar_distribucion_topicos(texto, rubro, api_key):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.0-flash', generation_config={"response_mime_type": "application/json"})
    prompt = f"""
    Analiza reseñas de {rubro}:
    {texto[:15000]} 
    Clasifica en 3 categorías y da % de Share of Voice.
    1. Calidad (Producto/Servicio).
    2. Conveniencia (Precio/Valor).
    3. Atención (Servicio al cliente).
    OUTPUT JSON: {{ "Calidad": int, "Conveniencia": int, "Atención": int }}
    """
    default_data = {"Calidad": 33, "Conveniencia": 33, "Atención": 34}
    try:
        response = model.generate_content(prompt)
        parsed = json.loads(response.text)
        if isinstance(parsed, list):
            if len(parsed) > 0 and isinstance(parsed[0], dict):
                return parsed[0]
            else:
                return default_data
        elif isinstance(parsed, dict):
            return parsed
        else:
            return default_data
    except:
        return default_data


def generar_analisis_exhaustivo(texto_mercado, texto_lideres, rubro, api_key):
    """
    Genera el reporte ejecutivo.
    CAMBIOS:
    - Matriz con formato de lista de acciones (1. Empezar mañana...).
    - Títulos más chicos.
    - Sin emojis en la matriz.
    - Basado 100% en evidencia del texto.
    """
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.0-flash', generation_config=genai.GenerationConfig(temperature=0.15))

    prompt = f"""
    ROL: Estratega de Negocios Senior.
    OBJETIVO: Decodificar el consumidor de **{rubro}** y definir prioridades basadas EXCLUSIVAMENTE en la evidencia leída.

    DATOS:
    [MERCADO]: {texto_mercado[:22000]}
    [LÍDERES]: {texto_lideres}

    ---
    INSTRUCCIONES DE ESTILO:
    1. EMOJIS: Solo permitidos en los títulos principales (##). PROHIBIDOS en el resto.
    2. FORMATO: Markdown profesional.
    3. FUENTE: No inventes consejos genéricos. Si recomiendas algo, debe ser porque lo leíste en las reseñas.

    ---
    ESTRUCTURA DEL REPORTE:

    ## 🧠 Psicología del Consumidor

    * **Lo que obsesiona al cliente (Valores Positivos):** (Qué genera euforia según las reseñas).
    * **Lo que irrita al cliente (Fricciones Reales):** (Qué quejas se repiten).

    ### 🔥 Los 3 Motores de Decisión
    1.  **[Driver 1]**: Explicación.
    2.  **[Driver 2]**: Explicación.
    3.  **[Driver 3]**: Explicación.

    ## 🏆 Benchmarking: Lecciones de los Líderes
    *(Usa la info de LÍDERES. Si no hay, indícalo).*

    ### [Nombre del Negocio]
    * **Por qué gana:** (Propuesta de valor).
    * **Precios:** (Percepción del cliente).
    * **Clave del éxito:** (Aprendizaje).

    ### 💎 Hallazgo de Nicho
    * **Insight:** [Detalle sutil valorado en la zona].

    ## 🚀 Matriz de Priorización (Basada en Reseñas)

    * **1. Empezar mañana [imperativo]:** (Cuál es la queja más grave y frecuente en la zona que se debe resolver YA. Sé específico).

    * **2. Priorizar en las próximas semanas [diferencial]:** (Qué característica de los líderes es la que más envidian los clientes y deberíamos copiar).

    * **3. No atender por ahora [ahorrar esfuerzo]:** (Menciona algo que los dueños suelen creer importante, pero que en estas reseñas NADIE mencionó o valoró. Ayuda a no gastar dinero en vano).
    """

    try:
        response = model.generate_content(prompt)
        return response.text.replace("```markdown", "").replace("```", "").strip()
    except Exception as e:
        return f"Error: {e}"


def analizar_brecha_mercado_vs_archivo(texto_mercado, reviews_propias, nombre, rubro, api_key):
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-2.0-flash', generation_config=genai.GenerationConfig(temperature=0.2))
    prompt = f"""
    Auditor CX Gap Analysis para {nombre}.
    Mercado: {texto_mercado[:10000]}
    Negocio: {" | ".join(reviews_propias[:500])}

    Regla Ponderación: <10% quejas = ✅, 10-30% = ⚠️, >30% = ❌.

    Reporte Markdown:
    ## ⚖️ Auditoría: Realidad vs Expectativa
    ### 1. Matriz Cumplimiento
    | Exigencia | Desempeño (Resumen + 1 Cita) | Veredicto |
    | :--- | :--- | :--- |
    | [Exigencia 1] | ... | ... |
    | [Exigencia 2] | ... | ... |
    ### 2. Análisis
    * Fortaleza: ...
    * Mejora: ...
    ### 3. Veredicto Final
    Alineado/Desalineado porque...
    """
    try:
        texto = model.generate_content(prompt).text
        return texto.replace("```markdown", "").replace("```", "").strip()
    except Exception as e:
        return f"Error: {e}"


# --- INTERFAZ ---
with st.sidebar:
    st.header("🔐 Acceso")
    st.info("Ingresa tu correo para desbloquear.")
    email_usuario = st.text_input("Tu Email", placeholder="usuario@empresa.com")
    # YA NO HAY UPLOADER ACÁ

st.title("📊 Qué pretende usted de mí?")
# CAMBIO 1: NUEVO TEXTO
st.markdown("Radar de expectativas de mercado y experiencia de clientes.")

if not email_usuario or "@" not in email_usuario:
    st.warning("👈 Ingresa tu email en la barra lateral para comenzar.")
    st.stop()

# ESTADO
if 'resultados_busqueda' not in st.session_state: st.session_state.resultados_busqueda = None
if 'modo_seleccionado' not in st.session_state: st.session_state.modo_seleccionado = None
if 'direccion_validada' not in st.session_state: st.session_state.direccion_validada = None

# Variable global para el archivo
uploaded_file = None

tab1, tab2 = st.tabs(["🏢 Búsqueda por Negocio", "📍 Búsqueda por Rubro"])

with tab1:
    col_a, col_b, col_c = st.columns([3, 1, 1])
    # CAMBIO 3: PLACEHOLDER EJEMPLO
    with col_a:
        q_negocio = st.text_input("Nombre del Negocio",
                                  placeholder="Ej: Panadería Antojos de Poeta, barrio Poeta Lugones")
    with col_b:
        r_negocio = st.number_input("Radio (km)", 0.1, 10.0, 2.5, 0.5, key="r1")
    with col_c:
        st.write("")
        st.write("")
        # CAMBIO BOTÓN UNIFICADO
        btn_buscar_negocio = st.button("🚀 Iniciar radar de competencia", use_container_width=True,
                                       key="btn_radar_negocio")

    # CAMBIO 2: UPLOADER EN TAB 1
    st.divider()
    uploaded_file = st.file_uploader(
        "Subí un listado de reseñas propio y descubrí cómo tu negocio se adapta a las expectativas del mercado (opcional).",
        type=["csv", "xlsx"])

    if btn_buscar_negocio and len(q_negocio) > 2:
        with st.spinner("Buscando..."):
            res = buscar_candidatos_negocio(q_negocio, GOOGLE_API_KEY)
            st.session_state.resultados_busqueda = res
            st.session_state.modo_seleccionado = "negocio"
            st.session_state.direccion_validada = None
            if not res: st.error("No se encontraron resultados.")

with tab2:
    col_x, col_y, col_z, col_w = st.columns([3, 2, 1, 1])
    with col_x:
        dir_input = st.text_input("Dirección Central", placeholder="Ej: Av. Colón 5000, Córdoba")
    with col_y:
        # MULTISELECT SIN DEFAULT
        rubros_input = st.multiselect(
            "Categorías del Negocio",
            CATEGORIAS_GOOGLE,
            default=None,  # Vacío por defecto
            placeholder="Elige una o más..."
        )
    with col_z:
        r_rubro = st.number_input("Radio (km)", 0.1, 10.0, 2.0, 0.5, key="r2")
    with col_w:
        st.write("")
        st.write("")
        # CAMBIO BOTÓN UNIFICADO
        btn_validar_rubro = st.button("🚀 Iniciar radar de competencia", use_container_width=True, key="btn_radar_rubro")

    if btn_validar_rubro and len(dir_input) > 5 and rubros_input:
        with st.spinner("Validando dirección..."):
            ubicacion_obj = validar_direccion(dir_input, GOOGLE_API_KEY)
            if ubicacion_obj:
                st.session_state.direccion_validada = ubicacion_obj
                st.session_state.resultados_busqueda = None
                st.session_state.modo_seleccionado = "rubro"
                st.session_state.rubro_actual = rubros_input
                st.success(f"📍 Dirección validada: {ubicacion_obj['formattedAddress']}")
            else:
                st.error("No se pudo validar esa dirección.")
    elif btn_validar_rubro and not rubros_input:
        st.warning("⚠️ Debes seleccionar al menos una categoría.")

exec_params = None

# LÓGICA DE EJECUCIÓN (CON LOS BOTONES YA PRESIONADOS ARRIBA O CONFIRMACIÓN)
# Nota: La lógica anterior tenía un segundo botón "Iniciar Auditoría" después de validar.
# Vamos a mantener ese flujo pero con el texto nuevo.

if st.session_state.modo_seleccionado == "negocio" and st.session_state.resultados_busqueda:
    st.divider()
    opts = {f"{c['displayName']['text']} - {c.get('formattedAddress', '')}": c for c in
            st.session_state.resultados_busqueda}
    sel = st.selectbox("Selecciona tu negocio:", list(opts.keys()))
    if st.button("Confirmar y Analizar", type="primary", key="btn_conf_neg"):
        exec_params = {"type": "negocio", "data": opts[sel], "radio": r_negocio}

if st.session_state.modo_seleccionado == "rubro" and st.session_state.direccion_validada:
    st.divider()
    rubros_str_user = ", ".join(st.session_state.rubro_actual)
    st.info(f"Analizando **{rubros_str_user}** en radio de **{r_rubro} km**.")
    if st.button("Confirmar y Analizar", type="primary", key="btn_conf_rubro"):
        exec_params = {"type": "rubro", "data": st.session_state.direccion_validada,
                       "rubro": st.session_state.rubro_actual, "radio": r_rubro}

if exec_params:
    with st.spinner("🤖 Activando satélites e IA..."):
        target_obj = None
        mercado_data = []
        rubro_final_str = ""
        lat_central = 0
        lng_central = 0

        # 1. OBTENCIÓN DE DATOS
        if exec_params["type"] == "negocio":
            target_obj, mercado_data, rubro_detectado = buscar_detalle_target_y_competencia(
                exec_params["data"], exec_params["radio"], GOOGLE_API_KEY
            )
            rubro_final_str = rubro_detectado
            det = f"Negocio: {target_obj.get('displayName', {}).get('text')}"
            lat_central = target_obj['location']['latitude']
            lng_central = target_obj['location']['longitude']

        elif exec_params["type"] == "rubro":
            loc = exec_params["data"]["location"]
            lista_rubros = exec_params["rubro"]
            rubro_final_str = " o ".join(lista_rubros)

            lat_central = loc['latitude']
            lng_central = loc['longitude']

            mercado_data = buscar_mercado_por_rubro(
                lat_central, lng_central, rubro_final_str, exec_params["radio"], GOOGLE_API_KEY
            )
            target_obj = None
            det = f"Rubros: {rubro_final_str} en {exec_params['data']['formattedAddress']}"

        if not mercado_data:
            st.error("No se encontró información suficiente.")
            st.stop()

        # Enviar Mail
        coord_m = f"{lat_central},{lng_central}"
        enviar_notificacion(email_usuario, exec_params["type"], det, exec_params["radio"], coord_m)

        # UNIFICAR LISTA VISUAL
        lista_final = []
        vistos = set()
        if target_obj:
            lista_final.append(target_obj)
            vistos.add(target_obj.get('formattedAddress'))
        for m in mercado_data:
            if m.get('formattedAddress') not in vistos:
                lista_final.append(m)
                vistos.add(m.get('formattedAddress'))

        lista_visual = lista_final[:15]

        # LÍDERES
        candidatos_lideres = [m for m in mercado_data if m.get('userRatingCount', 0) >= 100]
        candidatos_lideres.sort(key=lambda x: x.get('rating', 0), reverse=True)
        top_lideres = candidatos_lideres[:3]

        texto_lideres = ""
        if top_lideres:
            for i, l in enumerate(top_lideres):
                nom = l.get('displayName', {}).get('text', 'N/A')
                rt = l.get('rating', 0)
                cnt = l.get('userRatingCount', 0)
                desc = l.get('editorialSummary', {}).get('text', 'Sin descripción.')
                precio = l.get('priceLevel', 'N/A')
                revs = " ".join([r.get('text', {}).get('text', '') for r in l.get('reviews', [])][:3])

                texto_lideres += f"""
                [LÍDER {i + 1}]
                Nombre: {nom}
                Rating: {rt} ({cnt} reviews)
                Descripción: {desc}
                Precio: {precio}
                Opiniones recientes: {revs}
                """
        else:
            texto_lideres = "No hay líderes consolidados."

        # TEXTO MERCADO
        texto_mercado = ""
        t_name = target_obj.get('displayName', {}).get('text') if target_obj else "Tu Negocio"
        for neg in lista_visual:
            n_n = neg.get('displayName', {}).get('text')
            if target_obj and n_n == t_name: continue
            rs = [r.get('text', {}).get('text', '') for r in neg.get('reviews', [])]
            if rs: texto_mercado += f"COMPETIDOR ({n_n}): {' '.join(rs)}\n\n"

        # IA
        resumenes = {}
        if GEMINI_API_KEY:
            resumenes = generar_resumenes_batch(lista_visual, GEMINI_API_KEY)
            analisis_experto = generar_analisis_exhaustivo(texto_mercado, texto_lideres, rubro_final_str,
                                                           GEMINI_API_KEY)
            dist_topicos = analizar_distribucion_topicos(texto_mercado, rubro_final_str, GEMINI_API_KEY)

        # DATAFRAME
        df_data = []
        for n in lista_visual:
            nom = n.get('displayName', {}).get('text')
            tipo = "MI NEGOCIO" if (target_obj and nom == t_name) else "COMPETENCIA"
            df_data.append({
                "Negocio": nom,
                "Rating": n.get('rating', 0.0),
                "Opiniones": n.get('userRatingCount', 0),
                "Tipo": tipo,
                "Resumen IA": resumenes.get(nom, "Analizando..."),
                "Link": n.get('googleMapsUri', '#'),
                "Rating_Visual": max(n.get('rating', 0.0), 3.5)
            })
        df = pd.DataFrame(df_data).sort_values("Rating", ascending=False)

        # A) TABLA
        st.divider()
        st.subheader(f"📍 Radar de Mercado: {rubro_final_str}")
        st.dataframe(df[["Negocio", "Rating", "Opiniones", "Resumen IA", "Link"]],
                     column_config={"Link": st.column_config.LinkColumn("Maps", display_text="Ver"),
                                    "Rating": st.column_config.NumberColumn("⭐", format="%.1f")},
                     hide_index=True, use_container_width=True)

        # --- SECCIÓN DE MÉTRICAS (KPIs) ---

        total_negocios = len(lista_visual)
        suma_rating = 0
        suma_ponderada = 0
        total_reviews = 0
        total_reviews_analizadas = 0

        for n in lista_visual:
            rt = n.get('rating', 0)
            cnt = n.get('userRatingCount', 0)
            revs_disponibles = len(n.get('reviews', []))

            suma_rating += rt
            suma_ponderada += (rt * cnt)
            total_reviews += cnt
            total_reviews_analizadas += revs_disponibles

        prom_simple = suma_rating / total_negocios if total_negocios > 0 else 0
        prom_ponderado = suma_ponderada / total_reviews if total_reviews > 0 else 0

        label_negocios = f"{total_negocios}"
        if total_negocios >= 20: label_negocios = "20 (Máx. API)"

        st.markdown("##### 🔢 Métricas de la Muestra")
        k1, k2, k3, k4, k5 = st.columns(5)

        with k1:
            st.metric("Negocios en Radar", label_negocios,
                      help="Cantidad de negocios encontrados en el radio (Top 20 por relevancia).")
        with k2:
            st.metric("Rating Promedio", f"{prom_simple:.2f} ⭐", help="Promedio simple de calificaciones.")
        with k3:
            st.metric("Rating Ponderado", f"{prom_ponderado:.2f} ⭐",
                      help="Promedio considerando el volumen de reseñas (da más peso a negocios con más opiniones).")
        with k4:
            st.metric("Volumen Histórico", f"{total_reviews:,}",
                      help="Suma total de reseñas históricas de estos negocios.")
        with k5:
            st.metric("Reseñas Analizadas", f"{total_reviews_analizadas}",
                      help="Cantidad de textos de reseñas leídos por la IA para este análisis.")

        # B) GRÁFICOS
        st.divider()
        c1, c2 = st.columns([2, 1])
        with c1:
            st.markdown("#### 🎯 Mapa de Calidad vs. Madurez")
            # CAMBIO: GRÁFICO MEJORADO YAXIS
            fig = px.scatter(df, x="Opiniones", y="Rating_Visual", color="Tipo", text="Negocio", log_x=True,
                             color_discrete_map={"MI NEGOCIO": "#1E88E5", "COMPETENCIA": "#90A4AE"},
                             template='plotly_white')  # TEMPLATE BLANCO

            fig.update_traces(textposition='top center', marker=dict(size=12, line=dict(width=1, color='gray')))
            # AUMENTO RANGO Y PARA QUE ENTREN ETIQUETAS DE 5 ESTRELLAS
            fig.update_layout(height=400, yaxis=dict(range=[3.0, 5.4]), margin=dict(t=50, l=20, r=20, b=20))
            st.plotly_chart(fig, use_container_width=True)

        with c2:
            st.markdown("#### 🗣️ Share of Voice")
            if isinstance(dist_topicos, list): dist_topicos = dist_topicos[0] if len(dist_topicos) > 0 else {}
            labels, values = list(dist_topicos.keys()), list(dist_topicos.values())
            fig_pie = go.Figure(data=[
                go.Pie(labels=labels, values=values, hole=.4, marker=dict(colors=["#66BB6A", "#FFA726", "#42A5F5"]))])
            fig_pie.update_layout(height=400, showlegend=True, legend=dict(orientation="h", y=-0.2))
            st.plotly_chart(fig_pie, use_container_width=True)

        # C) REPORTE
        st.divider()
        st.markdown("## 🧠 Inteligencia de Mercado")
        st.markdown(analisis_experto)

        # D) AUDITORÍA
        if uploaded_file:
            st.divider()
            st.markdown(f"## ⚖️ Auditoría Privada")
            with st.spinner("Auditando..."):
                rp = cargar_reseñas_archivo(uploaded_file)
                if rp:
                    st.markdown(analizar_brecha_mercado_vs_archivo(texto_mercado, rp, "Tu Archivo", rubro_final_str,
                                                                   GEMINI_API_KEY))
                else:
                    st.error("Archivo inválido.")

        st.success("Análisis completado.")