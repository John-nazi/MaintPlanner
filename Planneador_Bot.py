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

TIEMPO_BORRADO = 60
TIEMPO_BORRADO_AVISO = 5

ONLYOFFICE_USERNAME = "onlyoffice_bot"


# ============================================================
# PDFs PENDIENTES DE EDICIÓN
#
# Se guardan temporalmente:
# chat + tema + nombre + message_id
#
# No almacena el PDF.
# ============================================================

PDF_PENDIENTES = []


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
    "culo",
]


# ============================================================
# ÁREAS
# ============================================================

AREAS = {
    "pintura": {
        "nombre": "Pintura y Secuenciado",
        "icono": "🔴",
        "semanas": {
            numero: f"PEGA_AQUI_LINK_PINTURA_SEMANA_{numero:02d}"
            for numero in range(52, 0, -1)
        },
    },

    "eco_custom": {
        "nombre": "Eco-Custom",
        "icono": "🟢",
        "semanas": {
            numero: f"PEGA_AQUI_LINK_ECO_CUSTOM_SEMANA_{numero:02d}"
            for numero in range(52, 0, -1)
        },
    },
}


# ============================================================
# VALIDAR COMANDOS
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

        except Exception as error:
            logger.warning(
                "No se pudo obtener el username del bot: %s",
                error,
            )
            return False

        return destinatario == nuestro_usuario

    return False


# ============================================================
# BORRADO PROGRAMADO
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
# PALABRAS PROHIBIDAS
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
# REGISTRAR PDF ORIGINAL
# ============================================================

def registrar_pdf_original(mensaje):

    documento = mensaje.document

    if documento is None:
        return

    nombre = documento.file_name or ""

    if not nombre.lower().endswith(".pdf"):
        return

    registro = {
        "chat_id": mensaje.chat_id,
        "tema": mensaje.message_thread_id,
        "message_id": mensaje.message_id,
        "nombre": nombre,
    }

    PDF_PENDIENTES.append(registro)

    logger.info(
        "PDF ORIGINAL REGISTRADO | chat=%s | tema=%s | "
        "message_id=%s | archivo=%s",
        registro["chat_id"],
        registro["tema"],
        registro["message_id"],
        registro["nombre"],
    )


# ============================================================
# BUSCAR PDF ORIGINAL
# ============================================================

def buscar_pdf_original(
    chat_id,
    tema,
    nombre_archivo,
):

    nombre_archivo = (
        nombre_archivo or ""
    ).lower()

    # Buscar del más reciente al más antiguo
    for indice in range(
        len(PDF_PENDIENTES) - 1,
        -1,
        -1,
    ):

        registro = PDF_PENDIENTES[indice]

        if registro["chat_id"] != chat_id:
            continue

        if registro["tema"] != tema:
            continue

        if registro["nombre"].lower() != nombre_archivo:
            continue

        return indice, registro

    return None, None


# ============================================================
# PROCESAR PDF FINAL DE ONLYOFFICE
# ============================================================

async def procesar_onlyoffice(
    mensaje,
    context,
):

    remitente = mensaje.from_user

    if remitente is None:
        return False

    username = (
        remitente.username or ""
    ).lower()

    if not remitente.is_bot:
        return False

    if username != ONLYOFFICE_USERNAME:
        return False

    documento = mensaje.document

    texto = (
        mensaje.text
        or mensaje.caption
        or ""
    )

    logger.info(
        "ONLYOFFICE DETECTADO | message_id=%s | tema=%s | "
        "archivo=%s | texto=%r",
        mensaje.message_id,
        mensaje.message_thread_id,
        documento.file_name if documento else None,
        texto,
    )

    # No es todavía el PDF final
    if documento is None:
        return True

    nombre_final = documento.file_name or ""

    if not nombre_final.lower().endswith(".pdf"):
        return True

    # Confirmación que usa ONLYOFFICE al devolver la versión final
    if (
        "your file is ready" not in texto.lower()
        and "final version" not in texto.lower()
    ):
        return True

    indice, original = buscar_pdf_original(
        mensaje.chat_id,
        mensaje.message_thread_id,
        nombre_final,
    )

    if original is None:

        logger.warning(
            "PDF FINAL RECIBIDO PERO NO SE ENCONTRÓ ORIGINAL | "
            "archivo=%s | tema=%s",
            nombre_final,
            mensaje.message_thread_id,
        )

        return True

    # ========================================================
    # ELIMINAR PDF ORIGINAL
    # ========================================================

    try:

        await context.bot.delete_message(
            chat_id=original["chat_id"],
            message_id=original["message_id"],
        )

        logger.info(
            "PDF ORIGINAL ELIMINADO | message_id=%s | archivo=%s",
            original["message_id"],
            original["nombre"],
        )

        # Ya no necesitamos ese registro
        PDF_PENDIENTES.pop(indice)

    except Exception as error:

        logger.error(
            "NO SE PUDO ELIMINAR PDF ORIGINAL | "
            "message_id=%s | error=%s",
            original["message_id"],
            error,
        )

    return True


