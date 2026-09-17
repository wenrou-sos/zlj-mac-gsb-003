from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/api/exhibitions", tags=["展陈管理"])


def _effective_status(ex: models.Exhibition, today: date | None = None) -> str:
    today = today or date.today()
    if today < ex.start_date:
        return "筹备中"
    if today > ex.end_date:
        return "已结束"
    return "开展中"


def _list_locked(ex: models.Exhibition) -> bool:
    """清单锁定 = 已人工冻结 或 展览已开展(开展中隐含锁定)。"""
    return ex.list_frozen or _effective_status(ex) == "开展中"


def _get_exhibition_or_404(db: Session, exhibition_id: int) -> models.Exhibition:
    ex = db.get(models.Exhibition, exhibition_id)
    if not ex:
        raise HTTPException(404, "展览不存在")
    return ex


def _get_item_or_404(db: Session, exhibition_id: int, item_id: int) -> models.ExhibitionItem:
    item = db.get(models.ExhibitionItem, item_id)
    if not item or item.exhibition_id != exhibition_id:
        raise HTTPException(404, "展陈条目不存在")
    return item


def _serialize(db: Session, ex: models.Exhibition) -> schemas.ExhibitionOut:
    ex.status = _effective_status(ex)
    out = schemas.ExhibitionOut.model_validate(ex)
    open_cnt = 0
    for item in out.items:
        coll = db.get(models.Collection, item.collection_id)
        if coll:
            item.collection_name = coll.name
            item.accession_no = coll.accession_no
        item.open_exception_count = sum(1 for e in item.exceptions if not e.resolved)
        open_cnt += item.open_exception_count
    out.open_exception_count = open_cnt
    for co in out.change_orders:
        if co.remove_collection_id:
            c = db.get(models.Collection, co.remove_collection_id)
            if c:
                co.remove_collection_name = c.name
                co.remove_accession_no = c.accession_no
        if co.add_collection_id:
            c = db.get(models.Collection, co.add_collection_id)
            if c:
                co.add_collection_name = c.name
                co.add_accession_no = c.accession_no
    return out


def _check_collection_available(db: Session, exhibition_id: int, collection_id: int) -> None:
    """同一藏品不得同时出现在其他未结束展览的有效清单(待布展/已布展)中。"""
    conflict = (
        db.query(models.ExhibitionItem)
        .join(models.Exhibition, models.ExhibitionItem.exhibition_id == models.Exhibition.id)
        .filter(
            models.ExhibitionItem.collection_id == collection_id,
            models.ExhibitionItem.exhibition_id != exhibition_id,
            models.ExhibitionItem.status.in_([models.ITEM_PLANNED, models.ITEM_MOUNTED]),
            models.Exhibition.end_date >= date.today(),
        )
        .first()
    )
    if conflict:
        raise HTTPException(400, "该藏品已列入其他未结束展览的展品清单")


def _add_item_row(
    db: Session,
    ex: models.Exhibition,
    collection_id: int,
    display_location: str | None,
    planned_mount_date: date | None = None,
) -> models.ExhibitionItem:
    c = db.get(models.Collection, collection_id)
    if not c:
        raise HTTPException(404, "藏品不存在")
    exists = (
        db.query(models.ExhibitionItem)
        .filter(
            models.ExhibitionItem.exhibition_id == ex.id,
            models.ExhibitionItem.collection_id == c.id,
            models.ExhibitionItem.status.in_([models.ITEM_PLANNED, models.ITEM_MOUNTED]),
        )
        .first()
    )
    if exists:
        raise HTTPException(400, "该藏品已在本展览的展品清单中")
    _check_collection_available(db, ex.id, c.id)
    item = models.ExhibitionItem(
        exhibition_id=ex.id,
        collection_id=c.id,
        display_location=display_location,
        planned_mount_date=planned_mount_date,
        status=models.ITEM_PLANNED,
    )
    db.add(item)
    db.flush()
    return item


