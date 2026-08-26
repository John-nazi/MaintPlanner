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

# Borrado de comandos y respuestas temporales
TIEMPO_BORRADO = 60

# Aviso de moderación
TIEMPO_BORRADO_AVISO = 5


# ============================================================
# AUTOLIMPIEZA / BARRIDO PROFUNDO
# ============================================================
# Compatible con Render Free:
# - No usa Disk.
# - No usa archivos persistentes.
# - Mantiene el barrido en memoria.
#
# El barrido NO elimina los PDF finales.
# Tampoco elimina mensajes de una edición activa.
# ============================================================

TIEMPO_BORRADO = 60
BARRIDO_CANTIDAD = 100

# Tiempos visuales. IMPORTANTE: es una lista, no una tupla.
INTERVALOS_TIMER = [
    45,
    30,
    20,
    10,
    5,
    3,
    2,
    1,
]

LIMPIEZAS_ACTIVAS = {}
ULTIMO_MENSAJE_POR_CHAT = {}

# PDF finales que deben permanecer en el chat.
# {chat_id: {message_id, message_id, ...}}
MENSAJES_PROTEGIDOS = {}



# ============================================================
# PDFs PENDIENTES DE EDICIÓN
#
# Aquí NO se guarda el PDF.
# Solo:
# - chat
# - tema
# - ID de OT
# - nombre
# - message_id
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
# FUNCIONES DE AUTOLIMPIEZA
# ============================================================

def obtener_mensajes_protegidos(chat_id):

    return MENSAJES_PROTEGIDOS.setdefault(
        chat_id,
        set(),
    )


def proteger_mensaje(
    chat_id,
    message_id,
):

    if message_id is None:
        return

    obtener_mensajes_protegidos(
        chat_id
    ).add(
        message_id
    )


def desproteger_mensaje(
    chat_id,
    message_id,
):

    if chat_id not in MENSAJES_PROTEGIDOS:
        return

    MENSAJES_PROTEGIDOS[chat_id].discard(
        message_id
    )

    if not MENSAJES_PROTEGIDOS[chat_id]:
        MENSAJES_PROTEGIDOS.pop(
            chat_id,
            None,
        )


def obtener_mensajes_edicion_activa(
    chat_id,
):

    protegidos = set()

    for registro in PDF_PENDIENTES:

        if registro.get("chat_id") != chat_id:
            continue

        for message_id in registro.get(
            "message_ids_limpieza",
            [],
        ):
            protegidos.add(
                message_id
            )

        original_id = registro.get(
            "message_id"
        )

        if original_id is not None:
            protegidos.add(
                original_id
            )

    return protegidos


