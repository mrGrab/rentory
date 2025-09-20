#!/usr/bin/env python3
# coding: UTF-8

from datetime import datetime, timezone, date, timedelta
from rich import print
import random
from random import choices
import requests
from typing import List
from core.dependency import hash_password, engine, save_to_db
from core.models import (User, UserCreate, ItemPrice, Item, Order,
                         OrderItemLink, Client, ItemStatus, ItemVariant,
                         ItemVariantStatus, PaymentDetails, PaymentType,
                         DeliveryInfo, PickupType, OrderStatus)
from sqlmodel import Session, select, func
from sqlalchemy.exc import SQLAlchemyError


def create_new_user(session,
                    user_create: UserCreate,
                    is_active: bool = True,
                    is_superuser: bool = True):
    now = datetime.now(timezone.utc)
    user_data = user_create.model_dump(exclude={"password"})
    hashed_pw = hash_password(user_create.password)
    user = User(**user_data,
                hashed_password=hashed_pw,
                is_active=is_active,
                is_superuser=is_superuser,
                created_at=now,
                updated_at=now)
    if save_to_db(session, user):
        print("[green]User created:[/]", user.username)
    else:
        print("[bold yellow]User already exists or failed to create[/]")


def create_clients(session, count: int = 10):
    now = datetime.now(timezone.utc)
    discounts = [0, 5, 10, 15, 20, 25, 30]
    given_names = ["Alice", "Bob", "Charlie", "David", "Eve", "Max"]
    surnames = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Doe"]
    phones = [
        "+380969544403", "+380665428745", "+380969578932", "+380625874123",
        "+380959785412", "+380979652148", "+380969645148", "+380999651140"
    ]

    for _ in range(count):
        client = Client(given_name=random.choice(given_names),
                        surname=random.choice(surnames),
                        phone=random.choice(phones),
                        discount=random.choice(discounts),
                        created_at=now,
                        updated_at=now)
        try:
            session.add(client)
            session.commit()
            session.refresh(client)
            print(
                f"[green]Client created:[/] {client.given_name} {client.surname}"
            )
        except SQLAlchemyError as e:
            session.rollback()
            print(f"[red]Failed to create client:[/] {e}")


def create_items(session: Session, count: int = 10):
    categories = ["dress", "corset", "skirt", "scarf"]
    sizes = ["XS", "S", "M", "L", "XL"]
    colors = ["red", "blue", "green", "black", "white"]
    prices_amount = [1000, 2000, 3000, 4000, 5000]
    price_types = ["1 day", "3 days", "sell"]
    tags_pool = ["new", "sale", "popular", "limited"]
    start = date(2025, 8, 1)
    dates = [start + timedelta(days=i) for i in range(31)]

    for _ in range(count):
        rand_int = random.randint(1, 100)
        item_status = choices(population=list(ItemStatus),
                              weights=[
                                  0.9 if s == ItemStatus.IN_STOCK else 0.1 /
                                  (len(ItemStatus) - 1) for s in ItemStatus
                              ],
                              k=1)[0]

        item = Item(
            title=f"#{rand_int}",
            category=random.choice(categories),
            description=f"Sample description for Item - #{rand_int}",
            image_url=random.choice([
                None,
                "https://images.icon-icons.com/2070/PNG/512/dress_icon_126365.png",
                "https://images.icon-icons.com/1465/PNG/512/422dress_100789.png",
                "https://images.icon-icons.com/2272/PNG/512/dress_clothing_icon_140714.png"
            ]),
            status=item_status,
            tags=random.choice([
                [],  # sometimes no tags
                random.sample(tags_pool, k=random.randint(1, len(tags_pool)))
            ]))

        # Create variants
        for _ in range(random.randint(1, 5)):
            variant_status = choices(
                population=list(ItemVariantStatus),
                weights=[
                    0.8 if s == ItemVariantStatus.AVAILABLE else 0.1 /
                    (len(ItemVariantStatus) - 1) for s in ItemVariantStatus
                ],
                k=1)[0]
            if variant_status in [
                    ItemVariantStatus.CLEANING, ItemVariantStatus.REPAIR
            ]:
                service_start = random.choice(dates)
                service_end = random.choice(
                    [d for d in dates if d >= service_start])
            else:
                service_start, service_end = None, None
            # print(variant_status, service_start, service_end)

            variant = ItemVariant(item_id=item.id,
                                  size=random.choice(sizes + [None]),
                                  color=random.choice(colors + [None]),
                                  stock_quantity=random.randint(1, 3),
                                  service_start_time=service_start,
                                  service_end_time=service_end,
                                  status=variant_status,
                                  item=item)

            # Create prices per variant
            for _ in range(random.randint(1, 3)):
                price = ItemPrice(variant_id=variant.id,
                                  amount=random.choice(prices_amount),
                                  price_type=random.choice(price_types),
                                  variant=variant)
                session.add(price)

            session.add(variant)

        session.add(item)

        try:
            session.commit()
            session.refresh(item)
            print(f"[green]Item created:[/] {item.title}")
        except Exception as e:
            session.rollback()
            print(f"[red]Failed to create item: {item.title}[/]")


