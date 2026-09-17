from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base

# 藏品状态
STATUS_IN_STORAGE = "在库"
STATUS_OUT_STORAGE = "出库中"
STATUS_EXHIBITION = "展陈中"
STATUS_RESTORATION = "修复中"
STATUS_LOAN_OUT = "借展中"

# 出入库 / 流转类型
MOVE_IN = "入库"
MOVE_OUT = "出库"
MOVE_TRANSFER = "移库"
MOVE_EXHIBIT = "布展"
MOVE_RETURN = "撤展归库"
MOVE_REPAIR_OUT = "修复出库"
MOVE_REPAIR_BACK = "修复归库"
MOVE_LOAN_OUT = "借展出库"
MOVE_LOAN_BACK = "借展归还"

# 温湿度告警级别
ALERT_NORMAL = "正常"
ALERT_WARNING = "预警"
ALERT_CRITICAL = "严重"

# 展览状态
EX_STATUS_PREP = "筹备中"
EX_STATUS_OPEN = "开展中"
EX_STATUS_CLOSED = "已结束"

# 展品条目状态(清单条目 + 现场安装状态)
ITEM_PLANNED = "待布展"
ITEM_MOUNTED = "已布展"
ITEM_DISMOUNTED = "已撤展"
ITEM_REMOVED = "已移出"

# 变更单类型 / 状态
CO_ADD = "新增"
CO_REMOVE = "撤除"
CO_REPLACE = "替换"
CO_PENDING = "待审批"
CO_APPROVED = "已批准"
CO_REJECTED = "已驳回"
CO_EXECUTED = "已执行"


class Location(Base):
    __tablename__ = "locations"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100))
    zone: Mapped[str] = mapped_column(String(50))  # 库区/楼层
    location_type: Mapped[str] = mapped_column(String(20), default="库房")  # 库房/展厅/修复室
    temp_min: Mapped[float] = mapped_column(Float, default=15.0)
    temp_max: Mapped[float] = mapped_column(Float, default=22.0)
    hum_min: Mapped[float] = mapped_column(Float, default=45.0)
    hum_max: Mapped[float] = mapped_column(Float, default=60.0)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    collections: Mapped[list["Collection"]] = relationship(back_populates="location")
    readings: Mapped[list["EnvReading"]] = relationship(
        back_populates="location", cascade="all, delete-orphan"
    )
    alerts: Mapped[list["EnvAlert"]] = relationship(
        back_populates="location", cascade="all, delete-orphan"
    )


class Collection(Base):
    __tablename__ = "collections"

    id: Mapped[int] = mapped_column(primary_key=True)
    accession_no: Mapped[str] = mapped_column(String(32), unique=True, index=True)  # 总登记号
    name: Mapped[str] = mapped_column(String(200))
    category: Mapped[str] = mapped_column(String(50))  # 陶瓷/书画/青铜器...
    dynasty: Mapped[str | None] = mapped_column(String(50), nullable=True)
    material: Mapped[str | None] = mapped_column(String(100), nullable=True)
    dimension: Mapped[str | None] = mapped_column(String(200), nullable=True)
    weight: Mapped[str | None] = mapped_column(String(50), nullable=True)
    grade: Mapped[str | None] = mapped_column(String(20), nullable=True)  # 一级/二级/三级
    source: Mapped[str | None] = mapped_column(String(100), nullable=True)  # 来源(征集/捐赠)
    acquired_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default=STATUS_IN_STORAGE, index=True)
    location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id"), nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(300), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    location: Mapped["Location"] = relationship(back_populates="collections")
    movements: Mapped[list["Movement"]] = relationship(
        back_populates="collection", cascade="all, delete-orphan"
    )
    exhibition_items: Mapped[list["ExhibitionItem"]] = relationship(
        back_populates="collection", cascade="all, delete-orphan"
    )
    restorations: Mapped[list["Restoration"]] = relationship(
        back_populates="collection", cascade="all, delete-orphan"
    )
    loans: Mapped[list["LoanRecord"]] = relationship(
        back_populates="collection", cascade="all, delete-orphan"
    )


