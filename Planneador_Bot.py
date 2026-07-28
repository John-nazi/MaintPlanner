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

# Borrado de comandos y respuestas temporales
TIEMPO_BORRADO = 60

# Aviso de moderación
TIEMPO_BORRADO_AVISO = 5

# Usuario oficial de ONLYOFFICE
ONLYOFFICE_USERNAME = "onlyoffice_bot"


# ============================================================
# EDICIONES ACTIVAS EN MEMORIA
#
# Compatible con Render Free:
# - No utiliza Disk.
# - No requiere BOT_DATA_DIR.
# - El registro se reconstruye desde el PDF al que responde
#   el comando /open@ONLYOFFICE_bot.
#
# IMPORTANTE:
# El comando /open debe enviarse respondiendo directamente
# al PDF que se desea editar.
# ============================================================

PDF_PENDIENTES = []


def ahora_utc_iso():

    return datetime.now(
        timezone.utc
    ).isoformat()


def cargar_estado():

    # En Render Free no se usa almacenamiento persistente.
    return


def guardar_estado():

    # Los registros viven únicamente mientras el proceso está activo.
    return


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
# EXTRAER ID ÚNICO DE OT
#
# Ejemplo:
#
# 24797437_Reemplazo_Baleros.pdf
#
# Devuelve:
#
# 24797437
# ============================================================

def extraer_id_ot(nombre_archivo):

    if not nombre_archivo:
        return None

    nombre_archivo = nombre_archivo.strip()

    coincidencia = re.match(
        r"^(\d+)_",
        nombre_archivo,
    )

    if not coincidencia:
        return None

    return coincidencia.group(1)


# ============================================================
# VALIDAR QUE EL COMANDO SEA PARA NUESTRO BOT
# ============================================================

async def comando_es_para_este_bot(
    update,
    context,
    comando,
):

    mensaje = update.effective_message

    if mensaje is None or not mensaje.text:
        return False

    primera_parte = (
        mensaje.text
        .split()[0]
        .lower()
    )

    comando_base = f"/{comando.lower()}"

    # Ejemplo:
    # /start
    if primera_parte == comando_base:
        return True

    # Ejemplo:
    # /start@Planeador_IA_Bot
    if primera_parte.startswith(
        comando_base + "@"
    ):

        destinatario = (
            primera_parte
            .split("@", 1)[1]
        )

        try:

            datos_bot = await context.bot.get_me()

            nuestro_usuario = (
                datos_bot.username or ""
            ).lower()

        except Exception as error:

            logger.warning(
                "No se pudo obtener el username del bot: %s",
                error,
            )

            return False

        return destinatario == nuestro_usuario

    return False


# ============================================================
# BORRAR MENSAJE DESPUÉS DE X SEGUNDOS
# ============================================================

async def borrar_mensaje_despues(
    context,
    chat_id,
    message_id,
    segundos,
):

    await asyncio.sleep(
        segundos
    )

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

    texto = normalizar_texto(
        texto
    )

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

        if re.search(
            patron,
            texto,
        ):
            return True

    return False


# ============================================================
# EXTRAER ID DE OT DESDE TEXTO GENERAL
#
# Detecta, por ejemplo:
# 24940262_Ensayos_no_destructivos.pdf
# ============================================================

def extraer_id_ot_de_texto(
    texto,
):

    if not texto:
        return None

    coincidencia = re.search(
        r"(?<!\d)(\d{6,})_",
        texto,
    )

    if not coincidencia:
        return None

    return coincidencia.group(1)


# ============================================================
# REGISTRAR PDF ORIGINAL
# ============================================================