def _mount_item(
    db: Session,
    ex: models.Exhibition,
    item: models.ExhibitionItem,
    acceptor: str,
    mounted_at: datetime | None,
    photo_notes: list[str],
    exceptions: list[str],
) -> None:
    """布展现场验收:条目 → 已布展,藏品 → 展陈中,登记布展流转与异常项。"""
    if item.status != models.ITEM_PLANNED:
        raise HTTPException(400, f"条目当前为「{item.status}」,无需布展")
    c = db.get(models.Collection, item.collection_id)
    if c.status != models.STATUS_IN_STORAGE:
        hint = {
            models.STATUS_EXHIBITION: "藏品已在其他展览中,请先撤展",
            models.STATUS_RESTORATION: "藏品正在修复中",
            models.STATUS_LOAN_OUT: "藏品借展在外",
            models.STATUS_OUT_STORAGE: "藏品不在库,请先办理入库归库",
        }.get(c.status, "")
        raise HTTPException(400, f"藏品当前为「{c.status}」状态,无法布展。{hint}")

    now = mounted_at or datetime.utcnow()
    item.status = models.ITEM_MOUNTED
    item.mounted_at = now
    item.mount_acceptor = acceptor
    item.mount_photo_notes = [n for n in photo_notes if n and n.strip()]
    for note in exceptions:
        if note and note.strip():
            db.add(
                models.ExhibitionException(
                    item_id=item.id,
                    phase=models.PHASE_MOUNT,
                    note=note.strip(),
                    created_by=acceptor,
                    created_at=now,
                )
            )
    db.add(
        models.Movement(
            collection_id=c.id,
            move_type=models.MOVE_EXHIBIT,
            from_location_id=c.location_id,
            purpose=f"布展:{ex.title}",
            operator="策展部",
            handler=acceptor,
            move_date=now,
            remark=item.display_location,
        )
    )
    c.status = models.STATUS_EXHIBITION
    c.location_id = None


def _dismount_item(
    db: Session,
    ex: models.Exhibition,
    item: models.ExhibitionItem,
    acceptor: str,
    dismounted_at: datetime | None,
    return_location_id: int | None,
    photo_notes: list[str],
    exceptions: list[str],
) -> None:
    """撤展现场验收:条目 → 已撤展,藏品归库,登记撤展流转与异常项。"""
    if item.status != models.ITEM_MOUNTED:
        raise HTTPException(400, f"条目当前为「{item.status}」,无法撤展验收")
    c = db.get(models.Collection, item.collection_id)

    now = dismounted_at or datetime.utcnow()
    item.status = models.ITEM_DISMOUNTED
    item.dismounted_at = now
    item.dismount_acceptor = acceptor
    item.dismount_photo_notes = [n for n in photo_notes if n and n.strip()]
    for note in exceptions:
        if note and note.strip():
            db.add(
                models.ExhibitionException(
                    item_id=item.id,
                    phase=models.PHASE_DISMOUNT,
                    note=note.strip(),
                    created_by=acceptor,
                    created_at=now,
                )
            )
    db.add(
        models.Movement(
            collection_id=c.id,
            move_type=models.MOVE_RETURN,
            to_location_id=return_location_id,
            purpose=f"撤展归库:{ex.title}",
            operator="策展部",
            handler=acceptor,
            move_date=now,
        )
    )
    if return_location_id and db.get(models.Location, return_location_id):
        c.location_id = return_location_id
        c.status = models.STATUS_IN_STORAGE
    else:
        c.status = models.STATUS_OUT_STORAGE


# ---------- 展览 ----------
@router.get("", response_model=list[schemas.ExhibitionOut])
def list_exhibitions(status: str | None = None, db: Session = Depends(get_db)):
    rows = (
        db.query(models.Exhibition)
        .options(
            joinedload(models.Exhibition.items).joinedload(models.ExhibitionItem.exceptions),
            joinedload(models.Exhibition.change_orders),
        )
        .order_by(models.Exhibition.start_date.desc())
        .all()
    )
    result = []
    for ex in rows:
        if status and _effective_status(ex) != status:
            continue
        result.append(_serialize(db, ex))
    return result


@router.post("", response_model=schemas.ExhibitionOut)
def create_exhibition(payload: schemas.ExhibitionCreate, db: Session = Depends(get_db)):
    if payload.end_date <= payload.start_date:
        raise HTTPException(400, "结束日期必须晚于开始日期")
    ex = models.Exhibition(**payload.model_dump())
    db.add(ex)
    db.commit()
    db.refresh(ex)
    return _serialize(db, ex)


