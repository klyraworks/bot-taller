from telegram import Update
from telegram.ext import ContextTypes
from database import get_conn
from utils import require_rol

@require_rol("admin")
async def registrar_usuario(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # /adduser @username nombre rol
    partes = update.message.text.strip().split()
    if len(partes) < 4:
        await update.message.reply_text("Uso: /adduser @username Nombre rol\nRoles: admin, jefe, mecanico")
        return

    username = partes[1].lstrip("@")
    nombre = partes[2]
    rol = partes[3].lower()

    if rol not in ("admin", "jefe", "mecanico"):
        await update.message.reply_text("❌ Rol inválido. Usa: admin, jefe, mecanico")
        return

    conn = get_conn()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO usuarios (telegram_id, username, nombre, rol)
        VALUES (0, %s, %s, %s)
        ON CONFLICT (telegram_id) DO UPDATE SET nombre = EXCLUDED.nombre, rol = EXCLUDED.rol
    """, (username, nombre, rol))
    conn.commit()
    cur.close()
    conn.close()

    await update.message.reply_text(f"✅ Usuario *{nombre}* registrado como *{rol}*\nCuando escriba al bot quedará vinculado automáticamente.", parse_mode="Markdown")


@require_rol("admin")
async def listar_usuarios(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT nombre, rol, activo FROM usuarios ORDER BY rol, nombre")
    rows = cur.fetchall()
    cur.close()
    conn.close()

    if not rows:
        await update.message.reply_text("Sin usuarios registrados.")
        return

    msg = "👥 *Usuarios:*\n\n"
    for nombre, rol, activo in rows:
        emoji = {"admin": "👑", "jefe": "⭐", "mecanico": "🔧"}.get(rol, "👤")
        estado = "" if activo else " _(inactivo)_"
        msg += f"{emoji} {nombre} — {rol}{estado}\n"
    await update.message.reply_text(msg, parse_mode="Markdown")


@require_rol("admin")
async def registrar_gasto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    usuario = context.user_data["usuario"]
    partes = update.message.text.strip().split()

    if len(partes) < 3:
        await update.message.reply_text("Uso: /gasto 5 Descripción")
        return

    try:
        monto = float(partes[1])
    except ValueError:
        await update.message.reply_text("❌ Monto inválido")
        return

    desc = " ".join(partes[2:])
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("INSERT INTO gastos (tipo, monto, descripcion, registrado_por) VALUES ('gasto', %s, %s, %s)",
                (monto, desc, usuario["id"]))
    conn.commit()
    cur.close()
    conn.close()

    await update.message.reply_text(f"✅ Gasto de ${monto:.2f} registrado: {desc}")
