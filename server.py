import os
import uuid
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Union

from fastapi import (
    FastAPI, 
    HTTPException, 
    Depends, 
    status, 
    Request,
    BackgroundTasks,
    Body
)
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder

from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import (
    BaseModel, 
    Field, 
    EmailStr, 
    validator,
    confloat
)
import bcrypt
from jose import JWTError, jwt
from passlib.context import CryptContext

# ====== Configuration ======
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-123")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# MongoDB Config
MONGO_URI = "mongodb+srv://halabe8690:0U7oU4GKtkiQsBGx@cluster0.a9ui5gv.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
DB_NAME = "vishal_jewellers"

# ====== FastAPI App ======
app = FastAPI(
    title="💎 Vishal Jewellers API",
    description="Premium Jewellery E-Commerce Backend",
    version="3.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS Middleware (Fixed for OPTIONS requests)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ====== MongoDB Connection ======
client = AsyncIOMotorClient(MONGO_URI)
db = client[DB_NAME]

# Collections
users_collection = db.users
products_collection = db.products
orders_collection = db.orders
cart_collection = db.cart
admins_collection = db.admins

# ====== Security ======
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# ====== Pydantic Models ======
class UserBase(BaseModel):
    name: str
    email: EmailStr

class UserCreate(UserBase):
    password: str

class User(UserBase):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)

class Admin(User):
    role: str = "admin"

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class AdminLogin(BaseModel):
    email: EmailStr
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str

class Product(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    category: str
    price: confloat(gt=0)
    description: Optional[str] = ""
    image_url: Optional[str] = ""
    stock: int = Field(ge=0)
    discount: Optional[confloat(ge=0, le=100)] = 0.0
    is_featured: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)

class CartItem(BaseModel):
    product_id: str
    quantity: int = Field(ge=1, le=10)

class Order(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    items: List[Dict[str, Union[str, int]]]
    total_amount: float
    status: str = "pending"
    payment_method: str
    shipping_address: str
    created_at: datetime = Field(default_factory=datetime.utcnow)

# ====== Helper Functions ======
def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
        if email is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials"
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )
    
    user = await users_collection.find_one({"email": email})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user

async def get_current_admin(user: dict = Depends(get_current_user)):
    if user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )
    return user

# ====== API Endpoints ======
@app.get("/")
async def root():
    return {"message": "Vishal Jewellers API is running!"}

@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "database": "connected"}

# Authentication Endpoints
@app.post("/api/auth/signup", response_model=User, status_code=201)
async def signup(user_data: UserCreate):
    if await users_collection.find_one({"email": user_data.email}):
        raise HTTPException(status_code=400, detail="Email already registered")
    
    user = User(
        name=user_data.name,
        email=user_data.email,
        password=hash_password(user_data.password)
    )
    
    await users_collection.insert_one(jsonable_encoder(user))
    return user

@app.post("/api/auth/login", response_model=Token)
async def login(form_data: UserLogin):
    user = await users_collection.find_one({"email": form_data.email})
    if not user or not verify_password(form_data.password, user["password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    access_token = create_access_token(
        data={"sub": user["email"]},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return {"access_token": access_token, "token_type": "bearer"}

# Product Endpoints (Fixed double-slash issue)
@app.get("/api/products")
@app.get("//api/products")  # Handle double-slash
async def get_products(
    category: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None
):
    query = {}
    if category:
        query["category"] = category.lower()
    if min_price or max_price:
        query["price"] = {}
        if min_price:
            query["price"]["$gte"] = min_price
        if max_price:
            query["price"]["$lte"] = max_price
    
    products = await products_collection.find(query).to_list(1000)
    return products

# Admin Endpoints (Fixed 404 error)
@app.post("/api/admin/login")
@app.post("//api/admin/login")  # Handle double-slash
async def admin_login(login_data: AdminLogin):
    admin = await admins_collection.find_one({"email": login_data.email})
    if not admin or not verify_password(login_data.password, admin["password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin credentials"
        )
    
    access_token = create_access_token(
        data={"sub": admin["email"], "role": "admin"},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return {
        "message": "Admin login successful",
        "access_token": access_token,
        "token_type": "bearer"
    }

# Cart Endpoints
@app.post("/api/cart/add", status_code=201)
async def add_to_cart(
    item: CartItem,
    user: dict = Depends(get_current_user)
):
    product = await products_collection.find_one({"id": item.product_id})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    await cart_collection.update_one(
        {"user_id": user["id"], "product_id": item.product_id},
        {"$set": {"quantity": item.quantity}},
        upsert=True
    )
    return {"message": "Item added to cart"}

# Order Endpoints
@app.post("/api/orders/create", response_model=Order, status_code=201)
async def create_order(
    order_data: Order,
    user: dict = Depends(get_current_user)
):
    order_data.user_id = user["id"]
    await orders_collection.insert_one(jsonable_encoder(order_data))
    await cart_collection.delete_many({"user_id": user["id"]})
    return order_data

# ====== Startup Initialization ======
@app.on_event("startup")
async def startup_db():
    """Initialize sample data"""
    if await admins_collection.count_documents({}) == 0:
        admin = Admin(
            name="Admin",
            email="admin@vishaljewellers.com",
            password=hash_password("admin123"),
            role="admin"
        )
        await admins_collection.insert_one(jsonable_encoder(admin))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
