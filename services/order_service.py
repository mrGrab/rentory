from datetime import UTC, date, datetime, timedelta
from io import BytesIO
from uuid import UUID

from jinja2 import Environment, FileSystemLoader, select_autoescape
from pdf2image import convert_from_bytes
from PIL import Image
from sqlmodel import select
from weasyprint import HTML

from core.exceptions import BadRequestException, ConflictException

# --- Project Imports ---
from core.logger import logger
from core.query_gateway import QueryGateway
from models.client import Client
from models.item_variant import ItemVariant
from models.links import OrderItemLink
from models.order import Order, OrderCreate, OrderFilters, OrderStatus, OrderUpdate
from models.payment import Payment, PaymentType
from services.item_variant_service import ItemVariantService
from services.order_query_gateway import OrderQueryGateway


def calculate_discount_amount(price: int, discount: int) -> int:
    if discount >= 100:
        return 0
    return price * discount // (100 - discount)


class OrderService:
    """Business logic for order operations"""

    def __init__(self, session):
        self.session = session
        self.item_variant_service = ItemVariantService(session)
        self.query_gateway: QueryGateway[Order, OrderFilters] = OrderQueryGateway(
            session
        )

    def get_orders(
        self,
        filters: OrderFilters,
        offset: int = 0,
        limit: int = 100,
        sort_field: str = "created_at",
        sort_order: str = "DESC",
    ) -> tuple[list[Order], int]:
        """Get filtered and paginated orders with total count"""
        logger.debug("Fetching orders")
        orders, total = self.query_gateway.list(
            filters=filters,
            offset=offset,
            limit=limit,
            sort_field=sort_field,
            sort_order=sort_order,
        )

        logger.debug(f"Found {len(orders)} orders out of {total} total")
        return orders, total

    def get_by_id(self, order_id: int) -> Order | None:
        """Get order by ID"""
        logger.debug(f"Fetching order by ID: {order_id}")
        return self.query_gateway.get_by_id(order_id)

    def check_variant_availability(
        self,
        variant_id: UUID,
        start_time: date,
        end_time: date,
        requested_quantity: int = 1,
        exclude_order_id: int | None = None,
    ) -> tuple[bool, str | None]:
        """Check if variant is available for booking period.

        Delegates the actual availability math (archived/maintenance/bookings)
        to ItemVariantService, the single source of truth for that logic.
        """
        variant: ItemVariant = self.session.get(ItemVariant, variant_id)
        if not variant:
            return False, f"Variant {variant_id} not found"

        _, available_quantity, _ = self.item_variant_service.check_availability(
            variant, start_time, end_time, exclude_order_id
        )

        if available_quantity < requested_quantity:
            message = (
                f"Variant {variant_id}: {available_quantity} unit(s) available, "
                f"requested {requested_quantity}"
            )
            return False, message

        return True, None

    def validate_order_items(
        self,
        items: list,
        start_time: date,
        end_time: date,
        exclude_order_id: int | None = None,
    ) -> None:
        """Validate all items in order are available"""
        if not items:
            raise BadRequestException("Order must contain at least one item")

        unavailable_variants = []

        for item in items:
            is_available, reason = self.check_variant_availability(
                variant_id=item.item_variant_id,
                start_time=start_time,
                end_time=end_time,
                requested_quantity=item.quantity,
                exclude_order_id=exclude_order_id,
            )

            if not is_available:
                unavailable_variants.append(reason)

        if unavailable_variants:
            error_msg = "; ".join(unavailable_variants)
            logger.warning(f"Validation failed: {error_msg}")
            raise ConflictException(error_msg)

    def create(self, order_in: OrderCreate) -> Order:
        """Create a new order"""
        logger.debug(f"Creating order for client {order_in.client_id}")

        # Validate dates
        if order_in.start_time > order_in.end_time:
            raise BadRequestException("Start time must be before end time")

        # Validate item availability
        self.validate_order_items(
            items=order_in.items,
            start_time=order_in.start_time,
            end_time=order_in.end_time,
        )

        # Zero deposit for trusted clients
        client = self.session.get(Client, order_in.client_id)
        if client and client.is_trusted:
            order_in.deposit_amount = 0

        # Create the order
        order_data = order_in.model_dump(
            exclude={"items", "payments"}, exclude_unset=True
        )
        order = Order(**order_data)

        # Create order-item links
        order.item_links = [
            OrderItemLink(
                item_variant_id=item.item_variant_id,
                price=item.price,
                deposit=item.deposit,
                quantity=item.quantity,
            )
            for item in order_in.items
        ]

        # Create payments if provided
        if order_in.payments:
            order.payments = [
                Payment(**payment.model_dump()) for payment in order_in.payments
            ]

        self.session.add(order)
        self.session.commit()
        self.session.refresh(order)

        logger.info(f"Order {order.id} created successfully")
        return order

    def update(self, order: Order, order_in: OrderUpdate) -> Order:
        """Update existing order"""
        logger.debug(f"Updating order: {order.id}")

        update_data = order_in.model_dump(
            exclude={"items", "payments"}, exclude_unset=True
        )

        if not update_data and not order_in.items and not order_in.payments:
            logger.warning("No data provided for update")
            raise BadRequestException("No data provided for update")

        # Get effective dates for validation
        start_time = order_in.start_time if order_in.start_time else order.start_time
        end_time = order_in.end_time if order_in.end_time else order.end_time

        # Validate dates
        if start_time > end_time:
            raise BadRequestException("Start time must be before end time")

        # Validate items if provided
        if order_in.items is not None:
            if not order_in.items:
                raise BadRequestException("Order must contain items")

            # Closing an order (DONE/RETURNED) hands the item back rather than
            # booking it out, so maintenance/availability no longer applies.
            effective_status = (
                order_in.status if order_in.status is not None else order.status
            )
            if effective_status not in (OrderStatus.DONE, OrderStatus.RETURNED):
                self.validate_order_items(
                    items=order_in.items,
                    start_time=start_time,
                    end_time=end_time,
                    exclude_order_id=order.id,
                )

        # Update order fields
        for field, value in update_data.items():
            setattr(order, field, value)

        # Zero deposit for trusted clients (enforced after field update)
        client = self.session.get(Client, order.client_id)
        if client and client.is_trusted:
            order.deposit_amount = 0

        # Update items if provided
        if order_in.items is not None:
            order.item_links = [
                OrderItemLink(
                    item_variant_id=item.item_variant_id,
                    price=item.price,
                    deposit=item.deposit,
                    quantity=item.quantity,
                )
                for item in order_in.items
            ]

        # Update payments if provided
        if order_in.payments is not None:
            order.payments = [
                Payment(**payment.model_dump()) for payment in order_in.payments
            ]

        order.updated_at = datetime.now(UTC)
        self.session.add(order)
        self.session.commit()
        self.session.refresh(order)

        logger.info(f"Order {order.id} updated successfully")
        return order

    def archive(self, order: Order) -> None:
        """Archive an order (soft delete)"""
        logger.debug(f"Archiving order: {order.id}")

        order.is_archived = True
        order.updated_at = datetime.now(UTC)

        self.session.add(order)
        self.session.commit()

        logger.info(f"Order {order.id} archived successfully")

    def delete(self, order: Order) -> None:
        """Delete an order"""

        logger.debug(f"Deleting order: {order.id}")

        self.session.delete(order)
        self.session.commit()

        logger.info(f"Order {order.id} deleted successfully")

    def get_orders_by_client(self, client_id: UUID) -> list[Order]:
        """Get all orders for a specific client"""
        logger.debug(f"Fetching orders for client: {client_id}")

        stmt = select(Order).where(Order.client_id == client_id)
        orders = self.session.exec(stmt).all()

        logger.debug(f"Found {len(orders)} orders for client {client_id}")
        return orders

    def get_orders_by_status(self, status: str) -> list[Order]:
        """Get all orders with a specific status"""
        logger.debug(f"Fetching orders with status: {status}")

        stmt = select(Order).where(Order.status == status)
        orders = self.session.exec(stmt).all()

        logger.debug(f"Found {len(orders)} orders with status {status}")
        return orders

    def generate_invoice_pdf(self, order: Order) -> bytes:
        """Generate PDF invoice from order data"""
        logger.debug(f"Generating invoice PDF for order {order.id}")

        items = [
            {
                "title": link.item_variant.item.title,
                "image_url": link.item_variant.image_url,
                "size": link.item_variant.size,
                "color": link.item_variant.color,
                "price": link.price,
                "deposit": link.deposit,
                "quantity": link.quantity,
            }
            for link in order.item_links
        ]

        rent_paid = sum(
            p.amount for p in order.payments if p.entry_type == PaymentType.PAYMENT
        )
        deposit_paid = sum(
            p.amount for p in order.payments if p.entry_type == PaymentType.DEPOSIT
        )

        delivery = order.delivery_info or {}
        if hasattr(delivery, "pickup_type"):
            pickup_type = delivery.pickup_type
            return_type = delivery.return_type
        else:
            pickup_type = delivery.get("pickup_type", "")
            return_type = delivery.get("return_type", "")

        is_postal_pickup = pickup_type == "postal_service"
        is_postal_return = return_type == "postal_service"

        display_start = order.start_time
        display_end = (
            order.end_time - timedelta(days=2) if is_postal_return else order.end_time
        )

        invoice_data = {
            "order": order,
            "client": order.client,
            "items": items,
            "payments": order.payments,
            "rent_paid": rent_paid,
            "deposit_paid": deposit_paid,
            "rent_due": order.price - rent_paid,
            "discount_amount": calculate_discount_amount(order.price, order.discount),
            "deposit_due": order.deposit_amount - deposit_paid,
            "display_start": display_start,
            "display_end": display_end,
            "pickup_action_label": "ВІДПРАВИМО" if is_postal_pickup else "ОТРИМАТИ",
            "return_action_label": "ВІДПРАВИТИ" if is_postal_return else "ПОВЕРНУТИ",
        }

        env = Environment(
            loader=FileSystemLoader("templates"),
            autoescape=select_autoescape(["html", "xml"]),
        )
        template = env.get_template("invoice.html")
        html_content = template.render(**invoice_data)

        pdf_bytes = HTML(string=html_content).write_pdf()

        logger.debug(f"Invoice PDF generated for order {order.id}")
        return pdf_bytes

    def generate_invoice_jpeg(self, order: Order) -> bytes:
        """Generate a single tall JPEG invoice from the PDF rendering."""
        pdf_bytes = self.generate_invoice_pdf(order)
        pages = convert_from_bytes(pdf_bytes, dpi=150, fmt="jpeg")

        width = max(page.width for page in pages)
        height = sum(page.height for page in pages)
        invoice_image = Image.new("RGB", (width, height), "white")

        top = 0
        for page in pages:
            invoice_image.paste(page.convert("RGB"), (0, top))
            top += page.height

        image_bytes = BytesIO()
        invoice_image.save(image_bytes, format="JPEG", quality=90, optimize=True)
        return image_bytes.getvalue()
