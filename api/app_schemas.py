"""Schemas for the operational application API."""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class UserView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    email: str
    display_name: str


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
    vat_reg_no: str | None = None
    receipt_footer: str | None = None


class OrganizationProfile(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    sector: str | None = Field(default=None, max_length=40)
    address: str | None = Field(default=None, max_length=300)
    phone: str | None = Field(default=None, max_length=30)
    vat_reg_no: str | None = Field(default=None, max_length=40)
    receipt_footer: str | None = Field(default=None, max_length=200)


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