def registrar_pdf_original(
    mensaje,
):

    documento = mensaje.document

    if documento is None:
        return

    nombre = (
        documento.file_name
        or ""
    )

    if not nombre.lower().endswith(
        ".pdf"
    ):
        return

    id_ot = extraer_id_ot(
        nombre
    )

    if not id_ot:

        logger.info(
            "PDF IGNORADO SIN ID DE OT | "
            "archivo=%s",
            nombre,
        )

        return

    # Evitar duplicar el mismo mensaje si Telegram reenvía
    # una actualización después de un reinicio.
    for registro in PDF_PENDIENTES:

        if (
            registro.get("chat_id")
            == mensaje.chat_id
            and registro.get("message_id")
            == mensaje.message_id
        ):

            return

    registro = {
        "chat_id": mensaje.chat_id,
        "tema": mensaje.message_thread_id,
        "message_id": mensaje.message_id,
        "nombre": nombre,
        "id_ot": id_ot,
        "message_ids_limpieza": [
            mensaje.message_id,
        ],
        "creado_en": ahora_utc_iso(),
        "actualizado_en": ahora_utc_iso(),
    }

    PDF_PENDIENTES.append(
        registro
    )

    guardar_estado()

    logger.info(
        "PDF ORIGINAL REGISTRADO | "
        "ID_OT=%s | chat=%s | tema=%s | "
        "message_id=%s | archivo=%s",
        id_ot,
        registro["chat_id"],
        registro["tema"],
        registro["message_id"],
        registro["nombre"],
    )


# ============================================================
# BUSCAR ORIGINAL POR ID DE OT
# ============================================================

def buscar_pdf_original(
    chat_id,
    tema,
    id_ot,
):

    for indice in range(
        len(PDF_PENDIENTES) - 1,
        -1,
        -1,
    ):

        registro = (
            PDF_PENDIENTES[indice]
        )

        if (
            registro.get("chat_id")
            != chat_id
        ):
            continue

        if (
            registro.get("tema")
            != tema
        ):
            continue

        if (
            str(registro.get("id_ot"))
            != str(id_ot)
        ):
            continue

        return (
            indice,
            registro,
        )

    return (
        None,
        None,
    )


# ============================================================
# BUSCAR REGISTRO POR CUALQUIER MENSAJE RELACIONADO
# ============================================================

def buscar_por_message_id(
    chat_id,
    tema,
    message_id,
):

    if message_id is None:
        return None, None

    for indice in range(
        len(PDF_PENDIENTES) - 1,
        -1,
        -1,
    ):

        registro = (
            PDF_PENDIENTES[indice]
        )

        if (
            registro.get("chat_id")
            != chat_id
        ):
            continue

        if (
            registro.get("tema")
            != tema
        ):
            continue

        mensajes = registro.get(
            "message_ids_limpieza",
            [],
        )

        if (
            registro.get("message_id")
            == message_id
            or message_id in mensajes
        ):

            return (
                indice,
                registro,
            )

    return (
        None,
        None,
    )


# ============================================================
# BUSCAR PDF PENDIENTE MÁS RECIENTE DEL CHAT/TEMA
# ============================================================

def buscar_pdf_pendiente_reciente(
    chat_id,
    tema,
):

    for indice in range(
        len(PDF_PENDIENTES) - 1,
        -1,
        -1,
    ):

        registro = (
            PDF_PENDIENTES[indice]
        )

        if (
            registro.get("chat_id")
            != chat_id
        ):
            continue

        if (
            registro.get("tema")
            != tema
        ):
            continue

        return (
            indice,
            registro,
        )

    return (
        None,
        None,
    )


# ============================================================
# AGREGAR MENSAJE A LA LIMPIEZA DE UNA OT
# ============================================================

def agregar_mensaje_a_limpieza(
    registro,
    message_id,
):

    if (
        registro is None
        or message_id is None
    ):
        return False

    mensajes = registro.setdefault(
        "message_ids_limpieza",
        [],
    )

    if message_id in mensajes:
        return False

    mensajes.append(
        message_id
    )

    registro["actualizado_en"] = (
        ahora_utc_iso()
    )

    guardar_estado()

    return True


# ============================================================
# RECONSTRUIR REGISTRO DESDE EL PDF RESPONDIDO
#
# Esto permite funcionar aunque Render haya reiniciado antes
# de que el usuario envíe /open.
# ============================================================

