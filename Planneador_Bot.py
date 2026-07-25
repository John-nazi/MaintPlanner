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

# Semanas visibles por página
SEMANAS_POR_PAGINA = 6

# Tiempo para borrar los mensajes normales enviados por el bot
TIEMPO_BORRADO_MENSAJES_BOT = 60

# Tiempo para borrar el aviso por lenguaje ofensivo
TIEMPO_BORRADO_AVISO = 15

# Mostrar aviso cuando se elimine un mensaje
MOSTRAR_AVISO_OFENSIVO = True


# ============================================================
# PALABRAS OFENSIVAS
# ============================================================
# Puedes agregar o quitar palabras.
# No importa si el usuario escribe mayúsculas o acentos.

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

    # Agrega más aquí:
    # "palabra",
    # "otra palabra",
]


# ============================================================
# ÁREAS Y CARPETAS SEMANALES
# ============================================================

AREAS = {

    # --------------------------------------------------------
    # PINTURA Y SECUENCIADO
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # ECO-CUSTOM
    # --------------------------------------------------------

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
# BORRAR MENSAJES AUTOMÁTICAMENTE
# ============================================================

async def borrar_mensaje_despues(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    message_id: int,
    segundos: int,
) -> None:

    await asyncio.sleep(segundos)

    try:
        await context.bot.delete_message(
            chat_id=chat_id,
            message_id=message_id,
        )

    except Exception as error:
        logger.warning(
            "No se pudo borrar el mensaje %s: %s",
            message_id,
            error,
        )


def programar_borrado(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    message_id: int,
    segundos: int,
) -> None:

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

def normalizar_texto(texto: str) -> str:

    texto = texto.lower()

    texto = unicodedata.normalize(
        "NFD",
        texto,
    )

    texto = "".join(
        caracter
        for caracter in texto
        if unicodedata.category(caracter) != "Mn"
    )

    return texto


# ============================================================
# DETECTAR PALABRAS OFENSIVAS
# ============================================================

def contiene_palabra_prohibida(texto: str) -> bool:

    texto_normalizado = normalizar_texto(texto)

    for palabra in PALABRAS_PROHIBIDAS:

        palabra_normalizada = normalizar_texto(
            palabra.strip()
        )

        if not palabra_normalizada:
            continue

        patron = (
            r"(?<!\w)"
            + re.escape(palabra_normalizada)
            + r"(?!\w)"
        )

        if re.search(
            patron,
            texto_normalizado,
            flags=re.IGNORECASE,
        ):
            return True

    return False


# ============================================================
# MODERAR MENSAJES DEL GRUPO
# ============================================================

async def moderar_mensaje(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:

    mensaje = update.message

    if mensaje is None:
        return

    # Ignorar mensajes enviados por bots
    if mensaje.from_user and mensaje.from_user.is_bot:
        return

    texto = mensaje.text or mensaje.caption or ""

    if not texto:
        return

    if not contiene_palabra_prohibida(texto):
        return

    try:

        await mensaje.delete()

        logger.info(
            "Mensaje ofensivo eliminado en chat %s.",
            mensaje.chat_id,
        )

    except Exception as error:

        logger.warning(
            "No se pudo eliminar el mensaje ofensivo: %s",
            error,
        )

        return

    # Aviso temporal
    if MOSTRAR_AVISO_OFENSIVO:

        aviso = await context.bot.send_message(
            chat_id=mensaje.chat_id,
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


# ============================================================
# OBTENER SEMANAS CONFIGURADAS
# ============================================================

def obtener_semanas_configuradas(
    clave_area: str,
) -> dict[int, str]:

    area = AREAS.get(clave_area)

    if not area:
        return {}

    semanas_configuradas = {}

    for numero_semana, enlace in area["semanas"].items():

        enlace = enlace.strip()

        if not enlace:
            continue

        if enlace.startswith("PEGA_AQUI_LINK_"):
            continue

        if not enlace.startswith(
            ("https://", "http://")
        ):
            continue

        semanas_configuradas[
            numero_semana
        ] = enlace

    return semanas_configuradas


# ============================================================
# MENÚ DE ÁREAS
# ============================================================

def crear_menu_areas() -> InlineKeyboardMarkup:

    botones = []

    for clave_area, datos_area in AREAS.items():

        botones.append(
            [
                InlineKeyboardButton(
                    text=(
                        f"{datos_area['icono']} "
                        f"{datos_area['nombre']}"
                    ),
                    callback_data=f"area:{clave_area}",
                )
            ]
        )

    return InlineKeyboardMarkup(botones)


# ============================================================
# MENÚ DE SEMANAS
# ============================================================

def crear_menu_semanas(
    clave_area: str,
    pagina: int = 0,
) -> InlineKeyboardMarkup:

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
                    text="⚠️ No hay semanas configuradas",
                    callback_data="sin_semanas",
                )
            ]
        )

        botones.append(
            [
                InlineKeyboardButton(
                    text="⬅ Volver a las áreas",
                    callback_data="volver_areas",
                )
            ]
        )

        return InlineKeyboardMarkup(botones)

    total_paginas = ceil(
        len(semanas) / SEMANAS_POR_PAGINA
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

    semanas_visibles = semanas[
        inicio:fin
    ]

    for numero_semana in semanas_visibles:

        botones.append(
            [
                InlineKeyboardButton(
                    text=(
                        f"📁 SEMANA "
                        f"{numero_semana:02d}"
                    ),
                    url=(
                        semanas_configuradas[
                            numero_semana
                        ]
                    ),
                )
            ]
        )

    navegacion = []

    if pagina > 0:

        navegacion.append(
            InlineKeyboardButton(
                text="◀ Anterior",
                callback_data=(
                    f"semanas:"
                    f"{clave_area}:"
                    f"{pagina - 1}"
                ),
            )
        )

    navegacion.append(
        InlineKeyboardButton(
            text=(
                f"{pagina + 1} "
                f"de {total_paginas}"
            ),
            callback_data="pagina_actual",
        )
    )

    if pagina < total_paginas - 1:

        navegacion.append(
            InlineKeyboardButton(
                text="Siguiente ▶",
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
                text="⬅ Volver a las áreas",
                callback_data="volver_areas",
            )
        ]
    )

    return InlineKeyboardMarkup(botones)


