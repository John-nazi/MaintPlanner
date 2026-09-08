import asyncio
import logging
import os
import re
import unicodedata
from math import ceil

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup, # <--- IMPORTACIÓN NUEVA
    KeyboardButton,      # <--- IMPORTACIÓN NUEVA
)
from telegram.ext import (
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# ============================================================
# CONFIGURACIÓN GENERAL
# ============================================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
PUERTO = int(os.getenv("PORT", "10000"))
URL_RENDER = os.getenv("RENDER_EXTERNAL_URL")

SEMANAS_POR_PAGINA = 6

# ============================================================
# ⚙️ PARÁMETROS DE AUTODESTRUCCIÓN
# ============================================================

TIEMPO_BORRADO = 180  

INTERVALOS_TIMER = [10, 5, 4, 3, 2, 1]
BARRIDO_CANTIDAD = 100
TIEMPO_BORRADO_AVISO = 5

LIMPIEZAS_ACTIVAS = {}
ULTIMO_MENSAJE_POR_CHAT = {}
MENSAJES_PROTEGIDOS = {}


# ============================================================
# PALABRAS PROHIBIDAS (SISTEMA DE MODERACIÓN)
# ============================================================

PALABRAS_PROHIBIDAS = [
    "puta", "puto", "pendejo", "pendeja", "imbecil", "idiota",
    "cabron", "cabrona", "culero", "culera", "chingada", "chingado",
    "jodete", "mierda", "verga", "pinche", "joto", "gay", "culo",
]


# ============================================================
# ÁREAS Y LINKS SEMANALES
# ============================================================

AREAS = {
    "pintura": {
        "nombre": "Pintura y Secuenciado",
        "icono": "🔴",
        "semanas": {
            52: "", 51: "", 50: "", 49: "", 48: "", 47: "", 46: "", 45: "", 44: "", 43: "", 42: "", 41: "",
            40: "https://grupometalsa.sharepoint.com/:f:/s/MMSMantenimientoEquiposVC/IgBIXpHXKby6Sp-tsiP_Z0vZATI_edTFZNfIVveA3T7Hd-M?e=XLVV8d",
            39: "https://grupometalsa.sharepoint.com/:f:/s/MMSMantenimientoEquiposVC/IgBsPEx7NZ1ZQYpvT_AgkUY3AeUrQ9kD5BQTgibCGlTOcqg?e=mAGZEb",
            38: "https://grupometalsa.sharepoint.com/:f:/s/MMSMantenimientoEquiposVC/IgCT8dS0HBNBQ7g8mUXtRNjXAbw3ZOkspb2j28-92JICJKo?e=dhLeJI",
            37: "https://grupometalsa.sharepoint.com/:f:/s/MMSMantenimientoEquiposVC/IgADatLyHOy-TqILvdDkrytVATBtUNoKDECFYAkFqjfhw1w?e=07uPVx",
            36: "https://grupometalsa.sharepoint.com/:f:/s/MMSMantenimientoEquiposVC/IgDKgPprvxzzTbWo8Rn0GTZYAfB5YAg6OXLfo6yj6HJnaAc?e=8IQOYb",
            35: "https://grupometalsa.sharepoint.com/:f:/s/MMSMantenimientoEquiposVC/IgB25IyE1cX0SKy5ETNt5mzrAV1sJlVnZ6djNQAD6AyqAtQ?e=JDr5Sm",
            34: "", 33: "", 32: "", 31: "", 30: "", 29: "", 28: "", 27: "", 26: "", 25: "", 24: "", 23: "",
            22: "", 21: "", 20: "", 19: "", 18: "", 17: "", 16: "", 15: "", 14: "", 13: "", 12: "", 11: "",
            10: "", 9: "", 8: "", 7: "", 6: "", 5: "", 4: "", 3: "", 2: "", 1: "",
        },
    },
    "eco_custom": {
        "nombre": "Eco-Custom",
        "icono": "🟢",
        "semanas": {
            52: "", 51: "", 50: "", 49: "", 48: "", 47: "", 46: "", 45: "", 44: "", 43: "", 42: "", 41: "",
            40: "https://grupometalsa.sharepoint.com/:f:/s/MMSMantenimientoEquiposVC/IgCiEfxuD_G0T5rLeDTegs0wAUJMAUQylvVICQZGZes63lQ?e=w6ZEQZ",
            39: "https://grupometalsa.sharepoint.com/:f:/s/MMSMantenimientoEquiposVC/IgDHJdsV8iQpQ4se4m5gQmYhAXUJZAlhKVVxR3oDr1rfJ0o?e=aMsJcC",
            38: "https://grupometalsa.sharepoint.com/:f:/s/MMSMantenimientoEquiposVC/IgBIHDAFDvduT5nSPkTwZ_a2AR8nrZtxngjw-kO0_tFdCcE?e=R8pNtI",
            37: "https://grupometalsa.sharepoint.com/:f:/s/MMSMantenimientoEquiposVC/IgD8WD3_qSoURJ-x1DlgaF3RAZmVP4yyj4ki7ujgymtAVZA?e=9GrCG5",
            36: "https://grupometalsa.sharepoint.com/:f:/s/MMSMantenimientoEquiposVC/IgAEcifIWjX5QJDEBOqYy9LRAff8cHRVllbqMxuiXJCcZKA?e=mO54GL",
            35: "https://grupometalsa.sharepoint.com/:f:/s/MMSMantenimientoEquiposVC/IgAE7H0CprJjQLbrNTJ3FRagAbNNourBQiUJGbRGE57FKEQ?e=MSt8j6",
            34: "", 33: "", 32: "", 31: "", 30: "", 29: "", 28: "", 27: "", 26: "", 25: "", 24: "", 23: "",
            22: "", 21: "", 20: "", 19: "", 18: "", 17: "", 16: "", 15: "", 14: "", 13: "", 12: "", 11: "",
            10: "", 9: "", 8: "", 7: "", 6: "", 5: "", 4: "", 3: "", 2: "", 1: "",
        },
    },
}


# ============================================================
# VALIDAR QUE EL COMANDO SEA PARA NUESTRO BOT
# ============================================================

async def comando_es_para_este_bot(update, context, comando):
    mensaje = update.effective_message
    if mensaje is None or not mensaje.text:
        return False
    primera_parte = mensaje.text.split()[0].lower()
    comando_base = f"/{comando.lower()}"
    if primera_parte == comando_base:
        return True
    if primera_parte.startswith(comando_base + "@"):
        destinatario = primera_parte.split("@", 1)[1]
        try:
            datos_bot = await context.bot.get_me()
            nuestro_usuario = (datos_bot.username or "").lower()
        except Exception:
            return False
        return destinatario == nuestro_usuario
    return False


# ============================================================
# FUNCIONES DE AUTOLIMPIEZA Y BARRIDO
# ============================================================

def obtener_mensajes_protegidos(chat_id):
    return MENSAJES_PROTEGIDOS.setdefault(chat_id, set())

def proteger_mensaje(chat_id, message_id):
    if message_id is None: return
    obtener_mensajes_protegidos(chat_id).add(message_id)

async def borrar_mensaje_despues(context, chat_id, message_id, segundos):
    await asyncio.sleep(segundos)
    if message_id in obtener_mensajes_protegidos(chat_id): return
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception:
        pass

def programar_borrado(context, chat_id, message_id, segundos=TIEMPO_BORRADO):
    context.application.create_task(
        borrar_mensaje_despues(context, chat_id, message_id, segundos)
    )

async def borrar_un_mensaje_barrido(context, chat_id, message_id):
    if message_id in obtener_mensajes_protegidos(chat_id): return False
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
        return True
    except Exception:
        return False

async def barrido_profundo(context, chat_id, message_id_tope):
    if message_id_tope is None: return
    protegidos = obtener_mensajes_protegidos(chat_id)
    inicio = max(1, message_id_tope - BARRIDO_CANTIDAD + 1)
    ids = [mid for mid in range(message_id_tope, inicio - 1, -1) if mid not in protegidos]
    if not ids: return
    eliminados = 0
    lote = 10
    for posicion in range(0, len(ids), lote):
        grupo = ids[posicion:posicion + lote]
        resultados = await asyncio.gather(
            *[borrar_un_mensaje_barrido(context, chat_id, mid) for mid in grupo],
            return_exceptions=True,
        )
        eliminados += sum(1 for resultado in resultados if resultado is True)
        await asyncio.sleep(0.15)

async def reiniciar_temporizador(context, chat_id, current_msg_id):
    if current_msg_id is not None:
        ULTIMO_MENSAJE_POR_CHAT[chat_id] = max(
            ULTIMO_MENSAJE_POR_CHAT.get(chat_id, 0), current_msg_id
        )
    anterior = LIMPIEZAS_ACTIVAS.get(chat_id)
    if anterior is not None:
        if anterior.get("task"):
            anterior["task"].cancel()
        timer_anterior = anterior.get("timer_msg_id")
        if timer_anterior is not None:
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=timer_anterior)
            except Exception:
                pass
        LIMPIEZAS_ACTIVAS.pop(chat_id, None)

    token_limpieza = object()
    LIMPIEZAS_ACTIVAS[chat_id] = {
        "task": None,
        "timer_msg_id": None,
        "token": token_limpieza,
    }

    tarea = context.application.create_task(
        rutina_limpieza_chat(
            context, chat_id, current_msg_id, TIEMPO_BORRADO, token_limpieza
        )
    )
    LIMPIEZAS_ACTIVAS[chat_id]["task"] = tarea