# ============================================================
# MENSAJES + ONLYOFFICE + MODERACIÓN
# ============================================================

async def procesar_mensaje(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    mensaje = update.effective_message

    if mensaje is None:
        return

    texto = (
        mensaje.text
        or mensaje.caption
        or ""
    )

    remitente = mensaje.from_user
    documento = mensaje.document

    # ========================================================
    # LOG DETALLADO
    # ========================================================

    logger.info(
        "MENSAJE RECIBIDO | chat=%s | tipo=%s | tema=%s | texto=%r",
        mensaje.chat_id,
        mensaje.chat.type if mensaje.chat else None,
        mensaje.message_thread_id,
        texto,
    )

    logger.info(
        "DETALLE MENSAJE | sender_id=%s | username=%s | "
        "es_bot=%s | message_id=%s | tema=%s | "
        "archivo=%s | file_id=%s",
        remitente.id if remitente else None,
        remitente.username if remitente else None,
        remitente.is_bot if remitente else None,
        mensaje.message_id,
        mensaje.message_thread_id,
        documento.file_name if documento else None,
        documento.file_id if documento else None,
    )

    # ========================================================
    # MENSAJES DE ONLYOFFICE
    # ========================================================

    if (
        remitente
        and remitente.is_bot
        and (remitente.username or "").lower()
        == ONLYOFFICE_USERNAME
    ):

        await procesar_onlyoffice(
            mensaje,
            context,
        )

        return

    # ========================================================
    # REGISTRAR PDFs NORMALES
    #
    # Puede ser un usuario normal o GroupAnonymousBot.
    # ========================================================

    if documento:

        nombre = documento.file_name or ""

        if nombre.lower().endswith(".pdf"):

            registrar_pdf_original(
                mensaje
            )

    # ========================================================
    # MODERACIÓN
    # ========================================================

    if not texto:
        return

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

        if enlace.startswith(
            "PEGA_AQUI_LINK_"
        ):
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

    return InlineKeyboardMarkup(
        botones
    )


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

        return InlineKeyboardMarkup(
            botones
        )

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

    botones.append(
        navegacion
    )

    botones.append(
        [
            InlineKeyboardButton(
                "⬅ Volver a las áreas",
                callback_data="volver_areas",
            )
        ]
    )

    return InlineKeyboardMarkup(
        botones
    )


# ============================================================
# /START
# ============================================================

async def iniciar(
    update,
    context,
):

    if not await comando_es_para_este_bot(
        update,
        context,
        "start",
    ):
        return

    mensaje = update.effective_message

    if mensaje is None:
        return

    programar_borrado(
        context,
        mensaje.chat_id,
        mensaje.message_id,
    )

    respuesta = await mensaje.reply_text(
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

    if not await comando_es_para_este_bot(
        update,
        context,
        "areas",
    ):
        return

    mensaje = update.effective_message

    if mensaje is None:
        return

    programar_borrado(
        context,
        mensaje.chat_id,
        mensaje.message_id,
    )

    respuesta = await mensaje.reply_text(
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

    area = AREAS.get(
        clave
    )

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

        _, clave, pagina = (
            datos.split(":")
        )

        pagina = int(
            pagina
        )

    except (
        ValueError,
        IndexError,
    ):
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

    # ========================================================
    # COMANDOS
    # ========================================================

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

    # ========================================================
    # BOTONES
    # ========================================================

    aplicacion.add_handler(
        CallbackQueryHandler(
            seleccionar_area,
            pattern=r"^area:",
        )
    )

    aplicacion.add_handler(
        CallbackQueryHandler(
            cambiar_pagina,
            pattern=(
                r"^(semanas:|"
                r"pagina_actual|"
                r"sin_semanas)"
            ),
        )
    )

    aplicacion.add_handler(
        CallbackQueryHandler(
            volver_areas,
            pattern=r"^volver_areas$",
        )
    )

    # ========================================================
    # TODOS LOS MENSAJES
    # ========================================================

    aplicacion.add_handler(
        MessageHandler(
            filters.ALL,
            procesar_mensaje,
        )
    )

    aplicacion.add_error_handler(
        manejar_error
    )

    # ========================================================
    # WEBHOOK RENDER
    # ========================================================

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
