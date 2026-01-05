import google.generativeai as genai

# --- IMPORTANTE: PEGA AQUÍ TU API KEY DE GEMINI ---
# (Asegúrate de usar la clave de AI Studio, no la de Maps si son diferentes)
API_KEY = "AIzaSyCG-wlXv21tQUwi87_oS_pDZmxMWN3cAyQ"

genai.configure(api_key=API_KEY)

print("🔍 Consultando modelos disponibles para tu clave...")

try:
    for m in genai.list_models():
        if 'generateContent' in m.supported_generation_methods:
            print(f"✅ Disponible: {m.name}")
except Exception as e:
    print(f"❌ Error al conectar: {e}")