class Movement(Base):
    """出入库 / 流转记录"""

    __tablename__ = "movements"

    id: Mapped[int] = mapped_column(primary_key=True)
    collection_id: Mapped[int] = mapped_column(ForeignKey("collections.id"), index=True)
    move_type: Mapped[str] = mapped_column(String(20), index=True)
    from_location_id: Mapped[int | None] = mapped_column(
        ForeignKey("locations.id"), nullable=True
    )
    to_location_id: Mapped[int | None] = mapped_column(ForeignKey("locations.id"), nullable=True)
    purpose: Mapped[str | None] = mapped_column(String(200), nullable=True)
    operator: Mapped[str | None] = mapped_column(String(50), nullable=True)
    handler: Mapped[str | None] = mapped_column(String(50), nullable=True)  # 经手人
    move_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)

    collection: Mapped["Collection"] = relationship(back_populates="movements")
    from_location: Mapped["Location | None"] = relationship(foreign_keys=[from_location_id])
    to_location: Mapped["Location | None"] = relationship(foreign_keys=[to_location_id])


class Exhibition(Base):
    __tablename__ = "exhibitions"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(200))
    venue: Mapped[str] = mapped_column(String(100))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="筹备中")  # 筹备中/开展中/已结束
    curator: Mapped[str | None] = mapped_column(String(50), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 展品清单冻结:筹备阶段可自由增删,冻结后只能通过变更单调整
    frozen: Mapped[bool] = mapped_column(Boolean, default=False)
    frozen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    frozen_by: Mapped[str | None] = mapped_column(String(50), nullable=True)

    items: Mapped[list["ExhibitionItem"]] = relationship(
        back_populates="exhibition", cascade="all, delete-orphan"
    )
    change_orders: Mapped[list["ChangeOrder"]] = relationship(
        back_populates="exhibition", cascade="all, delete-orphan"
    )


class ExhibitionItem(Base):
    """展品清单条目:展位/安装计划 + 布展、撤展现场验收记录"""

    __tablename__ = "exhibition_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    exhibition_id: Mapped[int] = mapped_column(ForeignKey("exhibitions.id"), index=True)
    collection_id: Mapped[int] = mapped_column(ForeignKey("collections.id"), index=True)
    display_location: Mapped[str | None] = mapped_column(String(100), nullable=True)
    install_plan_note: Mapped[str | None] = mapped_column(String(300), nullable=True)  # 安装计划
    planned_mount_date: Mapped[date | None] = mapped_column(Date, nullable=True)  # 计划布展日期
    status: Mapped[str] = mapped_column(String(20), default=ITEM_PLANNED)  # 待布展/已布展/已撤展

    # 布展现场验收
    mounted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    mount_acceptor: Mapped[str | None] = mapped_column(String(50), nullable=True)  # 现场验收人
    mount_photo_note: Mapped[str | None] = mapped_column(String(500), nullable=True)  # 照片说明
    mount_anomaly: Mapped[str | None] = mapped_column(Text, nullable=True)  # 布展异常项
    mount_anomaly_resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    mount_anomaly_resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    mount_anomaly_resolved_by: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # 撤展现场验收
    dismounted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    dismount_acceptor: Mapped[str | None] = mapped_column(String(50), nullable=True)
    dismount_photo_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    dismount_anomaly: Mapped[str | None] = mapped_column(Text, nullable=True)  # 撤展异常项
    dismount_anomaly_resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    dismount_anomaly_resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    dismount_anomaly_resolved_by: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # 关联来源变更单(经变更单批准加入清单时记录)
    change_order_id: Mapped[int | None] = mapped_column(
        ForeignKey("change_orders.id"), nullable=True
    )

    exhibition: Mapped["Exhibition"] = relationship(back_populates="items")
    collection: Mapped["Collection"] = relationship(back_populates="exhibition_items")
    change_order: Mapped["ChangeOrder | None"] = relationship(
        back_populates="items", foreign_keys=[change_order_id]
    )


class ChangeOrder(Base):
    """清单冻结后的展品变更单:新增 / 撤除 / 替换,须审批后执行"""

    __tablename__ = "change_orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    exhibition_id: Mapped[int] = mapped_column(ForeignKey("exhibitions.id"), index=True)
    change_type: Mapped[str] = mapped_column(String(10))  # 新增/撤除/替换
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)  # 变更事由
    display_location: Mapped[str | None] = mapped_column(String(100), nullable=True)  # 展位
    install_plan_note: Mapped[str | None] = mapped_column(String(300), nullable=True)  # 安装计划
    planned_mount_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(10), default=CO_PENDING, index=True)

    # 新增/替换的新展品
    add_collection_id: Mapped[int | None] = mapped_column(
        ForeignKey("collections.id"), nullable=True
    )
    # 撤除/替换的原展品条目
    remove_item_id: Mapped[int | None] = mapped_column(
        ForeignKey("exhibition_items.id"), nullable=True
    )
    # 快照:原条目在执行时可能被直接移出清单,保留名称便于审计追溯
    remove_item_label: Mapped[str | None] = mapped_column(String(200), nullable=True)

    requested_by: Mapped[str | None] = mapped_column(String(50), nullable=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    approved_by: Mapped[str | None] = mapped_column(String(50), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    approval_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    executed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    exhibition: Mapped["Exhibition"] = relationship(back_populates="change_orders")
    add_collection: Mapped["Collection | None"] = relationship(
        foreign_keys=[add_collection_id]
    )
    remove_item: Mapped["ExhibitionItem | None"] = relationship(
        foreign_keys=[remove_item_id]
    )
    items: Mapped[list["ExhibitionItem"]] = relationship(
        back_populates="change_order", foreign_keys="ExhibitionItem.change_order_id"
    )


class Restoration(Base):
    """修复过程记录"""

    __tablename__ = "restorations"

    id: Mapped[int] = mapped_column(primary_key=True)
    collection_id: Mapped[int] = mapped_column(ForeignKey("collections.id"), index=True)
    project_name: Mapped[str] = mapped_column(String(200))
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)  # 残损状况
    plan: Mapped[str | None] = mapped_column(Text, nullable=True)  # 修复方案
    restorer: Mapped[str | None] = mapped_column(String(50), nullable=True)
    start_date: Mapped[date] = mapped_column(Date, default=date.today)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="进行中")  # 进行中/已完成
    result: Mapped[str | None] = mapped_column(Text, nullable=True)  # 修复结果
    timeline: Mapped[list] = mapped_column(JSON, default=list)  # 过程节点 [{date,stage,note}]

    collection: Mapped["Collection"] = relationship(back_populates="restorations")


