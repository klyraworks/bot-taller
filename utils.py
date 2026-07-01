import re
from database import get_conn

COLORES = {"v": "verde", "r": "roja", "a": "amarilla", "az": "azul", "rs": "rojo san carlos"}

def parsear_tricimoto(texto):
    match = re.match(r'^(\d+)(az|v|r|a)$', texto.loswer())
    if not match:
        return None, None
    return match.group(1), match.group(2)

def get_usuario(telegram_id):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute("SELECT id, nombre, rol, is_active FROM usuarios WHERE telegram_id = %s", (telegram_id,))
    row = cur.fetchone()
    cur.close()
    conn.close()
    if not row:
        return None
    return {"id": row[0], "nombre": row[1], "rol": row[2], "is_active": row[3]}

def require_rol(*roles):
    """Decorador que verifica rol antes de ejecutar el handler."""
    def decorator(func):
        async def wrapper(update, context):
            usuario = get_usuario(update.effective_user.id)
            if not usuario:
                await update.message.reply_text("❌ No estás registrado. Contacta al administrador.")
                return
            if not usuario["is_active"]:
                await update.message.reply_text("❌ Tu cuenta está desactivada.")
                return
            if usuario["rol"] not in roles:
                await update.message.reply_text("❌ No tienes permiso para este comando.")
                return
            context.user_data["usuario"] = usuario
            return await func(update, context)
        return wrapper
    return decorator
