from fastapi import FastAPI, APIRouter, HTTPException, Query, Depends, status, UploadFile, File
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import osa
import logging
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional
import uuid
from datetime import datetime, timedelta
import jwt
import hashlib
import base64

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# Security
security = HTTPBearer()
SECRET_KEY = "vishal_jewellers_secret_key_2024"
ALGORITHM = "HS256"

# Define Models
class Product(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str
    price: float
    original_price: Optional[float] = None
    category: str
    metal_type: str
    weight: Optional[float] = None
    purity: Optional[str] = None
    image_url: str
    images: Optional[List[str]] = []
    rating: float = 4.5
    review_count: int = 0
    in_stock: bool = True
    stock_quantity: int = 1
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class ProductCreate(BaseModel):
    name: str
    description: str
    price: float
    original_price: Optional[float] = None
    category: str
    metal_type: str
    weight: Optional[float] = None
    purity: Optional[str] = None
    image_url: str
    images: Optional[List[str]] = []
    in_stock: bool = True
    stock_quantity: int = 1

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None
    original_price: Optional[float] = None
    category: Optional[str] = None
    metal_type: Optional[str] = None
    weight: Optional[float] = None
    purity: Optional[str] = None
    image_url: Optional[str] = None
    images: Optional[List[str]] = None
    in_stock: Optional[bool] = None
    stock_quantity: Optional[int] = None

class Order(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    customer_name: str
    customer_email: str
    customer_phone: str
    products: List[dict]
    total_amount: float
    status: str = "pending"  # pending, confirmed, processing, shipped, delivered, cancelled
    payment_status: str = "pending"  # pending, paid, failed, refunded
    shipping_address: dict
    order_date: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class OrderCreate(BaseModel):
    customer_name: str
    customer_email: str
    customer_phone: str
    products: List[dict]
    total_amount: float
    shipping_address: dict

class OrderUpdate(BaseModel):
    status: Optional[str] = None
    payment_status: Optional[str] = None

class Admin(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    username: str
    email: str
    password_hash: str
    role: str = "admin"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_login: Optional[datetime] = None

class AdminCreate(BaseModel):
    username: str
    email: str
    password: str

class AdminLogin(BaseModel):
    username: str
    password: str

class CartItem(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    product_id: str
    quantity: int = 1
    added_at: datetime = Field(default_factory=datetime.utcnow)

class User(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    email: str
    full_name: str
    phone: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

# Utility functions
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password: str, hashed_password: str) -> bool:
    return hash_password(password) == hashed_password

def create_jwt_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=24)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_jwt_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload
    except jwt.PyJWTError:
        return None

async def get_current_admin(credentials: HTTPAuthorizationCredentials = Depends(security)):
    token = credentials.credentials
    payload = verify_jwt_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    admin = await db.admins.find_one({"username": payload.get("sub")})
    if admin is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return Admin(**admin)

# Public Routes
@api_router.get("/")
async def root():
    return {"message": "Vishal Jewellers API"}

@api_router.get("/products", response_model=List[Product])
async def get_products(
    category: Optional[str] = None,
    metal_type: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    sort_by: Optional[str] = "created_at"
):
    filters = {}
    if category:
        filters["category"] = category
    if metal_type:
        filters["metal_type"] = metal_type
    if min_price is not None or max_price is not None:
        price_filter = {}
        if min_price is not None:
            price_filter["$gte"] = min_price
        if max_price is not None:
            price_filter["$lte"] = max_price
        filters["price"] = price_filter
    
    sort_field = sort_by if sort_by in ["price", "created_at", "rating"] else "created_at"
    sort_direction = 1 if sort_field != "price" else 1
    
    products = await db.products.find(filters).sort(sort_field, sort_direction).to_list(100)
    return [Product(**product) for product in products]

@api_router.get("/products/{product_id}", response_model=Product)
async def get_product(product_id: str):
    product = await db.products.find_one({"id": product_id})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return Product(**product)

@api_router.get("/categories")
async def get_categories():
    categories = await db.products.distinct("category")
    return {"categories": categories}

@api_router.get("/metal-types")
async def get_metal_types():
    metal_types = await db.products.distinct("metal_type")
    return {"metal_types": metal_types}

@api_router.post("/cart", response_model=CartItem)
async def add_to_cart(cart_item: CartItem):
    await db.cart.insert_one(cart_item.dict())
    return cart_item

@api_router.get("/cart", response_model=List[CartItem])
async def get_cart():
    cart_items = await db.cart.find().to_list(100)
    return [CartItem(**item) for item in cart_items]

@api_router.delete("/cart/{item_id}")
async def remove_from_cart(item_id: str):
    result = await db.cart.delete_one({"id": item_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Cart item not found")
    return {"message": "Item removed from cart"}

# Order routes
@api_router.post("/orders", response_model=Order)
async def create_order(order: OrderCreate):
    order_dict = order.dict()
    order_obj = Order(**order_dict)
    await db.orders.insert_one(order_obj.dict())
    return order_obj

@api_router.get("/orders/{order_id}", response_model=Order)
async def get_order(order_id: str):
    order = await db.orders.find_one({"id": order_id})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return Order(**order)

# Admin Authentication Routes
@api_router.post("/admin/register")
async def register_admin(admin_data: AdminCreate):
    # Check if admin already exists
    existing_admin = await db.admins.find_one({"$or": [{"username": admin_data.username}, {"email": admin_data.email}]})
    if existing_admin:
        raise HTTPException(status_code=400, detail="Admin already exists")
    
    # Create admin
    admin_dict = admin_data.dict()
    admin_dict["password_hash"] = hash_password(admin_data.password)
    del admin_dict["password"]
    
    admin_obj = Admin(**admin_dict)
    await db.admins.insert_one(admin_obj.dict())
    
    return {"message": "Admin registered successfully"}

@api_router.post("/admin/login")
async def login_admin(credentials: AdminLogin):
    admin = await db.admins.find_one({"username": credentials.username})
    if not admin or not verify_password(credentials.password, admin["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password"
        )
    
    # Update last login
    await db.admins.update_one(
        {"id": admin["id"]},
        {"$set": {"last_login": datetime.utcnow()}}
    )
    
    # Create JWT token
    access_token = create_jwt_token(data={"sub": admin["username"]})
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "admin": {
            "id": admin["id"],
            "username": admin["username"],
            "email": admin["email"],
            "role": admin["role"]
        }
    }

# Admin Protected Routes
@api_router.get("/admin/dashboard")
async def get_dashboard_stats(current_admin: Admin = Depends(get_current_admin)):
    # Get statistics
    total_products = await db.products.count_documents({})
    total_orders = await db.orders.count_documents({})
    pending_orders = await db.orders.count_documents({"status": "pending"})
    
    # Get sales data for last 30 days
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    sales_pipeline = [
        {"$match": {"order_date": {"$gte": thirty_days_ago}}},
        {"$group": {"_id": None, "total_sales": {"$sum": "$total_amount"}, "order_count": {"$sum": 1}}}
    ]
    sales_result = await db.orders.aggregate(sales_pipeline).to_list(1)
    total_sales = sales_result[0]["total_sales"] if sales_result else 0
    
    # Get recent orders
    recent_orders = await db.orders.find().sort("order_date", -1).limit(5).to_list(5)
    
    # Get low stock products
    low_stock = await db.products.find({"stock_quantity": {"$lte": 5}}).to_list(10)
    
    return {
        "stats": {
            "total_products": total_products,
            "total_orders": total_orders,
            "pending_orders": pending_orders,
            "total_sales": total_sales
        },
        "recent_orders": [Order(**order) for order in recent_orders],
        "low_stock_products": [Product(**product) for product in low_stock]
    }

@api_router.get("/admin/products", response_model=List[Product])
async def admin_get_products(current_admin: Admin = Depends(get_current_admin)):
    products = await db.products.find().sort("created_at", -1).to_list(100)
    return [Product(**product) for product in products]

@api_router.post("/admin/products", response_model=Product)
async def admin_create_product(product: ProductCreate, current_admin: Admin = Depends(get_current_admin)):
    product_dict = product.dict()
    product_obj = Product(**product_dict)
    await db.products.insert_one(product_obj.dict())
    return product_obj

@api_router.put("/admin/products/{product_id}", response_model=Product)
async def admin_update_product(product_id: str, product_update: ProductUpdate, current_admin: Admin = Depends(get_current_admin)):
    update_data = {k: v for k, v in product_update.dict().items() if v is not None}
    update_data["updated_at"] = datetime.utcnow()
    
    result = await db.products.update_one({"id": product_id}, {"$set": update_data})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Product not found")
    
    updated_product = await db.products.find_one({"id": product_id})
    return Product(**updated_product)

@api_router.delete("/admin/products/{product_id}")
async def admin_delete_product(product_id: str, current_admin: Admin = Depends(get_current_admin)):
    result = await db.products.delete_one({"id": product_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Product not found")
    return {"message": "Product deleted successfully"}

@api_router.get("/admin/orders", response_model=List[Order])
async def admin_get_orders(current_admin: Admin = Depends(get_current_admin)):
    orders = await db.orders.find().sort("order_date", -1).to_list(100)
    return [Order(**order) for order in orders]

@api_router.put("/admin/orders/{order_id}", response_model=Order)
async def admin_update_order(order_id: str, order_update: OrderUpdate, current_admin: Admin = Depends(get_current_admin)):
    update_data = {k: v for k, v in order_update.dict().items() if v is not None}
    update_data["updated_at"] = datetime.utcnow()
    
    result = await db.orders.update_one({"id": order_id}, {"$set": update_data})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Order not found")
    
    updated_order = await db.orders.find_one({"id": order_id})
    return Order(**updated_order)

@api_router.post("/admin/upload-image")
async def upload_image(file: UploadFile = File(...), current_admin: Admin = Depends(get_current_admin)):
    # Read file content and convert to base64
    content = await file.read()
    base64_image = base64.b64encode(content).decode('utf-8')
    
    # Create data URL
    file_extension = file.filename.split('.')[-1].lower()
    mime_type = f"image/{file_extension}" if file_extension in ['jpg', 'jpeg', 'png', 'gif', 'webp'] else "image/jpeg"
    data_url = f"data:{mime_type};base64,{base64_image}"
    
    return {"image_url": data_url}

# Initialize sample data and admin
@api_router.post("/initialize-data")
async def initialize_sample_data():
    # Check if data already exists
    existing_products = await db.products.count_documents({})
    if existing_products > 0:
        return {"message": "Data already initialized"}
    
    # Create default admin
    existing_admin = await db.admins.find_one({"username": "admin"})
    if not existing_admin:
        default_admin = Admin(
            username="admin",
            email="admin@vishaljewellers.com",
            password_hash=hash_password("admin123"),
            role="admin"
        )
        await db.admins.insert_one(default_admin.dict())
    
    sample_products = [
        {
            "name": "Elegant Gold Ring",
            "description": "Beautifully crafted 18k gold ring with intricate traditional design. Perfect for special occasions and daily wear.",
            "price": 25000.0,
            "original_price": 30000.0,
            "category": "Rings",
            "metal_type": "Gold",
            "weight": 8.5,
            "purity": "18K",
            "image_url": "https://images.unsplash.com/photo-1617038220319-276d3cfab638?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NTY2Njd8MHwxfHNlYXJjaHwxfHxqZXdlbHJ5fGVufDB8fHx8MTc1NDI5NDAxNHww&ixlib=rb-4.1.0&q=85",
            "images": [
                "https://images.unsplash.com/photo-1617038220319-276d3cfab638?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NTY2Njd8MHwxfHNlYXJjaHwxfHxqZXdlbHJ5fGVufDB8fHx8MTc1NDI5NDAxNHww&ixlib=rb-4.1.0&q=85"
            ],
            "rating": 4.8,
            "review_count": 45,
            "in_stock": True,
            "stock_quantity": 5
        },
        {
            "name": "Premium Gold Necklace",
            "description": "Stunning 22k gold necklace with traditional Indian craftsmanship. A timeless piece for special occasions.",
            "price": 85000.0,
            "original_price": 95000.0,
            "category": "Necklaces",
            "metal_type": "Gold",
            "weight": 35.2,
            "purity": "22K",
            "image_url": "https://images.unsplash.com/photo-1616837874254-8d5aaa63e273?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NTY2Njd8MHwxfHNlYXJjaHwyfHxqZXdlbHJ5fGVufDB8fHx8MTc1NDI5NDAxNHww&ixlib=rb-4.1.0&q=85",
            "images": [
                "https://images.unsplash.com/photo-1616837874254-8d5aaa63e273?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NTY2Njd8MHwxfHNlYXJjaHwyfHxqZXdlbHJ5fGVufDB8fHx8MTc1NDI5NDAxNHww&ixlib=rb-4.1.0&q=85"
            ],
            "rating": 4.9,
            "review_count": 78,
            "in_stock": True,
            "stock_quantity": 3
        },
        {
            "name": "Delicate Pendant Necklace",
            "description": "Exquisite gold pendant necklace with fine detailing. Perfect for everyday elegance and formal occasions.",
            "price": 45000.0,
            "original_price": 52000.0,
            "category": "Necklaces",
            "metal_type": "Gold",
            "weight": 15.8,
            "purity": "18K",
            "image_url": "https://images.unsplash.com/photo-1600721391689-2564bb8055de?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NTY2Njd8MHwxfHNlYXJjaHwzfHxqZXdlbHJ5fGVufDB8fHx8MTc1NDI5NDAxNHww&ixlib=rb-4.1.0&q=85",
            "images": [
                "https://images.unsplash.com/photo-1600721391689-2564bb8055de?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NTY2Njd8MHwxfHNlYXJjaHwzfHxqZXdlbHJ5fGVufDB8fHx8MTc1NDI5NDAxNHww&ixlib=rb-4.1.0&q=85"
            ],
            "rating": 4.7,
            "review_count": 32,
            "in_stock": True,
            "stock_quantity": 8
        },
        {
            "name": "Classic Gold Bracelet",
            "description": "Elegant chain bracelet crafted in pure gold. A versatile piece that complements any outfit.",
            "price": 35000.0,
            "original_price": 40000.0,
            "category": "Bracelets",
            "metal_type": "Gold",
            "weight": 18.3,
            "purity": "22K",
            "image_url": "https://images.unsplash.com/photo-1602173574767-37ac01994b2a?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NTY2Njd8MHwxfHNlYXJjaHw0fHxqZXdlbHJ5fGVufDB8fHx8MTc1NDI5NDAxNHww&ixlib=rb-4.1.0&q=85",
            "images": [
                "https://images.unsplash.com/photo-1602173574767-37ac01994b2a?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NTY2Njd8MHwxfHNlYXJjaHw0fHxqZXdlbHJ5fGVufDB8fHx8MTc1NDI5NDAxNHww&ixlib=rb-4.1.0&q=85"
            ],
            "rating": 4.6,
            "review_count": 28,
            "in_stock": True,
            "stock_quantity": 12
        },
        {
            "name": "Diamond Solitaire Ring",
            "description": "Exquisite diamond solitaire ring set in platinum. A symbol of eternal love and commitment.",
            "price": 120000.0,
            "original_price": 135000.0,
            "category": "Rings",
            "metal_type": "Platinum",
            "weight": 6.2,
            "purity": "PT950",
            "image_url": "https://images.unsplash.com/photo-1599707367072-cd6ada2bc375?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NDk1NzZ8MHwxfHNlYXJjaHwxfHxkaWFtb25kfGVufDB8fHx8MTc1NDI5NDAxOXww&ixlib=rb-4.1.0&q=85",
            "images": [
                "https://images.unsplash.com/photo-1599707367072-cd6ada2bc375?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NDk1NzZ8MHwxfHNlYXJjaHwxfHxkaWFtb25kfGVufDB8fHx8MTc1NDI5NDAxOXww&ixlib=rb-4.1.0&q=85"
            ],
            "rating": 5.0,
            "review_count": 95,
            "in_stock": True,
            "stock_quantity": 2
        },
        {
            "name": "Premium Diamond Earrings",
            "description": "Stunning diamond earrings with brilliant cut stones. Perfect for special occasions and celebrations.",
            "price": 95000.0,
            "original_price": 110000.0,
            "category": "Earrings",
            "metal_type": "Gold",
            "weight": 8.7,
            "purity": "18K",
            "image_url": "https://images.unsplash.com/photo-1596213411964-ee96819a396c?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NDk1NzZ8MHwxfHNlYXJjaHwyfHxkaWFtb25kfGVufDB8fHx8MTc1NDI5NDAxOXww&ixlib=rb-4.1.0&q=85",
            "images": [
                "https://images.unsplash.com/photo-1596213411964-ee96819a396c?crop=entropy&cs=srgb&fm=jpg&ixid=M3w3NDk1NzZ8MHwxfHNlYXJjaHwyfHxkaWFtb25kfGVufDB8fHx8MTc1NDI5NDAxOXww&ixlib=rb-4.1.0&q=85"
            ],
            "rating": 4.9,
            "review_count": 67,
            "in_stock": True,
            "stock_quantity": 6
        }
    ]
    
    for product_data in sample_products:
        product_obj = Product(**product_data)
        await db.products.insert_one(product_obj.dict())
    
    # Create sample orders
    sample_orders = [
        {
            "customer_name": "Priya Sharma",
            "customer_email": "priya@example.com",
            "customer_phone": "+91 9876543210",
            "products": [{"name": "Elegant Gold Ring", "quantity": 1, "price": 25000}],
            "total_amount": 25000,
            "status": "confirmed",
            "payment_status": "paid",
            "shipping_address": {
                "street": "123 MG Road",
                "city": "Mumbai",
                "state": "Maharashtra",
                "pincode": "400001"
            },
            "order_date": datetime.utcnow() - timedelta(days=2)
        },
        {
            "customer_name": "Rajesh Patel",
            "customer_email": "rajesh@example.com", 
            "customer_phone": "+91 9876543211",
            "products": [{"name": "Premium Gold Necklace", "quantity": 1, "price": 85000}],
            "total_amount": 85000,
            "status": "processing",
            "payment_status": "paid",
            "shipping_address": {
                "street": "456 FC Road",
                "city": "Pune",
                "state": "Maharashtra", 
                "pincode": "411005"
            },
            "order_date": datetime.utcnow() - timedelta(days=1)
        }
    ]
    
    for order_data in sample_orders:
        order_obj = Order(**order_data)
        await db.orders.insert_one(order_obj.dict())
    
    return {"message": f"Initialized {len(sample_products)} products, {len(sample_orders)} orders, and admin account (username: admin, password: admin123)"}

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