def reconstruir_registro_desde_pdf_respondido(
    mensaje,
):

    respondido = mensaje.reply_to_message

    if respondido is None:
        return None, None

    documento = respondido.document

    if documento is None:
        return None, None

    nombre = (
        documento.file_name
        or ""
    )

    if not nombre.lower().endswith(
        ".pdf"
    ):
        return None, None

    id_ot = extraer_id_ot(
        nombre
    )

    if not id_ot:
        return None, None

    # Si ya existe, reutilizarlo.
    indice, existente = (
        buscar_pdf_original(
            mensaje.chat_id,
            mensaje.message_thread_id,
            id_ot,
        )
    )

    if existente is not None:

        agregar_mensaje_a_limpieza(
            existente,
            respondido.message_id,
        )

        return indice, existente

    registro = {
        "chat_id": mensaje.chat_id,
        "tema": mensaje.message_thread_id,
        "message_id": respondido.message_id,
        "nombre": nombre,
        "id_ot": id_ot,
        "message_ids_limpieza": [
            respondido.message_id,
        ],
        "creado_en": ahora_utc_iso(),
        "actualizado_en": ahora_utc_iso(),
    }

    PDF_PENDIENTES.append(
        registro
    )

    indice = (
        len(PDF_PENDIENTES) - 1
    )

    logger.info(
        "REGISTRO RECONSTRUIDO DESDE RESPUESTA | "
        "ID_OT=%s | original_message_id=%s | "
        "archivo=%s",
        id_ot,
        respondido.message_id,
        nombre,
    )

    return indice, registro


# ============================================================
# IDENTIFICAR A QUÉ OT PERTENECE UN MENSAJE
#
# Prioridad:
# 1. ID de OT presente en archivo/texto.
# 2. Mensaje al que está respondiendo.
# 3. PDF pendiente más reciente del mismo tema.
# ============================================================

def identificar_registro_del_mensaje(
    mensaje,
):

    documento = mensaje.document

    texto = (
        mensaje.text
        or mensaje.caption
        or ""
    )

    id_ot = None

    if documento is not None:

        id_ot = extraer_id_ot(
            documento.file_name
            or ""
        )

    if not id_ot:

        id_ot = extraer_id_ot_de_texto(
            texto
        )

    if id_ot:

        indice, registro = (
            buscar_pdf_original(
                mensaje.chat_id,
                mensaje.message_thread_id,
                id_ot,
            )
        )

        if registro is not None:
            return indice, registro

    respondido = (
        mensaje.reply_to_message
    )

    if respondido is not None:

        indice, registro = (
            buscar_por_message_id(
                mensaje.chat_id,
                mensaje.message_thread_id,
                respondido.message_id,
            )
        )

        if registro is not None:
            return indice, registro

        documento_respondido = (
            respondido.document
        )

        if documento_respondido is not None:

            id_ot_respondido = extraer_id_ot(
                documento_respondido.file_name
                or ""
            )

            if id_ot_respondido:

                indice, registro = (
                    buscar_pdf_original(
                        mensaje.chat_id,
                        mensaje.message_thread_id,
                        id_ot_respondido,
                    )
                )

                if registro is not None:
                    return indice, registro

                # Si Render se reinició y perdió la memoria,
                # reconstruir el registro desde el PDF original
                # incluido en reply_to_message.
                indice, registro = (
                    reconstruir_registro_desde_pdf_respondido(
                        mensaje
                    )
                )

                if registro is not None:
                    return indice, registro

    return buscar_pdf_pendiente_reciente(
        mensaje.chat_id,
        mensaje.message_thread_id,
    )


# ============================================================
# BORRAR MENSAJES RELACIONADOS CON LA EDICIÓN
#
# Conserva únicamente el mensaje con el PDF final.
# ============================================================