@router.get("/{exhibition_id}", response_model=schemas.ExhibitionOut)
def get_exhibition(exhibition_id: int, db: Session = Depends(get_db)):
    ex = (
        db.query(models.Exhibition)
        .options(
            joinedload(models.Exhibition.items).joinedload(models.ExhibitionItem.exceptions),
            joinedload(models.Exhibition.change_orders),
        )
        .filter(models.Exhibition.id == exhibition_id)
        .first()
    )
    if not ex:
        raise HTTPException(404, "展览不存在")
    return _serialize(db, ex)


@router.put("/{exhibition_id}", response_model=schemas.ExhibitionOut)
def update_exhibition(
    exhibition_id: int, payload: schemas.ExhibitionUpdate, db: Session = Depends(get_db)
):
    ex = _get_exhibition_or_404(db, exhibition_id)
    data = payload.model_dump(exclude_unset=True)
    start = data.get("start_date", ex.start_date)
    end = data.get("end_date", ex.end_date)
    if end <= start:
        raise HTTPException(400, "结束日期必须晚于开始日期")
    for k, v in data.items():
        setattr(ex, k, v)
    db.commit()
    db.refresh(ex)
    return _serialize(db, ex)


# ---------- 清单冻结 ----------
@router.post("/{exhibition_id}/freeze", response_model=schemas.ExhibitionOut)
def freeze_list(
    exhibition_id: int, payload: schemas.ExhibitionFreeze, db: Session = Depends(get_db)
):
    ex = _get_exhibition_or_404(db, exhibition_id)
    if _effective_status(ex) != "筹备中":
        raise HTTPException(400, "仅筹备中的展览可执行冻结;开展后清单自动锁定")
    if ex.list_frozen:
        raise HTTPException(400, "展品清单已处于冻结状态")
    ex.list_frozen = True
    ex.frozen_at = datetime.utcnow()
    ex.frozen_by = payload.operator
    db.commit()
    db.refresh(ex)
    return _serialize(db, ex)


@router.post("/{exhibition_id}/unfreeze", response_model=schemas.ExhibitionOut)
def unfreeze_list(exhibition_id: int, db: Session = Depends(get_db)):
    ex = _get_exhibition_or_404(db, exhibition_id)
    if _effective_status(ex) != "筹备中":
        raise HTTPException(400, "展览已开展,清单锁定不可解除")
    if not ex.list_frozen:
        raise HTTPException(400, "展品清单未冻结")
    ex.list_frozen = False
    ex.frozen_at = None
    ex.frozen_by = None
    db.commit()
    db.refresh(ex)
    return _serialize(db, ex)


# ---------- 展品清单 ----------
@router.post("/{exhibition_id}/items", response_model=schemas.ExhibitionOut)
def add_exhibition_item(
    exhibition_id: int, payload: schemas.ExhibitionItemAdd, db: Session = Depends(get_db)
):
    ex = _get_exhibition_or_404(db, exhibition_id)
    if _effective_status(ex) == "已结束":
        raise HTTPException(400, "展览已结束,不能再调整展品清单")
    if _list_locked(ex):
        raise HTTPException(
            400, "展品清单已冻结或展览已开展,增删展品须提交变更单并经审批后执行"
        )
    _add_item_row(db, ex, payload.collection_id, payload.display_location, payload.planned_mount_date)
    db.commit()
    db.refresh(ex)
    return _serialize(db, ex)


@router.put("/{exhibition_id}/items/{item_id}", response_model=schemas.ExhibitionOut)
def update_exhibition_item(
    exhibition_id: int,
    item_id: int,
    payload: schemas.ExhibitionItemUpdate,
    db: Session = Depends(get_db),
):
    """调整展位 / 计划安装日期(冻结后仍允许,属于安装计划维护)。"""
    ex = _get_exhibition_or_404(db, exhibition_id)
    item = _get_item_or_404(db, exhibition_id, item_id)
    if item.status == models.ITEM_DISMOUNTED:
        raise HTTPException(400, "条目已撤展,不能再调整")
    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(item, k, v)
    db.commit()
    db.refresh(ex)
    return _serialize(db, ex)


@router.delete("/{exhibition_id}/items/{item_id}", response_model=schemas.ExhibitionOut)
def remove_exhibition_item(exhibition_id: int, item_id: int, db: Session = Depends(get_db)):
    ex = _get_exhibition_or_404(db, exhibition_id)
    item = _get_item_or_404(db, exhibition_id, item_id)
    if _list_locked(ex):
        raise HTTPException(
            400, "展品清单已冻结或展览已开展,增删展品须提交变更单并经审批后执行"
        )
    if item.status != models.ITEM_PLANNED:
        raise HTTPException(400, "已布展的展品须通过撤展验收下线,不能直接移除")
    db.delete(item)
    db.commit()
    db.refresh(ex)
    return _serialize(db, ex)


