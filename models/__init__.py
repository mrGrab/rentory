from .auth import NewPassword, Token, TokenPayload
from .client import Client, ClientCreate, ClientFilters, ClientPublic, ClientUpdate
from .common import ListQueryParams, TimestampMixin, UUIDMixin
from .item import Item, ItemBase, ItemCreate, ItemFilters, ItemPublic, ItemUpdate
from .item_variant import (
    ItemVariant,
    ItemVariantBase,
    ItemVariantCreate,
    ItemVariantFilters,
    ItemVariantPrice,
    ItemVariantPriceBase,
    ItemVariantPublic,
    ItemVariantPublicInternal,
    ItemVariantQuantity,
    ItemVariantStatus,
    ItemVariantUpdate,
)
from .links import OrderItemLink
from .order import Order, OrderBase, OrderCreate, OrderPublic, OrderUpdate

models_to_rebuild = [
    Item,
    ItemCreate,
    ItemUpdate,
    ItemPublic,
    ItemVariantPrice,
    ItemVariant,
    ItemVariantBase,
    ItemVariantPublic,
    OrderItemLink,
    Order,
    OrderCreate,
    OrderUpdate,
    OrderPublic,
    ItemFilters,
    ItemVariantPublicInternal,
]

for model in models_to_rebuild:
    model.model_rebuild()
