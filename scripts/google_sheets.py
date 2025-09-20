#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import re
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2 import service_account
from rich import print
from datetime import datetime
from rich.logging import RichHandler
from sqlmodel import Session, select

# Root project directory
ROOT_DIR = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT_DIR))
from core.models import Item, ItemVariant
from core.database import engine

# ------------------- Logging Setup -------------------
logging.basicConfig(level="NOTSET",
                    format="%(message)s",
                    handlers=[RichHandler(show_time=False)])
log = logging.getLogger("rich")

# ------------------- Config -------------------
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
SPREADSHEET_ID = "1QNawRp5WzNMaL2NqY1vdWDrgQdLhhhdjoMPqZIinWhk"
SERVICE_ACCOUNT_KEY_FILE = Path("service_account_key.json")

COLOR_MAP = {
    "рожева": "pink",
    "рожеві": "pink",
    "рожевий": "pink",
    "рожеве": "pink",
    "бежева": "beige",
    "бежеві": "beige",
    "бежевий": "beige",
    "молочний": "milky",
    "молочні": "milky",
    "молочна": "milky",
    "золоте": "gold",
    "золота": "gold",
    "золоті": "gold",
    "чорна": "black",
    "чорні": "black",
    "чорний": "black",
    "блакитна": "sky-blue",
    "блакитний": "sky-blue",
    "біле": "white",
    "біла": "white",
    "білі": "white",
    "білий": "white",
    "червона": "red",
    "червона": "red",
    "червоні": "red",
    "червоний": "red",
    "бордова": "burgundy",
    "коричневі": "brown",
    "сіра": "grey",
    "темно-сірі": "grey",
    "фіолетовий": "purple"
}

CATEGORY_MAP = {
    "болеро": "bolero",
    "сорочка": "shirt",
    "кофтинка": "sweater",
    "жакет": "jacket",
    "шляпа": "hat",
    "сережки": "earrings",
    "намисто": "necklace",
    "кулончик": "pendant",
    "чокер": "choker",
    "браслет": "bracelet",
    "підвіска": "pendant",
    "туфлі": "shoes",
    "бантики": "bow",
    "кейп": "cape",
    "накидка": "cape",
    "піджак": "jacket",
    "боді": "bodysuit",
    "гольф": "turtleneck",
    "корсет": "corset",
    "шлейф": "train",
    "спідниця": "skirt",
    "штани": "trousers",
    "топ": "top",
    "лосіни": "leggings",
    "костюм": "suit",
    "сукня": "dress",
    "босоніжки": "sandals",
    "тканина": "fabric",
    "сукні, накидки, короткі жакети, кейпи, шлейфи": "dress-cape-jacket-train",
    "сукні, накидки, короткі жакети": "dress-cape-short-jacket",
    "корсети, топи, брюки, спідниці": "corset-top-trousers-skirt",
    "жіночі піджаки, брючні костюми, шуба": "womensjacket-pantsuit-furcoat",
    "чоловічі костюми, сорочки, гольфи": "suit-shirt-turtleneck",
    "весільні": "wedding",
    "family  look": "family-look",
    "піжами та светри": "pyjamas-and-sweaters",
    "дитячі речі (сукні, хлопчачі костюми та піджаки)": "kid-dress-suit-jacket",
    "трусики": "underwear",
    "взуття доросле": "shoes",
    "взуття дитяче": "kid-shoes",
    "рукавиці": "gloves",
    "квіточки": "flowers",
    "квіточка": "flowers",
    "сумочки": "bag",
    "сережки, прикраси на шию, браслети": "earrings-necklace-bracelets",
    "аксесуари на голову": "head-accessories",
    "гетри": "leg-warmers",
    "комбез": "romper",
    "шапка": "hat",
    "носочки": "socks",
    "шуба": "fur-coat",
    "кардиган": "cardigan",
    "туніка": "tunic"
}