async def borrar_mensaje_despues(
    context,
    chat_id,
    message_id,
    segundos,
):

    await asyncio.sleep(
        segundos
    )

    # Si el mensaje fue protegido mientras esperaba,
    # no se elimina.
    if message_id in obtener_mensajes_protegidos(
        chat_id
    ):
        logger.info(
            "BORRADO OMITIDO | mensaje protegido | "
            "chat=%s | message_id=%s",
            chat_id,
            message_id,
        )
        return

    try:

        await context.bot.delete_message(
            chat_id=chat_id,
            message_id=message_id,
        )

        logger.info(
            "MENSAJE BORRADO | chat=%s | message_id=%s",
            chat_id,
            message_id,
        )

    except Exception as error:

        logger.warning(
            "NO SE PUDO BORRAR MENSAJE | "
            "chat=%s | message_id=%s | error=%s",
            chat_id,
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


async def borrar_un_mensaje_barrido(
    context,
    chat_id,
    message_id,
):

    if message_id in obtener_mensajes_protegidos(
        chat_id
    ):
        return False

    try:

        await context.bot.delete_message(
            chat_id=chat_id,
            message_id=message_id,
        )

        return True

    except Exception:
        return False


async def barrido_profundo(
    context,
    chat_id,
    message_id_tope,
):

    if message_id_tope is None:
        return

    protegidos = (
        obtener_mensajes_protegidos(
            chat_id
        )
        | obtener_mensajes_edicion_activa(
            chat_id
        )
    )

    inicio = max(
        1,
        message_id_tope
        - BARRIDO_CANTIDAD
        + 1,
    )

    ids = [
        message_id
        for message_id in range(
            message_id_tope,
            inicio - 1,
            -1,
        )
        if message_id not in protegidos
    ]

    if not ids:
        logger.info(
            "BARRIDO PROFUNDO | nada que eliminar | "
            "chat=%s",
            chat_id,
        )
        return

    eliminados = 0

    # Telegram puede devolver errores para mensajes inexistentes.
    # No dejamos que uno detenga todo el barrido.
    # Se procesan pequeños lotes para no saturar la API.
    lote = 10

    for posicion in range(
        0,
        len(ids),
        lote,
    ):

        grupo = ids[
            posicion:posicion + lote
        ]

        resultados = await asyncio.gather(
            *[
                borrar_un_mensaje_barrido(
                    context,
                    chat_id,
                    message_id,
                )
                for message_id in grupo
            ],
            return_exceptions=True,
        )

        eliminados += sum(
            1
            for resultado in resultados
            if resultado is True
        )

        # Pequeña pausa entre lotes para reducir
        # el riesgo de límites de Telegram.
        await asyncio.sleep(
            0.15
        )

    logger.info(
        "BARRIDO PROFUNDO FINALIZADO | "
        "chat=%s | revisados=%s | eliminados=%s | protegidos=%s",
        chat_id,
        len(ids),
        eliminados,
        len(protegidos),
    )


async def reiniciar_temporizador(
    context,
    chat_id,
    current_msg_id,
):

    # Actualizar el último mensaje conocido del chat.
    if current_msg_id is not None:

        ULTIMO_MENSAJE_POR_CHAT[
            chat_id
        ] = max(
            ULTIMO_MENSAJE_POR_CHAT.get(
                chat_id,
                0,
            ),
            current_msg_id,
        )

    anterior = LIMPIEZAS_ACTIVAS.get(
        chat_id
    )

    if anterior is not None:

        tarea_anterior = anterior.get(
            "task"
        )

        if tarea_anterior is not None:
            tarea_anterior.cancel()

        timer_anterior = anterior.get(
            "timer_msg_id"
        )

        if timer_anterior is not None:

            try:

                await context.bot.delete_message(
                    chat_id=chat_id,
                    message_id=timer_anterior,
                )

            except Exception:
                pass

        LIMPIEZAS_ACTIVAS.pop(
            chat_id,
            None,
        )

    token_limpieza = object()

    LIMPIEZAS_ACTIVAS[
        chat_id
    ] = {
        "task": None,
        "timer_msg_id": None,
        "token": token_limpieza,
    }

    tarea = context.application.create_task(
        rutina_limpieza_chat(
            context,
            chat_id,
            current_msg_id,
            TIEMPO_BORRADO,
            token_limpieza,
        )
    )

    LIMPIEZAS_ACTIVAS[
        chat_id
    ]["task"] = tarea


async def rutina_limpieza_chat(
    context,
    chat_id,
    max_msg_id,
    tiempo_total,
    token_limpieza,
):

    timer_id = None

    try:

        # ----------------------------------------------------
        # MENSAJE INICIAL
        # ----------------------------------------------------

        msg_timer = await context.bot.send_message(
            chat_id=chat_id,
            text=(
                "⏳ *Iniciando protocolo de limpieza...*"
            ),
            parse_mode="Markdown",
        )

        timer_id = msg_timer.message_id

        info = LIMPIEZAS_ACTIVAS.get(
            chat_id
        )

        # Si otra limpieza ya tomó el control del chat,
        # esta tarea termina y elimina su propio timer.
        if (
            info is None
            or info.get("token")
            is not token_limpieza
        ):

            try:
                await context.bot.delete_message(
                    chat_id=chat_id,
                    message_id=timer_id,
                )
            except Exception:
                pass

            return

        info[
            "timer_msg_id"
        ] = timer_id

        ULTIMO_MENSAJE_POR_CHAT[
            chat_id
        ] = max(
            ULTIMO_MENSAJE_POR_CHAT.get(
                chat_id,
                0,
            ),
            timer_id,
        )

        # ----------------------------------------------------
        # CUENTA REGRESIVA
        # ----------------------------------------------------

        tiempos = [
            t
            for t in INTERVALOS_TIMER
            if t < tiempo_total
        ]

        tiempo_anterior = (
            tiempo_total
        )

        for tiempo in tiempos:

            espera = (
                tiempo_anterior
                - tiempo
            )

            if espera > 0:
                await asyncio.sleep(
                    espera
                )

            # Verificar si la limpieza sigue siendo
            # la activa para este chat.
            info_actual = (
                LIMPIEZAS_ACTIVAS.get(
                    chat_id
                )
            )

            if (
                info_actual is None
                or info_actual.get("token")
                is not token_limpieza
            ):
                return

            progreso = int(
                (
                    (
                        tiempo_total
                        - tiempo
                    )
                    / tiempo_total
                )
                * 15
            )

            barra = (
                "🟥" * progreso
                + "🟩" * (
                    15 - progreso
                )
            )

            texto_timer = (
                "⚠️ *AUTODESTRUCCIÓN DEL CHAT* ⚠️\n\n"
                f"{barra}\n\n"
                "🧹 Limpiando todo en: "
                f"*{tiempo} segundos*"
            )

            try:

                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=timer_id,
                    text=texto_timer,
                    parse_mode="Markdown",
                )

            except Exception as error:

                logger.warning(
                    "NO SE PUDO ACTUALIZAR TIMER | "
                    "chat=%s | error=%s",
                    chat_id,
                    error,
                )

            tiempo_anterior = (
                tiempo
            )

        if tiempo_anterior > 0:
            await asyncio.sleep(
                tiempo_anterior
            )

        info_actual = (
            LIMPIEZAS_ACTIVAS.get(
                chat_id
            )
        )

        if (
            info_actual is None
            or info_actual.get("token")
            is not token_limpieza
        ):
            return

        # ----------------------------------------------------
        # BARRIDO PROFUNDO
        # ----------------------------------------------------
        # IMPORTANTE:
        # Se toma el último message_id recibido, no solamente
        # el ID del timer. Así también se limpian mensajes
        # enviados mientras Render estaba tardando.
        # ----------------------------------------------------

        ultimo = max(
            ULTIMO_MENSAJE_POR_CHAT.get(
                chat_id,
                0,
            ),
            timer_id,
        )

        logger.info(
            "INICIANDO BARRIDO PROFUNDO | "
            "chat=%s | ultimo_message_id=%s | "
            "cantidad=%s",
            chat_id,
            ultimo,
            BARRIDO_CANTIDAD,
        )

        await barrido_profundo(
            context,
            chat_id,
            ultimo,
        )

        # El timer se elimina expresamente si no quedó
        # dentro del barrido.
        try:

            await context.bot.delete_message(
                chat_id=chat_id,
                message_id=timer_id,
            )

        except Exception:
            pass

    except asyncio.CancelledError:

        # La cancelación es normal cuando llega un mensaje nuevo.
        # El timer anterior se elimina sin afectar al nuevo.
        raise

    except Exception as error:

        logger.exception(
            "ERROR EN RUTINA DE AUTOLIMPIEZA | "
            "chat=%s | error=%s",
            chat_id,
            error,
        )

    finally:

        info_final = LIMPIEZAS_ACTIVAS.get(
            chat_id
        )

        if (
            info_final is not None
            and info_final.get("token")
            is token_limpieza
        ):

            LIMPIEZAS_ACTIVAS.pop(
                chat_id,
                None,
            )


