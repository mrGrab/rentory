"""Invoice rendering for Orders: PDF and JPEG adapters over one Jinja template."""

from datetime import timedelta
from io import BytesIO

from jinja2 import Environment, FileSystemLoader, select_autoescape
from pdf2image import convert_from_bytes
from PIL import Image
from weasyprint import HTML

from core.exceptions import BadRequestException
from core.logger import logger
from models.order import DeliveryInfo, Order
from models.payment import PaymentType
from services.helpers import display_color, display_size, display_title


def calculate_discount_amount(price: int, discount: int) -> int:
    if discount >= 100:
        return 0
    return price * discount // (100 - discount)


def generate_invoice_pdf(order: Order) -> bytes:
    """Generate PDF invoice from order data"""
    logger.debug(f"Generating invoice PDF for order {order.id}")

    items = []
    for link in order.item_links:
        if link.item_variant is None or link.item_variant.item is None:
            raise BadRequestException("Order has an invalid item variant link")
        items.append(
            {
                "title": display_title(
                    link.item_title_snapshot, link.item_variant.item.title
                ),
                "image_url": link.item_variant.image_url,
                "size": display_size(
                    link.variant_size_snapshot, link.item_variant.size
                ),
                "color": display_color(
                    link.variant_color_snapshot, link.item_variant.color
                ),
                "price": link.price,
                "deposit": link.deposit,
                "quantity": link.quantity,
            }
        )

    rent_paid = sum(
        p.amount for p in order.payments if p.entry_type == PaymentType.PAYMENT
    )
    deposit_paid = sum(
        p.amount for p in order.payments if p.entry_type == PaymentType.DEPOSIT
    )

    delivery = order.delivery_info
    if isinstance(delivery, DeliveryInfo):
        pickup_type = delivery.pickup_type
        return_type = delivery.return_type
    else:
        delivery_data = delivery or {}
        pickup_type = delivery_data.get("pickup_type", "")
        return_type = delivery_data.get("return_type", "")

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
    if pdf_bytes is None:
        raise RuntimeError("Invoice PDF rendering returned no data")

    logger.debug(f"Invoice PDF generated for order {order.id}")
    return pdf_bytes


def generate_invoice_jpeg(order: Order) -> bytes:
    """Generate a single tall JPEG invoice from the PDF rendering."""
    pdf_bytes = generate_invoice_pdf(order)
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
