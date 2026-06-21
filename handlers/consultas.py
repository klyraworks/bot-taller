from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes
from database import get_conn
from utils import parsear_tricimoto, COLORES, require_rol, get_usuario

# ─── FORMATO ─────────────────────────────────────────────────────────────────

def formatear_servicio(row):
    sid, num, color, total, pendiente, desc, mecanico, fecha, estado = row
    fecha_str = fecha.strftime("%d/%m/%Y %H:%M") if fecha else "?"
    cobrado = float(total) - float(pendiente)
    linea = f"[#{sid}] *{num} {color}* | Total: ${float(total):.2f} | Cobrado: ${cobrado:.2f}"
    if float(pendiente) > 0:
        linea += f" | Pendiente: ${float(pendiente):.2f}"
    if desc:
        linea += f"\n  📝 {desc}"
    linea += f"\n  🔧 {mecanico} | 📅 {fecha_str} | _{estado}_"
    return linea

def formatear_lista(rows):
    if not rows:
        return "Sin registros."
    return "\n\n".join(formatear_servicio(r) for r in rows)

def parsear_fecha(texto):
    """Intenta parsear dd/mm/yyyy o mm/yyyy."""
    try:
        return datetime.strptime(texto, "%d/%m/%Y"), "dia"
    except ValueError:
        pass
    try:
        return datetime.strptime(texto, "%m/%Y"), "mes"
    except ValueError:
        pass
    return None, None

# ─── CONSULTAS ───────────────────────────────────────────────────────────────

QUERY_BASE = """
    SELECT s.id, s.tricimoto_num, s.tricimoto_color, s.monto_total, s.monto_pendiente,
           s.descripcion, u.nombre, s.created_at, s.estado
    FROM servicios s
    JOIN usuarios u ON s.mecanico_id = u.id
    WHERE s.is_active = TRUE
"""

@require_rol("admin", "jefe", "mecanico")
async def consulta_dia(update: Update, context: ContextTypes.DEFAULT_TYPE):
    usuario = context.user_data["usuario"]
    args = context.args

    if not args:
        await update.message.reply_text("Uso:\n`/dia dd/mm/yyyy` — día\n`/dia dd/mm/yyyy dd/mm/yyyy` — rango\n`/dia mm/yyyy` — mes", parse_mode="Markdown")
        return

    conn = get_conn()
    cur = conn.cursor()

    if len(args) == 1:
        fecha, tipo = parsear_fecha(args[0])
        if not fecha:
            await update.message.reply_text("❌ Formato inválido. Ej: `20/06/2025` o `06/2025`", parse_mode="Markdown")
            cur.close(); conn.close(); return

        if tipo == "dia":
            cur.execute(QUERY_BASE + "AND DATE(s.created_at) = %s ORDER BY s.created_at DESC", (fecha.date(),))
            titulo = f"📅 Servicios del {args[0]}"
        else:
            cur.execute(QUERY_BASE + "AND EXTRACT(MONTH FROM s.created_at) = %s AND EXTRACT(YEAR FROM s.created_at) = %s ORDER BY s.created_at DESC",
                        (fecha.month, fecha.year))
            titulo = f"📅 Servicios de {args[0]}"

    elif len(args) == 2:
        fecha_ini, _ = parsear_fecha(args[0])
        fecha_fin, _ = parsear_fecha(args[1])
        if not fecha_ini or not fecha_fin:
            await update.message.reply_text("❌ Formato inválido. Ej: `20/06/2025 25/06/2025`", parse_mode="Markdown")
            cur.close(); conn.close(); return
        cur.execute(QUERY_BASE + "AND DATE(s.created_at) BETWEEN %s AND %s ORDER BY s.created_at DESC",
                    (fecha_ini.date(), fecha_fin.date()))
        titulo = f"📅 Servicios del {args[0]} al {args[1]}"

    else:
        await update.message.reply_text("❌ Demasiados argumentos.")
        cur.close(); conn.close(); return

    # Mecánicos solo ven sus propios registros
    rows = cur.fetchall()
    if usuario["rol"] == "mecanico":
        rows = [r for r in rows if r[6] == usuario["nombre"]]

    cur.close()
    conn.close()

    msg = f"{titulo}\n\n{formatear_lista(rows)}"
    await update.message.reply_text(msg, parse_mode="Markdown")


@require_rol("admin", "jefe", "mecanico")
async def consulta_moto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    usuario = context.user_data["usuario"]
    args = context.args

    if not args:
        await update.message.reply_text("Uso: `/moto 21r`", parse_mode="Markdown")
        return

    num, color = parsear_tricimoto(args[0])
    if not num:
        await update.message.reply_text("❌ Tricimoto inválida. Ej: 21r, 05v, 31az")
        return

    color_nombre = COLORES.get(color, color)
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(QUERY_BASE + "AND s.tricimoto_num = %s AND s.tricimoto_color = %s ORDER BY s.created_at DESC LIMIT 20",
                (num, color_nombre))
    rows = cur.fetchall()

    if usuario["rol"] == "mecanico":
        rows = [r for r in rows if r[6] == usuario["nombre"]]

    cur.close()
    conn.close()

    msg = f"🛺 Historial de *{num} {color_nombre}*\n\n{formatear_lista(rows)}"
    await update.message.reply_text(msg, parse_mode="Markdown")

