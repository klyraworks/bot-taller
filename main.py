import os
import logging
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from database import init_db, get_conn
from utils import get_usuario
from handlers.mecanico import registrar_servicio, registrar_pago_pendiente, mis_stats
from handlers.jefe import resumen_dia, resumen_semana, deudas, registrar_adelanto
from handlers.admin import registrar_usuario, listar_usuarios, registrar_gasto
from handlers.consultas import consulta_dia, consulta_moto, editar_servicio, eliminar_servicio
from handlers.reportes import cmd_hoy, cmd_resumen, cmd_resumen_semana, cmd_exportar

load_dotenv()
logging.basicConfig(level=logging.INFO)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    telegram_id = update.effective_user.id
    username = update.effective_user.username or ""
    usuario = get_usuario(telegram_id)

    # Auto-vincular si existe por username pero sin telegram_id
    if not usuario and username:
        conn = get_conn()
        cur = conn.cursor()
        cur.execute("SELECT id FROM usuarios WHERE username = %s AND telegram_id = 0", (username,))
        row = cur.fetchone()
        if row:
            cur.execute("UPDATE usuarios SET telegram_id = %s WHERE id = %s", (telegram_id, row[0]))
            conn.commit()
            usuario = get_usuario(telegram_id)
        cur.close()
        conn.close()

    if not usuario:
        await update.message.reply_text("❌ No estás registrado. Contacta al administrador.")
        return

    rol_emoji = {"admin": "👑", "jefe": "⭐", "mecanico": "🔧"}.get(usuario["rol"], "👤")
    await update.message.reply_text(
        f"Hola *{usuario['nombre']}* {rol_emoji}\n\nUsa /ayuda para ver los comandos disponibles.",
        parse_mode="Markdown"
    )

async def ayuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    usuario = get_usuario(update.effective_user.id)
    if not usuario:
        await update.message.reply_text("❌ No estás registrado.")
        return

    msg = "🔧 *Bot del Taller*\n\n"

    if usuario["rol"] in ("admin", "jefe", "mecanico"):
        msg += ("*Servicios:*\n"
                "`21r 15` — registrar servicio\n"
                "`21r 15 8p` — con pendiente\n"
                "`21r 15 8p Descripcion @Diego` — completo\n"
                "*Colores:* v=verde, r=roja, a=amarilla, az=azul\n\n"
                "`/pagar 21r` — saldar deuda\n"
                "`/pagar 21r 5` — pago parcial\n"
                "`/mistats` — tus estadísticas del mes\n\n"
                "*Consultas:*\n"
                "`/hoy` — servicios y resumen de hoy\n"
                "`/resumen 20/06/2025` — resumen de un día\n"
                "`/resumen_semana 20/06/2025` — semana de esa fecha\n"
                "`/dia 20/06/2025` — listado detallado de un día\n"
                "`/dia 20/06/2025 25/06/2025` — rango\n"
                "`/dia 06/2025` — mes completo\n"
                "`/moto 21r` — historial de una moto\n\n")

    if usuario["rol"] in ("admin", "jefe"):
        msg += ("*Reportes:*\n"
                "`/resumen` — totales del día\n"
                "`/semana` — resumen semanal\n"
                "`/deudas` — deudas activas\n"
                "`/adelanto 5 [Nombre]` — registrar adelanto\n\n"
                "*Edición:*\n"
                "`/editar 42 monto 20` — editar campo\n"
                "`/editar 42 pendiente 0`\n"
                "`/editar 42 descripcion Texto`\n"
                "`/editar 42 mecanico Diego`\n"
                "`/editar 42 moto 21r`\n"
                "`/eliminar 42` — eliminar servicio\n\n"
                "*Exportar:*\n"
                "`/exportar dia 20/06/2025`\n"
                "`/exportar semana 20/06/2025`\n"
                "`/exportar mes 06/2025`\n\n")

    if usuario["rol"] == "admin":
        msg += ("*Admin:*\n"
                "`/adduser @username Nombre rol` — agregar usuario\n"
                "`/usuarios` — listar usuarios\n"
                "`/gasto 5 Descripcion` — registrar gasto\n")

    await update.message.reply_text(msg, parse_mode="Markdown")

def main():
    init_db()

    token = os.getenv("BOT_TOKEN")
    app = ApplicationBuilder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ayuda", ayuda))

    # Mecánico
    app.add_handler(CommandHandler("pagar", registrar_pago_pendiente))
    app.add_handler(CommandHandler("mistats", mis_stats))

    # Jefe
    app.add_handler(CommandHandler("resumen", resumen_dia))
    app.add_handler(CommandHandler("semana", resumen_semana))
    app.add_handler(CommandHandler("deudas", deudas))
    app.add_handler(CommandHandler("adelanto", registrar_adelanto))

    # Admin
    app.add_handler(CommandHandler("adduser", registrar_usuario))
    app.add_handler(CommandHandler("usuarios", listar_usuarios))
    app.add_handler(CommandHandler("gasto", registrar_gasto))

    # Consultas (todos los roles)
    app.add_handler(CommandHandler("dia", consulta_dia))
    app.add_handler(CommandHandler("moto", consulta_moto))

    # Edición (admin/jefe)
    app.add_handler(CommandHandler("editar", editar_servicio))
    app.add_handler(CommandHandler("eliminar", eliminar_servicio))

    # Nuevos comandos de consulta (todos los roles)
    app.add_handler(CommandHandler("hoy", cmd_hoy))
    app.add_handler(CommandHandler("resumen", cmd_resumen))
    app.add_handler(CommandHandler("resumen_semana", cmd_resumen_semana))

    # Exportar Excel (admin/jefe)
    app.add_handler(CommandHandler("exportar", cmd_exportar))

    # Mensajes de texto (servicios)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, registrar_servicio))

    app.run_polling()

if __name__ == "__main__":
    main()
