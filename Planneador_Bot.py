import asyncio
import logging
import os
import re
import unicodedata
from datetime import datetime, timezone
from math import ceil

from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
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

# Tiempo asignado para el temporizador visual y autodestrucción
TIEMPO_BORRADO = 15

# Usuario oficial de ONLYOFFICE
ONLYOFFICE_USERNAME = "onlyoffice_bot"

# ============================================================
# GESTOR DE AUTODESTRUCCIÓN Y BARRIDO PROFUNDO
# ============================================================
LIMPIEZAS_ACTIVAS = {}  # Guarda las tareas de limpieza por chat_id

async def reiniciar_temporizador(context, chat_id, current_msg_id):
    """
    Cancela cualquier limpieza en curso y crea una nueva.
    Esto permite que si el usuario sigue interactuando, el menú no se borre.
    """
    if chat_id in LIMPIEZAS_ACTIVAS:
        info = LIMPIEZAS_ACTIVAS[chat_id]
        info['task'].cancel()
        try:
            if info['timer_msg_id']:
                await context.bot.delete_message(chat_id=chat_id, message_id=info['timer_msg_id'])
        except Exception:
            pass
        del LIMPIEZAS_ACTIVAS[chat_id]
        
    tarea = context.application.create_task(
        rutina_limpieza_chat(context, chat_id, current_msg_id, TIEMPO_BORRADO)
    )
    LIMPIEZAS_ACTIVAS[chat_id] = {'task': tarea, 'timer_msg_id': None}

async def rutina_limpieza_chat(context, chat_id, max_msg_id, tiempo_total):
    """
    Muestra el temporizador visual y luego borra los últimos 80 mensajes del chat
    para garantizar que se elimine todo (incluso lo de antes de que Render despertara).
    """
    try:
        # 1. Enviar mensaje inicial del timer
        msg_timer = await context.bot.send_message(
            chat_id=chat_id,
            text="⏳ *Iniciando protocolo de limpieza...*",
            parse_mode="Markdown"
        )
        
        # Registrar el ID para poder borrar el timer si se interrumpe
        if chat_id in LIMPIEZAS_ACTIVAS:
            LIMPIEZAS_ACTIVAS[chat_id]['timer_msg_id'] = msg_timer.message_id
            
        id_tope = msg_timer.message_id

        # 2. Secuencia de actualización (Efecto Visual)
        # Se actualiza en estos segundos restantes para evitar bloqueo por spam (Rate Limit de Telegram)
        tiempos = [15,10, 5, 3, 2, 1],
        tiempos = [t for t in tiempos if t < tiempo_total]
        
        tiempo_restante = tiempo_total
        
        for t in tiempos:
            espera = tiempo_restante - t
            if espera > 0:
                await asyncio.sleep(espera)
            
            tiempo_restante = t
            
            # Calcular la barra de progreso
            progreso = int(((tiempo_total - t) / tiempo_total) * 15)
            barra = "🟥" * progreso + "🟩" * (15 - progreso)
            texto = f"⚠️ *AUTODESTRUCCIÓN DEL CHAT* ⚠️\n\n{barra}\n\n🧹 Limpiando todo en: *{t} segundos*"
            
            try:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=id_tope,
                    text=texto,
                    parse_mode="Markdown"
                )
            except Exception:
                pass # Ignorar si el mensaje fue borrado manualmente

        # Esperar el último segundo
        if tiempo_restante > 0:
            await asyncio.sleep(tiempo_restante)

        # 3. Barrido profundo (La limpieza final)
        # Borra 80 mensajes hacia atrás "a ciegas". 
        # Esto soluciona los mensajes acumulados mientras el bot dormía en Render.
        for i in range(80):
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=id_tope - i)
            except Exception:
                pass # Ignorar si el mensaje ya no existe o es demasiado viejo

    except asyncio.CancelledError:
        # Si se cancela la tarea, simplemente terminamos en silencio
        raise

# ============================================================
# EDICIONES ACTIVAS EN MEMORIA
# ============================================================

PDF_PENDIENTES = []

def ahora_utc_iso():
    return datetime.now(timezone.utc).isoformat()

def cargar_estado():
    return

def guardar_estado():
    return

# ============================================================
# PALABRAS PROHIBIDAS
# ============================================================

PALABRAS_PROHIBIDAS = [
    "puta", "puto", "pendejo", "pendeja", "imbecil", "idiota",
    "cabron", "cabrona", "culero", "culera", "chingada",
    "chingado", "jodete", "mierda", "verga", "pinche",
    "joto", "gay", "culo",
]