# ============================================================
# EDICIONES ACTIVAS EN MEMORIA
# ============================================================

PDF_PENDIENTES = []


def ahora_utc_iso():

    from datetime import datetime, timezone

    return datetime.now(
        timezone.utc
    ).isoformat()


def cargar_estado():
    # Render Free: sin almacenamiento persistente.
    return


def guardar_estado():
    # Render Free: estado solamente en memoria.
    return


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


def agregar_mensaje_a_limpieza(
    registro,
    message_id,
):

    if (
        registro is None
        or message_id is None
    ):
        return

    mensajes = registro.setdefault(
        "message_ids_limpieza",
        [],
    )

    if message_id not in mensajes:
        mensajes.append(
            message_id
        )

    registro[
        "actualizado_en"
    ] = ahora_utc_iso()


def reconstruir_registro_desde_pdf_respondido(
    mensaje,
):

    respondido = (
        mensaje.reply_to_message
    )

    if respondido is None:
        return None, None

    documento = (
        respondido.document
    )

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
        "REGISTRO RECONSTRUIDO DESDE PDF RESPONDIDO | "
        "ID_OT=%s | original_message_id=%s | "
        "archivo=%s",
        id_ot,
        respondido.message_id,
        nombre,
    )

    return indice, registro


# ============================================================
# BUSCAR ORIGINAL POR ID DE OT
# ============================================================

