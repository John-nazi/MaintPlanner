import logging
import os
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
)

# ============================================================
# CONFIGURACIÓN GENERAL
# ============================================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

logger = logging.getLogger(__name__)

# Variables configuradas en Render
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
PUERTO = int(os.getenv("PORT", "10000"))
URL_RENDER = os.getenv("RENDER_EXTERNAL_URL")

# Cantidad de semanas mostradas en cada página
SEMANAS_POR_PAGINA = 6


# ============================================================
# ENLACES DE LAS CARPETAS DE SHAREPOINT
# ============================================================
# Reemplaza el texto PEGA_AQUI_LINK_SEMANA_XX por el enlace
# correspondiente de SharePoint.
#
# Ejemplo:
# 30: "https://grupometalsa.sharepoint.com/...",
#
# Las semanas que todavía no tengan un enlace real no
# aparecerán en el menú de Telegram.

CARPETAS_SEMANALES = {
    52: "PEGA_AQUI_LINK_SEMANA_52",
    51: "PEGA_AQUI_LINK_SEMANA_51",
    50: "PEGA_AQUI_LINK_SEMANA_50",
    49: "PEGA_AQUI_LINK_SEMANA_49",
    48: "PEGA_AQUI_LINK_SEMANA_48",
    47: "PEGA_AQUI_LINK_SEMANA_47",
    46: "PEGA_AQUI_LINK_SEMANA_46",
    45: "PEGA_AQUI_LINK_SEMANA_45",
    44: "PEGA_AQUI_LINK_SEMANA_44",
    43: "PEGA_AQUI_LINK_SEMANA_43",
    42: "PEGA_AQUI_LINK_SEMANA_42",
    41: "PEGA_AQUI_LINK_SEMANA_41",
    40: "PEGA_AQUI_LINK_SEMANA_40",
    39: "PEGA_AQUI_LINK_SEMANA_39",
    38: "PEGA_AQUI_LINK_SEMANA_38",
    37: "PEGA_AQUI_LINK_SEMANA_37",
    36: "PEGA_AQUI_LINK_SEMANA_36",
    35: "PEGA_AQUI_LINK_SEMANA_35",
    34: "PEGA_AQUI_LINK_SEMANA_34",
    33: "PEGA_AQUI_LINK_SEMANA_33",
    32: "PEGA_AQUI_LINK_SEMANA_32",
    31: "PEGA_AQUI_LINK_SEMANA_31",
    30: "PEGA_AQUI_LINK_SEMANA_30",
    29: "PEGA_AQUI_LINK_SEMANA_29",
    28: "PEGA_AQUI_LINK_SEMANA_28",
    27: "PEGA_AQUI_LINK_SEMANA_27",
    26: "PEGA_AQUI_LINK_SEMANA_26",
    25: "PEGA_AQUI_LINK_SEMANA_25",
    24: "PEGA_AQUI_LINK_SEMANA_24",
    23: "PEGA_AQUI_LINK_SEMANA_23",
    22: "PEGA_AQUI_LINK_SEMANA_22",
    21: "PEGA_AQUI_LINK_SEMANA_21",
    20: "PEGA_AQUI_LINK_SEMANA_20",
    19: "PEGA_AQUI_LINK_SEMANA_19",
    18: "PEGA_AQUI_LINK_SEMANA_18",
    17: "PEGA_AQUI_LINK_SEMANA_17",
    16: "PEGA_AQUI_LINK_SEMANA_16",
    15: "PEGA_AQUI_LINK_SEMANA_15",
    14: "PEGA_AQUI_LINK_SEMANA_14",
    13: "PEGA_AQUI_LINK_SEMANA_13",
    12: "PEGA_AQUI_LINK_SEMANA_12",
    11: "PEGA_AQUI_LINK_SEMANA_11",
    10: "PEGA_AQUI_LINK_SEMANA_10",
    9: "PEGA_AQUI_LINK_SEMANA_09",
    8: "PEGA_AQUI_LINK_SEMANA_08",
    7: "PEGA_AQUI_LINK_SEMANA_07",
    6: "PEGA_AQUI_LINK_SEMANA_06",
    5: "PEGA_AQUI_LINK_SEMANA_05",
    4: "PEGA_AQUI_LINK_SEMANA_04",
    3: "PEGA_AQUI_LINK_SEMANA_03",
    2: "PEGA_AQUI_LINK_SEMANA_02",
    1: "PEGA_AQUI_LINK_SEMANA_01",
}


# ============================================================
# OBTENER SOLO LAS SEMANAS CON ENLACE CONFIGURADO
# ============================================================

