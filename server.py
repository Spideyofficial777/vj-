from fastapi import FastAPI, HTTPException, Depends, Body
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field
from typing import List, Optional
import os
import uuid
import bcrypt
from datetime import datetime

# Initialize FastAPI app
app = FastAPI(title="Vishal Jwellers API", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MongoDB connection
MONGO_URL = os.environ.get('MONGO_URL', 'mongodb+srv://halabe8690:0U7oU4GKtkiQsBGx@cluster0.a9ui5gv.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0')
client = AsyncIOMotorClient(MONGO_URL)
db = client.vishal_jwellers

# Collections
users_collection = db.users
products_collection = db.products
orders_collection = db.orders
cart_collection = db.cart
admins_collection = db.admins

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

# Initialize sample data
@app.on_event("startup")
async def startup_db():
    """Initialize database with sample products and admin user"""
    
    # Check if admin already exists
    existing_admin = await admins_collection.count_documents({})
    
    if existing_admin == 0:
        # Create default admin user
        admin_password = hash_password("admin123")
        default_admin = Admin(
            name="Admin User",
            email="admin@vishaljwellers.com",
            password=admin_password,
            role="admin"
        )
        await admins_collection.insert_one(default_admin.dict())
        print("Default admin user created!")
        print("Email: admin@vishaljwellers.com")
        print("Password: admin123")
    
    # Check if products already exist
    existing_products = await products_collection.count_documents({})
    
    if existing_products == 0:
        sample_products = [
            {
                "id": str(uuid.uuid4()),
                "name": "Royal Gold Ring",
                "category": "rings",
                "price": 25000.0,
                "description": "Exquisite handcrafted gold ring with intricate designs",
                "image": "https://images.unsplash.com/photo-1605100804567-1ffe942b5cd6",
                "stock": 10,
                "created_at": datetime.utcnow()
            },
            {
                "id": str(uuid.uuid4()),
                "name": "Diamond Solitaire Ring",
                "category": "rings",
                "price": 85000.0,
                "description": "Brilliant cut diamond solitaire in platinum setting",
                "image": "https://images.unsplash.com/photo-1605100804567-1ffe942b5cd6",
                "stock": 5,
                "created_at": datetime.utcnow()
            },
            {
                "id": str(uuid.uuid4()),
                "name": "Pearl Necklace Set",
                "category": "necklaces",
                "price": 45000.0,
                "description": "Elegant cultured pearl necklace with matching earrings",
                "image": "https://images.unsplash.com/photo-1614178113230-87b333095202",
                "stock": 8,
                "created_at": datetime.utcnow()
            },
            {
                "id": str(uuid.uuid4()),
                "name": "Gold Chain Necklace",
                "category": "necklaces",
                "price": 35000.0,
                "description": "22K gold chain necklace with traditional patterns",
                "image": "https://images.unsplash.com/photo-1574281852611-b2f04c86a520",
                "stock": 15,
                "created_at": datetime.utcnow()
            },
            {
                "id": str(uuid.uuid4()),
                "name": "Diamond Drop Earrings",
                "category": "earrings",
                "price": 55000.0,
                "description": "Stunning diamond drop earrings in white gold",
                "image": "https://images.unsplash.com/photo-1630524250640-97602e7324cc",
                "stock": 12,
                "created_at": datetime.utcnow()
            },
            {
                "id": str(uuid.uuid4()),
                "name": "Gold Hoops",
                "category": "earrings",
                "price": 18000.0,
                "description": "Classic gold hoop earrings for everyday elegance",
                "image": "https://images.unsplash.com/photo-1614178113230-87b333095202",
                "stock": 20,
                "created_at": datetime.utcnow()
            },
            {
                "id": str(uuid.uuid4()),
                "name": "Designer Gold Bangles",
                "category": "bangles",
                "price": 42000.0,
                "description": "Set of 2 designer gold bangles with carved motifs",
                "image": "https://images.unsplash.com/photo-1574281852611-b2f04c86a520",
                "stock": 6,
                "created_at": datetime.utcnow()
            },
            {
                "id": str(uuid.uuid4()),
                "name": "Diamond Tennis Bracelet",
                "category": "bangles",
                "price": 125000.0,
                "description": "Luxury diamond tennis bracelet in white gold",
                "image": "https://images.unsplash.com/photo-1630524250640-97602e7324cc",
                "stock": 3,
                "created_at": datetime.utcnow()
            }
        ]
        
        await products_collection.insert_many(sample_products)
        print("Sample products initialized!")

# Authentication utilities
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

# API Routes

@app.get("/")
async def root():
    return {"message": "Welcome to Vishal Jwellers API"}

@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "service": "Vishal Jwellers API"}

