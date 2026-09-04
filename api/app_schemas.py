"""Schemas for the operational application API."""

from datetime import datetime
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


class ProductCreate(BaseModel):
    sku: str = Field(min_length=1, max_length=80)
    barcode: str | None = Field(default=None, max_length=80)
    name: str = Field(min_length=1, max_length=200)
    category: str | None = Field(default=None, max_length=100)
    unit: str = Field(default="pcs", min_length=1, max_length=20)
    selling_price: Decimal = Field(ge=0, max_digits=14, decimal_places=2)
    cost_price: Decimal = Field(default=Decimal("0"), ge=0, max_digits=14, decimal_places=2)
    reorder_level: Decimal = Field(default=Decimal("0"), ge=0, max_digits=14, decimal_places=3)


class ProductView(ProductCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str
    active: bool


class StockAdjustment(BaseModel):
    branch_id: str
    product_id: str
    quantity_delta: Decimal = Field(max_digits=14, decimal_places=3)
    reason: str = Field(min_length=2, max_length=120)

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
    role: str = Field(pattern=r"^(owner|manager|cashier|accountant|viewer)$")


class StaffView(BaseModel):
    membership_id: str
    user_id: str
    email: str
    display_name: str
    role: str
    active: bool


class CustomerCreate(BaseModel):
    code: str = Field(min_length=1, max_length=80)
    display_name: str | None = Field(default=None, max_length=160)
    phone: str | None = Field(default=None, pattern=r"^\+?\d{10,15}$")
    marketing_consent: bool = False


class CustomerView(BaseModel):
    id: str
    code: str
    display_name: str | None
    marketing_consent: bool


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
    id: str


class LedgerBalanceView(BaseModel):
    party_id: str | None
    balance: Decimal
