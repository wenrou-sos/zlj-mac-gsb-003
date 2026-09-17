from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from .. import models, schemas
from ..database import get_db

router = APIRouter(tags=["藏品档案与出入库"])


def _get_collection_or_404(db: Session, collection_id: int) -> models.Collection:
    c = db.get(models.Collection, collection_id)
    if not c:
        raise HTTPException(404, "藏品不存在")
    return c


# ---------- 藏品档案 ----------
@router.get("/api/collections", response_model=list[schemas.CollectionList])
def list_collections(
    db: Session = Depends(get_db),
    keyword: str | None = None,
    category: str | None = None,
    status: str | None = None,
    location_id: int | None = None,
):
    q = db.query(models.Collection)
    if keyword:
        like = f"%{keyword}%"
        q = q.filter(
            or_(
                models.Collection.name.like(like),
                models.Collection.accession_no.like(like),
                models.Collection.dynasty.like(like),
            )
        )
    if category:
        q = q.filter(models.Collection.category == category)
    if status:
        q = q.filter(models.Collection.status == status)
    if location_id is not None:
        q = q.filter(models.Collection.location_id == location_id)
    return q.order_by(models.Collection.accession_no).all()


@router.get("/api/collections/meta")
def collection_meta(db: Session = Depends(get_db)):
    categories = [r[0] for r in db.query(models.Collection.category).distinct().all()]
    statuses = [
        models.STATUS_IN_STORAGE,
        models.STATUS_OUT_STORAGE,
        models.STATUS_EXHIBITION,
        models.STATUS_RESTORATION,
        models.STATUS_LOAN_OUT,
    ]
    return {"categories": sorted(categories), "statuses": statuses}


@router.get("/api/collections/{collection_id}", response_model=schemas.CollectionDetail)
def get_collection(collection_id: int, db: Session = Depends(get_db)):
    c = _get_collection_or_404(db, collection_id)
    return c


@router.get(
    "/api/collections/{collection_id}/exhibition-exceptions",
    response_model=list[schemas.CollectionExceptionOut],
)
def collection_exhibition_exceptions(
    collection_id: int,
    db: Session = Depends(get_db),
    unresolved_only: bool = False,
):
    """藏品在各展览布展/撤展中产生的现场异常(未解决的在藏品详情持续可见)。"""
    _get_collection_or_404(db, collection_id)
    q = (
        db.query(models.ExhibitionException, models.ExhibitionItem, models.Exhibition)
        .join(
            models.ExhibitionItem,
            models.ExhibitionException.item_id == models.ExhibitionItem.id,
        )
        .join(models.Exhibition, models.ExhibitionItem.exhibition_id == models.Exhibition.id)
        .filter(models.ExhibitionItem.collection_id == collection_id)
    )
    if unresolved_only:
        q = q.filter(models.ExhibitionException.resolved.is_(False))
    rows = q.order_by(models.ExhibitionException.created_at.desc()).all()
    result = []
    for exc, item, ex in rows:
        out = schemas.CollectionExceptionOut.model_validate(exc)
        out.exhibition_id = ex.id
        out.exhibition_title = ex.title
        out.display_location = item.display_location
        result.append(out)
    return result


@router.post("/api/collections", response_model=schemas.CollectionDetail)
def create_collection(payload: schemas.CollectionCreate, db: Session = Depends(get_db)):
    if db.query(models.Collection).filter(
        models.Collection.accession_no == payload.accession_no
    ).first():
        raise HTTPException(400, f"总登记号 {payload.accession_no} 已存在")
    data = payload.model_dump()
    loc_id = data.get("location_id")
    c = models.Collection(**data)
    c.status = models.STATUS_IN_STORAGE if loc_id else models.STATUS_OUT_STORAGE
    db.add(c)
    db.flush()
    if loc_id:
        db.add(
            models.Movement(
                collection_id=c.id,
                move_type=models.MOVE_IN,
                to_location_id=loc_id,
                purpose="建档入库",
                operator="系统",
                move_date=datetime.utcnow(),
            )
        )
    db.commit()
    db.refresh(c)
    return c