def create_orders(session: Session, count: int = 10):
    now = datetime.now(timezone.utc)
    clients = session.exec(select(Client)).all()
    users = session.exec(select(User)).all()

    dates = [date(2025, 8, 1) + timedelta(days=i) for i in range(31)]
    addresses = ["123 Main St", "456 Elm St", "789 Oak St", "101 Pine St"]
    tags_pool = ["new", "strange", "bad"]

    tracking_numbers = [
        "TRK123456789", "TRK987654321", "TRK456789123", "TRK321654987", None
    ]
    for i in range(count):
        start = random.choice(dates)
        end = random.choice([d for d in dates if d >= start])
        client = random.choice(clients)
        user = random.choice(users)
        tags = random.sample(tags_pool, k=random.randint(0, len(tags_pool)))

        pickup_type = random.choice(list(PickupType))
        delivery = DeliveryInfo(
            pickup_type=pickup_type,
            address=None
            if pickup_type == PickupType.SHOWROOM else random.choice(addresses),
            tracking_number=random.choice(tracking_numbers)
            if pickup_type == PickupType.POSTAL_SERVICE else None)
        order = Order(start_time=start,
                      end_time=end,
                      status=random.choice(list(OrderStatus)),
                      order_discount=random.choice([0, 5, 10, 15]),
                      notes=f"Order comment #{i}",
                      tags=tags,
                      delivery_info=delivery.model_dump(),
                      created_by_user_id=user.id,
                      client_id=client.id,
                      created_at=now,
                      updated_at=now)
        try:

            session.add(order)
            session.flush()

            added_variants = set()
            total = 0
            variants = random.randint(1, 5)
            while len(added_variants) < variants:
                item_variant = session.exec(
                    select(ItemVariant).order_by(func.random())).first()
                if item_variant.id in added_variants:
                    continue
                if item_variant.service_end_time and item_variant.service_end_time > order.start_time:
                    continue
                added_variants.add(item_variant.id)

                link = OrderItemLink(order_id=order.id,
                                     item_variant_id=item_variant.id,
                                     price=random.choice(
                                         item_variant.prices).amount,
                                     quantity=1)

                session.add(link)
                total += link.price

            order.payment_details = PaymentDetails(
                total=total,
                paid=random.randint(0, int(total * 0.7)),
                deposit=random.randint(0, int(total * 0.5)),
                payment_type=random.choice(list(PaymentType))).model_dump()

            session.commit()
            print("[green]Order created:[/]", order.id)
        except Exception as e:
            session.rollback()
            print("[red]Failed to create order:[/]", e)


def main():

    users = [
        UserCreate(username="root",
                   email="root@example.com",
                   password="qwertyzz"),
        UserCreate(username="user",
                   email="user@example.com",
                   password="qwertyzz")
    ]

    with Session(engine) as session:
        #---------------------
        # Create users
        #---------------------
        for user in users:
            create_new_user(session, user)

        # --------------------
        # Create clients
        # --------------------
        create_clients(session, count=10)

        # --------------------
        # Create dummy items
        # --------------------
        create_items(session, count=30)

        # --------------------
        # Create dummy orders
        # --------------------
        create_orders(session, count=20)

    data = {"username": "root", "password": "qwertyzz"}
    r = requests.post("http://127.0.0.1:5233/api/v1/login", data=data)

    print("[blue]Token:[/]", r.json().get("access_token"))


if __name__ == "__main__":
    main()