# ============================================================
# COMANDO /START
# ============================================================

async def iniciar(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:

    if update.message is None:
        return

    mensaje = await update.message.reply_text(
        "🤖 *Bot de Planeación activo*\n\n"
        "Utiliza el comando /areas para consultar "
        "las carpetas de Órdenes de Trabajo Semanales.",
        parse_mode="Markdown",
    )

    programar_borrado(
        context,
        mensaje.chat_id,
        mensaje.message_id,
        TIEMPO_BORRADO_MENSAJES_BOT,
    )


# ============================================================
# COMANDO /AREAS
# ============================================================

async def mostrar_areas(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:

    if update.message is None:
        return

    mensaje = await update.message.reply_text(
        "📁 *Carpetas de Órdenes de Trabajo Semanales*\n\n"
        "Selecciona el área:",
        reply_markup=crear_menu_areas(),
        parse_mode="Markdown",
    )

    programar_borrado(
        context,
        mensaje.chat_id,
        mensaje.message_id,
        TIEMPO_BORRADO_MENSAJES_BOT,
    )


# ============================================================
# SELECCIONAR ÁREA
# ============================================================

async def seleccionar_area(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:

    consulta = update.callback_query

    if consulta is None:
        return

    await consulta.answer()

    datos = consulta.data or ""

    try:
        clave_area = datos.split(":")[1]

    except IndexError:
        return

    area = AREAS.get(clave_area)

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
            clave_area,
            0,
        ),
        parse_mode="Markdown",
    )


# ============================================================
# CAMBIAR PÁGINA
# ============================================================

async def cambiar_pagina(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:

    consulta = update.callback_query

    if consulta is None:
        return

    datos = consulta.data or ""

    if datos == "pagina_actual":

        await consulta.answer(
            "Indicador de página."
        )

        return

    if datos == "sin_semanas":

        await consulta.answer(
            "Todavía no hay semanas "
            "configuradas para esta área.",
            show_alert=True,
        )

        return

    await consulta.answer()

    try:

        _, clave_area, pagina_texto = (
            datos.split(":")
        )

        pagina = int(
            pagina_texto
        )

    except (ValueError, IndexError):
        return

    await consulta.edit_message_reply_markup(
        reply_markup=crear_menu_semanas(
            clave_area,
            pagina,
        )
    )


# ============================================================
# VOLVER AL MENÚ DE ÁREAS
# ============================================================

async def volver_areas(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:

    consulta = update.callback_query

    if consulta is None:
        return

    await consulta.answer()

    await consulta.edit_message_text(
        text=(
            "📁 *Carpetas de Órdenes de Trabajo Semanales*\n\n"
            "Selecciona el área:"
        ),
        reply_markup=crear_menu_areas(),
        parse_mode="Markdown",
    )


# ============================================================
# MANEJO DE ERRORES
# ============================================================

async def manejar_error(
    update: object,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:

    logger.error(
        "Ocurrió un error en el bot:",
        exc_info=context.error,
    )


# ============================================================
# INICIAR BOT EN RENDER
# ============================================================

def main() -> None:

    if not TOKEN:
        raise ValueError(
            "No se encontró la variable "
            "TELEGRAM_BOT_TOKEN."
        )

    if not URL_RENDER:
        raise ValueError(
            "No se encontró la variable "
            "RENDER_EXTERNAL_URL."
        )

    aplicacion = (
        ApplicationBuilder()
        .token(TOKEN)
        .build()
    )

    # --------------------------------------------------------
    # COMANDOS
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # BOTONES
    # --------------------------------------------------------

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

    # --------------------------------------------------------
    # MODERACIÓN AUTOMÁTICA
    # --------------------------------------------------------

    aplicacion.add_handler(
        MessageHandler(
            (
                filters.TEXT
                | filters.CaptionRegex(r".+")
            )
            & ~filters.COMMAND,
            moderar_mensaje,
        )
    )

    # --------------------------------------------------------
    # ERRORES
    # --------------------------------------------------------

    aplicacion.add_error_handler(
        manejar_error
    )

    # --------------------------------------------------------
    # WEBHOOK RENDER
    # --------------------------------------------------------

    ruta_webhook = "telegram"

    url_webhook = (
        f"{URL_RENDER}/"
        f"{ruta_webhook}"
    )

    print(
        "Bot de Planeación activo."
    )

    print(
        f"Webhook activo: {url_webhook}"
    )

    aplicacion.run_webhook(
        listen="0.0.0.0",
        port=PUERTO,
        url_path=ruta_webhook,
        webhook_url=url_webhook,
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    main()
