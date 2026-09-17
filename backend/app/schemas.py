from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


# ---------- Location ----------
class LocationBase(BaseModel):
    code: str
    name: str
    zone: str
    location_type: str = "库房"
    temp_min: float = 15.0
    temp_max: float = 22.0
    hum_min: float = 45.0
    hum_max: float = 60.0
    description: str | None = None


class LocationCreate(LocationBase):
    pass


class LocationOut(LocationBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    collection_count: int = 0
    latest_temp: float | None = None
    latest_hum: float | None = None
    latest_reading_at: datetime | None = None
    active_alert_count: int = 0


# ---------- Collection ----------
class CollectionBase(BaseModel):
    accession_no: str
    name: str
    category: str
    dynasty: str | None = None
    material: str | None = None
    dimension: str | None = None
    weight: str | None = None
    grade: str | None = None
    source: str | None = None
    acquired_date: date | None = None
    location_id: int | None = None
    image_url: str | None = None
    description: str | None = None


class CollectionCreate(CollectionBase):
    pass


class CollectionUpdate(BaseModel):
    accession_no: str | None = None
    name: str | None = None
    category: str | None = None
    dynasty: str | None = None
    material: str | None = None
    dimension: str | None = None
    weight: str | None = None
    grade: str | None = None
    source: str | None = None
    acquired_date: date | None = None
    location_id: int | None = None
    image_url: str | None = None
    description: str | None = None


class CollectionList(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    accession_no: str
    name: str
    category: str
    dynasty: str | None
    grade: str | None
    status: str
    location_id: int | None
    image_url: str | None


class LocationBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    code: str
    name: str


class CollectionDetail(CollectionBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    status: str
    created_at: datetime
    location: LocationBrief | None = None


# ---------- Movement ----------
class MovementCreate(BaseModel):
    move_type: str
    to_location_id: int | None = None
    purpose: str | None = None
    operator: str | None = None
    handler: str | None = None
    move_date: datetime | None = None
    remark: str | None = None


class MovementOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    collection_id: int
    move_type: str
    from_location_id: int | None
    to_location_id: int | None
    from_location: LocationBrief | None
    to_location: LocationBrief | None
    purpose: str | None
    operator: str | None
    handler: str | None
    move_date: datetime
    remark: str | None
    collection_name: str | None = None
    accession_no: str | None = None


# ---------- Exhibition ----------
class ExhibitionBase(BaseModel):
    title: str
    venue: str
    start_date: date
    end_date: date
    curator: str | None = None
    description: str | None = None


class ExhibitionCreate(ExhibitionBase):
    pass


class ExhibitionItemPlanAdd(BaseModel):
    """筹备阶段把展品加入清单(仅登记展位与安装计划,不触发现场布展)"""

    collection_id: int
    display_location: str | None = None
    install_plan_note: str | None = None
    planned_mount_date: date | None = None


class ExhibitionFreeze(BaseModel):
    frozen_by: str | None = None


class ExhibitionItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    collection_id: int
    display_location: str | None
    install_plan_note: str | None
    planned_mount_date: date | None
    mounted_at: datetime | None
    dismounted_at: datetime | None
    status: str
    mount_acceptor: str | None
    mount_photo_note: str | None
    mount_anomaly: str | None
    mount_anomaly_resolved: bool
    mount_anomaly_resolved_at: datetime | None
    mount_anomaly_resolved_by: str | None
    dismount_acceptor: str | None
    dismount_photo_note: str | None
    dismount_anomaly: str | None
    dismount_anomaly_resolved: bool
    dismount_anomaly_resolved_at: datetime | None
    dismount_anomaly_resolved_by: str | None
    change_order_id: int | None
    collection_name: str | None = None
    accession_no: str | None = None
    has_open_anomaly: bool = False


class MountRequest(BaseModel):
    """布展现场验收"""

    acceptor: str
    photo_note: str | None = None
    anomaly: str | None = None
    mounted_at: datetime | None = None


class DismountRequest(BaseModel):
    """撤展现场验收"""

    acceptor: str
    photo_note: str | None = None
    anomaly: str | None = None
    return_location_id: int | None = None
    dismounted_at: datetime | None = None


class AnomalyResolve(BaseModel):
    resolved_by: str
    note: str | None = None


class ChangeOrderCreate(BaseModel):
    change_type: str  # 新增/撤除/替换
    reason: str | None = None
    add_collection_id: int | None = None
    remove_item_id: int | None = None
    display_location: str | None = None
    install_plan_note: str | None = None
    planned_mount_date: date | None = None
    requested_by: str | None = None


class ChangeOrderApprove(BaseModel):
    approved_by: str
    approval_note: str | None = None


class ChangeOrderReject(BaseModel):
    approved_by: str
    approval_note: str | None = None


class ChangeOrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    exhibition_id: int
    change_type: str
    reason: str | None
    display_location: str | None
    install_plan_note: str | None
    planned_mount_date: date | None
    status: str
    add_collection_id: int | None
    remove_item_id: int | None
    requested_by: str | None
    requested_at: datetime
    approved_by: str | None
    approved_at: datetime | None
    approval_note: str | None
    executed_at: datetime | None
    add_collection_label: str | None = None
    remove_item_label: str | None = None


class ExhibitionOut(ExhibitionBase):
    model_config = ConfigDict(from_attributes=True)
    id: int
    status: str
    frozen: bool
    frozen_at: datetime | None
    frozen_by: str | None
    items: list[ExhibitionItemOut] = []
    change_orders: list[ChangeOrderOut] = []
    open_anomaly_count: int = 0


# ---------- Restoration ----------
class RestorationCreate(BaseModel):
    collection_id: int
    project_name: str
    reason: str | None = None
    plan: str | None = None
    restorer: str | None = None
    start_date: date | None = None


class TimelineEntry(BaseModel):
    date: date
    stage: str
    note: str | None = None


class RestorationComplete(BaseModel):
    result: str | None = None
    end_date: date | None = None


class RestorationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    collection_id: int
    project_name: str
    reason: str | None
    plan: str | None
    restorer: str | None
    start_date: date
    end_date: date | None
    status: str
    result: str | None
    timeline: list[Any] = []
    collection_name: str | None = None
    accession_no: str | None = None


# ---------- Loan ----------
class LoanCreate(BaseModel):
    collection_id: int
    borrowing_institution: str
    exhibition_title: str | None = None
    contact_person: str | None = None
    contact_phone: str | None = None
    loan_date: date | None = None
    due_date: date
    purpose: str | None = None
    remark: str | None = None


class LoanReturn(BaseModel):
    return_date: date | None = None
    to_location_id: int | None = None


class LoanOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    collection_id: int
    borrowing_institution: str
    exhibition_title: str | None
    contact_person: str | None
    contact_phone: str | None
    loan_date: date
    due_date: date
    return_date: date | None
    status: str
    purpose: str | None
    remark: str | None
    collection_name: str | None = None
    accession_no: str | None = None
    days_remaining: int | None = None


# ---------- Environment ----------
class ReadingCreate(BaseModel):
    temperature: float
    humidity: float
    recorded_at: datetime | None = None
    source: str = "人工"


class ReadingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    location_id: int
    temperature: float
    humidity: float
    recorded_at: datetime
    source: str


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    location_id: int
    level: str
    metric: str
    value: float
    threshold: float
    message: str
    created_at: datetime
    acknowledged: bool
    acknowledged_at: datetime | None
    acknowledged_by: str | None
    location_name: str | None = None
    location_code: str | None = None


class SimRequest(BaseModel):
    inject_anomaly: bool = False
    anomaly_location_id: int | None = None


class DashboardOut(BaseModel):
    total_collections: int
    by_status: dict[str, int]
    by_category: list[dict[str, Any]]
    grade_stats: list[dict[str, Any]]
    active_alerts: int
    critical_alerts: int
    loans_active: int
    loans_overdue: int
    loans_due_soon: int
    exhibitions_active: int
    restorations_active: int
    env_status: list[dict[str, Any]]
