from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload

from .. import models, schemas
from ..database import get_db

router = APIRouter(prefix="/api/exhibitions", tags=["展陈管理"])
# 跨展览的异常跟踪(不带 /api/exhibitions 前缀,避免与 /{exhibition_id} 冲突)
anomaly_router = APIRouter(prefix="/api/exhibition-anomalies", tags=["展陈异常"])


def _effective_status(ex: models.Exhibition, today: date | None = None) -> str:
    today = today or date.today()
    if today < ex.start_date:
        return models.EX_STATUS_PREP
    if today > ex.end_date:
        return models.EX_STATUS_CLOSED
    return models.EX_STATUS_OPEN


def _has_open_anomaly(item: models.ExhibitionItem) -> bool:
    if item.mount_anomaly and not item.mount_anomaly_resolved:
        return True
    if item.dismount_anomaly and not item.dismount_anomaly_resolved:
        return True
    return False


def _serialize_item(db: Session, item: models.ExhibitionItem) -> schemas.ExhibitionItemOut:
    out = schemas.ExhibitionItemOut.model_validate(item)
    coll = db.get(models.Collection, item.collection_id)
    if coll:
        out.collection_name = coll.name
        out.accession_no = coll.accession_no
    out.has_open_anomaly = _has_open_anomaly(item)
    return out


def _serialize_co(db: Session, co: models.ChangeOrder) -> schemas.ChangeOrderOut:
    out = schemas.ChangeOrderOut.model_validate(co)
    if co.add_collection_id:
        c = db.get(models.Collection, co.add_collection_id)
        if c:
            out.add_collection_label = f"{c.accession_no} {c.name}"
    if co.remove_item_id:
        old = db.get(models.ExhibitionItem, co.remove_item_id)
        if old:
            c = db.get(models.Collection, old.collection_id)
            label = f"{c.accession_no} {c.name}" if c else f"藏品#{old.collection_id}"
            if old.display_location:
                label += f"(原展位 {old.display_location})"
            out.remove_item_label = label
        elif co.remove_item_label:
            # 替换撤除的计划条目已在执行时移出清单,使用审批快照
            out.remove_item_label = co.remove_item_label
    return out


def _serialize(db: Session, ex: models.Exhibition) -> schemas.ExhibitionOut:
    ex.status = _effective_status(ex)
    out = schemas.ExhibitionOut.model_validate(ex)
    # 经变更单移出清单的计划条目仅保留在变更审计中,不在展品清单中展示
    visible_items = [it for it in ex.items if it.status != models.ITEM_REMOVED]
    out.items = [_serialize_item(db, it) for it in visible_items]
    out.change_orders = [
        _serialize_co(db, co)
        for co in sorted(ex.change_orders, key=lambda x: x.requested_at, reverse=True)
    ]
    out.open_anomaly_count = sum(1 for it in visible_items if _has_open_anomaly(it))
    return out


def _get_exhibition(db: Session, exhibition_id: int) -> models.Exhibition:
    ex = (
        db.query(models.Exhibition)
        .options(
            joinedload(models.Exhibition.items),
            joinedload(models.Exhibition.change_orders),
        )
        .filter(models.Exhibition.id == exhibition_id)
        .first()
    )
    if not ex:
        raise HTTPException(404, "展览不存在")
    return ex


def _active_item(
    db: Session, exhibition_id: int, collection_id: int
) -> models.ExhibitionItem | None:
    """同一展览中尚未撤展的条目(待布展/已布展)。"""
    return (
        db.query(models.ExhibitionItem)
        .filter(
            models.ExhibitionItem.exhibition_id == exhibition_id,
            models.ExhibitionItem.collection_id == collection_id,
            models.ExhibitionItem.status.in_([models.ITEM_PLANNED, models.ITEM_MOUNTED]),
        )
        .first()
    )