# ============================================================
# ÁREAS
# ============================================================

AREAS = {
    "pintura": {
        "nombre": "Pintura y Secuenciado",
        "icono": "🔴",
        "semanas": {
            52: "",
            51: "PEGA_AQUI_LINK_PINTURA_SEMANA_51",
            50: "PEGA_AQUI_LINK_PINTURA_SEMANA_50",
            49: "PEGA_AQUI_LINK_PINTURA_SEMANA_49",
            48: "PEGA_AQUI_LINK_PINTURA_SEMANA_48",
            47: "PEGA_AQUI_LINK_PINTURA_SEMANA_47",
            46: "PEGA_AQUI_LINK_PINTURA_SEMANA_46",
            45: "PEGA_AQUI_LINK_PINTURA_SEMANA_45",
            44: "PEGA_AQUI_LINK_PINTURA_SEMANA_44",
            43: "PEGA_AQUI_LINK_PINTURA_SEMANA_43",
            42: "PEGA_AQUI_LINK_PINTURA_SEMANA_42",
            41: "PEGA_AQUI_LINK_PINTURA_SEMANA_41",
            40: "PEGA_AQUI_LINK_PINTURA_SEMANA_40",
            39: "PEGA_AQUI_LINK_PINTURA_SEMANA_39",
            38: "PEGA_AQUI_LINK_PINTURA_SEMANA_38",
            37: "PEGA_AQUI_LINK_PINTURA_SEMANA_37",
            36: "PEGA_AQUI_LINK_PINTURA_SEMANA_36",
            35: "https://grupometalsa.sharepoint.com/:f:/s/MMSMantenimientoEquiposVC/IgB25IyE1cX0SKy5ETNt5mzrAV1sJlVnZ6djNQAD6AyqAtQ?e=qkF8Wc",
            34: "PEGA_AQUI_LINK_PINTURA_SEMANA_34",
            33: "PEGA_AQUI_LINK_PINTURA_SEMANA_33",
            32: "PEGA_AQUI_LINK_PINTURA_SEMANA_32",
            31: "PEGA_AQUI_LINK_PINTURA_SEMANA_31",
            30: "PEGA_AQUI_LINK_PINTURA_SEMANA_30",
            29: "PEGA_AQUI_LINK_PINTURA_SEMANA_29",
            28: "PEGA_AQUI_LINK_PINTURA_SEMANA_28",
            27: "PEGA_AQUI_LINK_PINTURA_SEMANA_27",
            26: "PEGA_AQUI_LINK_PINTURA_SEMANA_26",
            25: "PEGA_AQUI_LINK_PINTURA_SEMANA_25",
            24: "PEGA_AQUI_LINK_PINTURA_SEMANA_24",
            23: "PEGA_AQUI_LINK_PINTURA_SEMANA_23",
            22: "PEGA_AQUI_LINK_PINTURA_SEMANA_22",
            21: "PEGA_AQUI_LINK_PINTURA_SEMANA_21",
            20: "PEGA_AQUI_LINK_PINTURA_SEMANA_20",
            19: "PEGA_AQUI_LINK_PINTURA_SEMANA_19",
            18: "PEGA_AQUI_LINK_PINTURA_SEMANA_18",
            17: "PEGA_AQUI_LINK_PINTURA_SEMANA_17",
            16: "PEGA_AQUI_LINK_PINTURA_SEMANA_16",
            15: "PEGA_AQUI_LINK_PINTURA_SEMANA_15",
            14: "PEGA_AQUI_LINK_PINTURA_SEMANA_14",
            13: "PEGA_AQUI_LINK_PINTURA_SEMANA_13",
            12: "PEGA_AQUI_LINK_PINTURA_SEMANA_12",
            11: "PEGA_AQUI_LINK_PINTURA_SEMANA_11",
            10: "PEGA_AQUI_LINK_PINTURA_SEMANA_10",
            9: "PEGA_AQUI_LINK_PINTURA_SEMANA_09",
            8: "PEGA_AQUI_LINK_PINTURA_SEMANA_08",
            7: "PEGA_AQUI_LINK_PINTURA_SEMANA_07",
            6: "PEGA_AQUI_LINK_PINTURA_SEMANA_06",
            5: "PEGA_AQUI_LINK_PINTURA_SEMANA_05",
            4: "PEGA_AQUI_LINK_PINTURA_SEMANA_04",
            3: "PEGA_AQUI_LINK_PINTURA_SEMANA_03",
            2: "PEGA_AQUI_LINK_PINTURA_SEMANA_02",
            1: "PEGA_AQUI_LINK_PINTURA_SEMANA_01",
        },
    },
    "eco_custom": {
        "nombre": "Eco-Custom",
        "icono": "🟢",
        "semanas": {
            52: "PEGA_AQUI_LINK_ECO_CUSTOM_SEMANA_52",
            51: "PEGA_AQUI_LINK_ECO_CUSTOM_SEMANA_51",
            50: "PEGA_AQUI_LINK_ECO_CUSTOM_SEMANA_50",
            49: "PEGA_AQUI_LINK_ECO_CUSTOM_SEMANA_49",
            48: "PEGA_AQUI_LINK_ECO_CUSTOM_SEMANA_48",
            47: "PEGA_AQUI_LINK_ECO_CUSTOM_SEMANA_47",
            46: "PEGA_AQUI_LINK_ECO_CUSTOM_SEMANA_46",
            45: "PEGA_AQUI_LINK_ECO_CUSTOM_SEMANA_45",
            44: "PEGA_AQUI_LINK_ECO_CUSTOM_SEMANA_44",
            43: "PEGA_AQUI_LINK_ECO_CUSTOM_SEMANA_43",
            42: "PEGA_AQUI_LINK_ECO_CUSTOM_SEMANA_42",
            41: "PEGA_AQUI_LINK_ECO_CUSTOM_SEMANA_41",
            40: "PEGA_AQUI_LINK_ECO_CUSTOM_SEMANA_40",
            39: "PEGA_AQUI_LINK_ECO_CUSTOM_SEMANA_39",
            38: "PEGA_AQUI_LINK_ECO_CUSTOM_SEMANA_38",
            37: "PEGA_AQUI_LINK_ECO_CUSTOM_SEMANA_37",
            36: "PEGA_AQUI_LINK_ECO_CUSTOM_SEMANA_36",
            35: "https://grupometalsa.sharepoint.com/:f:/s/MMSMantenimientoEquiposVC/IgAE7H0CprJjQLbrNTJ3FRagAbNNourBQiUJGbRGE57FKEQ?e=hqaoG6",
            34: "PEGA_AQUI_LINK_ECO_CUSTOM_SEMANA_34",
            33: "PEGA_AQUI_LINK_ECO_CUSTOM_SEMANA_33",
            32: "PEGA_AQUI_LINK_ECO_CUSTOM_SEMANA_32",
            31: "PEGA_AQUI_LINK_ECO_CUSTOM_SEMANA_31",
            30: "PEGA_AQUI_LINK_ECO_CUSTOM_SEMANA_30",
            29: "PEGA_AQUI_LINK_ECO_CUSTOM_SEMANA_29",
            28: "PEGA_AQUI_LINK_ECO_CUSTOM_SEMANA_28",
            27: "PEGA_AQUI_LINK_ECO_CUSTOM_SEMANA_27",
            26: "PEGA_AQUI_LINK_ECO_CUSTOM_SEMANA_26",
            25: "PEGA_AQUI_LINK_ECO_CUSTOM_SEMANA_25",
            24: "PEGA_AQUI_LINK_ECO_CUSTOM_SEMANA_24",
            23: "PEGA_AQUI_LINK_ECO_CUSTOM_SEMANA_23",
            22: "PEGA_AQUI_LINK_ECO_CUSTOM_SEMANA_22",
            21: "PEGA_AQUI_LINK_ECO_CUSTOM_SEMANA_21",
            20: "PEGA_AQUI_LINK_ECO_CUSTOM_SEMANA_20",
            19: "PEGA_AQUI_LINK_ECO_CUSTOM_SEMANA_19",
            18: "PEGA_AQUI_LINK_ECO_CUSTOM_SEMANA_18",
            17: "PEGA_AQUI_LINK_ECO_CUSTOM_SEMANA_17",
            16: "PEGA_AQUI_LINK_ECO_CUSTOM_SEMANA_16",
            15: "PEGA_AQUI_LINK_ECO_CUSTOM_SEMANA_15",
            14: "PEGA_AQUI_LINK_ECO_CUSTOM_SEMANA_14",
            13: "PEGA_AQUI_LINK_ECO_CUSTOM_SEMANA_13",
            12: "PEGA_AQUI_LINK_ECO_CUSTOM_SEMANA_12",
            11: "PEGA_AQUI_LINK_ECO_CUSTOM_SEMANA_11",
            10: "PEGA_AQUI_LINK_ECO_CUSTOM_SEMANA_10",
            9: "PEGA_AQUI_LINK_ECO_CUSTOM_SEMANA_09",
            8: "PEGA_AQUI_LINK_ECO_CUSTOM_SEMANA_08",
            7: "PEGA_AQUI_LINK_ECO_CUSTOM_SEMANA_07",
            6: "PEGA_AQUI_LINK_ECO_CUSTOM_SEMANA_06",
            5: "PEGA_AQUI_LINK_ECO_CUSTOM_SEMANA_05",
            4: "PEGA_AQUI_LINK_ECO_CUSTOM_SEMANA_04",
            3: "PEGA_AQUI_LINK_ECO_CUSTOM_SEMANA_03",
            2: "PEGA_AQUI_LINK_ECO_CUSTOM_SEMANA_02",
            1: "PEGA_AQUI_LINK_ECO_CUSTOM_SEMANA_01",
        },
    },
}

