from fastapi import FastAPI, HTTPException, Depends, Body, status
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field
from typing import List, Optional
import os
import uuid
import bcrypt
from datetime import datetime
from contextlib import asynccontextmanager

# MongoDB connection details
MONGO_URL = "mongodb+srv://halabe8690:0U7oU4GKtkiQsBGx@cluster0.a9ui5gv.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
DB_NAME = "vishal_jwellers"

# Initialize FastAPI app with lifespan
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize MongoDB connection
    app.mongodb_client = AsyncIOMotorClient(MONGO_URL)
    app.mongodb = app.mongodb_client[DB_NAME]
    
    # Initialize sample data
    await startup_db(app.mongodb)
    yield
    
    # Close MongoDB connection
    app.mongodb_client.close()

app = FastAPI(
    title="Vishal Jwellers API",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models
class User(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    email: str
    password: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Admin(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    email: str
    password: str
    role: str = "admin"
    created_at: datetime = Field(default_factory=datetime.utcnow)

class UserLogin(BaseModel):
    email: str
    password: str

class AdminLogin(BaseModel):
    email: str
    password: str

class UserSignup(BaseModel):
    name: str
    email: str
    password: str

class Product(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    category: str
    price: float
    description: str = ""
    image: str = ""
    stock: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)

class CartItem(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    product_id: str
    quantity: int = 1
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Order(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    items: List[dict]
    total_amount: float
    status: str = "pending"
    created_at: datetime = Field(default_factory=datetime.utcnow)

# Helper functions
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

async def startup_db(db):
    """Initialize database with sample products and admin user"""
    # Check if admin already exists
    existing_admin = await db.admins.count_documents({})
    
    if existing_admin == 0:
        # Create default admin user
        admin_password = hash_password("admin123")
        default_admin = Admin(
            name="Admin User",
            email="admin@vishaljwellers.com",
            password=admin_password,
            role="admin"
        )
        await db.admins.insert_one(default_admin.dict())
        print("Default admin user created!")
        print("Email: admin@vishaljwellers.com")
        print("Password: admin123")
    
    # Check if products already exist
    existing_products = await db.products.count_documents({})
    
    if existing_products == 0:
        sample_products = [
            {
                "id": str(uuid.uuid4()),
                "name": "Royal Gold Ring",
                "category": "rings",
                "price": 25000.0,
                "description": "Exquisite handcrafted gold ring with intricate designs",
                "image": "https://example.com/ring1.jpg",
                "stock": 10,
                "created_at": datetime.utcnow()
            },
            {
                "id": str(uuid.uuid4()),
                "name": "Diamond Solitaire Ring",
                "category": "rings",
                "price": 85000.0,
                "description": "Brilliant cut diamond solitaire in platinum setting",
                "image": "https://example.com/ring2.jpg",
                "stock": 5,
                "created_at": datetime.utcnow()
            }
        ]
        await db.products.insert_many(sample_products)
        print("Sample products initialized!")

# API Routes
@app.get("/")
async def root():
    return {"message": "Welcome to Vishal Jwellers API"}

@app.get("/api/health")
async def health_check():
    return {
        "status": "healthy",
        "database": "connected" if app.mongodb_client else "disconnected",
        "service": "Vishal Jwellers API"
    }

# Authentication routes
@app.post("/api/auth/signup", status_code=status.HTTP_201_CREATED)
async def signup(user_data: UserSignup):
    """User registration"""
    # Check if user already exists
    existing_user = await app.mongodb.users.find_one({"email": user_data.email})
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered"
        )
    
    # Hash password and create user
    user = User(
        name=user_data.name,
        email=user_data.email,
        password=hash_password(user_data.password)
    )
    
    await app.mongodb.users.insert_one(user.dict())
    return {"message": "User created successfully", "user_id": user.id}

@app.post("/api/auth/login")
async def login(login_data: UserLogin):
    """User login"""
    user = await app.mongodb.users.find_one({"email": login_data.email})
    if not user or not verify_password(login_data.password, user["password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials"
        )
    
    return {
        "message": "Login successful",
        "user": {
            "id": user["id"],
            "name": user["name"],
            "email": user["email"]
        }
    }

# Product routes
@app.get("/api/products")
async def get_products(category: Optional[str] = None):
    """Get all products or by category"""
    query = {"category": category.lower()} if category and category.lower() != "all" else {}
    
    products = []
    async for product in app.mongodb.products.find(query):
        product.pop("_id", None)
        products.append(product)
    
    return products if products else {"message": "No products found", "products": []}

@app.get("/api/products/{product_id}")
async def get_product(product_id: str):
    """Get single product by ID"""
    product = await app.mongodb.products.find_one({"id": product_id})
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found"
        )
    
    product.pop("_id", None)
    return product

@app.post("/api/products", status_code=status.HTTP_201_CREATED)
async def create_product(product: Product):
    """Create new product (Admin only)"""
    await app.mongodb.products.insert_one(product.dict())
    return {"message": "Product created successfully", "product_id": product.id}

# Cart routes
@app.get("/api/cart/{user_id}")
async def get_cart(user_id: str):
    """Get user's cart items"""
    cart_items = []
    async for item in app.mongodb.cart.find({"user_id": user_id}):
        item.pop("_id", None)
        product = await app.mongodb.products.find_one({"id": item["product_id"]})
        if product:
            product.pop("_id", None)
            item["product"] = product
        cart_items.append(item)
    
    return cart_items

# Order routes
@app.get("/api/orders/{user_id}")
async def get_user_orders(user_id: str):
    """Get user's orders"""
    orders = []
    async for order in app.mongodb.orders.find({"user_id": user_id}):
        order.pop("_id", None)
        orders.append(order)
    
    return orders

# Admin routes
@app.get("/api/admin/stats")
async def get_admin_stats():
    """Get admin dashboard statistics"""
    total_products = await app.mongodb.products.count_documents({})
    total_users = await app.mongodb.users.count_documents({})
    total_orders = await app.mongodb.orders.count_documents({})
    pending_orders = await app.mongodb.orders.count_documents({"status": "pending"})
    
    revenue_cursor = app.mongodb.orders.aggregate([
        {"$match": {"status": {"$in": ["completed", "delivered"]}}},
        {"$group": {"_id": None, "total": {"$sum": "$total_amount"}}}
    ])
    revenue_result = await revenue_cursor.to_list(1)
    total_revenue = revenue_result[0]["total"] if revenue_result else 0
    
    return {
        "total_products": total_products,
        "total_users": total_users,
        "total_orders": total_orders,
        "pending_orders": pending_orders,
        "total_revenue": total_revenue
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
