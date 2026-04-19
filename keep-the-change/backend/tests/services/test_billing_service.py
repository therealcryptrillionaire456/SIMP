"""
Tests for the billing service
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
import sys
import os

# Add the app directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../app'))

from services.billing_service import (
    BillingService,
    Invoice,
    PaymentReceipt,
    BillingHistoryEntry,
    InvoiceStatus,
    PaymentStatus
)


class TestBillingService:
    """Test suite for BillingService"""
    
    @pytest.fixture
    def billing_service(self):
        """Create a billing service instance for testing"""
        return BillingService()
    
    @pytest.fixture
    def mock_payment_service(self):
        """Create a mock payment service"""
        return AsyncMock()
    
    @pytest.fixture
    def sample_invoice_data(self):
        """Create sample invoice data for testing"""
        now = datetime.utcnow()
        return {
            "subscription_id": "sub_123",
            "user_id": "user_123",
            "amount": 49.99,
            "currency": "USD",
            "description": "Monthly subscription fee",
            "period_start": now - timedelta(days=30),
            "period_end": now,
            "due_days": 7
        }
    
    @pytest.fixture
    def sample_receipt_data(self):
        """Create sample receipt data for testing"""
        return {
            "invoice_id": "inv_123",
            "user_id": "user_123",
            "amount": 49.99,
            "currency": "USD",
            "payment_method": "credit_card",
            "transaction_id": "tx_123"
        }
    
    @pytest.mark.asyncio
    async def test_billing_service_initialization(self, billing_service):
        """Test billing service initialization"""
        assert billing_service is not None
        assert billing_service.payment_service is None
        assert billing_service.invoices == {}
        assert billing_service.receipts == {}
        assert billing_service.billing_history == {}
    
    @pytest.mark.asyncio
    async def test_create_invoice(self, billing_service, sample_invoice_data):
        """Test creating an invoice"""
        # Create invoice
        success, invoice, message = await billing_service.create_invoice(**sample_invoice_data)
        
        # Verify result
        assert success is True
        assert invoice is not None
        assert "successfully" in message.lower()
        
        # Verify invoice details
        assert invoice.subscription_id == "sub_123"
        assert invoice.user_id == "user_123"
        assert invoice.amount == 49.99
        assert invoice.currency == "USD"
        assert invoice.status == InvoiceStatus.OPEN
        assert invoice.description == "Monthly subscription fee"
        assert invoice.due_date is not None
        assert invoice.period_start is not None
        assert invoice.period_end is not None
        
        # Verify calculated fields
        assert invoice.tax_amount > 0  # Should have tax
        assert invoice.total_amount == invoice.amount + invoice.tax_amount
        
        # Verify items
        assert isinstance(invoice.items, list)
        assert len(invoice.items) == 1
        assert invoice.items[0]["description"] == "Monthly subscription fee"
        assert invoice.items[0]["amount"] == 49.99
        
        # Verify invoice is stored
        assert invoice.invoice_id in billing_service.invoices
        stored_invoice = billing_service.invoices[invoice.invoice_id]
        assert stored_invoice == invoice
        
        # Verify billing history entry
        assert invoice.user_id in billing_service.billing_history
        history_entries = billing_service.billing_history[invoice.user_id]
        assert len(history_entries) == 1
        assert history_entries[0].reference_id == invoice.invoice_id
        assert history_entries[0].type == "invoice"
    
    @pytest.mark.asyncio
    async def test_get_invoice(self, billing_service, sample_invoice_data):
        """Test getting an invoice by ID"""
        # Create an invoice first
        success, invoice, _ = await billing_service.create_invoice(**sample_invoice_data)
        invoice_id = invoice.invoice_id
        
        # Get the invoice
        retrieved_invoice = await billing_service.get_invoice(invoice_id)
        
        # Verify result
        assert retrieved_invoice is not None
        assert retrieved_invoice.invoice_id == invoice_id
        assert retrieved_invoice.user_id == "user_123"
        assert retrieved_invoice.amount == 49.99
        
        # Get non-existent invoice
        nonexistent_invoice = await billing_service.get_invoice("nonexistent")
        assert nonexistent_invoice is None
    
    @pytest.mark.asyncio
    async def test_get_user_invoices(self, billing_service, sample_invoice_data):
        """Test getting invoices for a user"""
        # Create multiple invoices for the same user
        for i in range(3):
            data = sample_invoice_data.copy()
            data["amount"] = 49.99 + i * 10
            data["description"] = f"Invoice {i+1}"
            await billing_service.create_invoice(**data)
        
        # Create invoice for different user
        other_user_data = sample_invoice_data.copy()
        other_user_data["user_id"] = "user_456"
        await billing_service.create_invoice(**other_user_data)
        
        # Get invoices for user_123
        user_invoices = await billing_service.get_user_invoices("user_123")
        
        # Verify result
        assert isinstance(user_invoices, list)
        assert len(user_invoices) == 3
        
        # Verify all invoices belong to user_123
        for invoice in user_invoices:
            assert invoice.user_id == "user_123"
        
        # Verify sorting (newest first)
        dates = [invoice.created_at for invoice in user_invoices]
        assert dates == sorted(dates, reverse=True)
    
    @pytest.mark.asyncio
    async def test_get_user_invoices_with_status_filter(self, billing_service, sample_invoice_data):
        """Test getting invoices for a user with status filter"""
        # Create invoices with different statuses
        data = sample_invoice_data.copy()
        
        # Create open invoice
        success, open_invoice, _ = await billing_service.create_invoice(**data)
        
        # Create paid invoice (by marking it as paid)
        data["amount"] = 59.99
        success, invoice_to_pay, _ = await billing_service.create_invoice(**data)
        await billing_service.mark_invoice_paid(
            invoice_to_pay.invoice_id,
            "credit_card",
            "tx_123"
        )
        
        # Get open invoices only
        open_invoices = await billing_service.get_user_invoices(
            "user_123",
            status=InvoiceStatus.OPEN
        )
        
        # Verify result
        assert len(open_invoices) == 1
        assert open_invoices[0].invoice_id == open_invoice.invoice_id
        assert open_invoices[0].status == InvoiceStatus.OPEN
        
        # Get paid invoices only
        paid_invoices = await billing_service.get_user_invoices(
            "user_123",
            status=InvoiceStatus.PAID
        )
        
        # Verify result
        assert len(paid_invoices) == 1
        assert paid_invoices[0].invoice_id == invoice_to_pay.invoice_id
        assert paid_invoices[0].status == InvoiceStatus.PAID
    
    @pytest.mark.asyncio
    async def test_mark_invoice_paid(self, billing_service, sample_invoice_data):
        """Test marking an invoice as paid"""
        # Create an invoice
        success, invoice, _ = await billing_service.create_invoice(**sample_invoice_data)
        invoice_id = invoice.invoice_id
        
        # Mark invoice as paid
        success, receipt, message = await billing_service.mark_invoice_paid(
            invoice_id=invoice_id,
            payment_method="credit_card",
            transaction_id="tx_123"
        )
        
        # Verify result
        assert success is True
        assert receipt is not None
        assert "successfully" in message.lower()
        
        # Verify receipt details
        assert receipt.invoice_id == invoice_id
        assert receipt.user_id == "user_123"
        assert receipt.amount == invoice.amount
        assert receipt.currency == "USD"
        assert receipt.payment_method == "credit_card"
        assert receipt.transaction_id == "tx_123"
        assert receipt.status == PaymentStatus.COMPLETED
        assert receipt.paid_at is not None
        assert receipt.receipt_number is not None
        
        # Verify receipt is stored
        assert receipt.receipt_id in billing_service.receipts
        stored_receipt = billing_service.receipts[receipt.receipt_id]
        assert stored_receipt == receipt
        
        # Verify invoice status is updated
        updated_invoice = await billing_service.get_invoice(invoice_id)
        assert updated_invoice.status == InvoiceStatus.PAID
        assert updated_invoice.paid_date is not None
        assert updated_invoice.updated_at >= invoice.updated_at
        
        # Verify billing history entry
        history_entries = billing_service.billing_history["user_123"]
        payment_entries = [entry for entry in history_entries if entry.type == "payment"]
        assert len(payment_entries) == 1
        assert payment_entries[0].reference_id == receipt.receipt_id
    
    @pytest.mark.asyncio
    async def test_mark_invoice_paid_nonexistent(self, billing_service):
        """Test marking non-existent invoice as paid"""
        # Mark non-existent invoice as paid
        success, receipt, message = await billing_service.mark_invoice_paid(
            invoice_id="nonexistent",
            payment_method="credit_card"
        )
        
        # Verify failure
        assert success is False
        assert receipt is None
        assert "not found" in message.lower()
    
    @pytest.mark.asyncio
    async def test_mark_invoice_paid_already_paid(self, billing_service, sample_invoice_data):
        """Test marking already paid invoice as paid"""
        # Create and pay an invoice
        success, invoice, _ = await billing_service.create_invoice(**sample_invoice_data)
        await billing_service.mark_invoice_paid(invoice.invoice_id, "credit_card")
        
        # Try to mark as paid again
        success, receipt, message = await billing_service.mark_invoice_paid(
            invoice_id=invoice.invoice_id,
            payment_method="credit_card"
        )
        
        # Verify failure
        assert success is False
        assert receipt is None
        assert "already paid" in message.lower()
    
    @pytest.mark.asyncio
    async def test_get_receipt(self, billing_service, sample_invoice_data):
        """Test getting a receipt by ID"""
        # Create and pay an invoice
        success, invoice, _ = await billing_service.create_invoice(**sample_invoice_data)
        success, receipt, _ = await billing_service.mark_invoice_paid(
            invoice.invoice_id,
            "credit_card",
            "tx_123"
        )
        receipt_id = receipt.receipt_id
        
        # Get the receipt
        retrieved_receipt = await billing_service.get_receipt(receipt_id)
        
        # Verify result
        assert retrieved_receipt is not None
        assert retrieved_receipt.receipt_id == receipt_id
        assert retrieved_receipt.invoice_id == invoice.invoice_id
        assert retrieved_receipt.transaction_id == "tx_123"
        
        # Get non-existent receipt
        nonexistent_receipt = await billing_service.get_receipt("nonexistent")
        assert nonexistent_receipt is None
    
    @pytest.mark.asyncio
    async def test_get_user_receipts(self, billing_service, sample_invoice_data):
        """Test getting receipts for a user"""
        # Create and pay multiple invoices for the same user
        for i in range(3):
            data = sample_invoice_data.copy()
            data["amount"] = 49.99 + i * 10
            success, invoice, _ = await billing_service.create_invoice(**data)
            await billing_service.mark_invoice_paid(
                invoice.invoice_id,
                "credit_card",
                f"tx_{i+1}"
            )
        
        # Create and pay invoice for different user
        other_user_data = sample_invoice_data.copy()
        other_user_data["user_id"] = "user_456"
        success, other_invoice, _ = await billing_service.create_invoice(**other_user_data)
        await billing_service.mark_invoice_paid(other_invoice.invoice_id, "paypal")
        
        # Get receipts for user_123
        user_receipts = await billing_service.get_user_receipts("user_123")
        
        # Verify result
        assert isinstance(user_receipts, list)
        assert len(user_receipts) == 3
        
        # Verify all receipts belong to user_123
        for receipt in user_receipts:
            assert receipt.user_id == "user_123"
        
        # Verify sorting (newest first)
        dates = [receipt.paid_at for receipt in user_receipts]
        assert dates == sorted(dates, reverse=True)
    
    @pytest.mark.asyncio
    async def test_generate_invoice_pdf(self, billing_service, sample_invoice_data):
        """Test generating invoice PDF"""
        # Create an invoice
        success, invoice, _ = await billing_service.create_invoice(**sample_invoice_data)
        
        # Generate PDF
        success, pdf_content, message = await billing_service.generate_invoice_pdf(invoice.invoice_id)
        
        # Verify result
        assert success is True
        assert pdf_content is not None
        assert isinstance(pdf_content, bytes)
        assert "successfully" in message.lower()
        
        # Verify PDF contains invoice information
        pdf_text = pdf_content.decode('utf-8')
        assert invoice.invoice_id in pdf_text
        assert str(invoice.amount) in pdf_text
        assert invoice.description in pdf_text
    
    @pytest.mark.asyncio
    async def test_generate_invoice_pdf_nonexistent(self, billing_service):
        """Test generating PDF for non-existent invoice"""
        # Generate PDF for non-existent invoice
        success, pdf_content, message = await billing_service.generate_invoice_pdf("nonexistent")
        
        # Verify failure
        assert success is False
        assert pdf_content is None
        assert "not found" in message.lower()
    
    @pytest.mark.asyncio
    async def test_generate_receipt_pdf(self, billing_service, sample_invoice_data):
        """Test generating receipt PDF"""
        # Create and pay an invoice
        success, invoice, _ = await billing_service.create_invoice(**sample_invoice_data)
        success, receipt, _ = await billing_service.mark_invoice_paid(
            invoice.invoice_id,
            "credit_card",
            "tx_123"
        )
        
        # Generate PDF
        success, pdf_content, message = await billing_service.generate_receipt_pdf(receipt.receipt_id)
        
        # Verify result
        assert success is True
        assert pdf_content is not None
        assert isinstance(pdf_content, bytes)
        assert "successfully" in message.lower()
        
        # Verify PDF contains receipt information
        pdf_text = pdf_content.decode('utf-8')
        assert receipt.receipt_number in pdf_text
        assert str(receipt.amount) in pdf_text
        assert receipt.payment_method in pdf_text
    
    @pytest.mark.asyncio
    async def test_get_billing_history(self, billing_service, sample_invoice_data):
        """Test getting billing history for a user"""
        # Create some billing activity
        success, invoice1, _ = await billing_service.create_invoice(**sample_invoice_data)
        
        data2 = sample_invoice_data.copy()
        data2["amount"] = 59.99
        success, invoice2, _ = await billing_service.create_invoice(**data2)
        
        # Pay one invoice
        await billing_service.mark_invoice_paid(invoice1.invoice_id, "credit_card")
        
        # Get billing history
        history = await billing_service.get_billing_history("user_123")
        
        # Verify result
        assert isinstance(history, list)
        assert len(history) >= 3  # 2 invoices + 1 payment
        
        # Verify entry types
        entry_types = [entry.type for entry in history]
        assert "invoice" in entry_types
        assert "payment" in entry_types
        
        # Verify sorting (newest first)
        dates = [entry.created_at for entry in history]
        assert dates == sorted(dates, reverse=True)
    
    @pytest.mark.asyncio
    async def test_get_billing_history_with_filters(self, billing_service, sample_invoice_data):
        """Test getting billing history with filters"""
        # Create billing activity over time
        now = datetime.utcnow()
        
        # Old invoice (30 days ago)
        old_data = sample_invoice_data.copy()
        old_invoice = Invoice(
            invoice_id="inv_old",
            subscription_id="sub_123",
            user_id="user_123",
            amount=39.99,
            created_at=now - timedelta(days=30)
        )
        billing_service.invoices["inv_old"] = old_invoice
        await billing_service._add_billing_history(
            user_id="user_123",
            entry_type="invoice",
            amount=39.99,
            currency="USD",
            description="Old invoice",
            reference_id="inv_old",
            status="created"
        )
        
        # Recent invoice
        success, recent_invoice, _ = await billing_service.create_invoice(**sample_invoice_data)
        
        # Get history with date range
        start_date = now - timedelta(days=15)
        recent_history = await billing_service.get_billing_history(
            "user_123",
            start_date=start_date
        )
        
        # Verify only recent entries
        for entry in recent_history:
            assert entry.created_at >= start_date
        
        # Get history with type filter
        invoice_history = await billing_service.get_billing_history(
            "user_123",
            entry_type="invoice"
        )
        
        # Verify only invoice entries
        for entry in invoice_history:
            assert entry.type == "invoice"
    
    @pytest.mark.asyncio
    async def test_get_billing_summary(self, billing_service, sample_invoice_data):
        """Test getting billing summary for a user"""
        # Create billing activity
        for i in range(3):
            data = sample_invoice_data.copy()
            data["amount"] = 49.99 + i * 10
            # due_date is calculated internally, not passed as parameter
            success, invoice, _ = await billing_service.create_invoice(**data)
            
            # Pay first invoice
            if i == 0:
                await billing_service.mark_invoice_paid(invoice.invoice_id, "credit_card")
        
        # Get billing summary
        summary = await billing_service.get_billing_summary("user_123")
        
        # Verify result
        assert isinstance(summary, dict)
        assert summary["user_id"] == "user_123"
        
        # Check summary fields
        assert "total_invoiced" in summary
        assert "total_paid" in summary
        assert "total_outstanding" in summary
        assert "invoice_count" in summary
        assert "paid_invoice_count" in summary
        assert "outstanding_invoice_count" in summary
        assert "receipt_count" in summary
        assert "upcoming_invoices" in summary
        assert "recent_activity" in summary
        
        # Verify calculations
        assert summary["total_invoiced"] > 0
        assert summary["total_paid"] > 0
        assert summary["total_outstanding"] > 0
        assert summary["invoice_count"] == 3
        assert summary["paid_invoice_count"] == 1
        assert summary["outstanding_invoice_count"] == 2
        assert summary["receipt_count"] == 1
        
        # Verify upcoming invoices
        assert isinstance(summary["upcoming_invoices"], list)
        
        # Verify recent activity
        assert isinstance(summary["recent_activity"], list)
        assert len(summary["recent_activity"]) <= 10
    
    @pytest.mark.asyncio
    async def test_process_recurring_billing(self, billing_service):
        """Test processing recurring billing"""
        # Process recurring billing
        result = await billing_service.process_recurring_billing()
        
        # Verify result
        assert isinstance(result, dict)
        assert "subscriptions_processed" in result
        assert "invoices_created" in result
        assert "payments_processed" in result
        assert "successful_payments" in result
        assert "failed_payments" in result
        assert "errors" in result
        
        # Verify mock data
        assert result["subscriptions_processed"] == 150
        assert result["invoices_created"] == 120
        assert result["payments_processed"] == 115
        assert result["successful_payments"] == 110
        assert result["failed_payments"] == 5
        assert result["errors"] == []
    
    @pytest.mark.asyncio
    async def test_invoice_to_dict(self, billing_service, sample_invoice_data):
        """Test converting invoice to dictionary"""
        # Create an invoice
        success, invoice, _ = await billing_service.create_invoice(**sample_invoice_data)
        
        # Convert to dict
        invoice_dict = invoice.to_dict()
        
        # Verify dictionary structure
        assert isinstance(invoice_dict, dict)
        assert invoice_dict["invoice_id"] == invoice.invoice_id
        assert invoice_dict["subscription_id"] == "sub_123"
        assert invoice_dict["user_id"] == "user_123"
        assert invoice_dict["amount"] == 49.99
        assert invoice_dict["currency"] == "USD"
        assert invoice_dict["status"] == "open"
        assert "due_date" in invoice_dict
        assert "period_start" in invoice_dict
        assert "period_end" in invoice_dict
        assert invoice_dict["description"] == "Monthly subscription fee"
        assert isinstance(invoice_dict["items"], list)
        assert invoice_dict["tax_amount"] > 0
        assert invoice_dict["total_amount"] == invoice_dict["amount"] + invoice_dict["tax_amount"]
        assert "created_at" in invoice_dict
        assert "updated_at" in invoice_dict
    
    @pytest.mark.asyncio
    async def test_receipt_to_dict(self, billing_service, sample_invoice_data):
        """Test converting receipt to dictionary"""
        # Create and pay an invoice
        success, invoice, _ = await billing_service.create_invoice(**sample_invoice_data)
        success, receipt, _ = await billing_service.mark_invoice_paid(
            invoice.invoice_id,
            "credit_card",
            "tx_123"
        )
        
        # Convert to dict
        receipt_dict = receipt.to_dict()
        
        # Verify dictionary structure
        assert isinstance(receipt_dict, dict)
        assert receipt_dict["receipt_id"] == receipt.receipt_id
        assert receipt_dict["invoice_id"] == invoice.invoice_id
        assert receipt_dict["user_id"] == "user_123"
        assert receipt_dict["amount"] == invoice.amount
        assert receipt_dict["currency"] == "USD"
        assert receipt_dict["payment_method"] == "credit_card"
        assert receipt_dict["transaction_id"] == "tx_123"
        assert receipt_dict["status"] == "completed"
        assert "paid_at" in receipt_dict
        assert receipt_dict["receipt_number"] is not None
        assert isinstance(receipt_dict["items"], list)
        assert receipt_dict["tax_amount"] == invoice.tax_amount
        assert receipt_dict["total_amount"] == invoice.total_amount
        assert "created_at" in receipt_dict


if __name__ == "__main__":
    pytest.main([__file__, "-v"])