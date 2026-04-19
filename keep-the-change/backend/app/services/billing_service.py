"""
Billing and invoicing service for KEEPTHECHANGE.com

This service handles invoice generation, billing history, payment receipts, and financial reporting.
"""

import uuid
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
import logging
from dataclasses import dataclass
import json
from enum import Enum

logger = logging.getLogger(__name__)


class InvoiceStatus(str, Enum):
    """Invoice status enumeration"""
    DRAFT = "draft"
    OPEN = "open"
    PAID = "paid"
    VOID = "void"
    UNCOLLECTIBLE = "uncollectible"


class PaymentStatus(str, Enum):
    """Payment status enumeration"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"
    CANCELLED = "cancelled"


@dataclass
class Invoice:
    """Invoice definition"""
    invoice_id: str
    subscription_id: str
    user_id: str
    amount: float
    currency: str = "USD"
    status: InvoiceStatus = InvoiceStatus.DRAFT
    due_date: Optional[datetime] = None
    paid_date: Optional[datetime] = None
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    description: str = ""
    items: List[Dict[str, Any]] = None
    tax_amount: float = 0.0
    total_amount: float = 0.0
    metadata: Dict[str, Any] = None
    created_at: datetime = None
    updated_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.updated_at is None:
            self.updated_at = datetime.utcnow()
        if self.items is None:
            self.items = []
        if self.metadata is None:
            self.metadata = {}
        if self.total_amount == 0.0:
            self.total_amount = self.amount + self.tax_amount
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "invoice_id": self.invoice_id,
            "subscription_id": self.subscription_id,
            "user_id": self.user_id,
            "amount": self.amount,
            "currency": self.currency,
            "status": self.status.value,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "paid_date": self.paid_date.isoformat() if self.paid_date else None,
            "period_start": self.period_start.isoformat() if self.period_start else None,
            "period_end": self.period_end.isoformat() if self.period_end else None,
            "description": self.description,
            "items": self.items,
            "tax_amount": self.tax_amount,
            "total_amount": self.total_amount,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }


@dataclass
class PaymentReceipt:
    """Payment receipt definition"""
    receipt_id: str
    invoice_id: str
    user_id: str
    amount: float
    currency: str = "USD"
    payment_method: str = ""
    transaction_id: Optional[str] = None
    status: PaymentStatus = PaymentStatus.COMPLETED
    paid_at: datetime = None
    receipt_number: str = ""
    items: List[Dict[str, Any]] = None
    tax_amount: float = 0.0
    total_amount: float = 0.0
    metadata: Dict[str, Any] = None
    created_at: datetime = None
    
    def __post_init__(self):
        if self.paid_at is None:
            self.paid_at = datetime.utcnow()
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.items is None:
            self.items = []
        if self.metadata is None:
            self.metadata = {}
        if not self.receipt_number:
            self.receipt_number = f"RCPT-{self.paid_at.strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
        if self.total_amount == 0.0:
            self.total_amount = self.amount + self.tax_amount
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "receipt_id": self.receipt_id,
            "invoice_id": self.invoice_id,
            "user_id": self.user_id,
            "amount": self.amount,
            "currency": self.currency,
            "payment_method": self.payment_method,
            "transaction_id": self.transaction_id,
            "status": self.status.value,
            "paid_at": self.paid_at.isoformat(),
            "receipt_number": self.receipt_number,
            "items": self.items,
            "tax_amount": self.tax_amount,
            "total_amount": self.total_amount,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat()
        }


@dataclass
class BillingHistoryEntry:
    """Billing history entry"""
    entry_id: str
    user_id: str
    type: str  # invoice, payment, refund, adjustment
    amount: float
    currency: str = "USD"
    description: str = ""
    reference_id: Optional[str] = None  # invoice_id, receipt_id, etc.
    status: str = ""
    metadata: Dict[str, Any] = None
    created_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.metadata is None:
            self.metadata = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "entry_id": self.entry_id,
            "user_id": self.user_id,
            "type": self.type,
            "amount": self.amount,
            "currency": self.currency,
            "description": self.description,
            "reference_id": self.reference_id,
            "status": self.status,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat()
        }


class BillingService:
    """Billing and invoicing service"""
    
    def __init__(self, payment_service=None):
        self.payment_service = payment_service
        self.invoices: Dict[str, Invoice] = {}
        self.receipts: Dict[str, PaymentReceipt] = {}
        self.billing_history: Dict[str, List[BillingHistoryEntry]] = {}
    
    async def create_invoice(
        self,
        subscription_id: str,
        user_id: str,
        amount: float,
        currency: str = "USD",
        description: str = "",
        period_start: Optional[datetime] = None,
        period_end: Optional[datetime] = None,
        due_days: int = 7
    ) -> Tuple[bool, Optional[Invoice], str]:
        """Create a new invoice"""
        try:
            invoice_id = f"inv_{uuid.uuid4().hex[:16]}"
            now = datetime.utcnow()
            
            # Calculate due date
            due_date = now + timedelta(days=due_days)
            
            # Create invoice items
            items = [
                {
                    "item_id": f"item_{uuid.uuid4().hex[:8]}",
                    "description": description or "Subscription fee",
                    "quantity": 1,
                    "unit_price": amount,
                    "amount": amount,
                    "tax_rate": 0.0,
                    "tax_amount": 0.0
                }
            ]
            
            # Calculate tax (simplified - would use tax service in production)
            tax_amount = amount * 0.08  # 8% tax rate for example
            total_amount = amount + tax_amount
            
            invoice = Invoice(
                invoice_id=invoice_id,
                subscription_id=subscription_id,
                user_id=user_id,
                amount=amount,
                currency=currency,
                status=InvoiceStatus.OPEN,
                due_date=due_date,
                period_start=period_start,
                period_end=period_end,
                description=description,
                items=items,
                tax_amount=tax_amount,
                total_amount=total_amount
            )
            
            # Store invoice
            self.invoices[invoice_id] = invoice
            
            # Add to billing history
            await self._add_billing_history(
                user_id=user_id,
                entry_type="invoice",
                amount=total_amount,
                currency=currency,
                description=f"Invoice {invoice_id} created",
                reference_id=invoice_id,
                status="created"
            )
            
            logger.info(f"Created invoice {invoice_id} for user {user_id}, amount {total_amount} {currency}")
            return True, invoice, "Invoice created successfully"
            
        except Exception as e:
            logger.error(f"Error creating invoice: {str(e)}")
            return False, None, f"Error creating invoice: {str(e)}"
    
    async def get_invoice(self, invoice_id: str) -> Optional[Invoice]:
        """Get invoice by ID"""
        return self.invoices.get(invoice_id)
    
    async def get_user_invoices(
        self,
        user_id: str,
        status: Optional[InvoiceStatus] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Invoice]:
        """Get invoices for a user"""
        user_invoices = [
            invoice for invoice in self.invoices.values()
            if invoice.user_id == user_id
        ]
        
        if status:
            user_invoices = [inv for inv in user_invoices if inv.status == status]
        
        # Sort by created_at descending
        user_invoices.sort(key=lambda x: x.created_at, reverse=True)
        
        return user_invoices[offset:offset + limit]
    
    async def mark_invoice_paid(
        self,
        invoice_id: str,
        payment_method: str,
        transaction_id: Optional[str] = None
    ) -> Tuple[bool, Optional[PaymentReceipt], str]:
        """Mark an invoice as paid and generate receipt"""
        try:
            invoice = await self.get_invoice(invoice_id)
            if not invoice:
                return False, None, f"Invoice {invoice_id} not found"
            
            if invoice.status == InvoiceStatus.PAID:
                return False, None, f"Invoice {invoice_id} is already paid"
            
            if invoice.status == InvoiceStatus.VOID:
                return False, None, f"Invoice {invoice_id} is void"
            
            # Update invoice status
            invoice.status = InvoiceStatus.PAID
            invoice.paid_date = datetime.utcnow()
            invoice.updated_at = datetime.utcnow()
            
            # Generate receipt
            receipt_id = f"rcpt_{uuid.uuid4().hex[:16]}"
            receipt = PaymentReceipt(
                receipt_id=receipt_id,
                invoice_id=invoice_id,
                user_id=invoice.user_id,
                amount=invoice.amount,
                currency=invoice.currency,
                payment_method=payment_method,
                transaction_id=transaction_id,
                status=PaymentStatus.COMPLETED,
                items=invoice.items,
                tax_amount=invoice.tax_amount,
                total_amount=invoice.total_amount,
                metadata={
                    "subscription_id": invoice.subscription_id,
                    "invoice_description": invoice.description
                }
            )
            
            # Store receipt
            self.receipts[receipt_id] = receipt
            
            # Add to billing history
            await self._add_billing_history(
                user_id=invoice.user_id,
                entry_type="payment",
                amount=invoice.total_amount,
                currency=invoice.currency,
                description=f"Payment for invoice {invoice_id}",
                reference_id=receipt_id,
                status="completed"
            )
            
            logger.info(f"Marked invoice {invoice_id} as paid, generated receipt {receipt_id}")
            return True, receipt, "Invoice marked as paid successfully"
            
        except Exception as e:
            logger.error(f"Error marking invoice as paid: {str(e)}")
            return False, None, f"Error marking invoice as paid: {str(e)}"
    
    async def get_receipt(self, receipt_id: str) -> Optional[PaymentReceipt]:
        """Get receipt by ID"""
        return self.receipts.get(receipt_id)
    
    async def get_user_receipts(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0
    ) -> List[PaymentReceipt]:
        """Get receipts for a user"""
        user_receipts = [
            receipt for receipt in self.receipts.values()
            if receipt.user_id == user_id
        ]
        
        # Sort by paid_at descending
        user_receipts.sort(key=lambda x: x.paid_at, reverse=True)
        
        return user_receipts[offset:offset + limit]
    
    async def generate_invoice_pdf(self, invoice_id: str) -> Tuple[bool, Optional[bytes], str]:
        """Generate PDF for an invoice"""
        try:
            invoice = await self.get_invoice(invoice_id)
            if not invoice:
                return False, None, f"Invoice {invoice_id} not found"
            
            # In a real implementation, this would use a PDF generation library
            # For now, return a mock PDF
            pdf_content = f"""
            INVOICE #{invoice_id}
            Date: {invoice.created_at.strftime('%Y-%m-%d')}
            Due Date: {invoice.due_date.strftime('%Y-%m-%d') if invoice.due_date else 'N/A'}
            
            Bill To:
            User ID: {invoice.user_id}
            
            Description: {invoice.description}
            
            Items:
            {json.dumps(invoice.items, indent=2)}
            
            Subtotal: ${invoice.amount:.2f}
            Tax: ${invoice.tax_amount:.2f}
            Total: ${invoice.total_amount:.2f}
            
            Status: {invoice.status.value}
            """.encode('utf-8')
            
            return True, pdf_content, "PDF generated successfully"
            
        except Exception as e:
            logger.error(f"Error generating invoice PDF: {str(e)}")
            return False, None, f"Error generating invoice PDF: {str(e)}"
    
    async def generate_receipt_pdf(self, receipt_id: str) -> Tuple[bool, Optional[bytes], str]:
        """Generate PDF for a receipt"""
        try:
            receipt = await self.get_receipt(receipt_id)
            if not receipt:
                return False, None, f"Receipt {receipt_id} not found"
            
            # In a real implementation, this would use a PDF generation library
            # For now, return a mock PDF
            pdf_content = f"""
            RECEIPT #{receipt.receipt_number}
            Date: {receipt.paid_at.strftime('%Y-%m-%d %H:%M:%S')}
            
            Payment To:
            KEEPTHECHANGE.com
            
            Paid By:
            User ID: {receipt.user_id}
            
            Payment Method: {receipt.payment_method}
            Transaction ID: {receipt.transaction_id or 'N/A'}
            
            Items:
            {json.dumps(receipt.items, indent=2)}
            
            Subtotal: ${receipt.amount:.2f}
            Tax: ${receipt.tax_amount:.2f}
            Total: ${receipt.total_amount:.2f}
            
            Status: {receipt.status.value}
            
            Thank you for your business!
            """.encode('utf-8')
            
            return True, pdf_content, "PDF generated successfully"
            
        except Exception as e:
            logger.error(f"Error generating receipt PDF: {str(e)}")
            return False, None, f"Error generating receipt PDF: {str(e)}"
    
    async def get_billing_history(
        self,
        user_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        entry_type: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[BillingHistoryEntry]:
        """Get billing history for a user"""
        user_history = self.billing_history.get(user_id, [])
        
        # Filter by date range
        if start_date:
            user_history = [entry for entry in user_history if entry.created_at >= start_date]
        if end_date:
            user_history = [entry for entry in user_history if entry.created_at <= end_date]
        
        # Filter by type
        if entry_type:
            user_history = [entry for entry in user_history if entry.type == entry_type]
        
        # Sort by created_at descending
        user_history.sort(key=lambda x: x.created_at, reverse=True)
        
        return user_history[offset:offset + limit]
    
    async def _add_billing_history(
        self,
        user_id: str,
        entry_type: str,
        amount: float,
        currency: str,
        description: str,
        reference_id: Optional[str] = None,
        status: str = ""
    ) -> None:
        """Add entry to billing history"""
        entry_id = f"bh_{uuid.uuid4().hex[:16]}"
        entry = BillingHistoryEntry(
            entry_id=entry_id,
            user_id=user_id,
            type=entry_type,
            amount=amount,
            currency=currency,
            description=description,
            reference_id=reference_id,
            status=status
        )
        
        if user_id not in self.billing_history:
            self.billing_history[user_id] = []
        
        self.billing_history[user_id].append(entry)
    
    async def get_billing_summary(self, user_id: str) -> Dict[str, Any]:
        """Get billing summary for a user"""
        try:
            # Get user invoices
            invoices = await self.get_user_invoices(user_id)
            
            # Get user receipts
            receipts = await self.get_user_receipts(user_id)
            
            # Calculate totals
            total_invoiced = sum(inv.total_amount for inv in invoices)
            total_paid = sum(rcpt.total_amount for rcpt in receipts if rcpt.status == PaymentStatus.COMPLETED)
            total_outstanding = sum(
                inv.total_amount for inv in invoices 
                if inv.status in [InvoiceStatus.OPEN, InvoiceStatus.DRAFT]
            )
            
            # Get recent activity
            recent_history = await self.get_billing_history(user_id, limit=10)
            
            # Get upcoming invoices (due in next 7 days)
            now = datetime.utcnow()
            next_week = now + timedelta(days=7)
            upcoming_invoices = [
                inv for inv in invoices
                if inv.due_date and inv.status == InvoiceStatus.OPEN and inv.due_date <= next_week
            ]
            
            return {
                "user_id": user_id,
                "total_invoiced": total_invoiced,
                "total_paid": total_paid,
                "total_outstanding": total_outstanding,
                "invoice_count": len(invoices),
                "paid_invoice_count": len([inv for inv in invoices if inv.status == InvoiceStatus.PAID]),
                "outstanding_invoice_count": len([inv for inv in invoices if inv.status == InvoiceStatus.OPEN]),
                "receipt_count": len(receipts),
                "upcoming_invoices": [
                    {
                        "invoice_id": inv.invoice_id,
                        "amount": inv.total_amount,
                        "due_date": inv.due_date.isoformat() if inv.due_date else None,
                        "description": inv.description
                    }
                    for inv in upcoming_invoices
                ],
                "recent_activity": [
                    {
                        "type": entry.type,
                        "amount": entry.amount,
                        "description": entry.description,
                        "date": entry.created_at.isoformat(),
                        "status": entry.status
                    }
                    for entry in recent_history
                ]
            }
            
        except Exception as e:
            logger.error(f"Error getting billing summary: {str(e)}")
            return {
                "user_id": user_id,
                "error": str(e),
                "total_invoiced": 0,
                "total_paid": 0,
                "total_outstanding": 0,
                "invoice_count": 0,
                "paid_invoice_count": 0,
                "outstanding_invoice_count": 0,
                "receipt_count": 0,
                "upcoming_invoices": [],
                "recent_activity": []
            }
    
    async def process_recurring_billing(self) -> Dict[str, Any]:
        """Process recurring billing for all subscriptions"""
        try:
            logger.info("Processing recurring billing")
            
            # In a real implementation, this would:
            # 1. Fetch all subscriptions with billing due
            # 2. Create invoices for each
            # 3. Process payments
            # 4. Update subscription statuses
            
            result = {
                "subscriptions_processed": 0,
                "invoices_created": 0,
                "payments_processed": 0,
                "successful_payments": 0,
                "failed_payments": 0,
                "errors": []
            }
            
            # Simulate processing
            result["subscriptions_processed"] = 150
            result["invoices_created"] = 120
            result["payments_processed"] = 115
            result["successful_payments"] = 110
            result["failed_payments"] = 5
            
            logger.info(f"Recurring billing processed: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Error processing recurring billing: {str(e)}")
            return {
                "subscriptions_processed": 0,
                "invoices_created": 0,
                "payments_processed": 0,
                "successful_payments": 0,
                "failed_payments": 0,
                "errors": [str(e)]
            }


# Singleton instance
billing_service = BillingService()