SIZES = ["XS", "S", "M", "L", "XL", "XL+", "XXL"]

CELL_MAP = {
    0: "A",
    1: "B",
    2: "C",
    3: "D",
    4: "E",
    5: "F",
    6: "G",
    7: "H",
    8: "I",
    9: "J",
    10: "K",
    11: "L",
    12: "M",
    13: "N",
    14: "O",
    15: "P",
    16: "R",
    17: "S",
    18: "T",
    19: "U",
    20: "V",
    21: "W",
    22: "Y",
    23: "Z",
    24: "AA",
    25: "AB",
    26: "AC",
    27: "AD",
    28: "AE",
    29: "AF",
    30: "AG",
    31: "AH",
    32: "AI",
    33: "AJ"
}


# ------------------- Google Sheets Wrapper -------------------
class GoogleSheet:
    """Wrapper class for Google Sheets API using Service Account credentials."""

    def __init__(self,
                 credentials_file: Path = SERVICE_ACCOUNT_KEY_FILE,
                 scopes: List[str] = SCOPES,
                 spreadsheet_id: str = SPREADSHEET_ID):
        self.spreadsheet_id = spreadsheet_id
        self.credentials = self._get_credentials(credentials_file, scopes)
        self.service = build("sheets", "v4", credentials=self.credentials)
        self.spreadsheets = self.service.spreadsheets()

    def _get_credentials(self, credentials_file: Path, scopes: List[str]):
        """Load service account credentials."""
        if not credentials_file.exists():
            raise FileNotFoundError(
                f"Service account file not found: {credentials_file}")
        print(str(credentials_file))
        try:
            return service_account.Credentials.from_service_account_file(
                filename=str(credentials_file), scopes=scopes)
        except Exception as e:
            sys.exit(f"Failed to load service account credentials: {e}")

    def get_spreadsheet(self, ranges=None, with_grid=False):
        try:
            req = self.spreadsheets.get(spreadsheetId=self.spreadsheet_id,
                                        includeGridData=with_grid,
                                        ranges=ranges)
            return req.execute()
        except HttpError as err:
            log.error(f"Google Sheets API error: {err}")
            return None

    def get_sheet_values(self, range_name: str):
        try:
            req = self.spreadsheets.values().get(
                spreadsheetId=self.spreadsheet_id, range=range_name)
            return req.execute().get("values", [])
        except HttpError as err:
            log.error(f"Google Sheets API error: {err}")
            return []

    def get_cells(self, sheet_name: str, cell_ref: str):
        """Get a single cell's value + properties"""
        try:
            req = self.spreadsheets.get(spreadsheetId=self.spreadsheet_id,
                                        ranges=f"{sheet_name}!{cell_ref}",
                                        includeGridData=True)
            result = req.execute()
            sheet = result["sheets"][0]
            row_data = sheet["data"][0]["rowData"]

            if not row_data or "values" not in row_data[0]:
                return None  # empty cell

            result = []
            for cell in row_data[0]["values"]:
                result.append({
                    "value":
                        cell.get("formattedValue"),
                    "background":
                        cell.get("effectiveFormat", {}).get("backgroundColor")
                })
            return result
        except HttpError as err:
            print(f"Google Sheets API error: {err}")
            return None


# ------------------- Parsers -------------------
def parse_date_cell(value: str, year: str = "2025") -> Optional[datetime]:
    """Convert dd.mm string into datetime object."""
    if not re.match(r"^\d{2}\.\d{2}$", value):
        return None
    try:
        return datetime.strptime(f"{value}-{year}", "%d.%m-%Y")
    except ValueError:
        log.debug(f"Cannot convert '{value}' to date")
        return None


def parse_category_cell(row: List[str]) -> str:
    """Return first non-empty cell in a row as category."""
    return next((cell for cell in row if cell.strip()), "")


