from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel
import os

app = FastAPI()

# Allow CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# MongoDB Connection
MONGO_URI = "mongodb+srv://halabe8690:0U7oU4GKtkiQsBGx@cluster0.a9ui5gv.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
client = AsyncIOMotorClient(MONGO_URI)
db = client.vishal_jewellers

# Handle both /api/products and //api/products
@app.get("/api/products")
@app.get("//api/products")  # Fix for double-slash issue
async def get_products():
    products = await db.products.find().to_list(1000)
    return products

@app.get("/")
async def root():
    return {"message": "Vishal Jewellers API is running!"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
