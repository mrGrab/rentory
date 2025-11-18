from .auth import Token, TokenPayload, NewPassword
from .common import UUIDMixin, TimestampMixin, ListQueryParams
from .client import Client, ClientCreate, ClientUpdate, ClientPublic, ClientFilters
from .links import OrderItemLink
from .item import Item, ItemBase, ItemCreate, ItemUpdate, ItemPublic, ItemFilters
from .item_variant import (ItemVariantPrice, ItemVariant, ItemVariantPriceBase,
                           ItemVariantBase, ItemVariantCreate,
                           ItemVariantUpdate, ItemVariantPublic,
                           ItemVariantPublicInternal, ItemVariantFilters,
                           ItemVariantQuantity, ItemVariantStatus)
from .order import Order, OrderBase, OrderCreate, OrderUpdate, OrderPublic

models_to_rebuild = [
    Item, ItemCreate, ItemUpdate, ItemPublic, ItemVariantPrice, ItemVariant,
    ItemVariantBase, ItemVariantPublic, OrderItemLink, Order, OrderCreate,
    OrderUpdate, OrderPublic, ItemFilters, ItemVariantPublicInternal
]

for model in models_to_rebuild:
    model.model_rebuild()
