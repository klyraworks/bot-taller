from telegram import Update
from telegram.ext import ContextTypes
from database import get_conn
from utils import require_rol

@require_rol("admin", "jefe")
async def resumen_dia(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT COALESCE(SUM(monto_total), 0), COALESCE(SUM(monto_pendiente), 0)
        FROM servicios
        WHERE DATE(created_at) = CURRENT_DATE AND is_active = TRUE AND estado != 'anulado'
    """)
    total, pendiente = cur.fetchone()
    cobrado = float(total) - float(pendiente)

    cur.execute("""
        SELECT u.nombre, COALESCE(SUM(s.monto_total - s.monto_pendiente), 0)
        FROM servicios s JOIN usuarios u ON s.mecanico_id = u.id
        WHERE DATE(s.created_at) = CURRENT_DATE AND s.is_active = TRUE AND s.estado != 'anulado'
        GROUP BY u.nombre ORDER BY 2 DESC
    """)
    por_mecanico = cur.fetchall()

    cur.execute("""
        SELECT tipo, COALESCE(SUM(monto), 0) FROM gastos
        WHERE DATE(created_at) = CURRENT_DATE AND is_active = TRUE
        GROUP BY tipo
    """)
    gastos_rows = dict(cur.fetchall())
    total_gastos = float(gastos_rows.get("gasto", 0))
    total_adelantos = float(gastos_rows.get("adelanto", 0))

    cur.close()
    conn.close()

    msg = (f"📊 *Resumen de hoy*\n\n"
           f"💰 Servicios: ${float(total):.2f}\n"
           f"✅ Cobrado: ${cobrado:.2f}\n"
           f"⏳ Pendiente: ${float(pendiente):.2f}\n"
           f"🛒 Gastos: ${total_gastos:.2f}\n"
           f"💵 Adelantos: ${total_adelantos:.2f}\n"
           f"📦 Neto: ${cobrado - total_gastos - total_adelantos:.2f}\n")

    if por_mecanico:
        msg += "\n🔧 *Por mecánico:*\n"
        for nombre, monto in por_mecanico:
            msg += f"  • {nombre}: ${float(monto):.2f}\n"

    await update.message.reply_text(msg, parse_mode="Markdown")


@require_rol("admin", "jefe")
async def resumen_semana(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        SELECT COALESCE(SUM(monto_total - monto_pendiente), 0), COALESCE(SUM(monto_pendiente), 0)
        FROM servicios
        WHERE created_at >= DATE_TRUNC('week', NOW()) AND is_active = TRUE AND estado != 'anulado'
    """)
    cobrado, pendiente = cur.fetchone()

    cur.execute("""
        SELECT u.nombre,
               COALESCE(SUM(s.monto_total - s.monto_pendiente), 0) AS cobrado,
               COALESCE((
                   SELECT SUM(g.monto) FROM gastos g
                   WHERE g.registrado_por = u.id AND g.tipo = 'adelanto'
                   AND g.created_at >= DATE_TRUNC('week', NOW()) AND g.is_active = TRUE
               ), 0) AS adelanto
        FROM servicios s JOIN usuarios u ON s.mecanico_id = u.id
        WHERE s.created_at >= DATE_TRUNC('week', NOW()) AND s.is_active = TRUE AND s.estado != 'anulado'
        GROUP BY u.id, u.nombre ORDER BY cobrado DESC
    """)
    por_mecanico = cur.fetchall()

    cur.execute("""
        SELECT COALESCE(SUM(monto), 0) FROM gastos
        WHERE tipo = 'gasto' AND created_at >= DATE_TRUNC('week', NOW()) AND is_active = TRUE
    """)
    gastos = cur.fetchone()[0]

    cur.close()
    conn.close()

    msg = (f"📅 *Resumen de la semana*\n\n"
           f"💰 Total cobrado: ${float(cobrado):.2f}\n"
           f"⏳ Pendiente: ${float(pendiente):.2f}\n"
           f"🛒 Gastos taller: ${float(gastos):.2f}\n")

    if por_mecanico:
        msg += "\n🔧 *Por mecánico:*\n"
        for nombre, monto, adelanto in por_mecanico:
            msg += f"  • {nombre}: ${float(monto):.2f} (adelanto: ${float(adelanto):.2f})\n"

    await update.message.reply_text(msg, parse_mode="Markdown")


@require_rol("admin", "jefe")
async def deudas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        SELECT tricimoto_num, tricimoto_color, monto_total, monto_pendiente
        FROM servicios
        WHERE is_active = TRUE AND estado = 'activo' AND monto_pendiente > 0
        ORDER BY created_at ASC
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()

    if not rows:
        await update.message.reply_text("✅ No hay deudas pendientes")
        return

    msg = "📋 *Deudas pendientes:*\n\n"
    for num, color, total, pendiente in rows:
        msg += f"🛺 *{num} {color}* — Debe: ${float(pendiente):.2f} de ${float(total):.2f}\n"
    await update.message.reply_text(msg, parse_mode="Markdown")


@require_rol("admin", "jefe")
async def registrar_adelanto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    usuario = context.user_data["usuario"]
    partes = update.message.text.strip().split()

    if len(partes) < 2:
        await update.message.reply_text("Uso: /adelanto 5 [Mecánico]")
        return

    try:
        monto = float(partes[1])
    except ValueError:
        await update.message.reply_text("❌ Monto inválido")
        return

    destino = " ".join(partes[2:]) if len(partes) > 2 else usuario["nombre"]

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT INTO gastos (tipo, monto, descripcion, registrado_por) VALUES ('adelanto', %s, %s, %s)",
                (monto, destino, usuario["id"]))
    conn.commit()
    cur.close()
    conn.close()

    await update.message.reply_text(f"✅ Adelanto de ${monto:.2f} registrado para {destino}")
