import requests
import json
import time

# --- CONFIGURACIÓN ---
API_KEY = "AIzaSyD0o-zuTp7VZFKiBQs3qKuionxMQPmdKZo"  # <--- TU API KEY
TARGET_BUSINESS = "Antojos de Poeta, Córdoba"  # Tu cliente
MERCADO_QUERY = "Panaderías en Barrio Poeta Lugones, Córdoba"  # El "Enjambre"


# --- FUNCIONES ---

def buscar_negocios(query, api_key, max_resultados=10):
    """ Busca negocios y devuelve una lista con sus detalles y reseñas """
    url = "https://places.googleapis.com/v1/places:searchText"

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        # Pedimos el nombre, rating y las reseñas
        "X-Goog-FieldMask": "places.displayName,places.formattedAddress,places.rating,places.userRatingCount,places.reviews,places.primaryTypeDisplayName"
    }

    data = {
        "textQuery": query,
        "pageSize": max_resultados  # Pedimos 10 competidores
    }

    print(f"📡 Consultando API para: '{query}'...")
    response = requests.post(url, headers=headers, json=data)

    if response.status_code == 200:
        return response.json().get('places', [])
    else:
        print(f"❌ Error: {response.status_code} - {response.text}")
        return []


def generar_mega_prompt(target, competidores):
    """ Genera el prompt estratégico cruzando Identidad vs. Mercado """

    # 1. Procesar datos del CLIENTE (Target)
    nombre_cliente = target.get('displayName', {}).get('text', 'N/A')
    tipo_cliente = target.get('primaryTypeDisplayName', {}).get('text', 'N/A')
    reviews_cliente = target.get('reviews', [])

    texto_cliente_reviews = ""
    for r in reviews_cliente:
        texto_cliente_reviews += f"- \"{r.get('text', {}).get('text', '')}\"\n"

    # 2. Procesar datos del MERCADO (Competidores)
    print(f"📊 Procesando {len(competidores)} competidores para extraer expectativas...")

    bolsa_de_reseñas = ""
    contador_total = 0

    for negocio in competidores:
        nombre = negocio.get('displayName', {}).get('text', 'Anónimo')
        reviews = negocio.get('reviews', [])

        # Agregamos las reseñas de este competidor a la "bolsa" general
        for r in reviews:
            texto = r.get('text', {}).get('text', '')
            if texto:  # Solo si tiene texto
                bolsa_de_reseñas += f"- [{nombre}]: \"{texto}\"\n"
                contador_total += 1

    # 3. Construir el Prompt Final
    print(f"✅ ¡Éxito! Se recolectaron {contador_total} reseñas relevantes del mercado.")
    print("\n" + "=" * 60)
    print("🧠 COPIA ESTE PROMPT PARA GEMINI / CHATGPT")
    print("=" * 60)

    prompt = f"""
    ACTÚA COMO ANALISTA DE CUSTOMER EXPERIENCE (CX).

    OBJETIVO: Determinar si la Propuesta de Valor del negocio "{nombre_cliente}" cumple con las Expectativas Reales del Mercado.

    ---
    PARTE 1: LA PROPUESTA DE VALOR (Deducida de su huella digital)
    Negocio: {nombre_cliente} ({tipo_cliente})
    Lo que dicen sus propios clientes (Top 5 reviews):
    {texto_cliente_reviews}

    --> TAREA A: Basado en esto, define en 1 frase cuál es la "Promesa de Marca" actual de {nombre_cliente}.

    ---
    PARTE 2: LAS EXPECTATIVAS DEL MERCADO (La Voz del "Enjambre")
    He analizado {len(competidores)} negocios similares en la misma zona. Aquí tienes {contador_total} opiniones reales de clientes de la competencia:

    {bolsa_de_reseñas}

    --> TAREA B: Ignora las quejas puntuales. Encuentra los 3 "Patrones de Expectativa" (¿Qué es lo que MÁS valora o castiga el cliente de esta zona en general?).

    ---
    PARTE 3: EL VEREDICTO (Gap Analysis)
    Cruza la "Promesa de Marca" (Parte 1) con las "Expectativas del Mercado" (Parte 2).

    Responde en una Tabla:
    | Expectativa del Mercado | ¿Antojos de Poeta lo cubre? | Veredicto (Oportunidad o Riesgo) |
    |-------------------------|-----------------------------|----------------------------------|
    | (Ej: Velocidad)         | (Ej: No, es lento)          | (Ej: Riesgo Alto)                |
    """

    print(prompt)


# --- EJECUCIÓN ---
if __name__ == "__main__":
    if API_KEY == "PEGA_TU_API_KEY_AQUI":
        print("⚠️ ERROR: Falta tu API Key.")
    else:
        # Paso 1: Buscar datos de TU cliente
        lista_cliente = buscar_negocios(TARGET_BUSINESS, API_KEY, max_resultados=1)

        # Paso 2: Buscar datos del MERCADO (Competencia)
        lista_mercado = buscar_negocios(MERCADO_QUERY, API_KEY, max_resultados=10)

        if lista_cliente and lista_mercado:
            # Paso 3: Magia
            generar_mega_prompt(lista_cliente[0], lista_mercado)
        else:
            print("❌ No se encontraron datos suficientes.")