@router.put("/api/collections/{collection_id}", response_model=schemas.CollectionDetail)
def update_collection(
    collection_id: int, payload: schemas.CollectionUpdate, db: Session = Depends(get_db)
):
    c = _get_collection_or_404(db, collection_id)
    data = payload.model_dump(exclude_unset=True)
    if "accession_no" in data:
        dup = (
            db.query(models.Collection)
            .filter(
                models.Collection.accession_no == data["accession_no"],
                models.Collection.id != collection_id,
            )
            .first()
        )
        if dup:
            raise HTTPException(400, "总登记号已存在")

    # 档案编辑变更存放位置:仅在库藏品允许,并自动补登出入库台账
    if "location_id" in data and data["location_id"] != c.location_id:
        old_id = c.location_id
        new_id = data["location_id"]
        if new_id is not None and not db.get(models.Location, new_id):
            raise HTTPException(400, "目标存放位置不存在")
        if c.status not in (models.STATUS_IN_STORAGE, models.STATUS_OUT_STORAGE):
            raise HTTPException(
                400,
                f"藏品当前为「{c.status}」状态,不能通过编辑档案修改位置,"
                "请在对应模块办理撤展/结项/归还归库",
            )
        if new_id is not None:
            db.add(
                models.Movement(
                    collection_id=c.id,
                    move_type=models.MOVE_IN if old_id is None else models.MOVE_TRANSFER,
                    from_location_id=old_id,
                    to_location_id=new_id,
                    purpose="档案编辑变更存放位置",
                    operator="档案管理",
                    move_date=datetime.utcnow(),
                )
            )
            c.status = models.STATUS_IN_STORAGE
        else:
            # 清空库位视为出库
            db.add(
                models.Movement(
                    collection_id=c.id,
                    move_type=models.MOVE_OUT,
                    from_location_id=old_id,
                    to_location_id=None,
                    purpose="档案编辑清空存放位置",
                    operator="档案管理",
                    move_date=datetime.utcnow(),
                )
            )
            c.status = models.STATUS_OUT_STORAGE

    for k, v in data.items():
        setattr(c, k, v)
    db.commit()
    db.refresh(c)
    return c


@router.delete("/api/collections/{collection_id}")
def delete_collection(collection_id: int, db: Session = Depends(get_db)):
    c = _get_collection_or_404(db, collection_id)
    db.delete(c)
    db.commit()
    return {"ok": True}


# ---------- 出入库 / 流转 ----------
@router.get("/api/movements", response_model=list[schemas.MovementOut])
def list_movements(
    db: Session = Depends(get_db),
    collection_id: int | None = None,
    move_type: str | None = None,
    limit: int = Query(200, le=1000),
):
    q = (
        db.query(models.Movement)
        .options(
            joinedload(models.Movement.collection),
            joinedload(models.Movement.from_location),
            joinedload(models.Movement.to_location),
        )
        .order_by(models.Movement.move_date.desc())
    )
    if collection_id:
        q = q.filter(models.Movement.collection_id == collection_id)
    if move_type:
        q = q.filter(models.Movement.move_type == move_type)
    rows = q.limit(limit).all()
    result = []
    for m in rows:
        out = schemas.MovementOut.model_validate(m)
        out.collection_name = m.collection.name if m.collection else None
        out.accession_no = m.collection.accession_no if m.collection else None
        result.append(out)
    return result


@router.post(
    "/api/collections/{collection_id}/movements", response_model=schemas.MovementOut
)
def create_movement(
    collection_id: int, payload: schemas.MovementCreate, db: Session = Depends(get_db)
):
    c = _get_collection_or_404(db, collection_id)
    if c.status not in (models.STATUS_IN_STORAGE, models.STATUS_OUT_STORAGE):
        raise HTTPException(
            400,
            f"藏品当前为「{c.status}」状态,布展/修复/借展请在对应模块办理撤展、结项或归还后再操作",
        )

    move_type = payload.move_type
    allowed = {
        models.MOVE_IN,
        models.MOVE_OUT,
        models.MOVE_TRANSFER,
        models.MOVE_RETURN,
    }
    if move_type not in allowed:
        raise HTTPException(400, f"通用流转仅支持: {sorted(allowed)}(布展/修复/借展请走专用流程)")

    from_id = c.location_id
    to_id = payload.to_location_id
    if move_type in (models.MOVE_IN, models.MOVE_TRANSFER) and not to_id:
        raise HTTPException(400, f"{move_type} 必须选择目标位置")
    if to_id and not db.get(models.Location, to_id):
        raise HTTPException(400, "目标位置不存在")

    m = models.Movement(
        collection_id=c.id,
        move_type=move_type,
        from_location_id=from_id,
        to_location_id=to_id,
        purpose=payload.purpose,
        operator=payload.operator,
        handler=payload.handler,
        move_date=payload.move_date or datetime.utcnow(),
        remark=payload.remark,
    )
    db.add(m)

    if move_type == models.MOVE_OUT:
        c.status = models.STATUS_OUT_STORAGE
        c.location_id = None
    elif move_type == models.MOVE_RETURN and not to_id:
        # 仅登记出库返回、未指定库位
        c.status = models.STATUS_OUT_STORAGE
    else:
        c.location_id = to_id
        c.status = models.STATUS_IN_STORAGE

    db.commit()
    db.refresh(m)
    out = schemas.MovementOut.model_validate(m)
    out.collection_name = c.name
    out.accession_no = c.accession_no
    return out