# ---------- 布展 / 撤展现场验收 ----------
@router.post("/{exhibition_id}/items/{item_id}/mount", response_model=schemas.ExhibitionOut)
def mount_item(
    exhibition_id: int,
    item_id: int,
    payload: schemas.MountConfirm,
    db: Session = Depends(get_db),
):
    ex = _get_exhibition_or_404(db, exhibition_id)
    if _effective_status(ex) == "已结束":
        raise HTTPException(400, "展览已结束,不能再布展")
    item = _get_item_or_404(db, exhibition_id, item_id)
    _mount_item(
        db, ex, item, payload.acceptor, payload.mounted_at, payload.photo_notes, payload.exceptions
    )
    db.commit()
    db.refresh(ex)
    return _serialize(db, ex)


@router.post("/{exhibition_id}/items/{item_id}/dismount", response_model=schemas.ExhibitionOut)
def dismount_item(
    exhibition_id: int,
    item_id: int,
    payload: schemas.DismountConfirm,
    db: Session = Depends(get_db),
):
    ex = _get_exhibition_or_404(db, exhibition_id)
    item = _get_item_or_404(db, exhibition_id, item_id)
    _dismount_item(
        db,
        ex,
        item,
        payload.acceptor,
        payload.dismounted_at,
        payload.return_location_id,
        payload.photo_notes,
        payload.exceptions,
    )
    db.commit()
    db.refresh(ex)
    return _serialize(db, ex)


# ---------- 现场异常 ----------
@router.post("/{exhibition_id}/items/{item_id}/exceptions", response_model=schemas.ExhibitionOut)
def add_exception(
    exhibition_id: int,
    item_id: int,
    payload: schemas.ExceptionCreate,
    db: Session = Depends(get_db),
):
    _get_exhibition_or_404(db, exhibition_id)
    item = _get_item_or_404(db, exhibition_id, item_id)
    if payload.phase not in (models.PHASE_MOUNT, models.PHASE_DISMOUNT):
        raise HTTPException(400, "异常阶段须为「布展」或「撤展」")
    if not payload.note or not payload.note.strip():
        raise HTTPException(400, "请填写异常内容")
    db.add(
        models.ExhibitionException(
            item_id=item.id,
            phase=payload.phase,
            note=payload.note.strip(),
            created_by=payload.created_by,
        )
    )
    db.commit()
    ex = _get_exhibition_or_404(db, exhibition_id)
    return _serialize(db, ex)


@router.post("/exceptions/{exception_id}/resolve", response_model=schemas.ExceptionOut)
def resolve_exception(
    exception_id: int, payload: schemas.ExceptionResolve, db: Session = Depends(get_db)
):
    exc = db.get(models.ExhibitionException, exception_id)
    if not exc:
        raise HTTPException(404, "异常记录不存在")
    if exc.resolved:
        raise HTTPException(400, "该异常已标记解决")
    exc.resolved = True
    exc.resolved_by = payload.resolved_by
    exc.resolved_at = datetime.utcnow()
    exc.resolve_note = payload.resolve_note
    db.commit()
    db.refresh(exc)
    return exc


# ---------- 变更单 ----------
def _get_order_or_404(db: Session, order_id: int) -> models.ExhibitionChangeOrder:
    co = db.get(models.ExhibitionChangeOrder, order_id)
    if not co:
        raise HTTPException(404, "变更单不存在")
    return co