async def limpiar_mensajes_edicion(
    context,
    registro,
    message_id_final,
):

    mensajes = list(
        dict.fromkeys(
            registro.get(
                "message_ids_limpieza",
                [],
            )
        )
    )

    original_id = registro.get(
        "message_id"
    )

    if (
        original_id is not None
        and original_id not in mensajes
    ):
        mensajes.insert(
            0,
            original_id,
        )

    eliminados = 0
    fallidos = 0

    for message_id in mensajes:

        if message_id == message_id_final:
            continue

        try:

            await context.bot.delete_message(
                chat_id=registro["chat_id"],
                message_id=message_id,
            )

            eliminados += 1

            logger.info(
                "MENSAJE DE EDICIÓN ELIMINADO | "
                "ID_OT=%s | message_id=%s",
                registro["id_ot"],
                message_id,
            )

        except Exception as error:

            fallidos += 1

            logger.warning(
                "NO SE PUDO ELIMINAR MENSAJE DE EDICIÓN | "
                "ID_OT=%s | message_id=%s | error=%s",
                registro["id_ot"],
                message_id,
                error,
            )

    return eliminados, fallidos


# ============================================================
# PROCESAR MENSAJE DE ONLYOFFICE
# ============================================================

async def procesar_onlyoffice(
    mensaje,
    context,
):

    remitente = mensaje.from_user

    if remitente is None:
        return False

    username = (
        remitente.username
        or ""
    ).lower()

    if (
        not remitente.is_bot
        or username
        != ONLYOFFICE_USERNAME
    ):
        return False

    documento = mensaje.document

    texto = (
        mensaje.text
        or mensaje.caption
        or ""
    )

    logger.info(
        "ONLYOFFICE DETECTADO | "
        "message_id=%s | tema=%s | "
        "archivo=%s | texto=%r",
        mensaje.message_id,
        mensaje.message_thread_id,
        (
            documento.file_name
            if documento
            else None
        ),
        texto,
    )

    indice_relacionado, registro_relacionado = (
        identificar_registro_del_mensaje(
            mensaje
        )
    )

    if registro_relacionado is not None:

        agregar_mensaje_a_limpieza(
            registro_relacionado,
            mensaje.message_id,
        )

    if documento is None:
        return True

    nombre_final = (
        documento.file_name
        or ""
    )

    if not nombre_final.lower().endswith(
        ".pdf"
    ):
        return True

    id_ot_final = extraer_id_ot(
        nombre_final
    )

    if not id_ot_final:

        logger.warning(
            "PDF DE ONLYOFFICE SIN ID DE OT | "
            "archivo=%s",
            nombre_final,
        )

        return True

    texto_normalizado = normalizar_texto(
        texto
    )

    es_version_final = any(
        frase in texto_normalizado
        for frase in [
            "your file is ready",
            "final version",
            "su archivo esta listo",
            "version final",
        ]
    )

    if not es_version_final:

        logger.info(
            "MENSAJE ONLYOFFICE NO ES VERSIÓN FINAL | "
            "ID_OT=%s | archivo=%s",
            id_ot_final,
            nombre_final,
        )

        return True

    indice, original = (
        buscar_pdf_original(
            mensaje.chat_id,
            mensaje.message_thread_id,
            id_ot_final,
        )
    )

    if original is None:

        logger.warning(
            "PDF FINAL RECIBIDO PERO NO SE ENCONTRÓ ORIGINAL | "
            "ID_OT=%s | archivo=%s | tema=%s | "
            "modo=memoria_render_free",
            id_ot_final,
            nombre_final,
            mensaje.message_thread_id,
        )

        return True

    # Registrar el mensaje final dentro de la relación,
    # aunque se excluye expresamente durante el borrado.
    agregar_mensaje_a_limpieza(
        original,
        mensaje.message_id,
    )

    logger.info(
        "PDF FINAL DETECTADO | "
        "ID_OT=%s | original_message_id=%s | "
        "final_message_id=%s",
        id_ot_final,
        original["message_id"],
        mensaje.message_id,
    )

    eliminados, fallidos = (
        await limpiar_mensajes_edicion(
            context,
            original,
            mensaje.message_id,
        )
    )

    # El registro se elimina al finalizar para que no vuelva
    # a asociarse con otra edición futura del mismo archivo.
    PDF_PENDIENTES.pop(
        indice
    )

    guardar_estado()

    logger.info(
        "LIMPIEZA FINALIZADA | "
        "ID_OT=%s | eliminados=%s | fallidos=%s | "
        "PDF_FINAL=%s",
        id_ot_final,
        eliminados,
        fallidos,
        mensaje.message_id,
    )

    return True