# ─── EDITAR ──────────────────────────────────────────────────────────────────

CAMPOS_VALIDOS = {"monto", "pendiente", "descripcion", "mecanico", "moto"}

@require_rol("admin", "jefe")
async def editar_servicio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    usuario = context.user_data["usuario"]
    args = context.args

    if len(args) < 3:
        await update.message.reply_text(
            "Uso: `/editar [id] [campo] [valor]`\n"
            "Campos: `monto`, `pendiente`, `descripcion`, `mecanico`, `moto`",
            parse_mode="Markdown"
        )
        return

    try:
        sid = int(args[0])
    except ValueError:
        await update.message.reply_text("❌ ID inválido")
        return

    campo = args[1].lower()
    valor = " ".join(args[2:])

    if campo not in CAMPOS_VALIDOS:
        await update.message.reply_text(f"❌ Campo inválido. Usa: {', '.join(CAMPOS_VALIDOS)}")
        return

    conn = get_conn()
    cur = conn.cursor()

    # Verificar que el servicio existe
    cur.execute("SELECT id FROM servicios WHERE id = %s", (sid,))
    if not cur.fetchone():
        await update.message.reply_text(f"❌ No existe el servicio #{sid}")
        cur.close(); conn.close(); return

    if campo == "monto":
        try:
            cur.execute("UPDATE servicios SET monto_total = %s WHERE id = %s", (float(valor), sid))
        except ValueError:
            await update.message.reply_text("❌ Monto inválido"); cur.close(); conn.close(); return

    elif campo == "pendiente":
        try:
            nuevo_pendiente = float(valor)
            estado = "pagado" if nuevo_pendiente == 0 else "activo"
            cur.execute("UPDATE servicios SET monto_pendiente = %s, estado = %s WHERE id = %s", (nuevo_pendiente, estado, sid))
        except ValueError:
            await update.message.reply_text("❌ Monto inválido"); cur.close(); conn.close(); return

    elif campo == "descripcion":
        cur.execute("UPDATE servicios SET descripcion = %s WHERE id = %s", (valor, sid))

    elif campo == "mecanico":
        cur.execute("SELECT id FROM usuarios WHERE LOWER(nombre) = LOWER(%s) AND activo = TRUE", (valor,))
        row = cur.fetchone()
        if not row:
            await update.message.reply_text(f"❌ No existe el mecánico *{valor}*", parse_mode="Markdown")
            cur.close(); conn.close(); return
        cur.execute("UPDATE servicios SET mecanico_id = %s WHERE id = %s", (row[0], sid))

    elif campo == "moto":
        num, color = parsear_tricimoto(valor)
        if not num:
            await update.message.reply_text("❌ Tricimoto inválida. Ej: 21r, 05v, 31az")
            cur.close(); conn.close(); return
        cur.execute("UPDATE servicios SET tricimoto_num = %s, tricimoto_color = %s WHERE id = %s",
                    (num, COLORES.get(color, color), sid))

    # Log
    cur.execute("""
        INSERT INTO logs (accion, tabla, registro_id, detalle, registrado_por)
        VALUES ('EDITAR', 'servicios', %s, %s, %s)
    """, (sid, f"campo={campo} valor={valor}", usuario["id"]))

    conn.commit()
    cur.close()
    conn.close()

    await update.message.reply_text(f"✅ Servicio #{sid} actualizado: *{campo}* → `{valor}`", parse_mode="Markdown")

# ─── ELIMINAR ────────────────────────────────────────────────────────────────

@require_rol("admin", "jefe")
async def eliminar_servicio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    usuario = context.user_data["usuario"]
    args = context.args

    if not args:
        await update.message.reply_text("Uso: `/eliminar [id]`", parse_mode="Markdown")
        return

    try:
        sid = int(args[0])
    except ValueError:
        await update.message.reply_text("❌ ID inválido")
        return

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT tricimoto_num, tricimoto_color, monto_total FROM servicios WHERE id = %s", (sid,))
    row = cur.fetchone()

    if not row:
        await update.message.reply_text(f"❌ No existe el servicio #{sid}")
        cur.close(); conn.close(); return

    num, color, monto = row
    cur.execute("""
        UPDATE servicios SET is_active = FALSE, deleted_at = NOW(), estado = 'anulado' WHERE id = %s
    """, (sid,))
    cur.execute("""
        INSERT INTO logs (accion, tabla, registro_id, detalle, registrado_por)
        VALUES ('ELIMINAR', 'servicios', %s, %s, %s)
    """, (sid, f"{num} {color} ${float(monto):.2f}", usuario["id"]))

    conn.commit()
    cur.close()
    conn.close()

    await update.message.reply_text(f"🗑️ Servicio #{sid} eliminado: *{num} {color}* ${float(monto):.2f}", parse_mode="Markdown")
