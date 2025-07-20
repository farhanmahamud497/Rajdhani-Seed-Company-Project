-- schema.sql
PRAGMA foreign_keys = OFF;

DROP TABLE IF EXISTS invoice_items;
DROP TABLE IF EXISTS invoices;
DROP TABLE IF EXISTS products;

PRAGMA foreign_keys = ON;

CREATE TABLE products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    description TEXT,
    packing TEXT NOT NULL,
    rate REAL NOT NULL CHECK (rate >= 0),
    quantity INTEGER NOT NULL DEFAULT 0 CHECK (quantity >= 0),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_number TEXT NOT NULL UNIQUE,
    buyer_name TEXT NOT NULL,
    buyer_address TEXT NOT NULL,
    buyer_mobile TEXT NOT NULL,
    payment_method TEXT NOT NULL,
    goods_description TEXT,
    total_amount REAL NOT NULL CHECK (total_amount >= 0),
    amount_in_words TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE invoice_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    product_name TEXT NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    packing TEXT NOT NULL,
    rate REAL NOT NULL CHECK (rate >= 0),
    amount REAL NOT NULL CHECK (amount >= 0),
    FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE CASCADE,
    FOREIGN KEY (product_id) REFERENCES products(id)
);

-- Create trigger to update product quantity when invoice items are added
CREATE TRIGGER update_product_quantity
AFTER INSERT ON invoice_items
BEGIN
    UPDATE products 
    SET quantity = quantity - NEW.quantity 
    WHERE id = NEW.product_id;
END;

-- Create trigger to update timestamps on product updates
CREATE TRIGGER update_product_timestamp
AFTER UPDATE ON products
FOR EACH ROW
BEGIN
    UPDATE products 
    SET updated_at = CURRENT_TIMESTAMP 
    WHERE id = OLD.id;
END;

-- Create trigger to prevent product deletion if used in invoices
CREATE TRIGGER prevent_product_deletion
BEFORE DELETE ON products
FOR EACH ROW
BEGIN
    SELECT CASE
        WHEN (SELECT COUNT(*) FROM invoice_items WHERE product_id = OLD.id) > 0
        THEN RAISE(ABORT, 'Cannot delete product referenced in invoices')
    END;
END;