async def rutina_limpieza_chat(context, chat_id, max_msg_id, tiempo_total, token_limpieza):
    timer_id = None
    try:
        msg_timer = await context.bot.send_message(
            chat_id=chat_id,
            text="📡 _Inicializando protocolo de purga..._",
            parse_mode="Markdown",
        )
        timer_id = msg_timer.message_id
        
        info = LIMPIEZAS_ACTIVAS.get(chat_id)
        if info is None or info.get("token") is not token_limpieza:
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=timer_id)
            except Exception: pass
            return

        info["timer_msg_id"] = timer_id
        ULTIMO_MENSAJE_POR_CHAT[chat_id] = max(
            ULTIMO_MENSAJE_POR_CHAT.get(chat_id, 0), timer_id
        )

        tiempos = [t for t in INTERVALOS_TIMER if t < tiempo_total]
        tiempo_anterior = tiempo_total

        for tiempo in tiempos:
            espera = tiempo_anterior - tiempo
            if espera > 0:
                await asyncio.sleep(espera)

            info_actual = LIMPIEZAS_ACTIVAS.get(chat_id)
            if info_actual is None or info_actual.get("token") is not token_limpieza:
                return

            progreso_porcentaje = int(((tiempo_total - tiempo) / tiempo_total) * 100)
            bloques_llenos = int(progreso_porcentaje / 10)
            barra = "█" * bloques_llenos + "░" * (10 - bloques_llenos)

            texto_timer = (
                "🚨 *PROTOCOLO DE PURGA ACTIVADO* 🚨\n\n"
                f"`[{barra}] {progreso_porcentaje}%`\n\n"
                f"⏳ Destrucción de historial en: *{tiempo}s*\n"
                "_Protegiendo la confidencialidad de la operación._"
            )

            try:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=timer_id,
                    text=texto_timer,
                    parse_mode="Markdown",
                )
            except Exception:
                pass
            tiempo_anterior = tiempo

        if tiempo_anterior > 0:
            await asyncio.sleep(tiempo_anterior)

        info_actual = LIMPIEZAS_ACTIVAS.get(chat_id)
        if info_actual is None or info_actual.get("token") is not token_limpieza:
            return

        ultimo = max(ULTIMO_MENSAJE_POR_CHAT.get(chat_id, 0), timer_id)
        await barrido_profundo(context, chat_id, ultimo)

        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=timer_id)
        except Exception:
            pass

    except asyncio.CancelledError:
        raise
    finally:
        info_final = LIMPIEZAS_ACTIVAS.get(chat_id)
        if info_final is not None and info_final.get("token") is token_limpieza:
            LIMPIEZAS_ACTIVAS.pop(chat_id, None)


