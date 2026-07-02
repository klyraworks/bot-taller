from telegram import Update
from telegram.ext import ContextTypes
from database import get_conn
from utils import parsear_tricimoto, COMPANIAS, COLORES, require_rol


@require_rol("admin", "jefe", "mecanico")
async def registrar_servicio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    usuario = context.user_data["usuario"]
    partes = update.message.text.strip().split()

    if len(partes) < 2:
        await update.message.reply_text("❌ Formato: `21r 15 [8p] [descripcion] [@Mecanico]`", parse_mode="Markdown")
        return

    num, color = parsear_tricimoto(partes[0])
    if not num:
        await update.message.reply_text("❌ Tricimoto inválida. Ej: 21r, 05v, 31az")
        return

    try:
        monto = float(partes[1])
    except ValueError:
        await update.message.reply_text("❌ Monto inválido")
        return

    pendiente = 0.0
    idx = 2
    if len(partes) > idx and partes[idx].lower().endswith("p"):
        try:
            pendiente = float(partes[idx][:-1])
            idx += 1
        except ValueError:
            pass

    resto = partes[idx:]
    mecanico_nombre = None
    desc_partes = []
    for i in range(len(resto) - 1, -1, -1):
        if resto[i].startswith("@"):
            mecanico_nombre = resto[i][1:]
            desc_partes = [r for j, r in enumerate(resto) if j != i]
            break
    else:
        desc_partes = resto

    descripcion = " ".join(desc_partes)

    conn = get_conn()
    cur = conn.cursor()

    mecanico_id = usuario["id"]
    if mecanico_nombre:
        cur.execute("SELECT id FROM usuarios WHERE LOWER(nombre) = LOWER(%s) AND is_active = TRUE", (mecanico_nombre,))
        row = cur.fetchone()
        if row:
            mecanico_id = row[0]

    estado = "pagado" if pendiente > 0 else "pagado"
    cur.execute("""
                INSERT INTO servicios (tricimoto_num, tricimoto_compania, monto_total, monto_pendiente, descripcion,
                                       mecanico_id, registrado_por, estado)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
                """,
                (num, COMPANIAS.get(color, color), monto, pendiente, descripcion, mecanico_id, usuario["id"], estado))
    servicio_id = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()

    msg = f"✅ Servicio registrado [#{servicio_id}]\n🛺 Tricimoto: *{num} {COLORES.get(color, color)} ({COMPANIAS.get(color, color)})*\n💰 Total: *${monto:.2f}*"
    if pendiente > 0:
        msg += f" | Pendiente: *${pendiente:.2f}*"
    if descripcion:
        msg += f"\n📝 {descripcion}"
    if mecanico_nombre:
        msg += f"\n🔧 Asignado a: *{mecanico_nombre}*"

    await update.message.reply_text(msg, parse_mode="Markdown")


@require_rol("admin", "jefe", "mecanico")
async def registrar_pago_pendiente(update: Update, context: ContextTypes.DEFAULT_TYPE):
    usuario = context.user_data["usuario"]
    partes = update.message.text.strip().split()

    if len(partes) < 2:
        await update.message.reply_text("Uso: /pagar 21r [monto]")
        return

    num, color = parsear_tricimoto(partes[1])
    if not num:
        await update.message.reply_text("❌ Tricimoto inválida")
        return

    monto_parcial = float(partes[2]) if len(partes) > 2 else None
    color_nombre = COMPANIAS.get(color, color)

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
                SELECT id, monto_pendiente
                FROM servicios
                WHERE tricimoto_num = %s
                  AND tricimoto_compania = %s
                  AND is_active = TRUE
                  AND estado != 'anulado' AND monto_pendiente > 0
                ORDER BY created_at ASC LIMIT 1
                """, (num, color_nombre))
    row = cur.fetchone()

    if not row:
        await update.message.reply_text(f"❌ No hay deuda activa para *{num} {color_nombre}*", parse_mode="Markdown")
        cur.close();
        conn.close()
        return

    servicio_id, pendiente_actual = row
    pagado = monto_parcial or float(pendiente_actual)
    nuevo_pendiente = max(0, float(pendiente_actual) - pagado)

    cur.execute("UPDATE servicios SET monto_pendiente = %s, estado = %s WHERE id = %s",
                (nuevo_pendiente, "pagado" if nuevo_pendiente == 0 else "pagado", servicio_id))
    cur.execute("INSERT INTO pagos (servicio_id, monto, registrado_por) VALUES (%s, %s, %s)",
                (servicio_id, pagado, usuario["id"]))
    conn.commit()
    cur.close()
    conn.close()

    if nuevo_pendiente == 0:
        await update.message.reply_text(f"✅ Deuda de *{num} {color_nombre}* saldada completamente",
                                        parse_mode="Markdown")
    else:
        await update.message.reply_text(f"✅ Pago de ${pagado:.2f} registrado. Pendiente: *${nuevo_pendiente:.2f}*",
                                        parse_mode="Markdown")


@require_rol("admin", "jefe", "mecanico")
async def mis_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    usuario = context.user_data["usuario"]
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
                SELECT COUNT(*), COALESCE(SUM(monto_total), 0), COALESCE(SUM(monto_pendiente), 0)
                FROM servicios
                WHERE mecanico_id = %s
                  AND DATE_TRUNC('month', created_at) = DATE_TRUNC('month', NOW())
                """, (usuario["id"],))
    count, total, pendiente = cur.fetchone()
    cobrado = float(total) - float(pendiente)

    cur.execute("""
                SELECT COALESCE(SUM(monto), 0)
                FROM gastos
                WHERE registrado_por = %s
                  AND tipo = 'adelanto'
                  AND DATE_TRUNC('month', created_at) = DATE_TRUNC('month', NOW())
                """, (usuario["id"],))
    adelantos = cur.fetchone()[0]

    cur.close()
    conn.close()

    msg = (f"📊 *Tus stats del mes*\n\n"
           f"🔧 Servicios: {count}\n"
           f"💰 Total generado: ${float(total):.2f}\n"
           f"✅ Cobrado: ${cobrado:.2f}\n"
           f"⏳ Pendiente: ${float(pendiente):.2f}\n"
           f"💵 Adelantos recibidos: ${float(adelantos):.2f}")
    await update.message.reply_text(msg, parse_mode="Markdown")
