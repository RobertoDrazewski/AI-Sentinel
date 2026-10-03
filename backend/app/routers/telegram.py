from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.auth import get_current_user
from app.database import get_session
from app.integrations.telegram_bot import enviar_alerta_telegram
from app.models import TelegramConfig, User
from app.schemas import TelegramConfigIn, TelegramConfigOut

router = APIRouter(prefix="/api/telegram", tags=["telegram"])


@router.get("", response_model=TelegramConfigOut)
def get_config(session: Session = Depends(get_session), current_user: User = Depends(get_current_user)):
    cfg = session.exec(select(TelegramConfig).where(TelegramConfig.user_id == current_user.id)).first()
    if not cfg:
        return TelegramConfigOut(bot_token="", chat_id="", enabled=False)
    return cfg


@router.put("", response_model=TelegramConfigOut)
def set_config(
    data: TelegramConfigIn,
    session: Session = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    cfg = session.exec(select(TelegramConfig).where(TelegramConfig.user_id == current_user.id)).first()
    if cfg:
        cfg.bot_token = data.bot_token
        cfg.chat_id = data.chat_id
        cfg.enabled = data.enabled
    else:
        cfg = TelegramConfig(
            user_id=current_user.id, bot_token=data.bot_token, chat_id=data.chat_id, enabled=data.enabled
        )
    session.add(cfg)
    session.commit()
    return cfg


@router.post("/test")
def test_telegram(current_user: User = Depends(get_current_user), session: Session = Depends(get_session)):
    cfg = session.exec(select(TelegramConfig).where(TelegramConfig.user_id == current_user.id)).first()
    if not cfg:
        return {"ok": False, "message": "Todavía no configuraste el bot de Telegram."}
    ok, detail = enviar_alerta_telegram(
        cfg.bot_token, cfg.chat_id, None, "✅ AI Sentinel: mensaje de prueba. Si ves esto, ¡quedó bien configurado!"
    )
    return {"ok": ok, "message": detail}