# ============================================================
# NORMALIZAR Y DETECTAR TEXTO (MODERACIÓN)
# ============================================================

def normalizar_texto(texto):
    texto = texto.lower()
    texto = unicodedata.normalize("NFD", texto)
    return "".join(caracter for caracter in texto if unicodedata.category(caracter) != "Mn")

def contiene_palabra_prohibida(texto):
    texto = normalizar_texto(texto)
    for palabra in PALABRAS_PROHIBIDAS:
        palabra = normalizar_texto(palabra.strip())
        if not palabra: continue
        patron = r"(?<!\w)" + re.escape(palabra) + r"(?!\w)"
        if re.search(patron, texto):
            return True
    return False


# ============================================================
# PROCESAR TODOS LOS MENSAJES
# ============================================================

async def procesar_mensaje(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mensaje = update.effective_message
    if mensaje is None:
        return

    ULTIMO_MENSAJE_POR_CHAT[mensaje.chat_id] = max(
        ULTIMO_MENSAJE_POR_CHAT.get(mensaje.chat_id, 0), mensaje.message_id
    )

    texto = mensaje.text or mensaje.caption or ""
    await reiniciar_temporizador(context, mensaje.chat_id, mensaje.message_id)

    # === CAPTURAR BOTÓN DEL TECLADO INFERIOR ===
    if texto == "📂 Desplegar Áreas de Trabajo":
        await mostrar_areas(update, context)
        return

    if not texto or texto.startswith("/"):
        return

    if contiene_palabra_prohibida(texto):
        try:
            await context.bot.delete_message(chat_id=mensaje.chat_id, message_id=mensaje.message_id)
            aviso = await context.bot.send_message(
                chat_id=mensaje.chat_id,
                message_thread_id=mensaje.message_thread_id,
                text="🛑 *INFRACCIÓN DETECTADA*\nEl mensaje fue bloqueado por contener lenguaje no permitido.",
                parse_mode="Markdown"
            )
            ULTIMO_MENSAJE_POR_CHAT[mensaje.chat_id] = max(
                ULTIMO_MENSAJE_POR_CHAT.get(mensaje.chat_id, 0), aviso.message_id
            )
            programar_borrado(context, aviso.chat_id, aviso.message_id, TIEMPO_BORRADO_AVISO)
        except Exception:
            pass


# ============================================================
# OBTENER Y CREAR MENÚS
# ============================================================

def obtener_semanas_configuradas(clave_area):
    area = AREAS.get(clave_area)
    if not area: return {}
    resultado = {}
    for numero, enlace in area["semanas"].items():
        enlace = enlace.strip()
        if enlace.startswith(("http://", "https://")):
            resultado[numero] = enlace
    return resultado

def crear_menu_areas():
    botones = [
        [InlineKeyboardButton(text=f"{area['icono']} {area['nombre']}", callback_data=f"area:{clave}")]
        for clave, area in AREAS.items()
    ]
    return InlineKeyboardMarkup(botones)

def crear_menu_semanas(clave_area, pagina=0):
    semanas_configuradas = obtener_semanas_configuradas(clave_area)
    semanas = sorted(semanas_configuradas.keys(), reverse=True)
    botones = []

    if not semanas:
        botones.append([InlineKeyboardButton("⚠️ Directorio Vacío", callback_data="sin_semanas")])
        botones.append([InlineKeyboardButton("⬅️ Panel Principal", callback_data="volver_areas")])
        return InlineKeyboardMarkup(botones)

    total_paginas = ceil(len(semanas) / SEMANAS_POR_PAGINA)
    pagina = max(0, min(pagina, total_paginas - 1))
    inicio = pagina * SEMANAS_POR_PAGINA
    fin = inicio + SEMANAS_POR_PAGINA

    for numero in semanas[inicio:fin]:
        botones.append([
            InlineKeyboardButton(text=f"📂 SEMANA {numero:02d}", url=semanas_configuradas[numero])
        ])

    navegacion = []
    if pagina > 0:
        navegacion.append(InlineKeyboardButton("◀️ Atrás", callback_data=f"semanas:{clave_area}:{pagina - 1}"))
    navegacion.append(InlineKeyboardButton(f"Pág. {pagina + 1}/{total_paginas}", callback_data="pagina_actual"))
    if pagina < (total_paginas - 1):
        navegacion.append(InlineKeyboardButton("Sig. ▶️", callback_data=f"semanas:{clave_area}:{pagina + 1}"))

    botones.append(navegacion)
    botones.append([InlineKeyboardButton("⬅️ Panel Principal", callback_data="volver_areas")])
    return InlineKeyboardMarkup(botones)


# ============================================================
# COMANDOS Y CALLBACKS
# ============================================================

async def iniciar(update, context):
    if not await comando_es_para_este_bot(update, context, "start"): return
    mensaje = update.effective_message
    
    programar_borrado(context, mensaje.chat_id, mensaje.message_id)

    # === CREAR EL TECLADO INFERIOR (App UI) ===
    teclado_inferior = ReplyKeyboardMarkup(
        [[KeyboardButton("📂 Desplegar Áreas de Trabajo")]],
        resize_keyboard=True,  # Hace los botones más pequeños y estéticos
        is_persistent=True     # Mantiene el teclado siempre visible
    )

    respuesta = await mensaje.reply_text(
        "🚀 *Sistema Integral de Gestión y Seguimiento de OTs MPS* 🚀\n\n"
        "Bienvenido. Aquí puedes consultar las Órdenes de Trabajo Semanales.\n\n"
        "👉 Utiliza el botón en la parte inferior o envía /areas.",
        reply_markup=teclado_inferior, # <--- ENVIAMOS EL TECLADO AQUÍ
        parse_mode="Markdown",
    )
    programar_borrado(context, respuesta.chat_id, respuesta.message_id)
    await reiniciar_temporizador(context, respuesta.chat_id, respuesta.message_id)


async def mostrar_areas(update, context):
    # Ya sea que llegue por comando (/areas) o por clic en el botón inferior
    if not update.callback_query:
        # Verificamos si no es callback, entonces checamos comando o texto
        mensaje = update.effective_message
        es_comando = await comando_es_para_este_bot(update, context, "areas")
        es_texto_boton = (mensaje and mensaje.text == "📂 Desplegar Áreas de Trabajo")
        if not (es_comando or es_texto_boton): return
    
    mensaje = update.effective_message
    programar_borrado(context, mensaje.chat_id, mensaje.message_id)

    respuesta = await mensaje.reply_text(
        "🗄️ *DIRECTORIO MAESTRO DE O.T.*\n\n"
        "Selecciona un departamento operativo:",
        reply_markup=crear_menu_areas(),
        parse_mode="Markdown",
    )
    programar_borrado(context, respuesta.chat_id, respuesta.message_id)
    await reiniciar_temporizador(context, respuesta.chat_id, respuesta.message_id)


async def seleccionar_area(update, context):
    consulta = update.callback_query
    if not consulta: return
    await consulta.answer()
    await reiniciar_temporizador(context, consulta.message.chat_id, consulta.message.message_id)

    try: clave = consulta.data.split(":")[1]
    except IndexError: return

    area = AREAS.get(clave)
    if not area: return

    await consulta.edit_message_text(
        text=(
            f"🗂️ *DEPARTAMENTO:* `{area['nombre']}`\n\n"
            "Selecciona la base de datos semanal correspondiente:"
        ),
        reply_markup=crear_menu_semanas(clave, 0),
        parse_mode="Markdown",
    )


async def cambiar_pagina(update, context):
    consulta = update.callback_query
    if not consulta: return
    datos = consulta.data or ""

    if datos == "pagina_actual":
        await consulta.answer()
        return
    if datos == "sin_semanas":
        await consulta.answer("El directorio actualmente está vacío.", show_alert=True)
        return

    await consulta.answer()
    await reiniciar_temporizador(context, consulta.message.chat_id, consulta.message.message_id)

    try:
        _, clave, pagina = datos.split(":")
        pagina = int(pagina)
    except (ValueError, IndexError):
        return

    await consulta.edit_message_reply_markup(reply_markup=crear_menu_semanas(clave, pagina))


async def volver_areas(update, context):
    consulta = update.callback_query
    if not consulta: return
    await consulta.answer()

    await consulta.edit_message_text(
        text="🗄️ *DIRECTORIO MAESTRO DE O.T.*\n\nSelecciona un departamento operativo:",
        reply_markup=crear_menu_areas(),
        parse_mode="Markdown",
    )

async def manejar_error(update, context):
    logger.error("Excepción en el sistema:", exc_info=context.error)

# ============================================================
# INICIO Y WEBHOOK
# ============================================================

def main():
    if not TOKEN: raise ValueError("Falta TELEGRAM_BOT_TOKEN.")
    if not URL_RENDER: raise ValueError("Falta RENDER_EXTERNAL_URL.")

    aplicacion = ApplicationBuilder().token(TOKEN).build()

    aplicacion.add_handler(CommandHandler("start", iniciar))
    aplicacion.add_handler(CommandHandler("areas", mostrar_areas))
    
    aplicacion.add_handler(CallbackQueryHandler(seleccionar_area, pattern=r"^area:"))
    aplicacion.add_handler(CallbackQueryHandler(cambiar_pagina, pattern=r"^(semanas:|pagina_actual|sin_semanas)"))
    aplicacion.add_handler(CallbackQueryHandler(volver_areas, pattern=r"^volver_areas$"))
    
    aplicacion.add_handler(MessageHandler(filters.ALL, procesar_mensaje))
    aplicacion.add_error_handler(manejar_error)

    ruta = "telegram"
    url_webhook = f"{URL_RENDER}/{ruta}"

    print(f"🚀 SISTEMA EN LÍNEA. Protocolo de purga establecido a {TIEMPO_BORRADO} segundos.")
    print(f"🔗 Enlace Webhook: {url_webhook}")

    aplicacion.run_webhook(
        listen="0.0.0.0",
        port=PUERTO,
        url_path=ruta,
        webhook_url=url_webhook,
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
    )

if __name__ == "__main__":
    main()