# ============================================================
# FUNCIONES AUXILIARES DE TEXTO
# ============================================================

def extraer_id_ot(nombre_archivo):
    if not nombre_archivo:
        return None
    nombre_archivo = nombre_archivo.strip()
    coincidencia = re.match(r"^(\d+)_", nombre_archivo)
    if not coincidencia:
        return None
    return coincidencia.group(1)

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
        except Exception as error:
            logger.warning("No se pudo obtener el username del bot: %s", error)
            return False
        return destinatario == nuestro_usuario

    return False

def normalizar_texto(texto):
    texto = texto.lower()
    texto = unicodedata.normalize("NFD", texto)
    return "".join(c for c in texto if unicodedata.category(c) != "Mn")

def contiene_palabra_prohibida(texto):
    texto = normalizar_texto(texto)
    for palabra in PALABRAS_PROHIBIDAS:
        palabra = normalizar_texto(palabra.strip())
        if not palabra:
            continue
        patron = r"(?<!\w)" + re.escape(palabra) + r"(?!\w)"
        if re.search(patron, texto):
            return True
    return False

# ============================================================
# PROCESAR TODOS LOS MENSAJES (Activador de limpieza)
# ============================================================

async def procesar_mensaje(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mensaje = update.effective_message
    if mensaje is None:
        return

    # Iniciar o reiniciar el barrido profundo con cada mensaje recibido
    await reiniciar_temporizador(context, mensaje.chat_id, mensaje.message_id)

    texto = mensaje.text or mensaje.caption or ""
    remitente = mensaje.from_user

    # Ignorar mensajes largos o comandos normales para el resto de la lógica
    if not texto or texto.startswith("/"):
        return

    # Si contiene groserías, se borra de inmediato y el aviso se destruirá con el barrido general
    if contiene_palabra_prohibida(texto):
        try:
            await context.bot.delete_message(chat_id=mensaje.chat_id, message_id=mensaje.message_id)
            await context.bot.send_message(
                chat_id=mensaje.chat_id,
                message_thread_id=mensaje.message_thread_id,
                text="⚠️ Mensaje eliminado por contener lenguaje no permitido.",
            )
        except Exception:
            pass

# ============================================================
# FUNCIONES DE MENÚ Y NAVEGACIÓN
# ============================================================

def obtener_semanas_configuradas(clave_area):
    area = AREAS.get(clave_area)
    if not area:
        return {}
        
    resultado = {}
    for numero, enlace in area["semanas"].items():
        enlace = enlace.strip()
        if enlace.startswith("PEGA_AQUI_LINK_"):
            continue
        if enlace.startswith(("http://", "https://")):
            resultado[numero] = enlace
            
    return resultado

def crear_menu_areas():
    botones = []
    for clave, area in AREAS.items():
        botones.append([
            InlineKeyboardButton(
                text=f"{area['icono']} {area['nombre']}",
                callback_data=f"area:{clave}",
            )
        ])
    return InlineKeyboardMarkup(botones)

def crear_menu_semanas(clave_area, pagina=0):
    semanas_configuradas = obtener_semanas_configuradas(clave_area)
    semanas = sorted(semanas_configuradas.keys(), reverse=True)
    botones = []

    if not semanas:
        botones.append([
            InlineKeyboardButton("⚠️ No hay semanas configuradas", callback_data="sin_semanas")
        ])
        botones.append([
            InlineKeyboardButton("⬅ Volver a las áreas", callback_data="volver_areas")
        ])
        return InlineKeyboardMarkup(botones)

    total_paginas = ceil(len(semanas) / SEMANAS_POR_PAGINA)
    pagina = max(0, min(pagina, total_paginas - 1))
    inicio = pagina * SEMANAS_POR_PAGINA
    fin = inicio + SEMANAS_POR_PAGINA

    for numero in semanas[inicio:fin]:
        botones.append([
            InlineKeyboardButton(text=f"📁 SEMANA {numero:02d}", url=semanas_configuradas[numero])
        ])

    navegacion = []
    if pagina > 0:
        navegacion.append(InlineKeyboardButton("◀ Anterior", callback_data=f"semanas:{clave_area}:{pagina - 1}"))
        
    navegacion.append(InlineKeyboardButton(f"{pagina + 1} de {total_paginas}", callback_data="pagina_actual"))
    
    if pagina < (total_paginas - 1):
        navegacion.append(InlineKeyboardButton("Siguiente ▶", callback_data=f"semanas:{clave_area}:{pagina + 1}"))

    botones.append(navegacion)
    botones.append([InlineKeyboardButton("⬅ Volver a las áreas", callback_data="volver_areas")])
    return InlineKeyboardMarkup(botones)

# ============================================================
# COMANDOS PRINCIPALES
# ============================================================

async def iniciar(update, context):
    if not await comando_es_para_este_bot(update, context, "start"):
        return
        
    mensaje = update.effective_message
    if mensaje is None:
        return
        
    respuesta = await mensaje.reply_text(
        "🤖 *Bot de Planeación activo*\n\n"
        "Utiliza /areas para consultar las carpetas de Órdenes de Trabajo Semanales.",
        parse_mode="Markdown",
    )
    # Activamos el timer con el ID de la respuesta
    await reiniciar_temporizador(context, respuesta.chat_id, respuesta.message_id)

async def mostrar_areas(update, context):
    if not await comando_es_para_este_bot(update, context, "areas"):
        return
        
    mensaje = update.effective_message
    if mensaje is None:
        return
        
    respuesta = await mensaje.reply_text(
        "📁 *Carpetas de Órdenes de Trabajo Semanales*\n\nSelecciona el área:",
        reply_markup=crear_menu_areas(),
        parse_mode="Markdown",
    )
    await reiniciar_temporizador(context, respuesta.chat_id, respuesta.message_id)

async def seleccionar_area(update, context):
    consulta = update.callback_query
    if not consulta:
        return
        
    await consulta.answer()
    
    # Cada clic en el menú reinicia el timer, dándole más tiempo al usuario
    await reiniciar_temporizador(context, consulta.message.chat_id, consulta.message.message_id)
    
    try:
        clave = consulta.data.split(":")[1]
    except IndexError:
        return
        
    area = AREAS.get(clave)
    if not area:
        return
        
    await consulta.edit_message_text(
        text=(
            "📁 *Carpetas de Órdenes de Trabajo Semanales*\n\n"
            f"Área seleccionada: *{area['nombre']}*\n\n"
            "Selecciona la semana correspondiente en la que deseas trabajar:"
        ),
        reply_markup=crear_menu_semanas(clave, 0),
        parse_mode="Markdown",
    )

async def cambiar_pagina(update, context):
    consulta = update.callback_query
    if not consulta:
        return
        
    await reiniciar_temporizador(context, consulta.message.chat_id, consulta.message.message_id)
    
    datos = consulta.data or ""
    if datos == "pagina_actual":
        await consulta.answer()
        return
        
    if datos == "sin_semanas":
        await consulta.answer("No hay semanas configuradas.", show_alert=True)
        return
        
    await consulta.answer()
    
    try:
        _, clave, pagina = datos.split(":")
        pagina = int(pagina)
    except (ValueError, IndexError):
        return
        
    await consulta.edit_message_reply_markup(
        reply_markup=crear_menu_semanas(clave, pagina)
    )

async def volver_areas(update, context):
    consulta = update.callback_query
    if not consulta:
        return
        
    await reiniciar_temporizador(context, consulta.message.chat_id, consulta.message.message_id)
    await consulta.answer()
    await consulta.edit_message_text(
        "📁 *Carpetas de Órdenes de Trabajo Semanales*\n\nSelecciona el área:",
        reply_markup=crear_menu_areas(),
        parse_mode="Markdown",
    )

async def manejar_error(update, context):
    logger.error("Error del bot:", exc_info=context.error)

# ============================================================
# INICIO
# ============================================================

def main():
    if not TOKEN:
        raise ValueError("Falta TELEGRAM_BOT_TOKEN.")
    if not URL_RENDER:
        raise ValueError("Falta RENDER_EXTERNAL_URL.")

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

    print("Bot activo. Modo Autodestrucción y Barrido Profundo Habilitado.")
    print(f"Webhook: {url_webhook}")

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
