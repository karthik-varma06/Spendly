from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import select
from app.api.deps import get_db
from app.models.category import Category

router = APIRouter(prefix="/categories", tags=["categories"])

@router.get("")
def list_categories(db: Session = Depends(get_db)):
    categories = db.scalars(select(Category).order_by(Category.id)).all()
    return [{"id": c.id, "name": c.name, "icon": c.icon, "color": c.color} for c in categories]