# Authentication routes
@app.post("/api/auth/signup")
async def signup(user_data: UserSignup):
    """User registration"""
    try:
        # Check if user already exists
        existing_user = await users_collection.find_one({"email": user_data.email})
        if existing_user:
            raise HTTPException(status_code=400, detail="Email already registered")
        
        # Hash password
        hashed_password = hash_password(user_data.password)
        
        # Create user
        user = User(
            name=user_data.name,
            email=user_data.email,
            password=hashed_password
        )
        
        # Insert user to database
        await users_collection.insert_one(user.dict())
        
        return {"message": "User created successfully", "user_id": user.id}
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"Signup error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/api/auth/login")
async def login(login_data: UserLogin):
    """User login"""
    try:
        # Find user by email
        user = await users_collection.find_one({"email": login_data.email})
        if not user:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        # Verify password
        if not verify_password(login_data.password, user["password"]):
            raise HTTPException(status_code=401, detail="Invalid credentials")
        
        # Return user data (excluding password)
        return {
            "message": "Login successful",
            "user": {
                "id": user["id"],
                "name": user["name"],
                "email": user["email"]
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"Login error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# Admin authentication routes
@app.post("/api/admin/login")
async def admin_login(login_data: AdminLogin):
    """Admin login"""
    try:
        # Find admin by email
        admin = await admins_collection.find_one({"email": login_data.email})
        if not admin:
            raise HTTPException(status_code=401, detail="Invalid admin credentials")
        
        # Verify password
        if not verify_password(login_data.password, admin["password"]):
            raise HTTPException(status_code=401, detail="Invalid admin credentials")
        
        # Return admin data (excluding password)
        return {
            "message": "Admin login successful",
            "admin": {
                "id": admin["id"],
                "name": admin["name"],
                "email": admin["email"],
                "role": admin["role"]
            }
        }
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"Admin login error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# Product routes
@app.get("/api/products")
async def get_products(category: Optional[str] = None):
    """Get all products or by category"""
    try:
        query = {}
        if category and category != "all":
            query["category"] = category
        
        products_cursor = products_collection.find(query)
        products = []
        
        async for product in products_cursor:
            # Remove MongoDB _id field and ensure proper types
            product.pop("_id", None)
            products.append(product)
        
        return products
    
    except Exception as e:
        print(f"Get products error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/api/products/{product_id}")
async def get_product(product_id: str):
    """Get single product by ID"""
    try:
        product = await products_collection.find_one({"id": product_id})
        if not product:
            raise HTTPException(status_code=404, detail="Product not found")
        
        product.pop("_id", None)
        return product
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"Get product error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/api/products")
async def create_product(product: Product):
    """Create new product (Admin only)"""
    try:
        await products_collection.insert_one(product.dict())
        return {"message": "Product created successfully", "product_id": product.id}
    
    except Exception as e:
        print(f"Create product error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.put("/api/products/{product_id}")
async def update_product(product_id: str, product_data: dict = Body(...)):
    """Update product (Admin only)"""
    try:
        result = await products_collection.update_one(
            {"id": product_id},
            {"$set": product_data}
        )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Product not found")
        
        return {"message": "Product updated successfully"}
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"Update product error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.delete("/api/products/{product_id}")
async def delete_product(product_id: str):
    """Delete product (Admin only)"""
    try:
        result = await products_collection.delete_one({"id": product_id})
        
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Product not found")
        
        return {"message": "Product deleted successfully"}
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"Delete product error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# Cart routes
@app.get("/api/cart/{user_id}")
async def get_cart(user_id: str):
    """Get user's cart items"""
    try:
        cart_cursor = cart_collection.find({"user_id": user_id})
        cart_items = []
        
        async for item in cart_cursor:
            item.pop("_id", None)
            # Get product details
            product = await products_collection.find_one({"id": item["product_id"]})
            if product:
                product.pop("_id", None)
                item["product"] = product
            cart_items.append(item)
        
        return cart_items
    
    except Exception as e:
        print(f"Get cart error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/api/cart")
async def add_to_cart(cart_item: CartItem):
    """Add item to cart"""
    try:
        # Check if item already exists in cart
        existing_item = await cart_collection.find_one({
            "user_id": cart_item.user_id,
            "product_id": cart_item.product_id
        })
        
        if existing_item:
            # Update quantity
            await cart_collection.update_one(
                {"id": existing_item["id"]},
                {"$set": {"quantity": existing_item["quantity"] + cart_item.quantity}}
            )
        else:
            # Add new item
            await cart_collection.insert_one(cart_item.dict())
        
        return {"message": "Item added to cart successfully"}
    
    except Exception as e:
        print(f"Add to cart error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.delete("/api/cart/{cart_item_id}")
async def remove_from_cart(cart_item_id: str):
    """Remove item from cart"""
    try:
        result = await cart_collection.delete_one({"id": cart_item_id})
        
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Cart item not found")
        
        return {"message": "Item removed from cart successfully"}
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"Remove from cart error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# Order routes
@app.get("/api/orders/{user_id}")
async def get_user_orders(user_id: str):
    """Get user's orders"""
    try:
        orders_cursor = orders_collection.find({"user_id": user_id})
        orders = []
        
        async for order in orders_cursor:
            order.pop("_id", None)
            orders.append(order)
        
        return orders
    
    except Exception as e:
        print(f"Get orders error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.post("/api/orders")
async def create_order(order: Order):
    """Create new order"""
    try:
        await orders_collection.insert_one(order.dict())
        
        # Clear user's cart after successful order
        await cart_collection.delete_many({"user_id": order.user_id})
        
        return {"message": "Order created successfully", "order_id": order.id}
    
    except Exception as e:
        print(f"Create order error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

# Admin routes
@app.get("/api/admin/orders")
async def get_all_orders():
    """Get all orders (Admin only)"""
    try:
        orders_cursor = orders_collection.find({})
        orders = []
        
        async for order in orders_cursor:
            order.pop("_id", None)
            # Get user details
            user = await users_collection.find_one({"id": order["user_id"]})
            if user:
                order["user_name"] = user["name"]
                order["user_email"] = user["email"]
            orders.append(order)
        
        return orders
    
    except Exception as e:
        print(f"Get all orders error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/api/admin/users")
async def get_all_users():
    """Get all users (Admin only)"""
    try:
        users_cursor = users_collection.find({})
        users = []
        
        async for user in users_cursor:
            user.pop("_id", None)
            user.pop("password", None)  # Don't return password
            users.append(user)
        
        return users
    
    except Exception as e:
        print(f"Get all users error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.put("/api/admin/orders/{order_id}")
async def update_order_status(order_id: str, status_data: dict = Body(...)):
    """Update order status (Admin only)"""
    try:
        result = await orders_collection.update_one(
            {"id": order_id},
            {"$set": {"status": status_data.get("status")}}
        )
        
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Order not found")
        
        return {"message": "Order status updated successfully"}
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"Update order status error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@app.get("/api/admin/stats")
async def get_admin_stats():
    """Get admin dashboard statistics"""
    try:
        # Get counts
        total_products = await products_collection.count_documents({})
        total_users = await users_collection.count_documents({})
        total_orders = await orders_collection.count_documents({})
        pending_orders = await orders_collection.count_documents({"status": "pending"})
        
        # Calculate total revenue
        revenue_cursor = orders_collection.aggregate([
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
    
    except Exception as e:
        print(f"Get admin stats error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)