def parse_item_cell(cell: str) -> Dict[str, Any]:

    log.debug(f"Cell value \"{cell}\"")

    result = {
        "title": None,
        "color": None,
        "sizes": [],
        "category": None,
        "description": cell
    }
    for char in "()-":
        cell = cell.replace(char, " ")

    for seg in cell.split():
        lower_seg = seg.lower()
        if seg.startswith("#"):
            result["title"] = seg
        elif seg.isdigit() and result["title"] == "#":
            result["title"] = f"#{seg}"
        elif seg.isdigit() and not result["title"]:
            result["title"] = f"#{seg}"
        elif seg in SIZES:
            result["sizes"].extend(seg.split("-"))
        elif lower_seg in COLOR_MAP:
            result["color"] = COLOR_MAP.get(lower_seg)
        elif lower_seg in CATEGORY_MAP:
            result["category"] = CATEGORY_MAP.get(lower_seg)

    return result


# ------------------- Database Operations -------------------
def check_item_exist(session: Session, title: str) -> Optional[Item]:
    return session.exec(select(Item).where(Item.title == title)).first()


def create_item(item_in: Dict[str, Any], row_number: int) -> Optional[Item]:
    """Create or reuse Item in DB with variants."""
    item_in["title"] = item_in.get("title") or f"#{row_number}"

    with Session(engine) as session:
        item = check_item_exist(session, item_in["title"])
        if item:
            log.warning(f"Item already exists: {item.title} (id={item.id})")
            if item.description == item_in["description"]:
                log.debug("Description unchanged, skipping")
                return item
            else:
                log.info("Different description → creating duplicate")
                item_in["title"] = f"{item_in['title']}_{row_number}"
                if check_item_exist(session, item_in["title"]):
                    log.error("Duplicate already exists, skipping")
                    return item
                item_in["tags"] = ["duplicate"]

        item = Item(**item_in)
        session.add(item)

        if not item_in["sizes"] and item_in.get("color"):
            session.add(
                ItemVariant(item_id=item.id, item=item, color=item_in["color"]))
        else:
            for size in set(item_in["sizes"]):
                session.add(
                    ItemVariant(item_id=item.id,
                                item=item,
                                size=size,
                                color=item_in.get("color")))

        try:
            session.commit()
            log.info(f"Item created: {item.title}")
            return item
        except Exception as e:
            session.rollback()
            log.error(f"Failed to create item '{item_in['title']}': {e}")
            return None


# ------------------- Main -------------------
def main():
    gs = GoogleSheet()
    spreadsheet = gs.get_spreadsheet()
    sheets = [i['properties']['title'] for i in spreadsheet['sheets']]
    for sheet in sheets:
        log.info(f"Processing {sheet} sheet")
        values = gs.get_sheet_values(sheet)

        if not values:
            log.warning(f"No data found in {sheet}")
            continue

        dates = []
        category = None
        for row_index, row in enumerate(values, start=1):
            if row_index == 1:
                log.info(f"Row {row_index}: Parsing header row as dates")
                dates = [parse_date_cell(cell) for cell in row if cell]
                continue

            if not row:
                log.debug(f"Row {row_index}: Skipping empty row")
                continue

            if not row[0]:
                # Category cell
                cat_value = parse_category_cell(row)
                category = CATEGORY_MAP.get(cat_value.lower(), cat_value)
                log.debug(f"Row {row_index}: Category set to {category}")
                continue

            # Item cell
            log.debug(f"Row {row_index}: Detecting Item from cell")
            item_data = parse_item_cell(row[0])
            item_data["category"] = item_data["category"] or category
            item = create_item(item_data, row_index)
            if not item:
                log.debug("Item not detected skeeped processing")
                continue

            # Order cell
            # if len(row) > 1:
            #     cell_ref = f"A{row_index}:AG{row_index}"
            #     values = gs.get_cells(sheet, cell_ref)
            #     print(values)

            # if row_index == 100:
            #     exit(0)

        exit(0)


if __name__ == "__main__":
    main()
