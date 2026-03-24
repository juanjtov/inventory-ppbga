import csv
import io
from app.database import supabase


def import_csv(file_content: bytes) -> dict:
    """Import products from CSV file.

    Handles: BOM, empty rows, column mapping (Sotck Actual typo),
    price parsing ($X,XXX → int), NA → service.
    """
    # Try UTF-8 with BOM, fallback to latin-1
    try:
        text = file_content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = file_content.decode("latin-1")

    reader = csv.reader(io.StringIO(text))
    rows = list(reader)

    # Find header row (contains "Producto")
    header_idx = None
    for i, row in enumerate(rows):
        cleaned = [c.strip() for c in row]
        if "Producto" in cleaned:
            header_idx = i
            break

    if header_idx is None:
        return {"created": 0, "skipped": 0, "errors": ["No se encontró la fila de encabezado"]}

    headers = [c.strip() for c in rows[header_idx]]

    # Map column indices
    col_map = {}
    for i, h in enumerate(headers):
        if h == "Producto":
            col_map["name"] = i
        elif h == "Categoria":
            col_map["category"] = i
        elif h == "Proveedor":
            col_map["supplier"] = i
        elif h == "Precio":
            col_map["price"] = i
        elif h in ("Sotck Actual", "Stock Actual"):
            col_map["stock"] = i

    required = ["name", "category", "supplier", "price", "stock"]
    missing = [k for k in required if k not in col_map]
    if missing:
        return {"created": 0, "skipped": 0, "errors": [f"Columnas faltantes: {', '.join(missing)}"]}

    # Cache for categories and suppliers
    cat_cache = {}
    sup_cache = {}

    # Load existing categories
    cats = supabase.table("categories").select("id, name").execute()
    for c in cats.data:
        cat_cache[c["name"].strip().lower()] = c["id"]

    # Load existing suppliers
    sups = supabase.table("suppliers").select("id, name").execute()
    for s in sups.data:
        sup_cache[s["name"].strip().lower()] = s["id"]

    created = 0
    skipped = 0
    errors = []

    data_rows = rows[header_idx + 1:]
    for row_num, row in enumerate(data_rows, start=header_idx + 2):
        try:
            # Skip empty rows
            if not row or all(c.strip() == "" for c in row):
                continue

            name = row[col_map["name"]].strip()
            if not name:
                continue

            category_name = row[col_map["category"]].strip()
            supplier_name = row[col_map["supplier"]].strip()
            price_str = row[col_map["price"]].strip()
            stock_str = row[col_map["stock"]].strip()

            if not category_name or not supplier_name or not price_str:
                errors.append(f"Fila {row_num}: datos incompletos para '{name}'")
                continue

            # Parse price: remove $ and , then convert to int
            price = int(price_str.replace("$", "").replace(",", "").strip())

            # Parse stock: NA means service
            if stock_str.upper() == "NA" or stock_str == "":
                product_type = "service"
                stock = None
            else:
                product_type = "product"
                stock = int(stock_str)

            # Find or create category
            cat_key = category_name.lower()
            if cat_key not in cat_cache:
                result = supabase.table("categories").insert({"name": category_name}).execute()
                cat_cache[cat_key] = result.data[0]["id"]
            category_id = cat_cache[cat_key]

            # Find or create supplier
            sup_key = supplier_name.lower()
            if sup_key not in sup_cache:
                result = supabase.table("suppliers").insert({"name": supplier_name}).execute()
                sup_cache[sup_key] = result.data[0]["id"]
            supplier_id = sup_cache[sup_key]

            # Check for duplicate (name + supplier)
            existing = (
                supabase.table("products")
                .select("id")
                .eq("name", name)
                .eq("supplier_id", supplier_id)
                .execute()
            )
            if existing.data:
                skipped += 1
                continue

            # Insert product
            product_data = {
                "name": name,
                "category_id": category_id,
                "supplier_id": supplier_id,
                "sale_price": price,
                "purchase_price": 0,
                "stock": stock,
                "type": product_type,
                "min_stock_alert": 5,
            }
            supabase.table("products").insert(product_data).execute()
            created += 1

        except Exception as e:
            name_val = row[col_map["name"]].strip() if len(row) > col_map["name"] else "desconocido"
            errors.append(f"Fila {row_num}: error procesando '{name_val}' — {str(e)}")

    return {"created": created, "skipped": skipped, "errors": errors}
