import os
from PIL import Image
from fastapi.testclient import TestClient
from app.main import app

# Create dummy valid images
Image.new("RGB", (100, 100), color="blue").save("dummy_user.jpg")
Image.new("RGB", (100, 100), color="red").save("dummy_cloth.jpg")

client = TestClient(app)

print("Starting API test...")
with open("dummy_user.jpg", "rb") as user_img, open("dummy_cloth.jpg", "rb") as cloth_img:
    response = client.post("/tryon/", files={
        "user_image": ("dummy_user.jpg", user_img, "image/jpeg"),
        "cloth_image": ("dummy_cloth.jpg", cloth_img, "image/jpeg")
    })

print(f"Status Code: {response.status_code}")
print(f"Response: {response.json()}")

# Cleanup
os.remove("dummy_user.jpg")
os.remove("dummy_cloth.jpg")
