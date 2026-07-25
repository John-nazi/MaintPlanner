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

# Borrado de /areas, /start y mensajes del bot
TIEMPO_BORRADO = 60

# Aviso de moderación
TIEMPO_BORRADO_AVISO = 5


# ============================================================
# PALABRAS PROHIBIDAS
# ============================================================

PALABRAS_PROHIBIDAS = [
    "puta",
    "puto",
    "pendejo",
    "pendeja",
    "imbecil",
    "idiota",
    "cabron",
    "cabrona",
    "culero",
    "culera",
    "chingada",
    "chingado",
    "jodete",
    "mierda",
    "verga",
    "pinche",
    "joto",
    "gay",
    "culo"

    # Agrega más aquí:
    # "palabra",
]


# ============================================================
# ÁREAS
# ============================================================

AREAS = {

    "pintura": {
        "nombre": "Pintura y Secuenciado",
        "icono": "🔴",

        "semanas": {
            52: "PEGA_AQUI_LINK_PINTURA_SEMANA_52",
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
            35: "PEGA_AQUI_LINK_PINTURA_SEMANA_35",
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
            35: "PEGA_AQUI_LINK_ECO_CUSTOM_SEMANA_35",
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
# BORRAR MENSAJES
# ============================================================

async def borrar_mensaje_despues(
    context,
    chat_id,
    message_id,
    segundos,
):

    await asyncio.sleep(segundos)

    try:
        await context.bot.delete_message(
            chat_id=chat_id,
            message_id=message_id,
        )

    except Exception as error:
        logger.warning(
            "No se pudo borrar mensaje %s: %s",
            message_id,
            error,
        )


def programar_borrado(
    context,
    chat_id,
    message_id,
    segundos=TIEMPO_BORRADO,
):

    context.application.create_task(
        borrar_mensaje_despues(
            context,
            chat_id,
            message_id,
            segundos,
        )
    )


# ============================================================
# NORMALIZAR TEXTO
# ============================================================

def normalizar_texto(texto):

    texto = texto.lower()

    texto = unicodedata.normalize(
        "NFD",
        texto,
    )

    return "".join(
        caracter
        for caracter in texto
        if unicodedata.category(caracter) != "Mn"
    )


# ============================================================
# DETECTAR PALABRAS PROHIBIDAS
# ============================================================

def contiene_palabra_prohibida(texto):

    texto = normalizar_texto(texto)

    for palabra in PALABRAS_PROHIBIDAS:

        palabra = normalizar_texto(
            palabra.strip()
        )

        if not palabra:
            continue

        patron = (
            r"(?<!\w)"
            + re.escape(palabra)
            + r"(?!\w)"
        )

        if re.search(patron, texto):
            return True

    return False


# ============================================================
# MODERACIÓN
# ============================================================

async def moderar_mensaje(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    # IMPORTANTE:
    # effective_message permite trabajar también con mensajes
    # de temas, supergrupos y otras variantes de Telegram.
    mensaje = update.effective_message

    if mensaje is None:
        return

    texto = (
        mensaje.text
        or mensaje.caption
        or ""
    )

    # Registro temporal para diagnóstico en Render
    logger.info(
        "MENSAJE RECIBIDO | chat=%s | tipo=%s | tema=%s | texto=%r",
        mensaje.chat_id,
        mensaje.chat.type if mensaje.chat else None,
        mensaje.message_thread_id,
        texto,
    )

    if not texto:
        return

    # No procesar comandos aquí
    if texto.startswith("/"):
        return

    if not contiene_palabra_prohibida(texto):
        return

    logger.info(
        "PALABRA PROHIBIDA DETECTADA | mensaje=%s",
        mensaje.message_id,
    )

    try:

        await context.bot.delete_message(
            chat_id=mensaje.chat_id,
            message_id=mensaje.message_id,
        )

        logger.info(
            "MENSAJE ELIMINADO CORRECTAMENTE."
        )

    except Exception as error:

        logger.error(
            "NO SE PUDO ELIMINAR EL MENSAJE: %s",
            error,
        )

        return

    # Enviar aviso dentro del mismo tema
    try:

        aviso = await context.bot.send_message(
            chat_id=mensaje.chat_id,
            message_thread_id=mensaje.message_thread_id,
            text=(
                "⚠️ Mensaje eliminado por contener "
                "lenguaje no permitido."
            ),
        )

        programar_borrado(
            context,
            aviso.chat_id,
            aviso.message_id,
            TIEMPO_BORRADO_AVISO,
        )

    except Exception as error:

        logger.warning(
            "No se pudo enviar aviso: %s",
            error,
        )


# ============================================================
# SEMANAS CONFIGURADAS
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

        if enlace.startswith(
            ("http://", "https://")
        ):
            resultado[numero] = enlace

    return resultado


# ============================================================
# MENÚ ÁREAS
# ============================================================

def crear_menu_areas():

    botones = []

    for clave, area in AREAS.items():

        botones.append(
            [
                InlineKeyboardButton(
                    text=(
                        f"{area['icono']} "
                        f"{area['nombre']}"
                    ),
                    callback_data=f"area:{clave}",
                )
            ]
        )

    return InlineKeyboardMarkup(botones)


# ============================================================
# MENÚ SEMANAS
# ============================================================

def crear_menu_semanas(
    clave_area,
    pagina=0,
):

    semanas_configuradas = (
        obtener_semanas_configuradas(
            clave_area
        )
    )

    semanas = sorted(
        semanas_configuradas.keys(),
        reverse=True,
    )

    botones = []

    if not semanas:

        botones.append(
            [
                InlineKeyboardButton(
                    "⚠️ No hay semanas configuradas",
                    callback_data="sin_semanas",
                )
            ]
        )

        botones.append(
            [
                InlineKeyboardButton(
                    "⬅ Volver a las áreas",
                    callback_data="volver_areas",
                )
            ]
        )

        return InlineKeyboardMarkup(botones)

    total_paginas = ceil(
        len(semanas)
        / SEMANAS_POR_PAGINA
    )

    pagina = max(
        0,
        min(
            pagina,
            total_paginas - 1,
        ),
    )

    inicio = (
        pagina
        * SEMANAS_POR_PAGINA
    )

    fin = (
        inicio
        + SEMANAS_POR_PAGINA
    )

    for numero in semanas[inicio:fin]:

        botones.append(
            [
                InlineKeyboardButton(
                    text=f"📁 SEMANA {numero:02d}",
                    url=semanas_configuradas[numero],
                )
            ]
        )

    navegacion = []

    if pagina > 0:

        navegacion.append(
            InlineKeyboardButton(
                "◀ Anterior",
                callback_data=(
                    f"semanas:"
                    f"{clave_area}:"
                    f"{pagina - 1}"
                ),
            )
        )

    navegacion.append(
        InlineKeyboardButton(
            f"{pagina + 1} de {total_paginas}",
            callback_data="pagina_actual",
        )
    )

    if pagina < total_paginas - 1:

        navegacion.append(
            InlineKeyboardButton(
                "Siguiente ▶",
                callback_data=(
                    f"semanas:"
                    f"{clave_area}:"
                    f"{pagina + 1}"
                ),
            )
        )

    botones.append(navegacion)

    botones.append(
        [
            InlineKeyboardButton(
                "⬅ Volver a las áreas",
                callback_data="volver_areas",
            )
        ]
    )

    return InlineKeyboardMarkup(botones)


# ============================================================
# /START
# ============================================================

async def iniciar(
    update,
    context,
):

    if update.message is None:
        return

    programar_borrado(
        context,
        update.message.chat_id,
        update.message.message_id,
    )

    respuesta = await update.message.reply_text(
        "🤖 *Bot de Planeación activo*\n\n"
        "Utiliza /areas para consultar las carpetas "
        "de Órdenes de Trabajo Semanales.",
        parse_mode="Markdown",
    )

    programar_borrado(
        context,
        respuesta.chat_id,
        respuesta.message_id,
    )


# ============================================================
# /AREAS
# ============================================================

async def mostrar_areas(
    update,
    context,
):

    if update.message is None:
        return

    programar_borrado(
        context,
        update.message.chat_id,
        update.message.message_id,
    )

    respuesta = await update.message.reply_text(
        "📁 *Carpetas de Órdenes de Trabajo Semanales*\n\n"
        "Selecciona el área:",
        reply_markup=crear_menu_areas(),
        parse_mode="Markdown",
    )

    programar_borrado(
        context,
        respuesta.chat_id,
        respuesta.message_id,
    )


# ============================================================
# SELECCIONAR ÁREA
# ============================================================

async def seleccionar_area(
    update,
    context,
):

    consulta = update.callback_query

    if not consulta:
        return

    await consulta.answer()

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
            "Selecciona la semana correspondiente "
            "en la que deseas trabajar:"
        ),
        reply_markup=crear_menu_semanas(
            clave,
            0,
        ),
        parse_mode="Markdown",
    )


# ============================================================
# CAMBIAR PÁGINA
# ============================================================

async def cambiar_pagina(
    update,
    context,
):

    consulta = update.callback_query

    if not consulta:
        return

    datos = consulta.data or ""

    if datos == "pagina_actual":

        await consulta.answer()

        return

    if datos == "sin_semanas":

        await consulta.answer(
            "No hay semanas configuradas.",
            show_alert=True,
        )

        return

    await consulta.answer()

    try:

        _, clave, pagina = datos.split(":")

        pagina = int(pagina)

    except (ValueError, IndexError):

        return

    await consulta.edit_message_reply_markup(
        reply_markup=crear_menu_semanas(
            clave,
            pagina,
        )
    )


# ============================================================
# VOLVER ÁREAS
# ============================================================

async def volver_areas(
    update,
    context,
):

    consulta = update.callback_query

    if not consulta:
        return

    await consulta.answer()

    await consulta.edit_message_text(
        "📁 *Carpetas de Órdenes de Trabajo Semanales*\n\n"
        "Selecciona el área:",
        reply_markup=crear_menu_areas(),
        parse_mode="Markdown",
    )


# ============================================================
# ERRORES
# ============================================================

async def manejar_error(
    update,
    context,
):

    logger.error(
        "Error del bot:",
        exc_info=context.error,
    )


# ============================================================
# INICIO RENDER
# ============================================================

def main():

    if not TOKEN:
        raise ValueError(
            "Falta TELEGRAM_BOT_TOKEN."
        )

    if not URL_RENDER:
        raise ValueError(
            "Falta RENDER_EXTERNAL_URL."
        )

    aplicacion = (
        ApplicationBuilder()
        .token(TOKEN)
        .build()
    )

    # Comandos
    aplicacion.add_handler(
        CommandHandler(
            "start",
            iniciar,
        )
    )

    aplicacion.add_handler(
        CommandHandler(
            "areas",
            mostrar_areas,
        )
    )

    # Botones
    aplicacion.add_handler(
        CallbackQueryHandler(
            seleccionar_area,
            pattern=r"^area:",
        )
    )

    aplicacion.add_handler(
        CallbackQueryHandler(
            cambiar_pagina,
            pattern=r"^(semanas:|pagina_actual|sin_semanas)",
        )
    )

    aplicacion.add_handler(
        CallbackQueryHandler(
            volver_areas,
            pattern=r"^volver_areas$",
        )
    )

    # ========================================================
    # MODERACIÓN
    # Escucha TODOS los mensajes que no hayan sido procesados
    # por los handlers anteriores.
    # ========================================================

    aplicacion.add_handler(
        MessageHandler(
            filters.ALL,
            moderar_mensaje,
        )
    )

    aplicacion.add_error_handler(
        manejar_error
    )

    ruta = "telegram"

    url_webhook = (
        f"{URL_RENDER}/{ruta}"
    )

    print("Bot activo.")
    print(
        f"Webhook: {url_webhook}"
    )

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
