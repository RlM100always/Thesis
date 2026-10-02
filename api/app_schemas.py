"""Schemas for the operational application API."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class UserView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    email: str
    display_name: str
    phone: str | None = None
    avatar_data_url: str | None = None
    mfa_enabled: bool = False
    is_platform_admin: bool = False


class OrganizationCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=80)
    sector: str = Field(default="retail", max_length=40)
    size_class: str | None = Field(default=None, max_length=20)
    default_branch_name: str = Field(default="প্রধান শাখা", min_length=2, max_length=120)


class OrganizationView(BaseModel):
    id: str
    name: str
    slug: str
    sector: str
    size_class: str | None
    currency: str
    timezone: str
    locale: str
    role: str
    # True once any product tracks batches/expiry, so the screens for it appear even
    # in a business type that does not use them by default.
    uses_expiry: bool = False
    address: str | None = None
    phone: str | None = None
    # Platform-admin module toggles (api/platform_routes.py FEATURE_FLAGS).
    # A key absent from this dict means "enabled" -- see Organization model.
    feature_flags: dict[str, bool] = {}
    vat_reg_no: str | None = None
    receipt_footer: str | None = None
    business_mode: str = "products"
    payment_methods: list[str] = Field(default_factory=lambda: ["cash"])
    sales_channels: list[str] = Field(default_factory=lambda: ["in_store"])
    reorder_budget_bdt: Decimal | None = None


class OrganizationProfile(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    sector: str | None = Field(default=None, max_length=40)
    address: str | None = Field(default=None, max_length=300)
    phone: str | None = Field(default=None, max_length=30)
    vat_reg_no: str | None = Field(default=None, max_length=40)
    receipt_footer: str | None = Field(default=None, max_length=200)


class OrganizationOperations(BaseModel):
    business_mode: str = Field(pattern=r"^(products|services|both)$")
    payment_methods: list[str] = Field(min_length=1, max_length=8)
    sales_channels: list[str] = Field(min_length=1, max_length=8)
    # None = leave the reorder budget as-is; the live B-SMART engine treats an
    # organization that never set one as genuinely unconstrained, not zero.
    reorder_budget_bdt: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)

    @model_validator(mode="after")
    def validate_choices(self):
        payments = {"cash", "bkash", "nagad", "bank", "card", "bangla_qr", "cod", "other"}
        channels = {"in_store", "phone", "whatsapp", "facebook", "website", "delivery"}
        if len(self.payment_methods) != len(set(self.payment_methods)) or not set(self.payment_methods) <= payments:
            raise ValueError("Unknown or duplicate payment method")
        if len(self.sales_channels) != len(set(self.sales_channels)) or not set(self.sales_channels) <= channels:
            raise ValueError("Unknown or duplicate sales channel")
        return self


class ProductCreate(BaseModel):
    sku: str = Field(min_length=1, max_length=80)
    barcode: str | None = Field(default=None, max_length=80)
    name: str = Field(min_length=1, max_length=200)
    category: str | None = Field(default=None, max_length=100)
    unit: str = Field(default="pcs", min_length=1, max_length=20)
    selling_price: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    cost_price: Decimal = Field(default=Decimal("0"), ge=0, max_digits=14, decimal_places=2)
    reorder_level: Decimal = Field(default=Decimal("0"), ge=0, max_digits=14, decimal_places=3)
    wholesale_price: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    track_expiry: bool = False


class ProductUpdate(BaseModel):
    """Fields the owner may change later. The SKU and expiry tracking are fixed once stock exists."""
    name: str | None = Field(default=None, min_length=1, max_length=200)
    barcode: str | None = Field(default=None, max_length=80)
    category: str | None = Field(default=None, max_length=100)
    unit: str | None = Field(default=None, min_length=1, max_length=20)
    selling_price: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    cost_price: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    wholesale_price: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    reorder_level: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=3)
    active: bool | None = None


class ProductView(ProductCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str
    active: bool


class StockAdjustment(BaseModel):
    branch_id: str
    product_id: str
    quantity_delta: Decimal = Field(max_digits=14, decimal_places=3)
    reason: str = Field(min_length=2, max_length=120)
    # Only for products that track expiry: which batch is being adjusted, or the
    # details of a new batch when adding stock.
    batch_id: str | None = None
    batch_no: str | None = Field(default=None, min_length=1, max_length=80)
    expiry_date: date | None = None

    @model_validator(mode="after")
    def non_zero(self):
        if self.quantity_delta == 0:
            raise ValueError("quantity_delta must not be zero")
        return self


class InventoryView(BaseModel):
    branch_id: str
    product_id: str
    sku: str
    product_name: str
    quantity: Decimal
    reorder_level: Decimal
    low_stock: bool


class SaleItemCreate(BaseModel):
    product_id: str
    quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=3)
    unit_price: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    discount_amount: Decimal = Field(default=Decimal("0"), ge=0, max_digits=14, decimal_places=2)


class SalePaymentCreate(BaseModel):
    method: str = Field(pattern=r"^(cash|bkash|nagad|bank|card|bangla_qr|cod|other)$")
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    reference: str | None = Field(default=None, max_length=120)


class SaleCreate(BaseModel):
    client_operation_id: str | None = Field(default=None, min_length=8, max_length=100)
    branch_id: str
    invoice_number: str = Field(min_length=1, max_length=80)
    customer_id: str | None = None
    sold_at: datetime
    channel: str = Field(default="in_store", max_length=30)
    tax_amount: Decimal = Field(default=Decimal("0"), ge=0, max_digits=14, decimal_places=2)
    items: list[SaleItemCreate] = Field(min_length=1, max_length=200)
    payments: list[SalePaymentCreate] = Field(default_factory=list, max_length=10)
    # A discount at or above the shop's threshold needs a qualifying manager's
    # credentials entered inline (a POS sale cannot sit in an async approval
    # queue the way an expense can) — see api/commerce_routes.py::create_sale.
    override_email: str | None = Field(default=None, max_length=255)
    override_password: str | None = Field(default=None, max_length=200)
    # Loyalty points this customer wants to spend on this bill; 0 if none or the
    # shop has loyalty off. See api/loyalty.py.
    redeem_points: Decimal = Field(default=Decimal("0"), ge=0, max_digits=14, decimal_places=3)

    @model_validator(mode="after")
    def unique_products(self):
        ids = [item.product_id for item in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("Duplicate product lines must be combined")
        return self


class SaleView(BaseModel):
    id: str
    invoice_number: str
    subtotal: Decimal
    discount_amount: Decimal
    tax_amount: Decimal
    total: Decimal
    paid: Decimal
    due: Decimal
    status: str


class SaleLineView(BaseModel):
    id: str
    product_id: str
    sku: str
    product_name: str
    quantity: Decimal
    returned_quantity: Decimal
    unit_price: Decimal
    line_total: Decimal


class SaleDetailView(SaleView):
    branch_id: str
    customer_id: str | None
    sold_at: datetime
    channel: str
    items: list[SaleLineView]


class SalesDocumentCreate(BaseModel):
    document_type: str = Field(pattern=r"^(quotation|order)$")
    document_number: str = Field(min_length=1, max_length=80)
    branch_id: str
    customer_id: str | None = None
    channel: str = Field(default="in_store", max_length=30)
    issued_at: datetime
    valid_until: date | None = None
    expected_delivery_at: datetime | None = None
    notes: str | None = Field(default=None, max_length=1000)
    tax_amount: Decimal = Field(default=Decimal("0"), ge=0, max_digits=14, decimal_places=2)
    items: list[SaleItemCreate] = Field(min_length=1, max_length=200)


class SalesDocumentInvoice(BaseModel):
    invoice_number: str = Field(min_length=1, max_length=80)
    sold_at: datetime
    payments: list[SalePaymentCreate] = Field(default_factory=list, max_length=10)


class PublicOrderItem(BaseModel):
    product_id: str
    quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=3)


class PublicOrderCreate(BaseModel):
    """What an anonymous online buyer submits at checkout.

    No price, discount, or customer tier is accepted from the client — every
    line is priced server-side off the product's current selling price, the
    same way a walk-in sale is, so a tampered request body can never change
    what the shop is paid.
    """

    branch_id: str | None = None
    shipping_name: str = Field(min_length=1, max_length=160)
    shipping_phone: str = Field(min_length=4, max_length=32)
    shipping_address: str = Field(min_length=1, max_length=1000)
    notes: str | None = Field(default=None, max_length=1000)
    items: list[PublicOrderItem] = Field(min_length=1, max_length=50)


class BranchCreate(BaseModel):
    code: str = Field(min_length=1, max_length=30)
    name: str = Field(min_length=2, max_length=120)
    division: str | None = Field(default=None, max_length=30)
    district: str | None = Field(default=None, max_length=50)
    address: str | None = Field(default=None, max_length=500)


class BranchView(BranchCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str
    active: bool


class WarehouseCreate(BaseModel):
    branch_id: str
    code: str = Field(min_length=1, max_length=30)
    name: str = Field(min_length=2, max_length=120)
    is_default: bool = False


class WarehouseView(WarehouseCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str
    organization_id: str
    active: bool


class StaffBranchesIn(BaseModel):
    branch_ids: list[str] = Field(default_factory=list)


class StaffInvite(BaseModel):
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$", max_length=254)
    display_name: str = Field(min_length=2, max_length=120)
    role: str = Field(
        pattern=r"^(owner|manager|cashier|accountant|stock_keeper|viewer|evaluator)$"
    )


class StaffView(BaseModel):
    membership_id: str
    user_id: str
    email: str
    display_name: str
    role: str
    active: bool
    # True until the person has set a password from their invite link.
    pending_setup: bool = False
    # Empty means org-wide access (SRD 2.3 ABAC default); non-empty narrows
    # this membership to only these branches.
    assigned_branch_ids: list[str] = Field(default_factory=list)


class StaffInvited(StaffView):
    """Returned once, to the owner, when a setup link is issued."""
    setup_token: str | None = None
    setup_expires_at: datetime | None = None


class StaffUpdate(BaseModel):
    role: str | None = Field(
        default=None,
        pattern=r"^(owner|manager|cashier|accountant|stock_keeper|viewer|evaluator)$",
    )
    active: bool | None = None


class CustomerCreate(BaseModel):
    code: str = Field(min_length=1, max_length=80)
    display_name: str | None = Field(default=None, max_length=160)
    phone: str | None = Field(default=None, pattern=r"^\+?\d{10,15}$")
    marketing_consent: bool = False
    credit_limit: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    price_tier: str = Field(default="retail", pattern=r"^(retail|wholesale)$")


class CustomerUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=160)
    phone: str | None = Field(default=None, pattern=r"^\+?\d{10,15}$")
    marketing_consent: bool | None = None
    credit_limit: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    price_tier: str | None = Field(default=None, pattern=r"^(retail|wholesale)$")


class CustomerView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    code: str
    display_name: str | None
    marketing_consent: bool
    credit_limit: Decimal | None = None
    price_tier: str = "retail"
    # What the customer owes now (receivable ledger); filled by the list endpoint.
    balance: Decimal = Decimal("0")


class SupplierCreate(BaseModel):
    code: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=2, max_length=160)
    typical_lead_days: int = Field(default=0, ge=0, le=365)


class SupplierView(SupplierCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str


class TicketCreate(BaseModel):
    subject: str = Field(min_length=2, max_length=200)
    category: str = Field(default="general", max_length=40)
    priority: str = Field(default="normal", pattern=r"^(low|normal|high|urgent)$")
    branch_id: str | None = None
    customer_id: str | None = None


class TicketUpdate(BaseModel):
    status: str | None = Field(default=None, pattern=r"^(open|pending|resolved|closed)$")
    priority: str | None = Field(default=None, pattern=r"^(low|normal|high|urgent)$")
    assigned_to_user_id: str | None = None


class TicketMessageCreate(BaseModel):
    body: str = Field(min_length=1, max_length=4000)
    internal: bool = False


class TicketMessageView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    author_user_id: str
    body: str
    internal: bool
    created_at: datetime


class TeamMessageCreate(BaseModel):
    body: str = Field(min_length=1, max_length=2000)
    branch_id: str | None = None


class TeamMessageView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    user_id: str
    author_name: str
    branch_id: str | None
    body: str
    created_at: datetime


class TicketView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    subject: str
    category: str
    priority: str
    status: str
    branch_id: str | None
    customer_id: str | None
    created_by_user_id: str
    assigned_to_user_id: str | None
    created_at: datetime
    resolved_at: datetime | None


class LeadCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    phone: str | None = Field(default=None, max_length=30)
    source: str | None = Field(default=None, max_length=60)
    estimated_value: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    owner_user_id: str | None = None


class LeadUpdate(BaseModel):
    stage: str | None = Field(default=None, pattern=r"^(new|qualified|quoted|won|lost)$")
    estimated_value: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    owner_user_id: str | None = None
    lost_reason: str | None = Field(default=None, max_length=200)


class LeadActivityCreate(BaseModel):
    note: str = Field(min_length=1, max_length=2000)


class LeadActivityView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    author_user_id: str
    note: str
    created_at: datetime


class LeadView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    source: str | None
    stage: str
    estimated_value: Decimal | None
    owner_user_id: str | None
    lost_reason: str | None
    converted_customer_id: str | None
    created_at: datetime
    closed_at: datetime | None


class FeedbackCreate(BaseModel):
    score: int = Field(ge=0, le=10)
    comment: str | None = Field(default=None, max_length=2000)
    customer_id: str | None = None
    sales_order_id: str | None = None


class FeedbackView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    score: int
    comment: str | None
    customer_id: str | None
    sales_order_id: str | None
    follow_up_ticket_id: str | None
    created_at: datetime


class NotificationView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    category: str
    severity: str
    title: str
    body: str | None
    link_type: str | None
    link_id: str | None
    read_at: datetime | None
    snoozed_until: datetime | None
    created_at: datetime


class AttendanceCheckIn(BaseModel):
    branch_id: str | None = None
    note: str | None = Field(default=None, max_length=300)


class AttendanceCorrection(BaseModel):
    user_id: str
    branch_id: str | None = None
    check_in_at: datetime
    check_out_at: datetime | None = None
    note: str = Field(min_length=1, max_length=300)


class AttendanceView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    user_id: str
    branch_id: str | None
    check_in_at: datetime
    check_out_at: datetime | None
    source: str
    corrects_record_id: str | None
    note: str | None


class LeaveRequestCreate(BaseModel):
    leave_type: str = Field(default="casual", max_length=30)
    start_date: date
    end_date: date
    reason: str | None = Field(default=None, max_length=300)

    @model_validator(mode="after")
    def _dates_make_sense(self):
        if self.end_date < self.start_date:
            raise ValueError("end_date must be on or after start_date")
        return self


class LeaveDecision(BaseModel):
    status: str = Field(pattern=r"^(approved|rejected)$")
    reason: str | None = Field(default=None, max_length=300)


class LeaveRequestView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    user_id: str
    leave_type: str
    start_date: date
    end_date: date
    reason: str | None
    status: str
    decided_by_user_id: str | None
    decided_at: datetime | None
    decision_reason: str | None


class RosterShiftCreate(BaseModel):
    user_id: str
    branch_id: str
    shift_date: date
    start_time: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    end_time: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    station: str | None = Field(default=None, max_length=60)

    @model_validator(mode="after")
    def _end_after_start(self):
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class RosterShiftView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    user_id: str
    branch_id: str
    shift_date: date
    start_time: str
    end_time: str
    station: str | None


class CommissionRuleUpdate(BaseModel):
    rate_percent: Decimal | None = Field(default=None, ge=0, le=100, max_digits=5, decimal_places=2)
    active: bool | None = None


class CommissionEntryView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    sales_order_id: str
    amount: Decimal
    reason: str
    occurred_at: datetime


class SalesTargetCreate(BaseModel):
    user_id: str
    period_start: date
    period_end: date
    target_amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)

    @model_validator(mode="after")
    def _period_makes_sense(self):
        if self.period_end < self.period_start:
            raise ValueError("period_end must be on or after period_start")
        return self


class SalesTargetUpdate(BaseModel):
    target_amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)


class SalesTargetView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    user_id: str
    period_start: date
    period_end: date
    target_amount: Decimal


class DeliveryCreate(BaseModel):
    sales_order_id: str
    rider_user_id: str
    cod_amount_expected: Decimal = Field(default=Decimal("0"), ge=0, max_digits=14, decimal_places=2)


class DeliveryComplete(BaseModel):
    status: str = Field(pattern=r"^(delivered|failed)$")
    cod_collected: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)
    proof_note: str | None = Field(default=None, max_length=300)
    failure_reason: str | None = Field(default=None, max_length=300)


class DeliveryView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    branch_id: str
    sales_order_id: str
    rider_user_id: str
    status: str
    cod_amount_expected: Decimal
    cod_amount_collected: Decimal | None
    proof_note: str | None
    failure_reason: str | None
    delivered_at: datetime | None


class CODHandoverCreate(BaseModel):
    shift_id: str
    handed_over_amount: Decimal = Field(ge=0, max_digits=14, decimal_places=2)


class CODHandoverView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    delivery_id: str
    shift_id: str
    handed_over_amount: Decimal
    shortage_amount: Decimal
    received_by_user_id: str


class StaffAdvanceCreate(BaseModel):
    user_id: str
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    reason: str | None = Field(default=None, max_length=300)


class StaffAdvanceRepay(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)


class StaffAdvanceView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    user_id: str
    amount: Decimal
    reason: str | None
    status: str
    issued_at: datetime


class PayrollRunCreate(BaseModel):
    period_start: date
    period_end: date

    @model_validator(mode="after")
    def _period_makes_sense(self):
        if self.period_end < self.period_start:
            raise ValueError("period_end must be on or after period_start")
        return self


class PayrollLineView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    user_id: str
    base_salary: Decimal
    commission_amount: Decimal
    advance_deduction: Decimal
    net_pay: Decimal


class PayrollRunView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    period_start: date
    period_end: date
    status: str
    approved_at: datetime | None
    paid_at: datetime | None


class MembershipSalaryUpdate(BaseModel):
    base_salary: Decimal | None = Field(default=None, ge=0, max_digits=14, decimal_places=2)


class ReservationCreate(BaseModel):
    sales_document_id: str
    hold_hours: int = Field(default=24, ge=1, le=720)


class ReservationView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    branch_id: str
    product_id: str
    sales_document_id: str
    quantity: Decimal
    status: str
    expires_at: datetime


class PurchaseItemCreate(BaseModel):
    product_id: str
    quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=3)
    unit_cost: Decimal = Field(ge=0, max_digits=14, decimal_places=2)


class PurchaseCreate(BaseModel):
    branch_id: str
    supplier_id: str
    order_number: str = Field(min_length=1, max_length=80)
    ordered_at: datetime
    expected_at: datetime | None = None
    items: list[PurchaseItemCreate] = Field(min_length=1, max_length=200)


class PurchaseView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    order_number: str
    status: str
    total: Decimal


class PurchaseLineView(BaseModel):
    id: str
    product_id: str
    sku: str
    product_name: str
    quantity: Decimal
    received_quantity: Decimal
    unit_cost: Decimal
    track_expiry: bool = False


class PurchaseDetailView(PurchaseView):
    branch_id: str
    supplier_id: str
    supplier_name: str
    ordered_at: datetime
    expected_at: datetime | None
    items: list[PurchaseLineView]


class ReceiveItem(BaseModel):
    purchase_order_item_id: str
    quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=3)
    # Required for products that track expiry; one entry per batch that arrived.
    batch_no: str | None = Field(default=None, min_length=1, max_length=80)
    expiry_date: date | None = None


class PurchaseReceive(BaseModel):
    received_at: datetime
    items: list[ReceiveItem] = Field(min_length=1, max_length=200)


class PurchaseReturnItemCreate(BaseModel):
    purchase_order_item_id: str
    quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=3)
    batch_id: str | None = None


class PurchaseReturnCreate(BaseModel):
    purchase_order_id: str
    return_number: str = Field(min_length=1, max_length=80)
    claim_type: str = Field(pattern=r"^(damaged|expired|wrong_item|quality|short_shipment|other)$")
    reason: str = Field(min_length=2, max_length=300)
    submitted_at: datetime
    items: list[PurchaseReturnItemCreate] = Field(min_length=1, max_length=200)


class PurchaseReturnLineView(BaseModel):
    id: str
    purchase_order_item_id: str
    product_id: str
    product_name: str
    sku: str
    batch_id: str | None
    batch_no: str | None
    quantity: Decimal
    unit_cost: Decimal
    amount: Decimal


class PurchaseReturnView(BaseModel):
    id: str
    purchase_order_id: str
    purchase_order_number: str
    supplier_id: str
    supplier_name: str
    branch_id: str
    return_number: str
    claim_type: str
    reason: str
    status: str
    total: Decimal
    submitted_at: datetime
    dispatched_at: datetime | None
    settled_at: datetime | None
    credit_note_number: str | None
    supplier_note: str | None
    items: list[PurchaseReturnLineView]


class PurchaseReturnDispatch(BaseModel):
    dispatched_at: datetime


class PurchaseReturnCreditNote(BaseModel):
    credit_note_number: str = Field(min_length=1, max_length=100)
    accepted_at: datetime
    supplier_note: str | None = Field(default=None, max_length=1000)


class PurchaseReturnReject(BaseModel):
    reason: str = Field(min_length=2, max_length=300)


class SettlementCreate(BaseModel):
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    payment_method: str = Field(min_length=2, max_length=30)
    occurred_at: datetime
    note: str | None = Field(default=None, max_length=500)


class ReturnItemCreate(BaseModel):
    sales_order_item_id: str
    quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=3)
    restock: bool = True


class ReturnCreate(BaseModel):
    return_number: str = Field(min_length=1, max_length=80)
    reason: str = Field(min_length=2, max_length=160)
    returned_at: datetime
    items: list[ReturnItemCreate] = Field(min_length=1, max_length=200)
    refund_method: str | None = Field(default=None, max_length=30)
    # A refund at or above the shop's threshold needs a qualifying manager's own
    # credentials, typed inline — see api/finance_routes.py::apply_return.
    override_email: str | None = Field(default=None, max_length=255)
    override_password: str | None = Field(default=None, max_length=200)


class ReturnView(BaseModel):
    id: str
    return_number: str
    total: Decimal
    refund_amount: Decimal


class ReturnHistoryView(BaseModel):
    id: str
    return_number: str
    invoice_number: str
    reason: str
    returned_at: datetime
    total: Decimal


class ExpenseCreate(BaseModel):
    branch_id: str | None = None
    category: str = Field(min_length=2, max_length=80)
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    payment_method: str = Field(min_length=2, max_length=30)
    note: str | None = Field(default=None, max_length=500)
    incurred_at: datetime


class ExpenseView(ExpenseCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str


class LedgerBalanceView(BaseModel):
    party_id: str | None
    balance: Decimal