class LoanRecord(Base):
    """借展记录(出入馆借展)"""

    __tablename__ = "loan_records"

    id: Mapped[int] = mapped_column(primary_key=True)
    collection_id: Mapped[int] = mapped_column(ForeignKey("collections.id"), index=True)
    borrowing_institution: Mapped[str] = mapped_column(String(200))
    exhibition_title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    contact_person: Mapped[str | None] = mapped_column(String(50), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    loan_date: Mapped[date] = mapped_column(Date, default=date.today)
    due_date: Mapped[date] = mapped_column(Date, index=True)  # 应还日期
    return_date: Mapped[date | None] = mapped_column(Date, nullable=True)  # 实际归还
    status: Mapped[str] = mapped_column(String(20), default="借出", index=True)  # 借出/已归还/已逾期
    purpose: Mapped[str | None] = mapped_column(Text, nullable=True)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)

    collection: Mapped["Collection"] = relationship(back_populates="loans")


class EnvReading(Base):
    """环境温湿度采集记录"""

    __tablename__ = "env_readings"

    id: Mapped[int] = mapped_column(primary_key=True)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"), index=True)
    temperature: Mapped[float] = mapped_column(Float)
    humidity: Mapped[float] = mapped_column(Float)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    source: Mapped[str] = mapped_column(String(20), default="传感器")  # 传感器/人工/模拟

    location: Mapped["Location"] = relationship(back_populates="readings")


class EnvAlert(Base):
    """温湿度异常提醒"""

    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    location_id: Mapped[int] = mapped_column(ForeignKey("locations.id"), index=True)
    reading_id: Mapped[int | None] = mapped_column(ForeignKey("env_readings.id"), nullable=True)
    level: Mapped[str] = mapped_column(String(10), default=ALERT_WARNING)  # 预警/严重
    metric: Mapped[str] = mapped_column(String(10))  # temperature / humidity
    value: Mapped[float] = mapped_column(Float)
    threshold: Mapped[float] = mapped_column(Float)
    message: Mapped[str] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    acknowledged: Mapped[bool] = mapped_column(Boolean, default=False)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    acknowledged_by: Mapped[str | None] = mapped_column(String(50), nullable=True)

    location: Mapped["Location"] = relationship(back_populates="alerts")