@router.post("/{exhibition_id}/change-orders", response_model=schemas.ExhibitionOut)
def create_change_order(
    exhibition_id: int, payload: schemas.ChangeOrderCreate, db: Session = Depends(get_db)
):
    ex = _get_exhibition_or_404(db, exhibition_id)
    if _effective_status(ex) == "已结束":
        raise HTTPException(400, "展览已结束,不能再发起变更")
    if payload.order_type not in (models.CO_ADD, models.CO_REMOVE, models.CO_REPLACE):
        raise HTTPException(400, "变更类型须为 增展/撤展/替换")

    remove_item = None
    remove_collection_id = None
    if payload.order_type in (models.CO_REMOVE, models.CO_REPLACE):
        if not payload.remove_item_id:
            raise HTTPException(400, "请选择要撤下的展品条目")
        remove_item = _get_item_or_404(db, exhibition_id, payload.remove_item_id)
        if remove_item.status == models.ITEM_DISMOUNTED:
            raise HTTPException(400, "该条目已撤展")
        remove_collection_id = remove_item.collection_id
    if payload.order_type in (models.CO_ADD, models.CO_REPLACE):
        if not payload.add_collection_id:
            raise HTTPException(400, "请选择要增加的藏品")
        if not db.get(models.Collection, payload.add_collection_id):
            raise HTTPException(404, "藏品不存在")
        dup = (
            db.query(models.ExhibitionItem)
            .filter(
                models.ExhibitionItem.exhibition_id == exhibition_id,
                models.ExhibitionItem.collection_id == payload.add_collection_id,
                models.ExhibitionItem.status.in_([models.ITEM_PLANNED, models.ITEM_MOUNTED]),
            )
            .first()
        )
        if dup:
            raise HTTPException(400, "该藏品已在本展览的展品清单中")

    co = models.ExhibitionChangeOrder(
        exhibition_id=exhibition_id,
        order_type=payload.order_type,
        remove_item_id=remove_item.id if remove_item else None,
        remove_collection_id=remove_collection_id,
        add_collection_id=payload.add_collection_id,
        display_location=payload.display_location,
        reason=payload.reason,
        applicant=payload.applicant,
        status=models.CO_PENDING,
    )
    db.add(co)
    db.commit()
    db.refresh(ex)
    return _serialize(db, ex)


@router.post("/change-orders/{order_id}/approve", response_model=schemas.ChangeOrderOut)
def approve_change_order(
    order_id: int, payload: schemas.ChangeOrderApprove, db: Session = Depends(get_db)
):
    co = _get_order_or_404(db, order_id)
    if co.status != models.CO_PENDING:
        raise HTTPException(400, f"变更单当前为「{co.status}」,不能审批")
    co.status = models.CO_APPROVED
    co.approver = payload.approver
    co.approval_note = payload.note
    co.approved_at = datetime.utcnow()
    db.commit()
    db.refresh(co)
    return co


@router.post("/change-orders/{order_id}/reject", response_model=schemas.ChangeOrderOut)
def reject_change_order(
    order_id: int, payload: schemas.ChangeOrderApprove, db: Session = Depends(get_db)
):
    co = _get_order_or_404(db, order_id)
    if co.status != models.CO_PENDING:
        raise HTTPException(400, f"变更单当前为「{co.status}」,不能审批")
    co.status = models.CO_REJECTED
    co.approver = payload.approver
    co.approval_note = payload.note
    co.approved_at = datetime.utcnow()
    db.commit()
    db.refresh(co)
    return co


@router.post("/change-orders/{order_id}/execute", response_model=schemas.ExhibitionOut)
def execute_change_order(
    order_id: int, payload: schemas.ChangeOrderExecute, db: Session = Depends(get_db)
):
    co = _get_order_or_404(db, order_id)
    if co.status != models.CO_APPROVED:
        raise HTTPException(400, "仅「已批准」的变更单可执行")
    ex = _get_exhibition_or_404(db, co.exhibition_id)
    if _effective_status(ex) == "已结束":
        raise HTTPException(400, "展览已结束,变更单不可执行")

    # 撤下旧展品(撤展 / 替换)
    if co.order_type in (models.CO_REMOVE, models.CO_REPLACE) and co.remove_item_id:
        item = _get_item_or_404(db, ex.id, co.remove_item_id)
        if item.status == models.ITEM_MOUNTED:
            if not payload.acceptor:
                raise HTTPException(400, "撤下已布展展品须填写现场验收人")
            _dismount_item(
                db,
                ex,
                item,
                payload.acceptor,
                None,
                payload.return_location_id,
                payload.photo_notes,
                payload.exceptions,
            )
        else:
            # 待布展条目直接移出清单,变更单留存记录
            co.remove_item_id = None
            db.delete(item)
            db.flush()

    # 增加新展品(增展 / 替换):列入清单,待布展验收
    if co.order_type in (models.CO_ADD, models.CO_REPLACE):
        _add_item_row(db, ex, co.add_collection_id, co.display_location)

    co.status = models.CO_EXECUTED
    co.executed_at = datetime.utcnow()
    db.commit()
    db.refresh(ex)
    return _serialize(db, ex)