def buscar_pdf_original(
    chat_id,
    tema,
    id_ot,
):

    # Buscar desde el más reciente
    # hacia el más antiguo.
    for indice in range(
        len(PDF_PENDIENTES) - 1,
        -1,
        -1,
    ):

        registro = (
            PDF_PENDIENTES[indice]
        )

        if (
            registro["chat_id"]
            != chat_id
        ):
            continue

        if (
            registro["tema"]
            != tema
        ):
            continue

        if (
            registro["id_ot"]
            != id_ot
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
# BUSCAR REGISTRO POR MESSAGE_ID
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

        registro = PDF_PENDIENTES[
            indice
        ]

        if registro.get(
            "chat_id"
        ) != chat_id:
            continue

        if registro.get(
            "tema"
        ) != tema:
            continue

        if (
            registro.get(
                "message_id"
            ) == message_id
            or message_id in registro.get(
                "message_ids_limpieza",
                [],
            )
        ):
            return indice, registro

    return None, None


def buscar_pdf_pendiente_reciente(
    chat_id,
    tema,
):

    for indice in range(
        len(PDF_PENDIENTES) - 1,
        -1,
        -1,
    ):

        registro = PDF_PENDIENTES[
            indice
        ]

        if registro.get(
            "chat_id"
        ) != chat_id:
            continue

        if registro.get(
            "tema"
        ) != tema:
            continue

        return indice, registro

    return None, None


def identificar_registro_del_mensaje(
    mensaje,
):

    documento = mensaje.document

    texto = (
        mensaje.text
        or mensaje.caption
        or ""
    )

    # 1. Buscar por ID de OT.
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

    # 2. Buscar por reply_to_message.
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

        # 3. Si Render reinició, reconstruir
        # directamente desde el PDF respondido.
        if respondido.document is not None:

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
# LIMPIAR MENSAJES DE UNA EDICIÓN
#
# Conserva únicamente el PDF final.
# ============================================================

async def limpiar_mensajes_edicion(
    context,
    registro,
    message_id_final,
):

    mensajes = set(
        registro.get(
            "message_ids_limpieza",
            [],
        )
    )

    original_id = registro.get(
        "message_id"
    )

    if original_id is not None:
        mensajes.add(
            original_id
        )

    eliminados = 0
    fallidos = 0

    # Primero proteger el PDF final para que el barrido
    # general jamás lo elimine.
    proteger_mensaje(
        registro["chat_id"],
        message_id_final,
    )

    for message_id in sorted(
        mensajes,
        reverse=True,
    ):

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

    ULTIMO_MENSAJE_POR_CHAT[
        mensaje.chat_id
    ] = max(
        ULTIMO_MENSAJE_POR_CHAT.get(
            mensaje.chat_id,
            0,
        ),
        mensaje.message_id,
    )

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

    logger.info(
        "MENSAJE RECIBIDO | "
        "chat=%s | tipo=%s | tema=%s | "
        "message_id=%s | texto=%r",
        mensaje.chat_id,
        (
            mensaje.chat.type
            if mensaje.chat
            else None
        ),
        mensaje.message_thread_id,
        mensaje.message_id,
        texto,
    )

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
    # REINICIAR AUTOLIMPIEZA
    # ========================================================
    # Se hace después de registrar PDF/OPEN para que el
    # barrido conozca los mensajes que debe proteger.

    await reiniciar_temporizador(
        context,
        mensaje.chat_id,
        mensaje.message_id,
    )

    # ========================================================
    # MODERACIÓN
    # ========================================================

    if not texto:
        return

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

        ULTIMO_MENSAJE_POR_CHAT[
            mensaje.chat_id
        ] = max(
            ULTIMO_MENSAJE_POR_CHAT.get(
                mensaje.chat_id,
                0,
            ),
            aviso.message_id,
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

    await reiniciar_temporizador(
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

    await reiniciar_temporizador(
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

    await reiniciar_temporizador(
        context,
        consulta.message.chat_id,
        consulta.message.message_id,
    )

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

    await reiniciar_temporizador(
        context,
        consulta.message.chat_id,
        consulta.message.message_id,
    )

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
        "Bot activo. Autolimpieza y barrido profundo habilitados (Render Free)."
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