def obtener_carpetas_configuradas() -> dict[int, str]:

    carpetas_configuradas = {}

    for numero_semana, enlace in CARPETAS_SEMANALES.items():

        enlace = enlace.strip()

        if not enlace:
            continue

        if enlace.startswith("PEGA_AQUI_LINK_SEMANA_"):
            continue

        if not enlace.startswith(("https://", "http://")):
            continue

        carpetas_configuradas[numero_semana] = enlace

    return carpetas_configuradas


# ============================================================
# CREAR MENÚ PAGINADO
# ============================================================

def crear_menu_semanas(pagina: int = 0) -> InlineKeyboardMarkup:

    carpetas = obtener_carpetas_configuradas()

    semanas = sorted(
        carpetas.keys(),
        reverse=True,
    )

    total_semanas = len(semanas)

    if total_semanas == 0:
        return InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        text="⚠️ No hay semanas configuradas",
                        callback_data="sin_semanas",
                    )
                ]
            ]
        )

    total_paginas = ceil(
        total_semanas / SEMANAS_POR_PAGINA
    )

    pagina = max(
        0,
        min(pagina, total_paginas - 1),
    )

    posicion_inicial = pagina * SEMANAS_POR_PAGINA
    posicion_final = posicion_inicial + SEMANAS_POR_PAGINA

    semanas_visibles = semanas[
        posicion_inicial:posicion_final
    ]

    botones = []

    # Botones de las carpetas
    for numero_semana in semanas_visibles:

        botones.append(
            [
                InlineKeyboardButton(
                    text=f"📁 SEMANA {numero_semana:02d}",
                    url=carpetas[numero_semana],
                )
            ]
        )

    # Botones de navegación
    botones_navegacion = []

    if pagina > 0:
        botones_navegacion.append(
            InlineKeyboardButton(
                text="◀ Anterior",
                callback_data=f"pagina:{pagina - 1}",
            )
        )

    botones_navegacion.append(
        InlineKeyboardButton(
            text=f"{pagina + 1} de {total_paginas}",
            callback_data="pagina_actual",
        )
    )

    if pagina < total_paginas - 1:
        botones_navegacion.append(
            InlineKeyboardButton(
                text="Siguiente ▶",
                callback_data=f"pagina:{pagina + 1}",
            )
        )

    botones.append(botones_navegacion)

    botones.append(
        [
            InlineKeyboardButton(
                text="🔄 Actualizar",
                callback_data=f"pagina:{pagina}",
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

    await update.message.reply_text(
        "🤖 *Bot de Planeación activo*\n\n"
        "Utiliza el comando /semanas para consultar "
        "las carpetas de Órdenes de Trabajo Semanales.",
        parse_mode="Markdown",
    )


# ============================================================
# COMANDO /SEMANAS
# ============================================================

async def mostrar_semanas(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:

    if update.message is None:
        return

    carpetas = obtener_carpetas_configuradas()

    if not carpetas:
        await update.message.reply_text(
            "⚠️ No hay carpetas semanales configuradas.\n\n"
            "Agrega los enlaces de SharePoint dentro del archivo "
            "`Planneador_Bot.py`.",
            parse_mode="Markdown",
        )
        return

    await update.message.reply_text(
        "📁 *Carpetas de Órdenes de Trabajo Semanales*\n\n"
        "Selecciona la semana correspondiente en la que "
        "deseas trabajar:",
        reply_markup=crear_menu_semanas(0),
        parse_mode="Markdown",
    )


# ============================================================
# CAMBIAR DE PÁGINA
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
            "No hay semanas configuradas.",
            show_alert=True,
        )
        return

    await consulta.answer()

    try:
        pagina = int(datos.split(":")[1])

    except (IndexError, ValueError):
        pagina = 0

    await consulta.edit_message_reply_markup(
        reply_markup=crear_menu_semanas(pagina)
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
            "No se encontró la variable TELEGRAM_BOT_TOKEN."
        )

    if not URL_RENDER:
        raise ValueError(
            "No se encontró la variable RENDER_EXTERNAL_URL."
        )

    aplicacion = (
        ApplicationBuilder()
        .token(TOKEN)
        .build()
    )

    aplicacion.add_handler(
        CommandHandler(
            "start",
            iniciar,
        )
    )

    aplicacion.add_handler(
        CommandHandler(
            "semanas",
            mostrar_semanas,
        )
    )

    aplicacion.add_handler(
        CallbackQueryHandler(
            cambiar_pagina,
            pattern=r"^(pagina:|pagina_actual|sin_semanas)",
        )
    )

    aplicacion.add_error_handler(
        manejar_error
    )

    ruta_webhook = "telegram"
    url_webhook = f"{URL_RENDER}/{ruta_webhook}"

    print("Bot de Planeación activo.")
    print(f"Webhook activo: {url_webhook}")

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