# ---------- 展览 ----------
@router.get("", response_model=list[schemas.ExhibitionOut])
def list_exhibitions(status: str | None = None, db: Session = Depends(get_db)):
    rows = (
        db.query(models.Exhibition)
        .options(
            joinedload(models.Exhibition.items),
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


@anomaly_router.get("", response_model=list[dict])
def list_open_anomalies(
    collection_id: int | None = None,
    open_only: bool = Query(True),
    db: Session = Depends(get_db),
):
    """跨展览的布展/撤展异常清单(默认只返回未闭环项),供展览与藏品详情持续展示。"""
    q = (
        db.query(models.ExhibitionItem)
        .options(joinedload(models.ExhibitionItem.exhibition))
        .order_by(models.ExhibitionItem.id.desc())
    )
    if collection_id is not None:
        q = q.filter(models.ExhibitionItem.collection_id == collection_id)
    result = []
    for item in q.all():
        coll = db.get(models.Collection, item.collection_id)
        ex = item.exhibition
        for phase, anomaly, at, acceptor, resolved, by, rat in (
            (
                "布展",
                item.mount_anomaly,
                item.mounted_at,
                item.mount_acceptor,
                item.mount_anomaly_resolved,
                item.mount_anomaly_resolved_by,
                item.mount_anomaly_resolved_at,
            ),
            (
                "撤展",
                item.dismount_anomaly,
                item.dismounted_at,
                item.dismount_acceptor,
                item.dismount_anomaly_resolved,
                item.dismount_anomaly_resolved_by,
                item.dismount_anomaly_resolved_at,
            ),
        ):
            if not anomaly:
                continue
            if open_only and resolved:
                continue
            result.append(
                {
                    "exhibition_id": ex.id,
                    "exhibition_title": ex.title,
                    "exhibition_status": _effective_status(ex),
                    "item_id": item.id,
                    "phase": phase,
                    "anomaly": anomaly,
                    "occurred_at": at,
                    "acceptor": acceptor,
                    "resolved": resolved,
                    "resolved_by": by,
                    "resolved_at": rat,
                    "collection_id": item.collection_id,
                    "accession_no": coll.accession_no if coll else None,
                    "collection_name": coll.name if coll else None,
                    "display_location": item.display_location,
                }
            )
    return result


@router.get("/{exhibition_id}", response_model=schemas.ExhibitionOut)
def get_exhibition(exhibition_id: int, db: Session = Depends(get_db)):
    return _serialize(db, _get_exhibition(db, exhibition_id))


@router.post("/{exhibition_id}/freeze", response_model=schemas.ExhibitionOut)
def freeze_checklist(
    exhibition_id: int, payload: schemas.ExhibitionFreeze, db: Session = Depends(get_db)
):
    """冻结展品清单;冻结后只能通过变更单增删展品。"""
    ex = _get_exhibition(db, exhibition_id)
    status = _effective_status(ex)
    if status != models.EX_STATUS_PREP:
        raise HTTPException(400, f"展览已「{status}」,清单无需再冻结")
    if ex.frozen:
        raise HTTPException(400, "清单已冻结")
    if not ex.items:
        raise HTTPException(400, "清单为空,无法冻结:请先添加展品与安装计划")
    ex.frozen = True
    ex.frozen_at = datetime.utcnow()
    ex.frozen_by = payload.frozen_by or "策展团队"
    db.commit()
    db.refresh(ex)
    return _serialize(db, ex)


# ---------- 筹备阶段:清单维护(仅未冻结) ----------
@router.post("/{exhibition_id}/items", response_model=schemas.ExhibitionOut)
def plan_exhibition_item(
    exhibition_id: int, payload: schemas.ExhibitionItemPlanAdd, db: Session = Depends(get_db)
):
    """筹备阶段把展品加入清单:仅登记展位与安装计划,不发生出入库。"""
    ex = _get_exhibition(db, exhibition_id)
    if _effective_status(ex) != models.EX_STATUS_PREP:
        raise HTTPException(400, "展览已进入开展中,新增展品请提交变更单审批")
    if ex.frozen:
        raise HTTPException(400, "展品清单已冻结,新增展品请提交变更单审批")
    c = db.get(models.Collection, payload.collection_id)
    if not c:
        raise HTTPException(404, "藏品不存在")
    if _active_item(db, exhibition_id, c.id):
        raise HTTPException(400, "该藏品已在本展览清单中")
    if c.status != models.STATUS_IN_STORAGE:
        raise HTTPException(400, f"藏品当前为「{c.status}」状态,无法纳入展品清单")

    item = models.ExhibitionItem(
        exhibition_id=exhibition_id,
        collection_id=c.id,
        display_location=payload.display_location,
        install_plan_note=payload.install_plan_note,
        planned_mount_date=payload.planned_mount_date,
        status=models.ITEM_PLANNED,
    )
    db.add(item)
    db.commit()
    db.refresh(ex)
    return _serialize(db, ex)


@router.delete("/{exhibition_id}/items/{item_id}", response_model=schemas.ExhibitionOut)
def remove_planned_item(exhibition_id: int, item_id: int, db: Session = Depends(get_db)):
    """筹备阶段、清单未冻结时,直接移除尚未布展的清单条目。"""
    ex = _get_exhibition(db, exhibition_id)
    if _effective_status(ex) != models.EX_STATUS_PREP:
        raise HTTPException(400, "展览已进入开展中,撤除展品请提交变更单审批")
    if ex.frozen:
        raise HTTPException(400, "展品清单已冻结,撤除展品请提交变更单审批")
    item = db.get(models.ExhibitionItem, item_id)
    if not item or item.exhibition_id != exhibition_id:
        raise HTTPException(404, "清单条目不存在")
    if item.status != models.ITEM_PLANNED:
        raise HTTPException(400, "已布展展品请走撤展流程,不能直接移出清单")
    db.delete(item)
    db.commit()
    db.refresh(ex)
    return _serialize(db, ex)


# ---------- 现场布展 / 撤展验收 ----------
def _acceptance_remark(photo_note: str | None, anomaly: str | None) -> str | None:
    parts = []
    if photo_note:
        parts.append(f"照片说明:{photo_note}")
    if anomaly:
        parts.append(f"异常项:{anomaly}")
    return " | ".join(parts) or None


@router.post("/{exhibition_id}/items/{item_id}/mount", response_model=schemas.ExhibitionOut)
def mount_item(
    exhibition_id: int,
    item_id: int,
    payload: schemas.MountRequest,
    db: Session = Depends(get_db),
):
    """现场布展验收:验收人、时间、照片说明、异常项;藏品出库进入展陈中。"""
    ex = _get_exhibition(db, exhibition_id)
    status = _effective_status(ex)
    if status == models.EX_STATUS_CLOSED:
        raise HTTPException(400, "展览已结束,不能再布展")
    item = db.get(models.ExhibitionItem, item_id)
    if not item or item.exhibition_id != exhibition_id:
        raise HTTPException(404, "清单条目不存在")
    if item.status != models.ITEM_PLANNED:
        raise HTTPException(400, f"该条目当前为「{item.status}」,不能布展")

    # 开展中布展 = 增补/替换展品,必须持有已批准并执行的变更单
    if status == models.EX_STATUS_OPEN and not item.change_order_id:
        raise HTTPException(400, "展览已开展,无审批变更单不允许新增/替换展品")

    c = db.get(models.Collection, item.collection_id)
    if not c:
        raise HTTPException(404, "藏品不存在")
    if c.status != models.STATUS_IN_STORAGE:
        raise HTTPException(400, f"藏品当前为「{c.status}」状态,无法布展")

    now = payload.mounted_at or datetime.utcnow()
    item.status = models.ITEM_MOUNTED
    item.mounted_at = now
    item.mount_acceptor = payload.acceptor
    item.mount_photo_note = payload.photo_note
    item.mount_anomaly = payload.anomaly
    item.mount_anomaly_resolved = False

    purpose = f"布展:{ex.title}"
    if item.change_order_id:
        purpose += f"(变更单 #{item.change_order_id})"
    db.add(
        models.Movement(
            collection_id=c.id,
            move_type=models.MOVE_EXHIBIT,
            from_location_id=c.location_id,
            purpose=purpose,
            operator=payload.acceptor,
            move_date=now,
            remark=_acceptance_remark(payload.photo_note, payload.anomaly)
            or item.display_location,
        )
    )
    c.status = models.STATUS_EXHIBITION
    c.location_id = None
    db.commit()
    db.refresh(ex)
    return _serialize(db, ex)


@router.post("/{exhibition_id}/items/{item_id}/dismount", response_model=schemas.ExhibitionOut)
def dismount_item(
    exhibition_id: int,
    item_id: int,
    payload: schemas.DismountRequest,
    db: Session = Depends(get_db),
):
    """现场撤展验收:验收人、时间、照片说明、异常项;可同时登记归库位置。"""
    ex = _get_exhibition(db, exhibition_id)
    item = db.get(models.ExhibitionItem, item_id)
    if not item or item.exhibition_id != exhibition_id:
        raise HTTPException(404, "清单条目不存在")
    if item.status != models.ITEM_MOUNTED:
        raise HTTPException(400, f"该条目当前为「{item.status}」,不能撤展")
    c = db.get(models.Collection, item.collection_id)

    now = payload.dismounted_at or datetime.utcnow()
    item.status = models.ITEM_DISMOUNTED
    item.dismounted_at = now
    item.dismount_acceptor = payload.acceptor
    item.dismount_photo_note = payload.photo_note
    item.dismount_anomaly = payload.anomaly
    item.dismount_anomaly_resolved = False

    purpose = f"撤展归库:{ex.title}"
    if item.change_order_id:
        purpose += f"(变更单 #{item.change_order_id})"
    db.add(
        models.Movement(
            collection_id=c.id,
            move_type=models.MOVE_RETURN,
            to_location_id=payload.return_location_id,
            purpose=purpose,
            operator=payload.acceptor,
            move_date=now,
            remark=_acceptance_remark(payload.photo_note, payload.anomaly),
        )
    )
    if payload.return_location_id and db.get(models.Location, payload.return_location_id):
        c.location_id = payload.return_location_id
        c.status = models.STATUS_IN_STORAGE
    else:
        c.status = models.STATUS_OUT_STORAGE
    db.commit()
    db.refresh(ex)
    return _serialize(db, ex)


@router.post(
    "/{exhibition_id}/items/{item_id}/resolve-anomaly",
    response_model=schemas.ExhibitionOut,
)
def resolve_item_anomaly(
    exhibition_id: int,
    item_id: int,
    payload: schemas.AnomalyResolve,
    phase: str = Query(..., pattern="^(mount|dismount)$"),
    db: Session = Depends(get_db),
):
    """闭环布展/撤展异常项(异常本身保留,仅标记处理结果与处理人)。"""
    ex = _get_exhibition(db, exhibition_id)
    item = db.get(models.ExhibitionItem, item_id)
    if not item or item.exhibition_id != exhibition_id:
        raise HTTPException(404, "清单条目不存在")
    now = datetime.utcnow()
    if phase == "mount":
        if not item.mount_anomaly:
            raise HTTPException(400, "该条目没有未处理的布展异常")
        if item.mount_anomaly_resolved:
            raise HTTPException(400, "布展异常已闭环")
        item.mount_anomaly_resolved = True
        item.mount_anomaly_resolved_at = now
        item.mount_anomaly_resolved_by = payload.resolved_by
        if payload.note:
            item.mount_anomaly = f"{item.mount_anomaly}\n【闭环 {payload.resolved_by}】{payload.note}"
    else:
        if not item.dismount_anomaly:
            raise HTTPException(400, "该条目没有未处理的撤展异常")
        if item.dismount_anomaly_resolved:
            raise HTTPException(400, "撤展异常已闭环")
        item.dismount_anomaly_resolved = True
        item.dismount_anomaly_resolved_at = now
        item.dismount_anomaly_resolved_by = payload.resolved_by
        if payload.note:
            item.dismount_anomaly = (
                f"{item.dismount_anomaly}\n【闭环 {payload.resolved_by}】{payload.note}"
            )
    db.commit()
    db.refresh(ex)
    return _serialize(db, ex)


# ---------- 变更单 ----------
@router.post("/{exhibition_id}/change-orders", response_model=schemas.ExhibitionOut)
def create_change_order(
    exhibition_id: int, payload: schemas.ChangeOrderCreate, db: Session = Depends(get_db)
):
    """清单冻结后的增删/替换展品申请(开展中替换展品同样走此审批流)。"""
    ex = _get_exhibition(db, exhibition_id)
    status = _effective_status(ex)
    if status == models.EX_STATUS_CLOSED:
        raise HTTPException(400, "展览已结束,不再受理展品变更")
    if not ex.frozen and status != models.EX_STATUS_OPEN:
        raise HTTPException(400, "清单尚未冻结:筹备阶段可直接增删展品,无需变更单")
    # 开展中:无论清单是否走过冻结动作,增删/替换一律凭审批变更单办理
    if payload.change_type not in (models.CO_ADD, models.CO_REMOVE, models.CO_REPLACE):
        raise HTTPException(400, "变更类型必须是 新增 / 撤除 / 替换")

    pending_q = db.query(models.ChangeOrder).filter(
        models.ChangeOrder.exhibition_id == exhibition_id,
        models.ChangeOrder.status == models.CO_PENDING,
    )

    add_coll = None
    remove_item = None
    if payload.change_type in (models.CO_ADD, models.CO_REPLACE):
        if not payload.add_collection_id:
            raise HTTPException(400, "请填写新增/替换进来的藏品")
        add_coll = db.get(models.Collection, payload.add_collection_id)
        if not add_coll:
            raise HTTPException(404, "新增藏品不存在")
        if _active_item(db, exhibition_id, add_coll.id):
            raise HTTPException(400, "该藏品已在本展览清单中")
        dup = pending_q.filter(models.ChangeOrder.add_collection_id == add_coll.id).first()
        if dup:
            raise HTTPException(400, f"该藏品已有待审批变更单(# {dup.id}),请勿重复申请")
        if add_coll.status != models.STATUS_IN_STORAGE:
            raise HTTPException(
                400, f"新增藏品当前为「{add_coll.status}」状态,无法参展"
            )
    if payload.change_type in (models.CO_REMOVE, models.CO_REPLACE):
        if not payload.remove_item_id:
            raise HTTPException(400, "请选择要撤除/替换的原展品条目")
        remove_item = db.get(models.ExhibitionItem, payload.remove_item_id)
        if not remove_item or remove_item.exhibition_id != exhibition_id:
            raise HTTPException(404, "原展品条目不存在")
        if remove_item.status not in (models.ITEM_PLANNED, models.ITEM_MOUNTED):
            raise HTTPException(400, "原展品已撤展,无需再申请撤除")
        dup = pending_q.filter(models.ChangeOrder.remove_item_id == remove_item.id).first()
        if dup:
            raise HTTPException(400, f"该展品已有待审批变更单(# {dup.id}),请勿重复申请")
        if (
            payload.change_type == models.CO_REPLACE
            and add_coll.id == remove_item.collection_id
        ):
            raise HTTPException(400, "替换进来的藏品不能与原展品相同")

    co = models.ChangeOrder(
        exhibition_id=exhibition_id,
        change_type=payload.change_type,
        reason=payload.reason,
        display_location=payload.display_location,
        install_plan_note=payload.install_plan_note,
        planned_mount_date=payload.planned_mount_date,
        add_collection_id=payload.add_collection_id,
        remove_item_id=payload.remove_item_id,
        requested_by=payload.requested_by,
        status=models.CO_PENDING,
    )
    db.add(co)
    db.commit()
    db.refresh(ex)
    return _serialize(db, ex)


def _execute_change_order(db: Session, ex: models.Exhibition, co: models.ChangeOrder) -> None:
    """批准后立即调整冻结清单;现场布展/撤展仍须分别做验收登记。"""
    # 新增条目(新增 / 替换)
    if co.add_collection_id:
        add_coll = db.get(models.Collection, co.add_collection_id)
        if not add_coll or add_coll.status != models.STATUS_IN_STORAGE:
            raise HTTPException(
                400,
                "新增藏品当前不在库(可能已被调拨/送修/借出),无法执行变更单",
            )
        if _active_item(db, ex.id, add_coll.id):
            raise HTTPException(400, "新增藏品已在本展览清单中,变更单无法重复执行")
        db.add(
            models.ExhibitionItem(
                exhibition_id=ex.id,
                collection_id=add_coll.id,
                display_location=co.display_location,
                install_plan_note=co.install_plan_note,
                planned_mount_date=co.planned_mount_date,
                status=models.ITEM_PLANNED,
                change_order_id=co.id,
            )
        )

    # 撤除原条目(撤除 / 替换)
    if co.remove_item_id:
        old = db.get(models.ExhibitionItem, co.remove_item_id)
        if old and old.status in (models.ITEM_PLANNED, models.ITEM_MOUNTED):
            old_coll = db.get(models.Collection, old.collection_id)
            if old_coll:
                label = f"{old_coll.accession_no} {old_coll.name}"
                if old.display_location:
                    label += f"(原展位 {old.display_location})"
                co.remove_item_label = label
            if old.status == models.ITEM_PLANNED:
                # 尚未进场:从清单移出(保留行记录用于审计追溯)
                old.status = models.ITEM_REMOVED
                old.change_order_id = co.id
            else:
                # 已在展:保留条目等待撤展验收,记录其撤展依据
                old.change_order_id = co.id

    co.status = models.CO_EXECUTED
    co.executed_at = datetime.utcnow()


@router.post(
    "/{exhibition_id}/change-orders/{co_id}/approve",
    response_model=schemas.ExhibitionOut,
)
def approve_change_order(
    exhibition_id: int,
    co_id: int,
    payload: schemas.ChangeOrderApprove,
    db: Session = Depends(get_db),
):
    ex = _get_exhibition(db, exhibition_id)
    co = db.get(models.ChangeOrder, co_id)
    if not co or co.exhibition_id != exhibition_id:
        raise HTTPException(404, "变更单不存在")
    if co.status != models.CO_PENDING:
        raise HTTPException(400, f"变更单已「{co.status}」,不能重复审批")
    co.approved_by = payload.approved_by
    co.approval_note = payload.approval_note
    co.approved_at = datetime.utcnow()
    _execute_change_order(db, ex, co)
    db.commit()
    db.refresh(ex)
    return _serialize(db, ex)


@router.post(
    "/{exhibition_id}/change-orders/{co_id}/reject",
    response_model=schemas.ExhibitionOut,
)
def reject_change_order(
    exhibition_id: int,
    co_id: int,
    payload: schemas.ChangeOrderReject,
    db: Session = Depends(get_db),
):
    ex = _get_exhibition(db, exhibition_id)
    co = db.get(models.ChangeOrder, co_id)
    if not co or co.exhibition_id != exhibition_id:
        raise HTTPException(404, "变更单不存在")
    if co.status != models.CO_PENDING:
        raise HTTPException(400, f"变更单已「{co.status}」,不能重复审批")
    co.status = models.CO_REJECTED
    co.approved_by = payload.approved_by
    co.approval_note = payload.approval_note
    co.approved_at = datetime.utcnow()
    db.commit()
    db.refresh(ex)
    return _serialize(db, ex)