# ============================================================
# PROCESAR TODOS LOS MENSAJES
# ============================================================

async def procesar_mensaje(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):

    mensaje = (
        update.effective_message
    )

    if mensaje is None:
        return

    texto = (
        mensaje.text
        or mensaje.caption
        or ""
    )

    remitente = (
        mensaje.from_user
    )

    documento = (
        mensaje.document
    )

    # ========================================================
    # LOG GENERAL
    # ========================================================

    logger.info(
        "MENSAJE RECIBIDO | "
        "chat=%s | tipo=%s | "
        "tema=%s | texto=%r",
        mensaje.chat_id,
        (
            mensaje.chat.type
            if mensaje.chat
            else None
        ),
        mensaje.message_thread_id,
        texto,
    )

    # ========================================================
    # LOG DETALLADO
    # ========================================================

    logger.info(
        "DETALLE MENSAJE | "
        "sender_id=%s | "
        "username=%s | "
        "es_bot=%s | "
        "message_id=%s | "
        "tema=%s | "
        "archivo=%s | "
        "file_id=%s | "
        "reply_to_message_id=%s | "
        "reply_to_archivo=%s",
        (
            remitente.id
            if remitente
            else None
        ),
        (
            remitente.username
            if remitente
            else None
        ),
        (
            remitente.is_bot
            if remitente
            else None
        ),
        mensaje.message_id,
        mensaje.message_thread_id,
        (
            documento.file_name
            if documento
            else None
        ),
        (
            documento.file_id
            if documento
            else None
        ),
        (
            mensaje.reply_to_message.message_id
            if mensaje.reply_to_message
            else None
        ),
        (
            mensaje.reply_to_message.document.file_name
            if (
                mensaje.reply_to_message
                and mensaje.reply_to_message.document
            )
            else None
        ),
    )

    # ========================================================
    # REGISTRAR COMANDO /OPEN DE ONLYOFFICE
    #
    # Si el comando responde a un PDF, se asocia directamente
    # con ese PDF. Así funciona correctamente aunque se hayan
    # cargado varios archivos al mismo tiempo.
    # ========================================================

    if texto:

        primera_parte = (
            texto.strip()
            .split()[0]
            .lower()
        )

        if (
            primera_parte == "/open"
            or primera_parte.startswith(
                "/open@"
            )
        ):

            _, registro_open = (
                identificar_registro_del_mensaje(
                    mensaje
                )
            )

            if registro_open is not None:

                agregar_mensaje_a_limpieza(
                    registro_open,
                    mensaje.message_id,
                )

                logger.info(
                    "COMANDO OPEN REGISTRADO PARA LIMPIEZA | "
                    "ID_OT=%s | message_id=%s | "
                    "reply_to=%s",
                    registro_open["id_ot"],
                    mensaje.message_id,
                    (
                        mensaje.reply_to_message.message_id
                        if mensaje.reply_to_message
                        else None
                    ),
                )

            else:

                logger.warning(
                    "COMANDO OPEN SIN PDF RELACIONADO | "
                    "message_id=%s | tema=%s",
                    mensaje.message_id,
                    mensaje.message_thread_id,
                )

    # ========================================================
    # ONLYOFFICE
    # ========================================================

    if (
        remitente
        and remitente.is_bot
        and (
            remitente.username
            or ""
        ).lower() == ONLYOFFICE_USERNAME
    ):

        await procesar_onlyoffice(
            mensaje,
            context,
        )

        return

    # ========================================================
    # REGISTRAR PDF ORIGINAL
    # ========================================================

    if documento:

        nombre = (
            documento.file_name
            or ""
        )

        if nombre.lower().endswith(
            ".pdf"
        ):

            registrar_pdf_original(
                mensaje
            )

    # ========================================================
    # MODERACIÓN
    # ========================================================

    if not texto:
        return

    # No moderar comandos
    if texto.startswith("/"):
        return

    if not contiene_palabra_prohibida(
        texto
    ):
        return

    logger.info(
        "PALABRA PROHIBIDA DETECTADA | "
        "mensaje=%s",
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

        aviso = (
            await context.bot.send_message(
                chat_id=mensaje.chat_id,
                message_thread_id=(
                    mensaje.message_thread_id
                ),
                text=(
                    "⚠️ Mensaje eliminado por contener "
                    "lenguaje no permitido."
                ),
            )
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

def obtener_semanas_configuradas(
    clave_area,
):

    area = AREAS.get(
        clave_area
    )

    if not area:
        return {}

    resultado = {}

    for numero, enlace in (
        area["semanas"].items()
    ):

        enlace = enlace.strip()

        if enlace.startswith(
            "PEGA_AQUI_LINK_"
        ):
            continue

        if enlace.startswith(
            (
                "http://",
                "https://",
            )
        ):
            resultado[numero] = (
                enlace
            )

    return resultado


# ============================================================
# MENÚ DE ÁREAS
# ============================================================

def crear_menu_areas():

    botones = []

    for clave, area in (
        AREAS.items()
    ):

        botones.append(
            [
                InlineKeyboardButton(
                    text=(
                        f"{area['icono']} "
                        f"{area['nombre']}"
                    ),
                    callback_data=(
                        f"area:{clave}"
                    ),
                )
            ]
        )

    return InlineKeyboardMarkup(
        botones
    )


# ============================================================
# MENÚ DE SEMANAS
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

    for numero in semanas[
        inicio:fin
    ]:

        botones.append(
            [
                InlineKeyboardButton(
                    text=(
                        f"📁 SEMANA "
                        f"{numero:02d}"
                    ),
                    url=(
                        semanas_configuradas[
                            numero
                        ]
                    ),
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
            (
                f"{pagina + 1} "
                f"de {total_paginas}"
            ),
            callback_data="pagina_actual",
        )
    )

    if pagina < (
        total_paginas - 1
    ):

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

    mensaje = (
        update.effective_message
    )

    if mensaje is None:
        return

    programar_borrado(
        context,
        mensaje.chat_id,
        mensaje.message_id,
    )

    respuesta = (
        await mensaje.reply_text(
            "🤖 *Bot de Planeación activo*\n\n"
            "Utiliza /areas para consultar las "
            "carpetas de Órdenes de Trabajo Semanales.",
            parse_mode="Markdown",
        )
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

    mensaje = (
        update.effective_message
    )

    if mensaje is None:
        return

    programar_borrado(
        context,
        mensaje.chat_id,
        mensaje.message_id,
    )

    respuesta = (
        await mensaje.reply_text(
            "📁 *Carpetas de Órdenes de Trabajo Semanales*\n\n"
            "Selecciona el área:",
            reply_markup=crear_menu_areas(),
            parse_mode="Markdown",
        )
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

    consulta = (
        update.callback_query
    )

    if not consulta:
        return

    await consulta.answer()

    try:

        clave = (
            consulta.data
            .split(":")[1]
        )

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

    consulta = (
        update.callback_query
    )

    if not consulta:
        return

    datos = (
        consulta.data
        or ""
    )

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
# VOLVER A ÁREAS
# ============================================================

async def volver_areas(
    update,
    context,
):

    consulta = (
        update.callback_query
    )

    if not consulta:
        return

    await consulta.answer()

    await consulta.edit_message_text(
        (
            "📁 *Carpetas de Órdenes de Trabajo Semanales*\n\n"
            "Selecciona el área:"
        ),
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
# INICIO
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

    # ========================================================
    # ERRORES
    # ========================================================

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

    print(
        "Bot activo."
    )

    print(
        "Modo de estado: memoria temporal (Render Free)"
    )

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
