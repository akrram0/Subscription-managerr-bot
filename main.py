from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import add_subscription

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.post("/add_subscription")
async def create_subscription(data: dict):
    sub_id = await add_subscription(
        data["user_id"],
        data["service_name"],
        float(data["cost"]),
        data["currency"],
        data["billing_cycle"],
        data["next_payment_date"]
    )
    return {"status": "success", "id": sub_id}
